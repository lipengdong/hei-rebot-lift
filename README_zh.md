<h1 align="center">HEI ReBot Lift</h1>

<p align="center">
  <img src="media/Repository-Header-Image.jpg" alt="HEI ReBot Lift" width="100%">
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> <b>|</b>
  <a href="README_zh.md"><b>中文</b></a> <b>|</b>
  <a href="README_Fr.md"><b>français</b></a> <b>|</b>
  <a href="README_es.md"><b>Español</b></a>
</p>

<p align="center">
  <a href="https://github.com/lipengdong/hei-rebot-lift/stargazers">
    <img src="https://img.shields.io/github/stars/lipengdong/hei-rebot-lift?style=social" alt="GitHub stars">
  </a>
</p>

## 🚀 项目简介
**HEI ReBot Lift** 是一个面向 **具身人工智能学习、复现和实机验证的双臂升降轮式机器人项目**，目标是**降低真实机器人学习系统的搭建门槛**。 **“真正可复现的开源”**：不仅开源代码，也整理 **硬件资料、接线方式、部署流程、VR 遥操作链路、数据录制方法、ACT/VLA 训练和真实机器人推理流程**，让学习者可以从硬件组装一路走到策略上机。机器人硬件由双臂、升降平台、四轮 O 型全向底盘和三路相机组成；软件基于LeRobot，覆盖MuJoCo/Pinocchio 逆解、LeRobotDataset、模仿学习和 VLA 策略部署。


<p align="center">
  <b>🚀 Dual-Arm Mobile Manipulation</b> · <b>📖 Open Hardware + Software Stack</b> · <b>🤖 LeRobot Ready</b>
</p>

<p align="center">
  <a href="#-快速部署">🚀 快速部署</a> ·
  <a href="#-硬件组成">🦾 硬件组成</a> ·
  <a href="#-启动流程">🎮 VR 遥操作</a> ·
  <a href="#-录制数据">📷 数据录制</a> ·
  <a href="#-训练-act">🧠 ACT 训练</a> ·
  <a href="#-训练-smolvla">✨ VLA 训练</a>
</p>

## ✨ 功能亮点

<div align="center">

<table>
  <thead>
    <tr>
      <th align="center">图标</th>
      <th align="center">能力</th>
      <th align="center">说明</th>
    </tr>
  </thead>
  <tbody>
    <tr><td align="center">🦾</td><td align="center">双臂操作</td><td align="center">达妙双臂 + 夹爪，支持实机遥操作、录制和策略推理</td></tr>
    <tr><td align="center">⬆️</td><td align="center">升降平台</td><td align="center">启动自动 homing，上限位作为 <code>height.pos = 0</code>，支持位置控制</td></tr>
    <tr><td align="center">⭕</td><td align="center">全向底盘</td><td align="center">四轮 O 型全向移动底盘，支持 <code>x/y/theta</code> 速度控制</td></tr>
    <tr><td align="center">🎮</td><td align="center">VR 遥操作</td><td align="center">Telegrip 获取 VR 手柄数据，MuJoCo + Pinocchio/CasADi 做 IK</td></tr>
    <tr><td align="center">📷</td><td align="center">三相机数据</td><td align="center"><code>front</code>、<code>left_wrist</code>、<code>right_wrist</code> 三路视觉输入</td></tr>
    <tr><td align="center">🧠</td><td align="center">模仿学习/VLA</td><td align="center">支持 LeRobotDataset、ACT、SmolVLA 和真实机器人 rollout</td></tr>
  </tbody>
</table>

<img src="media/hei-robot-lift-play.gif" alt="HEI ReBot Lift demo" width="60%">

</div>

## 🤝 获取机器人 / 加入社区

如果你也想复现一台 **HEI ReBot Lift**，可以根据本项目逐步整理的硬件资料、BOM、接线说明和软件部署文档自行采购零件并完成组装。我们也欢迎对双臂移动操作、VR 遥操作、LeRobot 数据采集、ACT/VLA 训练和真实机器人部署感兴趣的朋友一起交流。

如果你希望**更快获得自己的机器人**，或者希望围绕硬件复现、教学实验、数据采集、算法验证、应用落地进行合作，也可以联系我们。

<p align="center">
  <b>微信社区 / 合作咨询：</b><code>hgm159951</code> &nbsp;&nbsp;|&nbsp;&nbsp;
  <b>邮箱：</b><a href="mailto:hgm159951@163.com">hgm159951@163.com</a>
