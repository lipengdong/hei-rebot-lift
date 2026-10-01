# MuJoCo IK

[English](README.md) | [中文](README_zh.md)

This is the MuJoCo + Pinocchio IK submodule in the HEI ReBot Lift VR teleoperation pipeline.

For environment installation, controller inputs, network configuration, and
safe real-robot startup, see the [VR guide](../README.md).
For simulated demonstrations, ACT training, and simulation rollout, see the
[MuJoCo dataset workflow](SIM_DATASET_WORKFLOW.md).
For collision, two-finger contact, friction, and drop validation, see
[MuJoCo physical grasp validation](PHYSICS_GRASP_SIMULATION.md).
The workflow keeps the `hei-rebot-vr` simulator separate from the `lerobot5`
recording and inference clients.

## Choose an Entry Point

Run these wrappers from the parent `VR_mujoco_ik/` directory. Simulation
wrappers use `hei-rebot-vr`; recording and inference wrappers use `lerobot5`.
Run only one real-robot action publisher on `6558`.

| Entry | Model | Purpose |
| --- | --- | --- |
| `./run_hei_robot_keyboard_sim.sh` | `model/HEI_robot_urdf/` | Complete keyboard-only simulation; no VR or real commands |
| `./run_hei_robot_keyboard_physics.sh` | `model/HEI_robot_urdf/` | Keyboard physical grasp validation with free objects, contacts, friction, and force-limited actuators |
| `./run_hei_robot_keyboard_dataset_sim.sh` | `model/HEI_robot_urdf/` | Keyboard demonstration simulation server (`hei-rebot-vr`) |
| `./run_hei_robot_keyboard_record.sh` | - | Keyboard demonstration recorder (`lerobot5`) |
| `./run_hei_robot_vr_sim.sh` | `model/HEI_robot_urdf/` | Complete robot, scene, VR, stable-grasp demonstration; no real commands |
| `./run_hei_robot_vr_physics.sh` | `model/HEI_robot_urdf/` | Independent physical grasp validation with gravity, contacts, friction, and force-limited fingers |
| `./run_hei_robot_vr_dataset_sim.sh` | `model/HEI_robot_urdf/` | VR dataset simulation server (`hei-rebot-vr`) |
| `./run_hei_robot_mujoco_record.sh` | - | Independent LeRobotDataset recorder (`lerobot5`) |
| `./run_hei_robot_policy_sim.sh` | `model/HEI_robot_urdf/` | Policy simulation server (`hei-rebot-vr`) |
| `./run_hei_robot_mujoco_rollout.sh` | - | Independent policy inference client (`lerobot5`) |
| `./run_hei_robot_vr_real.sh --enable-real-publish` | `model/HEI_robot_urdf/` | Robot-only viewer and real command bridge; requires robot feedback and grip-release arming |
| `./run_mujoco_ik.sh` | `model/reBot_description/` | Legacy dual-arm realtime controller; not the complete robot entry |

## IK Smoothing and Continuous Tracking

Pure and physical complete-model simulation use this control path:

```text
VR/keyboard TCP target -> adaptive pose filter (VR) -> one IK solve
                       -> cached full joint target -> real-dt tracking
```

The VR filter automatically shortens its time constant during fast motion and
increases it during slow or stationary motion; the mapping scale remains 1:1.
Each TCP target that passes the simulation deadband is solved once. Later render
loops continue tracking the cached joint target without rerunning IPOPT for a
stationary target. Keyboard mode skips VR pose filtering but shares the joint
target cache and `dt`-based tracking.

All settings are in `hei_robot_vr_mujoco_sim.py`:

| Setting | Default | Purpose |
| --- | --- | --- |
| `TARGET_POS_EPS_M` / `TARGET_ROT_EPS_RAD` | `0.0003 m` / `0.10 deg` | Simulation TCP target deadband |
| `ARM_TARGET_FILTER_FAST_TAU_S` / `SLOW_TAU_S` | `0.018 s` / `0.055 s` | Fast/slow VR filter time constants |
| `ARM_TRACK_TIME_CONSTANT_S` | `0.045 s` | Cached joint-target tracking time constant |
| `ARM_MAX_JOINT_SPEED_RAD_S` | `[3,3,3,4,4,4]` | Maximum simulated tracking speed for six joints |
| `REAL_TARGET_POS_EPS_M` / `REAL_TARGET_ROT_EPS_RAD` | `0.0012 m` / `0.35 deg` | Original real-bridge target deadband |

A shorter `ARM_TRACK_TIME_CONSTANT_S` feels more responsive but exposes more
noise; a longer value is smoother but adds lag. Change one parameter group at a
time, then run pure simulation and the offline checks below. Real mode bypasses
the adaptive filter and `dt` tracking and retains its original fixed-step logic.

In keyboard simulation, press `5` to reset the left arm gradually or `6` to
reset the right arm. Press once; moving that arm again or pressing `Space`
cancels the reset and holds its current pose. See the [parent guide](../README.md)
for the complete key map.

From the `software/lerobot-hei-rebot-lift` root, visualize a keyboard-simulation dataset with:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  lerobot-dataset-viz \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --episode-index 0
```

Real mode also needs the robot host and exactly one of `teleoperate.py` or
`record.py`. See the parent guide before enabling hardware commands.

## Offline Self-Checks

These checks do not publish real commands or require a VR headset:

```bash
./run_hei_robot_keyboard_sim.sh --headless-check
./run_hei_robot_keyboard_physics.sh --headless-check
./run_hei_robot_vr_sim.sh --headless-check
./run_hei_robot_vr_physics.sh --headless-check
./run_hei_robot_vr_real.sh --headless-check
conda run --no-capture-output -n hei-rebot-vr python -m unittest discover -s mujoco_ik/tests -p 'test_*.py' -v
```

Passing model/protocol checks does not validate physical motor zeros, directions,
limit switches, or load capacity; test those independently before real use.

Note: install `pinocchio`, `casadi`, `eigenpy`, and `coal-python` from the conda-forge versions defined in the parent `environment.yml`. Do not install `pin` separately with pip in this folder.

## Chinese Version

- [README_zh.md](README_zh.md)
