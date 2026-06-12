#!/usr/bin/env python3
"""
2_train.py — QLoRA fine-tune Qwen2.5-7B-Instruct on Twin-2K-500 survey responses

Run on RunPod (RTX A6000 48GB) after 1_prepare_data.py has created data/train.jsonl.

Typical runtime: ~30-60 min for ~22K examples, 2 epochs on RTX A6000.

Loss is computed on the assistant answer only (see train_on_responses_only below) —
we want to shift the *response distribution* toward human biases, not teach the model
to reproduce the persona blocks and survey questions.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import torch
import yaml

# Backport torch.nn.Module.set_submodule — added in torch 2.6, required by
# transformers 5.x bitsandbytes quantizer. Safe to add: it's just setattr
# navigated through the module tree, identical to the upstream implementation.
if not hasattr(torch.nn.Module, "set_submodule"):
    def _set_submodule(self, target: str, module: torch.nn.Module) -> None:
        atoms = target.split(".")
        name = atoms.pop()
        mod = self
        for atom in atoms:
            mod = getattr(mod, atom)
        setattr(mod, name, module)
    torch.nn.Module.set_submodule = _set_submodule  # type: ignore[attr-defined]

# Redirect HuggingFace downloads to /workspace if available.
# RunPod container disks are small (~20GB); /workspace has TB of space.
# Must be set before any HF/unsloth imports touch the cache path.
if Path("/workspace").is_dir():
    _hf_cache = "/workspace/hf_cache"
    os.environ.setdefault("HF_HOME", _hf_cache)
    os.environ.setdefault("HF_HUB_CACHE", f"{_hf_cache}/hub")
    os.environ.setdefault("TRANSFORMERS_CACHE", f"{_hf_cache}/hub")

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

    # Force-load torch._inductor.config so unsloth_zoo can inspect it.
    # The submodule exists in torch 2.4 but isn't auto-loaded as an attribute.
    import torch._inductor.config  # noqa: F401
    # Unsloth must be imported before transformers
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from datasets import load_dataset as hf_load_dataset
    from trl import SFTTrainer, SFTConfig

    # Resolve local HF cache path so unsloth doesn't re-download.
    # Unsloth's fast-download ignores HF_HOME env vars; passing the local
    # snapshot path directly bypasses the download entirely.
    model_name = model_cfg["base"]
    hf_home = os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
    _slug = model_name.replace("/", "--")
    _snapshots = Path(hf_home) / "hub" / f"models--{_slug}" / "snapshots"
    if _snapshots.exists():
        _snaps = sorted(_snapshots.iterdir())
        if _snaps:
            model_name = str(_snaps[-1])
            print(f"  Using cached model: {model_name}")

    print(f"Loading base model: {model_cfg['base']}")
    print(f"  4-bit quantization: {model_cfg['load_in_4bit']}")
    print(f"  Max seq length: {model_cfg['max_seq_length']}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
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

    # Anchor relative output paths to this script's directory, not the CWD —
    # run_job.sh runs from the repo root while 3_eval.py defaults to
    # <script-dir>/checkpoints/final.
    out_root = Path(train_cfg["output_dir"])
    if not out_root.is_absolute():
        out_root = Path(__file__).parent / out_root

    import inspect
    sft_kwargs = dict(
        dataset_text_field="text",
        # packing must stay off: train_on_responses_only masks labels per example,
        # which packing's sequence concatenation breaks.
        packing=False,
        output_dir=str(out_root),
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
    )
    # TRL ≥0.13 renamed SFTConfig.max_seq_length → max_length.
    sft_params = inspect.signature(SFTConfig.__init__).parameters
    seq_key = "max_seq_length" if "max_seq_length" in sft_params else "max_length"
    sft_kwargs[seq_key] = model_cfg["max_seq_length"]

    trainer_kwargs = dict(
        model=model,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        args=SFTConfig(**sft_kwargs),
    )
    try:
        trainer = SFTTrainer(tokenizer=tokenizer, **trainer_kwargs)
    except TypeError:  # TRL ≥0.13 renamed tokenizer → processing_class
        trainer = SFTTrainer(processing_class=tokenizer, **trainer_kwargs)

    # Mask everything before the assistant turn so loss is computed only on the
    # {"answer": ...} completion — the human response distribution we want to learn.
    # Markers match the ChatML template applied above.
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    print("Training...")
    trainer_stats = trainer.train()
    print(f"\nTraining complete. {trainer_stats.metrics}")

    out_dir = out_root / "final"
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
