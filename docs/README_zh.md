# HEI ReBot Lift 文档导航

[English](README.md) | [中文](README_zh.md)

## 从这里开始

推荐顺序：准备硬件 → 部署环境 → 纯仿真验证 → 单模块硬件调试 → 真机遥操作 →
录制数据 → 训练与推理。真机启动会自动执行升降回零，请先清空工作区并确认急停可用。

| 主题 | 对应文档 | 内容 |
| --- | --- | --- |
| 项目与快速部署 | [项目主页](../README_zh.md) | 硬件概览、环境安装、整体启动顺序 |
| 硬件复现 | [硬件说明](../hardware/README_zh.md) | BOM、整机 STEP、打印件与金属加工件 |
| 机器人配置 | [驱动说明](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README_zh.md) | 端口映射、电机参数、升降单位、看门狗 |
| VR 部署与操作 | [VR + MuJoCo IK](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md) | Pinocchio/CasADi 安装、手柄教程、安全解锁与排障 |
| 模型与控制入口 | [MuJoCo IK 说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README_zh.md) | 完整模型仿真/真机、旧双臂入口、自检 |
| 调试与数据采集 | [示例使用教程](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md) | 端口绑定、升降/底盘调试、录制、续录与清洗 |
| 训练与推理 | [示例使用教程](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md) | ACT/SmolVLA、模型路径、回放、评估与 rollout |
| 交流与合作 | [社区](../community/README_zh.md) | 微信群、联系方式与二维码 |

## 使用约定

- 遵循各教程的执行目录说明；使用相对路径，不依赖某台电脑的绝对目录。
- 机器人 IP 与电脑 IP 是两项配置。`--remote-ip` 只改变 LeRobot 客户端连接，相机显示地址需另改 `telegrip/config.yaml`。
- 同一时间只保留一个机器人控制源。录制前停止遥操作，回放/策略推理前停止 VR 控制与录制。
- 工作空间投影和关节限位不等于碰撞检测；稳定抓取场景是运动学演示，不代表真实接触抓取已经验证。
- 数据默认保存在本地。删除 episode 或变更相机字段前，请先备份数据。

后续装配、接线和视频教程整理完成后，可继续加入本导航。
