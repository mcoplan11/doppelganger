# Grounded-Persona Fine-Tuning Plan (v2)

> **Status (2026-06-15):** Stages 1 and 2 are **complete**. Artifacts exist at
> `data/personas_generated.json` (200 clusters, K=200) and `data/pid_to_persona.json`
> (all 2,058 PIDs mapped). Training data built (`data/train.jsonl`, `data/val.jsonl`).
> `3_eval.py` updated to use the 200 hand-crafted Prolific-worker personas from
> `personas.py` / `responses/generated_v3.json` instead of `personas_generated.json`.
> **Next step: Stage 3 GPU runs on RunPod (Run 0 baseline FT, then Run A grounded FT).**
> **⚠ Before relaunching, read §2.3 — the first GPU attempt (2026-06-19/20) hit a chain of
> RunPod stack gotchas (volume too small, `lora_dropout` must be 0, and the binding one:
> Unsloth MoE needs Triton ≥3.3 so the pod must run PyTorch 2.8+). §2.3 has the known-good
> resume runbook. The experiment code/data/LoRA config are all correct — only the stack changed.**
>
> **⚠ Pre-flight audit (2026-06-15) — read §2.1 before any GPU spend.** Three issues
> were found and two fixed: (1) `train.jsonl` on disk was a **500-row smoke test**, not
> the real dataset — rebuilt to **107,028 examples** (all 2,058 participants); (2) a new
> per-study data-quality report + a `persona_signal_check.py` ICC diagnostic were added;
> (3) the **persona-signal ICC is ~0.02** (demographics barely predict these biases),
> which means grounded FT may not beat the fictional-map baseline on most studies, and
> the Phase-1 gate was rewritten to be winnable (§8). These don't block the run, but they
> reset expectations: see §2.1.
>
> **⚠ Pre-flight audit round 2 (2026-06-16) — read §2.2 before any GPU spend.** A
> code-level review found one **genuine bug, now FIXED**: a train/eval chat-template +
> thinking-mode mismatch in `3_eval.py` that would have collapsed *every* fine-tuned eval
> regardless of whether grounding works. A new GPU-free `prompt_parity_check.py` also
> showed that **4–5 studies (incl. the current gate `dominator_neglect`) are TRANSFER-ONLY**:
> training and eval use different *answer spaces*/elicitations, so SFT on them adds no
> *in-sample* signal toward their eval. This is an **interpretation fact, not a blocker**
> — scenario paraphrasing is by-design across the whole benchmark, and at eval the model
> reads the eval prompt, so nothing mechanically breaks. Implication: don't expect grounding
> to move those in-sample, and prefer a matched study for the gate's mechanism test. Three
> smaller fixes also landed (val-split leakage, signal diagnostic, render budget). See §2.2.

---

## 2.1 Pre-flight audit findings (2026-06-15) — reset expectations before Stage 3

A pre-GPU audit of the on-disk artifacts surfaced three things. All tooling lives in
`1_prepare_data.py` (report) and `persona_signal_check.py` (ICC); rerun both after any
data change.

1. **`train.jsonl` was a 500-row smoke test, now rebuilt to 107,028 examples.** The file
   committed as "Stage 2 done" had exactly 475 train + 25 val = 500 rows (the signature
   of a stray `--max-examples 500`). The real grounded build over all 2,058 participants
   yields **101,676 train / 5,352 val**. Training Stage 3 on the old file would have
   produced the answer-format collapse the decision log warns about and been misread as
   "grounding didn't help." `1_prepare_data.py` now prints a loud warning whenever
   `--max-examples` is set. **Always confirm the build prints ~100K examples and the
   "Loading grounded pid→persona mapping … 2058 participants" line before training.**

2. **Severe class imbalance.** Three multi-row matrix studies (`false_consensus` 41,160,
   `risk_benefit` 16,464, `probability_matching` 16,476) are **~69%** of the data, while
   the trainable gate studies (`wta_wtp` 2,058, `dominator_neglect` 4,116) are **~6%**.
   SFT will optimise the big studies and barely move the small ones. New lever:
   `--cap-per-study N` (recommend ~3000) downsamples each study before the split. The
   pre-flight report flags any >10× largest/smallest ratio. Decide whether Run A uses the
   cap (cleaner per-study gradient share) or the full set (faithful to "all 2,058").

3. **Persona signal is weak — the binding finding.** `persona_signal_check.py` computes,
   per study, the ICC(1) of condition-residualised human answers grouped by persona — i.e.
   how much of the answer variance persona membership explains, net of the manipulation.
   **Mean ICC ≈ 0.020.** Most studies are ~0; only `dominator_neglect` (0.063),
   `omission_bias` (0.060), `myside` (0.058), `savings` (0.046) carry any signal. This is
   the §3.1 caveat firing and corroborates the Mega-Study result quoted in §2 ("no higher
   than generic demographics-only personas"). **Implication:** fixing the i%n map (Run A)
   can only help where demographics actually separate behaviour — which is almost nowhere
   in this benchmark. Expect Run A ≈ Run 0 on most studies; the honest pre-registered
   prediction is that grounding moves at most `dominator_neglect` and maybe `myside`/
   `savings`. If Run A confirms this, the finding is "demographics don't predict these
   JDM biases" (publishable, per §6 Stage-1 note), not "the pipeline is broken." Base
   model capability (§2: 30B-A3B already 11/17) remains the dominant lever.

---

## 2.2 Pre-GPU audit round 2 (2026-06-16) — code review + stimulus parity

A code-level review of the train→eval path (not just the on-disk data) found one
breaking bug, one structural finding, and three smaller fixes. The four code fixes
are done; the structural finding needs a design decision (below).

### FIXED — train/eval chat-template + thinking-mode mismatch (`3_eval.py`)
Training (`2_train.py`) SFTs on **plain ChatML** (`get_chat_template(…, "chatml")`)
with the answer JSON emitted directly after the assistant tag. But `3_eval.py`'s
`_render` was applying the **base model's native Qwen3 template** (the LoRA-checkpoint
path loads the tokenizer from `base_id`, not the checkpoint) with `add_generation_prompt=True`
and **no `enable_thinking=False`**. Two consequences: (1) Qwen3 defaults to thinking ON,
so with `max_new_tokens=64` the model burns its budget in a `<think>` block and never
emits the JSON → **answer-format collapse**, which §10 says to read as "not replicated";
(2) the FT model was graded on a prompt surface it never trained on. This would have made
**every** FT run look broken — the exact "grounding didn't help" false negative the plan
is built to avoid. **Fix:** `_render` now reproduces plain ChatML byte-for-byte for FT
checkpoints (matching training) and forces `enable_thinking=False` on the base reference;
`max_new_tokens` raised to 128 for headroom. This is the §6 "thinking-mode mismatch
silently changes behavior" warning, made real and closed.

### STRUCTURAL FINDING — 4–5 studies are TRANSFER-ONLY (not a mechanical break)
New tool `prompt_parity_check.py` (GPU-free) compares the **answer space** the SFT data
teaches against the space `runner.py` grades on, per study (scenario wording is ignored —
see below). Result: the scale studies are **in-sample-compatible** (cosmetic gloss-text
differences only), `savings` is an order-dependent letter↔semantic enum (bridged by
`_coerce` if option order holds), and these are **transfer-only**, because training and
eval use different *answer spaces* / elicitations:

