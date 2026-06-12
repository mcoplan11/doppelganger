# Centaur-70B Bias Experiment Eval

Evaluates [`marcelbinz/Llama-3.1-Centaur-70B`](https://huggingface.co/marcelbinz/Llama-3.1-Centaur-70B) on the same 16 heuristics-and-biases studies used in `twin2k_replication/` and `qwen_human_finetuning/`.

**The question:** Does Centaur — a foundation model of human cognition fine-tuned on ~160K behavioral experiment trials — replicate the population-level cognitive biases that standard LLMs miss?

---

## What is Centaur?

Centaur (Binz et al., 2024) is Llama-3.1-70B fine-tuned on [Psych-101](https://huggingface.co/datasets/marcelbinz/Psych-101), a dataset of ~160K human participants across hundreds of cognitive science experiments. The model is trained to predict trial-by-trial human responses in natural language.

**Key difference from our other models:** Centaur uses `<<...>>` tokens to mark human choices:
```
You see a big black square. You press <<K>>. The correct category is K.
You press <<L>> and get 84.0 points.
```

This eval uses **constrained logit masking** — instead of parsing JSON, we prompt ending in `"You press <<"` and force the model to emit only valid answer tokens (e.g., `A`/`B` for choice, `1`–`7` for scale). Open numeric questions use short free-text generation + regex.

---

## Prompting design

Each prompt includes the Doppelganger persona description (for individual-level variation across 150 participants) followed by the scenario and question in clean natural language — no `Return JSON` instruction. The `"You press <<"` suffix is appended by the client.

For the two-pass studies (`false_consensus`, `risk_benefit`), prior answers are injected in Centaur's `<<X>>` format:
```
YOUR PREVIOUS ANSWERS:
Do you personally support or oppose: 'Carbon tax'? → You answered <<Somewhat support>>

What percentage (0-100) of the public supports: 'Carbon tax'?

You press <<
```

---

## Hardware requirements

| GPU | VRAM | Status | RunPod price |
|-----|------|--------|------|
| **A100 80GB SXM** | 80 GB | ✓ Recommended | ~$2.39/hr |
| **A100 80GB PCIe** | 80 GB | ✓ Works | ~$1.99/hr |
| H100 80GB NVL | 80 GB | ✓ Fastest | ~$3.99/hr |
| 2× A40 48GB | 96 GB combined | ✓ Works (slower) | ~$2.00/hr |
| A6000 48GB (single) | 48 GB | ✗ Too small | — |

70B in 4-bit (NF4) uses ~38 GB VRAM for weights. Inference batch_size=8 adds ~5 GB.

---

## Setup

```bash
# 1. SSH into RunPod pod, clone repo
git clone https://github.com/mcoplan11/doppelganger.git
cd doppelganger

# 2. Install dependencies (~3 min)
bash experiments/centaur_eval/runpod/setup.sh

# 3. Set HuggingFace token (Meta Llama 3.1 license required)
#    Accept license at: https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct
export HF_TOKEN=hf_your_token_here

# 4. Run full eval (~1-2 hours)
bash experiments/centaur_eval/runpod/run_job.sh
```

### Running steps individually

```bash
cd experiments/centaur_eval

# Run all 16 experiments
python eval.py

# Single experiment
python eval.py --experiment framing

# List all experiment IDs
python eval.py --list

# Re-analyze existing results (no GPU needed)
python eval.py --analyze

# Alternate model or local checkpoint
python eval.py --model-path /workspace/my_model/
```

---

## Files

| File | Purpose |
|------|---------|
| `eval.py` | Main eval script — `LocalCentaurClient` + runners + analysis |
| `config.yaml` | Model ID, temperature, n_personas, batch_size |
| `requirements.txt` | pip dependencies (inference only, no training stack) |
| `runpod/setup.sh` | One-shot environment setup |
| `runpod/run_job.sh` | Full pipeline: HF login → download → eval |
| `results/` | Output JSON per experiment + `report.md` |

---

## Key config options

| Setting | Default | Notes |
|---------|---------|-------|
| `model.id` | `marcelbinz/Llama-3.1-Centaur-70B` | HF model ID or local path |
| `eval.n_personas` | `150` | Samples per condition |
| `eval.temperature` | `0.7` | Higher than other runs — more variation from population distribution |
| `eval.batch_size` | `8` | Lower than Qwen-7B due to model size; reduce to 4 if OOM |
| `eval.between_subject_mode` | `within` | Every persona sees every condition |

---

## Estimated cost (A100 80GB PCIe, $1.99/hr)

| Step | Time | Cost |
|------|------|------|
| Model download (37 GB) | ~20 min | ~$0.66 |
| 16 experiments × 150 personas (constrained decoding) | ~30-60 min | ~$1-2 |
| **Total** | **~1-1.5 hr** | **~$2-3** |

Constrained decoding (single forward pass per batch) is much faster than `generate()` — the bottleneck is model loading and the two-pass experiments.

---

## Interpreting results

The output table compares Centaur's results to the Twin-2K-500 paper (digital twins built from real respondents' prior answers). "Replicated" means the expected directional effect is statistically significant (p < 0.05).

**Benchmarks:**
- Twin-2K-500 digital twins (Toubia et al., 2025): ~7/15 effects replicated  
- Qwen3-30B via API (our `twin2k_replication` run): see `results/20260608_211042/`
- Qwen2.5-7B base: see `qwen_human_finetuning/results/base/`
- Qwen2.5-7B fine-tuned on human data: see `qwen_human_finetuning/results/finetuned/`

---

## Citation

```bibtex
@article{binz2024centaur,
  title={Centaur: A Foundation Model of Human Cognition},
  author={Binz, Marcel and Akata, Elif and Bethge, Matthias and others},
  journal={arXiv:2410.20268},
  year={2024}
}
```
