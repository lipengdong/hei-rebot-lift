#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${HEI_REBOT_VR_CONDA_ENV:-hei-rebot-vr}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/mujoco_ik"

if [[ -z "${CONDA_PREFIX:-}" || "$(basename "$CONDA_PREFIX")" != "$ENV_NAME" ]]; then
  if [[ -n "${CONDA_EXE:-}" ]]; then
    CONDA_BASE="$("$CONDA_EXE" info --base)"
  else
    CONDA_BASE="$(conda info --base)"
  fi
  # conda activate 在非交互 bash 中需要先加载 conda.sh。
  source "$CONDA_BASE/etc/profile.d/conda.sh"
  conda activate "$ENV_NAME"
fi

# 实时跟手版：运行新脚本，取消 VR 目标滤波、IK 限频和主循环 sleep。
env -u LD_LIBRARY_PATH python hei_rebot_lift_vr_mujoco_ik_realtime.py "$@"