| Study | TRAIN (Twin-2K QID) | EVAL (`experiments.json`) | Difference |
|---|---|---|---|
| **dominator_neglect** (current GATE) | QID174–179 fire-extinguisher/seatbelt lives-saved, **5–6 options** | constructed "certain $50 vs 50% $50/$25" gamble, **2 options** | different elicitation + cardinality; possibly *proportion* vs *stochastic* dominance — verify the construct matches |
| omission_bias | QID, **4 options** | constructed flu vaccinate/skip, **2 options** | different elicitation + cardinality |
| probability_matching | per-round red/green predictions, **integer 1–2** | meta "maximize vs match" strategy, **enum** | different elicitation + type |
| sunk_cost | QID181/182_TEXT coffee-shop, **numeric** | classic Michigan/Wisconsin ski, **enum** | different elicitation + type |
| less_is_more | (no train examples — excluded from SFT) | scale | transfer-only by exclusion |

**Why this is NOT a blocker (corrected 2026-06-17 after review):** scenario paraphrasing
is the *existing, deliberate* design across the whole benchmark, not unique to these
studies — e.g. `framing` trains on "unusual disease" and evals on "unusual *Asian*
disease"; `anchoring_redwood` trains on the no-anchor wording and evals with the anchor
injected. Training on the survey wording and testing on a cleaner paraphrase is what makes
the eval a *generalization* test rather than a memorisation check — desirable. And at eval
the model is conditioned on the **eval** prompt (built fresh from `experiments.json`), so it
reads the eval's answer space directly and produces parseable output as long as it follows
instructions. The answer-space difference therefore does **not** mechanically break the eval.

**What actually follows:** for these studies the SFT teaches a *different task* than the
eval grades, so grounding adds **no in-sample signal** toward them — they are **transfer**
results, full stop. Two consequences: (1) don't read a flat Run-A result on them as "grounding
failed" — it was never an in-sample test; (2) the gate's rule (b) ("grounding *moved* study X")
should use an **in-sample, signal-bearing** study so it isolates the mechanism — the current
gate `dominator_neglect` reads as a transfer/construct test, so `myside` (scale-matched, ICC
0.058) is the cleaner mechanism gate (keep `dominator_neglect` as a reported transfer result).
Separately, **output collapse** (model emits a memorised token instead of following the eval
prompt; the 7B `savings` p=1.000) is a real but *distinct* SFT-overfitting risk — monitor it
via the eval's per-study no-response rate and the degenerate-label flag; it is, if anything,
likelier on the *matched* studies. Run `python prompt_parity_check.py` (always exits 0,
informational) to see the per-study in-sample/transfer split.

### FIXED — val-split persona leakage (`1_prepare_data.py:build_all_examples`)
The split was a random row slice, so the same persona (and persona×study pair) appeared in
both train and val — `val_loss` measured in-distribution fit and could never warn about
persona overfitting. Now a **group split by persona** (verified: 190 train / 10 val
personas, **0 overlap**), so `val_loss` is a real "generalizes to unseen personas" signal —
matching the inference condition (eval uses a disjoint Prolific roster). Rebuild is
100,498 train / 6,530 val.

### FIXED — signal diagnostic over-claimed; ICC has a single-item floor (`persona_signal_check.py`)
ICC(1) on single dichotomous/few-category items is downward-biased with a low ceiling, so
reading "mean ICC ≈ 0.02" as "demographics are irrelevant" overshoots. The tool now also
prints **`btwn_sd`** (between-persona SD of condition-residualised means, in answer units —
interpretable regardless of item reliability), a **gate-study callout** (`dominator_neglect`
ICC=0.063, *has* trainable signal), and a caveat that the product goal is **aggregate effect
replication, not per-respondent prediction**. Conclusion is unchanged (signal is weak) but
no longer overstated.

---

## 2.3 Stage-3 GPU launch log (2026-06-19/20) — RunPod environment gotchas, RESOLVED

First live attempt to run the Phase-1 matrix (`runpod/run_phase1.sh`) on RunPod surfaced a
chain of **environment/stack** problems — none in the experiment code itself. The data, the
LoRA config, and the model all proved correct (training reached the loop and produced the
right tokenized persona examples). Recorded here so the next session doesn't re-derive them.

**Order of failures hit, and the fix for each:**

1. **Disk-quota OOM during base-model download (`OSError: [Errno 122]`).** The HF-cache
   redirect to `/workspace` (in `run_phase1.sh`) works correctly, but the **network volume
   was too small** (~35GB) for the 30B-A3B bf16 base (~57GB across 16 shards). `df -h` is
   misleading on RunPod — `/workspace` shows the whole MooseFS cluster (`2.1P`), not your
   per-volume quota, so quota exhaustion only shows up as `EDQUOT` mid-download.
   **FIX: provision the `/workspace` network volume at ≥120GB** (base ~57GB + both LoRA
   checkpoints + dataset + headroom). Container disk 30GB is fine. The volume is persistent,
   so the cached base survives stop/start and pod redeploys — reattach it and nothing
   re-downloads.

2. **`lora_dropout != 0` rejected on MoE expert LoRA (`ValueError: lora.ParamWrapper does
   not work with lora_dropout != 0`).** The MoE-expert LoRA path (`ParamWrapper`, applied to
   `mlp.experts.gate_up_proj`/`down_proj`) forbids dropout. **FIX: `lora_dropout: 0.0` in
   `config.yaml`** (committed). This is independent of the Triton issue below — it applies on
   any stack.

3. **THE BINDING ONE — Unsloth MoE kernel needs Triton ≥3.3, the pod had 3.0
   (`AttributeError: module 'triton.language' has no attribute 'make_tensor_descriptor'`).**
   The default RunPod template was **Torch 2.4.0 + Triton 3.0.0**. Unsloth 2026.6.8's fused
   MoE grouped-GEMM kernel calls `tl.make_tensor_descriptor` (TMA API, added in Triton 3.3).
   `requirements_runpod.txt` pins `unsloth[cu121-torch240]`, whose extra controls only the
   torch/CUDA deps, **not** the Unsloth version — so pip pulled latest Unsloth onto an
   incompatible Triton.
   - The `UNSLOTH_MOE_BACKEND=native_torch` env var does **not** rescue it: the backend
     selector only governs the *base* expert forward, but the **LoRA `ParamWrapper` on the
     experts calls `forward_triton_grouped_gemm` unconditionally**. So as long as LoRA is on
     the MoE experts (which we want), the Triton kernel is forced regardless of the backend.
   - `native_torch` *does* eventually train if you drop expert LoRA, but the loop fallback ran
     at **~154 s/step → ~47 h / ~$70 for one run** on an A100 80GB. Unusable.
   - **FIX (the supported path): redeploy on a PyTorch 2.8+/2.9 template (Triton ≥3.4/3.5),
     reattach the same `/workspace` volume, and reinstall Unsloth WITHOUT re-pinning torch.**
     This is Unsloth's own documented MoE combo (Torch 2.9.1 / Triton 3.5.1 / transformers 5.x,
     **bf16 LoRA — not 4-bit**, which `config.yaml` already does). With the real kernel, expect
     seconds/step, not minutes.

**More gotchas hit during the 2026-06-20/21 runs (also RESOLVED):**

4. **Fresh container wipes all pip installs.** pip installs land on the **container disk**, not
   the `/workspace` network volume. A pod stop/start, redeploy, or brand-new pod loses every
   dep — even though the repo, data, and base-model cache survive on the volume. **FIX: re-run
   the installer on every fresh pod** (now one command: `runpod/setup_moe.sh`).
5. **`torchaudio`/`torchvision` ABI crash after the torch bump (`Could not load
   libtorchaudio.so`).** `--upgrade unsloth` pulls torch ~2.10, but torchaudio stays pinned to
   the template's torch 2.8; transformers 5.x imports torchaudio transitively (Parakeet RNNT
   loss) and dies on load. **FIX: `pip uninstall -y torchaudio torchvision`** — we use neither.
   (Folded into `setup_moe.sh`.)
