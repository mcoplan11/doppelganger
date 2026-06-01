# Validation results — 2026-05-21

Snapshot of all calibration runs done this day against the Ed and Selin studies. Saved so future Annabelle can look back at exactly what was tested and what was found.

## Studies

| Study | Survey ID | Real-world result | DV |
|---|---|---|---|
| **Ed** (work vs leisure choice) | `SV_50zu2tznyCiX7oO` | Other 58% / Self 61% / Self+intervention 63%, p = .756 (null), N=300 | choice (QID177/QID180): "1" = productive, "2" = enjoyable |
| **Selin** (fast vs slow wait) | `SV_4YMErTBas8bqRJc` | Fast M = 49.94 (SD=21.40) / Slow M = 39.01 (SD=21.05), p < .001, d = 0.51, N=400 | % likelihood of acceptance (QID38), 0–100 |

## All runs

| Run | Model | Temp | N | Out dir |
|---|---|---|---|---|
| 1 | gemini-3.1-flash-lite | 0.5 | 100 | `responses/ed_t05/` |
| 2 | gemini-3.1-flash-lite | 0.9 | 100 | `responses/ed_t09/` |
| 3 | gemini-3.1-flash-lite | 0.5 | 100 | `responses/selin_t05/` |
| 4 | gemini-3.1-flash-lite | 0.9 | 100 | `responses/selin_t09/` |
| 5 | gemini-3.5-flash | 0.9 | 100 | `responses/selin_t09_flash/` |
| 6 | gemini-3.5-flash | 0.5 | 100 | `responses/selin_t05_flash/` |

Personas: v2 Prolific-modeled roster (100 personas in `personas.py`). Same roster across all runs.

## Selin — final 4-way comparison

Real: fast 49.94 (21.40) / slow 39.01 (21.05), diff +10.93, p < .001, d = 0.51

| Config | fast M (SD) | slow M (SD) | diff | p | d | % of real effect |
|---|---|---|---|---|---|---|
| flash-lite × T=0.5 | 53.37 (14.22) | 50.00 (8.29) | +3.37 | .162 | 0.29 | 31% |
| flash-lite × T=0.9 | 53.23 (10.54) | 51.84 (11.76) | +1.39 | .539 | 0.12 | 13% |
| flash × T=0.9 | 48.70 (11.90) | 43.60 (13.21) | +5.10 | .043 | 0.41 | 47% |
| **flash × T=0.5** | **50.90 (12.19)** | **40.51 (11.91)** | **+10.39** | **<.001** | **0.86** | **95%** |

### Slow-condition distribution (% in 40–50 bucket vs % below 40)

| Config | anchored to 40–50% | below 40% (real pessimism) |
|---|---|---|
| flash-lite × T=0.5 | 82% | 4% |
| flash-lite × T=0.9 | 76% | 4% |
| flash × T=0.9 | 48% | 22% |
| **flash × T=0.5** | **41%** | **39%** |

Real respondents (with SD ~21 around M ~39) would have a lot of mass below 40 — `flash × T=0.5` reproduces this.

## Ed — temperature comparison (flash-lite only)

Real: other 58% / self 61% / self+intervention 63%, p = .756 (null), N=300

| Config | other | self | self+int | spread | χ²(2) | p |
|---|---|---|---|---|---|---|
| flash-lite × T=0.5 | 76% | 87% | 88% | 13pp | 2.46 | .29 |
| flash-lite × T=0.9 | 71% | 91% | 77% | 20pp | 4.15 | .13 |

Both temperatures **correctly reach the null** (matches real p = .756) but **both overshoot %productive by ~20pp** at the aggregate level (AI ~80% vs real ~61%).

**Ed × flash has not been run yet** — open question whether the model upgrade also fixes the %productive overshoot.

## Key findings

1. **Model size matters more than temperature** for inferential manipulations. `flash-lite` couldn't connect "long wait" to "rejection signal" — 76–82% of slow personas anchored at 50%. `flash` made the inference (only 41% anchored at T=0.5) and produced reasoning text matching real respondents.

2. **Within `flash-lite`, T=0.5 > T=0.9** on both studies. Mechanism: at higher T, the LLM samples more uniformly and arms converge on the prior (~50% for binary-likelihood questions).

3. **Within `flash`, T=0.5 > T=0.9** also holds. T=0.5 captures 95% of real effect; T=0.9 captures 47%. Bigger model + lower temperature: both moves required.

4. **AI Cohen's d (0.86) is bigger than real d (0.51)** at the winning config. Reason: AI SDs ~12 vs real ~21. The AI catches the means almost exactly but is more decisive (less within-arm variance) than real respondents. For power analysis, use real-population SDs, not AI ones — otherwise you'll under-power.

5. **Sample reasoning at flash × T=0.5, slow condition:**
   > "If they really wanted to sell to me they wouldn't have made me wait three days, so I'm probably just the backup plan." — `truck_driver_51m`, 30%
   >
   > "If it was good news they would have heard back sooner." — `junior_designer_23f`, 0%

   This matches real-respondent inference. Was completely absent at `flash-lite`.

6. **My earlier "AI is under-experiential" diagnosis was partly wrong.** The smaller model couldn't make the inferential leap from "long wait" → "rejection." It wasn't a missing emotional intuition — it was missing reasoning capability. Bigger model + same personas + lower temp largely closed the gap.

## What we don't yet know

- Does `flash` also fix Ed's %productive overshoot? (Run Ed × flash × T=0.5 to find out.)
- Would `gemini-3.5-pro` capture the full 100% of real Selin effect, or are we hitting a ceiling? (~30× cost; probably not worth it given flash × T=0.5 is already at 95%.)
- Are these results robust to a different persona roster? Untested.
- Are these results robust at smaller N? Untested. With N=100 per cell we get clean stats; an N=25 pilot might be too noisy.

## Cost note

`flash` is ~5× the per-call cost of `flash-lite`. Selin × 100 personas at `flash` ran in ~30 min for a few dollars. Still negligible for real research workflows.

## Raw data

All session-level JSON artifacts are in `responses/`. Each file is one persona × one survey × one model/temp combo. To re-analyze any cell, see `analyze.py` for the loader patterns and the DV mappings.
