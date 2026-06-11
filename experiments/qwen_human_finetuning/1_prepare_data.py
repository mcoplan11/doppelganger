#!/usr/bin/env python3
"""
1_prepare_data.py — Build SFT training data from Twin-2K-500 behavioral experiments

Maps our 16 bias experiments to their corresponding Twin-2K catalog QIDs, then pairs
each real human's answer (wave4_response_label.csv) with the AI persona that maps to
that participant (sequential cycling across 100 personas).

IMPORTANT: Twin-2K uses different scenario versions for some experiments:
  - Sunk cost   → coffee shop (not ski trips)
  - Anchoring   → African countries (not Mississippi River) + Redwood tree
  - Savings     → calculator $30→$20 / jacket $250→$240
  - Myside      → Ford Explorer vs German car (both "8x more deadly")
  - Less is More → gambles (not ice cream cups)
  - WTA/WTP     → vaccine risk scenarios (not lottery tickets)
The fine-tuning uses the Twin-2K versions; evaluation uses experiments.json versions.
This is intentional — we're teaching human-like PATTERNS, not identical scenarios.

Persona mapping (sequential, cycling every 100):
  pid sorted position 0   → DEFAULT_PERSONAS[0]  (biology_student_19f)
  pid sorted position 1   → DEFAULT_PERSONAS[1]  (retail_cashier_22m)
  ...
  pid sorted position 100 → DEFAULT_PERSONAS[0]  (wraps)

Usage:
  python 1_prepare_data.py --preview           # print mapping + 4 examples, exit
  python 1_prepare_data.py                     # build full dataset
  python 1_prepare_data.py --max-examples 100000
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TWIN2K_DIR = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))

from personas import DEFAULT_PERSONAS

DATASET_ID = "LLM-Digital-Twin/Twin-2K-500"
CATALOG_FILE = "question_catalog_and_human_response_csv/question_catalog.json"
WAVE4_LABEL_FILE = "question_catalog_and_human_response_csv/wave4_response_label.csv"

# ── Manual QID map ────────────────────────────────────────────────────────────
# Maps "<exp_id>::<condition_id>" → csv_column in wave4_response_label.csv
# Each tuple is (csv_column, notes).
# Complex experiments (false_consensus, risk_benefit, etc.) handled separately below.
CONDITION_TO_COLUMN: dict[str, str] = {
    # Framing (Asian Disease — gain vs loss frame)
    "framing::gain":   "QID157",
    "framing::loss":   "QID158",

    # Linda handled by build_linda_examples() — needs sequential row context

    # Anchoring Redwood Tree (Twin-2K anchors: 85ft vs 1000ft; we have 180ft vs 1200ft)
    "anchoring_redwood::low_anchor":  "QID168_TEXT",
    "anchoring_redwood::high_anchor": "QID170_TEXT",

    # Anchoring African Countries (replaces Mississippi River in Twin-2K)
    "anchoring_mississippi::low_anchor":  "QID164_TEXT",
    "anchoring_mississippi::high_anchor": "QID166_TEXT",

    # Savings — Absolute vs. Relative (calculator $30→$20 = cheap; jacket $250→$240 = expensive)
    "savings::cheap_item":     "QID183",
    "savings::expensive_item": "QID184",

    # Myside Bias (Ford Explorer = domestic; German car = foreign; both 8x more deadly)
    "myside::domestic": "QID194",
    "myside::foreign":  "QID195",

    # Less is More — Gamble version (no ice cream cups in Twin-2K)
    # Gamble A: 7/36 win $9 / 29/36 win $0  (less: no downside)
    # Gamble B: 7/36 win $9 / 29/36 lose $0.05  (more: tiny loss added, but actually rated lower)
    "less_is_more::overfilled":  "QID171",
    "less_is_more::underfilled": "QID172",

    # WTA/WTP — Vaccine risk scenarios (not lottery tickets)
    # WTP certain (1/1000 death): QID189; WTP noncertain (4/1000 death): QID191
    # WTA certain (4/1000 exposure, min$ to participate): QID190
    "wta_wtp::wtp_certain":    "QID189",
    "wta_wtp::wta_certain":    "QID190",
    "wta_wtp::wtp_noncertain": "QID191",

    # Allais (same structure as our version)
    "allais::problem1": "QID192",
    "allais::problem2": "QID193",

    # Myside Ford/German already above; extra alias for our exp_id names
    # (already correct above)

    # Sunk Cost — Coffee Shop version (not ski trips)
    # QID181_TEXT: no sunk cost ($1.50 Coffee Connection vs $2.00 Java, 10 min away)
    # QID182_TEXT: with sunk cost ($50 card already paid for Coffee Connection)
    # Answer = how many of next 20 purchases from Java Coffee (0–20)
    "sunk_cost::free": "QID181_TEXT",
    "sunk_cost::paid": "QID182_TEXT",

    # Outcome Bias (same heart-surgery scenario as our version)
    "outcome_bias::good_outcome": "QID161",
    "outcome_bias::bad_outcome":  "QID162",

    # Base Rate — Jack engineer/lawyer (same Jack description as our version)
    "base_rate::low_baserate":  "QID154",   # Slider: 30 engineers / 70 lawyers
    "base_rate::high_baserate": "QID156",   # Slider: 70 engineers / 30 lawyers

    # Omission Bias (single-condition in Twin-2K; we'll use it as the "commission" condition)
    "omission_bias::commission": "QID291",

    # Probability Matching — two problems in Twin-2K
    # QID198: 10-card deck (7 "1"s, 3 "2"s) — predict all 10 shuffles
    # QID203: 4-red/2-green die — predict all 6 rolls
    # We'll use each roll/shuffle as a separate training row (see complex handler)
    # (handled in build_complex_examples)

    # Proportion Dominance / Dominator Neglect
    # QID174–176: fire extinguisher (1A/1B/1C); QID177–179: seatbelt (2A/2B/2C)
    # (handled in build_complex_examples)
}

# Scale labels used in Twin-2K catalog (need integer rank for training)
# Maps option text → integer rank (1-indexed from left)
LINDA_SCALE = ["Extremely improbable", "Very improbable", "Somewhat probable",
               "Moderately probable", "Very probable", "Extremely probable"]

OUTCOME_BIAS_SCALE = [
    "Incorrect, a very bad decision", "Incorrect, all things considered",
    "Incorrect, but not unreasonable", "The decision and its opposite are equally good",
    "Correct, but the opposite would be reasonable too", "Correct, all things considered",
    "Clearly correct, an excellent decision",
]

POLICY_SCALE = [  # QID287 false consensus own-view
    "Strongly oppose", "Somewhat oppose", "Neither oppose nor support",
    "Somewhat support", "Strongly support"
]


# ── HuggingFace helpers ───────────────────────────────────────────────────────

def _inject_ssl() -> None:
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass  # only needed behind a corporate SSL proxy (e.g. local dev); skip on RunPod


def load_question_catalog() -> dict[str, dict]:
    """Returns dict keyed by QID."""
    _inject_ssl()
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id=DATASET_ID, filename=CATALOG_FILE, repo_type="dataset")
    with open(path) as f:
        entries = json.load(f)
    return {q["QuestionID"]: q for q in entries}


def load_response_labels() -> pd.DataFrame:
    """Wave-4 responses indexed by pid."""
    _inject_ssl()
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id=DATASET_ID, filename=WAVE4_LABEL_FILE, repo_type="dataset")
    df = pd.read_csv(path, dtype=str)
    first_col = df.columns[0]
    if first_col.lower() != "pid":
        df = df.rename(columns={first_col: "pid"})
    return df.set_index("pid")


def load_pids_sorted(df: pd.DataFrame) -> list[str]:
    """Sort pids numerically from the label DataFrame (avoids datasets/_lzma dep)."""
    pids = df.index.tolist()
    return sorted(pids, key=lambda p: int(p) if str(p).isdigit() else p)


# ── Persona mapping ───────────────────────────────────────────────────────────

def build_pid_to_persona(pids: list[str], max_per_persona: int = 2) -> dict[str, Any]:
    """Map sorted pids to personas, capping at max_per_persona participants per persona.

    With 200 personas and max_per_persona=2 we use 400 participants total,
    giving each persona exactly 2 real-human training examples — appropriate
    for LoRA which needs far fewer examples than full fine-tuning.
    """
    n = len(DEFAULT_PERSONAS)
    cutoff = n * max_per_persona   # first N*max pids only
    return {
        pid: DEFAULT_PERSONAS[i % n]
        for i, pid in enumerate(pids)
        if i < cutoff
    }


# ── Prompt / answer builders ──────────────────────────────────────────────────

_PERSONA_HEADER = (
    "You are responding to a Qualtrics survey, staying fully in character as this persona:\n\n"
    "PERSONA: {name}\n{description}\n\n"
    "Answer as this persona would — with their biases, blind spots, and rhythm. "
    "Do not be artificially neutral or balanced.\n"
)


def _persona_block(persona) -> str:
    return _PERSONA_HEADER.format(name=persona.name, description=persona.description)


def build_mc_prompt(persona, catalog_entry: dict,
                    prior_qa: list[tuple[str, str]] | None = None) -> str:
    """Prompt for a multiple-choice question using catalog text and options."""
    options = catalog_entry.get("Options", [])
    lines = [_persona_block(persona)]
    if prior_qa:
        lines.append(_prior_context_block(prior_qa))
    lines += [catalog_entry["QuestionText"], "", "OPTIONS:"]
    for i, opt in enumerate(options):
        lines.append(f"  {chr(65+i)}: {opt}")
    lines.append("")
    ids = [chr(65 + i) for i in range(len(options))]
    lines.append(f'Return JSON: {{"answer": "<one of {ids}>"}}\n')
    return "\n".join(lines)


def build_scale_prompt(persona, catalog_entry: dict, row_idx: int | None = None,
                       prior_qa: list[tuple[str, str]] | None = None) -> str:
    """Prompt for a matrix row (Likert) or slider (ordinal scale)."""
    columns = catalog_entry.get("Columns", [])
    question = catalog_entry["QuestionText"]
    rows = catalog_entry.get("Rows", [])
    min_v, max_v = 1, len(columns) if columns else 100

    lines = [_persona_block(persona)]
    if prior_qa:
        lines.append(_prior_context_block(prior_qa))
    lines.append(question)
    if row_idx is not None and rows:
        lines += ["", f'Statement: "{rows[row_idx]}"']
    if columns:
        lines += ["", f"Scale: {' | '.join(columns)}"]
        lines.append("")
        lines.append(
            f"Return JSON: {{\"answer\": <integer {min_v}–{max_v} "
            f"where 1={columns[0]!r} and {max_v}={columns[-1]!r}>}}\n"
        )
    else:  # Slider — open numeric
        lines += ["", "Return JSON: {\"answer\": <number 0–100>}\n"]
    return "\n".join(lines)


def build_numeric_prompt(persona, catalog_entry: dict,
                         prior_qa: list[tuple[str, str]] | None = None) -> str:
    """Prompt for a free-text numeric question."""
    lines = [_persona_block(persona)]
    if prior_qa:
        lines.append(_prior_context_block(prior_qa))
    lines += [
        catalog_entry["QuestionText"],
        "",
        'Return JSON: {"answer": <number>}\n',
    ]
    return "\n".join(lines)


def _mc_answer(raw: str, catalog_entry: dict) -> str | None:
    """Parse label-CSV text → option letter (A, B, C…)."""
    options = catalog_entry.get("Options", [])
    if not options:
        return None
    raw = str(raw).strip()
    for i, opt in enumerate(options):
        if raw == opt or raw.lower() == opt.lower():
            return chr(65 + i)
    # Fallback: find best substring match
    import difflib
    scores = [
        (difflib.SequenceMatcher(None, raw.lower(), opt.lower()).ratio(), i)
        for i, opt in enumerate(options)
    ]
    best_score, best_i = max(scores, key=lambda x: x[0])
    return chr(65 + best_i) if best_score >= 0.4 else None


def _scale_answer(raw: str, scale_labels: list[str]) -> int | None:
    """Convert label text → integer rank (1-indexed)."""
    raw = str(raw).strip()
    for i, label in enumerate(scale_labels):
        if raw.lower() == label.lower():
            return i + 1
    # Try parsing as number
    try:
        val = int(float(raw))
        if 1 <= val <= len(scale_labels):
            return val
    except ValueError:
        pass
    return None


def _numeric_answer(raw: str) -> float | None:
    try:
        return float(str(raw).strip().replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return None


def _make_example(prompt: str, answer: Any) -> dict:
    return {
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": json.dumps({"answer": answer})},
        ]
    }


def _prior_context_block(prior_qa: list[tuple[str, str]]) -> str:
    """Format prior Q&A as 'YOUR ANSWERS SO FAR' — matches simulator's sequential context."""
    if not prior_qa:
        return ""
    lines = ["YOUR ANSWERS SO FAR (stay consistent with these):"]
    for q_text, a_text in prior_qa:
        lines.append(f"  {q_text}")
        lines.append(f"    → {a_text}")
    return "\n".join(lines) + "\n\n"


