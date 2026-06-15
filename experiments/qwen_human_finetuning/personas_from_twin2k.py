#!/usr/bin/env python3
"""
personas_from_twin2k.py — Stage 1: Build grounded persona roster from Twin-2K-500 demographics

Fixes the core bug in 1_prepare_data.py where personas were assigned by sorted-pid position
mod 100 (i % n), making them statistically independent of the actual human answers.

This module:
  1. Loads demographics (wave1_3_response_label.csv, QID11-QID24) for all 2,058 participants
  2. Encodes mixed ordinal/nominal fields
  3. Clusters into K groups using k-prototypes (lib: kmodes)
  4. Flags ~25% as prolific_like (Gower distance to a Prolific survey-worker prototype)
  5. Generates one readable persona per cluster (deterministic template or Gemini)
  6. Emits data/personas_generated.json and data/pid_to_persona.json

Usage:
  python personas_from_twin2k.py --k-sweep          # run K ∈ {150,200,250,300,350,400} sweep
  python personas_from_twin2k.py --k 300             # generate personas at K=300
  python personas_from_twin2k.py --k 300 --gemini    # use Gemini for richer persona text
  python personas_from_twin2k.py --diagnostics-only  # print diagnostics on cached artifacts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TWIN2K_DIR = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))

DATASET_ID = "LLM-Digital-Twin/Twin-2K-500"
WAVE13_FILE = "question_catalog_and_human_response_csv/wave1_3_response_label.csv"
WAVE4_FILE = "question_catalog_and_human_response_csv/wave4_response_label.csv"

# ── Demographics field definitions (QID11-QID24) ──────────────────────────────

DEMO_QIDS = [f"QID{i}" for i in range(11, 25)]

# Ordinal fields with their ordered option lists (ascending, low → high)
ORDINAL_OPTIONS: dict[str, list[str]] = {
    "QID13": ["18-29", "30-49", "50-64", "65+"],                               # age
    "QID14": [                                                                   # education
        "Less than high school", "High school graduate",
        "Some college, no degree", "Associate's degree",
        "College graduate/some postgrad", "Postgraduate",
    ],
    "QID19": [                                                                   # religious attendance
        "Never", "Seldom", "A few times a year",
        "Once or twice a month", "Once a week", "More than once a week",
    ],
    "QID21": [                                                                   # income
        "Less than $30,000", "$30,000-$50,000", "$50,000-$75,000",
        "$75,000-$100,000", "$100,000 or more",
    ],
    "QID22": ["Very conservative", "Conservative", "Moderate", "Liberal", "Very liberal"],
    "QID23": ["1", "2", "3", "4", "More than 4"],                              # household size
}

ORDINAL_QIDS = list(ORDINAL_OPTIONS.keys())
NOMINAL_QIDS = [q for q in DEMO_QIDS if q not in ORDINAL_OPTIONS]

# Reverse maps: label → rank (1-indexed)
ORDINAL_RANKS: dict[str, dict[str, int]] = {
    qid: {label: i + 1 for i, label in enumerate(options)}
    for qid, options in ORDINAL_OPTIONS.items()
}

# ── Prolific-likeness prototype ───────────────────────────────────────────────
# Target: age 18-40, college+, full-time/part-time/student, liberal-leaning Democrat.
# Weights: age, education, employment are primary (3×); views, party are secondary (1×).

PROLIFIC_EMPLOYMENT = {"Full-time employment", "Part-time employment", "Student"}

# Ordinal prototype ranks (non-integer → preferred range midpoint)
_PROLIFIC_ORD_PROTO = {
    "QID13": 1.5,   # between rank 1 (18-29) and rank 2 (30-49): target 18-40
    "QID14": 5.0,   # college grad (rank 5)
    "QID22": 4.0,   # liberal (rank 4)
}
_PROLIFIC_ORD_WEIGHT = {"QID13": 3.0, "QID14": 3.0, "QID22": 1.0}

# Nominal prototype values
_PROLIFIC_NOM_PROTO = {"QID20": "Democrat"}   # party
_PROLIFIC_NOM_WEIGHT = {"QID20": 1.0}
# Employment handled separately (multi-value match)
_PROLIFIC_EMPL_WEIGHT = 2.0


# ── Behavioral study QIDs from wave4 (for K-sweep divergence diagnostic) ─────
# These map to the same conditions used in 1_prepare_data.py's CONDITION_TO_COLUMN.
_WAVE4_STUDY_COLS = [
    "QID157", "QID158",   # framing
    "QID168_TEXT", "QID170_TEXT",  # anchoring_redwood
    "QID164_TEXT", "QID166_TEXT",  # anchoring_africa
    "QID183", "QID184",   # savings
    "QID194", "QID195",   # myside
    "QID189", "QID190", "QID191",  # wta_wtp
    "QID192", "QID193",   # allais
    "QID181_TEXT", "QID182_TEXT",  # sunk_cost
    "QID161", "QID162",   # outcome_bias
    "QID154", "QID156",   # base_rate
    "QID291",             # omission_bias
]


# ── HuggingFace helpers ───────────────────────────────────────────────────────

def _inject_ssl() -> None:
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass


def _hf_download(filename: str) -> str:
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo_id=DATASET_ID, filename=filename, repo_type="dataset")


def load_demographics() -> pd.DataFrame:
    """Load wave1_3 demographics, return DataFrame[pid × QID11-QID24] with raw labels."""
    _inject_ssl()
    path = _hf_download(WAVE13_FILE)
    df = pd.read_csv(path, dtype=str, low_memory=False)
    # Normalise pid column
    first = df.columns[0]
    if first.lower() != "pid":
        df = df.rename(columns={first: "pid"})
    df = df.set_index("pid")
    # Keep only demographic QIDs that exist in the file
    present = [q for q in DEMO_QIDS if q in df.columns]
    missing = [q for q in DEMO_QIDS if q not in df.columns]
    if missing:
        print(f"  [WARN] Demographics QIDs not found in wave1_3: {missing}")
    return df[present].copy()


def load_wave4() -> pd.DataFrame:
    """Load wave4 behavioral responses for divergence diagnostic."""
    _inject_ssl()
    path = _hf_download(WAVE4_FILE)
    df = pd.read_csv(path, dtype=str, low_memory=False)
    first = df.columns[0]
    if first.lower() != "pid":
        df = df.rename(columns={first: "pid"})
    return df.set_index("pid")


# ── Encoding + imputation ─────────────────────────────────────────────────────

def encode_demographics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Encode demographics into ordinal ranks (df_ord) and nominal labels (df_nom).

    Returns:
        df_ord: DataFrame[pid × ORDINAL_QIDS] with integer ranks 1..max (NaN for missing)
        df_nom: DataFrame[pid × NOMINAL_QIDS] with string labels (NaN for missing)
    """
    ord_data: dict[str, pd.Series] = {}
    for qid, rank_map in ORDINAL_RANKS.items():
        if qid not in df.columns:
            continue
        raw = df[qid].str.strip()
        # Normalise common label variations
        if qid == "QID14":
            raw = raw.replace({
                "College graduate": "College graduate/some postgrad",
                "Some college": "Some college, no degree",
            })
        if qid == "QID23":
            raw = raw.replace({"More than 4": "More than 4", ">4": "More than 4", "5+": "More than 4"})
        ord_data[qid] = raw.map(rank_map)   # NaN if label not in rank_map

    df_ord = pd.DataFrame(ord_data, index=df.index, dtype=float)

    nom_cols = [q for q in NOMINAL_QIDS if q in df.columns]
    df_nom = df[nom_cols].apply(lambda s: s.str.strip()).copy()

    return df_ord, df_nom


