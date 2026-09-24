# HEI ReBot Lift Examples

[English](README.md) | [中文](README_zh.md)

这个目录是 HEI ReBot Lift 的实机使用入口，覆盖从硬件检查、VR/MuJoCo 遥操作、数据录制、数据清洗、训练到策略推理的完整流程。

除非另有说明，每个命令块都在新终端的 `software/lerobot-hei-rebot-lift/` 目录
执行，不是在本 examples 文件夹执行。先按 [项目部署教程](../../../../README_zh.md)
安装 LeRobot 环境。

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
debug/Arm_Zero_Status_Test.py   达妙机械臂写零位和状态检查
debug/Lift_Status_Test.py       升降归零、I/K 位置控制、限位 IO 和电机状态
debug/Chassis_Status_Test.py    底盘键盘控制、速度档位和四轮状态
debug/Port_Binding_Wizard.py    串口自动识别、故障诊断和 udev 端口绑定向导
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
终端 3：完整模型 MuJoCo IK + 真机桥接
终端 4：record.py 录制数据
```

机器人 IP 示例（不同脚本默认值可能不同，建议始终传入 `--remote-ip`）：

```text
192.168.31.127
```

如果 IP 改了，可以在 `teleoperate.py`、`record.py`、`replay.py`、`evaluate.py` 或 `rollout.py` 后传入 `--remote-ip 新IP`。程序会在连接前打印最终生效的 `host=...`；不传该参数时才使用脚本中的默认地址。

## 最短完整流程

先完成 [纯仿真练习](VR_mujoco_ik/README_zh.md#2a-先用完整模型测试-vr-仿真)，练习时不运行 host/客户端/真机桥接。之后实机按这个顺序走：

1. 机器人端确认 udev 端口、相机和达妙电机可用。
2. 启动 `hei-rebot-lift-host`，等待升降 homing 完成。
3. 电脑端启动 `VR_mujoco_ik/run_telegrip.sh`。
4. VR 头显访问 `https://电脑IP:8443` 并进入 VR。
5. 先跑 `teleoperate.py` 提供实机反馈，它会等待 VR 动作。
6. 启动 `VR_mujoco_ik/run_hei_robot_vr_real.sh --enable-real-publish`，同时松开两侧 grip，等待 `command bridge ARMED`，再缓慢检查各模块方向。
7. 停止 `teleoperate.py` 后跑 `record.py`；反馈恢复后松开两侧 grip 重新解锁。
8. 用 `lerobot-dataset-viz` 检查数据，必要时用 `lerobot-edit-dataset` 删除坏 episode。
9. 训练 ACT 或 SmolVLA。
10. 停止 VR 真机发布与录制，保留 host，再用 `rollout.py` 上机推理。

## 1. 硬件检查