6. **Eval couldn't load the MoE LoRA (`...Qwen3MoeRMSNorm... is not supported`).** `3_eval.py`
   loaded checkpoints with vanilla `PeftModel.from_pretrained`, which can't inject LoRA into the
   fused expert tensors. **FIX: load FT checkpoints via `FastLanguageModel.from_pretrained`**
   (mirrors training; committed in `3_eval.py`).
7. **Checkpoint pileup re-hit the disk quota (`os error 122`) at ~step 1050.** No
   `save_total_limit`, so every `save_steps` checkpoint accumulated. **FIX: `save_total_limit=1`**
   in `2_train.py` (committed).

**Cost lever (don't skip):** the task converges almost instantly — loss (train AND val) is flat
at ~0.20 by **step 150**. The full 2-epoch grounded run is 4,492 steps → ~13h/$22 of no-op
compute. `config.yaml` now caps `max_steps: 600` (4× past plateau) and `save_steps: 300`
(2 in-loop evals, each ~12 min on the 1.7k val set). Per run ≈ ~2h instead of ~13h. The cap is
identical for both arms, so the ablation stays clean. Set `max_steps: -1` to use full epochs.

**Known-good resume runbook (start here next session) — now ~2 commands:**

```bash
# Pod: A100 80GB SXM, PyTorch 2.8+ template (Triton >=3.4), /workspace volume >=120GB
#      reattached (base-model cache already on it). NEW POD = deps wiped, see #4.
cd /workspace/doppelganger && git pull

# 1. Install the correct MoE stack + gate check (NOT setup.sh — see #3). Re-run on every
#    fresh pod. Asserts Triton has make_tensor_descriptor before you spend GPU.
bash experiments/qwen_human_finetuning/runpod/setup_moe.sh

# 2. Full Phase-1 matrix in tmux (survives web-terminal disconnect).
#    run_phase1.sh now: skips base_30b if results/base_30b exists (committed to git),
#    builds Run 0 with --match-grounded-pids (clean 2,058-participant ablation), and
#    trains both arms capped at max_steps=600. CAP=3000 baked in.
tmux new -s phase1
bash experiments/qwen_human_finetuning/runpod/run_phase1.sh 2>&1 | tee /workspace/phase1.log
#   detach: Ctrl-b then d   |   reattach: tmux attach -t phase1
```

**Stage-3 results so far (2026-06-21):**
- `base_30b` (untrained reference) eval **DONE and committed to git** (`results/base_30b/`):
  **10/17 effects replicated** under the corrected significance-tested analyzers (see §10 /
  `analysis.py`). This is the bar the fine-tunes must beat.
- `run0_fictional` (matched, 2,058) and `runA_grounded` — **still to run** (one `run_phase1.sh`
  invocation does both, capped, then the 3-way compare). The old 400-participant Run 0 is
  superseded by the matched build.

**TODO once a fast run succeeds:** `pip freeze > experiments/qwen_human_finetuning/requirements_runpod.lock.txt`
to pin the working stack so the **235B confirmation run** (also MoE) doesn't repeat this. Also
update `requirements_runpod.txt` to a torch-2.8+ / Triton-3.4+ base and drop the
`[cu121-torch240]` extra. The MoE-stack lesson transfers directly to 235B-A22B (§3.6).

---

## 1. The goal

Build an LLM that **"thinks like a human"** on judgment-and-decision-making tasks, so that
behavioral scientists can **pre-test a study** — run it on synthetic respondents first — to
check whether there's likely a real effect before spending money fielding it on humans.

**Primary objective: minimize false negatives.** If a real human effect exists, the tool
should surface it. We *tolerate false positives* (tool says "effect" when there isn't one),
because users still run a real human study to publish — a false positive costs them one
wasted study; a false negative means they wrongly abandon a real finding.

**Hard constraint that protects the goal from collapsing:** a model that detects an effect in
*every* study is 100% sensitive and useless (a "yes-machine"). So while we bias toward
sensitivity, we must still **measure specificity** — see §4 and §8.

### Product framing
- The tool outputs **raw per-respondent data**, exactly like real Qualtrics participants.
  The user runs **their own stats** on it to decide if their effect is real. We do not output
  a binary verdict.
- Deployment-target note (unresolved, doesn't block the build): the live product
  (`doppelgangerlabs.com`) currently runs on Gemini; this experiment fine-tunes Qwen. Decide
  later whether the end goal is a self-hosted fine-tuned Qwen we serve, or research to inform
  Gemini prompting.

### Near-term scope (this milestone) — read this first

This is intentionally a **two-phase** effort. Do not build the whole thing at once.

- **Phase 1 (now): just replicate the 17 Twin-2K studies.** Get the grounded-persona fine-tune
  to reproduce the known human effects on the benchmark we already have wired up. This is the
  gate — if we can't replicate in-sample, nothing downstream matters.
- **Phase 2 (only if Phase 1 works): a true held-out test.** Treat the **19 studies from the
  follow-up Mega-Study paper (arXiv:2509.19088v3)** as an out-of-distribution test set the model
  has *never* trained on, and add a set of **known null effects** to confirm the model doesn't
  just predict an effect everywhere. This is the real test of whether we built a pre-test tool
  vs. a benchmark-overfit lookup table.

Everything below is organized around these two phases.

---

## 2. Where we are now

### Benchmark
We replicate the **16–17 heuristics-and-biases effects** from Table 3 of Toubia et al. (2025),
*Twin-2K-500* (arXiv:2505.17479). The paper's AI "digital twins" (built from real respondents'
prior answers) replicated **~7/15** effects. Our `twin2k_replication/` harness runs the same
studies against any model. **This is the Phase-1 (in-sample) benchmark.**

### Held-out benchmark (Phase 2): the Mega-Study
The follow-up paper — Peng, Gui, Merlau et al. (2025), *"A Mega-Study of Digital Twins Reveals
Strengths, Weaknesses and Opportunities for Further Improvement"* (arXiv:2509.19088v3) — runs
**19 diverse behavioral studies** on the same Twin-2K panel (accuracy nudges for misinformation,
default effects, context effects, privacy preferences, preferences for redistribution, hiring
algorithms, idea/creativity evaluation, recommendation-system behavior, etc.). These are
**not** heuristics-and-biases tasks, so they're a genuinely out-of-distribution test of
generalization. Notably, that paper found twins reached ~75% individual accuracy but only ~0.2
correlation with humans — **"no higher than generic demographics-only personas."** Two takeaways
for us: (a) it reinforces rejecting verbatim twins in favor of aggregate effect replication, and
(b) it's a caution that demographics may carry limited *individual*-level signal (relevant to
the K-sweep divergence check in §6).

### Current model results (zero-shot, reasoning off, within-subjects, N=150)
| Model | Effects replicated | Notes |
|---|---|---|
| Centaur-70B | 3/17 | mostly degenerate numeric output |
| qwen3-14b | 10/17 | dense; fails savings/base_rate/sunk_cost (capability gaps) + 4 "too rational" |
| qwen3-30b-a3b | 11/17 | MoE; fails anchoring_redwood + the canonical 5 "too rational" |
| qwen3-235b-a22b | 12/17 | MoE; canonical 5 "too rational" failures only |
| qwen3.7-max | 13/17 | |

The 4–5 consistent **failures** across the good models are all "**too rational**" cases —
the LLM doesn't fall for the bias because it reasons normatively:
`less_is_more`, `wta_wtp` (endowment), `omission_bias`, `dominator_neglect`
(+ `probability_matching` for 235b).

**Why 30B-A3B is the right fine-tuning proxy for 235B** (not 14B): (1) same MoE architecture
family — fine-tuning quirks (router stability, target modules) transfer directly; (2) failure
profile matches 235B almost exactly — 30B-A3B shares all 5 canonical "too rational" failures
with 235B, whereas 14B additionally fails on capability-limited studies (savings, base_rate,
sunk_cost) that 235B handles fine, meaning 14B fine-tuning would target the wrong deficits.

### Existing fine-tuning experiment (`experiments/qwen_human_finetuning/`)
QLoRA on Qwen2.5-7B using Twin-2K human answers, then re-run the 17 studies base-vs-finetuned.
**The core bug we are fixing:** `1_prepare_data.py:build_pid_to_persona` maps participants to
personas by **sorted-pid position mod 100** (`DEFAULT_PERSONAS[i % n]`). The persona text
("19-year-old construction worker…") is therefore **statistically independent** of the human
answers it's trained on. The model can only learn the *population marginal*, never
demographic→behavior. It also caps at 2 participants/persona = only 400 of 2,058 used.

**Results from this pilot (Qwen2.5-7B, N=150, within-subjects, 100 fictional Prolific-style personas):**

| Study | Paper | Base 7B | FT 7B (broken map) |
|---|---|---|---|
| Framing | ✓ | ✓ | ✓ |
| Linda | ✓ | ✓ | ✓ |
| Anchoring (Redwood) | ✓ | ✓ | ✓ |
| Anchoring (Mississippi) | ✗ | ✓ | ✓ |
| Savings | ✓ | ✗ | ✗ (p=1.000 — answer-format collapse) |
| Myside | ✓ | ✗ (p=0.086) | ✗ (p=0.571 — fine-tune made it worse) |
| Less is More | ✓ | ✗ | ✗ |
| WTA/WTP | ✓ | ✗ | ✗ |
| Sunk Cost | ✗ | ✗ | ✓ (p=0.027 — emerged from FT) |
| Outcome Bias | ✗ | ✓ | ✓ |
| Allais | ✗ | ✗ | ✗ |
| Base Rate | ✗ | ✓ | ✓ |
| False Consensus | ✓ | ✓ | ✓ |
| Risk-Benefit | ~ | ✓ | ✓ |
| Omission Bias | ✗ | ✗ | ✗ |
| Probability Matching | ✗ | ✗ | ✗ |
| Dominator Neglect | ✓ | ✗ | ✗ |
| **Total effects shown** | | **8/17** | **9/17** |

**Net gain from fine-tuning with broken map: +1 study (sunk_cost).** The 5 "too rational"
failures didn't move at all. This confirms the diagnosis: the persona-answer independence
bug is the binding constraint, not the fine-tuning approach itself.

**Lessons for Run 0 / Run A (see §10 for rationale):**
1. **+1 from broken FT vs. +3 from model size** — base capability is the dominant driver.
   30B-A3B base (11/17) already outperforms 7B fine-tuned (9/17) without any training.
   Run 0 (30B-A3B with broken map) should be the new baseline to beat, not the 7B results.
2. **Answer-format collapse is a real risk** — savings p=1.000 in fine-tuned 7B means the
   model learned to always output the same token regardless of condition. Flag any study with
   p≈1.000 in Run A as potential collapse (not a "replicated" effect).
3. **Fine-tuning can regress borderline effects** — myside went from p=0.086 to p=0.571
   after fine-tuning. Monitor which studies degrade in Run A vs `base_30b`.
4. **Sunk_cost is potentially learnable** — it emerged at p=0.027 post-FT even on the
   broken map. The grounded map (Run A) with 5× more data may surface other latent effects.

### Completed: Stage 1 + 2 (2026-06-14)

**K-sweep results** (PAM k-medoids on Gower distance, n_init=3):

| K | Divergence | ≥5 members | Prolific-majority clusters | Notes |
|---|---|---|---|---|
| 150 | 0.314 | 91.3% | 26 | |
| **200** | **0.352** | **84.0%** | **41** | **chosen** |
| 250 | 0.374 | 72.8% | 44 | |
| 300 | 0.387 | 64.7% | 50 | |
| 350 | 0.404 | 56.0% | 64 | |
| 400 | 0.412 | 47.0% | 69 | |

**K=200 chosen** — best cluster-size floor (84% ≥5 members); divergence gains above 200 are
marginal (0.035 across the full remaining range). Prolific-majority cluster count never reaches
200 at any K, so raising K does not solve the eval-roster problem (see §3.3 resolution below).

**Artifacts on disk:**
- `data/personas_generated.json` — 200 personas, deterministic template (no Gemini),
  cluster sizes min=1 / median=9 / max=31; 32 clusters below the ≥5 floor
- `data/pid_to_persona.json` — all 2,058 PIDs mapped; 539 flagged `prolific_like` (26.2%)
- `data/train.jsonl` / `data/val.jsonl` — SFT data built from all 2,058 participants

---

## 3. Design decisions (settled — do not reverse without discussion)

### 3.1 Keep within-subjects + memoryless inference
- Every persona answers every condition, each in an **independent zero-shot call** (no memory
  across conditions). This is mechanically equivalent to between-subjects from the model's
  view — the model never "sees" two conditions together, so it can't reconcile them (which in
  humans attenuates effects like framing). We get un-reconciled full-strength responses **and**
  a paired data structure for statistical power.