# ── Simple condition → column examples ───────────────────────────────────────

def build_simple_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """Build training examples for all conditions in CONDITION_TO_COLUMN."""
    examples: list[dict] = []
    exp_path = TWIN2K_DIR / "experiments.json"
    with open(exp_path) as f:
        experiments = json.load(f)
    exp_by_id = {e["id"]: e for e in experiments}

    for key, csv_col in CONDITION_TO_COLUMN.items():
        exp_id, cond_id = key.split("::", 1)
        if csv_col not in df.columns:
            print(f"  [SKIP] {key}: column {csv_col!r} not in wave4 CSV")
            continue

        # Get the catalog entry for this column's base QID
        base_qid = csv_col.split("_")[0]  # e.g. QID159_3 → QID159
        if base_qid not in catalog:
            print(f"  [SKIP] {key}: QID {base_qid} not in catalog")
            continue
        cat_entry = catalog[base_qid]

        # Determine row index for matrix questions (e.g. QID159_3 → row_idx=2)
        row_idx = None
        if "_" in csv_col and csv_col.split("_")[-1].isdigit():
            row_idx = int(csv_col.split("_")[-1]) - 1

        qtype = cat_entry.get("QuestionType", "")
        columns = cat_entry.get("Columns", [])

        count_before = len(examples)
        for pid, persona in pid_to_persona.items():
            if pid not in df.index:
                continue
            raw = df.at[pid, csv_col]
            if pd.isna(raw) or str(raw).strip() in ("", "nan"):
                continue

            # Parse answer + build prompt based on question type
            if csv_col.endswith("_TEXT") or qtype == "TE":
                answer = _numeric_answer(raw)
                prompt = build_numeric_prompt(persona, cat_entry)
            elif qtype == "Matrix" and columns:
                answer = _scale_answer(raw, columns)
                prompt = build_scale_prompt(persona, cat_entry, row_idx)
            elif qtype == "Slider":
                answer = _numeric_answer(raw)
                prompt = build_scale_prompt(persona, cat_entry)
            elif qtype == "MC":
                answer = _mc_answer(raw, cat_entry)
                prompt = build_mc_prompt(persona, cat_entry)
            else:
                continue

            if answer is None:
                continue
            examples.append(_make_example(prompt, answer))

        added = len(examples) - count_before
        print(f"  [{key}] ({csv_col}) → {added:,} examples")

    return examples


