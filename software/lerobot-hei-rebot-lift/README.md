# HEI ReBot Lift

HEI ReBot Lift 是基于 LeRobot 改造的一套双臂升降轮式机器人项目。它把达妙双臂、丝杆升降平台、四轮 O 型全向底盘、三路相机、VR 遥操作、MuJoCo/Pinocchio 逆解、LeRobot 数据录制、ACT/SmolVLA 训练和实机推理串成一条完整链路。

项目目标是让这台自定义机器人可以像 LeRobot 官方机器人一样完成：遥操作采集数据、保存 LeRobotDataset、训练模仿学习或 VLA 策略，并把策略部署回真实机器人。

## 硬件组成

```text
双臂：左右各 7 个达妙电机，关节 1-3 使用 DM4340P，关节 4-6 和夹爪使用 DM4310；底盘四轮电机和升降电机均使用 DM4310
底盘：四轮 O 型全向移动底盘
升降：丝杆升降平台，启动后上限位 homing，把上限位作为 height.pos = 0
相机：front、left_wrist、right_wrist 三路 OpenCV 相机
通信：机器人端 host 和电脑端 client 通过 ZMQ 通信
遥操作：VR 头显 + 手柄，Telegrip 获取 VR 数据，MuJoCo + Pinocchio/CasADi 做 IK
```

## 目录说明

```text
src/lerobot/robots/hei_rebot_lift/        HEI ReBot Lift 机器人驱动
src/lerobot/motors/damiao_u2can/          达妙 U2CAN 电机通信封装
examples/hei_rebot_lift/                  遥操作、录制、回放、评估、推理脚本
examples/hei_rebot_lift/VR_mujoco_ik/     VR + MuJoCo + Pinocchio IK 控制链路
```

更细的说明可以看：

```text
src/lerobot/robots/hei_rebot_lift/README.md
examples/hei_rebot_lift/README.md
examples/hei_rebot_lift/VR_mujoco_ik/README.md
```

## 推荐部署结构

建议机器人端和训练/遥操作电脑都使用同一份代码。机器人端主要运行 `hei-rebot-lift-host`，电脑端运行 VR、MuJoCo IK、录制、训练和推理脚本。

```text
机器人端：连接达妙驱动板、升降限位开关、底盘、相机，启动 host
电脑端：启动 Telegrip、MuJoCo IK、record/rollout/evaluate
默认机器人 IP：192.168.31.127
```

## 1. 创建 LeRobot 环境

如果你已经有 `lerobot5` 环境，可以跳过创建步骤，直接安装本项目依赖。

```bash
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
pip install -e .
```

常用启动命令里建议加上：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 ...
```

`--no-capture-output` 可以让日志实时输出，录制数据时更容易看清当前阶段。

## 2. 创建 VR/MuJoCo IK 环境

VR 和 MuJoCo IK 使用单独的统一环境 `hei-rebot-vr`。正逆解依赖 `pinocchio/casadi/eigenpy/coal-python` 比较特殊，建议按这里的 `environment.yml` 安装，不要手动混装。

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

如果环境已经存在：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env update -n hei-rebot-vr -f environment.yml --prune
```

验证 Pinocchio + CasADi：

```bash
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

看到 `casadi binding ok` 就说明 IK 依赖正常。

## 3. 端口和设备映射

机器人默认使用 udev 绑定后的稳定端口名：

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

相机默认配置：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

三路相机建议使用 `MJPG`，可以降低 USB 带宽占用，避免多相机同时采集时卡顿。

查找相机：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

查看某个相机支持的格式：

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

## 4. 启动机器人端 host

在机器人端执行：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

启动后 host 会完成这些事情：

```text
1. 连接左右达妙机械臂、底盘、升降电机、限位开关和相机
2. 升降平台先向上 homing，触发上限位后设为 height.pos = 0
3. 监听电脑端动作命令，默认端口 6555
4. 发布机器人观测和图像，默认端口 6556
5. 如果动作命令超时，看门狗会停止底盘和升降
```

如果短时间看到：

```text
No command available
```

通常表示电脑端还没有开始发动作，录制或推理启动后应减少。

## 5. 启动 VR + MuJoCo IK

打开一个终端启动 Telegrip：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

VR 头显浏览器访问：

```text
https://电脑IP:8443
```

再打开一个终端启动 MuJoCo IK：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

默认数据链路：

```text
VR 头显/手柄 -> Telegrip -> tcp://*:5567
MuJoCo IK 订阅 5567，计算双臂关节目标
MuJoCo IK -> tcp://*:6558 发布 LeRobot action
record.py / teleoperate.py 订阅 6558 并发送给机器人
```

## 6. 遥操作测试

正式录数据前，先跑遥操作测试，确认双臂、底盘、升降方向和速度都正确。

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py   --remote-ip 192.168.31.127
```

