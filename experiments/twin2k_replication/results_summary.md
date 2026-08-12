# Twin-2K-500 Replication — Model Results Summary

Purpose: pick which models to run in the ensemble. Scoring rule (same as the
preprint): an effect counts as **reproduced** when the simulated sample shows a
statistically significant result (p < .05) in the direction the original
authors predicted. `~` = partial (0.5). Battery = 17 classic experiments,
N ≈ 150 personas/experiment, temp 0.5.

Source runs are under `results/<timestamp>/report.md`. The preprint anonymizes
these as Model A–E; below they are de-anonymized to the real models.

---

## 1. Per-model ranking (individual score /17)

| Rank | Model | Score | Run dir |
|-----|-------|------|---------|
| 1 | **glm-5.2** (`z-ai/glm-5.2`) | **13.5** | `20260809_201050` |
| 2 | **qwen3.7-max** (`qwen/qwen3.7-max`) | **12.5** | `20260613_222645` |
| 2 | **qwen3-235b-a22b-2507** (`qwen/qwen3-235b-a22b-2507`) | **12.5** | `20260614_104358` |
| 4 | **gemini-3.5-flash** | **12.0** | `20260607_173525` |
| 5 | gpt-5.6-luna — reasoning (`openai/gpt-5.6-luna`) | 10.5 | `20260809_150620_luna_reasoning` |
| 6 | qwen3-30b-a3b-instruct-2507 | 10.0 | `20260608_211042` / `20260614_201511` (reran, same score) |
| 7 | gpt-5.6-luna — no reasoning | 8.5 | `20260809_111411` |
| 7 | qwen3-14b | 8.5 | `20260614_202236` |

Notes
- **Reasoning helps gpt-5.6-luna** (10.5 vs 8.5). Prefer the reasoning config.
- **qwen3-30b is stable**: two independent runs both landed at 10.0/17.
- Early `gemini-2.0-flash-exp` / `gemini-2.5-flash` runs (`20260607_134842`,
  `20260607_134903`) were N=3 pilots / failed parses — excluded.

---

## 2. Full replication matrix

`Y` = reproduced · `~` = partial · `x` = not reproduced

| Experiment | glm-5.2 | qwen3.7-max | qwen3-235b | gemini-3.5 | luna(rsn) | qwen3-30b | luna | qwen3-14b |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| framing | Y | Y | Y | Y | Y | Y | Y | Y |
| linda (conjunction) | Y | Y | Y | Y | Y | Y | Y | Y |
| anchoring (redwood) | Y | Y | Y | Y | Y | x | Y | Y |
| anchoring (mississippi) | Y | Y | Y | Y | Y | Y | Y | Y |
| savings (abs vs rel) | Y | Y | Y | x | Y | Y | x | x |
| myside bias | Y | Y | Y | Y | x | Y | x | Y |
| less-is-more | **Y** | x | x | x | x | x | x | x |
| sunk cost | Y | Y | Y | Y | Y | Y | x | x |
| outcome bias | Y | Y | Y | Y | Y | Y | Y | Y |
| allais | Y | Y | Y | Y | Y | Y | Y | Y |
| base rate | Y | Y | Y | Y | Y | Y | Y | x |
| false consensus | Y | Y | Y | Y | Y | Y | Y | Y |
| risk–benefit | x | x | **Y** | x | x | x | x | x |
| omission bias | **Y** | x | x | x | x | x | x | x |
| probability matching | x | **Y** | x | **Y** | x | x | x | x |
| wta/wtp (endowment) | ~ | ~ | ~ | **Y** | ~ | x | ~ | ~ |
| dominator neglect | x | x | x | x | x | x | x | x |
| **Total** | **13.5** | **12.5** | **12.5** | **12.0** | **10.5** | **10.0** | **8.5** | **8.5** |

---

## 3. Who covers the "hard" effects (the ones that decide the ensemble)

Most effects are reproduced by nearly everyone. The ensemble is really decided
by a handful of rare captures:

| Hard effect | Only reproduced by |
|---|---|
| **less-is-more** | glm-5.2 (only model, full) |
| **omission bias** | glm-5.2 (only model, full) |
| **risk–benefit nonseparability** | qwen3-235b-a22b-2507 (only model, full) |
| **probability matching** | qwen3.7-max **or** gemini-3.5-flash |
| **endowment (wta/wtp), FULL** | gemini-3.5-flash (only full Y; everyone else is partial `~`) |
| **dominator neglect** | nobody — unreproducible across all models |

The endowment result is the important one: the preprint reports it as **Partial**
for its 5-model ensemble because **gemini-3.5-flash was not in that ensemble**.
gemini-3.5-flash is the only model that gets endowment to a full, correctly
ordered significant effect.

---

## 4. Recommended ensembles

Scoring counts an effect reproduced if **any** ensemble member shows it.

### ⭐ Best minimal ensemble — 3 models → **16 / 17 (94%)**
- **glm-5.2** — top overall; sole source of less-is-more + omission bias
- **qwen3-235b-a22b-2507** — sole source of risk–benefit
- **gemini-3.5-flash** — sole full source of endowment; also gets probability matching

This 3-model set covers **every reproducible effect** and beats the preprint's
published 5-model ensemble (15.5/17) by fully capturing endowment. Only
dominator neglect remains unreproduced (no model reproduces it).

### Robust ensemble — add a 4th for redundancy → 16 / 17
Add **qwen3.7-max** (backs up probability matching and the mid-tier effects
savings/sunk-cost/base-rate). Doesn't raise the ceiling but reduces reliance on
any single model for the rare captures.

### If you must include gpt-5.6-luna
Use the **reasoning** config (10.5), not the plain one (8.5). It adds no unique
capture over the trio above, so it's optional.

### Skip
- **qwen3-14b** (8.5) — dominated; every effect it gets is covered by stronger models.
- **dominator neglect** — don't expect any model to hit it; it's a known ceiling.

---

## 5. One-line takeaway
Run **glm-5.2 + qwen3-235b-a22b-2507 + gemini-3.5-flash** for a 16/17 ensemble.
glm-5.2 is the best single model; gemini-3.5-flash is the non-obvious must-have
(only model that fully reproduces the endowment effect).