</p>

欢迎复现、交流、提 issue，也欢迎把你的改进方案和实机测试结果反馈回来。

## 📁 项目结构

```text
hei-rebot-lift/
├── README.md
├── README_zh.md
├── README_Fr.md
├── README_es.md
├── LICENSE
├── community/                    # 社区资料、后续协作记录
├── hardware/                     # 硬件 BOM、接线、端口绑定、机械资料
├── media/                        # 图片、视频、README 展示素材
├── docs/                         # 项目部署和使用文档
└── software/
    └── lerobot-hei-rebot-lift/   # 基于 LeRobot 的完整可运行代码
```

程序主体在：

```text
software/lerobot-hei-rebot-lift/
```

快速部署从项目根目录开始；后续各章节的命令块均在新终端、项目根目录执行，
每段自行进入对应目录。软件目录为：

```bash
cd software/lerobot-hei-rebot-lift
```

## 🖼️ 项目展示

<p align="center">
  <img src="media/7.jpg" alt="HEI ReBot Lift robot" width="72%">
</p>

## ⭐ Star History

<p align="center">
  <a href="https://www.star-history.com/?repos=lipengdong%2Fhei-rebot-lift&type=date&legend=top-left">
    <img src="media/star-history-2026731.png" alt="HEI ReBot Lift Star History" width="72%">
  </a>
</p>

## 🗺️ 路线图与最新进展

我们会持续完善 HEI ReBot Lift 的硬件资料、软件接口、数据采集流程和主流具身智能算法适配。下面是当前项目进展和对应文档入口。