- **Exception (keep as-is):** `false_consensus` and `risk_benefit` are genuinely
  within-person correlational — the eval injects first-stage answers back as a
  "YOUR ANSWERS SO FAR" block. Training mirrors this. Do not make these memoryless.
- **Caveat to remember:** within-subjects power is only real if personas carry *stable
  individual differences* (positive within-persona covariance across conditions). That is
  exactly what persona grounding (§3.2) buys — without it, the pairing is empty.

### 3.2 Ground personas by clustering real participants — NOT verbatim "twins"
We keep readable, hand-style personas ("You are a 19-year-old…"), but make each one correspond
to a **real demographic cluster** of Twin-2K participants, and train it on that cluster's real
answers. This fixes the §2 independence bug while keeping the persona format the product uses.

We explicitly **reject** the paper's verbatim-profile "digital twin" approach (feed a full
profile to a frozen model): the paper showed those twins were weak at individual prediction.
Our setup is different — we *fine-tune* readable personas on the *answer distribution of
demographically-similar humans*, which is a more robust target.

**Mechanism: cluster → generate → assign.**
1. Cluster all 2,058 participants on demographics into **K ≈ 300** groups.
2. Generate **one readable persona per cluster** from the cluster's representative profile.
3. Assign every participant to its cluster's persona; train that persona on **all** its
   members' real answers (uses all 2,058 — ~5× current data).

**Choosing K — start ~300, but pick it empirically (not a derived optimum).** K is a
bias–variance tradeoff on each persona's answer distribution: too-high K → 1–3 members/cluster
→ noisy, thin per-individual twins (which we rejected); too-low K → huge clusters that span a
wide demographic range and average the demographic→behavior signal back toward the global
marginal. That puts the sensible box at ~5–10 members/cluster, i.e. **K ≈ 200–400** for 2,058
participants. Pick the actual value from the **Stage-1 K-sweep** (§6 Stage 1), not the round
number.

**Interaction to resolve:** the ~200-persona eval roster (§3.3) wants to be predominantly
`prolific_like`. The ~515 Prolific-like people concentrate into the young/educated clusters, so
at K=300 there may be only ~75–100 "Prolific-majority" clusters — *fewer than 200 distinct
Prolific personas*. Resolve by either (a) topping up the roster with the next-closest personas /
instantiating multiple respondents per Prolific persona, or (b) raising K to create more (finer)
Prolific clusters — which trades against the ≥5-members-per-cluster floor. Decide during the
K-sweep.

### 3.3 Train broad, query narrow (the "Prolific" flag) — **RESOLVED 2026-06-15**

- **Train** on all 2,058 (representative US panel) so the model learns the full
  demographic→behavior function. ✅ Done — `train.jsonl` uses all 2,058.
