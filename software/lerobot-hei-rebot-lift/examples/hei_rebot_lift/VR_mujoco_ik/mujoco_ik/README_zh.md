# MuJoCo IK

[English](README.md) | [中文](README_zh.md)

这是 HEI ReBot Lift VR 遥操作链路里的 MuJoCo + Pinocchio IK 子模块。

统一部署、手柄操作、网络配置和真机安全启动请看 [VR 使用教程](../README_zh.md)。
仿真示教采集、ACT 训练和仿真推理请看
[MuJoCo 数据采集、训练与推理](SIM_DATASET_WORKFLOW_zh.md)。
碰撞、双指接触、摩擦和掉落验证请看
[MuJoCo 物理抓取验证](PHYSICS_GRASP_SIMULATION_zh.md)。
该流程将 `hei-rebot-vr` 仿真进程与 `lerobot5` 采集/推理进程完全分开。

## 选择启动入口

以下脚本在上一级 `VR_mujoco_ik/` 目录执行。仿真脚本自动使用
`hei-rebot-vr`，采集和推理脚本自动使用 `lerobot5`。
`6558` 端口同一时间只能保留一个真机动作发布程序。

| 入口 | 模型 | 用途 |
| --- | --- | --- |
| `./run_hei_robot_keyboard_sim.sh` | `model/HEI_robot_urdf/` | 完整机器人键盘纯仿真；不需要 VR，不发布真机命令 |
| `./run_hei_robot_keyboard_physics.sh` | `model/HEI_robot_urdf/` | 键盘物理抓取验证；自由物体、碰撞及双指接触触发软吸附 |
| `./run_hei_robot_keyboard_dataset_sim.sh` | `model/HEI_robot_urdf/` | 键盘示教数据采集用仿真服务端（`hei-rebot-vr`） |
| `./run_hei_robot_keyboard_record.sh` | - | 键盘示教数据采集客户端（`lerobot5`） |
| `./run_hei_robot_vr_sim.sh` | `model/HEI_robot_urdf/` | 完整机器人、场景、VR、稳定抓取演示；不发布真机命令 |
| `./run_hei_robot_vr_physics.sh` | `model/HEI_robot_urdf/` | VR 物理抓取验证；启用重力、碰撞及双指接触触发软吸附 |
| `./run_hei_robot_vr_dataset_sim.sh` | `model/HEI_robot_urdf/` | VR 数据采集用仿真服务端（`hei-rebot-vr`） |
| `./run_hei_robot_mujoco_record.sh` | - | 独立 LeRobotDataset 采集客户端（`lerobot5`） |
| `./run_hei_robot_policy_sim.sh` | `model/HEI_robot_urdf/` | 策略推理用仿真服务端（`hei-rebot-vr`） |
| `./run_hei_robot_mujoco_rollout.sh` | - | 独立策略推理客户端（`lerobot5`） |
| `./run_hei_robot_vr_real.sh --enable-real-publish` | `model/HEI_robot_urdf/` | 仅机器人显示与真机桥接；需要实机反馈及松开握把解锁 |
| `./run_mujoco_ik.sh` | `model/reBot_description/` | 旧双臂 realtime 控制程序，不是完整机器人入口 |

## IK 平滑与连续追踪

完整模型的纯仿真与物理仿真使用以下链路：

```text
VR/键盘 TCP 目标 -> 自适应位姿滤波（VR） -> 单次 IK 求解
                 -> 缓存完整关节目标 -> 按真实 dt 连续追踪
```

VR 快速运动时滤波时间常数自动减小，静止和慢速运动时自动增大；映射比例仍为
1:1。每个超过仿真死区的新 TCP 目标只求解一次，后续渲染循环继续追踪缓存的
关节目标，不会对静止目标重复运行 IPOPT。键盘模式不需要 VR 位姿滤波，但共用
关节目标缓存和 `dt` 追踪。

参数都在 `hei_robot_vr_mujoco_sim.py`：

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `TARGET_POS_EPS_M` / `TARGET_ROT_EPS_RAD` | `0.0003 m` / `0.10 deg` | 仿真 TCP 新目标死区 |
| `ARM_TARGET_FILTER_FAST_TAU_S` / `SLOW_TAU_S` | `0.018 s` / `0.055 s` | VR 快速/慢速运动滤波时间常数 |
| `ARM_TRACK_TIME_CONSTANT_S` | `0.045 s` | 缓存关节目标的跟随时间常数 |
| `ARM_MAX_JOINT_SPEED_RAD_S` | `[3,3,3,4,4,4]` | 仿真六关节最大追踪速度 |
| `REAL_TARGET_POS_EPS_M` / `REAL_TARGET_ROT_EPS_RAD` | `0.0012 m` / `0.35 deg` | 真机桥原目标死区 |

减小 `ARM_TRACK_TIME_CONSTANT_S` 会更跟手但更容易显出噪声，增大则更平滑但延迟
更明显。一次只改一组参数，并先运行纯仿真与下面的无界面测试。真机模式自动绕过
自适应滤波和 `dt` 追踪，继续使用原固定步进逻辑。

键盘仿真中按 `5` 可让左臂缓慢复位，按 `6` 可让右臂缓慢复位；按一下即可，
重新操作对应机械臂或按 `Space` 会取消复位并保持当前位置。完整键位见
[上级使用教程](../README_zh.md)。

在 `software/lerobot-hei-rebot-lift` 根目录可视化键盘仿真数据集：

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  lerobot-dataset-viz \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --episode-index 0
```

真机模式还需要机器人 host，以及 `teleoperate.py` 或 `record.py` 中的一个。
启用真机命令前请先阅读上级教程。

## 无界面自检

以下命令不发布真机命令，也不需要 VR 头显：

```bash
./run_hei_robot_keyboard_sim.sh --headless-check
./run_hei_robot_keyboard_physics.sh --headless-check
./run_hei_robot_vr_sim.sh --headless-check
./run_hei_robot_vr_physics.sh --headless-check
./run_hei_robot_vr_real.sh --headless-check
conda run --no-capture-output -n hei-rebot-vr python -m unittest discover -s mujoco_ik/tests -p 'test_*.py' -v
```

模型与协议自检通过，不代表实机零位、方向、限位开关和负载能力已经验证；
这些仍需单独进行硬件调试。

注意：`pinocchio`、`casadi`、`eigenpy`、`coal-python` 请使用上级 `environment.yml` 里的 conda-forge 版本安装，不要在这里单独 `pip install pin`。
