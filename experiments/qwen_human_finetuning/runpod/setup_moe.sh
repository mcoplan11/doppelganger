#!/bin/bash
# setup_moe.sh — One-shot dependency install for the Qwen3-MoE fine-tune on a
# FRESH RunPod pod (PyTorch 2.8+ template, Triton >=3.4).
#
# USE THIS, not setup.sh — setup.sh pins torch 2.4 via unsloth[cu121-torch240],
# which ships Triton 3.0 and breaks the MoE grouped-GEMM kernel (it needs the
# Triton >=3.3 TMA API tl.make_tensor_descriptor). See GROUNDED_PERSONAS_PLAN §2.3.
#
# Why every fresh pod needs this: pip installs land on the CONTAINER disk, not the
# /workspace network volume. A pod stop/start, redeploy, or new pod wipes them —
# even though your repo, data, and ~57GB base-model cache survive on the volume.
#
# Run from anywhere:  bash experiments/qwen_human_finetuning/runpod/setup_moe.sh
set -euo pipefail

echo "=== MoE setup: installing the torch-2.8+/Triton-3.4+ stack ==="

# --upgrade pulls the latest Unsloth, which pulls a recent torch (~2.10) — exactly
# what the MoE kernel needs. Do NOT re-pin torch back to 2.4 (that is the §2.3 trap).
pip install --upgrade unsloth unsloth_zoo
pip install --upgrade peft trl transformers accelerate bitsandbytes datasets scipy pyyaml pandas huggingface_hub

# The torch bump leaves torchaudio/torchvision built against the OLD torch ABI.
# transformers 5.x imports torchaudio transitively (Parakeet RNNT loss) and dies
# with "Could not load libtorchaudio.so". We use neither — remove them so the
# model import is clean. (torchvision is belt-and-suspenders; same coupling.)
pip uninstall -y torchaudio torchvision 2>/dev/null || true

# Gate: confirm the binding §2.3 root cause (missing Triton TMA API) is gone BEFORE
# spending on GPU. Must print "make_tensor_descriptor: True".
python - <<'EOF'
import triton, torch, triton.language as tl
ok = hasattr(tl, "make_tensor_descriptor")
print(f"torch {torch.__version__} | triton {triton.__version__} | make_tensor_descriptor: {ok}")
assert ok, "Triton too old (need >=3.3) — wrong pod template. Redeploy on a PyTorch 2.8+ image."
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE (CPU-only check)")
EOF

echo ""
echo "=== Setup OK. Next:"
echo "    tmux new -s phase1"
echo "    bash experiments/qwen_human_finetuning/runpod/run_phase1.sh 2>&1 | tee /workspace/phase1.log"
