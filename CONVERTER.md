# Full Study → AI-Ready Converter

Tool: `convert_to_ai.py`

Takes a full Qualtrics survey, copies it into your account, strips everything the Sessions API can't handle, activates the copy, and returns a survey ID you can plug into `main.py run`.

## Usage

```bash
python convert_to_ai.py SV_xxxxFULLxxxx
```

Output ends with:

```
DONE.  New AI-ready survey: SV_yyyyyyy
  23 → 10 questions  (removed: 13)

Run with:
  python main.py run --survey-id SV_yyyyyyy
```

Options:
- `--name "Custom Name"` — override the default `"[Original Name] - AI Copy"` name
- `--no-soft-strip` — keep demographics, consent, attention checks (only strip mechanically-incompatible types). Conservative.
- `--keep-on-failure` — if conversion fails, leave the partial copy in your account for inspection instead of deleting it.

## What it strips

### Always (Sessions API rejects these — would 400 the run)
- `Slider/*` (any sub-type: HSLIDER, STAR, HBAR, VRTL)
- `Timing/*` (PageTimer, FirstClick, LastClick)
- `Captcha/V2`
- `Matrix/Likert`
- `Meta/Browser`
- `TE/PW`

If the API surfaces a new incompatible type after the conversion (`⚠️ Sessions API rejected additional types AFTER activation`), add it to `INCOMPATIBLE_TYPE_SELECTORS` in `convert_to_ai.py`.

### By default — "soft-strip" (useless for AI even if mechanically valid)
Questions whose `DataExportTag` is one of:
- `age`, `sex`, `gender` — demographics
- `consent` — informed consent form
- `check`, `AC`, `fail` — attention checks and their failure-feedback blocks
- `bot`, `Captcha` — bot screening
- `delay` — forced page timers

## Known limitation — manual cleanup step

The converter handles **questions**, not the **survey flow**. If your full survey contains a flow branch that *references* a question we strip, the branch is left dangling.

The most common case: an attention-check branch like

> `if QID34 ≠ "ride a bike (correct)" → display "you failed" block → end survey`

When `QID34` is stripped, the condition still evaluates — and since the question no longer exists, the comparison evaluates to "not equal" → the survey routes to the failure block and terminates immediately.

**Symptom**: `main.py run` against the converted survey completes sessions in zero time with `answers: {}` and the response body contains text like *"You failed an attention check embedded in a previous question."*

**Manual fix (1–2 min in Qualtrics UI):**
1. Open the converted survey in Qualtrics
2. Survey Flow tab (left sidebar)
3. Delete any **Branch** element that references a now-deleted QID (e.g. "If QID34 is not equal to ...")
4. Delete the **End of Survey** target block that the failed branch pointed to (the "you failed" block — often a DB/TB with `tag=fail`)
5. Save the flow

After this, re-run `main.py run` and the survey will progress through all questions normally.

If you do this often enough that the manual step becomes painful, the converter could be extended to also do flow-cleanup via `PUT /survey-definitions/{id}/flow`. Defer until needed.

## Workflow for a new study

```bash
# 1. Convert
python convert_to_ai.py SV_xxxFULLxxx
# → DONE. New AI-ready survey: SV_yyyyy

# 2. (If the study has attention-check routing) — open SV_yyyyy in Qualtrics UI,
#    Survey Flow tab, delete the now-orphaned attention-check branches + end blocks.

# 3. Smoke test with one persona
python main.py run --survey-id SV_yyyyy --personas biology_student_19f --runs 1

# 4. If smoke is clean, full run
python main.py run --survey-id SV_yyyyy
```

## Why deletes happen BEFORE activation (technical note)

Discovered 2026-05-25 on Hiding Success Full: the Sessions API caches the survey state at activation time. Questions deleted *after* activation are removed from `GET /survey-definitions/{id}` but still flagged as incompatible by `POST /surveys/{id}/sessions`. Toggling activation off-then-on does not refresh the cache. So the converter does all deletes during the "draft" phase, activates exactly once, and then probes — a single pass.