| 模块 | 状态 | 当前进展 | 相关 DOC |
| --- | --- | --- | --- |
| 机械本体 | ✅ 已完成首版 | 双臂 + 升降平台 + 四轮 O 型全向底盘整体方案已跑通 | [Hardware](hardware/README.md) |
| 完整机器人 URDF | ✅ 已完成 | 已建立底盘、轮组、升降、双臂、平行夹爪与 TCP 坐标系的完整模型，用于仿真和真机 IK | [URDF 模型](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/) |
| MuJoCo 仿真测试 | ✅ 已完成 | 已测试 VR 控制双臂、夹爪、升降与底盘，支持轮组动画、工作空间投影及稳定抓取模式的取放演示 | [仿真教程](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md) |
| 达妙电机驱动 | ✅ 已完成首版 | 已封装 `damiao_u2can`，支持双臂、夹爪、底盘和升降电机控制 | [Damiao U2CAN](software/lerobot-hei-rebot-lift/src/lerobot/motors/damiao_u2can/) |
| 升降平台 | ✅ 已完成首版 | 支持启动上限位 homing，并使用 `height.pos` 位置目标控制 | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) · [升降独立控制](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md#单独调试升降) |
| 全向底盘 | ✅ 已完成首版 | 支持 `x.vel`、`y.vel`、`theta.vel` 控制，并加入基础加减速平滑 | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) · [底盘独立控制](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md#单独调试底盘) |
| 三相机视觉 | ✅ 已完成首版 | 支持 `front`、`left_wrist`、`right_wrist` 三路 OpenCV 相机，默认 MJPG | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) |
| VR + MuJoCo IK | ✅ 已完成首版 | Telegrip + MuJoCo + Pinocchio/CasADi 已接入真实机器人控制链路 | [VR MuJoCo IK](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) |
| LeRobot 集成 | ✅ 已完成首版 | 已实现 `hei_rebot_lift` robot/client/host，支持 teleoperate、record、replay、evaluate、rollout | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| 数据采集 | ✅ 已完成首版 | 支持 LeRobotDataset 录制、继续录制、可视化和坏 episode 清理 | [Record Guide](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| ACT 训练与推理 | ✅ 已跑通 | 支持 ACT 训练和真实机器人 rollout | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| SmolVLA / VLA | ✅ 初步跑通 | 支持 SmolVLA 训练和真实机器人推理入口 | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| 硬件开源资料 | ✅ 已完成 | 已提供整机 BOM、整机 STEP 总装、打印件 STL、金属件清单及 STEP/DWG 加工图纸 | [硬件说明](hardware/README_zh.md) |
| 社区与复现 | 🚧 持续进行 | 已提供微信交流群、邮箱和 GitHub 项目入口 | [Community](community/README.md) |
| 其他主流 VLA 部署复现 | ⏳ 即将进行 | 计划继续复现和测试更多主流 VLA 策略在 HEI ReBot Lift 上的训练、推理和实机部署流程 | 未完成 |

## 🦾 硬件组成

当前硬件资料包已经包含整机总 BOM、整机 STEP 总装模型、3D 打印件、金属 / CNC / 钣金加工文件，方便从采购、加工到装配逐步复现。

| 资料 | 文件 / 目录 | 说明 |
| --- | --- | --- |
| 硬件说明 | [hardware/README_zh.md](hardware/README_zh.md) | 硬件目录索引、推荐复现顺序和上电前检查清单 |
| 整机 BOM | [hardware/HEI_ReBot_Lift_BOM.md](hardware/HEI_ReBot_Lift_BOM.md) / [xlsx](hardware/HEI_ReBot_Lift_BOM.xlsx) | 整机外购件、加工件和装配准备清单 |
| 整机总装模型 | [hardware/Hei_robot_lift.STEP](hardware/Hei_robot_lift.STEP) | 用于查看整机结构、空间布局和装配关系 |
| 3D 打印件 | [hardware/3D_Printed_Parts/](hardware/3D_Printed_Parts/) | 外壳、支架、升降、底盘、相机等相关 STL 文件 |
| 金属件清单 | [hardware/Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](hardware/Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) | 金属 / CNC / 钣金件清单 |
| 金属 CAD 文件 | [hardware/Metal_Parts/step/](hardware/Metal_Parts/step/) / [hardware/Metal_Parts/dwg/](hardware/Metal_Parts/dwg/) | 用于加工沟通的 STEP 和 DWG 文件 |

```text
双臂：左右各 7 个达妙电机，关节 1-3 使用 DM4340P，关节 4-6 和夹爪使用 DM4310
底盘：四轮 O 型全向移动底盘，轮毂/轮组电机使用 DM4310
升降：丝杆升降平台，升降电机使用 DM4310，启动后上限位 homing，把上限位作为 height.pos = 0
相机：front、left_wrist、right_wrist 三路 OpenCV 相机
通信：机器人端 host 和电脑端 client 通过 ZMQ 通信
遥操作：VR 头显 + 手柄，Telegrip 获取 VR 数据，MuJoCo + Pinocchio/CasADi 做 IK
```

## 🧩 软件目录

```text
software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/        机器人驱动
software/lerobot-hei-rebot-lift/src/lerobot/motors/damiao_u2can/          达妙 U2CAN 通信
software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/                  录制、回放、评估、推理脚本
software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/     VR + MuJoCo + Pinocchio IK
```

## ⚡ 快速部署

机器人端与电脑端都需要本项目代码，但安装内容和运行职责不同。
**以下各小节从对应机器的项目根目录开始，不要跨机器连续执行命令。**

| 部署位置 | 环境 | 安装用途 |
| --- | --- | --- |
| 机器人端 Jetson | `lerobot5` | 硬件驱动、串口绑定、机器人 host；无需安装 VR/IK 环境 |
| 自己的电脑：控制/训练端 | `lerobot5` | 遥操作客户端、数据录制/编辑、可视化、训练与策略推理 |
| 自己的电脑：VR/仿真端 | `hei-rebot-vr` | Telegrip、MuJoCo、Pinocchio/CasADi 正逆解 |

### 1. 机器人端 Jetson 安装

**只在机器人端执行。** 使用硬件相关安装项，不安装电脑端的数据可视化和训练
额外依赖。此安装仍包含项目的基础依赖，并不是完全不含 PyTorch 的独立驱动包。

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
python -m pip install -e ".[hardware,pyzmq-dep]"
python -c "import serial, zmq, cv2; print('robot dependencies ok')"
```

若 Jetson 已有可用的 `lerobot5` 环境，跳过创建步骤，激活后安装即可。Jetson 的
PyTorch/torchvision 如遇平台或版本不兼容，需要根据实际 JetPack 和本项目版本
约束处理；不要直接照搬电脑端 CUDA 安装包，也不要用 `--no-deps` 跳过所有依赖。

安装后按下面的“设备映射”完成端口绑定，检查限位与相机，再按“启动流程”运行
`hei-rebot-lift-host`。机器人端不用创建 `hei-rebot-vr`。

### 2. 自己的电脑：控制/录制/训练安装

**只在自己的电脑执行。** 这个环境运行 `teleoperate.py`、`record.py`、训练、
回放和策略推理，不负责直接打开机器人上的电机串口。

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
python -m pip install -e ".[core_scripts,training,pyzmq-dep]"
python -m pip show pyzmq rerun-sdk pynput datasets accelerate
```

该安装包含数据集录制/编辑、Rerun 可视化、键盘输入、ZMQ 和通用策略训练依赖。
SmolVLA 专用依赖在后面的训练章节另行安装。已有 `lerobot5` 时跳过创建步骤。

### 3. 自己的电脑：VR/MuJoCo IK 安装

仍在自己的电脑执行，**另开终端，从项目根目录开始**。Telegrip 与 MuJoCo IK
共用 `hei-rebot-vr`，不要混入上面的 `lerobot5`；正逆解库按 `environment.yml`
里的 conda-forge 版本安装，不要额外 `pip install pin`。

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

已有该环境时，用 `conda env update -n hei-rebot-vr -f environment.yml --prune`
替代创建命令。启动脚本会自动激活它。先做纯仿真验证，再连接真实机器人；
详细操作见 [VR 部署教程](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md)。

## 🔌 设备映射

默认使用 udev 绑定后的稳定端口：

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

### 1. 串口自动识别与绑定向导

在**机器人端 Jetson**运行
[Port_Binding_Wizard.py](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/debug/Port_Binding_Wizard.py)，
它会扫描 `ttyACM*` / `ttyUSB*`，根据响应的电机 ID 和有效限位 IO 帧识别设备，
确认后生成稳定端口映射。程序不会使能电机、写零位或发送运动命令。

**运行前准备：**

1. 停止 `hei-rebot-lift-host` 和所有电机、串口调试程序，确保串口未被占用。
2. 为区分相同的双臂驱动板，断电并支撑好机械臂，临时断开**右臂 ID 4-7**，只保留右臂 ID 1-3；左臂保持 ID 1-7 完整连接。
3. 确认底盘 ID 1-4、升降 ID 1、升降限位 IO 接线正确，再给四块 U2CAN、IO 板及待识别电机上电。
4. 扫描及安装规则期间不要更换 USB 插口。

从项目根目录执行交互向导：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  python -u examples/hei_rebot_lift/debug/Port_Binding_Wizard.py
```

按提示查看扫描结果、确认左右臂/底盘/升降/IO 映射，再确认是否安装系统规则。
默认写入 `examples/hei_rebot_lift/rules/99-nx-robot.rules`，并备份已有文件；
安装到 `/etc/udev/rules.d/` 时需要 `sudo`，向导会重新加载规则并检查软链接。
已有雷达与 IMU 规则会保留，本次不识别这两项设备。

**绑定后检查：**

```bash
ls -l /dev/hei_right_arm /dev/hei_left_arm /dev/hei_chassis /dev/hei_lift /dev/hei_lift_io
```

若软链接未生效，保持 USB 插口不变，重新插拔对应 USB 设备并检查。
验证完成后，断电恢复右臂 ID 4-7 接线，再上电进行下面的独立硬件测试。规则按 USB 物理位置
绑定，后续应保持驱动板连接原插口；更换插口或 USB 集线器后需重新绑定。

若提示设备缺失、识别有歧义、串口忙或 IO 帧无效，先检查上电、USB/CAN 接线、
电机 ID、串口占用及 IO 波特率，不要在未确认时强行接受映射。
权限不足时检查用户是否具有串口访问权限（通常为 `dialout` 组）。
首次部署使用交互模式；`--yes --install` 仅适用于接线已验证且扫描无歧义的重复绑定。

### 2. 绑定后：机械臂零位与独立硬件测试

**以下全部在机器人端 Jetson 执行，不需要 VR 或电脑客户端。** 每次只运行一个
调试程序，保持 host 和其他串口程序关闭；每个命令块从项目根目录的新终端开始。
键盘调试建议先 `conda activate lerobot5` 再直接运行 Python，需要交互终端；
SSH 连接时分配 TTY（如 `ssh -t 用户名@机器人IP`）。各程序使用固定位置刷新的
状态表，便于观察，不需要滚动查找日志。准备好物理急停，软件停止键不能替代急停。

#### 2.1 按设计零位摆放机械臂，再写入零位

**警告：`Arm_Zero_Status_Test.py` 一启动就会失能并对该臂 ID 1-7 全部写零位，
没有确认步骤，也没有只读模式。不要在任意姿态下启动，不要把它作为日常查看
状态的工具。** 电机失能后机械臂可能因重力下落，先支撑好双臂并清空周围空间。

按装配设计与 [完整 URDF 模型](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/)
的关节零位定义，将待标定机械臂摆到正确的机械零位；它不是 VR 程序的默认工作
姿态。夹爪物理零位约定为闭合（`0 rad`），不要强压夹爪。程序无法判断你摆放的
姿态是否正确；不确定设计零位时，先核对装配资料，不要尝试写入。

<p align="center">
  <a href="media/arm_zero.png"><img src="media/arm_zero.png" alt="双臂设计机械零位姿态" width="70%"></a>
  <br>
  <em>双臂设计机械零位姿态参考。写零位前逐一核对关节与装配设计；此姿态不是 VR 默认工作姿态。</em>
</p>

右臂写零位：

```bash
cd software/lerobot-hei-rebot-lift
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Arm_Zero_Status_Test.py \
  --port /dev/hei_right_arm
```

右臂确认后按 `Ctrl+C` 退出，再摆好左臂并执行：

```bash
cd software/lerobot-hei-rebot-lift
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Arm_Zero_Status_Test.py \
  --port /dev/hei_left_arm
```

写入后程序保持电机失能，刷新 `POS/VEL/TORQUE/ERROR`。确认 7 个电机接线及反馈
正常，再检查零位附近的 `POS`；不能仅凭表格显示 `0` 判断电机在线或标定成功。
`ERROR` 是驱动反馈状态码，需按对应电机协议解释，不要把所有非零值都当成故障。
标定完成后退出程序；零位只应在装配/维修后需要重新标定时写入。

#### 2.2 底盘独立测试：方向、档位与四轮反馈

先架起并稳固底盘，让轮子离地，确认周围没有线缆或人员。此程序只连接底盘，
不初始化双臂、升降和相机；**四轮按底盘运动学联动，不是单个轮子点动**。

```bash
cd software/lerobot-hei-rebot-lift
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Chassis_Status_Test.py \
  --port /dev/hei_chassis
```

| 按键 | 功能 |
| --- | --- |
| `1 / 2 / 3` | 低 / 中 / 高档，首次测试使用 `1` 低档 |
| `W / S` | 前进 / 后退 |
| `A / D` | 左移 / 右移 |
| `Q / E` | 左转 / 右转 |
| `Space` | 软件发送四轮零速 |
| `X` 或 `Ctrl+C` | 退出并停止底盘 |

按住或重复方向键维持运动；默认 `0.65 s` 未收到新的方向按键会清除运动请求。
依次短按测试各方向，观察请求/反馈底盘速度、每轮目标和反馈角速度、位置、力矩
及状态码。界面底盘速度使用驱动命令单位，不应直接当作实测 `m/s`。

| 电机 ID | 轮子位置 | 面板名称 |
| --- | --- | --- |
| `1` | 右前 | `RF` |
| `2` | 右后 | `RR` |
| `3` | 左后 | `LR` |
| `4` | 左前 | `LF` |

若某轮不转、映射不符、反馈缺失或出现异常抖动，先停止并检查电机 ID、接线与
配置，不要通过加大速度掩盖问题。离地检查通过后，再在空场地低档测试实际方向。
需要单轮点动时应另加专用测试模式，现有程序没有该功能，不要用机械臂零位脚本
连接底盘来代替。

#### 2.3 升降独立测试：回零、高度与 IO 限位

**程序启动会自动向上回零。** 先确认上下限位 IO 接线正确、升降路径无障碍，
支撑好可能在失能后下落的结构；首次测试保持急停可用。控制逻辑复用正式驱动，
只连接升降电机和限位 IO。

```bash
cd software/lerobot-hei-rebot-lift
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Lift_Status_Test.py \
  --motor-port /dev/hei_lift --io-port /dev/hei_lift_io --height-step-mm 5
```

| 按键 | 功能 |
| --- | --- |
| `I / K` | 目标高度上升 / 下降，示例每次按键改变 `5 mm` |
| `Space` | 发送停止并以当前反馈高度作为保持目标 |
| `H` | 重新向上回零，只在路径安全时使用 |
| `X` 或 `Ctrl+C` | 退出，停止并失能 |

上限位回零后高度为 `0 mm`，向下为负，范围 `-800～0 mm`。先小步下降再上升，
观察当前/目标高度、误差、反馈速度、电机命令速度、IO 在线状态和上下限位。
到达已知限位时确认对应 IO 状态正确；IO 离线、两个限位同时触发或状态不符时
停止测试，先排查，不要靠反复撞限位确认接线。

**独立测试全部完成并退出调试程序后**，再进行下面的新手仿真练习与真机启动；
不要让调试程序与 host 同时占用串口。

### 3. 相机映射

默认相机（请在**机器人端**确认实际设备，不是自己电脑的相机）：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

查找相机：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

## 🎮 启动流程

### 先区分电脑 IP 与机器人 IP

以下使用你的电脑 IP `192.168.31.245`，机器人 IP 暂以 `192.168.31.127` 举例；
**机器人实际地址不同时，只替换机器人相关地址，不要替换头显访问的电脑地址。**

| 地址 | 属于谁 | 用在哪里 |
| --- | --- | --- |
| `192.168.31.245` | 自己的控制电脑，运行 Telegrip 和 MuJoCo IK | VR 头显访问 `https://192.168.31.245:8443` |
| `192.168.31.127` | 机器人 Jetson，运行 host | 电脑客户端的 `--remote-ip 192.168.31.127`；VR 相机地址 `tcp://192.168.31.127:6556` |
| `localhost` / `127.0.0.1` | 当前程序所在机器自身，不是远端机器人 | Telegrip、MuJoCo IK 与客户端都在同一电脑时，用于电脑内部 VR、动作和反馈连接 |

先完成下面的纯仿真练习，再进入真机流程。纯仿真只需电脑和头显互通；真机阶段
再确保机器人、电脑与头显处于能互相访问的同一局域网。
**每个命令块都在指定机器的新终端、项目根目录执行**；长时间运行的进程不要关闭。

### 1. 新手先练习：电脑端纯仿真（不连接真机）

<p align="center">
  <img src="media/robot-mujoco.png" alt="HEI ReBot Lift MuJoCo VR 仿真场景" width="85%">
</p>

先完成 `hei-rebot-vr` 环境安装。**这一阶段不要启动机器人 host、
`teleoperate.py`、`record.py` 或真机桥接程序**；若它们已运行，先停止。
纯仿真不需要电机、端口绑定或机器人反馈，也不会发布 `6558` 真机动作命令。

#### 1.1 电脑练习终端 A：启动 Telegrip

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

VR 头显与电脑连接同一局域网，在头显浏览器访问
`https://192.168.31.245:8443`（电脑 IP），确认自签名证书后进入 VR。

#### 1.2 电脑练习终端 B：启动完整机器人仿真

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_sim.sh
```

在**电脑上的 MuJoCo 窗口**观察机器人。场景包含双臂、平行夹爪、升降、四轮
全向底盘，以及桌子、方块和香蕉，可用于练习取放。没有真实机器人时，头显不会
收到实机相机图像，这不影响仿真练习。当前 `telegrip/config.yaml` 已设为
`vr_images.enabled: false`，练习时保持关闭即可；修改后需要重启 Telegrip。

#### 1.3 按顺序练习手柄操作

<table align="center">
  <tr>
    <td align="center"><a href="media/META-QUEST-BUTTON.jpg"><img src="media/META-QUEST-BUTTON.jpg" alt="右手柄 Meta Quest 系统按钮位置" width="200"></a><br><b>Meta Quest 系统按钮</b></td>
    <td align="center"><a href="media/META-GRIP-BUTTON.jpg"><img src="media/META-GRIP-BUTTON.jpg" alt="侧面 grip 握把按钮位置" width="200"></a><br><b>Grip：侧面握把</b></td>
    <td align="center"><a href="media/META-FRONT-TRIGGER.jpg"><img src="media/META-FRONT-TRIGGER.jpg" alt="前方 trigger 扳机位置" width="200"></a><br><b>Trigger：前扳机</b></td>
  </tr>
</table>

点击图片可查看大图。

> [!IMPORTANT]
> **控制前先校准 VR 原点：长按右手柄的 META QUEST BUTTON 约 3 秒，以当前头显位置和朝向重新居中，作为本次操作的 VR 参考原点。**
> **换了站立/坐姿位置或操作朝向，都需要重新长按约 3 秒校准。发现手柄与机械臂运动方向不一致、方向不跟手时，也要先停止控制并重新校准，不要继续强行操作。**
> 校准顺序：**松开左右两侧 `grip` → 摇杆回中 → 在新的操作位置面向期望的前方 → 长按 Meta Quest 按钮约 3 秒 → 稳定后重新按住 `grip`**，先小幅移动确认方向。

Meta Quest 按钮校准的是**头显/VR 参考坐标**；`grip` 建立的是每条臂的相对控制
原点，两者不是一回事。这也不是给机械臂电机写零位，更不会代替升降回零；
仿真和真机 VR 操作都要遵守上述校准步骤。

| 练习 | 操作与观察 |
| --- | --- |
| 单臂平移与旋转 | 按住对应侧 `grip` 建立相对控制原点，小幅移动 XYZ、旋转手柄，观察 TCP；先练一条臂，再练另一条 |
| 松开与重新抓取控制原点 | 松开 `grip` 停止跟随，换一个舒服的手柄位置再按住；机械臂不需要随手柄回到原点 |
| 夹爪取放 | 仿真夹爪默认闭合，真机启动先同步实际状态；按住 `grip` 时按 `trigger` 张开，松开 `trigger` 闭合；在物体附近闭合可练习稳定抓取，再张开放置 |
| 升降 | 左 `grip` + 左摇杆上下；松开左 `grip` 停止升降请求 |
| 底盘 | 右 `grip` + 右摇杆前后/左右；右 `B` 顺时针、左 `Y` 逆时针旋转；松开右 `grip` 停止请求 |
| 恢复初始状态 | 对应 `grip` 松开时，右 `A` / 左 `X` 缓慢复位对应臂；电脑 MuJoCo 窗口获得焦点后按 `R` 重置机器人和场景物体，仅用于纯仿真 |

练机械臂时保持摇杆回中，避免同时移动底盘或升降。到关节/工作空间边界时，
减小动作并返回可达区域，不要持续向边界外推。完整说明见
[VR 手柄教程](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md)。

#### 1.4 练熟后再进入真机

- 能分别控制左右臂平移、旋转，并熟练松开/重新按住 `grip` 建立新原点。
- 能长按 Meta Quest 按钮校准 VR 原点，知道换位置、换朝向或方向不一致时要重新校准。
- 能完成一次夹爪取放，理解松开 `grip` 后夹爪保持最后状态。
- 能控制底盘、升降方向，知道如何停止请求并保持摇杆回中。
- 能区分纯仿真与真机启动入口，并清楚急停位置和真实工作区风险。

练习结束，关闭纯仿真 MuJoCo 窗口或用 `Ctrl+C` 停止仿真程序，再按下面第 2、3
节启动真机。Telegrip 可继续使用；若练习时停用了相机，需要显示实机画面时恢复
`vr_images.enabled: true`、检查机器人相机 IP 并重启 Telegrip，不要重复启动两份。
**仿真练习通过不代表硬件安全检查通过**：稳定抓取是运动学演示，不是接触力学
验证；实机方向、零位、限位和负载仍需单独检查，仿真升降速度也可能快于实机。

### 2. 机器人端 Jetson：启动 host（终端 1）

本小节只在机器人上执行。先完成端口映射，清空工作区并确认急停可用；host
启动后升降会自动上行归零，**等待归零完成**，再继续电脑端操作。host 运行在
机器人上，不需要传入电脑 IP，也不要把它误当作电脑客户端。

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

机器人端保持这个终端运行，无需启动 Telegrip 或 MuJoCo IK。

### 3. 自己的电脑：启动控制程序

下面三个程序全部在 IP 为 `192.168.31.245` 的**自己的电脑**上运行，不是在 Jetson 上。

#### 3.1 启动 Telegrip（电脑终端 2）

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

#### 3.2 VR 头显浏览器：访问电脑页面

例如，运行 Telegrip 的电脑局域网 IP 是 `192.168.31.245`，就在 **VR 头显浏览器**
中输入：

```text
https://192.168.31.245:8443
```

头显与电脑需连接同一局域网，先启动 `run_telegrip.sh` 再访问。这里使用的是
**电脑 IP，不是机器人 IP**，且必须使用 `https`。首次访问若提示自签名证书不受
信任，请确认地址是自己的电脑后继续访问，并按页面提示进入 VR。

当前 VR 相机回传已关闭。如果需要在头显显示机器人相机，在电脑上的
`software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/telegrip/config.yaml`
设置 `vr_images.enabled: true` 和 `vr_images.endpoint: tcp://192.168.31.127:6556`，这里必须填**机器人 IP**。
更改后重启 Telegrip；客户端的 `--remote-ip` 不会自动修改这个配置。

#### 3.3 启动遥操作客户端（电脑终端 3）

`--remote-ip` 填**机器人 Jetson 的 IP**，不是本电脑的 `192.168.31.245`。
客户端提供实机反馈，并等待 MuJoCo IK 发布动作：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py --remote-ip 192.168.31.127
```

#### 3.4 启动完整模型 MuJoCo IK 真机桥接（电脑终端 4）

与 Telegrip、遥操作客户端运行在同一台电脑，默认使用电脑内部连接，不需要
把这些内部地址改为机器人 IP：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

收到新鲜实机反馈和 VR 数据后，**同时松开左右 grip**，等待终端出现
`command bridge ARMED`。`--enable-real-publish` 只是确认允许发布真机命令，
不会跳过同步检查。纯仿真用 `./run_hei_robot_vr_sim.sh`；原双臂入口仍为
`./run_mujoco_ik.sh`。手柄用法、恢复流程及升降显示限制见
[VR 使用教程](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md)。

完成后应保持 **1 个机器人端 host + 3 个电脑端程序**。切换为数据录制时，用
`record.py` 替换电脑终端 3 的 `teleoperate.py`，不要同时运行两者。

## 📷 录制数据

先停止 `teleoperate.py`，再运行 `record.py`：两者都接收动作并发布实机反馈，
**不能同时运行**。host 和 Telegrip 保持运行；反馈重连后松开两侧 grip 重新解锁。

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --repo-id HGM/hei_rebot_lift_task1   --remote-ip 192.168.31.127   --num-episodes 5   --episode-time-sec 120   --reset-time-sec 30   --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

默认只保存本地，不上传 Hugging Face Hub。需要上传时显式加 `--push-to-hub`。

## 🧠 训练 ACT

在电脑端训练，不需要运行机器人 host 或 VR 程序。数据路径以录制日志为准；
若录制使用自定义 `--root`，训练也要加 `--dataset.root=实际数据集目录`，且
repo ID 必须一致。下面的短训练用于跑通链路，不保证策略已经能可靠上机。

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=act   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/act_hei_rebot_lift_task1   --job_name=act_hei_rebot_lift_task1   --batch_size=8   --steps=10000   --save_freq=10000   --log_freq=200   --num_workers=4   --wandb.enable=false
```

## ✨ 训练 SmolVLA

先在项目根目录的新终端安装该策略的额外依赖：

```bash
cd software/lerobot-hei-rebot-lift
conda run --no-capture-output -n lerobot5 python -m pip install -e ".[smolvla]"
```

通用 `training` 安装项不包含所有 VLA 策略的专用依赖。

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=smolvla   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/smolvla_hei_rebot_lift_task1   --job_name=smolvla_hei_rebot_lift_task1   --batch_size=1   --steps=1000   --save_freq=1000   --log_freq=50   --num_workers=2   --wandb.enable=false
```

## 🤖 实机推理

保留机器人 host，但先停止 VR 真机命令发布、遥操作、录制和回放进程，
**同一时间只保留一个机器人控制源**。确认模型目录存在、相机名称与训练数据
一致，先在空工作区做短时间测试。

ACT 推理：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --remote-ip 192.168.31.127   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 30   --inference sync
```

SmolVLA 推理：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --remote-ip 192.168.31.127   --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 60   --fps 10   --inference rtc
```

## 📖 更多文档

- [文档导航](docs/README_zh.md)
- [录制、续录、训练与推理](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md)
- [机器人配置、升降单位与看门狗](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README_zh.md)
- [VR 部署、手柄教程与自检](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md)

## 🙏 References & Acknowledgments

HEI ReBot Lift 的开发受益于多个优秀开源项目和社区工作的支持，特别感谢：

- **LeRobot**：提供了统一的机器人接口、LeRobotDataset 数据格式、训练工具链以及 ACT/SmolVLA 等策略实现，为真实机器人数据采集、训练和部署提供了完整基础。
- **reBot / reBot-DevArm**：提供了开放机械臂硬件、模型资料和具身智能开源实践参考，也启发了本项目在硬件资料、部署文档和复现流程上的整理方式。

本项目基于上述开源生态进行定制和扩展，目标是进一步降低双臂升降轮式机器人在学习、复现、数据采集和真实机器人策略部署中的门槛。

## 📄 许可证

本项目基于 Hugging Face LeRobot 改造，保留 LeRobot 的数据集、训练、策略和机器人接口体系。请同时遵守 LeRobot 原始许可证要求。
