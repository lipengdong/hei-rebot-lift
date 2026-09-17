# HEI ReBot Lift Robot Driver

This directory is the LeRobot robot driver layer for HEI ReBot Lift. It wraps the Damiao dual arms, lift platform, four-wheel O-type omnidirectional chassis, and three cameras into LeRobot `Robot` / `RobotClient` interfaces.

Upper-level scripts are in:

```text
examples/hei_rebot_lift/
```

## Hardware

- Dual arms: left and right arms with 7 Damiao motors each. Joints 1-3 use `DM4340P`; joints 4-6 and gripper use `DM4310`.
- Chassis: four-wheel O-type omnidirectional base using four `DM4310` motors, with `x.vel`, `y.vel`, and `theta.vel` action interfaces.
- Lift: lead-screw lift platform using one `DM4310` motor. It homes to the upper limit on startup and uses target height `height.pos`.
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

`height.pos` is in **millimeters**. The motor uses `VEL` mode: the host implements
the outer position loop, converts height error into velocity, applies speed and
acceleration limits, and checks IO limits. It is not the motor's native position
mode. Height comes from homing plus motor position feedback, not joystick timing.

### Speed Units and the 1610 Lead Screw

Configuration lives in [config_hei_rebot_lift.py](config_hei_rebot_lift.py).
The deployed 1610 screw uses `10 mm/rev` lead. These conversions assume 1:1
coupling between the motor output shaft and screw; account for any added gearing.

```text
rpm = angular_speed_rad_s * 60 / (2 * pi)
linear_speed_mm_s = angular_speed_rad_s * lead_mm_per_rev / (2 * pi)
18 rad/s = 171.89 rpm = 28.65 mm/s (10 mm/rev)
200 rpm = 20.94 rad/s = 33.33 mm/s (conversion only, not a recommended setting)
```

| Parameter | Current default | Meaning |
| --- | --- | --- |
| `lift_lead_mm_per_rev` | `10.0` | Millimeters per output-shaft revolution |
| `lift_max_speed_rad_s` | `18.0` | Motor angular velocity cap in radians/second |
| `lift_max_accel_rad_s2` | `30.0` | Motor angular acceleration limit |
| `lift_position_kp_rad_s_per_mm` | `0.45` | Velocity requested per millimeter of height error |
| `lift_position_tolerance_mm` | `1.0` | Position-error deadband |

These are robot-side settings; restart the host after changing them. A motor's
no-load maximum RPM is not a guaranteed continuous loaded operating speed.
Validate load, temperature, power supply, and end-stop behavior before increasing
limits. The real VR viewer's `--lift-speed-m-s` only changes visualization; see
the [VR guide](../../../../examples/hei_rebot_lift/VR_mujoco_ik/README.md).

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

The host includes a watchdog: if no action is received within `watchdog_timeout_ms` (default: `1000 ms`), it automatically stops the chassis and lift to avoid motion after disconnection.

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

Joints 1-6 use `POS_VEL`; on connect the driver attempts to write `KP_APR`,
`ACC`, and `DEC`. The six-element tuples follow joint order 1 through 6 and are
shared by both arms. `arm_velocity_limit_rad_s` sets the velocity limit in
position/velocity commands, while `arm_kp_apr` is the motor position-loop gain,
not an IK weight or MIT-mode stiffness. The driver does not configure a complete
position PID (I/D terms are not set here). `arm_dec` must be negative for this
firmware; a failed parameter write means the requested configuration may not be
active, so inspect startup warnings before testing.

```python
right_arm_min_rad / right_arm_max_rad
left_arm_min_rad / left_arm_max_rad
```

Current values (read the configuration file as the source of truth):

```python
arm_velocity_limit_rad_s = (3.0, 3.0, 3.0, 1.8, 2.5, 2.5)
arm_kp_apr = (150.0, 200.0, 200.0, 45.0, 50.0, 50.0)
arm_acc = (2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
arm_dec = (-2.0, -2.0, -2.0, -2.0, -2.0, -2.0)
```

These joint parameters do not apply to the seventh gripper motor, which uses
`Torque_Pos` and its own `gripper_force_velocity` / `gripper_current` commands.
Higher gain/current is not automatically better; test without payload first.

## Related Directories

```text
src/lerobot/motors/damiao_u2can/   Damiao U2CAN low-level communication
examples/hei_rebot_lift/           Recording, replay, evaluation, rollout, and VR control scripts
```

## Chinese Version

- [README_zh.md](README_zh.md)
