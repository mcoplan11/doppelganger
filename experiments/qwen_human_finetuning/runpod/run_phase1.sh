#!/bin/bash
# run_phase1.sh — Phase-1 in-sample replication matrix (GROUNDED_PERSONAS_PLAN §Stage 3)
#
# Runs, in order, changing exactly ONE variable per comparison:
#   base_30b       — untrained Qwen3-30B-A3B reference (no fine-tuning)
#   run0_fictional — FT on the fictional i%n persona map (the baseline to beat)
#   runA_grounded  — FT on the grounded clustered persona map (the §2 fix)
#
# Run A vs Run 0 isolates the GROUNDING effect — the only thing that changes
# between them. base_30b vs Run 0 shows what any fine-tuning bought.
#
# Why this script exists (vs run_job.sh): the old script baselined Qwen2.5-7B
# while training the 30B base (confounding model size with fine-tuning), built
# data with no grounding flag (auto-detects grounded → Run 0 silently became
# Run A), and never preserved the Run-0 checkpoint before Run-A overwrote it.
#
# Run from anywhere:  bash experiments/qwen_human_finetuning/runpod/run_phase1.sh
set -euo pipefail

EXPERIMENT_DIR="experiments/qwen_human_finetuning"
cd "$(dirname "$0")/../../.."   # repo root

# Put ALL HuggingFace downloads (30B base ~60GB, datasets) on the big /workspace
# volume — the container root disk is tiny and overflows ("Disk quota exceeded").
if [ -d /workspace ]; then
  export HF_HOME=/workspace/hf_cache
  export HF_HUB_CACHE=/workspace/hf_cache/hub
  export TRANSFORMERS_CACHE=/workspace/hf_cache/hub
  # The xet transfer protocol's chunk cache ignores HF_HOME and writes to the
  # tiny container disk → "Disk quota exceeded". Disable it so downloads use the
  # normal HTTPS path into HF_HUB_CACHE above. (Also pin HF_XET_CACHE as backup.)
  export HF_HUB_DISABLE_XET=1
  export HF_XET_CACHE=/workspace/hf_cache/xet
fi

# Base model MUST equal the fine-tune base (config.yaml model.base), or the
# base-vs-FT comparison confounds model size with fine-tuning.
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen3-30B-A3B}"

# IDENTICAL per-study cap for BOTH fine-tune runs. The cap fights matrix-study
# imbalance (false_consensus/risk_benefit/probability_matching are ~69% of the
# uncapped data) so the signal-bearing gate study `myside` gets a fair gradient
# share. It must be the same for Run 0 and Run A, or the cap becomes a second
# changed variable. Set CAP=0 to disable (full ~100K, matrix studies dominate).
CAP="${CAP:-3000}"
cap_flag() { if [ "$CAP" -gt 0 ]; then echo "--cap-per-study $CAP"; fi; }

# Checkpoints live on the big /workspace volume on RunPod; locally, under the
# experiment dir. Mirrors 2_train.py / 3_eval.py path resolution.
if [ -d /workspace ]; then CKPT_ROOT=/workspace/checkpoints; else CKPT_ROOT="$EXPERIMENT_DIR/checkpoints"; fi

echo "Phase 1 — base=$BASE_MODEL  cap_per_study=$CAP  checkpoints=$CKPT_ROOT"

# ── Optional GPU-free pre-flights (informational; uncomment to run on the pod) ─
# python "$EXPERIMENT_DIR/prompt_parity_check.py"   # in-sample vs transfer studies
# python "$EXPERIMENT_DIR/persona_signal_check.py"  # per-study persona ICC

# ── base_30b: untrained reference ────────────────────────────────────────────
# base_30b is deterministic and its results are committed to git, so skip the
# ~30-min re-eval when they're already present. rm -rf results/base_30b to force.
if [ -d "$EXPERIMENT_DIR/results/base_30b" ] && [ -n "$(ls -A "$EXPERIMENT_DIR/results/base_30b" 2>/dev/null)" ]; then
  echo ""; echo "=== base_30b: results already present — skipping eval (rm -rf results/base_30b to force) ==="
else
  echo ""; echo "=== base_30b: untrained $BASE_MODEL (no fine-tuning) ==="
  python "$EXPERIMENT_DIR/3_eval.py" --model-path "$BASE_MODEL" --out-label base_30b
fi

# ── Run 0: fictional persona map (baseline to beat) ──────────────────────────
# --match-grounded-pids: build over the EXACT 2,058 grounded participants with
# fictional roster personas, so Run 0 and Run A differ ONLY in persona text — not
# in dataset size. Without it, --no-grounded uses just 200×2=400 participants,
# confounding grounding with a 5× larger training set. See §2.3 / §3.3.
echo ""; echo "=== Run 0: build fictional-map data (--no-grounded --match-grounded-pids) ==="
python "$EXPERIMENT_DIR/1_prepare_data.py" --no-grounded --match-grounded-pids $(cap_flag)
echo "=== Run 0: fine-tune ==="
python "$EXPERIMENT_DIR/2_train.py"
echo "=== Run 0: eval (BEFORE the checkpoint is overwritten by Run A) ==="
python "$EXPERIMENT_DIR/3_eval.py" --out-label run0_fictional
mv "$CKPT_ROOT/final" "$CKPT_ROOT/run0_final"   # preserve Run-0 checkpoint

# ── Run A: grounded clustered map (the §2 fix) ───────────────────────────────
echo ""; echo "=== Run A: build grounded-map data (--grounded) ==="
python "$EXPERIMENT_DIR/1_prepare_data.py" --grounded $(cap_flag)
echo "=== Run A: fine-tune ==="
python "$EXPERIMENT_DIR/2_train.py"
echo "=== Run A: eval ==="
python "$EXPERIMENT_DIR/3_eval.py" --out-label runA_grounded
mv "$CKPT_ROOT/final" "$CKPT_ROOT/runA_final"

# ── Comparison: the whole point — Run A vs Run 0 isolates grounding ──────────
echo ""; echo "=== Phase-1 comparison ==="
python "$EXPERIMENT_DIR/3_eval.py" --compare \
    --compare-labels base_30b run0_fictional runA_grounded

echo ""
echo "Done. Checkpoints preserved at:"
echo "  $CKPT_ROOT/run0_final   (Run 0 — fictional map)"
echo "  $CKPT_ROOT/runA_final   (Run A — grounded map)"
