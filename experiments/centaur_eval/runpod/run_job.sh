#!/bin/bash
# run_job.sh — Full Centaur eval pipeline on RunPod
#
# Pre-requisites:
#   - HF_TOKEN env var set (Meta Llama 3.1 license accepted on HuggingFace)
#   - setup.sh has been run
#
# Run from the repo root:
#   bash experiments/centaur_eval/runpod/run_job.sh
set -e

EXPERIMENT_DIR="experiments/centaur_eval"
cd "$(dirname "$0")/../../.."   # move to repo root

# ── HuggingFace authentication ────────────────────────────────────────────────
# Load from .env if HF_TOKEN not already in environment
if [ -z "$HF_TOKEN" ] && [ -f ".env" ]; then
    export HF_TOKEN=$(grep '^HF_TOKEN=' .env | cut -d= -f2-)
fi
if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: HF_TOKEN not found in environment or .env"
    exit 1
fi
# HF_TOKEN in environment is enough — transformers reads it automatically.
# Try hf auth login if available; ignore failure if CLI is missing/deprecated.
hf auth login --token "$HF_TOKEN" 2>/dev/null || true

# ── Pre-download model (optional but avoids timeout during eval) ──────────────
echo ""
echo "=== Pre-downloading marcelbinz/Llama-3.1-Centaur-70B (~37 GB, 20-30 min) ==="
python - <<'EOF'
from huggingface_hub import snapshot_download
path = snapshot_download(
    "marcelbinz/Llama-3.1-Centaur-70B",
    ignore_patterns=["*.pt", "original/*"],  # skip fp32 weights if present
)
print(f"Model cached at: {path}")
EOF

# ── Run all 16 experiments ────────────────────────────────────────────────────
echo ""
echo "=== Running Centaur eval (all 16 experiments) ==="
echo "    Results → $EXPERIMENT_DIR/results/"
python "$EXPERIMENT_DIR/eval.py"

echo ""
echo "=== Done! Results saved to $EXPERIMENT_DIR/results/ ==="