- **Eval roster = 200 hand-crafted Prolific-worker personas** from `personas.py` +
  `responses/generated_v3.json`. ✅ Done — `3_eval.py` updated to load `DEFAULT_PERSONAS`
  directly instead of `personas_generated.json`.

**Why not use prolific-majority clusters from `personas_generated.json` for eval?**
The K-sweep showed that at K=200 only 41 clusters are prolific-majority (share >0.5), and
raising K to 400 only gets to 69 — never close to 200. This is because only ~26% of Twin-2K
participants are prolific-like, so prolific-heavy clusters are always a minority at any sensible K.
The cleaner solution: keep `personas_generated.json` as training cluster labels only, and use the
separately hand-crafted prolific roster (`personas.py`) for inference. The fine-tuned model has
learned the demographic→behavior mapping from prolific-like participants in training; at
inference, any prolific-style persona description activates that learned pattern.

**Roster size:** `personas.py` has 100 inline personas + 100 loaded from
`responses/generated_v3.json` = **200 total**, all Prolific/MTurk-worker style. If
`--n-personas` < 200, `3_eval.py` samples randomly with the configured seed.

### 3.4 Raw-data deliverable → effect-size, not binary
The tool emits per-respondent rows; the user runs their own stats. Internally we still report
**effect sizes with uncertainty** (not just p<.05), because within-subjects + large N makes
almost anything "significant" and that miscalibrates both error types. See the calibration plot
in §8.

### 3.5 Inference with reasoning OFF
Cheaper, and more bias-preserving (deliberation corrects System-1 errors — the opposite of
what we want). Train in non-thinking mode too. Optionally test thinking-on later *only* on the
"too-rational" studies if grounding alone doesn't fix them.

### 3.6 Iterate small, scale 235B exactly once
- Method questions (does grounding help? does it transfer? rationale ablation?) are cheap to
  answer at small scale. Settle the recipe on **Qwen3-30B-A3B** (same MoE family as
  235B-A22B → rehearses the exact MoE/router quirks for ~10× less).
- Then do **one** confirmation run on **Qwen3-235B-A22B**.
- Do **not** change the model and the method at the same time (confounds the experiment).

### 3.7 Rationale ("train the process") = later ablation, not the first run
Have a teacher write a short System-1 rationale consistent with the human's answer, SFT on
rationale+answer. **Risk:** rationales add deliberation, which tends to *suppress* biases —
cuts against the grain. So: establish clean **answer-only** grounded SFT first; test rationale
as an *isolated* change on held-out/scenario-shifted studies only. Be ready for it to hurt.

---

## 4. Two validation gaps we must close (besides "replication count")

Both are **Phase 2** — only after Phase 1 replicates the 17 in-sample.

1. **Generalization (anti-overfitting) — the Mega-Study as a true test set.** The product's value
   is on *new* studies, not the 17 we train on. Rather than holding out a subset of the same
   benchmark, we use the **19 independent Mega-Study studies (arXiv:2509.19088v3, §2)** as a
   never-trained test set. If grounded fine-tuning transfers to those out-of-distribution
   constructs, we have a pre-test tool; if it only works on the 17, we built a lookup table — and
   we'll know. (Note: same panel of people, but entirely different *tasks*; we train on clustered
   personas, not individuals, so this is a fair task-level generalization test.)
   - **Build cost:** the 19 studies are diverse real experiments, so this requires authoring 19
     new experiment definitions + analyses (designs, conditions, expected effects, stats),
     ideally seeded from the Mega-Study's published materials/data. This is the bulk of Phase-2
     work and is downstream of a successful Phase 1.
2. **Specificity — known NULLs.** All 17 (and the 19) are *known real effects*, so on their own
   they only measure sensitivity. To prove the model isn't a "yes-machine," **add a set of known
   NULL effects** (the Ed calibration null; published/registered-report nulls in JDM; a few
   constructed placebo manipulations — e.g. an irrelevant anchor, a framing manipulation on a
   value-neutral item). Even 5–8 nulls is enough to place real points near the origin of the
   calibration plot (§8). Include the nulls in the Phase-2 test pass.

---

## 5. The data (Twin-2K-500)

- Dataset: `LLM-Digital-Twin/Twin-2K-500` (HF). Cached at `~/.cache/huggingface/hub/`.
- **Answers:** `question_catalog_and_human_response_csv/wave4_response_label.csv` (2,058 rows,
  keyed by `pid`, readable labels). Already used by current pipeline.
- **Question catalog:** `question_catalog_and_human_response_csv/question_catalog.json`
  (QID → text/options/type).
- **Demographics:** `question_catalog_and_human_response_csv/wave1_3_response_label.csv`
  (2,058 rows; 761 columns; headers are QIDs). The clean **Demographics block is QID11–QID24**,
  all human-readable labels:

| Field | QID | Type | Values |
|---|---|---|---|
| Region | QID11 | nominal | Northeast / Midwest / South / West |
| Sex | QID12 | binary | Male / Female |
| Age band | QID13 | ordinal | 18-29 / 30-49 / 50-64 / 65+ |
| Education | QID14 | ordinal | <HS → HS grad → Some college → Associate's → College grad → Postgraduate |
| Race | QID15 | nominal | White / Black / Asian / Hispanic / Other |
| Citizen | QID16 | binary | Yes / No |
| Marital | QID17 | nominal | Married / Living w/ partner / Divorced / Separated / Widowed / Never married |
| Religion | QID18 | nominal | Protestant / Catholic / Mormon / … / Atheist / Agnostic |
| Religious attendance | QID19 | ordinal | |
| Party | QID20 | nominal | Republican / Democrat / Independent / Something else |
| Income | QID21 | ordinal | <$30k / $30-50k / $50-75k / $75-100k / $100k+ |
| Political views | QID22 | ordinal | Very conservative → Conservative → Moderate → Liberal → Very liberal |
| Household size | QID23 | ordinal | 1 / 2 / 3 / 4 / >4 |
| Employment | QID24 | nominal | Full-time / Part-time / Unemployed / Self-employed / Home-maker / Student / Retired |

- Handle missing/blank demographic cells (impute to mode or treat as an "Unknown" category;
  document which).
- (Available but **not used for matching** per decision: Big Five / personality items, the
  `full_persona/` parquet chunks.)

---

## 6. Implementation plan

### Stage 1 — Persona builder ✅ COMPLETE (2026-06-14)

Module: `experiments/qwen_human_finetuning/personas_from_twin2k.py`

Functions:
1. `load_demographics()` → DataFrame[pid × 14 fields] from `wave1_3_response_label.csv`,
   selecting QID11–QID24, readable labels.
2. `encode_demographics(df)` → ordinals as integer ranks (age, education, income, political
   views, household, religious attendance); nominals as categories (region, sex, race, citizen,
   marital, religion, party, employment).
3. `cluster(df, K)` → k-prototypes (lib: `kmodes`) over mixed ordinal/nominal fields.
   Output: cluster label per pid + a **representative profile** per cluster (mode for nominal,
   median for ordinal). (Alternative: Gower distance + k-medoids so each centroid is a real
   participant; pick whichever is simpler to get working — document the choice.)
   - **K-sweep (run before fixing K):** cluster at K ∈ {150, 200, 250, 300, 350, 400} and for
     each report (a) per-cluster answer-divergence-from-marginal (want high — demographics
     actually separate behavior), (b) cluster stability / silhouette on the Gower distance,
     (c) the min/median cluster size (keep the floor ≥ ~5), and (d) the count of
     Prolific-majority clusters (see the §3.2/§3.3 roster interaction). **Pick K at the knee.**
     If divergence stays weak at every K, surface that — it means these demographics don't
     predict *these biases* much, and grounding won't help as hoped (an important finding, not
     a bug).
4. `score_prolific_likeness(df)` → Gower distance to a Prolific prototype, weighting
   **age / education / employment** highest. Flag the closest ~25% as `prolific_like`.
