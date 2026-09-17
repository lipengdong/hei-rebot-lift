# HEI ReBot Lift Software

[English](README.md) | [中文](README_zh.md)

This is the runnable LeRobot-based software project for the dual-arm lifting
mobile robot. The repository-wide deployment guide lives two directories above.
**Do not follow a second, older installation procedure from this folder.**

## Start Here

1. Follow the [project setup guide](../../README.md#-quick-setup): install the robot-side `lerobot5`, computer-side `lerobot5`, and computer-side `hei-rebot-vr` dependencies according to their roles.
2. Practice with the [complete-model pure simulation](examples/hei_rebot_lift/VR_mujoco_ik/README.md#2a-test-vr-with-the-complete-robot-model) before connecting real hardware.
3. On the robot, bind serial ports and independently verify zeros, chassis, lift IO, and cameras using the [hardware tests](examples/hei_rebot_lift/README.md#1-hardware-check).
4. Follow the [real startup guide](../../README.md#-startup-flow), then record, train, and test using the examples below.

## Module Guides

| Module | Guide | Purpose |
| --- | --- | --- |
| Example programs | [Examples](examples/hei_rebot_lift/README.md) | Binding, independent tests, teleoperate, record/resume, dataset editing, ACT/SmolVLA, replay, evaluate, rollout |
| VR and simulation | [VR + MuJoCo IK](examples/hei_rebot_lift/VR_mujoco_ik/README.md) | Shared VR/IK environment, headset URL, Meta Quest calibration, controller inputs, real synchronization |
| Robot driver | [Driver](src/lerobot/robots/hei_rebot_lift/README.md) | Device/camera config, action/observation units, lift homing, motor gains and safety timeouts |
| Motor transport | [Damiao U2CAN source](src/lerobot/motors/damiao_u2can/) | Local motor communication implementation; independent of the old copied reference projects |
| All documentation | [Documentation index](../../docs/README.md) | Hardware, software, model, community, and language navigation |

## Working Directories and Safety

This directory is the **software root**. Commands beginning with
`PYTHONPATH=src` in the examples guide run here. VR wrappers run from
`examples/hei_rebot_lift/VR_mujoco_ik/` and activate `hei-rebot-vr` automatically.

- Headset URL uses the **computer IP**; client `--remote-ip` uses the **robot IP**.
- VR camera display is currently disabled in Telegrip, but host camera capture and recording remain enabled.
- The host automatically homes the lift upward. Check both limits and clear the path before starting.
- Only one robot command source may run at a time. Stop teleoperation before recording and stop VR real publishing before replay/evaluate/rollout.
- The arm zero tool writes zeros immediately; it is not a read-only diagnostic.
- The real bridge needs fresh VR and robot feedback plus both grips released. Do not bypass feedback to fix a connection fault.
- No-load simulation and IK guards do not establish collision avoidance or payload safety.

## LeRobot Foundation

General LeRobot documentation remains under `docs/`, and policy-specific notes
under `docs/source/policy_*_README.md`. Those explain the underlying framework;
they do not replace the HEI hardware startup instructions. Respect the
[repository license](../../LICENSE) and third-party asset licenses.
