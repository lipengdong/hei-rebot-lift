# HEI ReBot Lift Hardware

本目录是 **HEI ReBot Lift** 的硬件资料包，用于复现一台 **双臂 + 升降平台 + 四轮 O 型全向底盘** 的移动操作机器人。

这个目录的目标不是只放几个模型文件，而是尽量把复现真实机器人需要的资料整理清楚：采购、加工、3D 打印、装配检查、后期维护都能有对应入口。

## 📁 目录结构

```text
hardware/
├── README.md                         # 英文硬件说明
├── README_zh.md                      # 中文硬件说明
├── HEI_ReBot_Lift_BOM.xlsx                      # 整机 BOM / 总采购清单
├── Hei_robot_lift.STEP               # 整体机器人 STEP 总装模型
├── 3D_Printed_Parts/                 # 3D 打印件 STL
└── Metal_Parts/
    ├── HEI_Metal_Body_Parts_List.xlsx       # 金属主体加工件清单
    ├── step/                         # 金属 / CNC / 钣金件 STEP
    └── dwg/                          # 金属加工件 DWG 图纸
```

## 🧾 核心文件

| 文件 | 用途 | 说明 |
| --- | --- | --- |
| [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx) | 整机总 BOM | 用于准备电机、电控、传感器、紧固件、电源、线材、相机等整机物料 |
| [Hei_robot_lift.STEP](Hei_robot_lift.STEP) | 整机总装模型 | 建议优先打开，用来理解整机结构、空间布局和装配关系 |
| [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) | 金属件清单 | 与 `Metal_Parts/step/`、`Metal_Parts/dwg/` 配合给加工厂使用 |
| [3D_Printed_Parts/](3D_Printed_Parts/) | 3D 打印件 | 包含外壳、支架、升降、底盘、相机等相关 STL 文件 |
| [Metal_Parts/step/](Metal_Parts/step/) | 金属件 STEP | 用于加工沟通、三维检查和装配确认 |
| [Metal_Parts/dwg/](Metal_Parts/dwg/) | 金属件 DWG | 用于二维图纸检查和加工沟通 |

## 🧭 推荐复现顺序

1. 先打开 [Hei_robot_lift.STEP](Hei_robot_lift.STEP)，理解整机结构和空间关系。
2. 根据 [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx) 准备电机、电控、传感器、相机、电源、线材、紧固件等物料。
3. 加工金属件前，先核对 [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx)。
4. 给加工厂沟通时，建议 `Metal_Parts/step/` 和 `Metal_Parts/dwg/` 一起提供。
5. 打印 [3D_Printed_Parts/](3D_Printed_Parts/) 中的 STL 文件，建议先小批量试装，再批量打印。
6. 依次完成底盘、升降平台、双臂、相机、走线、电源和急停系统装配。
7. 装配完成后，再进入软件侧检查：电机 ID、端口绑定、升降 homing、底盘方向、机械臂零位和相机画面。

## 🦾 机械臂硬件参考

机械臂部分参考了 [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm) 的开源思路。HEI ReBot Lift 在此基础上扩展为双臂移动操作平台，并接入 LeRobot 数据采集、ACT/VLA 训练和真实机器人推理流程。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机械臂数量 | 2 | 左右双臂 |
| 每臂自由度 | 6 DOF + 1 Gripper | 6 个关节 + 夹爪 |
| 关节 1-3 | DM4340P 系列 | 主要承担肩部、肘部等大负载关节 |
| 关节 4-6 | DM4310 系列 | 主要承担腕部关节，软件中单独调参 |
| 夹爪 | DM4310 系列 | 夹爪开合控制 |
| 通信 | U2CAN | 系统中左右臂使用独立驱动板/端口 |
| 主要控制方式 | 位置控制 | LeRobot action 使用关节位置目标 |

## ⬆️ 升降平台

升降平台用于扩展双臂工作高度。软件侧启动后会先回上限位，并将上限位定义为 `height.pos = 0`。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机构形式 | 丝杆升降平台 | 相关结构件包含在 3D 打印件和金属件中 |
| 电机 | DM4310 系列 | 升降电机，通过 U2CAN 控制 |
| 位置范围 | -800 mm 到 0 mm | 上限位为 0，向下为负值 |
| 控制接口 | 位置目标 | LeRobot action key 为 `height.pos` |
| 回零方式 | 上限位开关 | 准确高度控制前必须先 homing |

