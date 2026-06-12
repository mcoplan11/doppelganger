# Qwen Human Fine-Tuning Experiment

## Goal

Standard LLMs respond to behavioral economics survey questions too rationally — they don't
reliably exhibit the cognitive biases and heuristics that real humans show (framing effects,
conjunction fallacy, anchoring, sunk cost, etc.).

This experiment tests whether **fine-tuning on real human survey responses** can fix that.
We fine-tune `Qwen2.5-7B-Instruct` using QLoRA on data from the
[Twin-2K-500 dataset](https://huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500)
(Toubia et al. 2025) — 2,058 participants answering 16 classic heuristics-and-biases studies —
and compare how many studies show the expected human bias effect before and after fine-tuning.

The hypothesis: a model trained on human answers will produce response distributions that
replicate population-level cognitive biases, making it a better stand-in for human survey
respondents in downstream research.

---

## The Three-Step Pipeline

```
Step 0 — Data prep        Twin-2K-500  →  data/train.jsonl   (cheap; fails fast)
Step 1 — Baseline eval    Base Qwen2.5-7B (no fine-tuning)  →  results/base/
Step 2 — Fine-tune        QLoRA training                     →  checkpoints/final/
Step 3 — Fine-tuned eval  Fine-tuned model                   →  results/finetuned/
```

All output paths (`data/`, `checkpoints/`, `results/`) are anchored to the
experiment directory regardless of the current working directory, so the
one-shot `run_job.sh` and the step-by-step commands write to the same places.

Both evals run the same 16 experiments with 150 AI personas each (within-subject),
producing a side-by-side table showing which studies "work" before and after fine-tuning.

---

## Experiment Design

### Training data: Twin-2K-500

The dataset contains real survey responses from 2,058 participants across 16 behavioral
economics studies. We use **400 participants** (the first 400 by sorted pid), mapping each
to one of our 200 AI personas:

```
pid 1   → biology_student_19f
pid 2   → retail_cashier_22m
...
pid 200 → (last persona)
pid 201 → biology_student_19f   (second participant for this persona)
pid 202 → retail_cashier_22m
...
pid 400 → (last persona)        (2 participants per persona, then stop)
```

Using 2 participants per persona is appropriate for LoRA: enough distributional signal
(each persona sees two real humans' answers) without noisy contradictory targets from
10+ different people.

### Training format

Each training example is a (prompt, answer) pair in ChatML format:

```
<|im_start|>user
You are responding to a Qualtrics survey, staying fully in character as this persona:

PERSONA: biology_student_19f
19-year-old biology student at a state university in Illinois...

Answer as this persona would — with their biases, blind spots, and rhythm.
Do not be artificially neutral or balanced.

[question scenario and options]

Return JSON: {"answer": ...}
<|im_end|>
<|im_start|>assistant
{"answer": "A"}
<|im_end|>
```

### Multi-question context (sequential studies)

For studies with multiple questions, each training example includes prior answers as context
— matching what participants actually saw on screen. This is critical for:

| Study | Prior context included |
|---|---|
| **false_consensus** public estimates (QID290) | All 10 own-view policy answers (QID287) |
| **risk_benefit** risk ratings (QID289) | Benefit rating for the same item (QID288) |
| **probability_matching** shuffle/roll N | All N-1 prior predictions |
| **linda** row 3 (bank teller) | Rows 1 and 2 answers |

Example (false consensus — public estimate):

```
YOUR ANSWERS SO FAR (stay consistent with these):
  Do you personally support or oppose: 'Placing a tax on carbon emissions'?
    → Somewhat support
  Do you personally support or oppose: 'Expanding Medicare to cover all Americans'?
    → Strongly support
  ...

What percentage (0–100) of the public do you think supports:
'Placing a tax on carbon emissions'

Return JSON: {"answer": <number>}
```

**The eval mirrors this:** for false_consensus and risk_benefit, `3_eval.py` runs
a two-pass protocol — it asks the first-stage questions (own views / benefit
ratings) first, then injects each persona's actual answers as the same
"YOUR ANSWERS SO FAR" block in the second-stage prompts. Without this, the
conditional the model learns in training (e.g. public estimate given own views)
could never activate at eval time, and the correlation would have to come purely
from persona consistency across independent calls.

### Twin-2K scenario differences

Twin-2K uses different scenario versions for some studies. Training uses the Twin-2K
scenarios; evaluation uses `experiments.json` scenarios. This is intentional — we're
teaching the model human-like *response patterns*, not memorizing specific scenarios.

| Study | Twin-2K version | Our eval version |
|---|---|---|
| Sunk cost | Coffee shop ($50 loyalty card) | Ski trip ($100 ticket) |
| Anchoring | African countries / Redwood tree | Mississippi River / Redwood tree |
| WTA/WTP | Vaccine risk scenarios | Lottery tickets |

**`less_is_more` is excluded from training:** Twin-2K stores it as 5-point
agree/disagree ratings about gambles while the eval asks dollar WTP for ice
cream — no format or construct overlap, so those examples would only add noise.
Its eval result is effectively a no-training control.

### Answer-format alignment (training format must match the eval)

Several studies are stored in a different response format in Twin-2K than the
eval asks for. Training re-encodes them so the trained format and direction match
the eval. `1_prepare_data.py` prints a `[NOTE]` for each MC-as-scale case and a
`[WARN]` if the option count and eval-scale length ever diverge.

| Study | Twin-2K | Eval | Training encoding |
|---|---|---|---|
| outcome_bias | 7-option MC (bad→good) | 1–7 scale (bad→good) | integer option-rank, aligned directly |
| myside | 6-option MC, "should it be **banned**?" (no→yes) | 1–6, "should it be **allowed**?" (yes→no) | integer option-rank — ban↔allow + scale flip cancel |
| framing | 6-point favor-A↔favor-B preference | binary A/B choice | collapsed to the favored program, binary A/B prompt |
| wta_wtp | MC dollar buckets ($10 … $5,000,000 or more) | open dollar amount | bucket's dollar value as a numeric answer |

As a final guard, the eval client validates every parsed answer against the
question's schema: stray option letters are mapped to option ids by position,
and out-of-range or unparseable answers are counted as errors rather than
silently scored as the non-risky option.

### Dataset size (~20.8K examples, measured)

| Study | Type | Examples |
|---|---|---|
| false_consensus (10 policies × own + public) | Complex | ~8,000 |
| probability_matching (10 shuffles + 6 rolls) | Complex | ~3,200 |
| risk_benefit (4 items × benefit + risk) | Complex | ~3,200 |
| linda (3 rows × 2 conditions) | Complex | ~1,200 |
| dominator_neglect (6 variants) | Complex | ~800 |
| Framing, anchoring, savings, allais, sunk cost, etc. | Simple between/within | ~4,400 |

---

## Setup and Running

### Requirements

- RunPod pod: **RTX A6000 48GB**, $0.49/hr
- Python 3.11, CUDA 12.1

### One-shot run

```bash
# 1. SSH into RunPod pod, clone the repo
git clone https://github.com/mcoplan11/doppelganger.git
cd doppelganger

# 2. Install dependencies (~5 min)
bash experiments/qwen_human_finetuning/runpod/setup.sh

# 3. Run full pipeline (~1.5–2 hours)
bash experiments/qwen_human_finetuning/runpod/run_job.sh
```

### Running steps individually

```bash
cd experiments/qwen_human_finetuning

# Preview training examples (no files written, no GPU needed)
python 1_prepare_data.py --preview

# Build dataset (~5 min)
python 1_prepare_data.py

# Baseline eval — base Qwen, no fine-tuning (~30 min, needs GPU)
python 3_eval.py --model-path Qwen/Qwen2.5-7B-Instruct --out-label base

# Fine-tune (~30-45 min on RTX A6000)
python 2_train.py

# Fine-tuned eval (~30 min, needs GPU)
python 3_eval.py --out-label finetuned

# Side-by-side comparison (any time after both evals have run)
python 3_eval.py --compare
```

---

## Files

| File | Purpose |
|---|---|
| `config.yaml` | All hyperparameters — model, LoRA, training, eval |
| `1_prepare_data.py` | Download Twin-2K-500, build SFT JSONL |
| `2_train.py` | QLoRA fine-tuning via Unsloth + TRL SFTTrainer |
| `3_eval.py` | Run 16 bias experiments; compare base vs fine-tuned |
| `requirements_runpod.txt` | pip dependencies for RunPod |
| `runpod/setup.sh` | One-shot environment setup on RunPod |
| `runpod/run_job.sh` | Full 3-step pipeline in one command |

---

## Key config options

| Setting | Default | Notes |
|---|---|---|
| `model.base` | `Qwen/Qwen2.5-7B-Instruct` | Base model to fine-tune |
| `model.max_seq_length` | `2048` | Must be ≥2048 to fit multi-question prompts |
| `data.max_per_persona` | `2` | Twin-2K participants per AI persona (400 total) |
| `lora.r` | `16` | LoRA rank — higher = more capacity, more VRAM |
| `training.num_epochs` | `2` | More epochs risks overfitting on ~22K examples |
| `eval.n_personas` | `150` | Personas per study (within-subject, matches twin2k_replication) |
| `eval.between_subject_mode` | `within` | Every persona sees every condition |
| `eval.batch_size` | `32` | GPU generations per batch during eval; lower if OOM |
| `hub.push_to_hub` | `false` | Set to `true` + add `repo_id` to publish the model |

---

## Estimated cost (RTX A6000, $0.49/hr)

Each eval is ~8,000 generations (within-subject: every persona × every condition;
false_consensus alone is 150 × 10 × 2 = 3,000). `LocalQwenClient` batches these on the
GPU (`eval.batch_size`, default 32), so a run is ~15–25 min rather than the ~2–3 hr a
one-at-a-time loop would take. Times below assume batched inference.

| Step | Time | Cost |
|---|---|---|
| Step 0 — Data prep (~21K examples) | ~5 min | ~$0.04 |
| Step 1 — Baseline eval (150 personas × 16 studies, ~8K gens) | ~20 min | ~$0.16 |
| Step 2 — Fine-tuning (2 epochs, ~21K examples, completion-only loss) | ~30–60 min | ~$0.40 |
| Step 3 — Fine-tuned eval | ~20 min | ~$0.16 |
| **Total** | **~1.5–2 hr** | **~$0.80** |

---

## Interpreting results

The eval output is a table of effect sizes and p-values for each of the 16 studies,
identical in format to `twin2k_replication/`. A study "works" if the expected directional
effect is significant (e.g., more participants choose the risky option in the loss frame
than the gain frame for framing; conjunction rated more probable than single for linda).

**Caveat — `omission_bias`:** Twin-2K only fields the commission condition (QID291), so
training contains just that half of the contrast. The eval is a 2-condition within-subject
comparison, so the omission/commission *effect* can't be learned from this data — read its
fine-tuned result as noise, not signal.

A successful fine-tuning run should show more studies reaching significance in the
fine-tuned column than the base column. If the improvement is small, the next steps are:
1. Increase `data.max_per_persona` (use more human training data per persona)
2. Add per-study example capping to fix imbalance between complex and simple studies
3. Increase `training.num_epochs`