# ── Complex experiment handlers ───────────────────────────────────────────────

def build_linda_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """
    Linda (Conjunction Fallacy): QID159 = single condition, QID160 = conjunction.
    Each is a 3-row Matrix. All rows are training targets; rows 1-2 answers are
    injected as prior context for row 3 — matching what participants saw on screen.
    """
    examples: list[dict] = []
    for qid in ("QID159", "QID160"):
        cat_entry = catalog.get(qid)
        if cat_entry is None:
            continue
        rows = cat_entry.get("Rows", [])
        cols = cat_entry.get("csv_columns", [])
        columns = cat_entry.get("Columns", [])

        for row_idx in range(len(rows)):
            col = cols[row_idx] if row_idx < len(cols) else None
            if col is None or col not in df.columns:
                continue
            for pid, persona in pid_to_persona.items():
                if pid not in df.index:
                    continue
                raw = df.at[pid, col]
                answer = _scale_answer(raw, columns)
                if answer is None:
                    continue

                prior_qa: list[tuple[str, str]] = []
                for prev_idx in range(row_idx):
                    prev_col = cols[prev_idx] if prev_idx < len(cols) else None
                    if prev_col is None or prev_col not in df.columns:
                        continue
                    prev_raw = df.at[pid, prev_col]
                    prev_answer_idx = _scale_answer(prev_raw, columns)
                    if prev_answer_idx is not None:
                        prior_qa.append((rows[prev_idx], columns[prev_answer_idx - 1]))

                prompt = build_scale_prompt(
                    persona, cat_entry, row_idx,
                    prior_qa=prior_qa if prior_qa else None,
                )
                examples.append(_make_example(prompt, answer))

    print(f"  [linda] → {len(examples):,} examples")
    return examples


