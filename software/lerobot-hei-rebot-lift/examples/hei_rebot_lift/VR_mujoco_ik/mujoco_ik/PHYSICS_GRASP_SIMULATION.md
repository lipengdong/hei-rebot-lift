# MuJoCo Physical Grasp Validation

[English](PHYSICS_GRASP_SIMULATION.md) | [中文](PHYSICS_GRASP_SIMULATION_zh.md)

This program is independent from the stable demonstration simulator. Stable mode directly attaches a nearby object to the TCP for repeatable demonstrations. Physical mode defaults to a hybrid contact-plus-assist model: an object must first contact both fingers of the same gripper, after which a bounded spring-damper attraction is activated at the current relative position. Objects remain free bodies with gravity, collision, and friction. Because the assist force is capped, table and finger contacts can still block the object instead of a hard weld pulling it through geometry.

The three colored cubes are `50 mm` wide in physical mode, making reliable two-finger contact easier than with the larger stable-demonstration cubes.

Gripper closure is compliant and runs at `40 mm/s` in simulation time before contact, independent of the VR/render loop rate. Default assisted mode freezes the measured finger opening after bilateral contact instead of adding more preload; contact-only mode retains `5 mm` of preload. Flat, high-friction contact pads replace the irregular finger STL collision surfaces. Attraction is capped at `12 N`, orientation-hold torque is capped at `0.10 N·m`, and assistance automatically breaks when position error exceeds `30 mm`. Opening the gripper or resetting the scene also releases it immediately. Both grippers cannot assist the same object simultaneously.

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

Contact-triggered soft assist is enabled by default. To evaluate a strict contact-only grasp using only actuator force, friction, and collision, run:

```bash
./run_hei_robot_keyboard_physics.sh --no-grasp-assist
```

The controls match the stable keyboard simulator. `1/2/3/4` select chassis,
lift, left arm, or right arm; `5/6` reset the left or right arm. `Z/X` opens or
closes the selected gripper, `Shift` enables fine control, `Space` stops arm
tracking, `C` toggles contacts, `V` toggles frames, `Backspace` resets the full
scene, and `Esc` exits. The complete mapping is also printed at startup.

The `contacts` status reports which fingers touch each object, while `assisted` reports active force-limited attraction. A `physical grasp confirmed` event still requires bilateral contact before the object is lifted. Opening the gripper or exceeding the break distance reports `grasp assist released`; losing the grasp reports `object released/dropped`.

## Parameters

```bash
./run_hei_robot_vr_physics.sh \
  --gripper-force-n 18 \
  --object-friction 1.0 \
  --grasp-assist \
  --robot-gravity-scale 0 \
  --physics-timestep-s 0.002
```

- `--gripper-force-n`: maximum force of each finger position actuator.
- `--object-friction`: sliding friction coefficient on object contacts.
- `--grasp-assist` / `--no-grasp-assist`: enable or disable bilateral-contact-triggered force-limited attraction; enabled by default.
- `--robot-gravity-scale`: robot gravity fraction; `0` fully compensates it and `1` uses full URDF weight.
- `--physics-timestep-s`: fixed MuJoCo physics step.

These simulation values are not direct equivalents of Damiao motor current, structural compliance, or real material friction. Calibrate mass, finger pad friction, and measured grip force before interpreting the result as a real-world success rate.

## Headless Check

```bash
./run_hei_robot_vr_physics.sh --headless-check
./run_hei_robot_keyboard_physics.sh --headless-check
```

The check verifies exact arm tracking of IK joint targets, actuator-driven finger motion, free object joints, gravity and table contact, contact-triggered assistance, and release followed by a physical drop.
