#!/bin/bash
# setup.sh — Run once on a fresh RunPod pod to install all dependencies
# Target: RTX A6000 48GB, CUDA 12.1, Python 3.11
set -e

echo "=== RunPod setup for Qwen human fine-tuning ==="

# 1. Upgrade pip
pip install --upgrade pip

# 2. Install all training deps from the requirements file (single source of truth).
# NOTE: version specs must never be passed unquoted on a pip command line — bash
# parses `pkg>=1.0` as an output redirection and silently drops the constraint.
pip install -r "$(dirname "$0")/../requirements_runpod.txt"

# 3. Verify GPU access
python - <<'EOF'
import torch
assert torch.cuda.is_available(), "No GPU detected!"
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF

echo ""
echo "=== Setup complete. Run: bash runpod/run_job.sh ==="
