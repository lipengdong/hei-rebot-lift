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
| Jetson 系统图标排障 | [红叉图标修复记录](jetson_system_icons_zh.md) | SVG 解码、被中断的 dpkg 配置、修复流程与预防 |

## README 分布与维护

每份文档职责不同；“同步”是共同参数和操作流程一致，不是每个子目录都复制
完整主页。目前 12 个位置共 26 份 HEI README：中英各 12 份，另有法语/西语主页。

| 位置（相对项目根目录） | 英文 | 中文 | 职责 |
| --- | --- | --- | --- |
| 项目根目录 | [README.md](../README.md) | [README_zh.md](../README_zh.md) | 首次部署、仿真练习、真机启动；另有 [法语](../README_Fr.md)、[西语](../README_es.md) |
| `hardware/` | [说明](../hardware/README.md) | [说明](../hardware/README_zh.md) | BOM、CAD、装配、上电检查 |
| `docs/` | [导航](README.md) | [导航](README_zh.md) | 文档索引与维护约定 |
| `community/` | [说明](../community/README.md) | [说明](../community/README_zh.md) | 联系方式与群二维码 |
| `media/` | [说明](../media/README.md) | [说明](../media/README_zh.md) | 图片、GIF、手柄示意图与静态 Star History |
| 软件根目录 | [说明](../software/lerobot-hei-rebot-lift/README.md) | [说明](../software/lerobot-hei-rebot-lift/README_zh.md) | 软件模块导航，统一链接主页部署教程 |
| HEI examples | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md) | 调试、录制、数据集、训练、回放/评估/推理 |
| VR/IK 根目录 | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md) | VR 环境、手柄操作、仿真与真机桥接 |
| Telegrip | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/telegrip/README.md) | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/telegrip/README_zh.md) | WebXR 桥接与图像显示配置 |
| MuJoCo IK | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README.md) | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README_zh.md) | 完整模型/旧入口区别、离线测试 |
| 完整 URDF 模型 | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/README.md) | [说明](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/README_zh.md) | 关节检查、可视化、TCP/夹爪约定、MJCF 导出 |
| 机器人驱动 | [说明](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) | [说明](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README_zh.md) | 设备配置、协议单位、电机参数、回零与看门狗 |

改安装/启动流程时，同步四语言主页；改手柄行为时，同步 VR 中英教程及主页
手柄摘要；改驱动默认值时，同步驱动中英教程和 VR/主页中的相关数值示例。
代码及 `environment.yml` 优先于复制到文档的参数。

LeRobot 通用策略、Docker 与其他机器人 README 不在本 HEI 教程维护范围内。
之前讨论的 D435/语音独立示例不在当前仓库，不能作为已提供的部署步骤。

## 使用约定

- 遵循各教程的执行目录说明；使用相对路径，不依赖某台电脑的绝对目录。
- 机器人 IP 与电脑 IP 是两项配置。`--remote-ip` 只改变 LeRobot 客户端连接，相机显示地址需另改 `telegrip/config.yaml`。
- 同一时间只保留一个机器人控制源。录制前停止遥操作，回放/策略推理前停止 VR 控制与录制。
- 工作空间投影和关节限位不等于碰撞检测；稳定抓取场景是运动学演示，不代表真实接触抓取已经验证。
- 数据默认保存在本地。删除 episode 或变更相机字段前，请先备份数据。

后续装配、接线和视频教程整理完成后，可继续加入本导航。
