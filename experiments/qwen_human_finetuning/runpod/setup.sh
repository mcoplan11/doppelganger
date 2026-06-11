#!/bin/bash
# setup.sh — Run once on a fresh RunPod pod to install all dependencies
# Target: RTX A6000 48GB, CUDA 12.1, Python 3.11
set -e

echo "=== RunPod setup for Qwen human fine-tuning ==="

# 1. Upgrade pip
pip install --upgrade pip

# 2. Install Unsloth (detects CUDA version automatically)
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# 3. Install remaining training deps
pip install \
    trl>=0.8.6 \
    peft>=0.10.0 \
    bitsandbytes>=0.43.0 \
    accelerate>=0.27.0 \
    transformers>=4.40.0 \
    datasets>=2.19.0 \
    huggingface_hub>=0.22.0 \
    pandas>=2.0.0 \
    scipy>=1.12.0 \
    pyyaml>=6.0

# 4. Verify GPU access
python - <<'EOF'
import torch
assert torch.cuda.is_available(), "No GPU detected!"
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF

echo ""
echo "=== Setup complete. Run: bash runpod/run_job.sh ==="
