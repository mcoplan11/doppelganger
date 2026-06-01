"""Compare AI-respondent results against Annabelle's real-world numbers.

Usage:
    python analyze.py
"""
from __future__ import annotations

import glob
import json
import math
import re
import statistics
from pathlib import Path

# QID layout discovered by inspecting branch responses:
# Ed: each randomizer arm uses a different DV QID
ED_DV_QID = {
    "Condition=other": "QID180",
    "Condition=self": "QID177",
    "Condition=self intervention": "QID177",
}
# Value mapping: "1" = productive task, "2" = enjoyable (puppy) task
ED_PRODUCTIVE_VALUE = "1"

# Selin: % likelihood that the application was accepted
SELIN_DV_QID = "QID38"

# Real-world numbers Annabelle reported (2026-05-20)
REAL_ED = {
    "Condition=other": {"n": 100, "productive_pct": 0.58},
    "Condition=self": {"n": 100, "productive_pct": 0.61},
    "Condition=self intervention": {"n": 100, "productive_pct": 0.63},
}
# p = .756 → null
REAL_SELIN = {
    "fast": {"mean": 49.94, "sd": 21.40, "n": 200},
    "slow": {"mean": 39.01, "sd": 21.05, "n": 200},
}
# p < .001 → strong effect


def load_dir(d: Path) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(d / "*.json"))):
        try:
            out.append(json.load(open(f)))
        except Exception:
            pass
    return out


def extract_number(value) -> float | None:
    if value is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None


def classify_selin_branch(bd: str) -> str | None:
    """'Wait=short, ...' → 'fast'; 'Wait=long, ...' → 'slow'."""
    if not bd:
        return None
    if "short" in bd.lower():
        return "fast"
    if "long" in bd.lower():
        return "slow"
    return None


def analyze_ed(dir_path: Path) -> dict:
    runs = [r for r in load_dir(dir_path) if r.get("completed")]
    by_branch: dict[str, list[bool]] = {}
    for r in runs:
        bd = r.get("branch_description")
        qid = ED_DV_QID.get(bd)
        if not qid:
            continue
        val = r.get("answers", {}).get(qid)
        if val is None:
            continue
        by_branch.setdefault(bd, []).append(str(val) == ED_PRODUCTIVE_VALUE)
    summary = {}
    for bd, vals in by_branch.items():
        n = len(vals)
        prod = sum(vals)
        summary[bd] = {
            "n": n,
            "productive": prod,
            "productive_pct": prod / n if n else None,
        }
    return summary


def analyze_selin(dir_path: Path) -> dict:
    runs = [r for r in load_dir(dir_path) if r.get("completed")]
    by_arm: dict[str, list[float]] = {}
    for r in runs:
        arm = classify_selin_branch(r.get("branch_description", ""))
        if arm is None:
            continue
        num = extract_number(r.get("answers", {}).get(SELIN_DV_QID))
        if num is None:
            continue
        by_arm.setdefault(arm, []).append(num)
    summary = {}
    for arm, vals in by_arm.items():
        n = len(vals)
        m = statistics.mean(vals) if n else None
        sd = statistics.stdev(vals) if n > 1 else None
        summary[arm] = {"n": n, "mean": m, "sd": sd}
    return summary


def welch_t(m1, sd1, n1, m2, sd2, n2):
    if None in (m1, sd1, m2, sd2) or n1 < 2 or n2 < 2:
        return None
    se = math.sqrt(sd1 ** 2 / n1 + sd2 ** 2 / n2)
    if se == 0:
        return None
    return (m1 - m2) / se


def cohens_d(m1, sd1, n1, m2, sd2, n2):
    if None in (m1, sd1, m2, sd2):
        return None
    s_pooled = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
    if s_pooled == 0:
        return None
    return (m1 - m2) / s_pooled