查相机：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  lerobot-find-cameras opencv --opencv-fourcc MJPG --opencv-width 640 --opencv-height 480 --opencv-fps 30
```

指定 `opencv` 可跳过无关的 RealSense 检测；查找工具会使用 MJPG 同时取图，避免
三路相机以默认 YUYV 工作时占满 USB 带宽。照片保存在 `outputs/captured_images/`。

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

查找后，在**机器人 Jetson** 上编辑
[config_hei_rebot_lift.py](../../src/lerobot/robots/hei_rebot_lift/config_hei_rebot_lift.py)
的 `hei_rebot_lift_cameras_config()`，将三路 `index_or_path` 分别改为头部、
左腕、右腕的实际设备路径。相机名称和其他参数保持不变，停止查找程序后重启
host。完整示例见 [相机 ID 修改说明](../../src/lerobot/robots/hei_rebot_lift/README_zh.md#在哪里修改相机-id)。

### 串口绑定向导

在**机器人 Jetson** 上执行，先停止 host 和所有串口调试程序。改接线前断电并
支撑机械臂；暂时断开右臂 ID 4-7，只留 ID 1-3，左臂保留 ID 1-7，底盘 ID 1-4，
升降 ID 1。扫描时给四块 U2CAN、电机及限位 IO 上电。

运行向导前设置串口读写权限：

```bash
sudo chmod 666 /dev/ttyACM*
sudo chmod 666 /dev/ttyUSB*
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  python -u examples/hei_rebot_lift/debug/Port_Binding_Wizard.py
```

向导根据电机响应 ID 和有效限位 IO 帧识别设备，提示缺失、占用或歧义，确认后写入
`examples/hei_rebot_lift/rules/99-nx-robot.rules`；可通过 sudo 安装到
`/etc/udev/rules.d/`，保留已有雷达/IMU 规则。不会使能、写零位或发送运动命令。
规则绑定 USB 物理拓扑，插口不要变；`--yes --install` 仅用于接线已验证且
识别结果无歧义的重复绑定。

```bash
ls -l /dev/hei_right_arm /dev/hei_left_arm /dev/hei_chassis /dev/hei_lift /dev/hei_lift_io
```

确认后断电，接回右臂 ID 4-7，再上电。详细排查与测试注意事项见
[主页设备映射教程](../../../../README_zh.md#-设备映射)。

### 机械臂设计零位标定

> [!WARNING]
> **零位脚本启动即失能并对 ID 1-7 全部写零位，没有确认，也不是只读状态工具。**
> 先支撑机械臂，将关节摆到设计机械零位，夹爪闭合到物理零位（`0 rad`），
> 不要强压。不能把任意 VR 工作姿态当零位；运行前确认七个电机全部连接。

<p align="center">
  <a href="../../../../media/arm_zero.png"><img src="../../../../media/arm_zero.png" alt="双臂设计机械零位姿态" width="70%"></a>
  <br>
  <em>双臂设计机械零位姿态参考。写零位前逐一核对关节与装配设计；此姿态不是 VR 默认工作姿态。</em>
</p>

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Arm_Zero_Status_Test.py \
  --port /dev/hei_right_arm
```

`Ctrl+C` 退出后，将左臂摆好，再用 `--port /dev/hei_left_arm` 单独运行。
表格显示最近的 POS/VEL/TORQUE/状态缓存；显示零不能证明电机在线或标定成功。
这是装配/维修标定流程，不是每次启动都执行。

### 单独调试升降

仅在机器人端执行，停止 host 和其他串口程序。**启动会自动上行回零，先验证
上下限位并清空升降路径。** 键盘工具使用交互终端，SSH 需 TTY（如 `ssh -t`）。
脚本复用正式驱动的 homing、反馈高度控制和限位逻辑。

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Lift_Status_Test.py \
  --motor-port /dev/hei_lift --io-port /dev/hei_lift_io --height-step-mm 2
```

`I/K` 每次提高/降低目标 2 mm（本例与程序默认一致），需要更细可用
`--height-step-mm 1`。`Space` 停止并保持
反馈高度，`H` 再次上行回零，`X` 或 `Ctrl+C` 退出并失能。检查
`-800..0 mm` 高度、IO 新鲜度、上下限位和电机状态。IO 离线或限位状态异常时
停止排查；软件停止键不能代替急停。

### 单独调试底盘

先稳固架起四个轮子，清空周围线材和人员。在机器人端停止 host 后，
使用交互终端执行。

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Chassis_Status_Test.py \
  --port /dev/hei_chassis
```

`W/S/A/D` 平移，`Q/E` 旋转，`1/2/3` 选择低/中/高档，先从低档 1 开始。
`Space` 命令四轮零速度，`X` 或 `Ctrl+C` 退出。按住/重复方向键维持请求，
0.65 s 没有新方向按键时看门狗清除请求。

**这是四轮底盘运动学控制，不提供单轮点动模式。** ID 1 右前、2 右后、
3 左后、4 左前。固定表格显示目标/反算机体速度、四轮目标/实测角速度、位置、
力矩及状态码；机体值是驱动命令单位，不是直接实测 m/s。所有调试工具退出后，
才能启动 host。

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

