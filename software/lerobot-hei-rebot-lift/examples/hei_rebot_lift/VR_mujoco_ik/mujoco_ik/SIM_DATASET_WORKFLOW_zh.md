# MuJoCo 数据采集、训练与推理

[English](SIM_DATASET_WORKFLOW.md) | [中文](SIM_DATASET_WORKFLOW_zh.md)

这套流程使用两个完全独立的进程和 Conda 环境。MuJoCo 只负责仿真、IK、三路相机渲染和动作执行；LeRobot 只负责数据集、训练与策略推理。两边通过 ZMQ 传输同步的观测和动作，不会连接真实机器人。

## 1. 架构

| 进程 | Conda 环境 | 入口 | 职责 |
| --- | --- | --- | --- |
| VR 示教仿真 | `hei-rebot-vr` | `run_hei_robot_vr_dataset_sim.sh` | 接收 VR，运行 MuJoCo，发布观测和示教动作 |
| 键盘示教仿真 | `hei-rebot-vr` | `run_hei_robot_keyboard_dataset_sim.sh` | 接收键盘输入，运行 MuJoCo，发布观测和示教动作 |
| VR 数据采集 | `lerobot5` | `run_hei_robot_mujoco_record.sh` | 接收 VR 仿真数据并写入 LeRobotDataset |
| 键盘数据采集 | `lerobot5` | `run_hei_robot_keyboard_record.sh` | 接收键盘仿真数据并写入 LeRobotDataset |
| 策略仿真 | `hei-rebot-vr` | `run_hei_robot_policy_sim.sh` | 运行 MuJoCo，接收策略动作 |
| 策略推理 | `lerobot5` | `run_hei_robot_mujoco_rollout.sh` | 加载模型、计算动作并发回仿真 |

默认使用：

- 观测端口：`6565`
- 命令端口：`6566`
- 同一台电脑运行时：`--sim-ip 127.0.0.1`

不要把 LeRobot 训练依赖安装进 `hei-rebot-vr`。两个环境分别按现有 VR 部署教程和 LeRobot 部署教程安装即可。

## 2. 录制 VR 仿真数据

先启动 Telegrip，并在头显中打开控制页面。换位置、换朝向或发现手柄方向不一致时，长按 **Meta Quest Button 3 秒**重新校准头显原点。

终端一启动 VR 示教仿真：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_dataset_sim.sh --publish-fps 30
```

终端二启动数据采集：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_mujoco_record.sh \
  --repo-id HGM/hei_rebot_lift_mujoco \
  --root datasets/hei_rebot_lift_mujoco \
  --num-episodes 10 \
  --episode-time-sec 30 \
  --fps 30 \
  --task "Pick up the red cube with the right gripper and place it in the center of the table."
```

采集端快捷键：

| 按键 | 功能 |
| --- | --- |
| 右方向键 | 提前结束并保存当前 episode |
| 左方向键 | 丢弃当前 episode 并重新录制 |
| `Esc` | 停止录制并整理数据集 |

仿真端和采集端的 FPS 应保持一致。仿真端始终运行高频控制，只按 `--publish-fps` 发布同步样本；采集端不会启动 MuJoCo。

继续追加数据：

```bash
./run_hei_robot_mujoco_record.sh \
  --repo-id HGM/hei_rebot_lift_mujoco \
  --root datasets/hei_rebot_lift_mujoco \
  --resume --num-episodes 10 --fps 30
```

如果仿真和采集不在同一台电脑，在采集命令中把 `--sim-ip` 改成运行 MuJoCo 的电脑 IP，并放行 TCP `6565/6566`。

## 3. 录制键盘仿真数据

键盘采集不需要启动 Telegrip。原有的 `run_hei_robot_keyboard_sim.sh` 仅用于练习控制，不发布数据；采集时必须使用下面的 `run_hei_robot_keyboard_dataset_sim.sh`。

终端一启动键盘示教仿真：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_dataset_sim.sh --publish-fps 30
```

终端二启动键盘数据采集：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_record.sh \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --num-episodes 10 \
  --episode-time-sec 30 \
  --fps 30 \
  --task "Pick up the red cube with the right gripper and place it in the center of the table."
```

键盘控制：

