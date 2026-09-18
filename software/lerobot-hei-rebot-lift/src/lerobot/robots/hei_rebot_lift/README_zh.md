# HEI ReBot Lift Robot Driver

[English](README.md) | [中文](README_zh.md)

这个目录是 HEI ReBot Lift 的 LeRobot 机器人驱动层，负责把达妙双臂、升降平台、四轮 O 型全向底盘和三路相机封装成 LeRobot 的 `Robot` / `RobotClient` 接口。

上层使用脚本在：

```text
examples/hei_rebot_lift/
```

下方命令从**软件根目录** `software/lerobot-hei-rebot-lift/` 执行，不是在本驱动
目录执行。硬件命令在 Jetson 的 `lerobot5` 运行，VR/IK 环境在电脑端。
先按 [项目部署教程](../../../../../../README_zh.md#-快速部署) 安装。默认参数以
配置代码为准，文档中的数值仅是当前配置说明。

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

### 在哪里修改相机 ID

在**机器人 Jetson** 上，先停止 host 和查找相机程序，然后编辑
[config_hei_rebot_lift.py](config_hei_rebot_lift.py) 中的
`hei_rebot_lift_cameras_config()`。从软件目录出发，文件路径是
`src/lerobot/robots/hei_rebot_lift/config_hei_rebot_lift.py`。

查看 `outputs/captured_images` 中保存的画面，确认哪路是头部、左腕、右腕，
再将各路的 `index_or_path` 改成实际设备路径。下面的编号只是示例，不是固定 ID：

```python
def hei_rebot_lift_cameras_config() -> dict[str, CameraConfig]:
    return {
        "front": OpenCVCameraConfig(index_or_path="/dev/video0", fps=30, width=640, height=480, fourcc="MJPG"),
        "left_wrist": OpenCVCameraConfig(index_or_path="/dev/video2", fps=30, width=640, height=480, fourcc="MJPG"),
        "right_wrist": OpenCVCameraConfig(index_or_path="/dev/video4", fps=30, width=640, height=480, fourcc="MJPG"),
    }
```

保留 `front`、`left_wrist`、`right_wrist` 名称，数据集、策略和客户端依赖这些
字段。只改 ID 时保留其他参数，不需要改 `camera_opencv.py` 或 VR YAML。
保存后重启 `hei-rebot-lift-host`。电脑端与机器人端分开部署时，客户端配置也
应保持相同的相机名称和图像尺寸；实际 USB 设备路径由机器人 host 打开，
不是由电脑客户端打开。重新插拔可能改变编号，需重新检查，或使用经过验证的
`/dev/v4l/by-id/...` 等稳定设备路径。

端口绑定与升降/底盘独立控制见
[示例硬件教程](../../../../examples/hei_rebot_lift/README_zh.md#1-硬件检查)。
串口调试时不能同时启动 host。机械臂零位工具启动即写零位，不是只读检查。

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
chassis_max_wheel_speed_rad_s
chassis_max_wheel_accel_rad_s2
```

这些是机器人端参数，修改后重启 host。轮速上限可能覆盖机体输入比例变化的
效果。ID 1 右前、2 右后、3 左后、4 左前；机体速度字段是驱动命令单位，
不是标定后的 m/s，轮速上限单位是 rad/s。

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

硬件说明中 1-3 关节为 DM4340P，但当前通信实现实际选择
`DM_Motor_Type.DM4340` 枚举。本次不修改代码；部署时应核对具体电机版本的
协议范围与固件兼容性，不能把文档型号名称当作兼容性验证。

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