def build_false_consensus_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """
    False consensus: QID287 = own political views (matrix, 10 rows),
    QID290 = public estimate sliders (10 rows, matching the same policies).

    Own-view examples have no prior context (all 10 rows shown simultaneously
    on one Qualtrics page). Each public estimate example includes ALL 10
    own-view answers as prior context — the participant completed the full
    QID287 page before seeing QID290, so every estimate reflects the complete
    set of self-positions.
    """
    examples: list[dict] = []
    own_cat = catalog.get("QID287")
    pub_cat = catalog.get("QID290")
    if own_cat is None or pub_cat is None:
        print("  [false_consensus] QID287/QID290 not found in catalog")
        return examples

    rows = own_cat.get("Rows", [])
    own_cols = own_cat.get("csv_columns", [])
    pub_cols = pub_cat.get("csv_columns", [])

    for pid, persona in pid_to_persona.items():
        if pid not in df.index:
            continue

        # Pass 1 — collect every own-view answer this participant gave on QID287
        own_answers: list[tuple[int, str, int, str]] = []  # (row_idx, row_text, idx, label)
        for row_idx, row_text in enumerate(rows):
            own_col = own_cols[row_idx] if row_idx < len(own_cols) else None
            if own_col is None or own_col not in df.columns:
                continue
            own_raw = df.at[pid, own_col]
            own_idx = _scale_answer(own_raw, POLICY_SCALE)
            if own_idx is not None:
                own_answers.append((row_idx, row_text, own_idx, POLICY_SCALE[own_idx - 1]))

        # Own-view training examples — no prior context (single simultaneous Matrix page)
        for row_idx, row_text, own_idx, _ in own_answers:
            prompt = build_scale_prompt(persona, own_cat, row_idx)
            examples.append(_make_example(prompt, own_idx))

        # Public-estimate training examples — all 10 own-view answers as prior context
        all_own_prior: list[tuple[str, str]] = [
            (f"Do you personally support or oppose: '{row_text}'?", label)
            for _, row_text, _, label in own_answers
        ]

        for row_idx, row_text in enumerate(rows):
            pub_col = pub_cols[row_idx] if row_idx < len(pub_cols) else None
            if pub_col is None or pub_col not in df.columns:
                continue
            pub_raw = df.at[pid, pub_col]
            pub_answer = _numeric_answer(pub_raw)
            if pub_answer is None:
                continue

            pub_entry = {
                "QuestionText": (
                    f"What percentage (0–100) of the public do you think "
                    f"supports: '{row_text}'"
                ),
                "QuestionType": "Slider",
            }
            prompt = build_numeric_prompt(
                persona, pub_entry,
                prior_qa=all_own_prior if all_own_prior else None,
            )
            examples.append(_make_example(prompt, pub_answer))

    print(f"  [false_consensus] → {len(examples):,} examples")
    return examples


