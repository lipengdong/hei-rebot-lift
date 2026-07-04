# HEI ReBot Lift Examples

这个目录是 HEI ReBot Lift 的实机使用入口，覆盖从硬件检查、VR/MuJoCo 遥操作、数据录制、数据清洗、训练到策略推理的完整流程。

机器人驱动代码在：

```text
src/lerobot/robots/hei_rebot_lift/
```

VR/MuJoCo IK 子系统在：

```text
examples/hei_rebot_lift/VR_mujoco_ik/
```

## 脚本说明

```text
Arm_Zero_Status_Test.py   达妙机械臂写零位和状态检查
teleoperate.py            只遥操作，不录数据
record.py                 VR 遥操作录制数据集
replay.py                 回放数据集中的某一集动作
evaluate.py               ACT 策略实机评估并记录 eval 数据
rollout.py                ACT / SmolVLA 等策略实机推理，不录数据
vr_control.py             MuJoCo/VR ZMQ 数据转 LeRobot action
VR_mujoco_ik/             Telegrip + MuJoCo + Pinocchio IK 一体化 VR 控制链路
```

## 推荐终端布局

实机录制通常开 4 个终端：

```text
终端 1：机器人端 host
终端 2：Telegrip VR 页面
终端 3：MuJoCo IK
终端 4：record.py 录制数据
```

默认机器人 IP：

```text
192.168.31.127
```

如果 IP 改了，在脚本里用 `--remote-ip 新IP` 覆盖。

## 最短完整流程

第一次部署时按这个顺序走：

1. 机器人端确认 udev 端口、相机和达妙电机可用。
2. 启动 `hei-rebot-lift-host`，等待升降 homing 完成。
3. 电脑端启动 `VR_mujoco_ik/run_telegrip.sh`。
4. VR 头显访问 `https://电脑IP:8443` 并进入 VR。
5. 电脑端启动 `VR_mujoco_ik/run_mujoco_ik.sh`。
6. 先跑 `teleoperate.py` 确认双臂、底盘、升降方向正确。
7. 跑 `record.py` 录制数据。
8. 用 `lerobot-dataset-viz` 检查数据，必要时用 `lerobot-edit-dataset` 删除坏 episode。
9. 训练 ACT 或 SmolVLA。
10. 用 `rollout.py` 上机推理。

## 1. 硬件检查

查相机：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

查某个相机支持格式：

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

三路相机默认配置：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

相机默认使用 `MJPG`，这样多个 USB 相机同时跑时更稳。

达妙机械臂写零位和状态检查：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/Arm_Zero_Status_Test.py \
  --port /dev/hei_right_arm
```

临时调试真实端口：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/Arm_Zero_Status_Test.py \
  --port /dev/ttyACM1
```

## 2. 启动机器人端 host

机器人端执行：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

host 启动后会：

1. 连接左右臂、底盘、升降和相机。
2. 升降平台执行上限位 homing，把上限位作为 `height.pos = 0`。
3. 监听动作命令端口 `6555`。
4. 通过端口 `6556` 发送观测和图像。

如果机器人端一直打印：

```text
No command available
```

说明电脑端 client 还没发命令。短时间出现正常，开始录制/推理后应减少。

## 3. 启动 VR + MuJoCo IK

先部署统一环境：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

启动 Telegrip：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

VR 头显访问：

```text
https://电脑IP:8443
```

启动 MuJoCo IK：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

默认链路：

```text
Telegrip -> MuJoCo IK: tcp://localhost:5567
MuJoCo IK -> record.py: tcp://*:6558
```

正逆解依赖 `pinocchio/casadi/eigenpy/coal-python` 比较特殊，统一环境里已经用 `conda-forge` 固定。不要额外 `pip install pin`。

## 4. 遥操作测试

只测试 VR 控制，不保存数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py
```

控制逻辑：

- 双臂由 VR 手柄位姿经 MuJoCo IK 生成关节目标。
- 右手握把按下时，右摇杆控制底盘；松开握把底盘停止。
- 左手握把按下时，左摇杆 Y 轴控制升降方向；松开握把升降停止。
- 升降最终发送的是目标高度 `height.pos`，不是速度积分。

## 5. 录制数据

新建数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py \
  --repo-id HGM/hei_rebot_lift_task1 \
  --num-episodes 5 \
  --episode-time-sec 120 \
  --reset-time-sec 30 \
  --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

默认只保存本地，不上传 Hugging Face Hub。需要上传时显式加：

```bash
--push-to-hub
```

继续录制已有数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py \
  --repo-id HGM/hei_rebot_lift_task1 \
  --root ~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1 \
  --resume \
  --num-episodes 5
```

