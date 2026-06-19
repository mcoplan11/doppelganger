#!/usr/bin/env python3
"""
persona_signal_check.py — does persona grounding actually carry signal?

A GPU-free pre-flight check for the §3.1 caveat in GROUNDED_PERSONAS_PLAN.md:

    "within-subjects power is only real if personas carry *stable individual
     differences* (positive within-persona covariance across conditions). That
     is exactly what persona grounding buys — without it, the pairing is empty."

We can test the prerequisite directly on the *human* data, before spending a
single GPU-hour: do participants assigned to the SAME grounded persona answer
more alike than participants in DIFFERENT personas — after removing each
condition's main effect (so we measure stable individual differences, not the
bias manipulation itself)?

The statistic is a one-way intraclass correlation (ICC(1)) of the
condition-residualised answers, grouped by persona, computed per study:

    residual          = answer − mean(answer | study, condition)
    ICC(1)            = (MSB − MSW) / (MSB + (k0−1)·MSW)

where MSB / MSW are the between-/within-persona mean squares of the residuals
and k0 is the ANOVA mean group size. Interpretation:

    ICC ≈ 0      personas do NOT separate behaviour on this study — grounding
                 adds nothing over the global marginal here, and the
                 within-subjects pairing buys no power. (An important *finding*,
                 per the plan, not a bug.)
    ICC ≳ 0.05   personas carry usable stable individual differences.

This reuses 1_prepare_data.py's builders so the answers/encodings are identical
to what training sees. Run AFTER `python 1_prepare_data.py` has produced the
grounded examples.

Usage:
    python persona_signal_check.py
    python persona_signal_check.py --min-members 3 --flag-below 0.05
"""
from __future__ import annotations

import argparse
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_PERSONA_RE = re.compile(r"^PERSONA:\s*(.+)$", re.MULTILINE)