5. `generate_persona(profile)` → one readable persona (name + description) per cluster in the
   existing `personas.py` voice, via the repo's Gemini client. **Generate once, cache to JSON**
   for reproducibility and hand-editing. (Deterministic template = fallback if we'd rather not
   call the LLM.)
6. Emit artifacts:
   - `data/personas_generated.json` — the ~300 personas: `{name, description, cluster_profile,
     n_participants, prolific_share}`
   - `data/pid_to_persona.json` — every pid → persona name + `prolific_like` flag
     (this **replaces** the `i % n` map)
7. Print **diagnostics** (no GPU):
   - cluster-size distribution
   - the `prolific_like` subset's demographic breakdown (eyeball: should skew young/educated/
     employed) — **review this and tune the weights/threshold before continuing**
   - per-cluster answer-distribution divergence from the global marginal (confirms demographics
     actually separate behavior; if every cluster ≈ average, K too low / features too weak)

**Gate:** review the generated personas + Prolific subset + divergence diagnostic before Stage 2.
K=200 chosen from sweep; artifacts reviewed; proceeding to Stage 2. ✅

### Stage 2 — Wire artifacts into training + eval ✅ COMPLETE (2026-06-14 / 2026-06-15)
- `1_prepare_data.py`: replaced `build_pid_to_persona` with loader for `pid_to_persona.json`;
  dropped `max_per_persona=2` cap; all 2,058 participants used. ✅
- `3_eval.py`: eval roster now uses `DEFAULT_PERSONAS` (200 hand-crafted Prolific-worker
  personas from `personas.py` + `responses/generated_v3.json`) — see §3.3. ✅
- `data/train.jsonl` and `data/val.jsonl` built. ✅ **Rebuilt 2026-06-16** to 100,498
  train / 6,530 val after the §2.2 **persona-grouped val split** (was 107,028 with a leaky
  random split). `1_prepare_data.py` prints a per-study data-quality report on every build
  and warns on `--max-examples`. New `--cap-per-study` lever for imbalance.
- `3_eval.py`: **`_render` fixed (§2.2)** — plain ChatML for FT checkpoints (matches
  training), `enable_thinking=False` on the base reference, `max_new_tokens=128`. ✅
- `persona_signal_check.py`: per-study persona-ICC diagnostic, now with `btwn_sd`, a
  gate-study callout, and a single-item-floor caveat (§2.2). ✅
- `prompt_parity_check.py` (new, §2.2): GPU-free in-sample-vs-transfer check. Flags 4–5
  **transfer-only** studies (incl. the current gate) where SFT teaches a different answer
  space than the eval — informational (exit 0), not a blocker; use it to pick a matched
  gate study. ✅

### Stage 3 — GPU runs (RunPod)

Run matrix, **one change at a time**, all on **Qwen3-30B-A3B**, reasoning off. The existing
3-script pipeline is reused throughout: `1_prepare_data.py` (build SFT JSONL),
`2_train.py` (QLoRA), `3_eval.py` (run the studies; `--compare` for side-by-side). Outputs land
in `results/<label>/`. **Change exactly one variable per run** so each comparison isolates one
effect.

#### Common setup (all Phase-1 runs)
- **Pod:** A100 80GB SXM ($1.49/hr). 30B-A3B is MoE with ~3B active params → ~15 GB in 4-bit,
  fits comfortably with room for the eval's batched generation.
- **`config.yaml` changes from the current file:**
  - `model.base: Qwen/Qwen3-30B-A3B` (was `Qwen2.5-7B-Instruct`)
  - keep `load_in_4bit: true`, `max_seq_length: 2048` (bump to 4096 only if Mega-Study prompts
    overflow in Phase 2)
  - keep LoRA block as-is (`r: 16`, `alpha: 32`, the 7 target modules, `dropout: 0.05`) for the
    first pass; only tune if Run A under-fits
  - keep `training`: `num_epochs: 2`, `lr: 2.0e-4`, effective batch 16, `val_fraction: 0.05`,
    `seed: 42`
  - keep `eval`: `n_personas: 150`, `temperature: 0.5`, `between_subject_mode: within`,
    `seed: 42`; lower `batch_size` only on OOM
- **Reasoning OFF** (§3.5): training examples contain no chain-of-thought; eval generates in
  non-thinking mode (set Qwen3's `enable_thinking=False` in the chat template / the
  `disable_reasoning` path used by `twin2k_replication`). Confirm both train and eval paths
  agree — a thinking-mode mismatch silently changes behavior.
- **Tooling caveat / fallback:** verify the training stack (Unsloth) supports **Qwen3-30B-A3B
  MoE** QLoRA before committing. Unsloth is dense/single-GPU-focused; if MoE QLoRA isn't
  supported, **fall back to dense `Qwen3-14B`** for method iteration and accept that MoE-specific
  rehearsal happens only at the 235B confirmation run. Note which path was used.
- **Pre-flight (run once, no GPU, before launching the pod):**
  - `python 1_prepare_data.py` → confirm it prints **~100K examples**, the
    "Loading grounded pid→persona mapping … 2058 participants" line (not the 500-row
    smoke test, not the fictional fallback), and the **`Val split: N/M personas held
    out`** line (group split, §2.2). Review the data-quality FLAGS.
  - `python prompt_parity_check.py` → informational (always exit 0). Note the
    **transfer-only** studies (`dominator_neglect`, `omission_bias`, `probability_matching`,
    `sunk_cost`, `less_is_more`, §2.2): grounding adds no in-sample signal there, so judge
    them as transfer and keep the in-sample gate on a matched study (`myside`). Not a
    blocker — at eval the model reads the eval prompt.
  - `python persona_signal_check.py` → note which studies have ICC ≥ 0.05 (and the new
    `btwn_sd` column); these are the only ones grounding can plausibly move (§2.1/§2.2).
    Set expectations for Run A from this. Gate study `dominator_neglect` ICC=0.063.
- **Base reference (run once):** before any fine-tune, eval the untrained model so we know the
  starting point:
  `python 3_eval.py --model-path Qwen/Qwen3-30B-A3B --out-label base_30b`

#### Phase 1 — replicate the 17 (in-sample gate)

| Run | What changes | Build command(s) | Eval label |
|---|---|---|---|
| **Run 0 — baseline FT** | Current fictional `i % n` persona map (existing `build_pid_to_persona`, `max_per_persona: 2`) | `python 1_prepare_data.py` → `python 2_train.py` → `python 3_eval.py --out-label run0_fictional` | `run0_fictional` |
| **Run A — grounded FT** | New clustered roster + `pid_to_persona.json` (Stage 1/2), **all 2,058**, eval roster Prolific-prioritized | `python 1_prepare_data.py` (now reads the grounded map) → `python 2_train.py` → `python 3_eval.py --out-label runA_grounded` | `runA_grounded` |

- **Compare:** `python 3_eval.py --compare` across `base_30b`, `run0_fictional`, `runA_grounded`.
  Run 0 vs base shows what the *old* fine-tune bought; Run A vs Run 0 isolates the **grounding**
  effect (the only thing that changed).
- **Phase-1 GATE (decision rule) — REVISED 2026-06-15, see §8 for the tiered rationale:**
  proceed to Phase 2 if **either** (a) Run A replicates **clearly more** of the 17 than Run 0,
  **or** (b) Run A moves **`dominator_neglect`** (the only trainable, signal-bearing
  "too-rational" study; the others are excluded or signal-poor per §2.1) in the human direction
  without regressing studies Run 0 already passes. If neither holds, the cause is most likely
  the weak persona-signal ICC (§2.1), **not** under-tuning — do **not** spend budget on
  K-sweeps / `r` / `num_epochs` chasing it. Advance to Phase 2 only on (a) or (b).

