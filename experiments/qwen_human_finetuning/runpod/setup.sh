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

# 3. Remove torchao — it requires torch.int1 (torch 2.6+) but we run torch 2.4,
#    and transformers 5.x imports it unconditionally if present, crashing on load.
pip uninstall -y torchao 2>/dev/null || true

# 3. Verify GPU access
python - <<'EOF'
import torch
assert torch.cuda.is_available(), "No GPU detected!"
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF

echo ""
echo "=== Setup complete. Run: bash runpod/run_job.sh ==="
