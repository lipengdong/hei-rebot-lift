#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${HEI_REBOT_VR_CONDA_ENV:-hei-rebot-vr}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${CONDA_PREFIX:-}" || "$(basename "$CONDA_PREFIX")" != "$ENV_NAME" ]]; then
  if [[ -n "${CONDA_EXE:-}" ]]; then
    CONDA_BASE="$("$CONDA_EXE" info --base)"
  else
    CONDA_BASE="$(conda info --base)"
  fi
  source "$CONDA_BASE/etc/profile.d/conda.sh"
  conda activate "$ENV_NAME"
fi

cd "$SCRIPT_DIR/mujoco_ik"
env -u LD_LIBRARY_PATH python -u hei_robot_vr_mujoco_real.py "$@"
