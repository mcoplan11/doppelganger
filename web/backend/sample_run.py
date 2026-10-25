"""Pre-seeded sample run for new accounts.

Every new user gets one completed "sample study" in their dashboard so they can
explore real-looking results (ensemble tabs, AI analysis, respondent grid,
cross-model comparison) before connecting Qualtrics or spending credits.

The data is a hand-tuned mock of a classic 2-condition price-framing experiment
("$12/month" vs "$144/year") run through the 3-model ensemble:
  - Model A and B show a clear framing effect on subscription intent,
  - Model C shows a weaker one (mirroring the real product's "at least one
    model moves" guidance),
  - brand trust is flat everywhere (an honest null),
  - a few annual-condition respondents flag billing-cadence confusion in the
    open text, which the canned AI analysis picks up.

Nothing here touches Qualtrics or an LLM — the run row is written directly
with status="done", results_json, and responses_json.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database import Run, User

SAMPLE_SURVEY_LABEL = "Sample study — Subscription price framing"

COND_MONTHLY = "Monthly framing — $12/month"
COND_ANNUAL = "Annual framing — $144/year"

MODELS = [("model-a", "Model A"), ("model-b", "Model B"), ("model-c", "Model C")]

# Personas in the product's slug style (occupation_age+gender), 6 per condition.
PERSONAS_MONTHLY = [
    "teacher_34f", "nurse_29f", "software_dev_31m",
    "barista_22nb", "retiree_67m", "grad_student_26f",
]
PERSONAS_ANNUAL = [
    "accountant_45m", "retail_manager_38f", "truck_driver_52m",
    "freelance_designer_33f", "call_center_24m", "stay_home_parent_41f",
]

Q_SUBSCRIBE = "Likelihood to subscribe (1–7)"
Q_EXPENSIVE = "How expensive does it feel? (1–7)"
Q_PLAN = "Which plan would you choose?"
Q_TRUST = "Trust in the brand (1–5)"
Q_VALUE = "Value for money (1–5)"
Q_TEXT = "What, if anything, was confusing?"

# Scale answers: {question: {model_slug: {condition: [6 values, one per persona]}}}
# Hand-tuned so A/B show the framing effect, C is weaker, trust is flat.
SCALE_ANSWERS: dict[str, dict[str, dict[str, list[int]]]] = {
    Q_SUBSCRIBE: {
        "model-a": {COND_MONTHLY: [6, 5, 6, 5, 7, 4], COND_ANNUAL: [4, 3, 4, 2, 5, 4]},
        "model-b": {COND_MONTHLY: [5, 6, 5, 4, 6, 5], COND_ANNUAL: [4, 4, 3, 4, 5, 3]},
        "model-c": {COND_MONTHLY: [5, 4, 5, 4, 6, 4], COND_ANNUAL: [4, 5, 4, 3, 5, 4]},
    },
    Q_EXPENSIVE: {
        "model-a": {COND_MONTHLY: [3, 2, 3, 4, 2, 4], COND_ANNUAL: [5, 6, 5, 4, 6, 5]},
        "model-b": {COND_MONTHLY: [3, 4, 3, 2, 4, 4], COND_ANNUAL: [5, 5, 6, 4, 5, 5]},
        "model-c": {COND_MONTHLY: [4, 3, 4, 4, 3, 5], COND_ANNUAL: [4, 5, 4, 4, 5, 4]},
    },
    Q_TRUST: {
        "model-a": {COND_MONTHLY: [4, 3, 4, 4, 3, 4], COND_ANNUAL: [4, 4, 3, 4, 3, 4]},
        "model-b": {COND_MONTHLY: [3, 4, 4, 3, 4, 3], COND_ANNUAL: [4, 3, 4, 4, 3, 4]},
        "model-c": {COND_MONTHLY: [4, 4, 3, 4, 3, 4], COND_ANNUAL: [3, 4, 4, 3, 4, 3]},
    },
    Q_VALUE: {
        "model-a": {COND_MONTHLY: [4, 4, 3, 4, 5, 3], COND_ANNUAL: [3, 3, 4, 2, 4, 3]},
        "model-b": {COND_MONTHLY: [4, 3, 4, 4, 4, 3], COND_ANNUAL: [3, 4, 3, 3, 4, 3]},
        "model-c": {COND_MONTHLY: [4, 3, 4, 3, 4, 3], COND_ANNUAL: [3, 4, 3, 4, 3, 3]},
    },
}
SCALE_MAX = {Q_SUBSCRIBE: 7, Q_EXPENSIVE: 7, Q_TRUST: 5, Q_VALUE: 5}

PLAN_BASIC = "Basic — $7.99/mo"
PLAN_STD = "Standard — $12.49/mo"
PLAN_PREM = "Premium — $18.99/mo"
PLAN_NONE = "None of these"
PLAN_CHOICES = [PLAN_BASIC, PLAN_STD, PLAN_PREM, PLAN_NONE]

PLAN_ANSWERS: dict[str, dict[str, list[str]]] = {
    "model-a": {
        COND_MONTHLY: [PLAN_STD, PLAN_STD, PLAN_PREM, PLAN_STD, PLAN_PREM, PLAN_BASIC],
        COND_ANNUAL: [PLAN_BASIC, PLAN_NONE, PLAN_BASIC, PLAN_STD, PLAN_BASIC, PLAN_NONE],
    },
    "model-b": {
        COND_MONTHLY: [PLAN_STD, PLAN_PREM, PLAN_STD, PLAN_STD, PLAN_BASIC, PLAN_STD],
        COND_ANNUAL: [PLAN_BASIC, PLAN_BASIC, PLAN_NONE, PLAN_STD, PLAN_BASIC, PLAN_BASIC],
    },
    "model-c": {
        COND_MONTHLY: [PLAN_STD, PLAN_BASIC, PLAN_STD, PLAN_PREM, PLAN_STD, PLAN_BASIC],
        COND_ANNUAL: [PLAN_BASIC, PLAN_STD, PLAN_BASIC, PLAN_BASIC, PLAN_NONE, PLAN_STD],
    },
}

# Open text per persona — same persona keeps the same gist across models (they
# are the same simulated person), with annual respondents raising the billing
# question the AI analysis flags.
TEXT_ANSWERS: dict[str, str] = {
    "teacher_34f": "Nothing confusing — pricing was clear.",
    "nurse_29f": "No, it was straightforward.",
    "software_dev_31m": "Clear enough, though I'd want to see what's in Premium.",
    "barista_22nb": "Nothing really, pretty simple page.",
    "retiree_67m": "The plan names could explain the differences better.",
    "grad_student_26f": "Not confusing, but is there a student discount?",
    "accountant_45m": "Is the $144 charged once a year or split monthly? It doesn't say.",
    "retail_manager_38f": "Wasn't sure if I could cancel mid-year on the annual plan.",
    "truck_driver_52m": "Nothing confusing.",
    "freelance_designer_33f": "The annual price made me pause — billed upfront or monthly?",
    "call_center_24m": "Fine overall, though the annual total felt buried.",
    "stay_home_parent_41f": "Clear, but I'd like the monthly equivalent shown next to $144.",
}

INTERPRETATION = {
    "headline": (
        "Monthly price framing lifts subscription intent in 2 of 3 models — a "
        "fieldable signal, with one billing-clarity issue to fix first."
    ),
    "observations": [
        "Subscription intent is ~1.5 points higher under monthly framing in "
        "Model A and Model B; Model C shows the same direction but a smaller gap.",
        "Perceived expensiveness mirrors the effect: the identical total price "
        "feels ~2 points more expensive when framed annually.",
        "Plan choice shifts down-market under annual framing — more Basic and "
        "'None of these', fewer Standard/Premium selections.",
        "Brand trust is flat across conditions and models — the manipulation "
        "moves price perception, not brand perception.",
    ],
    "issues_to_check": [
        {
            "question": Q_TEXT,
            "concern": (
                "Several annual-condition respondents weren't sure whether $144 "
                "is billed once upfront or split monthly."
            ),
            "suggestion": (
                "State the billing cadence explicitly in the annual stimulus, "
                "e.g. '$144 billed once per year'."
            ),
        },
        {
            "question": Q_PLAN,
            "concern": (
                "Plan descriptions don't say what differs between tiers, which "
                "may add noise to the choice measure."
            ),
            "suggestion": "Add one line of feature detail per tier, or drop tiers "
                          "and measure willingness to subscribe only.",
        },
    ],
    "recommendation": (
        "Field it — the framing manipulation produces a consistent, directionally "
        "correct signal. Clarify annual billing wording first so the effect isn't "
        "confounded with billing confusion."
    ),
}


def _personas_by_condition() -> list[tuple[str, str]]:
    return [(p, COND_MONTHLY) for p in PERSONAS_MONTHLY] + [
        (p, COND_ANNUAL) for p in PERSONAS_ANNUAL
    ]


def _build_rows() -> tuple[list[str], list[dict]]:
    columns = ["model", "persona", "branch",
               Q_SUBSCRIBE, Q_EXPENSIVE, Q_PLAN, Q_TRUST, Q_VALUE, Q_TEXT]
    rows: list[dict] = []
    for slug, label in MODELS:
        for cond, personas in ((COND_MONTHLY, PERSONAS_MONTHLY),
                               (COND_ANNUAL, PERSONAS_ANNUAL)):
            for i, persona in enumerate(personas):
                rows.append({
                    "model": label,
                    "persona": persona,
                    "branch": cond,
                    Q_SUBSCRIBE: SCALE_ANSWERS[Q_SUBSCRIBE][slug][cond][i],
                    Q_EXPENSIVE: SCALE_ANSWERS[Q_EXPENSIVE][slug][cond][i],
                    Q_PLAN: PLAN_ANSWERS[slug][cond][i],
                    Q_TRUST: SCALE_ANSWERS[Q_TRUST][slug][cond][i],
                    Q_VALUE: SCALE_ANSWERS[Q_VALUE][slug][cond][i],
                    Q_TEXT: TEXT_ANSWERS[persona],
                })
    return columns, rows


def _scale_summary(values: list[int], scale_max: int) -> dict:
    """Choice-kind summary for a numeric scale, in results.py's output shape.

    Every scale point is included (zero counts allowed) so the frontend's
    min/max bounds are the full scale for every model, not just observed values.
    """
    counts = {v: values.count(v) for v in range(1, scale_max + 1)}
    return {
        "kind": "choice",
        "n": len(values),
        "distribution": [
            {"label": str(v), "count": c, "recode": v} for v, c in counts.items()
        ],
        "mean": round(sum(values) / len(values), 2),
    }


def _plan_summary(values: list[str]) -> dict:
    return {
        "kind": "choice",
        "n": len(values),
        "distribution": [
            {"label": c, "count": values.count(c), "recode": None}
            for c in PLAN_CHOICES if values.count(c) > 0
        ],
        "mean": None,
    }


def _model_results(slug: str) -> dict:
    """Per-model ResultsSummary matching results.build_results() output."""
    conditions = sorted([COND_MONTHLY, COND_ANNUAL])

    def scale_question(qid: str, prompt: str) -> dict:
        per_cond = SCALE_ANSWERS[prompt][slug]
        all_vals = per_cond[COND_MONTHLY] + per_cond[COND_ANNUAL]
        return {
            "qid": qid, "prompt": prompt, "type": "MC", "n": len(all_vals),
            "overall": _scale_summary(all_vals, SCALE_MAX[prompt]),
            "by_condition": [
                {"condition": c, **_scale_summary(per_cond[c], SCALE_MAX[prompt])}
                for c in conditions
            ],
        }

    plan_vals = PLAN_ANSWERS[slug]
    plan_q = {
        "qid": "Q3", "prompt": Q_PLAN, "type": "MC", "n": 12,
        "overall": _plan_summary(plan_vals[COND_MONTHLY] + plan_vals[COND_ANNUAL]),
        "by_condition": [
            {"condition": c, **_plan_summary(plan_vals[c])} for c in conditions
        ],
    }
    text_q = {
        "qid": "Q6", "prompt": Q_TEXT, "type": "TE", "n": 12,
        "overall": {
            "kind": "text", "n": 12,
            "responses": [TEXT_ANSWERS[p] for p, _ in _personas_by_condition()],
        },
    }
    return {
        "available": True,
        "n_completed": 12,
        "has_conditions": True,
        "conditions": conditions,
        "questions": [
            scale_question("Q1", Q_SUBSCRIBE),
            scale_question("Q2", Q_EXPENSIVE),
            plan_q,
            scale_question("Q4", Q_TRUST),
            scale_question("Q5", Q_VALUE),
            text_q,
        ],
    }


def build_sample_payloads() -> tuple[dict, dict, dict]:
    """Returns (results_json payload, responses_json payload, branch_summary)."""
    results = {
        "ensemble": True,
        "n_completed": 36,
        "models": [
            {
                "label": label, "slug": slug, "ai_survey_id": None,
                "n_completed": 12, "failed": 0, "error": None,
                "results": _model_results(slug),
            }
            for slug, label in MODELS
        ],
        "interpretation": INTERPRETATION,
    }
    columns, rows = _build_rows()
    responses = {"available": True, "columns": columns, "rows": rows}
    branch_summary = {COND_MONTHLY: 6, COND_ANNUAL: 6}
    return results, responses, branch_summary


def create_sample_run(db: Session, user_id: int) -> Run:
    """Insert the completed sample run for a newly created user. Commits."""
    results, responses, branch_summary = build_sample_payloads()
    now = datetime.now(timezone.utc)
    run = Run(
        user_id=user_id,
        original_survey_id=SAMPLE_SURVEY_LABEL,
        qualtrics_datacenter="sample",
        qualtrics_token_enc="SAMPLE",  # never decrypted — sample runs never execute
        n_participants=12,
        is_smoke_test=False,
        is_sample=True,
        platform="prolific",
        status="done",
        credits_used=0,
        branch_summary=json.dumps(branch_summary),
        results_json=json.dumps(results),
        responses_json=json.dumps(responses),
        created_at=now - timedelta(seconds=160),
        completed_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def backfill_sample_runs(db: Session) -> int:
    """Seed the sample run for every user that doesn't have one yet.

    Runs at startup so accounts created before the feature get it too.
    Idempotent — users who already have a sample run are skipped — so repeat
    boots are a cheap no-op. Returns the number of runs created.
    """
    seeded_user_ids = {
        uid for (uid,) in db.query(Run.user_id).filter(Run.is_sample.is_(True))
    }
    created = 0
    for user in db.query(User).all():
        if user.id not in seeded_user_ids:
            create_sample_run(db, user.id)
            created += 1
    return created
