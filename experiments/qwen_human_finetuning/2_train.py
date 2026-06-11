#!/usr/bin/env python3
"""
2_train.py — QLoRA fine-tune Qwen2.5-7B-Instruct on Twin-2K-500 survey responses

Run on RunPod (RTX A6000 48GB) after 1_prepare_data.py has created data/train.jsonl.

Typical runtime: ~3-4 hours for 100K examples, 2 epochs on RTX A6000.
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch
import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()
    model_cfg = cfg["model"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]
    hub_cfg = cfg.get("hub", {})

    data_dir = Path(__file__).parent / "data"
    train_path = data_dir / "train.jsonl"
    val_path = data_dir / "val.jsonl"

    if not train_path.exists():
        print(f"ERROR: {train_path} not found. Run 1_prepare_data.py first.")
        sys.exit(1)

    # Unsloth must be imported before transformers
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    from datasets import load_dataset as hf_load_dataset
    from trl import SFTTrainer, SFTConfig

    print(f"Loading base model: {model_cfg['base']}")
    print(f"  4-bit quantization: {model_cfg['load_in_4bit']}")
    print(f"  Max seq length: {model_cfg['max_seq_length']}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_cfg["base"],
        max_seq_length=model_cfg["max_seq_length"],
        load_in_4bit=model_cfg["load_in_4bit"],
        dtype=None,  # auto-detect bfloat16 / float16
    )

    # ChatML template is what Qwen2.5-Instruct uses natively
    tokenizer = get_chat_template(tokenizer, chat_template="chatml")

    print("Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg["target_modules"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias="none",
        use_gradient_checkpointing="unsloth",  # saves ~30% VRAM vs standard
        random_state=42,
    )

    print("Loading dataset...")
    train_ds = hf_load_dataset("json", data_files=str(train_path), split="train")
    val_ds = hf_load_dataset("json", data_files=str(val_path), split="train")

    def apply_template(batch: dict) -> dict:
        return {
            "text": [
                tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
                for msgs in batch["messages"]
            ]
        }

    train_ds = train_ds.map(apply_template, batched=True, remove_columns=["messages"])
    val_ds = val_ds.map(apply_template, batched=True, remove_columns=["messages"])

    print(f"  Train: {len(train_ds):,} examples")
    print(f"  Val:   {len(val_ds):,} examples")
    print(f"\nSample tokenized input:\n{train_ds[0]['text'][:300]}...\n")

    use_bf16 = torch.cuda.is_bf16_supported()
    print(f"Mixed precision: {'bf16' if use_bf16 else 'fp16'}")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        args=SFTConfig(
            dataset_text_field="text",
            max_seq_length=model_cfg["max_seq_length"],
            packing=True,             # pack multiple short examples per sequence — faster
            output_dir=train_cfg["output_dir"],
            num_train_epochs=train_cfg["num_epochs"],
            per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
            gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
            learning_rate=train_cfg["learning_rate"],
            warmup_steps=train_cfg["warmup_steps"],
            save_steps=train_cfg["save_steps"],
            logging_steps=train_cfg["logging_steps"],
            eval_strategy="steps",
            eval_steps=train_cfg["save_steps"],
            fp16=not use_bf16,
            bf16=use_bf16,
            optim="adamw_8bit",
            lr_scheduler_type="cosine",
            seed=42,
            report_to="none",
        ),
    )

    print("Training...")
    trainer_stats = trainer.train()
    print(f"\nTraining complete. {trainer_stats.metrics}")

    out_dir = Path(train_cfg["output_dir"]) / "final"
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"\nSaved fine-tuned model → {out_dir}")

    if hub_cfg.get("push_to_hub") and hub_cfg.get("repo_id"):
        repo = hub_cfg["repo_id"]
        print(f"Pushing to HuggingFace Hub: {repo}")
        model.push_to_hub(repo)
        tokenizer.push_to_hub(repo)
        print(f"  Done — https://huggingface.co/{repo}")

    print("\nNext step: python 3_eval.py")


if __name__ == "__main__":
    main()