def impute_missing(df_ord: pd.DataFrame, df_nom: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Impute missing values: median rank for ordinals, mode for nominals.

    We use median (not mean) for ordinals to stay on a valid rank value.
    Mode is taken across non-null values; if a column is all-null the fill
    value is 1 (ordinal) or 'Unknown' (nominal).
    """
    # Ordinal: floor of median (keeps it integer-valued)
    df_ord_imp = df_ord.copy()
    for col in df_ord_imp.columns:
        median_val = df_ord_imp[col].dropna().median()
        fill = int(round(median_val)) if not np.isnan(median_val) else 1
        n_miss = df_ord_imp[col].isna().sum()
        if n_miss:
            print(f"  [impute] {col}: {n_miss} missing → median rank {fill}")
        df_ord_imp[col] = df_ord_imp[col].fillna(fill)

    # Nominal: mode
    df_nom_imp = df_nom.copy()
    for col in df_nom_imp.columns:
        nonnull = df_nom_imp[col].dropna()
        fill = nonnull.mode().iloc[0] if len(nonnull) else "Unknown"
        n_miss = df_nom_imp[col].isna().sum() + (df_nom_imp[col] == "").sum()
        if n_miss:
            print(f"  [impute] {col}: {n_miss} missing → mode '{fill}'")
        df_nom_imp[col] = df_nom_imp[col].fillna(fill).replace("", fill)

    return df_ord_imp, df_nom_imp


# ── Gower distance (used for clustering and prolific scoring) ─────────────────

def gower_matrix(df_ord: pd.DataFrame, df_nom: pd.DataFrame) -> np.ndarray:
    """Compute N×N Gower distance matrix over mixed ordinal/nominal features.

    Ordinal features: L1 distance normalised to [0, 1] by feature range.
    Nominal features: 0 if equal, 1 if different.
    Average across all D features.
    Result is float32 (~17 MB for N=2058) to save memory.
    """
    n = len(df_ord)
    D = df_ord.shape[1] + df_nom.shape[1]
    dist = np.zeros((n, n), dtype=np.float32)

    # Ordinal: per-feature normalised L1
    X_ord = df_ord.values.astype(np.float32)
    for j in range(X_ord.shape[1]):
        col = X_ord[:, j]
        rng = col.max() - col.min()
        if rng > 0:
            dist += np.abs(col[:, None] - col[None, :]) / rng / D
        # If rng == 0 all values identical → contributes 0 to distance

    # Nominal: 0 if equal, 1 if different
    X_nom = df_nom.values
    for j in range(X_nom.shape[1]):
        col = X_nom[:, j]
        dist += (col[:, None] != col[None, :]).astype(np.float32) / D

    return dist


# ── Clustering ────────────────────────────────────────────────────────────────

def cluster(df_ord: pd.DataFrame, df_nom: pd.DataFrame,
            K: int, n_init: int = 5, verbose: bool = False,
            _D: np.ndarray | None = None) -> tuple[np.ndarray, list[dict]]:
    """Cluster using PAM k-medoids on the Gower distance matrix.

    Each centroid is a real participant (the medoid), which guarantees
    non-empty clusters and avoids the kmodes init failures at K ≥ 100.

    Args:
        _D: precomputed Gower matrix (reuse across K-sweep to save time)

    Returns:
        labels:    np.ndarray[int] of cluster assignments, shape (n_participants,)
        centroids: list of K dicts {qid: value} (the medoid's demographic profile)
    """
    n = len(df_ord)
    if _D is None:
        _D = gower_matrix(df_ord, df_nom)

    # Sum-of-distances from each point to all others (used for initial medoid)
    row_sums = _D.sum(axis=1).astype(np.float64)

    rng = np.random.RandomState(42)
    best_labels: np.ndarray | None = None
    best_cost = float("inf")

    for init_run in range(n_init):
        # k-means++ style initialisation: guarantees K distinct medoids
        medoids = np.empty(K, dtype=int)
        if init_run == 0:
            # First run: seed with the most central point
            medoids[0] = int(row_sums.argmin())
        else:
            medoids[0] = rng.randint(n)

        min_d_to_medoid = _D[medoids[0]].copy().astype(np.float64)
        for m in range(1, K):
            # Probabilistic selection proportional to squared distance to nearest medoid
            probs = min_d_to_medoid ** 2
            probs_sum = probs.sum()
            if probs_sum == 0:
                # All remaining points are identical to existing medoids
                remaining = list(set(range(n)) - set(medoids[:m].tolist()))
                medoids[m] = rng.choice(remaining) if remaining else rng.randint(n)
            else:
                probs /= probs_sum
                medoids[m] = rng.choice(n, p=probs)
            min_d_to_medoid = np.minimum(min_d_to_medoid, _D[medoids[m]])

        # PAM iterations
        for _ in range(100):
            # Assign each point to nearest medoid
            D_medoids = _D[:, medoids]                   # (n, K)
            labels = D_medoids.argmin(axis=1).astype(int) # (n,)

            # Update each medoid to the cluster member minimising total within-cluster dist
            new_medoids = medoids.copy()
            for k in range(K):
                mask = labels == k
                if not mask.any():
                    # Empty cluster (rare with k-means++ init): keep old medoid
                    continue
                cluster_idxs = np.where(mask)[0]
                # Sum of distances from each candidate to all other cluster members
                within = _D[np.ix_(cluster_idxs, cluster_idxs)].sum(axis=1)
                new_medoids[k] = cluster_idxs[within.argmin()]

            if np.array_equal(new_medoids, medoids):
                break
            medoids = new_medoids

        cost = _D[:, medoids].min(axis=1).sum()
        if cost < best_cost:
            best_cost = cost
            best_labels = labels.copy()
            best_medoids = medoids.copy()

        if verbose:
            print(f"  [cluster] init {init_run + 1}/{n_init}: cost={cost:.4f}")

    # Build centroid dicts from the medoid's actual profile
    ord_qids = df_ord.columns.tolist()
    nom_qids = df_nom.columns.tolist()
    centroids = []
    for k in range(K):
        med_idx = best_medoids[k]
        centroid: dict[str, str] = {}
        for i, qid in enumerate(ord_qids):
            rank = int(round(float(df_ord.iloc[med_idx, i])))
            options = ORDINAL_OPTIONS[qid]
            rank_clamped = max(1, min(rank, len(options)))
            centroid[qid] = options[rank_clamped - 1]
        for i, qid in enumerate(nom_qids):
            centroid[qid] = str(df_nom.iloc[med_idx, i])
        centroids.append(centroid)

    return best_labels, centroids


# ── Prolific-likeness scoring ─────────────────────────────────────────────────

def score_prolific_likeness(df_ord: pd.DataFrame, df_nom: pd.DataFrame) -> pd.Series:
    """Compute per-participant Gower distance to the Prolific survey-worker prototype.

    Lower score = more Prolific-like. Weights: age (3×), education (3×),
    employment (2×), political views (1×), party (1×). Total weight = 10.
    """
    scores = pd.Series(0.0, index=df_ord.index)
    weight_sum = 0.0

    # Ordinal features
    for qid, proto_rank in _PROLIFIC_ORD_PROTO.items():
        if qid not in df_ord.columns:
            continue
        w = _PROLIFIC_ORD_WEIGHT.get(qid, 0.5)
        max_rank = len(ORDINAL_OPTIONS[qid])
        dist = (df_ord[qid] - proto_rank).abs() / (max_rank - 1)
        scores += w * dist
        weight_sum += w

    # Employment (multi-value nominal match)
    empl_qid = "QID24"
    if empl_qid in df_nom.columns:
        w = _PROLIFIC_EMPL_WEIGHT
        dist = (~df_nom[empl_qid].isin(PROLIFIC_EMPLOYMENT)).astype(float)
        scores += w * dist
        weight_sum += w

    # Nominal features
    for qid, proto_val in _PROLIFIC_NOM_PROTO.items():
        if qid not in df_nom.columns:
            continue
        w = _PROLIFIC_NOM_WEIGHT.get(qid, 0.5)
        dist = (df_nom[qid] != proto_val).astype(float)
        scores += w * dist
        weight_sum += w

    if weight_sum > 0:
        scores /= weight_sum

    return scores


def flag_prolific_like(scores: pd.Series, target_fraction: float = 0.25) -> pd.Series:
    """Return boolean Series: True for the closest `target_fraction` to the Prolific prototype."""
    threshold = scores.quantile(target_fraction)
    return scores <= threshold


# ── K-sweep diagnostic ────────────────────────────────────────────────────────

def _compute_divergence(labels: np.ndarray, wave4: pd.DataFrame,
                        pids: list[str]) -> float:
    """Mean absolute deviation of cluster means from the global mean, averaged
    across behavioral study columns. Higher = demographics predict behavior more."""
    study_cols = [c for c in _WAVE4_STUDY_COLS if c in wave4.columns]
    if not study_cols:
        return float("nan")

    # Align wave4 to the clustered pids
    common = [p for p in pids if p in wave4.index]
    if not common:
        return float("nan")

    idx_map = {p: i for i, p in enumerate(pids)}
    sub_labels = np.array([labels[idx_map[p]] for p in common])
    sub_wave4 = wave4.loc[common, study_cols].apply(pd.to_numeric, errors="coerce")

    K = labels.max() + 1
    # Build pid → sub_labels index for fast lookup
    pid_to_sub_idx = {p: i for i, p in enumerate(common)}
    deviations = []
    for col in study_cols:
        col_vals = sub_wave4[col].dropna()
        if len(col_vals) < 10:
            continue
        global_mean = col_vals.mean()
        global_std = col_vals.std()
        if global_std < 1e-6:
            continue
        # Get cluster labels for each pid in col_vals
        col_pids = col_vals.index.tolist()
        col_lbls = np.array([sub_labels[pid_to_sub_idx[p]]
                             for p in col_pids if p in pid_to_sub_idx], dtype=int)
        col_v = col_vals[[p for p in col_pids if p in pid_to_sub_idx]].values
        cluster_means = []
        for k in range(K):
            mask = col_lbls == k
            if mask.sum() < 2:
                continue
            cluster_means.append(abs(col_v[mask].mean() - global_mean) / global_std)
        if cluster_means:
            deviations.append(np.mean(cluster_means))

    return float(np.mean(deviations)) if deviations else float("nan")


def k_sweep(df_ord: pd.DataFrame, df_nom: pd.DataFrame,
            prolific_scores: pd.Series,
            wave4: pd.DataFrame | None,
            K_values: list[int] | None = None,
            n_init: int = 3,
            _D: np.ndarray | None = None) -> None:
    """Run k-prototypes at multiple K values and print a diagnostic table.

    Reports per K:
      (a) mean per-cluster answer-divergence from behavioral marginal (want high)
      (b) min/median/max cluster size
      (c) % clusters with ≥ 5 members (required floor)
      (d) count of Prolific-majority clusters (>50% prolific_like members)
    """
    if K_values is None:
        K_values = [150, 200, 250, 300, 350, 400]

    prolific_flag = flag_prolific_like(prolific_scores)
    pids = df_ord.index.tolist()

    # Precompute Gower matrix once and reuse across all K values
    if _D is None:
        print("  Computing Gower distance matrix (reused across all K values)...")
        t_gower = time.time()
        _D = gower_matrix(df_ord, df_nom)
        print(f"  Gower matrix: {_D.shape}, {_D.nbytes // 1024 // 1024}MB "
              f"({(time.time() - t_gower)*1000:.0f}ms)")

    print("\n" + "=" * 80)
    print("K-SWEEP DIAGNOSTIC")
    print("=" * 80)
    print(f"{'K':>5} | {'divergence':>10} | {'min':>4} {'med':>4} {'max':>4} | "
          f"{'≥5 (%)':>7} | {'prolific clusters':>18} | {'cost (ms)':>9}")
    print("-" * 80)

    results = []
    for K in K_values:
        t0 = time.time()
        labels, _ = cluster(df_ord, df_nom, K, n_init=n_init, _D=_D)
        elapsed_ms = (time.time() - t0) * 1000

        sizes = np.bincount(labels)
        min_sz, med_sz, max_sz = sizes.min(), np.median(sizes), sizes.max()
        pct_floor = 100.0 * (sizes >= 5).sum() / K

        # Prolific-majority clusters
        n_prolific_maj = 0
        for k in range(K):
            mask = labels == k
            if mask.sum() == 0:
                continue
            pid_in_k = [pids[i] for i, m in enumerate(mask) if m]
            n_prolific_in_k = prolific_flag.loc[pid_in_k].sum()
            if n_prolific_in_k / mask.sum() > 0.5:
                n_prolific_maj += 1

        # Behavioral divergence
        if wave4 is not None:
            div = _compute_divergence(labels, wave4, pids)
        else:
            div = float("nan")

        results.append((K, div, int(min_sz), int(med_sz), int(max_sz),
                        pct_floor, n_prolific_maj, elapsed_ms))
        div_str = f"{div:.3f}" if not np.isnan(div) else "  n/a"
        print(f"{K:>5} | {div_str:>10} | {int(min_sz):>4} {int(med_sz):>4} {int(max_sz):>4} | "
              f"{pct_floor:>6.1f}% | {n_prolific_maj:>18} | {elapsed_ms:>8.0f}ms")

    print("-" * 80)
    print("\nGUIDELINES:")
    print("  • Pick K at the divergence knee (where gains flatten)")
    print("  • Ensure ≥ ~90% of clusters have ≥ 5 members (keep individuality signal)")
    print("  • Prolific clusters ≥ 200 preferred (eval roster target = 200)")
    print("  • If divergence is weak at every K, demographics may not predict these biases")


# ── Persona generation ────────────────────────────────────────────────────────

_REGION_SHORT = {
    "Northeast": "ne",
    "Midwest": "mw",
    "South": "south",
    "West": "west",
    "Pacific": "pacific",
}
_EMPL_SHORT = {
    "Full-time employment": "worker",
    "Part-time employment": "worker_pt",
    "Unemployed": "unemployed",
    "Self-employed": "self_employed",
    "Home-maker": "homemaker",
    "Student": "student",
    "Retired": "retired",
}
_AGE_FIRST_NUM = {"18-29": "18", "30-49": "30", "50-64": "50", "65+": "65"}


def _persona_name(cluster_id: int, profile: dict) -> str:
    age = profile.get("QID13", "30-49")
    empl = profile.get("QID24", "Full-time employment")
    region_raw = profile.get("QID11", "")
    sex = profile.get("QID12", "")

    region_key = region_raw.split(" ")[0] if region_raw else ""
    region_short = _REGION_SHORT.get(region_key, "us")
    sex_short = "f" if "Female" in (sex or "") else "m" if "Male" in (sex or "") else "x"
    empl_short = _EMPL_SHORT.get(empl, "worker")
    age_num = _AGE_FIRST_NUM.get(age, "30")

    return f"{region_short}_{empl_short}_{age_num}{sex_short}_c{cluster_id:03d}"


_AGE_DESC = {
    "18-29": "in their twenties", "30-49": "in their thirties or forties",
    "50-64": "in their fifties or early sixties", "65+": "65 or older",
}
_EDU_DESC = {
    "Less than high school": "did not complete high school",
    "High school graduate": "high school graduate",
    "Some college, no degree": "some college, no degree",
    "Associate's degree": "associate's degree holder",
    "College graduate/some postgrad": "college graduate",
    "Postgraduate": "postgraduate degree holder",
}
_EMPL_DESC = {
    "Full-time employment": "works full-time",
    "Part-time employment": "works part-time",
    "Unemployed": "currently unemployed",
    "Self-employed": "self-employed",
    "Home-maker": "homemaker",
    "Student": "student",
    "Retired": "retired",
}
_VIEWS_DESC = {
    "Very conservative": "strongly conservative", "Conservative": "center-right",
    "Moderate": "moderate", "Liberal": "center-left", "Very liberal": "strongly liberal",
}
_SURVEY_BEHAVIORS = [
    "Takes surveys at a moderate pace, reads questions fully before answering.",
    "Tends to satisfice on long matrix pages; picks the first plausible option.",
    "Reads carefully and occasionally reconsiders before submitting.",
    "Moves quickly through familiar question formats; uses the middle of scales as a default.",
    "Engages earnestly; writes short sentences on open-ended text boxes.",
    "Skims vignettes for keywords, answers promptly, rarely changes responses.",
    "Paces steadily; uses the full scale range when confident, middle options when unsure.",
    "Completes surveys efficiently; prefers binary or MC questions over sliders.",
    "Takes time on attention checks; answers more quickly on repeated question formats.",
    "Pragmatic: reads enough to understand the gist and answers from gut instinct.",
]


def generate_persona_template(cluster_id: int, profile: dict) -> tuple[str, str]:
    """Generate persona name + description deterministically from cluster profile."""
    age = profile.get("QID13", "30-49")
    edu = profile.get("QID14", "Some college, no degree")
    empl = profile.get("QID24", "Full-time employment")
    region_raw = profile.get("QID11", "")
    sex = profile.get("QID12", "")
    income = profile.get("QID21", "")
    views = profile.get("QID22", "Moderate")
    party = profile.get("QID20", "")

    name = _persona_name(cluster_id, profile)

    region_key = region_raw.split(" ")[0] if region_raw else ""
    region_phrase = {
        "Northeast": "in the northeastern US", "Midwest": "in the Midwest",
        "South": "in the South", "West": "in the western US", "Pacific": "in the Pacific",
    }.get(region_key, "in the US")

    age_desc = _AGE_DESC.get(age, "")
    edu_desc = _EDU_DESC.get(edu, "some college education")
    empl_desc = _EMPL_DESC.get(empl, "works")
    views_desc = _VIEWS_DESC.get(views, "moderate")
    sex_desc = "Woman" if "Female" in (sex or "") else "Man" if "Male" in (sex or "") else "Person"

    income_phrase = ""
    if income:
        income_phrase = f" Family income around {income.lower()}."

    party_phrase = f" Votes {party}." if party and party not in ("Something else", "Independent") else ""

    behavior = _SURVEY_BEHAVIORS[cluster_id % len(_SURVEY_BEHAVIORS)]

    description = (
        f"{sex_desc} {age_desc}, {region_phrase}. {edu_desc.capitalize()}, {empl_desc}."
        f" Politically {views_desc}.{party_phrase}{income_phrase}"
        f" {behavior}"
    )

    return name, description


def generate_persona_gemini(cluster_id: int, profile: dict, api_key: str,
                            model: str = "gemini-2.0-flash") -> tuple[str, str]:
    """Call Gemini to write a vivid persona in the personas.py voice."""
    from google import genai as google_genai
    from google.genai import types as gtypes

    client = google_genai.Client(api_key=api_key)

    example_persona = (
        "19-year-old biology student at a state university in Illinois. High school diploma. "
        "Takes Prolific surveys on her phone between classes for coffee money. She skims "
        "vignettes looking for keywords and clicks neutral options if a matrix question "
        "looks too long."
    )

    # Build readable profile string
    field_labels = {
        "QID11": "Region", "QID12": "Sex", "QID13": "Age band", "QID14": "Education",
        "QID15": "Race", "QID16": "Citizen", "QID17": "Marital status",
        "QID18": "Religion", "QID19": "Religious attendance", "QID20": "Political party",
        "QID21": "Income", "QID22": "Political views",
        "QID23": "Household size", "QID24": "Employment",
    }
    profile_lines = "\n".join(f"  {field_labels.get(k, k)}: {v}" for k, v in profile.items())

    prompt = f"""Write a short persona description for a Prolific/MTurk survey participant with this demographic profile:

{profile_lines}

Write exactly 3–4 sentences in this exact voice (do not copy, just match the style):
"{example_persona}"

Rules:
- Start with "{profile.get('QID13', '')} {profile.get('QID12', '').lower()}, {profile.get('QID14', '').lower()}, {profile.get('QID24', '').lower()}"
- Mention a specific US location consistent with {profile.get('QID11', '')}
- Include one survey-taking behavior detail (pace, device, attention, satisficing pattern)
- Do NOT mention the cluster ID number
- Return ONLY the description text, no JSON, no preamble

Description:"""

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=gtypes.GenerateContentConfig(temperature=0.8),
    )
    description = resp.text.strip()

    name = _persona_name(cluster_id, profile)
    return name, description


# ── Artifact emission ─────────────────────────────────────────────────────────

def build_personas(
    labels: np.ndarray,
    centroids: list[dict],
    df_raw: pd.DataFrame,
    prolific_scores: pd.Series,
    prolific_flag: pd.Series,
    use_gemini: bool = False,
    gemini_api_key: str | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Build personas_generated.json entries and pid_to_persona.json mapping.

    Returns:
        personas: list of persona dicts (one per cluster)
        pid_map: {pid → {persona_name, prolific_like}}
    """
    K = len(centroids)
    pids = df_raw.index.tolist()

    # Per-cluster statistics
    cluster_pids: dict[int, list[str]] = {k: [] for k in range(K)}
    for i, pid in enumerate(pids):
        cluster_pids[labels[i]].append(pid)

    personas = []
    pid_map: dict[str, dict] = {}

    print(f"  Generating {K} persona descriptions ({' Gemini' if use_gemini else 'template'})...")
    for k in range(K):
        profile = centroids[k]
        c_pids = cluster_pids[k]
        n_members = len(c_pids)
        prolific_in_k = prolific_flag.loc[c_pids].sum() if c_pids else 0
        prolific_share = prolific_in_k / n_members if n_members else 0.0

        if use_gemini and gemini_api_key:
            try:
                name, description = generate_persona_gemini(k, profile, gemini_api_key)
            except Exception as e:
                print(f"    [WARN] Gemini failed for cluster {k}: {e} — falling back to template")
                name, description = generate_persona_template(k, profile)
        else:
            name, description = generate_persona_template(k, profile)

        persona = {
            "name": name,
            "description": description,
            "cluster_id": k,
            "cluster_profile": profile,
            "n_participants": n_members,
            "prolific_share": round(float(prolific_share), 3),
        }
        personas.append(persona)

        # Build pid → persona mapping
        for pid in c_pids:
            pid_map[pid] = {
                "persona_name": name,
                "prolific_like": bool(prolific_flag.get(pid, False)),
            }

        if (k + 1) % 50 == 0:
            print(f"    {k + 1}/{K} done")

    return personas, pid_map


# ── Diagnostics ───────────────────────────────────────────────────────────────

def print_diagnostics(personas: list[dict], pid_map: dict[str, dict],
                      df_raw: pd.DataFrame, prolific_scores: pd.Series) -> None:
    """Print cluster-size distribution, Prolific subset demographics, and persona preview."""
    sizes = [p["n_participants"] for p in personas]
    prolific_flag = pd.Series({pid: v["prolific_like"] for pid, v in pid_map.items()})

    print("\n" + "=" * 80)
    print("CLUSTER SIZE DISTRIBUTION")
    print("=" * 80)
    print(f"  Total clusters: {len(personas)}")
    print(f"  Min: {min(sizes)}, Median: {np.median(sizes):.1f}, Max: {max(sizes)}")
    print(f"  Clusters with < 5 members: {sum(1 for s in sizes if s < 5)}")
    buckets = [(1, 1), (2, 2), (3, 4), (5, 9), (10, 19), (20, 99), (100, 9999)]
    for lo, hi in buckets:
        n = sum(1 for s in sizes if lo <= s <= hi)
        if n:
            label = f"{lo}" if lo == hi else f"{lo}–{hi}"
            print(f"    {label:>8} members: {n} clusters")

    print(f"\n  Total participants mapped: {len(pid_map)}")
    n_prolific = prolific_flag.sum()
    print(f"  Prolific-like participants: {n_prolific} ({100*n_prolific/len(pid_map):.1f}%)")
    n_prolific_maj = sum(1 for p in personas if p["prolific_share"] > 0.5)
    print(f"  Prolific-majority clusters: {n_prolific_maj} (>50% prolific_like members)")

    print("\n" + "=" * 80)
    print("PROLIFIC-LIKE SUBSET DEMOGRAPHICS  (should skew young / educated / employed)")
    print("=" * 80)
    prolific_pids = [pid for pid, v in pid_map.items() if v["prolific_like"]]
    sub = df_raw.loc[[p for p in prolific_pids if p in df_raw.index]]
    for qid in ["QID13", "QID14", "QID24", "QID22", "QID20"]:
        if qid not in sub.columns:
            continue
        counts = sub[qid].value_counts(normalize=True) * 100
        print(f"\n  {qid}:")
        for val, pct in counts.head(6).items():
            print(f"    {val:<40} {pct:5.1f}%")

    print("\n" + "=" * 80)
    print("PERSONA SAMPLE (first 5)")
    print("=" * 80)
    for p in personas[:5]:
        print(f"\n  Cluster {p['cluster_id']:>3} | n={p['n_participants']:>4} | "
              f"prolific_share={p['prolific_share']:.2f}")
        print(f"  Name: {p['name']}")
        print(f"  Desc: {p['description'][:120]}...")
        prof = p["cluster_profile"]
        print(f"  Profile: age={prof.get('QID13')}, edu={prof.get('QID14')}, "
              f"empl={prof.get('QID24')}, views={prof.get('QID22')}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build grounded personas from Twin-2K-500 demographics (Stage 1)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--k-sweep", action="store_true",
                      help="Run K-sweep diagnostic at K ∈ {150,200,250,300,350,400}")
    mode.add_argument("--k", type=int, metavar="K",
                      help="Generate personas at this K (e.g. --k 300)")
    mode.add_argument("--diagnostics-only", action="store_true",
                      help="Print diagnostics on existing cached artifacts, skip regeneration")

    parser.add_argument("--gemini", action="store_true",
                        help="Use Gemini API for richer persona text (default: deterministic template)")
    parser.add_argument("--n-init", type=int, default=5,
                        help="k-prototypes random restarts (default: 5)")
    parser.add_argument("--prolific-fraction", type=float, default=0.25,
                        help="Fraction to flag as prolific_like (default: 0.25)")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory (default: <script-dir>/data)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).parent / "data"
    if not out_dir.is_absolute():
        out_dir = Path(__file__).parent / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    personas_path = out_dir / "personas_generated.json"
    pid_map_path = out_dir / "pid_to_persona.json"

    if args.diagnostics_only:
        if not personas_path.exists() or not pid_map_path.exists():
            print("No cached artifacts found. Run with --k <K> first.")
            sys.exit(1)
        with open(personas_path) as f:
            personas = json.load(f)
        with open(pid_map_path) as f:
            pid_map = json.load(f)

        print("Loading demographics for diagnostic...")
        df_raw = load_demographics()
        _, df_nom = encode_demographics(df_raw)
        df_ord, df_nom = encode_demographics(df_raw)
        df_ord, df_nom = impute_missing(df_ord, df_nom)
        prolific_scores = score_prolific_likeness(df_ord, df_nom)
        print_diagnostics(personas, pid_map, df_raw, prolific_scores)
        return

    # Load + encode demographics
    print("Loading demographics (wave1_3_response_label.csv)...")
    df_raw = load_demographics()
    print(f"  {len(df_raw)} participants × {len(df_raw.columns)} columns")

    print("Encoding demographics...")
    df_ord, df_nom = encode_demographics(df_raw)
    print(f"  Ordinal features: {df_ord.columns.tolist()}")
    print(f"  Nominal features: {df_nom.columns.tolist()}")

    print("Imputing missing values...")
    df_ord, df_nom = impute_missing(df_ord, df_nom)

    print("Scoring Prolific-likeness...")
    prolific_scores = score_prolific_likeness(df_ord, df_nom)
    prolific_flag = flag_prolific_like(prolific_scores, args.prolific_fraction)
    n_prolific = prolific_flag.sum()
    print(f"  {n_prolific} participants flagged as prolific_like "
          f"({100*n_prolific/len(df_raw):.1f}%)")

    if args.k_sweep:
        print("\nLoading wave4 behavioral data for divergence diagnostic...")
        try:
            wave4 = load_wave4()
            print(f"  {len(wave4)} rows × {len(wave4.columns)} columns")
        except Exception as e:
            print(f"  [WARN] Could not load wave4: {e} — divergence will be n/a")
            wave4 = None
        k_sweep(df_ord, df_nom, prolific_scores, wave4, n_init=args.n_init)
        return

    # Generate at specified K
    K = args.k
    print(f"\nComputing Gower distance matrix...")
    D = gower_matrix(df_ord, df_nom)
    print(f"  {D.shape}, {D.nbytes // 1024 // 1024}MB")
    print(f"Clustering at K={K} (n_init={args.n_init}, PAM k-medoids)...")
    labels, centroids = cluster(df_ord, df_nom, K, n_init=args.n_init, _D=D)
    sizes = np.bincount(labels)
    print(f"  Cluster sizes: min={sizes.min()}, median={np.median(sizes):.1f}, max={sizes.max()}")
    n_below_floor = (sizes < 5).sum()
    if n_below_floor:
        print(f"  [WARN] {n_below_floor} clusters have < 5 members — consider lower K")

    gemini_api_key = None
    if args.gemini:
        gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not gemini_api_key:
            # Try .env in repo root
            env_path = ROOT / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("GEMINI_API_KEY="):
                        gemini_api_key = line.split("=", 1)[1].strip()
                        break
        if not gemini_api_key:
            print("[WARN] --gemini requested but no GEMINI_API_KEY found; using template")
            args.gemini = False

    print("Building personas...")
    personas, pid_map = build_personas(
        labels, centroids, df_raw, prolific_scores, prolific_flag,
        use_gemini=args.gemini, gemini_api_key=gemini_api_key,
    )

    # Save artifacts
    with open(personas_path, "w") as f:
        json.dump(personas, f, indent=2)
    print(f"\nSaved {len(personas)} personas → {personas_path}")

    with open(pid_map_path, "w") as f:
        json.dump(pid_map, f, indent=2)
    print(f"Saved {len(pid_map)} pid mappings → {pid_map_path}")

    # Print diagnostics
    print_diagnostics(personas, pid_map, df_raw, prolific_scores)

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("  1. Review the diagnostics above — especially:")
    print("     • Prolific-like subset should skew young/educated/employed")
    print("     • Per-cluster sizes should mostly be ≥ 5")
    print("     • Run --k-sweep to confirm this K is at the divergence knee")
    print("  2. Hand-edit data/personas_generated.json if any descriptions need fixing")
    print("  3. Proceed to Stage 2: update 1_prepare_data.py and 3_eval.py")
    print()


if __name__ == "__main__":
    main()