def build_risk_benefit_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """
    Risk-Benefit: QID288 = benefit ratings, QID289 = risk ratings.
    Items: bicycles, alcoholic beverages, chemical plants, pesticides.

    Benefit ratings are shown first. Risk rating examples include the
    corresponding benefit rating as prior context (same item, different page).
    """
    examples: list[dict] = []
    benefit_cat = catalog.get("QID288")
    risk_cat = catalog.get("QID289")
    if benefit_cat is None or risk_cat is None:
        print("  [risk_benefit] QID288 or QID289 not found in catalog")
        return examples

    benefit_rows = benefit_cat.get("Rows", [])
    benefit_cols = benefit_cat.get("csv_columns", [])
    benefit_columns = benefit_cat.get("Columns", [])

    risk_rows = risk_cat.get("Rows", [])
    risk_cols = risk_cat.get("csv_columns", [])
    risk_columns = risk_cat.get("Columns", [])

    # Benefit ratings — no prior context (answered first)
    for row_idx, item_label in enumerate(benefit_rows):
        col = benefit_cols[row_idx] if row_idx < len(benefit_cols) else None
        if col is None or col not in df.columns:
            continue
        for pid, persona in pid_to_persona.items():
            if pid not in df.index:
                continue
            raw = df.at[pid, col]
            answer = _scale_answer(raw, benefit_columns)
            if answer is None:
                continue
            prompt = build_scale_prompt(persona, benefit_cat, row_idx)
            examples.append(_make_example(prompt, answer))

    # Risk ratings — include benefit rating for the same item as prior context
    for row_idx, item_label in enumerate(risk_rows):
        risk_col = risk_cols[row_idx] if row_idx < len(risk_cols) else None
        benefit_col = benefit_cols[row_idx] if row_idx < len(benefit_cols) else None
        if risk_col is None or risk_col not in df.columns:
            continue
        for pid, persona in pid_to_persona.items():
            if pid not in df.index:
                continue
            risk_raw = df.at[pid, risk_col]
            risk_answer = _scale_answer(risk_raw, risk_columns)
            if risk_answer is None:
                continue

            prior_qa: list[tuple[str, str]] | None = None
            if benefit_col and benefit_col in df.columns:
                benefit_raw = df.at[pid, benefit_col]
                benefit_idx = _scale_answer(benefit_raw, benefit_columns)
                if benefit_idx is not None:
                    prior_qa = [(
                        f'"{item_label}" — How beneficial is this to society?',
                        benefit_columns[benefit_idx - 1],
                    )]

            prompt = build_scale_prompt(persona, risk_cat, row_idx, prior_qa=prior_qa)
            examples.append(_make_example(prompt, risk_answer))

    print(f"  [risk_benefit] → {len(examples):,} examples")
    return examples


