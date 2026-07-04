# HEI ReBot Lift Hardware

HEI ReBot Lift 的硬件资料用于帮助复现 **双臂 + 升降平台 + 四轮 O 型全向底盘** 的真实机器人平台。本目录当前包含 3D 打印件、金属/钣金加工件和外购件 BOM。

机械臂部分参考了 [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm) 的开源思路：不仅记录代码，也尽量把硬件资料整理到可采购、可加工、可装配、可标定、可调试的程度。HEI ReBot Lift 在此基础上扩展为 **双臂移动操作平台**，并接入 LeRobot 数据采集、ACT/VLA 训练和真实机器人推理流程。

## 📁 当前目录

```text
hardware/
├── README.md
├── 3D_Printed_Parts/              # STL 3D 打印件
├── Metal_Parts/                   # STEP 金属/钣金加工件
└── Purchased_Parts/
    ├── Purchased_Parts.xls        # 原始采购件表
    └── Purchased_Parts.md         # Markdown 采购件 BOM
```

## 🧾 外购件 BOM

- Markdown 表格：[Purchased_Parts/Purchased_Parts.md](Purchased_Parts/Purchased_Parts.md)
- 原始表格：[Purchased_Parts/Purchased_Parts.xls](Purchased_Parts/Purchased_Parts.xls)

采购件表包含相机、线材、IO/RS485 模块、急停、USB Hub、显示器、接口模块、轴承、全向轮、电池、电源相关件等。价格和链接只作为复现参考，实际采购前请重新核对规格。

## 🖨️ 3D 打印件

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| [part_danpan_dm_zhijia_dayin.STL](3D_Printed_Parts/part_danpan_dm_zhijia_dayin.STL) | STL | 3D 打印件: `part_danpan_dm_zhijia_dayin` |
| [part_dianchi_ke_1.STL](3D_Printed_Parts/part_dianchi_ke_1.STL) | STL | 3D 打印件: `part_dianchi_ke_1` |
| [part_dianchi_ke_2.STL](3D_Printed_Parts/part_dianchi_ke_2.STL) | STL | 3D 打印件: `part_dianchi_ke_2` |
| [part_dianchi_ke_3.STL](3D_Printed_Parts/part_dianchi_ke_3.STL) | STL | 3D 打印件: `part_dianchi_ke_3` |
| [part_dipan_3-1.STL](3D_Printed_Parts/part_dipan_3-1.STL) | STL | 3D 打印件: `part_dipan_3-1` |
| [part_dipan_3.STL](3D_Printed_Parts/part_dipan_3.STL) | STL | 3D 打印件: `part_dipan_3` |
| [part_shengjiang_10.STL](3D_Printed_Parts/part_shengjiang_10.STL) | STL | 3D 打印件: `part_shengjiang_10` |
| [part_shengjiang_11.STL](3D_Printed_Parts/part_shengjiang_11.STL) | STL | 3D 打印件: `part_shengjiang_11` |
| [part_shengjiang_12.STL](3D_Printed_Parts/part_shengjiang_12.STL) | STL | 3D 打印件: `part_shengjiang_12` |
| [part_shengjiang_6.STL](3D_Printed_Parts/part_shengjiang_6.STL) | STL | 3D 打印件: `part_shengjiang_6` |
| [part_shengjiang_7.STL](3D_Printed_Parts/part_shengjiang_7.STL) | STL | 3D 打印件: `part_shengjiang_7` |
| [part_shengjiang_8.STL](3D_Printed_Parts/part_shengjiang_8.STL) | STL | 3D 打印件: `part_shengjiang_8` |
| [part_shengjiang_9.STL](3D_Printed_Parts/part_shengjiang_9.STL) | STL | 3D 打印件: `part_shengjiang_9` |
| [part_shengjiang_pingtai_1.STL](3D_Printed_Parts/part_shengjiang_pingtai_1.STL) | STL | 3D 打印件: `part_shengjiang_pingtai_1` |
| [part_shengjiang_pingtai_2.STL](3D_Printed_Parts/part_shengjiang_pingtai_2.STL) | STL | 3D 打印件: `part_shengjiang_pingtai_2` |
| [part_waike_7.STL](3D_Printed_Parts/part_waike_7.STL) | STL | 3D 打印件: `part_waike_7` |
| [part_xiangji_1.STL](3D_Printed_Parts/part_xiangji_1.STL) | STL | 3D 打印件: `part_xiangji_1` |
| [part_xiangji_2.STL](3D_Printed_Parts/part_xiangji_2.STL) | STL | 3D 打印件: `part_xiangji_2` |

