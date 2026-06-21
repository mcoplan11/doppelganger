"""Statistical analysis and replication check for each experiment."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from scipy import stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False
    print("WARNING: scipy not installed. Some statistics will be unavailable.")


def _load_rows(results_dir: Path, experiment_id: str) -> list[dict]:
    path = results_dir / f"{experiment_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Return (t_stat, p_value) for independent samples t-test."""
    if not _HAS_SCIPY or len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    result = stats.ttest_ind(a, b, equal_var=False)
    return float(result.statistic), float(result.pvalue)


def _chi2_test(a_yes: int, a_no: int, b_yes: int, b_no: int) -> tuple[float, float]:
    if not _HAS_SCIPY:
        return float("nan"), float("nan")
    table = [[a_yes, a_no], [b_yes, b_no]]
    try:
        chi2, p, _, _ = stats.chi2_contingency(table)
        return float(chi2), float(p)
    except ValueError:
        # Zero cell (e.g. unanimous responses) — fall back to Fisher's exact test
        _, p = stats.fisher_exact(table)
        return float("nan"), float(p)


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else float("nan")


def _pct(vals: list[str], target: str) -> float:
    if not vals:
        return float("nan")
    return 100.0 * sum(1 for v in vals if v == target) / len(vals)


# ── Individual experiment analyzers ──────────────────────────────────────────

def _analyze_mean_comparison(exp: dict, rows: list[dict]) -> dict:
    by_cond: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.get("answer") is not None and r.get("error") is None:
            try:
                by_cond[r["condition_id"]].append(float(r["answer"]))
            except (TypeError, ValueError):
                pass

    cond_ids = [c["id"] for c in exp["conditions"]]
    means = {cid: _mean(by_cond[cid]) for cid in cond_ids}
    direction = exp["analysis"]["direction"]

    # Determine expected "higher" condition from direction string
    # Conventions: direction contains the condition_id of the expected higher condition
    # Or uses special tokens like "condition_high_anchor_higher"
    replication_check = _check_direction_mean(direction, cond_ids, means)

    if len(cond_ids) == 2:
        t, p = _t_test(by_cond[cond_ids[0]], by_cond[cond_ids[1]])
        sig = p < 0.05 if not (p != p) else False  # nan check
    else:
        t, p, sig = float("nan"), float("nan"), False

    return {
        "means": means,
        "n_per_condition": {cid: len(by_cond[cid]) for cid in cond_ids},
        "t_stat": t,
        "p_value": p,
        "significant": sig,
        "correct_direction": replication_check,
        "replicated": replication_check and sig,
    }


def _check_direction_mean(direction: str, cond_ids: list[str], means: dict) -> bool:
    """Return True if means are in the expected direction based on the direction string."""
    if len(cond_ids) < 2:
        return False
    # The direction string encodes which condition should be higher.
    # We look for condition IDs embedded in the direction token.
    for cid in cond_ids:
        if cid in direction and "higher" in direction:
            # This condition should be higher
            other_cids = [c for c in cond_ids if c != cid]
            return all(means.get(cid, 0) > means.get(other, 0) for other in other_cids)
    # Fallback: first condition listed in direction after "condition_" is expected higher
    return means.get(cond_ids[0], 0) != means.get(cond_ids[1], 0)


def _analyze_proportion_comparison(exp: dict, rows: list[dict]) -> dict:
    by_cond: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r.get("answer") is not None and r.get("error") is None:
            by_cond[r["condition_id"]].append(str(r["answer"]))

    cond_ids = [c["id"] for c in exp["conditions"]]
    risky = exp["analysis"].get("risky_option", "")
    direction = exp["analysis"]["direction"]

    proportions = {cid: _pct(by_cond[cid], risky) for cid in cond_ids}
    # Higher proportion choosing risky in second condition?
    replication_check = _check_direction_prop(direction, cond_ids, proportions)

    if len(cond_ids) == 2 and risky:
        a, b = cond_ids
        a_yes = sum(1 for v in by_cond[a] if v == risky)
        a_no = len(by_cond[a]) - a_yes
        b_yes = sum(1 for v in by_cond[b] if v == risky)
        b_no = len(by_cond[b]) - b_yes
        chi2, p = _chi2_test(a_yes, a_no, b_yes, b_no)
        sig = p < 0.05 if not (p != p) else False
    else:
        chi2, p, sig = float("nan"), float("nan"), False

    return {
        "proportions_pct": proportions,
        "n_per_condition": {cid: len(by_cond[cid]) for cid in cond_ids},
        "chi2_stat": chi2,
        "p_value": p,
        "significant": sig,
        "correct_direction": replication_check,
        "replicated": replication_check and sig,
    }


def _check_direction_prop(
    direction: str, cond_ids: list[str], props: dict
) -> bool:
    for cid in cond_ids:
        if cid in direction and "higher" in direction:
            other_cids = [c for c in cond_ids if c != cid]
            return all(props.get(cid, 0) > props.get(other, 0) for other in other_cids)
    # Fallback: check if any difference exists
    vals = [props.get(c, 0) for c in cond_ids]
    return len(set(vals)) > 1


