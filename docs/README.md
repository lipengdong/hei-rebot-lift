# HEI ReBot Lift Documentation

[English](README.md) | [中文](README_zh.md)

## Start Here

Follow this order: prepare hardware, deploy environments, test pure simulation,
verify hardware independently, test real teleoperation, record data, then train
and run a policy. Real startup automatically homes the lift; clear the workspace
and keep the emergency stop reachable.

| Topic | Guide | Contents |
| --- | --- | --- |
| Project and quick setup | [Project README](../README.md) | Hardware overview, environments, startup order |
| Hardware reproduction | [Hardware guide](../hardware/README.md) | BOM, full STEP assembly, printed and metal parts |
| Robot configuration | [Driver guide](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) | Device mapping, motor parameters, lift units, watchdog |
| VR deployment and use | [VR + MuJoCo IK](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) | Pinocchio/CasADi installation, controller inputs, safe arming, troubleshooting |
| Model and controller entry points | [MuJoCo IK guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README.md) | Complete-model simulation/real mode, legacy dual-arm entry, self-checks |
| Debugging and data collection | [Examples guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | Port binding, lift/chassis tests, recording, resume, cleanup |
| Training and inference | [Examples guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | ACT/SmolVLA, checkpoint paths, replay, evaluate, rollout |
| Reproduction and collaboration | [Community](../community/README.md) | WeChat group, contact details, QR code |

## Important Conventions

- Follow each guide's working-directory instructions; paths are relative, not tied to a particular home directory.
- Robot IP and computer IP are different settings. `--remote-ip` changes the LeRobot client connection; configure the VR camera endpoint separately in `telegrip/config.yaml`.
- Run only one robot command source. Stop teleoperation before recording; stop VR control and recording before replay or policy inference.
- Workspace projection and joint limits are not collision avoidance. The stable-grasp scene is a kinematic demonstration, not proof of physical grasp stability.
- Local data is not uploaded by default. Back up datasets before deleting episodes or changing camera schemas.

Additional assembly, wiring, and video tutorials can be linked here when available.