#### Phase 2 — generalization + specificity (only if the Phase-1 gate passes)

Prerequisite (Stage 4 work): the 19 Mega-Study experiment definitions + the NULL set must be
authored in the `experiments.json` / `analysis.py` format first.

| Run | What changes | How |
|---|---|---|
| **Run B — transfer** | No new training; new eval set | Eval **Run A's checkpoint** on the 19 Mega-Study studies **+ NULLs**. Also eval `base_30b` on the same set as the no-FT reference. |
| **Run C — rationale (ablation)** | Add teacher System-1 rationales to the SFT targets (§3.7); retrain from the same base | Rebuild JSONL with rationale+answer, retrain, eval on the **Mega-Study + NULLs** (the held-out set — never judge rationale on the trained 17). Only attempt if Run B transfers. Expect possible regression. |

- **What we measure (Run B/C):** the synthetic-vs-human effect-size plot (§8) over the 19 + the
  NULLs — real effects on/above the diagonal (sensitivity), NULLs near the origin (specificity).

#### Confirmation run — scale once to 235B
After the recipe is locked on 30B-A3B, do **one** run of the winning configuration on
**Qwen3-235B-A22B**:
- **Pod:** single **B300 288GB** ($7.39/hr) — ~120–140 GB for 4-bit weights needs the headroom.
- **Framework:** Unsloth may not handle 235B MoE; be ready to use `transformers` + `peft` +
  `bitsandbytes` QLoRA instead. The 30B-A3B work should have surfaced the MoE quirks (router
  stability, target modules) already.
- Run the same `base` → grounded-FT → eval sequence, then the §8 plot. This is a confirmation,
  not an iteration loop — budget for one clean pass (§7).

### Stage 4 — Calibration & validation
- Assemble the NULL set (§4.2) and author the 19 Mega-Study experiment definitions (§4.1).
- Produce the **synthetic-vs-human effect-size plot** (§8) across the 17, the 19, and the nulls.
- Re-run the **Selin/Ed calibration** with the Prolific-prioritized roster.

---

## 7. Compute budget (RunPod, target < $100)

| Phase | Model | GPU | Est. cost |
|---|---|---|---|
| Method iteration (Runs 0/A/B/C) | Qwen3-30B-A3B | A100 80GB ($1.49/hr) | ~$4/run × ~5 = ~$20 |
| Lock recipe + null/held-out eval | Qwen3-30B-A3B | A100 80GB | ~$10 |
| Scale once | Qwen3-235B-A22B | B300 288GB ($7.39/hr) | ~$40 |
| Buffer (failed pods, re-runs) | | | ~$30 |

Notes: 235B-A22B is MoE, ~120–140GB in 4-bit → needs single B300 (288GB); Unsloth is
single-GPU/dense-focused and may not handle 235B MoE cleanly — the 30B-A3B work de-risks this.
Iterate at small scale; spend the $40 only after the recipe is locked.

---

## 8. Success criteria

**Phase-1 gate (must pass first) — REVISED 2026-06-15 to be winnable.** The original gate
required Run A to recover all 5 "too-rational" failures (`less_is_more`, `wta_wtp`,
`omission_bias`, `dominator_neglect`, `probability_matching`). Two of those are not directly
trainable, and two more carry ~no persona signal (§2.1), so the original gate was unachievable
by construction. The studies tier as follows:

| Tier | Studies | Trainable? | Persona ICC | Gate role |
|---|---|---|---|---|
| **Trainable + signal** | `dominator_neglect` | yes (6 conditions) | 0.063 | **Required** — the one fair test of grounding |
| **Trainable, weak signal** | `wta_wtp`, `probability_matching` | yes | 0.009 / 0.022 | Stretch — movement is a bonus, not required |
| **Not directly trainable** | `less_is_more` (EXCLUDED from training — no format overlap), `omission_bias` (only one condition mapped, no contrast) | no | — / 0.060 | **Excluded from gate** — transfer-only stretch goals |

**⚠ Gate-study caveat (§2.2):** `dominator_neglect` is **transfer-only**, not in-sample —
its training data (Twin-2K fire-extinguisher/seatbelt items) and its eval (`experiments.json`
constructed $50 gamble) use different answer spaces/elicitations (and possibly different
constructs: *proportion* vs *stochastic* dominance — verify). Grounding therefore can't move
it *in-sample*, so it's not a clean test of the grounding mechanism. This is not a bug and
not a blocker — judge it as a transfer result. For rule (b) below, prefer an **in-sample,
signal-bearing** study (`myside`, scale-matched, ICC 0.058) so the gate isolates the mechanism;
keep `dominator_neglect` as a reported transfer outcome. `prompt_parity_check.py` lists the
in-sample-compatible studies.

**Revised decision rule — proceed to Phase 2 if EITHER:**
- (a) Run A replicates **clearly more** of the 17 than Run 0 overall, **or**
- (b) Run A moves an **in-sample, signal-bearing gate study** (`myside`; `dominator_neglect`
  only if its construct/answer-space is first matched to the eval) in the human direction
  without regressing studies `base_30b`/Run 0 already pass.

If neither holds, the likely cause is the weak persona signal in §2.1, not a tuning miss —
**do not** burn budget chasing it with K-sweeps/`r`/epochs. The correct readout is then
"demographics don't predict these JDM biases" (a finding), and the lever shifts to base-model
capability and the 235B confirmation run. No Phase 2 until (a) or (b) holds.

**Phase-2 key artifact:** plot synthetic Cohen's *d* (y-axis) vs human *d* (x-axis) across the
**19 Mega-Study effects + the NULL set** (the true held-out test).
- Real effects should sit **on or above the diagonal** (sensitivity — we never undershoot a
  real effect; above the diagonal = tolerated false positives by design).