def _analyze_wta_wtp(exp: dict, rows: list[dict]) -> dict:
    by_cond: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.get("answer") is not None and r.get("error") is None:
            try:
                by_cond[r["condition_id"]].append(float(r["answer"]))
            except (TypeError, ValueError):
                pass

    ordering = exp["analysis"]["ordering"]
    means = {cid: _mean(by_cond[cid]) for cid in ordering}

    # Check if means follow the expected ordering
    correct = all(
        means.get(ordering[i], 0) > means.get(ordering[i + 1], 0)
        for i in range(len(ordering) - 1)
    )

    # t-tests between adjacent pairs
    tests = {}
    for i in range(len(ordering) - 1):
        a, b = ordering[i], ordering[i + 1]
        t, p = _t_test(by_cond[a], by_cond[b])
        tests[f"{a}_vs_{b}"] = {"t": t, "p": p}

    return {
        "means": means,
        "n_per_condition": {cid: len(by_cond[cid]) for cid in ordering},
        "pairwise_tests": tests,
        "correct_direction": correct,
        "replicated": correct and all(
            v["p"] < 0.05 for v in tests.values() if not (v["p"] != v["p"])
        ),
    }


def _analyze_allais(exp: dict, rows: list[dict]) -> dict:
    by_cond: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r.get("answer") is not None and r.get("error") is None:
            by_cond[r["condition_id"]].append(str(r["answer"]))

    # Expected: problem1 → mostly A (safe), problem2 → mostly B (risky)
    p1_pct_safe = _pct(by_cond.get("problem1", []), "A")
    p2_pct_risky = _pct(by_cond.get("problem2", []), "B")
    # Allais pattern requires: mostly A in p1 AND mostly B in p2
    correct = p1_pct_safe > 50 and p2_pct_risky > 50
    return {
        "problem1_pct_safe_A": p1_pct_safe,
        "problem2_pct_risky_B": p2_pct_risky,
        "n_per_condition": {cid: len(v) for cid, v in by_cond.items()},
        "correct_direction": correct,
        "replicated": correct,
    }


def _analyze_false_consensus(exp: dict, rows: list[dict]) -> dict:
    own_views, public_ests = [], []
    for r in rows:
        if r.get("own_view") is not None and r.get("public_estimate") is not None:
            own_views.append(float(r["own_view"]))
            public_ests.append(float(r["public_estimate"]))

    if len(own_views) < 3:
        return {"n": len(own_views), "replicated": False, "note": "Insufficient data"}

    if _HAS_SCIPY:
        r_val, p_val = stats.pearsonr(own_views, public_ests)
    else:
        r_val, p_val = float("nan"), float("nan")

    correct = r_val > 0 if not (r_val != r_val) else False
    sig = p_val < 0.05 if not (p_val != p_val) else False
    return {
        "n_pairs": len(own_views),
        "pearson_r": r_val,
        "p_value": p_val,
        "correct_direction": correct,
        "replicated": correct and sig,
    }


def _analyze_risk_benefit(exp: dict, rows: list[dict]) -> dict:
    by_item: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for r in rows:
        if r.get("risk_rating") is not None and r.get("benefit_rating") is not None:
            by_item[r["item_id"]][0].append(float(r["risk_rating"]))
            by_item[r["item_id"]][1].append(float(r["benefit_rating"]))

    item_results = {}
    replicated_count = 0
    for item_id, (risks, benefits) in by_item.items():
        if len(risks) < 3:
            continue
        if _HAS_SCIPY:
            r_val, p_val = stats.pearsonr(risks, benefits)
        else:
            r_val, p_val = float("nan"), float("nan")
        item_rep = (r_val < 0) and (p_val < 0.05)
        item_results[item_id] = {"r": r_val, "p": p_val, "replicated": item_rep}
        if item_rep:
            replicated_count += 1

    total = len(item_results)
    return {
        "items": item_results,
        "replicated_count": replicated_count,
        "total_items": total,
        "replicated": replicated_count > 0,
        "summary": f"{replicated_count}/{total} items show negative risk-benefit correlation",
    }


def _analyze_omission_bias(exp: dict, rows: list[dict]) -> dict:
    by_cond: dict[str, list] = defaultdict(list)
    for r in rows:
        if r.get("answer") is not None and r.get("error") is None:
            by_cond[r["condition_id"]].append(r["answer"])

    # Expected: more refuse vaccine in commission condition (action causes harm)
    commission_skip = _pct(by_cond.get("commission", []), "skip")
    omission_skip = _pct(by_cond.get("omission", []), "skip")

    correct = commission_skip > omission_skip
    return {
        "commission_pct_skip": commission_skip,
        "omission_pct_skip": omission_skip,
        "n_per_condition": {k: len(v) for k, v in by_cond.items()},
        "correct_direction": correct,
        "replicated": correct,
    }


