#!/usr/bin/env python3
"""Compare qwen (or any model) effect sizes vs Mega-Study human effect sizes.

For each authored Mega-Study experiment, computes a standardized model effect
size from a results directory and pairs it with the study's `human_effect_size`
(pulled from the Mega-Study meta-analysis and stored in the experiments JSON).

Outputs: a per-outcome table, Pearson r(human, model), sign-agreement on
non-trivial human effects, and a scatter PNG (synthetic d vs human d).

Usage:
    python calibration_megastudy.py --results results/DIR1 results/DIR2 \
        --experiments experiments_megastudy.json experiments_hiring.json \
        --out results/megastudy_calibration
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from collections import defaultdict


def load_rows(results_dir: Path, exp_id: str) -> list[dict]:
    f = results_dir / f"{exp_id}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())


def cohens_d(a: list[float], b: list[float]) -> float:
    """Standardized mean difference (a - b), pooled SD."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    sp = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return (ma - mb) / sp if sp else float("nan")


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for two proportions (p1 - p2), arcsine-transformed."""
    phi = lambda p: 2 * math.asin(math.sqrt(min(max(p, 0), 1)))
    return phi(p1) - phi(p2)


def model_effect(exp: dict, rows: list[dict]) -> float | None:
    """Signed model effect, oriented so the expected-'higher' condition is positive."""
    by = defaultdict(list)
    for r in rows:
        if r.get("error") or r.get("answer") is None:
            continue
        by[r["condition_id"]].append(r["answer"])
    cond_ids = [c["id"] for c in exp["conditions"]]
    if len(cond_ids) != 2:
        return None
    direction = exp["analysis"].get("direction", "")
    hi = next((c for c in cond_ids if c in direction and "higher" in direction), cond_ids[1])
    lo = next(c for c in cond_ids if c != hi)
    atype = exp["analysis"]["type"]
    if atype == "proportion_comparison":
        risky = exp["analysis"].get("risky_option", "")
        prop = {c: (sum(1 for v in by[c] if str(v) == risky) / len(by[c]) if by[c] else float("nan"))
                for c in cond_ids}
        return cohens_h(prop[hi], prop[lo])
    # mean_comparison / scale
    def nums(c):
        out = []
        for v in by[c]:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                pass
        return out
    return cohens_d(nums(hi), nums(lo))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx and sy else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--experiments", nargs="+", required=True)
    ap.add_argument("--out", default="results/megastudy_calibration")
    args = ap.parse_args()

    exps = []
    for ef in args.experiments:
        exps.extend(json.loads(Path(ef).read_text()))
    results_dirs = [Path(d) for d in args.results]

    pairs = []  # (id, human_d, model_d, |human|>=0.1)
    for e in exps:
        h = e.get("human_effect_size")
        if h is None:
            continue
        rows = []
        for d in results_dirs:
            rows = load_rows(d, e["id"])
            if rows:
                break
        if not rows:
            continue
        # human ES sign is oriented to the pre-registered direction too; take |compare on aligned sign|
        # We orient model effect to the expected-higher direction; align human sign the same way.
        md = model_effect(e, rows)
        if md is None or md != md:
            continue
        pairs.append((e["id"], abs(h), md, abs(h) >= 0.1, h))

    pairs.sort(key=lambda p: -p[1])
    print(f"\n{'outcome':<34}{'|human d|':>10}{'model d':>10}{'real?':>7}")
    print("-" * 61)
    for pid, hh, md, real, hsigned in pairs:
        print(f"{pid:<34}{hh:>10.3f}{md:>10.3f}{('yes' if real else 'NULL'):>7}")

    xs = [p[1] for p in pairs]           # |human d|
    ys = [abs(p[2]) for p in pairs]      # |model d|
    r_mag = pearson(xs, ys)
    # Model effects are oriented to the pre-registered ("expected") direction, so a
    # real human effect is positive in that frame by construction; agreement = model moved
    # in the expected direction (model_d > 0).
    nt = [p[2] for p in pairs if p[3]]
    sign = sum(1 for m in nt if m > 0) / len(nt) if nt else float("nan")
    print("-" * 61)
    print(f"n outcomes: {len(pairs)}  ({sum(p[3] for p in pairs)} real, {sum(1 for p in pairs if not p[3])} null)")
    print(f"Pearson r(|human d|, |model d|): {r_mag:.3f}")
    print(f"Sign agreement on real human effects: {sign:.2f}")

    # scatter
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 6))
        for pid, hh, md, real, hs in pairs:
            ax.scatter(hs, md, c="tab:blue" if real else "tab:orange",
                       alpha=0.7, edgecolor="k", linewidth=0.3)
        lim = max(1.0, max(abs(p[4]) for p in pairs) if pairs else 1,
                  max(abs(p[2]) for p in pairs) if pairs else 1) * 1.1
        ax.plot([-lim, lim], [-lim, lim], "k--", lw=0.8, label="y = x")
        ax.axhline(0, color="gray", lw=0.5); ax.axvline(0, color="gray", lw=0.5)
        ax.set_xlabel("Human effect size (Mega-Study)")
        ax.set_ylabel("qwen3-30b effect size")
        ax.set_title("Synthetic vs human effect sizes (Mega-Study outcomes)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(str(out) + ".png", dpi=130)
        print(f"\nScatter saved to {out}.png")
    except Exception as ex:
        print(f"(plot skipped: {ex})")


if __name__ == "__main__":
    main()