def build_probability_matching_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """
    Probability matching: QID198 (10-card deck) and QID203 (6-roll die).
    Each row includes all prior row answers as context — participants fill
    in predictions sequentially and can see what they've already predicted.
    """
    examples: list[dict] = []
    for qid in ("QID198", "QID203"):
        cat_entry = catalog.get(qid)
        if cat_entry is None:
            continue
        rows = cat_entry.get("Rows", [])
        cols = cat_entry.get("csv_columns", [])
        columns = cat_entry.get("Columns", [])

        for row_idx, row_label in enumerate(rows):
            col = cols[row_idx] if row_idx < len(cols) else None
            if col is None or col not in df.columns:
                continue
            for pid, persona in pid_to_persona.items():
                if pid not in df.index:
                    continue
                raw = df.at[pid, col]
                answer = _scale_answer(raw, columns)
                if answer is None:
                    continue

                # Collect all prior predictions for this participant
                prior_qa: list[tuple[str, str]] = []
                for prev_idx in range(row_idx):
                    prev_col = cols[prev_idx] if prev_idx < len(cols) else None
                    if prev_col is None or prev_col not in df.columns:
                        continue
                    prev_raw = df.at[pid, prev_col]
                    prev_idx_val = _scale_answer(prev_raw, columns)
                    if prev_idx_val is not None:
                        prior_qa.append((
                            rows[prev_idx],
                            columns[prev_idx_val - 1],
                        ))

                prompt = build_scale_prompt(
                    persona, cat_entry, row_idx,
                    prior_qa=prior_qa if prior_qa else None,
                )
                examples.append(_make_example(prompt, answer))

    print(f"  [probability_matching] → {len(examples):,} examples")
    return examples