注意：如果相机数量或名字变了，比如从 `front/wrist` 改成 `front/left_wrist/right_wrist`，不要 resume 到旧数据集，应该新建 repo-id。

## 6. 查看和清洗数据

可视化某一集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-dataset-viz \
  --repo-id HGM/hei_rebot_lift_task1 \
  --episode-index 0
```

删除坏 episode，原地生成新数据并自动备份旧目录为 `_old`：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-edit-dataset \
  --repo_id HGM/hei_rebot_lift_task1 \
  --new_repo_id HGM/hei_rebot_lift_task1 \
  --operation.type delete_episodes \
  --operation.episode_indices "[57]"
```

删除后会重新编号，原来的第 58 集会变成新的第 57 集。

## 7. 训练 ACT

示例命令：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --policy.type=act \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --output_dir=outputs/train/act_hei_rebot_lift_task1 \
  --job_name=act_hei_rebot_lift_task1 \
  --batch_size=8 \
  --steps=10000 \
  --save_freq=10000 \
  --log_freq=200 \
  --num_workers=4 \
  --wandb.enable=false
```

如果本地数据没有上传 Hub，但训练去联网找数据，通常需要指定本地 root 或确保数据在默认缓存目录：

```text
~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1
```

## 8. 训练 SmolVLA

SmolVLA 是当前更适合继续尝试的 VLA 路线。三相机数据会在 rollout 时自动映射：

```text
front       -> camera1
left_wrist  -> camera2
right_wrist -> camera3
```

训练命令根据机器显存调整 batch size。低显存优先从小 batch 和短 steps 开始。

示例命令：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --policy.type=smolvla \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --output_dir=outputs/train/smolvla_hei_rebot_lift_task1 \
  --job_name=smolvla_hei_rebot_lift_task1 \
  --batch_size=1 \
  --steps=1000 \
  --save_freq=1000 \
  --log_freq=50 \
  --num_workers=2 \
  --wandb.enable=false
```

第一次运行可能会下载视觉语言模型权重。离线训练前，需要先把依赖模型下载到 Hugging Face 缓存。

离线运行时可设置：

```bash
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

## 9. 策略推理

ACT 或 SmolVLA 都可以用 `rollout.py`。

ACT 示例：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py \
  --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model \
  --task "Pick up the yellow block from the floor and put it on the table in front" \
  --duration-sec 30 \
  --inference sync
```

SmolVLA 示例：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py \
  --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model \
  --task "Pick up the yellow block from the floor and put it on the table in front" \
  --duration-sec 60 \
  --fps 10 \
  --inference rtc
```

`sync` 是同步推理，适合先跑通。`rtc` 更适合推理较慢的 VLA 模型，会尽量保持控制更平滑。

## 10. 回放和评估

回放某一集数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/replay.py \
  --repo-id HGM/hei_rebot_lift_task1 \
  --episode-index 0 \
  --display-data
```

ACT 评估并记录 eval 数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/evaluate.py \
  --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model \
  --dataset-id HGM/hei_rebot_lift_task1_eval \
  --num-episodes 5 \
  --episode-time-sec 60
```

## 常见问题

### Speech Dispatcher 报错

如果看到：

```text
Failed to connect to Speech Dispatcher
```

这是 `log_say()` 语音播报服务问题，不影响数据保存和机器人控制。

### 相机卡顿或读帧超时

优先检查：

- 是否使用 `fourcc="MJPG"`。
- 多相机是否挤在同一个 USB Hub。
- 是否需要降低 FPS 或分辨率。

### 录制 episode 为空

`record.py` 只有收到 MuJoCo/VR 动作后才保存帧。若反复出现空 episode：

1. 检查 Telegrip 是否进入 VR。
2. 检查 MuJoCo IK 是否收到 VR 数据。
3. 检查 MuJoCo IK 是否持续向 `6558` 发布动作。
4. 检查 `record.py` 是否显示 `saved_frames` 增长。

### ACT 推理 KeyError: observation.images.*

通常是模型训练时的相机名字和当前机器人配置不一致。旧两相机数据可能是 `front/wrist`，当前三相机是 `front/left_wrist/right_wrist`。这种情况建议重新录三相机数据并训练。