def _load_prep_module():
    """Import 1_prepare_data.py despite its leading-digit (non-identifier) name."""
    spec = importlib.util.spec_from_file_location("prep", HERE / "1_prepare_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _persona_of(example: dict) -> str | None:
    m = _PERSONA_RE.search(example["messages"][0]["content"])
    return m.group(1).strip() if m else None


def _icc_one_way(groups: list[list[float]]) -> tuple[float, int, int]:
    """ICC(1) from a one-way random-effects ANOVA. Returns (icc, n_groups, n_obs)."""
    groups = [g for g in groups if len(g) >= 1]
    G = len(groups)
    n_total = sum(len(g) for g in groups)
    if G < 2 or n_total <= G:  # need ≥2 groups and within-group residual df
        return float("nan"), G, n_total

    grand = sum(v for g in groups for v in g) / n_total
    ss_between = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups)
    ss_within = sum((v - sum(g) / len(g)) ** 2 for g in groups for v in g)

    df_between = G - 1
    df_within = n_total - G
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within if df_within else 0.0

    # ANOVA mean group size (corrects for unequal group sizes)
    k0 = (n_total - sum(len(g) ** 2 for g in groups) / n_total) / df_between
    denom = ms_between + (k0 - 1) * ms_within
    if denom <= 0:
        return 0.0, G, n_total
    icc = (ms_between - ms_within) / denom
    return max(0.0, icc), G, n_total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-members", type=int, default=2,
                    help="Minimum participants per persona to include in a study's ICC")
    ap.add_argument("--flag-below", type=float, default=0.05,
                    help="Flag studies whose ICC falls below this (weak persona signal)")
    args = ap.parse_args()

    prep = _load_prep_module()

    print("Loading catalog + responses + grounded persona map...")
    catalog = prep.load_question_catalog()
    df = prep.load_response_labels()
    out = HERE / "data"
    if not (out / "pid_to_persona.json").exists():
        raise SystemExit("data/pid_to_persona.json not found — run personas_from_twin2k.py first.")
    pid_to_persona = prep.load_grounded_pid_to_persona(out)

    print("Rebuilding tagged examples in-memory (reusing training builders)...")
    examples, _ = prep.build_all_examples(
        catalog, df, pid_to_persona,
        max_examples=None, val_fraction=0.0, seed=42,
    )

    # Gather (persona, study, condition, numeric_answer) for numeric-codeable answers.
    # study → condition → answers, and study → persona → residualised answers.
    by_study_cond: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    rows: list[tuple[str, str, str, float]] = []  # (study, condition, persona, value)
    for ex in examples:
        meta = ex.get("_meta") or {}
        study, cond, ans = meta.get("study"), meta.get("condition"), meta.get("answer")
        persona = _persona_of(ex)
        if study is None or persona is None:
            continue
        val = prep._coerce_numeric(ans)
        if val is None and isinstance(ans, str) and len(ans) == 1 and ans.isalpha():
            val = float(ord(ans.upper()) - 64)  # A→1, B→2, … for MC studies
        if val is None:
            continue
        by_study_cond[study][cond].append(val)
        rows.append((study, cond, persona, val))

    # Condition means for residualisation.
    cond_mean = {
        (study, cond): (sum(vals) / len(vals) if vals else 0.0)
        for study, conds in by_study_cond.items()
        for cond, vals in conds.items()
    }

    # study → persona → residuals
    resid: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for study, cond, persona, val in rows:
        resid[study][persona].append(val - cond_mean[(study, cond)])

    print("\n" + "=" * 78)
    print("  PERSONA-SIGNAL CHECK — ICC(1) of condition-residualised human answers")
    print("  (variance in answers explained by persona membership)")
    print("=" * 78)
    print(f"  {'study':<22}{'ICC':>8}{'btwn_sd':>12}{'personas':>10}{'n_obs':>8}   signal")
    print("  " + "-" * 76)

    def _between_persona_sd(groups: list[list[float]]) -> float:
        """SD of per-persona residual means, in raw answer units.

        Complements ICC: ICC is downward-biased and has a low ceiling for the
        single dichotomous/few-category items most of these studies use, so a
        near-zero ICC can understate a real demographic shift. btwn_sd is the
        spread of persona means in the answer's own units — interpretable as
        "how far apart do personas sit after removing the manipulation."
        """
        means = [sum(g) / len(g) for g in groups if g]
        if len(means) < 2:
            return float("nan")
        mu = sum(means) / len(means)
        return (sum((m - mu) ** 2 for m in means) / (len(means) - 1)) ** 0.5

    iccs: dict[str, float] = {}
    flags: list[str] = []
    for study in sorted(resid):
        groups = [g for g in resid[study].values() if len(g) >= args.min_members]
        icc, G, n = _icc_one_way(groups)
        bsd = _between_persona_sd(groups)
        iccs[study] = icc
        if icc != icc:  # nan
            label = "n/a (too few groups)"
        elif icc < args.flag_below:
            label = "⚠ WEAK — persona adds ~nothing here"
            flags.append(f"{study}: ICC={icc:.3f}")
        else:
            label = "ok"
        icc_str = "  nan" if icc != icc else f"{icc:.3f}"
        bsd_str = "  nan" if bsd != bsd else (f"{bsd:.3f}" if bsd < 1e4 else f"{bsd:.3e}")
        print(f"  {study:<22}{icc_str:>8}{bsd_str:>12}{G:>10}{n:>8}   {label}")

    valid = [v for v in iccs.values() if v == v]
    print("  " + "-" * 76)
    if valid:
        print(f"  mean ICC across studies: {sum(valid) / len(valid):.3f}")

    # Gate-study callout (§8): dominator_neglect is the one trainable, signal-
    # bearing target. Surface its numbers explicitly so the gate is judged on a
    # concrete prior, not the pooled mean.
    gate = "dominator_neglect"
    if gate in iccs:
        gi = iccs[gate]
        gi_str = "nan" if gi != gi else f"{gi:.3f}"
        print(f"  gate study `{gate}`: ICC={gi_str} "
              f"({'has' if (gi == gi and gi >= args.flag_below) else 'lacks'} "
              f"trainable persona signal)")

    print("\n" + "-" * 78)
    print("  NOTE: ICC(1) on single dichotomous/few-category items is downward-")
    print("  biased and ceilings low — read a ~0.02 ICC as 'little MEASURABLE")
    print("  per-item signal', NOT 'demographics are irrelevant'. The product")
    print("  goal is aggregate effect replication, not per-respondent prediction;")
    print("  btwn_sd shows whether persona means separate at all in answer units.")
    print("-" * 78)
    if flags:
        print("  ⚠ Studies where grounded personas carry little stable signal:")
        for fl in flags:
            print(f"      • {fl}")
        print("\n  On these, a grounded fine-tune cannot beat the global marginal and the")
        print("  within-subjects pairing buys no extra power — expect grounding NOT to")
        print("  move them, regardless of model size. (This is a finding, per §3.1, not")
        print("  a bug: these demographics don't predict these biases.)")
    else:
        print("  ✓ Personas carry stable signal on every study (ICC ≥ flag threshold).")
    print("=" * 78)


if __name__ == "__main__":
    main()
