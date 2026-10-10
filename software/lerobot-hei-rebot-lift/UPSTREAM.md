# LeRobot Upstream Baseline

This software tree is based on Hugging Face LeRobot:

- Version: `0.6.2`
- Upstream commit: `b9cb121cb7d4e3e26ec5c906d08dda68d151ba52`
- Upstream commit date: 2026-10-08
- Upstream repository: <https://github.com/huggingface/lerobot>

## HEI-Owned Modules

The following paths contain HEI ReBot Lift integrations and must be preserved
when synchronizing with a newer upstream revision:

- `src/lerobot/robots/hei_rebot_lift/`
- `src/lerobot/motors/damiao_u2can/`
- `examples/hei_rebot_lift/`
- the `hei_rebot_lift` dependency extra and `hei-rebot-lift-host` entry point in
  `pyproject.toml`
- the HEI registrations in `src/lerobot/robots/__init__.py` and
  `src/lerobot/robots/utils.py`

Local `datasets/`, `outputs/`, and MuJoCo runtime logs are generated artifacts
and are intentionally excluded from source control and upstream replacement.

## 0.6.2 Migration Notes

- Updated `lerobot.types` imports to `lerobot.lerobot_types`.
- Moved recording keyboard input to `lerobot.utils.keyboard_input`.
- Updated the HEI host to LeRobot's multipart ZMQ observation protocol. The HEI
  client still accepts legacy Base64 JSON observations for staged deployment.
- Preserved the 18-dimensional HEI state/action schema and three named camera
  features: `front`, `left_wrist`, and `right_wrist`.
- Removed obsolete generated requirements lock files; install from
  `pyproject.toml` extras so dependency versions follow the current baseline.
