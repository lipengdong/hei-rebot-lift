# MuJoCo Physical Grasp Validation

[English](PHYSICS_GRASP_SIMULATION.md) | [中文](PHYSICS_GRASP_SIMULATION_zh.md)

This program is independent from the stable demonstration simulator. Stable mode attaches an object to the TCP for repeatable demonstrations. Physical mode never attaches objects and instead relies on MuJoCo gravity, collision, two-finger contact, actuator force, and friction to expose sliding, dropping, and grasp failures.

The three colored cubes are `50 mm` wide in physical mode, making reliable two-finger contact easier than with the larger stable-demonstration cubes.

Gripper closure is compliant: it closes at `40 mm/s` in simulation time before contact, independent of the VR/render loop rate, then holds the measured opening with `5 mm` of preload after both fingers touch the same object. Flat, high-friction contact pads are used instead of the irregular finger STL collision surfaces. A force-limited spring-damper assist, capped at `6 N`, compensates tangential slip only after bilateral contact; it does not teleport or weld the object. This keeps applying grip force without continuously wedging a rigid cube out of the fingers. Opening the gripper or persistently losing contact clears the hold and assist immediately.

This mode uses hybrid control. Arm joints follow IK output kinematically for the same TCP response as the stable simulator. The fingers use force-limited position actuators, while tabletop objects remain free bodies with full contact dynamics. The chassis and lift use command-level motion. This validates finger-object contact, friction, and dropping, not arm motor dynamics.

Because the robot masses in the current URDF are not measured values, `--robot-gravity-scale 0` remains the default. Tabletop objects always retain full gravity. The option is primarily reserved for later mass and inertia calibration; the kinematically controlled arms do not depend on the inaccurate arm weight.

## Start With VR

Start Telegrip first, then run:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_physics.sh
```

VR controls are unchanged. Additional keys:

| Key | Action |
| --- | --- |
| `C` | Toggle contact points and forces |
| `R` | Reset the robot and all free objects |
| `F` | Toggle body frames |

## Start With Keyboard

Keyboard mode does not require Telegrip:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_physics.sh
```

The controls match the stable keyboard simulator. `1/2/3/4` select chassis,
lift, left arm, or right arm; `5/6` reset the left or right arm. `Z/X` opens or
closes the selected gripper, `Shift` enables fine control, `Space` stops arm
tracking, `C` toggles contacts, `V` toggles frames, `Backspace` resets the full
scene, and `Esc` exits. The complete mapping is also printed at startup.

The `contacts` status reports which fingers touch each object. A `physical grasp confirmed` event requires simultaneous contact with both fingers and lifting the object above the table. Losing that condition reports `object released/dropped`.

## Parameters

```bash
./run_hei_robot_vr_physics.sh \
  --gripper-force-n 18 \
  --object-friction 1.0 \
  --robot-gravity-scale 0 \
  --physics-timestep-s 0.002
```

- `--gripper-force-n`: maximum force of each finger position actuator.
- `--object-friction`: sliding friction coefficient on object contacts.
- `--robot-gravity-scale`: robot gravity fraction; `0` fully compensates it and `1` uses full URDF weight.
- `--physics-timestep-s`: fixed MuJoCo physics step.

These simulation values are not direct equivalents of Damiao motor current, structural compliance, or real material friction. Calibrate mass, finger pad friction, and measured grip force before interpreting the result as a real-world success rate.

## Headless Check

```bash
./run_hei_robot_vr_physics.sh --headless-check
./run_hei_robot_keyboard_physics.sh --headless-check
```

The check verifies exact arm tracking of IK joint targets, actuator-driven finger motion, free object joints, gravity, table contact, and settling without TCP attachment.
