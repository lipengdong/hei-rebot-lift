# HEI 完整机器人 URDF 与 MuJoCo 验证

[English](README.md) | [中文](README_zh.md)

本目录保存 SW2URDF 导出的完整模型和独立运动学检查窗口，不会启动真机控制。
以下检查命令均从**本模型目录**执行，不是软件根目录；
脚本自动激活 `hei-rebot-vr`。

## 1. 模型检查

编译 URDF 并打印 MuJoCo 关节、轴、范围及 qpos 地址：

```bash
./run_mujoco_sim.sh --headless-check
```

## 2. 可视化

```bash
./run_mujoco_sim.sh
```

窗口按键：`N/P` 选择前后关节，`-/=` 减少/增加位置，`O/C` 张开/闭合两侧
夹爪，`R` 恢复检查姿态。只是运动学显示，不调用 `mj_step`。

## 3. 完整模型 VR 仿真与真机入口

切换到上三级 `VR_mujoco_ik/`，先完成该目录的
[VR 教程](../../../README_zh.md)。纯仿真分开两个终端运行：

```bash
./run_telegrip.sh
```

```bash
./run_hei_robot_vr_sim.sh
```

仿真控制双臂、平行夹爪、升降、底盘前后/横移/旋转及四轮动画，不发布真机命令。
先练习 Meta Quest 长按约 3 秒校准、grip 相对控制和释放停止。
稳定抓取模式是 TCP 绑定物体的运动学演示，不是接触力学验证。

完成硬件检查后，停止纯仿真，在机器人端启动 host，在电脑端先启动一个
`teleoperate.py` 或 `record.py` 客户端，再从 `VR_mujoco_ik/` 运行：

```bash
./run_hei_robot_vr_real.sh --enable-real-publish
```

需要新鲜 VR/实机反馈、同时松开两侧 grip，等待 `command bridge ARMED`。
启动 host 会上行回零，先检查上下限位与急停，不要同时开两种真机控制源。
真机入口只显示机器人；完整步骤见上级教程。

## 4. 平行夹爪与 TCP

每侧左手指是主控制关节。MuJoCo 不自动处理 URDF `mimic`，窗口程序显式更新
右手指为相反位移。固定坐标系：

- `a_right_end_link` / `b_left_end_link`：手指导轨中心。
- `a_right_tcp` / `b_left_tcp`：两指尖之间的名义抓取点。

仿真夹爪默认闭合，保持 grip 时按 trigger 张开、松 trigger 闭合，松 grip 保持
最后状态；真机启动先同步反馈的实际夹爪状态。

## 5. 相机 TF

模型包含三个随机器人运动的相机安装 link，以及对应的标准 optical frame：

- `front_camera_link` 挂载到 `lift_carriage_link`。
- `left_wrist_camera_link` 挂载到 `b_left_link6`。
- `right_wrist_camera_link` 挂载到 `a_right_link6`。
- 对应 optical frame 分别为 `front_camera_optical_frame`、
  `left_wrist_camera_optical_frame` 和 `right_wrist_camera_optical_frame`。

本次 SW2URDF 导出的 camera link 使用 `+Z` 朝镜头、`+X` 向画面左、`+Y`
向画面上；optical frame 将其转换为 `+X` 画面右、`+Y` 画面下、`+Z`
镜头前方。`hei_robot_mujoco_scene.py` 会在这些 frame 上创建三个 MuJoCo
具名相机：`front`、`left_wrist` 和 `right_wrist`。

当前三路分辨率均为 `640x480`。`front` 暂按 D435 RGB 的典型垂直视场角
`42.5°` 配置；两路腕部相机在取得实测内参前暂用 `60°`。一次性输出三路
预览图：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
MUJOCO_GL=egl conda run --no-capture-output -n hei-rebot-vr \
  python mujoco_ik/preview_mujoco_cameras.py
```

图片保存在 `mujoco_ik/outputs/camera_preview/`。相机内参确定后，应使用
`fovy = 2 * atan(height / (2 * fy))` 更新场景构建器中的垂直视场角。

## 6. 导出编译后的 MJCF

回到本模型目录执行：

```bash
./run_mujoco_sim.sh --headless-check --save-mjcf /tmp/HEI_robot_urdf_compiled.xml
```

导出的 XML 用于检查 MuJoCo 的解释结果，URDF 仍是源模型；移动 XML 后可能需要
调整 mesh 路径。

## 7. 模型约定

- 臂关节范围沿用旧 `reBot_dual_with_gripper.urdf` 控制约定。
- 关节 2 使用新 SW 局部轴 `0 -1 0`，物理方向对应旧模型旋转后的 `0 0 -1`。
- `base_footprint` 位于四轮接地点中心地面高度，`+X` 前、`+Y` 左、`+Z` 上。
- 升降与夹爪移动关节单位是米；升降 `-0.7..0 m` 对应实机 `-700..0 mm`。
- 轮电机 ID：1 右前、2 右后、3 左后、4 左前。
- 关节限位和工作空间投影不等于碰撞检测。
