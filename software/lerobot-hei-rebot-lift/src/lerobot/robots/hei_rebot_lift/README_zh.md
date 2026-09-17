# HEI ReBot Lift Robot Driver

这个目录是 HEI ReBot Lift 的 LeRobot 机器人驱动层，负责把达妙双臂、升降平台、四轮 O 型全向底盘和三路相机封装成 LeRobot 的 `Robot` / `RobotClient` 接口。

上层使用脚本在：

```text
examples/hei_rebot_lift/
```

## 硬件组成

- 双臂：左右各 7 个达妙电机，1-3 关节为 `DM4340P`，4-6 关节和夹爪为 `DM4310`。
- 底盘：四轮 O 型全向移动底盘，四个轮组电机均使用 `DM4310`，动作接口为 `x.vel`、`y.vel`、`theta.vel`。
- 升降：丝杆升降平台，升降电机使用 `DM4310`，启动时回上限位归零，动作接口为目标高度 `height.pos`。
- 相机：三路 OpenCV 相机，默认 `front`、`left_wrist`、`right_wrist`。
- 通信：机器人端 host 通过 ZMQ 和电脑端 client 交互。

## 文件职责

```text
config_hei_rebot_lift.py   # 端口、电机参数、限位、底盘比例、升降参数、相机配置
hei_rebot_lift.py          # 实机驱动：达妙电机、底盘运动学、升降归零/位置控制、相机读帧
hei_rebot_lift_host.py     # 机器人端服务：接收动作、发送观测、看门狗保护
hei_rebot_lift_client.py   # 电脑端客户端：发送 action、接收 observation
__init__.py                # 对外导出类
```

## 默认端口映射

默认使用 udev 绑定后的稳定名字，不直接依赖易变化的 `/dev/ttyACM*`：

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

这些默认值在 `HeiRebotLiftConfig` 中：

```python
right_arm_port = "/dev/hei_right_arm"
left_arm_port = "/dev/hei_left_arm"
chassis_port = "/dev/hei_chassis"
lift_motor_port = "/dev/hei_lift"
lift_io_port = "/dev/hei_lift_io"
```

## 相机配置

默认三路相机：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

配置位于 `hei_rebot_lift_cameras_config()`。所有相机默认使用：

```text
640x480 @ 30 FPS
fourcc="MJPG"
```

`MJPG` 能显著降低 USB 带宽占用。多 USB 相机同时工作时，不建议使用默认 `YUYV`。

查看相机：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

查看某路相机支持的格式：

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

## 动作和观测字段

动作字段：

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

观测字段包含对应关节位置、底盘/升降状态和三路图像：

```text
front
left_wrist
right_wrist
```

## 升降逻辑

升降平台启动时默认执行 homing：

1. 向上运动直到上限位触发。
2. 将当前高度设为 `0.0 mm`。
3. 后续 `height.pos` 使用位置目标控制。

默认范围：

```text
lift_min_height_mm = -800.0
lift_max_height_mm = 0.0
```

也就是上限位为 `0`，向下为负值。

`height.pos` 的单位是**毫米**。电机底层使用 `VEL` 速度模式，由 host 在软件中
实现外层位置闭环：高度误差转换成速度，再限速、限加速度并检查 IO 限位。
这不是电机自身的位置模式。高度来自回零后电机位置反馈，不是靠摇杆时间估算。

### 速度单位与 1610 丝杆

配置文件：[config_hei_rebot_lift.py](config_hei_rebot_lift.py)。当前 1610 丝杆
导程为 `10 mm/rev`。以下换算假设电机输出轴与丝杆 1:1 连接；若增加传动比，
需要额外换算。

```text
转速 rpm = 角速度 rad/s * 60 / (2 * pi)
线速度 mm/s = 角速度 rad/s * 导程 mm/rev / (2 * pi)
18 rad/s = 171.89 rpm = 28.65 mm/s（导程 10 mm/rev）
200 rpm = 20.94 rad/s = 33.33 mm/s（仅单位换算，不是推荐设置）
```

| 参数 | 当前默认值 | 含义 |
| --- | --- | --- |
| `lift_lead_mm_per_rev` | `10.0` | 电机输出轴每转对应的毫米数 |
| `lift_max_speed_rad_s` | `18.0` | 电机角速度上限，单位 rad/s |
| `lift_max_accel_rad_s2` | `30.0` | 电机角加速度限制 |
| `lift_position_kp_rad_s_per_mm` | `0.45` | 每毫米高度误差对应的速度请求 |
| `lift_position_tolerance_mm` | `1.0` | 高度误差死区 |

这些参数在**机器人端**生效，修改后重启 host。电机空载最高转速不等于带载持续
工作转速，提高限速前要验证负载、温度、供电和限位停止行为。真机 VR 程序中的
`--lift-speed-m-s` 只改显示速度，具体限制见
[VR 说明](../../../../examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md)。

## 机器人端 host

机器人端启动：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

默认 ZMQ 端口：

```text
6555  client -> host 动作命令
6556  host -> client 观测和图像
```

host 内置看门狗：如果超过 `watchdog_timeout_ms`（默认 `1000 ms`）没有收到动作，会自动停止底盘和升降，避免断联后继续运动。

## 常调参数

底盘方向和速度：

```python
chassis_x_sign
chassis_y_sign
chassis_theta_sign
chassis_linear_speed_scale
chassis_yaw_speed_scale
chassis_max_wheel_accel_rad_s2
```

升降速度和平滑：

```python
lift_max_speed_rad_s
lift_max_accel_rad_s2
lift_position_kp_rad_s_per_mm
```

夹爪力度：

```python
gripper_force_velocity
gripper_current
```

机械臂软件限位：

关节 1-6 使用 `POS_VEL` 模式，连接时尝试写入 `KP_APR`、`ACC` 和 `DEC`。
六元素元组依次对应关节 1-6，左右臂共用。`arm_velocity_limit_rad_s` 是位置/速度
命令的速度限制，`arm_kp_apr` 是电机位置环增益，不是 IK 权重或 MIT 模式刚度。
这里并没有设置完整的位置 PID（未配置 I/D 项）。当前固件的 `arm_dec` 必须为
负数；写入失败意味着期望配置可能未生效，测试前应检查启动警告。

```python
right_arm_min_rad / right_arm_max_rad
left_arm_min_rad / left_arm_max_rad
```

当前值如下，部署时以配置文件为准：

```python
arm_velocity_limit_rad_s = (3.0, 3.0, 3.0, 1.8, 2.5, 2.5)
arm_kp_apr = (150.0, 200.0, 200.0, 45.0, 50.0, 50.0)
arm_acc = (2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
arm_dec = (-2.0, -2.0, -2.0, -2.0, -2.0, -2.0)
```

这组参数不作用于第七个夹爪电机；夹爪使用 `Torque_Pos` 和独立的
`gripper_force_velocity` / `gripper_current` 命令。增益和电流不是越大越好，
调参先空载小幅测试。

## 相关目录

```text
src/lerobot/motors/damiao_u2can/   达妙 U2CAN 底层通信
examples/hei_rebot_lift/           录制、回放、评估、推理和 VR 控制脚本
```
