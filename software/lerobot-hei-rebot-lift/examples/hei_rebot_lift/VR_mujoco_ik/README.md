# HEI ReBot Lift VR + MuJoCo IK

This directory contains the complete VR teleoperation pipeline:

- `telegrip/`: starts the HTTPS/WebXR page, receives VR headset/controller data, and publishes it through ZMQ at `tcp://*:5567`.
- `mujoco_ik/`: receives Telegrip VR data, visualizes the dual-arm model in MuJoCo, solves FK/IK with Pinocchio + CasADi, and publishes LeRobot-compatible actions to `tcp://*:6558`.
- `examples/hei_rebot_lift/vr_control.py`: receives those actions and publishes lightweight real-robot joint/lift feedback on `tcp://*:6559` for safe startup synchronization.
- `mujoco_ik/hei_robot_vr_mujoco_sim.py`: controls the complete robot model in pure simulation. It never publishes commands to the real robot.
- `examples/hei_rebot_lift/record.py`: subscribes to `tcp://localhost:6558` and saves robot actions/observations into a LeRobotDataset.

## Layout

```text
VR_mujoco_ik/
  environment.yml          # Unified conda environment for Telegrip + MuJoCo IK
  run_telegrip.sh          # Start the VR Web page and VR data publisher
  run_mujoco_ik.sh         # Existing dual-arm real-robot action pipeline
  run_hei_robot_vr_sim.sh  # Complete robot, VR-controlled pure simulation
  run_hei_robot_vr_real.sh # Complete model + real-robot command bridge
  telegrip/                # WebXR/HTTPS/WebSocket/ZMQ VR bridge
  mujoco_ik/               # MuJoCo model, IK main program, Pinocchio tools
```

## Environment Setup

Use one shared conda environment instead of separate `VR_Telegrip` and `mujoco_vr` environments.

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

Update an existing environment:

```bash
conda env update -n hei-rebot-vr -f environment.yml --prune
```

Verify Pinocchio + CasADi:

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

## Startup Flow

### 1. Start Telegrip

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

Open in the VR headset browser:

```text
https://COMPUTER_IP:8443
```

For the first visit to the self-signed HTTPS page, manually continue in the browser.

### 2A. Test VR With the Complete Robot Model

Start Telegrip first, then open another terminal:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_sim.sh
```

This is the recommended first test for the new complete URDF. VR controls the
O-layout omnidirectional chassis, all four wheel animations, both arms, both
parallel grippers, and the lift. No command is published to port `6558` or sent
to the real robot.
The default debug scene provides a light-gray checker floor, gradient sky,
soft overhead/front-side lighting, an orange `4 x 4 m` safety boundary, a cyan
start area, and world axes at the start origin (X red, Y green, Z blue). A work
table, three colored cubes, and a locally stored textured YCB banana are also
included for pick-and-place practice.

The scene uses a stable grasp mode suitable for kinematic VR testing. Closing a
gripper near an object attaches the nearest object to that TCP while preserving
its relative pose. The object remains attached after releasing the grip button.
Opening the gripper releases it and places it on the table when it is above the
table footprint, or on the floor otherwise. Each arm can hold one object.

Controls:

- Hold the left or right grip button to move that arm. Controller translation and rotation map to the corresponding TCP at a 1:1 scale.
- While holding grip, press trigger to close the gripper and grasp a nearby scene object. Release trigger to open and place it. Releasing grip preserves the last gripper opening and any held object.
- Hold right grip and use the right thumbstick vertically for forward/backward motion and horizontally for strafing.
- While holding right grip, right `B` rotates clockwise and left `Y` rotates counterclockwise. Releasing right grip or losing the VR stream stops the chassis immediately.
- Hold left grip and move the left thumbstick vertically to control the lift.
- When grip is not held, right `A` resets the right arm and left `X` resets the left arm.
- In the MuJoCo window, press `F` to toggle body frames and `R` to reset the robot and all scene objects.

Run the model and IK self-check without opening a viewer:

```bash
./run_hei_robot_vr_sim.sh --headless-check
```

Disable all environment elements and render only the robot with:

```bash
./run_hei_robot_vr_sim.sh --plain-scene
```

The banana asset is stored under
`mujoco_ik/model/HEI_robot_urdf/scene_assets/ycb_011_banana/`. See its
`SOURCE.md` for YCB attribution and CC BY 4.0 licensing details.

### 2B. Control the Real Robot With the Complete Model

Before enabling commands, clear the robot workspace and make the emergency stop
reachable. Start the robot host and `teleoperate.py` as described in the HEI
ReBot Lift guide. `teleoperate.py` now publishes the current arm, gripper, and
lift state at 10 Hz on port `6559`. Then run:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

Real publishing remains locked until it receives fresh robot feedback and a
fresh Telegrip frame with both grip buttons released. The MuJoCo model is first
synchronized to the measured arm, gripper, and lift positions; only then does
the program publish the 14-joint/chassis/lift bridge protocol on `6558`. It maps
each URDF parallel-gripper opening to the physical Damiao gripper range (`-4.5`
open, `0` closed).

If either the VR stream or robot feedback times out, the bridge sends a zero
chassis/lift packet and returns to the locked state. After the connection
recovers, release both grip buttons to synchronize and arm again. The console
shows `feedback=<age>` and `bridge=locked/armed` for diagnosis.

For compatibility only, `--allow-no-feedback` bypasses startup synchronization.
This mode can move the arms toward the simulated startup pose as soon as the
bridge is armed and is not recommended for hardware operation.

For a first hardware test, suspend the wheels, keep the lift away from both end
stops, and test one arm at a time at low motion amplitude. Confirm that the log
shows fresh feedback and `command bridge ARMED` before pressing grip. Closing
the viewer or losing either safety stream stops chassis/lift commands; the arms
hold their latest joint targets.

### 2C. Start the Existing Dual-Arm Real-Robot Pipeline

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

## Network and Ports

```text
8443  Telegrip HTTPS VR page
8442  Telegrip WebSocket
5567  Telegrip publishes VR data, MuJoCo IK subscribes
6558  MuJoCo IK publishes actions, LeRobot record subscribes
6559  teleoperate.py/record.py publishes real robot state for startup synchronization
6556  Robot image stream, optionally displayed in Telegrip
```

Key settings in `telegrip/config.yaml`:

```yaml
vr:
  zmq_publish_endpoint: tcp://*:5567
  zmq_topic: vr_data
```

To display robot cameras in VR:

```yaml
vr_images:
  enabled: true
  endpoint: tcp://ROBOT_IP:6556
```

Default image keys:

```text
front
left_wrist
right_wrist
```

## Troubleshooting

### MuJoCo/Pinocchio Import Failure

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__)"
```

If imports only work after clearing `LD_LIBRARY_PATH`, keep using `run_mujoco_ik.sh`, which handles this case.

### VR Page Cannot Open

Make sure the computer and VR headset are on the same LAN and use:

```text
https://COMPUTER_IP:8443
```

Do not use `http`.

### Port Already in Use

```bash
ss -ltnp | grep -E '8443|8442|5567|6558'
```

Stop old Telegrip/MuJoCo IK processes and restart.

### LeRobot Recording Has No Actions

Check that Telegrip is in VR, MuJoCo IK receives controller data, MuJoCo IK publishes to `tcp://*:6558`, and `record.py` shows increasing `saved_frames`.

## Chinese Version

- [README_zh.md](README_zh.md)
