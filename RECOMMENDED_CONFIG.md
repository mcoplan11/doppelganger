# Recommended config for AI survey simulation

Last validated: 2026-05-21 against the Ed and Selin studies.

## Settings

| Setting | Value | Where it lives |
|---|---|---|
| `GEMINI_MODEL` | **`gemini-2.5-flash`** (cost-saving; not yet validated — see Caveats) | `.env` |
| `--temperature` | **`0.5`** | CLI flag on `python main.py run` |
| Persona roster | v2 + v3 (200 personas across `personas.py` + `responses/generated_v3.json`) | already set |
| Runs per persona | `1` | CLI default |
| Batch API | auto (sync when total sessions ≤ 20, batch otherwise) | `--batch` / `--no-batch` to override |

## Quick start

```bash
eval "$(pyenv init -)" && eval "$(pyenv virtualenv-init -)" && pyenv activate env_3.11.8
python main.py run --temperature 0.5 --survey-id SV_XXXXXXXXXXXX --out-dir responses/<name>
```

If your `.env` still has `GEMINI_MODEL=gemini-3.1-flash-lite`, either update it to `gemini-3.5-flash` or prefix the command with `GEMINI_MODEL=gemini-3.5-flash`.

## Why these values — evidence

### Model: `gemini-3.5-flash`

Direct A/B on Selin (real fast−slow diff = +10.93, p<.001, d=0.51):

| Model | fast M | slow M | diff | p | d | % of real effect |
|---|---|---|---|---|---|---|
| `gemini-3.1-flash-lite` | 53.23 | 51.84 | +1.39 | .54 (NS) | 0.12 | 13% |
| `gemini-3.5-flash` | 48.70 | 43.60 | +5.10 | **.042** | 0.41 | **47%** |

The smaller model (`flash-lite`) couldn't connect "long wait" to "rejection signal" — 76% of slow personas anchored to 50%. The larger model (`flash`) made the inferential leap and produced reasoning text matching real respondents:

> "If they really wanted to sell to me they wouldn't have made me wait three days, so I'm probably just the backup plan." — `truck_driver_51m`, 30%

Cost difference is ~5× per call; absolute cost is still small (~$1–3 per 100-persona Selin-sized run).

### Temperature: `0.5`

Direct A/B on both studies at `flash-lite`:

**Ed (real: 58/61/63%, p=.756 null):**
| T | spread | ordering | p |
|---|---|---|---|
| 0.5 | 13pp | other (76) < self (87) < self+intervention (88) — monotone matches real | .29 |
| 0.9 | 20pp | other (71) < self+intervention (77) < self (91) — non-monotone | .13 |

**Selin (real: fast 49.94 / slow 39.01):**
| T | diff | d | % of real effect |
|---|---|---|---|
| 0.5 | +3.37 | 0.29 | 31% |
| 0.9 | +1.39 | 0.12 | 13% |

Mechanism: at higher temperature the LLM samples more uniformly and both arms drift toward the prior (~50% for binary-likelihood questions). At lower temperature the manipulation has more pull on the modal answer.

**Validated at `gemini-3.5-flash` too (2026-05-21):**

| Config | Selin diff | p | d | % of real effect |
|---|---|---|---|---|
| flash × T=0.9 | +5.10 | .043 | 0.41 | 47% |
| **flash × T=0.5** | **+10.39** | **<.001** | **0.86** | **95%** |

Means at flash × T=0.5: fast 50.90 (real 49.94), slow 40.51 (real 39.01). The combination captures essentially the entire real effect.

## What this config is good for

- **Cognitive manipulation studies (Ed-like)**: AI correctly signals null when null exists. Treat results as a reliable "would I find anything?" pre-test.
- **Visceral / inferential manipulation studies (Selin-like)**: AI captures ~half the true effect magnitude. Useful for sign and direction, undersized in magnitude.

## What it's not good for (yet)

- **Absolute level prediction.** The AI still over-predicts %productive on Ed (~80% vs real 61%). It catches the *shape* of the data but not the *level*.
- **Tasks where the gut-level signal is the manipulation.** Even at flash, the AI may under-call effects that real respondents pick up viscerally.

## Open questions

- Does `flash @ T=0.5` outperform `flash @ T=0.9` on Selin? (Not yet tested.)
- Does upgrading to `flash` fix Ed's overshoot on %productive? (Run pending.)
- Would `gemini-3.5-pro` capture the full real effect, or are we hitting a fundamental ceiling for LLM simulation of human respondents? (Untested; ~30× cost.)

## How this file should be maintained

After any future calibration run against a new benchmark study, update the headline numbers and recommendations here. If the recommendation changes, also update `.env` and the `--temperature` default in `main.py`.

Related memory:
- `~/.claude/projects/-Users-mitchell-coplan-VsCode-qualtrics-ai/memory/project_calibration_ed_selin.md` — full calibration history
