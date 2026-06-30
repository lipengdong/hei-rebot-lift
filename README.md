<h1 align="center">HEI ReBot Lift</h1>

<p align="center">
  <img src="media/Repository-Header-Image.jpg" alt="HEI ReBot Lift" width="100%">
</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/中文-README-d32f2f?style=for-the-badge" alt="中文 README"></a>
  <a href="README_en.md"><img src="https://img.shields.io/badge/English-README-2f6fd3?style=for-the-badge" alt="English README"></a>
</p>

## 🚀 项目简介
**HEI ReBot Lift** 是一个面向 **具身人工智能学习、复现和实机验证的双臂升降轮式机器人项目**，目标是**降低真实机器人学习系统的搭建门槛**。 **“真正可复现的开源”**：不仅开源代码，也整理 **硬件资料、接线方式、部署流程、VR 遥操作链路、数据录制方法、ACT/VLA 训练和真实机器人推理流程**，让学习者可以从硬件组装一路走到策略上机。机器人硬件由双臂、升降平台、四轮 O 型全向底盘和三路相机组成；软件基于LeRobot，覆盖MuJoCo/Pinocchio 逆解、LeRobotDataset、模仿学习和 VLA 策略部署。


<p align="center">
  <b>🚀 Dual-Arm Mobile Manipulation</b> · <b>📖 Open Hardware + Software Stack</b> · <b>🤖 LeRobot Ready</b>
</p>

<p align="center">
  <a href="#快速部署">🚀 快速部署</a> ·
  <a href="#硬件组成">🦾 硬件组成</a> ·
  <a href="#启动流程">🎮 VR 遥操作</a> ·
  <a href="#录制数据">📷 数据录制</a> ·
  <a href="#训练-act">🧠 ACT 训练</a> ·
  <a href="#训练-smolvla">✨ VLA 训练</a>
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

后续所有运行命令默认先进入这个目录：

```bash
cd software/lerobot-hei-rebot-lift
```

## 🖼️ 项目展示

<p align="center">
  <img src="media/7.jpg" alt="HEI ReBot Lift robot" width="72%">
</p>

## 🗺️ 路线图与最新进展

我们会持续完善 HEI ReBot Lift 的硬件资料、软件接口、数据采集流程和主流具身智能算法适配。下面是当前项目进展和对应文档入口。

| 模块 | 状态 | 当前进展 | 相关 DOC |
| --- | --- | --- | --- |
| 机械本体 | ✅ 已完成首版 | 双臂 + 升降平台 + 四轮 O 型全向底盘整体方案已跑通 | [Hardware](hardware/README.md) |
| 达妙电机驱动 | ✅ 已完成首版 | 已封装 `damiao_u2can`，支持双臂、夹爪、底盘和升降电机控制 | [Damiao U2CAN](software/lerobot-hei-rebot-lift/src/lerobot/motors/damiao_u2can/) |
| 升降平台 | ✅ 已完成首版 | 支持启动上限位 homing，并使用 `height.pos` 位置目标控制 | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) |
| 全向底盘 | ✅ 已完成首版 | 支持 `x.vel`、`y.vel`、`theta.vel` 控制，并加入基础加减速平滑 | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) |
| 三相机视觉 | ✅ 已完成首版 | 支持 `front`、`left_wrist`、`right_wrist` 三路 OpenCV 相机，默认 MJPG | [Robot Driver](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) |
| VR + MuJoCo IK | ✅ 已完成首版 | Telegrip + MuJoCo + Pinocchio/CasADi 已接入真实机器人控制链路 | [VR MuJoCo IK](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) |
| LeRobot 集成 | ✅ 已完成首版 | 已实现 `hei_rebot_lift` robot/client/host，支持 teleoperate、record、replay、evaluate、rollout | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| 数据采集 | ✅ 已完成首版 | 支持 LeRobotDataset 录制、继续录制、可视化和坏 episode 清理 | [Record Guide](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| ACT 训练与推理 | ✅ 已跑通 | 支持 ACT 训练和真实机器人 rollout | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| SmolVLA / VLA | ✅ 初步跑通 | 支持 SmolVLA 训练和真实机器人推理入口 | [Examples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| 硬件开源资料 | 🚧 整理中 | 已建立 `hardware/`、`media/`、`docs/`、`community/` 项目结构 | [Hardware](hardware/README.md) |
| 社区与复现 | 🚧 持续进行 | 已提供微信交流群、邮箱和 GitHub 项目入口 | [Community](community/README.md) |
| 其他主流 VLA 部署复现 | ⏳ 即将进行 | 计划继续复现和测试更多主流 VLA 策略在 HEI ReBot Lift 上的训练、推理和实机部署流程 | 未完成 |

## 🦾 硬件组成

```text
双臂：左右各 7 个达妙电机，关节 1-3 使用 DM4340，关节 4-6 和夹爪使用 DM4310
底盘：四轮 O 型全向移动底盘
升降：丝杆升降平台，启动后上限位 homing，把上限位作为 height.pos = 0
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

创建 LeRobot 环境：

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
pip install -e .
```

创建 VR/MuJoCo IK 环境：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

验证 Pinocchio + CasADi：

```bash
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

## 🔌 设备映射

默认使用 udev 绑定后的稳定端口：

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

默认相机：

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

机器人端启动 host：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

电脑端启动 Telegrip：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

VR 头显访问：

```text
https://电脑IP:8443
```

电脑端启动 MuJoCo IK：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

遥操作测试：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py   --remote-ip 192.168.31.127
```

## 📷 录制数据

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --repo-id HGM/hei_rebot_lift_task1   --remote-ip 192.168.31.127   --num-episodes 5   --episode-time-sec 120   --reset-time-sec 30   --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

默认只保存本地，不上传 Hugging Face Hub。需要上传时显式加 `--push-to-hub`。

## 🧠 训练 ACT

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=act   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/act_hei_rebot_lift_task1   --job_name=act_hei_rebot_lift_task1   --batch_size=8   --steps=10000   --save_freq=10000   --log_freq=200   --num_workers=4   --wandb.enable=false
```

## ✨ 训练 SmolVLA

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=smolvla   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/smolvla_hei_rebot_lift_task1   --job_name=smolvla_hei_rebot_lift_task1   --batch_size=1   --steps=1000   --save_freq=1000   --log_freq=50   --num_workers=2   --wandb.enable=false
```

## 🤖 实机推理

ACT 推理：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 30   --inference sync
```

SmolVLA 推理：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 60   --fps 10   --inference rtc
```

## 📖 更多文档

```text
software/lerobot-hei-rebot-lift/README.md
software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md
software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md
software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md
```

## 🙏 References & Acknowledgments

HEI ReBot Lift 的开发受益于多个优秀开源项目和社区工作的支持，特别感谢：

- **LeRobot**：提供了统一的机器人接口、LeRobotDataset 数据格式、训练工具链以及 ACT/SmolVLA 等策略实现，为真实机器人数据采集、训练和部署提供了完整基础。
- **reBot / reBot-DevArm**：提供了开放机械臂硬件、模型资料和具身智能开源实践参考，也启发了本项目在硬件资料、部署文档和复现流程上的整理方式。

本项目基于上述开源生态进行定制和扩展，目标是进一步降低双臂升降轮式机器人在学习、复现、数据采集和真实机器人策略部署中的门槛。

## 📄 许可证

本项目基于 Hugging Face LeRobot 改造，保留 LeRobot 的数据集、训练、策略和机器人接口体系。请同时遵守 LeRobot 原始许可证要求。
