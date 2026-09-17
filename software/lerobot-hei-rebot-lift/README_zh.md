# HEI ReBot Lift 软件

[English](README.md) | [中文](README_zh.md)

这里是双臂升降轮式机器人的 LeRobot 软件工程。整机部署教程位于上两级的项目
主页，**本目录不再重复维护另一套安装流程**，避免新旧步骤冲突。

## 从这里开始

1. 按 [项目部署教程](../../README_zh.md#-快速部署) 区分安装：机器人端 `lerobot5`、电脑控制/训练端 `lerobot5`、电脑 VR/IK 端 `hei-rebot-vr`。
2. 真机上手前先完成 [完整模型纯仿真练习](examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md#2a-先用完整模型测试-vr-仿真)。
3. 在机器人端完成端口绑定，并按 [独立硬件测试](examples/hei_rebot_lift/README_zh.md#1-硬件检查) 检查零位、底盘、升降 IO 和相机。
4. 按 [真机启动流程](../../README_zh.md#-启动流程) 遥操作，再使用下方示例教程录制、训练与测试。

## 模块文档

| 模块 | 文档 | 功能 |
| --- | --- | --- |
| 示例程序 | [Examples](examples/hei_rebot_lift/README_zh.md) | 端口绑定、独立测试、遥操作、录制/续录、数据编辑、ACT/SmolVLA、回放、评估、推理 |
| VR 与仿真 | [VR + MuJoCo IK](examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md) | 统一 VR/IK 环境、头显网址、Meta Quest 校准、手柄操作和真机同步 |
| 机器人驱动 | [Driver](src/lerobot/robots/hei_rebot_lift/README_zh.md) | 端口/相机配置、动作观测单位、升降回零、电机参数与安全超时 |
| 电机通信 | [Damiao U2CAN 源码](src/lerobot/motors/damiao_u2can/) | 项目内独立通信实现，不依赖以前复制进来的参考工程 |
| 全部教程 | [文档导航](../../docs/README_zh.md) | 硬件、软件、模型、社区与语言入口 |

## 执行目录与安全

这里是**软件根目录**。examples 教程中 `PYTHONPATH=src` 的命令在此执行；
VR 启动脚本在 `examples/hei_rebot_lift/VR_mujoco_ik/` 执行并自动激活
`hei-rebot-vr`。

- 头显网址填**电脑 IP**，客户端 `--remote-ip` 填**机器人 IP**。
- Telegrip 的 VR 图像回传当前关闭，但 host 相机采集和录制仍开启。
- host 启动会自动上行回零，先检查上下限位并清空路径。
- 同时只能有一个机器人控制源；录制前停遥操作，回放/评估/推理前停 VR 真机发布。
- 机械臂零位工具启动即写零位，不是只读诊断。
- 真机桥需要新鲜 VR 和实机反馈，并同时松开两侧握把解锁；不要绕过反馈解决网络问题。
- 仿真与 IK 防护不能证明碰撞检测或负载安全。

## 基于 LeRobot

通用 LeRobot 文档保留在 `docs/`，策略说明位于
`docs/source/policy_*_README.md`；它们介绍底层框架，不替代 HEI 真机启动教程。
请遵守 [仓库许可证](../../LICENSE) 及第三方资源许可证。
