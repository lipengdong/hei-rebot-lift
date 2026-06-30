# HEI ReBot Lift Hardware

HEI ReBot Lift 的硬件部分包含 **达妙双臂、丝杆升降平台、四轮 O 型全向底盘、三路相机、U2CAN 驱动板、电源系统和限位开关**。本目录用于整理可复现硬件资料，包括 BOM、接线、端口绑定、装配说明和安全注意事项。

机械臂部分参考了 Seeed reBot-DevArm 的开源思路：不仅记录电机和结构，也尽量整理到可采购、可装配、可标定、可调试的程度。reBot-DevArm 项目强调开放硬件蓝图、BOM、软件与算法生态，并提供 Damiao/Robostride 版本作为具身智能机械臂参考；HEI ReBot Lift 在此基础上扩展为 **双臂 + 升降 + 全向底盘** 的移动操作平台。

## 📁 计划目录

```text
hardware/
├── README.md
├── BOM.md                         # 总 BOM，含采购链接、数量、备注
├── wiring.md                      # 接线说明：U2CAN、电源、限位、相机
├── power.md                       # 电源方案、电压电流、保险、急停
├── udev_rules/
│   └── 99-hei-rebot-lift.rules    # 稳定端口名绑定规则
├── mechanical/
│   ├── arm/                       # 双臂结构资料
│   ├── lift/                      # 升降平台结构资料
│   ├── chassis/                   # 四轮 O 型全向底盘资料
│   └── camera_mounts/             # 相机支架资料
├── electronics/
│   ├── damiao_u2can.md            # 达妙 U2CAN 驱动板说明
│   ├── limit_switch.md            # 升降限位开关说明
│   └── camera_usb.md              # USB 相机与带宽说明
└── calibration/
    ├── arm_zero.md                # 机械臂零位标定
    ├── lift_homing.md             # 升降 homing 标定
    └── chassis_direction.md       # 底盘方向和轮速标定
```

## 🦾 机械臂硬件

HEI ReBot Lift 使用双臂结构，左右两侧各 6 个关节 + 1 个夹爪电机。机械臂设计思路和硬件资料整理方式参考 reBot-DevArm，目标是让学习者可以根据开源资料完成采购、装配、标定和二次开发。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机械臂数量 | 2 | 左右双臂 |
| 每臂自由度 | 6 DOF + 1 Gripper | 6 个关节 + 夹爪 |
| 关节 1-3 | DM4340 | 主要承担肩部和大负载关节 |
| 关节 4-6 | DM4310 | 主要承担腕部关节 |
| 夹爪 | DM4310 | 夹爪开合控制 |
| 通信 | U2CAN | 左右臂分别使用独立驱动板/端口 |
| 控制方式 | 位置控制为主 | 上层 LeRobot action 使用 `*.pos` |

### 机械臂端口

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
```

### 机械臂动作字段

```text
right_joint_1.pos ... right_joint_6.pos
right_gripper.pos
left_joint_1.pos ... left_joint_6.pos
left_gripper.pos
```

### 需要继续补充的机械臂资料

- 左右臂 BOM：电机、结构件、螺丝、轴承、线材、连接件
- 机械臂 STEP/STL/装配图
- 电机 CAN ID 表
- 关节方向、零位姿态和软件限位
- 夹爪指尖材料和夹取力调节说明
- 机械臂零位标定流程
- 机械臂常见故障和排查方法

## ⬆️ 升降平台

升降平台用于扩展双臂工作高度。当前软件侧已经支持启动后自动回上限位，并将上限位定义为 `height.pos = 0`。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机构 | 丝杆升降平台 | 具体结构资料待整理 |
| 电机通信 | U2CAN | 默认端口 `/dev/hei_lift` |
| 限位输入 | 串口/IO | 默认端口 `/dev/hei_lift_io` |
| 位置范围 | -800 mm 到 0 mm | 上限位为 0，向下为负值 |
| 控制方式 | 位置目标 | 上层 action 使用 `height.pos` |

### 待补充资料

- 升降平台 BOM
- 丝杆、导轨、滑块和安装结构图
- 上限位开关接线图
- homing 安全注意事项
- 电机参数、速度和加速度建议

## 🛞 四轮 O 型全向底盘

底盘用于移动操作任务中的平移和转向。当前软件侧支持 `x.vel`、`y.vel`、`theta.vel` 三个速度接口，并加入基础加减速平滑，减少启动和停止时的晃动。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 底盘形式 | 四轮 O 型全向 | 支持前后、左右、旋转 |
| 通信 | U2CAN | 默认端口 `/dev/hei_chassis` |
| 控制接口 | 速度控制 | `x.vel`、`y.vel`、`theta.vel` |
| 平滑方式 | 加减速限制 | 降低机器人晃动 |

### 待补充资料

- 底盘 BOM
- 轮子安装方向和轮距参数
- 电机 ID 与轮子位置映射
- 底盘运动学参数
- 地面测试和方向标定方法

## 📷 三路相机

默认三路 OpenCV 相机：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

建议使用 `MJPG` 格式，降低 USB 带宽占用，提高多相机同时采集稳定性。

### 待补充资料

- 相机型号和采购链接
- 前视相机安装位置
- 左右腕部相机支架
- USB Hub/带宽建议
- 相机标定和视角示例图

## 🔌 端口绑定

项目默认使用稳定设备名，避免 `/dev/ttyACM*` 或 `/dev/video*` 顺序变化导致程序启动失败。

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

待补充：`udev_rules/99-hei-rebot-lift.rules`。

## ⚡ 电源与安全

硬件复现时建议优先整理并确认电源系统，尤其是双臂、底盘和升降平台同时运动时的峰值电流。

### 建议补充

- 总电源电压和额定电流
- 各驱动板供电分配
- 急停按钮接线
- 保险丝或断路器规格
- 地线和屏蔽线处理
- 上电、下电、homing 前检查清单

## ✅ 启动前硬件检查清单

- [ ] 左右臂机械零位正确
- [ ] 升降平台上限位开关可靠触发
- [ ] 底盘四轮方向和 ID 映射正确
- [ ] 所有 U2CAN 端口能被系统识别
- [ ] 三路相机能稳定输出 MJPG 图像
- [ ] 电源电压、电流和急停正常
- [ ] 机器人周围留有安全空间

## 🙏 References

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm): open robotic arm hardware, BOM, software ecosystem, and reproducible embodied AI hardware documentation.
- [LeRobot](https://github.com/huggingface/lerobot): robot interface, dataset format, training and policy deployment ecosystem.
