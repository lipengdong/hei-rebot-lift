# MuJoCo 物理抓取验证

[English](PHYSICS_GRASP_SIMULATION.md) | [中文](PHYSICS_GRASP_SIMULATION_zh.md)

这套程序与原来的稳定示教仿真完全分开。稳定示教模式会直接把附近物体绑定到 TCP，适合采集可重复的数据；本模式默认采用“物理碰撞 + 接触触发限力吸附”：物体首先必须同时接触同一夹爪的左右两指，程序才会在当前相对位置启用弹簧阻尼吸附力。物体始终是自由刚体并保留重力、碰撞和摩擦，吸附力有上限，因此桌面和手指接触仍能阻挡物体，不会像硬焊接约束一样强行拉动物体穿过几何体。

物理模式中的三个彩色方块边长为 `50 mm`，比稳定示教场景中的方块更小，方便平行夹爪完成双指接触。

夹爪闭合采用柔顺策略：未接触物体时按照仿真时间以 `40 mm/s` 渐进闭合，不受 VR/渲染循环帧率影响。默认吸附模式在同一物体形成双指接触后锁定实际接触开度，不再继续施加预压；纯碰撞模式才保留 `5 mm` 预压。物理接触使用规则的高摩擦平面夹持垫，不再使用不规则的手指 STL 碰撞面。吸附力最大为 `12 N`，姿态保持力矩最大为 `0.10 N·m`，吸附位置误差超过 `30 mm` 时自动脱附；张开夹爪或复位场景也会立即解除吸附。左右夹爪不会同时吸附同一个物体。

本模式采用混合控制：双臂关节直接跟随 IK 输出，保持与原仿真一致的末端响应；夹爪使用限力位置执行器，桌面物体使用自由刚体和完整接触动力学。底盘位姿和升降仍使用命令级运动模型。因此该模式用于验证夹爪与物体的接触、摩擦和掉落，不用于评估机械臂电机动力学。

由于当前 URDF 的机器人质量并非实测值，默认 `--robot-gravity-scale 0`。桌面物体始终保留完整重力；该参数主要保留给后续质量和惯量标定使用，当前双臂由运动学位置控制，不依赖错误的机械臂重量。

## VR 控制启动

先启动 Telegrip，然后运行：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_physics.sh
```

操作方式与原 VR 仿真一致。额外快捷键：

| 按键 | 功能 |
| --- | --- |
| `C` | 显示/隐藏接触点与接触力 |
| `R` | 复位机器人和所有自由物体 |
| `F` | 显示/隐藏刚体坐标系 |

## 键盘控制启动

键盘模式不需要启动 Telegrip：

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_physics.sh
```

默认启用接触触发软吸附。如果需要严格验证只依靠夹爪力、摩擦和碰撞的纯物理抓取，可运行：

```bash
./run_hei_robot_keyboard_physics.sh --no-grasp-assist
```

键位与原键盘仿真一致：`1/2/3/4` 切换底盘、升降、左臂和右臂，`5/6`
分别复位左臂和右臂。`Z/X` 张开或闭合当前夹爪，`Shift` 精细控制，`Space`
停止双臂追踪，`C` 显示接触点和接触力，`V` 显示坐标系，`Backspace` 复位
完整场景，`Esc` 退出。终端启动时也会输出完整键位。

日志中的 `contacts` 会显示每个物体接触了哪一侧手指，`assisted` 显示当前限力吸附关系；只有同一物体先同时接触两指并被抬离桌面，才会输出 `physical grasp confirmed`。张开夹爪或吸附偏差过大会输出 `grasp assist released`，物体失去有效夹持后会输出 `object released/dropped`。

## 参数

```bash
./run_hei_robot_vr_physics.sh \
  --gripper-force-n 18 \
  --object-friction 1.0 \
  --grasp-assist \
  --robot-gravity-scale 0 \
  --physics-timestep-s 0.002
```

- `--gripper-force-n`：每个手指位置执行器的最大推力。
- `--object-friction`：物体接触面的滑动摩擦系数。
- `--grasp-assist` / `--no-grasp-assist`：启用或关闭双指接触触发的限力吸附，默认启用。
- `--robot-gravity-scale`：机器人重力比例，`0` 为完全补偿，`1` 为使用 URDF 完整重量。
- `--physics-timestep-s`：MuJoCo 固定物理步长。

这些参数用于仿真验证，不等同于达妙电机真实电流、夹爪结构变形或材料摩擦。判断真实成功率前，仍需根据物体质量、夹爪胶垫和实测夹持力进行标定。

## 无界面自检

```bash
./run_hei_robot_vr_physics.sh --headless-check
./run_hei_robot_keyboard_physics.sh --headless-check
```

自检会确认双臂准确跟随 IK 关节目标、夹爪由执行器实际开合、物体具有自由关节、重力和桌面接触有效，并验证双指接触能够触发限力吸附、张开夹爪能够解除吸附并使物体下落。
