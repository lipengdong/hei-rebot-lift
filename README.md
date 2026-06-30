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

## 📄 许可证

本项目基于 Hugging Face LeRobot 改造，保留 LeRobot 的数据集、训练、策略和机器人接口体系。请同时遵守 LeRobot 原始许可证要求。
