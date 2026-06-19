#!/bin/bash
# run_job.sh — DEPRECATED. Use run_phase1.sh.
#
# The original 3-step flow here baselined Qwen2.5-7B-Instruct while 2_train.py
# fine-tuned the config base (now Qwen3-30B-A3B). That compared two DIFFERENT
# models, so the "base vs fine-tuned" delta was dominated by model size, not
# fine-tuning. It also built data with no grounding flag (auto-detects grounded
# → the intended Run-0 baseline silently became Run-A data) and never preserved
# the Run-0 checkpoint before Run-A overwrote it.
#
# run_phase1.sh implements the correct Phase-1 matrix (GROUNDED_PERSONAS_PLAN
# §Stage 3): base_30b → run0_fictional → runA_grounded, one variable per step.
set -euo pipefail

echo "run_job.sh is deprecated — delegating to run_phase1.sh"
echo "(see the header of this file for why; it compared two different models)"
exec bash "$(dirname "$0")/run_phase1.sh" "$@"
