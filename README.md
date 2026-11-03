# Doppelganger

AI-powered Qualtrics survey simulator. Have a panel of synthetic respondents take your survey before you field it to real participants — catch bad skip logic, ambiguous wording, and biased phrasing before you spend recruiting budget.

Live at [doppelgangerlabs.com](https://doppelgangerlabs.com).

---

## What it does

Doppelganger submits AI-generated responses to a Qualtrics survey using the **Sessions API**, so Qualtrics's server-side logic (randomizers, skip logic, branch routing) fires exactly as it would for a real respondent. Each simulated response comes from a distinct **persona** — a modeled survey-taker with a specific demographic background, platform experience, and response style (Prolific participants, MTurk workers, etc.).

You get back:
- Per-persona JSON response files
- A summary of answer distributions across all personas
- Branch assignment breakdown (for randomized studies)

This lets you pretest a survey in minutes rather than days, and it's cheaper than re-fielding a study after discovering a problem.

---

## Architecture

The project has two layers:

### CLI simulator (`/`)

Python command-line tool. Point it at a Qualtrics survey, specify a persona roster and run count, and it drives Gemini through the Sessions API to produce completed survey responses.

| File | Purpose |
|---|---|
| `main.py` | Entry point — `inspect` and `run` subcommands |
| `simulator.py` | Orchestrates per-persona sessions (sync or Gemini Batch API) |
| `gemini_client.py` | Gemini API wrapper |
| `qualtrics_client.py` | Qualtrics REST API v3 wrapper + survey definition parser |
| `personas.py` | Default roster of 100 synthetic respondents |
| `config.py` | Loads `.env` config |

**Quick start:**
```bash
# Inspect survey structure (no AI calls, no credits)
python main.py inspect

# Run all 100 personas through the survey once
python main.py run --out-dir responses/my_study

# Run specific personas, 3 times each, sync mode
python main.py run --personas biology_student_19f retail_cashier_22m --runs 3 --no-batch
```

**Required env vars (`.env`):**
```
QUALTRICS_API_TOKEN=...
QUALTRICS_DATACENTER=...    # e.g. yul1
QUALTRICS_SURVEY_ID=...     # SV_...
GEMINI_API_KEY=...
```

### Web app (`/web/`)

Self-service platform built on FastAPI (backend) + Next.js (frontend). Researchers sign in with a magic link, buy credits, and launch simulation runs from a browser — no CLI required.

```
Next.js (Vercel)  →  FastAPI (Railway)  →  Gemini API
                                        →  Qualtrics API
                                        →  Postgres
```

**Key design decisions:**
- **1 credit = 1 simulated participant.** Credits deducted on completion, not on start.
- **Smoke test is free.** Every run begins with a 5-participant preview before committing credits.
- **Shared Gemini key.** The app absorbs Gemini costs; users bring their own Qualtrics API token per run.
- **Magic link auth.** No passwords — enter email, click link, get a session cookie.
- **Async runs.** Simulations run as background tasks; the UI polls for status.

**Credit packs (v1):**

| Pack | Credits | Price |
|---|---|---|
| Starter | 50 | $4.99 |
| Standard | 100 | $8.99 |
| Pro | 250 | $19.99 |
| Research | 500 | $34.99 |

---

## Personas

The default roster (`personas.py`) models 100 online survey-takers — skewed younger and more educated than the US population, reflecting the actual demographics of Prolific and MTurk panels. Each persona has a name, age, occupation, platform experience, and response style (e.g. straight-liners, attention-check hunters, neutral-option clickers).

An earlier roster of 10 "average American" demographics is preserved in `personas_v1_demographic_americans.py.bak` for comparison.

---

## What the LLM prompt looks like

Each time Qualtrics returns a block of questions, the simulator sends one prompt to Gemini per question (in batch mode) or one prompt per block (in sync mode). The prompt is assembled in `gemini_client.py:_build_prompt`.

Here is a concrete example for `biology_student_19f` mid-survey, where she's already answered one question and is now seeing a matrix rating question:

```
You are responding to a Qualtrics survey, staying fully in character as this persona:

PERSONA: biology_student_19f
19-year-old biology student at a state university in Illinois. High school diploma.
Takes Prolific surveys on her phone between classes for coffee money. She skims
vignettes looking for keywords and clicks neutral options if a matrix question
looks too long.

Answer as this persona would — with their biases, blind spots, and rhythm.
Do not be artificially neutral or balanced.

SURVEY: Housing Preferences Study

WHAT YOU'VE READ SO FAR (instructions and scenario shown to you in this order —
no response required, but treat them as the situation you are now responding to):
  (1) Imagine you are searching for an apartment near campus. You have found a unit
      you like, but the landlord says there is a 6-week wait before you can move in.

YOUR ANSWERS SO FAR (stay consistent with these):
  [QID1] How acceptable is a 6-week wait before moving in?
    → Somewhat unacceptable

NEW QUESTIONS — answer each:

[QID2] (Matrix/Likert) Please rate how much each of the following factors
influences your decision to wait for a rental unit.
  Rate each row on the scale below:
    row sub_id=1: Price of the unit
    row sub_id=2: Distance from campus
    row sub_id=3: Quality of the building
    scale choice_id=1 (recode=1): Not at all influential
    scale choice_id=2 (recode=2): Slightly influential
    scale choice_id=3 (recode=3): Moderately influential
    scale choice_id=4 (recode=4): Very influential
    scale choice_id=5 (recode=5): Extremely influential

Return only JSON matching the provided schema.
```

Gemini is also given a **JSON schema** that constrains its output to valid choice IDs — so it can only return `"1"` through `"5"` for a 5-point scale, never free text. For the matrix above the schema looks like:

```json
{
  "type": "object",
  "properties": {
    "QID2": {
      "type": "object",
      "properties": {
        "1": {"type": "string", "enum": ["1","2","3","4","5"]},
        "2": {"type": "string", "enum": ["1","2","3","4","5"]},
        "3": {"type": "string", "enum": ["1","2","3","4","5"]}
      },
      "required": ["1","2","3","4","5"]
    }
  },
  "required": ["QID2"]
}
```

And a typical response:

```json
{"QID2": {"1": "5", "2": "3", "3": "3"}}
```

The simulator then translates these choice IDs into the Sessions API format (`{choiceId: {"selected": true}}`) and POSTs them to Qualtrics to advance the session to the next block.

**Three context layers** accumulate as the session progresses:
1. **`read_context`** — text-only (DB) blocks the persona has "seen" on screen, included verbatim so later answers are grounded in the scenario.
2. **`prior_answers`** — all questions answered so far, shown as human-readable labels (not raw IDs) so the model stays internally consistent.
3. **`new questions`** — the current block's answerable questions, each with full choice text and IDs.

---

## Survey compatibility

Doppelganger uses the Qualtrics **Sessions API** (not the bulk response endpoint) so branching and skip logic fires server-side. This means:

- Randomizer elements are supported — Qualtrics assigns branches, not the simulator.
- Image stimuli (ads, product photos) are supported — `<img>` tags in question or descriptive text are extracted (`stimuli.py`), downloaded once per unique image, and attached to the LLM call as multimodal content. The web app detects image surveys automatically and routes them to a vision-capable model roster (`ensemble.VISION_ROSTER`); text-only surveys keep the benchmark-validated default roster.
- Slider questions are **not** supported by the Sessions API, so the converter automatically rebuilds each one as a numeric text-entry question on the same min–max scale (Matrix-Likert questions are similarly converted to multiple choice). CAPTCHA blocks and end-of-survey redirect flows are removed. See `CONVERTER.md` for the conversion workflow.

---

## Deployment

| Service | Provider | URL |
|---|---|---|
| Frontend | Vercel | https://doppelgangerlabs.com |
| Backend | Railway | https://api.doppelgangerlabs.com |
| Email | Resend | hello@doppelgangerlabs.com |
| DNS | Cloudflare | — |

See `web/docs/DEPLOY.md` for full deployment instructions and env var reference.

---

## Development setup

```bash
# Python (requires pyenv + Python 3.11.8)
pyenv activate env_3.11.8
pip install -r requirements.txt
cp .env.example .env   # fill in your keys

# Web backend
cd web/backend
pip install -r requirements.txt
uvicorn main:app --reload

# Web frontend
cd web/frontend
npm install
cp .env.local.example .env.local
npm run dev
```

See `web/docs/SETUP.md` for the full local setup guide.
