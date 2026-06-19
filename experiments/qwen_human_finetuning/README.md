# Qwen Human Fine-Tuning Experiment

> **The authoritative design doc is [`GROUNDED_PERSONAS_PLAN.md`](GROUNDED_PERSONAS_PLAN.md).**
> This README is the operational quick-start; the plan has the rationale, the pre-flight
> audits, and the success criteria. Read the plan before spending GPU.

## Goal

Standard LLMs respond to behavioral-economics survey questions too rationally — they don't
reliably exhibit the cognitive biases real humans show (framing, conjunction fallacy,
anchoring, sunk cost, etc.). This experiment tests whether **fine-tuning on real human survey
responses, with personas grounded in real demographic clusters**, makes a model reproduce
population-level biases well enough to pre-test a study before fielding it on humans.

We fine-tune **`Qwen3-30B-A3B`** (MoE) with bf16 LoRA on the
[Twin-2K-500 dataset](https://huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500)
(Toubia et al. 2025) — 2,058 participants across 16–17 heuristics-and-biases studies — then
re-run the studies base-vs-fine-tuned and count which human effects replicate.

---

## The core fix this experiment tests (the "grounding")

The earlier pipeline mapped participants to personas by `i % n` (sorted-pid position), so the
persona text was **statistically independent** of the human answers it trained on — the model
could only learn the population marginal, never demographic→behavior. The grounded pipeline
clusters all 2,058 participants on demographics, writes one readable persona per cluster
(`data/personas_generated.json`, K=200), and maps every pid to its cluster persona
(`data/pid_to_persona.json`). Run A vs Run 0 isolates exactly this change.

---

## Pipeline

```
Stage 1/2 (done)  Cluster participants → grounded personas → SFT JSONL
                  data/{personas_generated,pid_to_persona}.json
                  data/{train,val}.jsonl   (≈100K train / 6.5K val, persona-grouped split)

Stage 3 (GPU)     Phase-1 matrix on Qwen3-30B-A3B:
                  base_30b        — untrained reference
                  run0_fictional  — FT on fictional i%n map (baseline to beat)
                  runA_grounded   — FT on grounded clustered map (the fix)
```

`1_prepare_data.py` (build JSONL) → `2_train.py` (bf16 LoRA) → `3_eval.py` (run studies).

### Training data

All **2,058** participants are used (grounded mode), each mapped to its demographic-cluster
persona. Each example is a (prompt, answer) pair in ChatML; loss is computed on the assistant
answer only (`train_on_responses_only`). Multi-question studies inject prior answers as
`YOUR ANSWERS SO FAR` context, matching what participants saw on screen:

| Study | Prior context included |
|---|---|
| **false_consensus** public estimates | all 10 own-view policy answers |
| **risk_benefit** risk ratings | benefit rating for the same item |
| **probability_matching** shuffle/roll N | all N-1 prior predictions |
| **linda** row 3 | rows 1 and 2 |

### Twin-2K scenario differences (intentional)

Training uses the Twin-2K scenario wording; eval uses `experiments.json` wording. Training on
the survey wording and testing on a paraphrase makes the eval a *generalization* test, not a
memorization check (see plan §2.2). Some studies are therefore **transfer-only** (different
answer space at train vs eval) — judge those as transfer, not in-sample.

| Study | Twin-2K version | Eval version |
|---|---|---|
| Sunk cost | Coffee shop ($50 card) | Ski trip |
| Anchoring | African countries / Redwood | Mississippi River / Redwood |
| Less is more | gambles (EXCLUDED from training) | ice cream cups |
| WTA/WTP | vaccine risk (encoded as $) | lottery tickets |

---

## Setup and running

### Requirements

- RunPod pod: **A100 80GB SXM** (~$1.49/hr). bf16 LoRA on 30B-A3B ≈ 60GB VRAM.
  Fallback if it won't fit: dense `Qwen3-14B` + `load_in_4bit: true` (loses MoE rehearsal).
- Python 3.11, CUDA 12.x

### Pre-flight (GPU-free, run before launching the pod)

```bash
cd experiments/qwen_human_finetuning
python 1_prepare_data.py --grounded --cap-per-study 3000   # confirm ~example counts + data-quality FLAGS
python prompt_parity_check.py        # in-sample vs transfer-only studies (exit 0)
python persona_signal_check.py       # per-study persona ICC — which studies grounding can move
```

### Full Phase-1 matrix (one command)

```bash
bash experiments/qwen_human_finetuning/runpod/run_phase1.sh
# CAP=0 bash .../run_phase1.sh        # to use the full uncapped ~100K instead of cap=3000
```

This runs `base_30b → run0_fictional → runA_grounded` (one variable per step), preserves both
fine-tuned checkpoints (`run0_final`, `runA_final`), and prints the three-way comparison.
`run_job.sh` is deprecated and just forwards here.

### Running steps individually

```bash
cd experiments/qwen_human_finetuning

# Base reference (same model as training — required for a clean base-vs-FT delta)
python 3_eval.py --model-path Qwen/Qwen3-30B-A3B --out-label base_30b

# Run 0 — fictional map (MUST pass --no-grounded, else it auto-detects grounded)
python 1_prepare_data.py --no-grounded --cap-per-study 3000
python 2_train.py
python 3_eval.py --out-label run0_fictional

# Run A — grounded map
python 1_prepare_data.py --grounded --cap-per-study 3000
python 2_train.py
python 3_eval.py --out-label runA_grounded

# Comparison (pass the labels — --compare alone defaults to base/finetuned)
python 3_eval.py --compare --compare-labels base_30b run0_fictional runA_grounded
```

---

## Files

| File | Purpose |
|---|---|
| `GROUNDED_PERSONAS_PLAN.md` | **Authoritative** design, audits, success criteria |
| `config.yaml` | Model / LoRA / training / eval hyperparameters |
| `personas_from_twin2k.py` | Stage 1 — cluster participants → grounded personas |
| `1_prepare_data.py` | Build SFT JSONL + pre-flight data-quality report |
| `2_train.py` | bf16 LoRA fine-tuning via Unsloth + TRL SFTTrainer |
| `3_eval.py` | Run the bias studies; `--compare` for side-by-side |
| `prompt_parity_check.py` | GPU-free in-sample-vs-transfer check |
| `persona_signal_check.py` | GPU-free per-study persona-ICC diagnostic |
| `runpod/run_phase1.sh` | The Phase-1 matrix in one command |
| `runpod/setup.sh` | One-shot RunPod environment setup |

---

## Key config options

| Setting | Default | Notes |
|---|---|---|
| `model.base` | `Qwen/Qwen3-30B-A3B` | MoE; fallback `Qwen3-14B` (dense) |
| `model.load_in_4bit` | `false` | bf16 LoRA — 4-bit QLoRA is unreliable on this MoE |
| `model.max_seq_length` | `2048` | bump to 4096 only if Phase-2 prompts overflow |
| `data.cap_per_study` | `null` | per-study downsample; scripts pass `--cap-per-study 3000` |
| `lora.r` / `lora_alpha` | `16` / `32` | first pass; tune only if Run A under-fits |
| `training.num_epochs` | `2` | more risks overfitting |
| `eval.n_personas` | `150` | sampled from the 200-persona Prolific roster |
| `eval.between_subject_mode` | `within` | every persona sees every condition (memoryless) |

---

## Cost (A100 80GB, ~$1.49/hr)

| Step | ~Time | ~Cost |
|---|---|---|
| base_30b eval | ~30 min | ~$0.8 |
| Run 0 (build + train + eval) | ~1–1.5 hr | ~$2 |
| Run A (build + train + eval) | ~1–1.5 hr | ~$2 |
| **Phase-1 total** | **~3–4 hr** | **~$5** |

The full <$100 budget (incl. the one-time 235B confirmation run on a B300) is in plan §7.

---

## Interpreting results

The eval output is a table of effect sizes and p-values per study, identical in format to
`twin2k_replication/`. The Phase-1 gate (plan §8): proceed to Phase 2 if Run A either
replicates clearly more of the 17 than Run 0, **or** moves the in-sample signal-bearing gate
study (`myside`) in the human direction without regressing what `base_30b`/Run 0 already pass.

Watch for the two known failure modes: **answer-format collapse** (a study at p≈1.000 / one
dominant answer token — not a replication) and **borderline regression** (a study `base_30b`
nearly passes degrading under FT). Persona-signal ICC ≈ 0.02, so expect Run A ≈ Run 0 on most
studies — a flat result is the finding "demographics don't predict these JDM biases," not a bug.
