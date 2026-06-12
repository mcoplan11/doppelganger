#!/bin/bash
# setup.sh — Run once on a fresh RunPod pod to install all dependencies
# Target: A100 80GB (PCIe or SXM), CUDA 12.1, Python 3.11
set -e

echo "=== RunPod setup for Centaur eval ==="

pip install --upgrade pip

pip install -r "$(dirname "$0")/../requirements.txt"

# Verify GPU access and VRAM
python - <<'EOF'
import torch
assert torch.cuda.is_available(), "No GPU detected!"
total_vram = 0
for i in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(i)
    vram_gb = props.total_memory / 1e9
    total_vram += vram_gb
    print(f"  GPU {i}: {props.name}, {vram_gb:.1f} GB VRAM")
print(f"  Total VRAM: {total_vram:.1f} GB")
if total_vram < 40:
    print("  WARNING: Centaur-70B in 4-bit needs ~38 GB VRAM. Consider A100 80GB.")
else:
    print("  VRAM looks sufficient for Centaur-70B (4-bit).")
EOF

echo ""
echo "=== Setup complete. Run: bash runpod/run_job.sh ==="