本节在电脑端运行。先启动第 4 节客户端提供反馈，再开真机桥。
按钮示意图、**Meta Quest 长按约 3 秒校准**、grip/trigger 和三条 1 秒超时链路，
统一看 [VR 手柄教程](VR_mujoco_ik/README_zh.md#vr-手柄使用教程)。当前 VR 图片
回传关闭，需要时才显式开启。

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

启动完整模型 MuJoCo IK 真机桥接：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

另开一个终端运行 `teleoperate.py` 或 `record.py`，为 `6559` 提供新鲜反馈。
同时收到 VR 数据后，松开左右 grip 并等待 `command bridge ARMED`，仅松握把
不能跳过反馈条件。如需使用原双臂模型，执行 `./run_mujoco_ik.sh`，不能与完整
模型真机桥接同时运行。

默认链路：

```text
Telegrip -> MuJoCo IK: tcp://localhost:5567
MuJoCo IK -> record.py: tcp://*:6558
```

正逆解依赖 `pinocchio/casadi/eigenpy/coal-python` 比较特殊，统一环境里已经用 `conda-forge` 固定。不要额外 `pip install pin`。

## 4. 遥操作测试

只测试 VR 控制，不保存数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py \
  --remote-ip 192.168.31.127
```

控制逻辑：

- 双臂由 VR 手柄位姿经 MuJoCo IK 生成关节目标。
- 右手握把按下时，右摇杆控制底盘；松开握把底盘停止。
- 左手握把按下时，左摇杆 Y 轴控制升降方向；松开握把升降停止。
- 升降最终发送的是目标高度 `height.pos`，不是速度积分。

## 5. 录制数据

先停止 `teleoperate.py`，两者不能同时运行，否则会争用反馈端口与机器人控制。
反馈恢复后松开两侧 grip，重新解锁真机桥接。

新建数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py \
  --remote-ip 192.168.31.127 \
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
  --remote-ip 192.168.31.127 \
  --repo-id HGM/hei_rebot_lift_task1 \
  --root ~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1 \
  --resume \
  --num-episodes 5
```

注意：如果相机数量或名字变了，比如从 `front/wrist` 改成 `front/left_wrist/right_wrist`，不要 resume 到旧数据集，应该新建 repo-id。

`--root` 请以日志 `Dataset ready at ...` 输出的实际目录为准；续录需保持相机
字段、图像尺寸和 FPS 一致。`--num-episodes 5` 表示本次新增五集。

## 6. 查看和清洗数据

episode 编号从零开始。编辑前另做备份，录制过程中不要同时编辑该数据集。

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

训练不需要运行 host/VR。短训练用于跑通链路，不保证策略质量。自定义录制目录时，
训练增加 `--dataset.root=实际数据集目录`，并保持 repo ID 一致。默认目录为：

```text
~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1
```

## 8. 训练 SmolVLA

先在软件根目录安装该策略额外依赖：

```bash
conda run --no-capture-output -n lerobot5 python -m pip install -e ".[smolvla]"
```

通用 `training` 安装项不包含所有 VLA 的专用依赖。

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
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

## 9. 策略推理

保留机器人 host，但先停止 VR 真机命令发布、遥操作、录制与回放；同一时间
只保留一个控制源。确认 `--model-id` 目录存在、相机名称与训练一致、任务描述
符合演示内容。`--fps` 改变执行时序，不会加快模型推理；降低它也会改变轨迹节奏。

ACT 或 SmolVLA 都可以用 `rollout.py`。

ACT 示例：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py \
  --remote-ip 192.168.31.127 \
  --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model \
  --task "Pick up the yellow block from the floor and put it on the table in front" \
  --duration-sec 30 \
  --inference sync
```

SmolVLA 示例：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py \
  --remote-ip 192.168.31.127 \
  --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model \
  --task "Pick up the yellow block from the floor and put it on the table in front" \
  --duration-sec 60 \
  --fps 10 \
  --inference rtc
```

`sync` 在控制循环同步推理，`rtc` 使用项目的实时动作块引擎。应验证相机兼容
和控制时序；降低 FPS 不会加快推理。rollout 结束时默认会尝试回到启动时记录的
关节/升降位置，返回路径也需保持无障碍。

## 10. 回放和评估

保留 host，但停止包括 VR 发布在内的其他控制源。replay 执行已录制动作；
evaluate 运行 **ACT** 策略并录制新的本地 episode，不会自动计算任务成功率，
也不是 SmolVLA 入口。请按实际情况填写数据/模型路径及任务文本。

回放某一集数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/replay.py \
  --remote-ip 192.168.31.127 \
  --repo-id HGM/hei_rebot_lift_task1 \
  --episode-index 0 \
  --display-data
```

ACT 评估并记录 eval 数据：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/evaluate.py \
  --remote-ip 192.168.31.127 \
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