控制逻辑：

```text
双臂：VR 手柄位姿经过 MuJoCo/Pinocchio IK 生成关节目标
底盘：右手握把按下时，右摇杆控制 x/y/theta；松开握把立刻停止
升降：左手握把按下时，左摇杆 Y 轴控制升降方向；松开握把立刻停止
升降动作：最终发送 height.pos 目标高度，不直接发送速度
```

## 7. 录制数据

新建数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --repo-id HGM/hei_rebot_lift_task1   --remote-ip 192.168.31.127   --num-episodes 5   --episode-time-sec 120   --reset-time-sec 30   --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

默认只保存到本地，不上传 Hugging Face Hub。需要上传时显式加：

```bash
--push-to-hub
```

继续录制已有数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --repo-id HGM/hei_rebot_lift_task1   --root ~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1   --resume   --num-episodes 5
```

注意：如果相机数量或名字变了，比如从两相机改成三相机，不要 resume 到旧数据集，应该新建一个 `repo-id`。

## 8. 查看和清洗数据

可视化某一集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-dataset-viz   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0
```

删除坏 episode：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-edit-dataset   --repo_id HGM/hei_rebot_lift_task1   --new_repo_id HGM/hei_rebot_lift_task1   --operation.type delete_episodes   --operation.episode_indices "[57]"
```

删除后 episode 会重新编号，原来的第 58 集会变成新的第 57 集。

## 9. 训练 ACT

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=act   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/act_hei_rebot_lift_task1   --job_name=act_hei_rebot_lift_task1   --batch_size=8   --steps=10000   --save_freq=10000   --log_freq=200   --num_workers=4   --wandb.enable=false
```

如果数据没有上传到 Hub，训练会优先在本地缓存里找：

```text
~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1
```

## 10. 训练 SmolVLA

SmolVLA 是当前比较适合继续尝试的 VLA 路线。三相机数据在推理时会自动映射：

```text
front       -> camera1
left_wrist  -> camera2
right_wrist -> camera3
```

示例命令：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=smolvla   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/smolvla_hei_rebot_lift_task1   --job_name=smolvla_hei_rebot_lift_task1   --batch_size=1   --steps=1000   --save_freq=1000   --log_freq=50   --num_workers=2   --wandb.enable=false
```

离线运行前，需要先把模型权重下载到 Hugging Face 缓存。离线时可设置：

```bash
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

## 11. 实机推理

ACT 推理：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 30   --inference sync
```

SmolVLA 推理：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 60   --fps 10   --inference rtc
```

`sync` 是同步推理，适合先跑通。`rtc` 更适合推理较慢的 VLA 模型，会尽量保持控制节奏。

## 12. 回放和评估

回放某一集动作：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/replay.py   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0   --display-data
```

ACT 评估并保存 eval 数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/evaluate.py   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --dataset-id HGM/hei_rebot_lift_task1_eval   --num-episodes 5   --episode-time-sec 60
```

## 常见问题

### GitHub 或 Hugging Face Token

不要把 Token 写进代码，也不要发到聊天窗口。推送 GitHub 时如果需要认证，把 Token 粘贴到终端的 Password 输入位置即可。

### Speech Dispatcher 报错

如果看到：

```text
Failed to connect to Speech Dispatcher
```

这是语音播报服务问题，通常不影响机器人控制和数据保存。

### 相机卡顿或读帧超时

优先检查：

```text
1. 是否使用 MJPG
2. 多个相机是否挤在同一个 USB Hub
3. 是否需要降低 FPS 或分辨率
4. /dev/video* 是否和配置一致
```

### 录制 episode 为空

`record.py` 只有收到 MuJoCo/VR 动作并成功获取机器人观测后才会保存帧。若反复出现空 episode：

```text
1. Telegrip 是否已经进入 VR
2. MuJoCo IK 是否收到 VR 手柄数据
3. MuJoCo IK 是否持续向 6558 发布动作
4. record.py 日志里的 saved_frames 是否增长
5. 机器人端 host 是否正常连接并返回观测
```

### ACT 推理 KeyError: observation.images.*

通常是训练时的相机名字和当前机器人配置不一致。比如旧数据是 `front/wrist`，当前配置是 `front/left_wrist/right_wrist`。这种情况建议重新录制三相机数据并重新训练。

## 基于 LeRobot

本项目基于 Hugging Face LeRobot 改造，保留 LeRobot 的数据集、训练、策略和机器人接口体系。原项目地址：

```text
https://github.com/huggingface/lerobot
```

使用本项目时请同时遵守 LeRobot 原始许可证要求。