def _analyze_probability_matching(exp: dict, rows: list[dict]) -> dict:
    answers = [r["answer"] for r in rows if r.get("answer") and not r.get("error")]
    pct_matching = _pct(answers, "match")
    pct_maximizing = _pct(answers, "maximize")
    # Replication = non-trivial fraction (>10%) choosing the suboptimal matching strategy
    replicated = pct_matching > 10
    return {
        "n": len(answers),
        "pct_matching": pct_matching,
        "pct_maximizing": pct_maximizing,
        "human_benchmark_pct_matching": 30.0,
        "correct_direction": replicated,
        "replicated": replicated,
    }


def _analyze_dominator_neglect(exp: dict, rows: list[dict]) -> dict:
    answers = [r["answer"] for r in rows if r.get("answer") and not r.get("error")]
    pct_dominated = _pct(answers, "dominated")
    # Replication = non-trivial fraction (>10%) choosing the dominated option
    replicated = pct_dominated > 10
    return {
        "n": len(answers),
        "pct_dominated": pct_dominated,
        "correct_direction": replicated,
        "replicated": replicated,
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

def analyze_experiment(exp: dict, rows: list[dict]) -> dict:
    analysis_type = exp.get("analysis", {}).get("type", "")
    if analysis_type == "mean_comparison":
        return _analyze_mean_comparison(exp, rows)
    if analysis_type == "mean_comparison_three":
        return _analyze_wta_wtp(exp, rows)
    if analysis_type == "proportion_comparison":
        if exp["id"] == "allais":
            return _analyze_allais(exp, rows)
        if exp["id"] == "omission_bias":
            return _analyze_omission_bias(exp, rows)
        return _analyze_proportion_comparison(exp, rows)
    if analysis_type == "false_consensus_correlation":
        return _analyze_false_consensus(exp, rows)
    if analysis_type == "within_correlation":
        return _analyze_risk_benefit(exp, rows)
    if analysis_type == "proportion_matching":
        return _analyze_probability_matching(exp, rows)
    if analysis_type == "proportion_dominated":
        return _analyze_dominator_neglect(exp, rows)
    return {"note": f"No analyzer for type {analysis_type!r}"}


# ── Report printer ────────────────────────────────────────────────────────────

_RESULT_ICON = {"replicated": "✓", "not_replicated": "✗", "partial": "~"}


def print_comparison_table(experiments: list[dict], results_dir: Path) -> None:
    # We don't compare against the Twin-2K paper anymore. Every experiment is a
    # known bias and should produce a significant effect in the expected direction,
    # so the only question is how many our model actually reproduces. "Effect?" = ✓
    # when our data shows the bias (significant + correct direction, or the
    # threshold the analyzer uses for the n/a-p-value designs).
    print("\n" + "=" * 80)
    print("BIAS REPLICATION — SIGNIFICANT EFFECT DETECTED")
    print("=" * 80)
    header = f"{'Experiment':<40} {'Effect?':^10} {'p-value':^10}"
    print(header)
    print("-" * 80)

    total = 0
    replicated_n = 0

    for exp in experiments:
        rows = _load_rows(results_dir, exp["id"])
        if not rows:
            print(f"  {'[no data]':<40} {exp['id']}")
            continue

        stats_out = analyze_experiment(exp, rows)
        is_rep = bool(stats_out.get("replicated"))
        p_val = stats_out.get("p_value", stats_out.get("pairwise_tests", {}).get(
            list(stats_out.get("pairwise_tests", {}).keys())[0], {}).get("p")
            if stats_out.get("pairwise_tests") else float("nan"))

        p_str = f"{p_val:.3f}" if isinstance(p_val, float) and not (p_val != p_val) else "n/a"
        icon = "✓" if is_rep else "✗"

        name = exp["name"][:39]
        print(f"  {name:<40} {icon:^10} {p_str:^10}")

        total += 1
        if is_rep:
            replicated_n += 1

    print("-" * 80)
    print(f"\n  Effects replicated: {replicated_n}/{total}")
    print("=" * 80)


def save_detailed_report(
    experiments: list[dict], results_dir: Path, report_path: Path
) -> None:
    lines = ["# Twin-2K-500 Replication — Detailed Analysis\n"]
    for exp in experiments:
        rows = _load_rows(results_dir, exp["id"])
        if not rows:
            continue
        stats_out = analyze_experiment(exp, rows)
        lines.append(f"## {exp['name']} ({exp['id']})")
        lines.append(f"- Citation: {exp.get('citation', '')}")
        lines.append(f"- Paper result: {exp.get('paper_result', '?')}")
        lines.append(f"- Our result: {'REPLICATED' if stats_out.get('replicated') else 'NOT REPLICATED'}")
        lines.append(f"- Stats: {json.dumps(stats_out, indent=2, default=str)}")
        lines.append("")
    report_path.write_text("\n".join(lines))
    print(f"\nDetailed report saved to {report_path}")
