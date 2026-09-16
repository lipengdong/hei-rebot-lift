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

#### VR Controller Tutorial

Arm motion uses relative poses. Each time a side's `grip` is pressed, the
current controller pose and corresponding robot TCP pose become the control
origin. Subsequent XYZ translation and rotation map to that TCP at a 1:1 scale.
Releasing `grip` holds the last arm target; pressing it again captures a new
origin, so the controller never needs to return to a fixed absolute pose.

| Controller input | Active when | Function |
| --- | --- | --- |
| Left `grip` | Held | Enable relative left-arm control and left-stick lift control |
| Right `grip` | Held | Enable relative right-arm control and chassis controls |
| Left/right `trigger` | Corresponding `grip` held | Press to open that gripper; release to close it |
| Left stick vertical | Left `grip` held | Push forward to raise the lift; pull back to lower it |
| Right stick vertical | Right `grip` held | Drive the chassis forward or backward |
| Right stick horizontal | Right `grip` held | Strafe the O-layout omnidirectional chassis left or right |
| Right `B` | Right `grip` held | Rotate the chassis clockwise |
| Left `Y` | Right `grip` held | Rotate the chassis counterclockwise |
| Right `A` | Right `grip` released | Return the right arm gradually to its default pose |
| Left `X` | Left `grip` released | Return the left arm gradually to its default pose |

Arm and gripper procedure:

1. Put the controller in a comfortable pose and clear the corresponding arm's workspace.
2. Hold that side's `grip` to capture the current control origin, then translate or rotate the controller to move the TCP.
3. The grippers start closed. While continuing to hold `grip`, press `trigger` to open the gripper and place it around the object.
4. Release `trigger` to close and grasp. Releasing `grip` stops arm tracking but preserves the last gripper state.
5. To release the object, hold the corresponding `grip` again and press `trigger`.

Chassis and lift procedure:

1. Right `grip` enables the chassis. Hold it while using the right stick for translation and right `B` or left `Y` for rotation. Releasing right `grip` stops the chassis immediately.
2. Left `grip` enables the lift. Hold it while moving the left stick forward/backward to raise/lower the platform. Releasing left `grip` stops lift motion and preserves the current target height.
3. Keep the corresponding stick centered when moving an arm without intending to move the chassis or lift.

First real-robot use and recovery:

1. After starting the real bridge, release both `grip` buttons and wait for `command bridge ARMED` in the terminal.
2. Test one arm at a time with small, slow controller motions and keep the emergency stop reachable.
3. A VR or robot-feedback timeout stops chassis/lift motion and locks the bridge. After recovery, release both `grip` buttons again to synchronize and re-arm.
4. In pure simulation, `F` toggles body frames and `R` resets the robot and scene objects. Full keyboard reset is disabled in real mode; use right `A` and left `X` to return the arms gradually.

Arm safety protection:

- Arm commands are velocity- and acceleration-limited using elapsed time. Motion slows automatically near a kinematic singularity.
- IK branch jumps, unreachable targets, entry into a joint soft-limit zone, or excessive real joint tracking error hold only the affected arm.
- A hold is reported as `[HEI VR Safety] ... arm HOLD` in the terminal. Do not keep pushing the controller toward the boundary. Release that arm's `grip`, move the controller away from the boundary, and hold `grip` again to capture a new origin.
- If the physical arm moved unexpectedly, press the emergency stop and inspect joint feedback, zero calibration, and motor alarms before re-enabling it.

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

Real-robot mode loads only the complete robot URDF for IK and state
visualization. It does not load the simulation floor, table, graspable objects,
or other debug-scene elements. Its lift visualization defaults to about
`0.0286 m/s`, matching the current `18 rad/s` motor limit and `10 mm/rev` lead
screw. Override it with `--lift-speed-m-s VALUE` after changing the physical
lift parameters. Standalone simulation keeps its original `0.20 m/s` default.

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
