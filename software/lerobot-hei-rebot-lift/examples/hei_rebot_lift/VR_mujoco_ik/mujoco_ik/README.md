# MuJoCo IK

[English](README.md) | [中文](README_zh.md)

This is the MuJoCo + Pinocchio IK submodule in the HEI ReBot Lift VR teleoperation pipeline.

For environment installation, controller inputs, network configuration, and
safe real-robot startup, see the [VR guide](../README.md).

## Choose an Entry Point

Run these wrappers from the parent `VR_mujoco_ik/` directory. They activate the
`hei-rebot-vr` environment automatically. Run only one action publisher on `6558`.

| Entry | Model | Purpose |
| --- | --- | --- |
| `./run_hei_robot_vr_sim.sh` | `model/HEI_robot_urdf/` | Complete robot, scene, VR, stable-grasp demonstration; no real commands |
| `./run_hei_robot_vr_real.sh --enable-real-publish` | `model/HEI_robot_urdf/` | Robot-only viewer and real command bridge; requires robot feedback and grip-release arming |
| `./run_mujoco_ik.sh` | `model/reBot_description/` | Legacy dual-arm realtime controller; not the complete robot entry |

Real mode also needs the robot host and exactly one of `teleoperate.py` or
`record.py`. See the parent guide before enabling hardware commands.

## Offline Self-Checks

These checks do not publish real commands or require a VR headset:

```bash
./run_hei_robot_vr_sim.sh --headless-check
./run_hei_robot_vr_real.sh --headless-check
conda run --no-capture-output -n hei-rebot-vr python -m unittest discover -s mujoco_ik/tests -p 'test_*.py' -v
```

Passing model/protocol checks does not validate physical motor zeros, directions,
limit switches, or load capacity; test those independently before real use.

Note: install `pinocchio`, `casadi`, `eigenpy`, and `coal-python` from the conda-forge versions defined in the parent `environment.yml`. Do not install `pin` separately with pip in this folder.

## Chinese Version

- [README_zh.md](README_zh.md)