- Nulls should cluster **near the origin** (specificity — we haven't become a yes-machine).
- Target: slope ≥ 1, intercept ≈ 0.

Secondary:
- Transfer holds on the Mega-Study 19 (not just the trained 17).
- Per-cluster behavior diverges from the global marginal (grounding worked).

---

## 9. Open questions / to decide

- [x] Final **K** — **K=200** chosen from sweep (2026-06-15). Best cluster-size floor;
      marginal divergence gains above 200.
- [x] **Prolific-likeness** definition — resolved by using `DEFAULT_PERSONAS` for eval
      instead of prolific-share filtering on clusters (2026-06-15).
- [x] Persona generation: **deterministic template** used (no Gemini).
- [x] Clustering algo: **Gower + PAM k-medoids** (`personas_from_twin2k.py`).
- [ ] **Phase 2:** author the **19 Mega-Study** experiment definitions + analyses
      (arXiv:2509.19088v3), seeded from its published materials/data — the bulk of Phase-2 work.
- [ ] Sourcing the **NULL set** for specificity (Ed calibration null + JDM registered-report
      nulls + constructed placebos; 5–8 to start).
- [ ] Deployment target (self-hosted Qwen vs Gemini-prompting research) — doesn't block build.
- [x] **Run A data: capped or full?** — **CAPPED at 3000/study (2026-06-19).** Run A's job is
      the in-sample `myside` gate test; uncapped, `myside` gets ~2% of gradient updates (matrix
      studies ~69%), so a flat result would be uninterpretable (gradient starvation vs no signal).
      Cap applied IDENTICALLY to Run 0 and Run A (`runpod/run_phase1.sh`, `CAP=3000`) so the cap
      isn't a second changed variable. `CAP=0` for the full ~100K. Cost: weakens the
      `false_consensus`/`risk_benefit` correlational studies in this run — acceptable, gate is the priority.
- [ ] **Given the weak persona ICC (§2.1), is grounded FT still worth the Run A spend,**
      or do we go straight to base-model/235B capability work? Run A is cheap (~$4) and is
      the clean test of the §2 independence-bug hypothesis, so it's still worth one run — but
      enter it expecting Run A ≈ Run 0 on most studies.
- [x] **(§2.2) Move the in-sample gate to a matched study** — the 4–5 transfer-only studies
      (`dominator_neglect`, `omission_bias`, `probability_matching`, `sunk_cost`, `less_is_more`)
      can't test grounding in-sample. Gate rule (b) now uses `myside` (scale-matched, ICC 0.058);
      transfer-only studies are reported as transfer (2026-06-17). Optional later: re-author the
      eval `experiments.json` entries to the Twin-2K answer space to make them in-sample too.
- [ ] **(§2.2) Verify the `dominator_neglect` construct** — training is *proportion* dominance
      (lives-saved framing); the eval gamble is *stochastic* dominance. Confirm these are the
      same bias before relying on it even as a transfer result.
- [x] **(§2.2) Verify scale/MC label DIRECTION for the encoded studies** — done 2026-06-17.
      `myside` (train "should ban?" 6=yes-ban vs eval "should be allowed?" 6=no-not-allowed:
      eval labels reversed to compensate → high=pro-ban in both, consistent), `outcome_bias`
      (7=excellent both), and `savings` (catalog `1:Yes,2:No`→A/B→eval `['yes','no']` by
      position, aligned) all check out. No direction flip; `myside` is safe as the in-sample
      gate. NOTE: the encoder assumes the Twin-2K catalog lists options in the eval's
      direction — re-verify if any NEW study is added (a reversed catalog flips every label).
- [ ] **(§2.2) Monitor output-collapse in Run A** — separate from transfer: watch the eval's
      per-study no-response rate + degenerate-label flag (the 7B `savings` p=1.000 mode).

---

## 10. Decision log (rationale to preserve)

- **Within-subjects kept** because memoryless zero-shot avoids the human reconciliation confound
  while giving paired-data power. (User corrected an earlier "between-person variance" framing.)
- **Verbatim digital twins rejected** — paper showed they're weak; readable clustered personas
  fine-tuned on cluster answer distributions are more robust and match the product format.
- **Grounding via clustering** chosen over per-participant personas to avoid thin/noisy targets
  and keep readable personas; over keeping the arbitrary `i % n` map which breaks
  demographic→behavior learning.
- **Train broad / query narrow** chosen to use all 2,058 for learning while matching the
  Prolific product population at inference — resolves the representative-US vs Prolific conflict
  without repeating the 2026-05-20 representative-roster failure (different mechanism:
  fine-tuned targets, not base-model prompts).
- **Reasoning off** — cheaper and bias-preserving.
- **Iterate at 30B-A3B, scale 235B once** — separate method from scale; rehearse MoE quirks
  cheaply; respect the <$100 budget.
- **Rationale SFT deferred** — adds deliberation that may suppress biases; test in isolation.
- **Two-phase scope** — Phase 1 just replicates the 17 in-sample (the gate); Phase 2 tests
  generalization. Chosen so we don't build the expensive test harness before proving the recipe
  works at all.
- **Generalization tested on the external Mega-Study (19 studies), not a held-out subset of the
  17** — fully independent constructs are a stronger anti-overfitting test than reworded
  in-benchmark holdouts. **Plus a NULL set** so specificity is measured, not assumed.
- **K=200 chosen from sweep (2026-06-15)** — K-sweep run across {150,200,250,300,350,400}.
  K=200 has the best cluster-size floor (84% ≥5 members) and divergence gains above it are
  marginal. Prolific-majority cluster count never reaches 200 at any K (tops at 69 at K=400),
  so raising K is not the right lever for the eval roster problem.
- **Broken-map FT (7B pilot) showed fine-tuning works, grounding was the bottleneck** —
  Qwen2.5-7B base→fine-tuned gained only +1 study (sunk_cost) despite QLoRA on real human
  answers. The 5 "too rational" failures didn't move. This validates that the i%n independence
  bug was the binding constraint, not the SFT recipe itself. Run A tests whether fixing the
  persona-answer coupling (with 5× more data) actually moves those failures.
- **Base capability dominates fine-tuning gain at small scale** — 30B-A3B base (11/17) already
  beats 7B fine-tuned (9/17). Run 0 (30B-A3B + broken map) is the meaningful baseline for
  Run A, not the 7B results; any Run A improvement has to clear the higher bar.
- **Watch for answer-format collapse post-FT** — savings showed p=1.000 in fine-tuned 7B
  (model always output same token regardless of condition). Flag p≈1.000 in any Run A study
  as collapse, not replication.
- **Fine-tuning can regress borderline effects** — myside went from p=0.086 (near-significant)
  to p=0.571 after 7B fine-tuning. After Run A, check whether any study that `base_30b`
  nearly replicates degrades under fine-tuning before claiming a net improvement.
- **Eval roster uses `DEFAULT_PERSONAS`, not `personas_generated.json` (2026-06-15)** —
  `personas_generated.json` clusters are representative-US by construction (derived from
  Twin-2K centroids). The 200 hand-crafted Prolific-worker personas in `personas.py` +
  `responses/generated_v3.json` are the correct eval population. The fine-tuned model
  activates the prolific-learned pattern from the description text; it does not need to have
  seen the exact persona name during training. This is the concrete implementation of
  train-broad/query-narrow (§3.3).
- **Pre-GPU audit round 2 (2026-06-16/17): chat-template bug (fixed) + transfer-only studies**
  — see §2.2. Four code fixes landed (eval ChatML/thinking parity in `3_eval.py`; persona-grouped
  val split; ICC over-claim corrected with `btwn_sd`; render token headroom). The chat-template
  bug was the one genuine bug — it would have collapsed *every* FT eval (false "grounding didn't
  help"), now fixed. A new `prompt_parity_check.py` showed **4–5 studies (incl. the current gate
  `dominator_neglect`) are transfer-only**: training and eval use different answer spaces, so SFT
  adds no in-sample signal toward them.
- **Transfer-only is an interpretation fact, NOT a blocker (corrected 2026-06-17)** — an initial
  framing called the answer-space differences a "breaking blocker." That was wrong on two counts,
  caught on review: (1) scenario paraphrasing between train and eval is the *existing, deliberate*
  design across the whole benchmark (e.g. framing "disease" vs "Asian disease"), which is what
  makes the eval a generalization test rather than a memorisation check — good, not broken;
  (2) at eval the model is conditioned on the **eval** prompt, so it reads the eval's answer space
  and produces parseable output — the training answer space never reaches it. The real, smaller
  consequence: those studies are *transfer* tests (no in-sample grounding signal), so the gate's
  mechanism test (rule b) moved to an in-sample matched study (`myside`); transfer studies are
  reported as transfer. Output collapse remains a *separate* SFT-overfitting risk, monitored via
  no-response rate. `prompt_parity_check.py` is informational (exit 0).
- **Pre-flight audit (2026-06-15): stale data, imbalance, and weak signal** — see §2.1.
  The committed `train.jsonl` was a 500-row smoke test (rebuilt to 107K); a per-study
  data-quality report and collapse/imbalance flags were added to `1_prepare_data.py`; and a
  new `persona_signal_check.py` showed the per-study persona ICC is ~0.02. The Stage-1
  "divergence 0.352" metric was overoptimistic relative to this properly-residualised ICC —
  the divergence number conflates condition effects and cluster-size artifacts, whereas the
  ICC isolates stable persona variance and finds almost none. This reframes the §2 hypothesis:
  the i%n map being broken was *a* bug, but even a perfect map carries little demographic→
  behavior signal for these JDM biases, so Run A is unlikely to beat Run 0 broadly. The
  Phase-1 gate (§8) was rewritten around the one trainable, signal-bearing study
  (`dominator_neglect`) accordingly.