def build_proportion_dominance_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> list[dict]:
    """
    Proportion dominance (dominator neglect): QID174–176 (fire extinguisher) and
    QID177–179 (seatbelt). Each has different framing of lives saved.
    """
    examples: list[dict] = []
    for qid in ("QID174", "QID175", "QID176", "QID177", "QID178", "QID179"):
        cat_entry = catalog.get(qid)
        if cat_entry is None:
            continue
        cols = cat_entry.get("csv_columns", [])
        col = cols[0] if cols else None
        if col is None or col not in df.columns:
            continue
        for pid, persona in pid_to_persona.items():
            if pid not in df.index:
                continue
            raw = df.at[pid, col]
            answer = _mc_answer(raw, cat_entry)
            if answer is None:
                continue
            prompt = build_mc_prompt(persona, cat_entry)
            examples.append(_make_example(prompt, answer))

    print(f"  [dominator_neglect] → {len(examples):,} examples")
    return examples


# ── Main builder ──────────────────────────────────────────────────────────────

def build_all_examples(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
    max_examples: int | None,
    val_fraction: float,
    seed: int,
) -> tuple[list[dict], list[dict]]:
    print("  Building simple condition→column examples...")
    all_ex = build_simple_examples(catalog, df, pid_to_persona)
    print("  Building linda examples...")
    all_ex += build_linda_examples(catalog, df, pid_to_persona)
    print("  Building false_consensus examples...")
    all_ex += build_false_consensus_examples(catalog, df, pid_to_persona)
    print("  Building risk_benefit examples...")
    all_ex += build_risk_benefit_examples(catalog, df, pid_to_persona)
    print("  Building probability_matching examples...")
    all_ex += build_probability_matching_examples(catalog, df, pid_to_persona)
    print("  Building dominator_neglect examples...")
    all_ex += build_proportion_dominance_examples(catalog, df, pid_to_persona)

    rng = random.Random(seed)
    rng.shuffle(all_ex)
    if max_examples is not None:
        all_ex = all_ex[:max_examples]

    split = int(len(all_ex) * (1 - val_fraction))
    return all_ex[:split], all_ex[split:]


# ── Preview printer ───────────────────────────────────────────────────────────