def print_ed_comparison(label: str, ai: dict):
    print(f"\n--- Ed: {label} ---")
    print(f"{'Branch':30s} {'AI n':>5s} {'AI %prod':>10s}   {'Real %prod':>12s}   {'Δ vs real':>11s}")
    for bd, real in REAL_ED.items():
        ai_cell = ai.get(bd, {"n": 0, "productive_pct": None})
        ai_pct = ai_cell["productive_pct"]
        delta = (ai_pct - real["productive_pct"]) if ai_pct is not None else None
        ai_str = f"{ai_pct*100:.0f}%" if ai_pct is not None else "n/a"
        delta_str = f"{delta*100:+.0f}pp" if delta is not None else "n/a"
        print(f"{bd:30s} {ai_cell['n']:>5d} {ai_str:>10s}   {real['productive_pct']*100:>11.0f}%   {delta_str:>11s}")
    branches_with_data = [b for b in REAL_ED if ai.get(b, {}).get("productive_pct") is not None]
    if len(branches_with_data) >= 2:
        pcts = [ai[b]["productive_pct"] for b in branches_with_data]
        spread = (max(pcts) - min(pcts)) * 100
        print(f"  → AI spread across conditions: {spread:.0f}pp   (Real spread: 5pp, p=.756 null)")


def print_selin_comparison(label: str, ai: dict):
    print(f"\n--- Selin: {label} ---")
    fast = ai.get("fast", {})
    slow = ai.get("slow", {})
    print(f"{'Arm':10s} {'AI n':>5s} {'AI mean':>10s} {'AI sd':>8s}   {'Real mean':>11s} {'Real sd':>8s}")
    print(f"{'fast':10s} {fast.get('n',0):>5d} {fmt(fast.get('mean')):>10s} {fmt(fast.get('sd')):>8s}   "
          f"{REAL_SELIN['fast']['mean']:>11.2f} {REAL_SELIN['fast']['sd']:>8.2f}")
    print(f"{'slow':10s} {slow.get('n',0):>5d} {fmt(slow.get('mean')):>10s} {fmt(slow.get('sd')):>8s}   "
          f"{REAL_SELIN['slow']['mean']:>11.2f} {REAL_SELIN['slow']['sd']:>8.2f}")

    if fast.get("mean") is not None and slow.get("mean") is not None:
        ai_diff = fast["mean"] - slow["mean"]
        real_diff = REAL_SELIN["fast"]["mean"] - REAL_SELIN["slow"]["mean"]
        d = cohens_d(fast["mean"], fast.get("sd") or 0, fast["n"],
                     slow["mean"], slow.get("sd") or 0, slow["n"])
        real_d = cohens_d(REAL_SELIN["fast"]["mean"], REAL_SELIN["fast"]["sd"], REAL_SELIN["fast"]["n"],
                          REAL_SELIN["slow"]["mean"], REAL_SELIN["slow"]["sd"], REAL_SELIN["slow"]["n"])
        print(f"  → AI fast−slow diff: {ai_diff:+.2f} (d≈{d:.2f})   Real fast−slow: {real_diff:+.2f} (d≈{real_d:.2f}, p<.001)")


def fmt(x):
    return f"{x:.2f}" if x is not None else "n/a"


def main():
    root = Path("responses")
    print("=" * 72)
    print("ED — work-vs-leisure choice (real: 58/61/63%, p=.756 null)")
    print("=" * 72)
    if (root / "ed_t05").exists():
        print_ed_comparison("T = 0.5", analyze_ed(root / "ed_t05"))
    if (root / "ed_t09").exists():
        print_ed_comparison("T = 0.9", analyze_ed(root / "ed_t09"))

    print()
    print("=" * 72)
    print("SELIN — fast vs slow wait (real: fast 49.94 / slow 39.01, p<.001 strong effect)")
    print("=" * 72)
    if (root / "selin_t05").exists():
        print_selin_comparison("T = 0.5", analyze_selin(root / "selin_t05"))
    if (root / "selin_t09").exists():
        print_selin_comparison("T = 0.9", analyze_selin(root / "selin_t09"))


if __name__ == "__main__":
    main()
