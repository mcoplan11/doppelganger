# Grounded-Persona Fine-Tuning Plan (v2)

> **Status:** planning document for review. Once finalized, this is the build spec to hand to
> an implementing model (e.g. Claude Sonnet). It captures **what we are doing, why, and in what
> order** — including the reasoning behind each decision so the builder doesn't re-derive or
> reverse them.

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
| Model | Effects replicated |
|---|---|
| Centaur-70B | 3/17 (mostly degenerate numeric output) |
| qwen3-235b-a22b | 12/17 |
| qwen3.7-max | 13/17 |

The 4–5 consistent **failures** across the good models are all "**too rational**" cases —
the LLM doesn't fall for the bias because it reasons normatively:
`less_is_more`, `wta_wtp` (endowment), `omission_bias`, `dominator_neglect`
(+ `probability_matching` for 235b).

### Existing fine-tuning experiment (`experiments/qwen_human_finetuning/`)
QLoRA on Qwen2.5-7B using Twin-2K human answers, then re-run the 16 studies base-vs-finetuned.
**The core bug we are fixing:** `1_prepare_data.py:build_pid_to_persona` maps participants to
personas by **sorted-pid position mod 100** (`DEFAULT_PERSONAS[i % n]`). The persona text
("19-year-old construction worker…") is therefore **statistically independent** of the human
answers it's trained on. The model can only learn the *population marginal*, never
demographic→behavior. It also caps at 2 participants/persona = only 400 of 2,058 used.

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

### 3.3 Train broad, query narrow (the "Prolific" flag)
- **Train** on all 2,058 (representative US panel) so the model learns the full
  demographic→behavior function.
- **Flag ~25% (~515)** of participants as **`prolific_like`** — those closest to a Prolific
  survey-worker prototype (skew: age 18–40, college+, employed/student; secondary
  Democrat/liberal lean).
- **"Run studies" (inference) roster ≈ 200 personas, prioritizing the `prolific_like` slice**,
  because that matches the product's real respondent population and the Selin/Ed calibration
  target.

This resolves a real validity conflict: Twin-2K is representative-US, but `personas.py` was
deliberately rebuilt on 2026-05-20 as Prolific workers *after a representative-American roster
failed to predict the Selin/Ed results*. That failure was **base-model prompting**; here the
representative personas are **fine-tuned training targets**, so they carry learned grounding.
Training broad + querying narrow keeps the data asset and the product population aligned.

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

### Stage 1 — Persona builder (pure CPU, ~$0, fully reviewable BEFORE any GPU)

New module: `experiments/qwen_human_finetuning/personas_from_twin2k.py`

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

### Stage 2 — Wire artifacts into training + eval (CPU)
- `1_prepare_data.py`: replace `build_pid_to_persona` with a loader for `pid_to_persona.json`;
  drop the `max_per_persona=2` cap; use all 2,058. Keep all existing format-alignment logic
  (framing→binary A/B, wta_wtp numeric, MC-as-scale rank encoding, two-pass context for
  false_consensus/risk_benefit, `less_is_more` excluded from training, omission_bias caveat).
- Train on **all 17** studies (no held-out subset — generalization is tested externally on the
  Mega-Study in Phase 2, §4.1). Keep `less_is_more` excluded from training as before.
- `3_eval.py`: build the eval roster (~200) from `personas_generated.json`, **prioritizing
  `prolific_like`** personas; top up to 200 with the next-most-Prolific-like if needed.

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
- **Phase-1 GATE (decision rule):** proceed to Phase 2 only if Run A
  (a) replicates **clearly more** of the 17 than Run 0, **and**
  (b) recovers at least some of the 4–5 "too-rational" failures (`less_is_more`, `wta_wtp`,
  `omission_bias`, `dominator_neglect`, `probability_matching`).
  If not: tune before spending more — first the **K-sweep / persona granularity** (§3.2), then
  LoRA capacity (`r`), then `num_epochs`. Do **not** advance a weak Run A to Phase 2.

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

**Phase-1 gate (must pass first):** the grounded fine-tune (Run A) replicates clearly more of
the **17** in-sample studies than the base model / Run 0 — especially the 4–5 "too-rational"
failures (`less_is_more`, `wta_wtp`, `omission_bias`, `dominator_neglect`,
`probability_matching`). No Phase 2 until this holds.

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

- [ ] Final **K** — pick from the Stage-1 K-sweep (start box ~200–400), balancing
      cluster divergence, stability, the ≥5 size floor, and the Prolific-cluster count.
- [ ] **Prolific-likeness** definition — confirm weights/threshold after seeing the flagged
      subset's demographics.
- [ ] Persona generation: **Gemini vs deterministic template**.
- [ ] **Phase 2:** author the **19 Mega-Study** experiment definitions + analyses
      (arXiv:2509.19088v3), seeded from its published materials/data — the bulk of Phase-2 work.
- [ ] Sourcing the **NULL set** for specificity (Ed calibration null + JDM registered-report
      nulls + constructed placebos; 5–8 to start).
- [ ] Clustering algo: **k-prototypes vs Gower + k-medoids**.
- [ ] Deployment target (self-hosted Qwen vs Gemini-prompting research) — doesn't block build.

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