## 🛞 四轮 O 型全向底盘

底盘用于移动操作任务中的平移和旋转。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 底盘形式 | 四轮 O 型全向底盘 | 支持前后、左右和旋转 |
| 轮组电机 | 4 x DM4310 系列 | 软件中四个底盘电机均配置为 DM4310 |
| 控制接口 | 速度控制 | `x.vel`、`y.vel`、`theta.vel` |
| 平滑方式 | 加减速限制 | 降低启动、停止时的整机晃动 |

## 🖨️ 3D 打印件

当前包含 **25 个 STL 文件**。

典型分类：

- 底盘相关：`part_dipan_*`
- 升降平台相关：`part_shengjiang_*`、`part_shengjiang_pingtai_*`
- 电池 / 外壳相关：`part_dianchi_ke_*`、`part_waike_7`
- 相机相关：`part_xiangji_*`
- 电机 / 支架相关：`part_danpan_dm_zhijia_dayin*`

打印建议：

- 先打印一套关键件试装，再批量打印。
- 重点检查螺丝孔、走线空间、电机安装方向和相机角度。
- 材料和填充率根据实际受力位置选择，不建议关键承力位置随意降低强度。

## 🧱 金属 / CNC / 钣金件

当前包含：

| 类型 | 数量 | 目录 |
| --- | ---: | --- |
| STEP | 11 | [Metal_Parts/step/](Metal_Parts/step/) |
| DWG | 9 | [Metal_Parts/dwg/](Metal_Parts/dwg/) |
| 金属件清单 | 1 | [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) |

金属 STEP 文件包括：

- `cnc-DM_4340P_banjin_falan.STEP`
- `cnc-part_shengjiang_falan.STEP`
- `part_danpan_dm_zhijia.STEP`
- `part_dipan_1.STEP`
- `part_shengjiang_falan_zhijia.STEP`
- `part_waike_2.STEP`
- `part_waike_3.STEP`
- `part_waike_5.STEP`
- `part_yaobu_1.STEP`
- `part_yaobu_2.STEP`
- `part_yaobu_3.STEP`

DWG 文件用于加工沟通和二维图纸检查。正式加工前，请和加工厂确认公差、折弯方向、表面处理、孔径、沉孔、螺纹孔等细节。

## 📷 相机与传感器

软件侧支持多相机配置，常见配置为：

```text
front       头部 / 前视相机
left_wrist  左腕相机
right_wrist 右腕相机
```

USB 相机建议使用 `MJPG` 格式，降低 USB 带宽占用，提高多相机同时采集稳定性。D435 RGB-D 的使用示例见：`software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/D435/`。

## ✅ 上电前硬件检查清单

- [ ] 已使用 [Hei_robot_lift.STEP](Hei_robot_lift.STEP) 检查整机装配关系
- [ ] 外购件已根据 [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx) 核对
- [ ] 金属件已对照清单和 CAD 文件确认
- [ ] 3D 打印件已完成试装
- [ ] 左右臂机械零位处于安全位置
- [ ] 升降平台上限位开关可以可靠触发
- [ ] 底盘四轮方向和电机 ID 映射正确
- [ ] 急停和电源分配检查正常
- [ ] USB / CAN / 串口线材固定可靠，有基本应力释放
- [ ] 相机画面稳定后再进行机器人运动测试

## ⚠️ 注意事项

- BOM、CAD 和图纸主要作为复现参考，正式采购和加工前请重新核对库存、价格、机械公差、电机版本和电气兼容性。
- 第一次上电、第一次运动和第一次升降测试时，机器人周围必须预留足够安全空间。
- 电机参数、端口映射、相机配置和控制命令以 software 目录中的最新程序和文档为准。

## 🙏 参考项目

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)：开放机械臂硬件、BOM、软件生态和可复现具身智能硬件文档。
- [LeRobot](https://github.com/huggingface/lerobot)：机器人接口、数据集格式、训练和真实机器人策略部署生态。