## 🧱 金属 / 钣金加工件

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| [DM_4340P_banjin_falan.STEP](Metal_Parts/DM_4340P_banjin_falan.STEP) | STEP | 金属/钣金加工件: `DM_4340P_banjin_falan` |
| [part_danpan_dm_zhijia.STEP](Metal_Parts/part_danpan_dm_zhijia.STEP) | STEP | 金属/钣金加工件: `part_danpan_dm_zhijia` |
| [part_dipan_1.STEP](Metal_Parts/part_dipan_1.STEP) | STEP | 金属/钣金加工件: `part_dipan_1` |
| [part_shengjiang_falan.STEP](Metal_Parts/part_shengjiang_falan.STEP) | STEP | 金属/钣金加工件: `part_shengjiang_falan` |
| [part_shengjiang_falan_zhijia.STEP](Metal_Parts/part_shengjiang_falan_zhijia.STEP) | STEP | 金属/钣金加工件: `part_shengjiang_falan_zhijia` |
| [part_waike_2.STEP](Metal_Parts/part_waike_2.STEP) | STEP | 金属/钣金加工件: `part_waike_2` |
| [part_waike_3.STEP](Metal_Parts/part_waike_3.STEP) | STEP | 金属/钣金加工件: `part_waike_3` |
| [part_waike_5.STEP](Metal_Parts/part_waike_5.STEP) | STEP | 金属/钣金加工件: `part_waike_5` |
| [part_yaobu_1.STEP](Metal_Parts/part_yaobu_1.STEP) | STEP | 金属/钣金加工件: `part_yaobu_1` |
| [part_yaobu_2.STEP](Metal_Parts/part_yaobu_2.STEP) | STEP | 金属/钣金加工件: `part_yaobu_2` |
| [part_yaobu_3.STEP](Metal_Parts/part_yaobu_3.STEP) | STEP | 金属/钣金加工件: `part_yaobu_3` |

## 🦾 机械臂硬件参考

HEI ReBot Lift 使用双臂结构，左右两侧各 6 个关节 + 1 个夹爪电机。机械臂部分的资料整理方式参考 reBot-DevArm，后续建议继续补充关节结构、零位标定、电机 ID、软件限位和夹爪指尖资料。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机械臂数量 | 2 | 左右双臂 |
| 每臂自由度 | 6 DOF + 1 Gripper | 6 个关节 + 夹爪 |
| 关节 1-3 | DM4340 | 主要承担肩部和大负载关节 |
| 关节 4-6 | DM4310 | 主要承担腕部关节 |
| 夹爪 | DM4310 | 夹爪开合控制 |
| 通信 | U2CAN | 左右臂分别使用独立驱动板/端口 |
| 控制方式 | 位置控制为主 | 上层 LeRobot action 使用 `*.pos` |

## ⬆️ 升降平台

升降平台用于扩展双臂工作高度。当前软件侧支持启动后自动回上限位，并将上限位定义为 `height.pos = 0`。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 机构 | 丝杆升降平台 | 结构件见 3D 打印件和金属加工件 |
| 电机通信 | U2CAN | 默认端口 `/dev/hei_lift` |
| 限位输入 | 串口/IO | 默认端口 `/dev/hei_lift_io` |
| 位置范围 | -800 mm 到 0 mm | 上限位为 0，向下为负值 |
| 控制方式 | 位置目标 | 上层 action 使用 `height.pos` |

## 🛞 四轮 O 型全向底盘

底盘用于移动操作任务中的平移和转向。当前软件侧支持 `x.vel`、`y.vel`、`theta.vel` 三个速度接口，并加入基础加减速平滑，减少启动和停止时的晃动。

| 项目 | 当前配置 | 说明 |
| --- | --- | --- |
| 底盘形式 | 四轮 O 型全向 | 支持前后、左右、旋转 |
| 通信 | U2CAN | 默认端口 `/dev/hei_chassis` |
| 控制接口 | 速度控制 | `x.vel`、`y.vel`、`theta.vel` |
| 平滑方式 | 加减速限制 | 降低机器人晃动 |

## 📷 三路相机

默认三路 OpenCV 相机：

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

建议使用 `MJPG` 格式，降低 USB 带宽占用，提高多相机同时采集稳定性。

## 🔌 端口绑定

项目默认使用稳定设备名，避免 `/dev/ttyACM*` 或 `/dev/video*` 顺序变化导致程序启动失败。

```text
/dev/hei_right_arm   右臂 U2CAN
/dev/hei_left_arm    左臂 U2CAN
/dev/hei_chassis     底盘 U2CAN
/dev/hei_lift        升降电机 U2CAN
/dev/hei_lift_io     升降限位开关串口
```

## ✅ 启动前硬件检查清单

- [ ] 左右臂机械零位正确
- [ ] 升降平台上限位开关可靠触发
- [ ] 底盘四轮方向和 ID 映射正确
- [ ] 所有 U2CAN 端口能被系统识别
- [ ] 三路相机能稳定输出 MJPG 图像
- [ ] 电源电压、电流和急停正常
- [ ] 机器人周围留有安全空间

## 🧩 待继续整理

- 总装配图和装配步骤
- 电气接线图和电源分配图
- U2CAN、电机 ID、限位开关和相机端口绑定规则
- 机械臂零位、升降 homing、底盘方向和相机标定流程
- 更完整的 BOM 分类和替代件说明

## 🙏 References

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm): open robotic arm hardware, BOM, software ecosystem, and reproducible embodied AI hardware documentation.
- [LeRobot](https://github.com/huggingface/lerobot): robot interface, dataset format, training and policy deployment ecosystem.
