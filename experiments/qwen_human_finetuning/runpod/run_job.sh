#!/bin/bash
# run_job.sh — Full fine-tuning pipeline on RunPod
#
# Steps:
#   0. Data prep      — build SFT training JSONL from Twin-2K-500 (cheap; fails fast)
#   1. Baseline eval  — base Qwen2.5-7B-Instruct, no fine-tuning
#   2. Fine-tune      — QLoRA training (~30-60 min on RTX A6000)
#   3. Fine-tuned eval — same experiments, fine-tuned checkpoint
#
# Run from the repo root:
#   bash experiments/qwen_human_finetuning/runpod/run_job.sh
set -e

EXPERIMENT_DIR="experiments/qwen_human_finetuning"
cd "$(dirname "$0")/../.."   # move to repo root

# ── Step 0: Prepare data (cheapest step first, so mapping errors fail fast) ──
echo "=== Step 0/3: Prepare training data ==="
python "$EXPERIMENT_DIR/1_prepare_data.py"   # defaults come from config.yaml data:

# ── Step 1: Baseline ─────────────────────────────────────────────────────────
echo ""
echo "=== Step 1/3: Baseline eval (base Qwen2.5-7B-Instruct) ==="
echo "    Results → $EXPERIMENT_DIR/results/base/"
python "$EXPERIMENT_DIR/3_eval.py" \
    --model-path Qwen/Qwen2.5-7B-Instruct \
    --out-label base

# ── Step 2: Fine-tune ─────────────────────────────────────────────────────────
echo ""
echo "=== Step 2/3: Fine-tune Qwen2.5-7B-Instruct ==="
python "$EXPERIMENT_DIR/2_train.py"

# ── Step 3: Fine-tuned eval ───────────────────────────────────────────────────
echo ""
echo "=== Step 3/3: Fine-tuned eval ==="
echo "    Results → $EXPERIMENT_DIR/results/finetuned/"
python "$EXPERIMENT_DIR/3_eval.py" \
    --out-label finetuned

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== All done! Printing base vs fine-tuned comparison ==="
python "$EXPERIMENT_DIR/3_eval.py" --compare