def print_preview(
    catalog: dict[str, dict],
    df: pd.DataFrame,
    pid_to_persona: dict,
) -> None:
    print("\n" + "=" * 70)
    print("  PERSONA MAPPING (first 5)")
    print("=" * 70)
    pids = list(pid_to_persona.keys())
    for pid in pids[:5]:
        print(f"  pid={pid:>4}  →  {pid_to_persona[pid].name}")
    print(f"  ...  (cycles every {len(DEFAULT_PERSONAS)} participants)")

    print("\n" + "=" * 70)
    print("  QID COLUMN MAP  (experiment condition → wave4 CSV column)")
    print("=" * 70)
    for key, col in sorted(CONDITION_TO_COLUMN.items()):
        present = "✓" if col in df.columns else "✗ MISSING"
        print(f"  {key:<40} {col:<20} {present}")

    # Show 4 sample training records covering different response types
    print("\n" + "=" * 70)
    print("  SAMPLE TRAINING RECORDS")
    print("=" * 70)

    demo_cases = [
        ("linda::conjunction",          "QID160_3",  "scale"),
        ("framing::gain",               "QID157",    "mc"),
        ("anchoring_redwood::low_anchor","QID168_TEXT","numeric"),
        ("sunk_cost::paid",             "QID182_TEXT","numeric"),
    ]

    pid = pids[0]
    persona = pid_to_persona[pid]

    for key, csv_col, _ in demo_cases:
        if csv_col not in df.columns:
            continue
        if pid not in df.index:
            continue
        base_qid = csv_col.split("_")[0]
        cat_entry = catalog.get(base_qid)
        if cat_entry is None:
            continue
        raw = df.at[pid, csv_col]
        if pd.isna(raw) or str(raw).strip() in ("", "nan"):
            continue

        qtype = cat_entry.get("QuestionType", "")
        columns = cat_entry.get("Columns", [])
        row_idx = None
        if "_" in csv_col and csv_col.split("_")[-1].isdigit():
            row_idx = int(csv_col.split("_")[-1]) - 1

        if csv_col.endswith("_TEXT") or qtype == "TE":
            answer = _numeric_answer(raw)
            prompt = build_numeric_prompt(persona, cat_entry)
        elif qtype == "Matrix" and columns:
            answer = _scale_answer(raw, columns)
            prompt = build_scale_prompt(persona, cat_entry, row_idx)
        elif qtype == "MC":
            answer = _mc_answer(raw, cat_entry)
            prompt = build_mc_prompt(persona, cat_entry)
        else:
            continue

        if answer is None:
            continue

        print(f"\n{'─'*70}")
        print(f"  {key}  |  pid={pid} → {persona.name}  |  raw={raw!r}")
        print(f"{'─'*70}")
        print("\n[USER / PROMPT]")
        print(prompt)
        print("[ASSISTANT / RESPONSE]")
        print(json.dumps({"answer": answer}))

    print(f"\n{'─'*70}")
    print("\nIf this looks correct, run without --preview to generate the full dataset.\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true",
                        help="Print mapping + sample records, exit without saving")
    parser.add_argument("--max-per-persona", type=int, default=2,
                        help="Max Twin-2K participants mapped to each AI persona (default: 2)")
    parser.add_argument("--max-examples", type=int, default=None)
    parser.add_argument("--val-fraction", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()

    print("Loading question catalog...")
    catalog = load_question_catalog()
    print(f"  {len(catalog)} entries")

    print("Loading wave4 response labels...")
    df = load_response_labels()
    print(f"  {len(df)} participants × {len(df.columns)} columns")

    pids = load_pids_sorted(df)
    pid_to_persona = build_pid_to_persona(pids, max_per_persona=args.max_per_persona)
    n_used = len(pid_to_persona)
    print(f"  {n_used} participants used ({args.max_per_persona}×{len(DEFAULT_PERSONAS)} personas)")

    if args.preview:
        print_preview(catalog, df, pid_to_persona)
        return

    print("\nBuilding training examples...")
    train, val = build_all_examples(
        catalog, df, pid_to_persona,
        max_examples=args.max_examples,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )
    print(f"\nTotal: train={len(train):,}, val={len(val):,}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, split in [("train", train), ("val", val)]:
        path = out / f"{name}.jsonl"
        with open(path, "w") as f:
            for ex in split:
                f.write(json.dumps(ex) + "\n")
        print(f"Saved {len(split):,} examples → {path}")

    print("\nNext step: python 2_train.py")


if __name__ == "__main__":
    main()