| 按键 | 功能 |
| --- | --- |
| `1` | 底盘模式：`W/S` 前后、`A/D` 横移、`Q/E` 旋转 |
| `2` | 升降模式：`I/K` 上升/下降 |
| `3` / `4` | 左臂/右臂模式 |
| `W/S A/D R/F` | 机械臂 TCP 的 X/Y/Z 平移 |
| `U/J I/K O/L` | 机械臂 TCP 的 Rx/Ry/Rz 旋转 |
| `Z/X` | 当前机械臂夹爪打开/闭合 |
| `5/6` | 左臂/右臂复位 |
| `Shift` | 精细低速控制 |
| `Space` | 停止并保持 |
| `Backspace` | 整机和场景复位 |

采集程序仍使用右方向键提前保存、左方向键丢弃重录、`Esc` 停止。由于两个进程都监听键盘，按 `Esc` 时键盘仿真也会退出，这是正常的安全行为。

## 4. 检查数据

先进入软件仓库根目录：

```bash
cd software/lerobot-hei-rebot-lift
```

使用 Rerun 可视化键盘仿真数据集中的完整 episode：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  lerobot-dataset-viz \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --episode-index 0
```

`--episode-index 0` 表示第 1 集。`--root` 必须指向实际包含 `meta/info.json` 的本地数据集目录；找不到该文件时，LeRobot 会尝试从 Hugging Face 下载数据。

检查某一帧的字段并导出三路相机图像：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  python -u examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/inspect_mujoco_dataset.py \
  --repo-id HGM/hei_rebot_lift_mujoco \
  --root datasets/hei_rebot_lift_mujoco \
  --episode-index 0 --frame-index 0
```

输出图像位于 `outputs/mujoco_dataset_sample/`。正式录制前先确认：

- `observation.state` 和 `action` 都是 18 维；
- 图像键为 `front`、`left_wrist`、`right_wrist`；
- 夹爪闭合为 `0 rad`，打开为 `-4.5 rad`；
- `height.pos` 范围为 `-800~0 mm`；
- `theta.vel` 为 `[-1, 1]` 归一化值。

检查程序还会输出 `moving action fields` 和 `constant action fields`。开始训练前，
任务实际使用的机械臂、夹爪、底盘或升降字段必须出现在变化列表中。如果 18 个
动作字段全部不变，策略只能学会保持初始姿态；如果任务写“右臂”但只有左臂字段
变化，也应重新录制或修正任务描述，不能靠增加训练步数解决。

## 5. 训练 ACT

训练只使用 `lerobot5`。下面示例训练**键盘仿真数据集**：

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_keyboard_mujoco \
  --dataset.root=datasets/hei_rebot_lift_keyboard_mujoco \
  --policy.type=act \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --output_dir=outputs/train/act_hei_rebot_lift_keyboard_mujoco \
  --job_name=act_hei_rebot_lift_keyboard_mujoco \
  --batch_size=8 \
  --steps=100000 \
  --save_freq=10000 \
  --log_freq=200 \
  --num_workers=4 \
  --wandb.enable=false
```

首次联调可将 `--steps` 改为 `1000`。

训练 VR 仿真数据时，将上述 `repo_id`、`root`、`output_dir` 和 `job_name` 中的
`keyboard_mujoco` 改为 `mujoco`。不要把键盘数据集名称和 VR 数据集名称混用；
检查点的 `train_config.json` 会记录它实际使用的数据集。

## 6. 在 MuJoCo 中推理

先关闭 VR 示教仿真。终端一启动策略仿真：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_policy_sim.sh --publish-fps 30
```

终端二在 `lerobot5` 中启动推理：

```bash
./run_hei_robot_mujoco_rollout.sh \
  --model-id outputs/train/act_hei_rebot_lift_keyboard_mujoco \
  --task "这里必须填写录制数据时使用的相同任务描述" \
  --duration-sec 30 --fps 30 --device cuda
```

推理程序只负责模型计算；MuJoCo 窗口、机器人状态和动作执行都由策略仿真进程负责。
推理日志中的 `requested=hold` 表示模型当前只请求保持；如果持续 3 秒从未请求运动，
程序会提示检查动作范围和任务/机械臂是否匹配。推理超时或退出时，仿真服务端会
保持机械臂和升降位置，并把底盘速度置零。

## 7. 数据兼容边界

仿真与真机使用相同的 18 维字段、单位、顺序和三相机名称，因此策略结构可以复用。但稳定抓取仍是确定性吸附逻辑，视觉、摩擦、负载与真实成像存在差异。建议先用仿真验证任务链路，再用真实示教数据微调。
