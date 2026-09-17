# HEI Robot URDF MuJoCo Validation

This directory contains the complete SW2URDF model and an independent MuJoCo
kinematic viewer. It does not modify or start the existing VR control program.

[English](README.md) | [中文](README_zh.md)

The following inspection commands start in this **model directory**, not the
software root. The wrapper automatically activates `hei-rebot-vr`.

## Model check

Compile the URDF and print every MuJoCo joint, axis, range, and qpos address:

```bash
./run_mujoco_sim.sh --headless-check
```

## Visualization

```bash
./run_mujoco_sim.sh
```

Viewer keyboard controls:

- `N` / `P`: select the next or previous controllable joint.
- `-` / `=`: decrease or increase the selected joint position.
- `O` / `C`: open or close both grippers.
- `R`: restore the neutral inspection pose.

## VR-controlled complete simulation

From the `VR_mujoco_ik` directory, start Telegrip and the new pure-simulation
entry point in separate terminals:

Terminal A:

```bash
./run_telegrip.sh
```

Terminal B (also in `VR_mujoco_ik/`):

```bash
./run_hei_robot_vr_sim.sh
```

The VR simulator uses both TCP frames for reduced Pinocchio/CasADi IK and
updates this complete MuJoCo model directly. It controls the two arms, parallel
grippers, lift, chassis translation/rotation, and all four wheel animations. It does not publish real
robot commands. See [`../../../README.md`](../../../README.md) for controls.

After validating pure simulation, the separate real-robot bridge can be started
from `VR_mujoco_ik` with:

```bash
./run_hei_robot_vr_real.sh --enable-real-publish
```

Do not use the real bridge until the robot workspace, emergency stop, startup
arm pose, wheel support, and both lift limit switches have been checked. Start
one robot host and one client first. The bridge requires fresh feedback and VR
with both grips released; wait for `command bridge ARMED`. Full startup and Meta
Quest recentering instructions are in the parent VR guide. Never run simulation
and real publishing together during beginner practice.

The left finger is the primary joint on each gripper. MuJoCo does not apply the
URDF `mimic` relationship, so the viewer explicitly updates the right finger to
the opposite displacement.

The model also contains fixed kinematic frames at the center of each gripper:

- `a_right_end_link` and `b_left_end_link`: center of the finger rails.
- `a_right_tcp` and `b_left_tcp`: nominal grasp point centered between the fingertips.

## Export compiled MJCF

```bash
./run_mujoco_sim.sh \
  --headless-check \
  --save-mjcf /tmp/HEI_robot_urdf_compiled.xml
```

The exported file is useful for inspecting MuJoCo's interpretation of the URDF.
Keep the URDF as the source model; the compiled XML is a generated diagnostic
artifact and may need mesh-path adjustment if moved to another directory.

## Important conventions

- Arm joint limits follow the existing `reBot_dual_with_gripper.urdf` control conventions.
- Joint 2 uses the new SW link frame's local axis `0 -1 0`, physically matching the old model's rotated `0 0 -1` axis.
- `base_footprint` follows the standard `+X` forward, `+Y` left, `+Z` up convention.
- `base_footprint` is centered between the four wheel contact points at ground height.
- Lift and gripper prismatic joint positions are measured in meters. The lift range is `-0.8` to `0` m, matching the real `-800` to `0` mm convention.
- The viewer performs kinematic inspection only and does not call `mj_step`.
- Wheel motor IDs are 1 right front, 2 right rear, 3 left rear, 4 left front.
- Simulation grippers start closed. Hold grip and press trigger to open; release trigger to close. Releasing grip retains the last state. Real startup instead synchronizes measured gripper state.
- The stable-grasp scene attaches objects kinematically; joint limits and workspace projection are not collision avoidance.
