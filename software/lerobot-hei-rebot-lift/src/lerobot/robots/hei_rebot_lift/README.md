# HEI ReBot Lift Robot Driver

This directory is the LeRobot robot driver layer for HEI ReBot Lift. It wraps the Damiao dual arms, lift platform, four-wheel O-type omnidirectional chassis, and three cameras into LeRobot `Robot` / `RobotClient` interfaces.

Upper-level scripts are in:

```text
examples/hei_rebot_lift/
```

## Hardware

- Dual arms: left and right arms with 7 Damiao motors each. Joints 1-3 use `DM4340`; joints 4-6 and gripper use `DM4310`.
- Chassis: four-wheel O-type omnidirectional base with `x.vel`, `y.vel`, and `theta.vel` action interfaces.
- Lift: lead-screw lift platform. It homes to the upper limit on startup and uses target height `height.pos`.
- Cameras: three OpenCV cameras: `front`, `left_wrist`, and `right_wrist`.
- Communication: robot-side host exchanges data with the computer-side client through ZMQ.

## Files

```text
config_hei_rebot_lift.py   # Ports, motor parameters, limits, chassis scaling, lift parameters, camera config
hei_rebot_lift.py          # Real hardware driver: Damiao motors, chassis kinematics, lift homing/position control, camera frames
hei_rebot_lift_host.py     # Robot-side service: receives actions, sends observations, watchdog protection
hei_rebot_lift_client.py   # Computer-side client: sends actions and receives observations
__init__.py                # Public exports
```

## Default Device Mapping

Stable udev device names are used by default instead of unstable `/dev/ttyACM*` names:

```text
/dev/hei_right_arm   Right arm U2CAN
/dev/hei_left_arm    Left arm U2CAN
/dev/hei_chassis     Chassis U2CAN
/dev/hei_lift        Lift motor U2CAN
/dev/hei_lift_io     Lift limit-switch serial port
```

Default values in `HeiRebotLiftConfig`:

```python
right_arm_port = "/dev/hei_right_arm"
left_arm_port = "/dev/hei_left_arm"
chassis_port = "/dev/hei_chassis"
lift_motor_port = "/dev/hei_lift"
lift_io_port = "/dev/hei_lift_io"
```

## Camera Configuration

Default cameras:

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

Configured in `hei_rebot_lift_cameras_config()`. All cameras default to:

```text
640x480 @ 30 FPS
fourcc="MJPG"
```

`MJPG` significantly reduces USB bandwidth usage. `YUYV` is not recommended when multiple USB cameras run at the same time.

Find cameras:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

List supported formats:

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

## Action and Observation Keys

Action keys:

```text
right_joint_1.pos ... right_joint_6.pos
right_gripper.pos
left_joint_1.pos ... left_joint_6.pos
left_gripper.pos
x.vel
y.vel
theta.vel
height.pos
```

Observation keys include joint positions, chassis/lift states, and three camera images:

```text
front
left_wrist
right_wrist
```

## Lift Logic

The lift performs homing on startup by default:

1. Move upward until the upper limit switch is triggered.
2. Set the current height to `0.0 mm`.
3. Use `height.pos` as the target position afterward.

Default range:

```text
lift_min_height_mm = -800.0
lift_max_height_mm = 0.0
```

The upper limit is `0`, and downward positions are negative.

## Robot-Side Host

Start on the robot side:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

Default ZMQ ports:

```text
6555  client -> host action commands
6556  host -> client observations and images
```

The host includes a watchdog: if no action is received within `watchdog_timeout_ms`, it automatically stops the chassis and lift to avoid motion after disconnection.

## Common Tuning Parameters

Chassis direction and speed:

```python
chassis_x_sign
chassis_y_sign
chassis_theta_sign
chassis_linear_speed_scale
chassis_yaw_speed_scale
chassis_max_wheel_accel_rad_s2
```

Lift speed and smoothing:

```python
lift_max_speed_rad_s
lift_max_accel_rad_s2
lift_position_kp_rad_s_per_mm
```

Gripper force:

```python
gripper_force_velocity
gripper_current
```

Arm software limits:

```python
right_arm_min_rad / right_arm_max_rad
left_arm_min_rad / left_arm_max_rad
```

## Related Directories

```text
src/lerobot/motors/damiao_u2can/   Damiao U2CAN low-level communication
examples/hei_rebot_lift/           Recording, replay, evaluation, rollout, and VR control scripts
```

## Chinese Version

- [README_zh.md](README_zh.md)
