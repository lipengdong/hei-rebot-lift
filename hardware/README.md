# HEI ReBot Lift Hardware

The HEI ReBot Lift hardware materials help reproduce the real robot platform with **dual arms + lift platform + four-wheel O-type omnidirectional chassis**. This directory currently contains 3D printed parts, metal/sheet-metal parts, and the purchased-parts BOM.

The arm hardware organization is inspired by [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm): not only code, but also materials that are practical for sourcing, machining, assembling, calibrating, and debugging. HEI ReBot Lift extends this idea into a **dual-arm mobile manipulation platform** connected to LeRobot data collection, ACT/VLA training, and real-robot rollout workflows.

## 📁 Current Layout

```text
hardware/
├── README.md
├── README_zh.md
├── 3D_Printed_Parts/              # STL 3D printed parts
├── Metal_Parts/                   # STEP metal / sheet-metal parts
└── Purchased_Parts/
    ├── Purchased_Parts.xls        # Original purchased-parts sheet
    └── Purchased_Parts.md         # Markdown purchased-parts BOM
```

## 🧾 Purchased Parts BOM

- Markdown table: [Purchased_Parts/Purchased_Parts.md](Purchased_Parts/Purchased_Parts.md)
- Original sheet: [Purchased_Parts/Purchased_Parts.xls](Purchased_Parts/Purchased_Parts.xls)

The BOM includes cameras, cables, IO/RS485 modules, emergency stop parts, USB hubs, display, interface modules, bearings, omnidirectional wheels, battery, and power-related parts. Prices and links are for reproduction reference only; please re-check specifications, stock, price, and compatibility before purchasing.

## 🖨️ 3D Printed Parts

| File | Type | Notes |
| --- | --- | --- |
| [part_danpan_dm_zhijia_dayin.STL](3D_Printed_Parts/part_danpan_dm_zhijia_dayin.STL) | STL | 3D printed part: `part_danpan_dm_zhijia_dayin` |
| [part_dianchi_ke_1.STL](3D_Printed_Parts/part_dianchi_ke_1.STL) | STL | 3D printed part: `part_dianchi_ke_1` |
| [part_dianchi_ke_2.STL](3D_Printed_Parts/part_dianchi_ke_2.STL) | STL | 3D printed part: `part_dianchi_ke_2` |
| [part_dianchi_ke_3.STL](3D_Printed_Parts/part_dianchi_ke_3.STL) | STL | 3D printed part: `part_dianchi_ke_3` |
| [part_dipan_3-1.STL](3D_Printed_Parts/part_dipan_3-1.STL) | STL | 3D printed part: `part_dipan_3-1` |
| [part_dipan_3.STL](3D_Printed_Parts/part_dipan_3.STL) | STL | 3D printed part: `part_dipan_3` |
| [part_shengjiang_10.STL](3D_Printed_Parts/part_shengjiang_10.STL) | STL | 3D printed part: `part_shengjiang_10` |
| [part_shengjiang_11.STL](3D_Printed_Parts/part_shengjiang_11.STL) | STL | 3D printed part: `part_shengjiang_11` |
| [part_shengjiang_12.STL](3D_Printed_Parts/part_shengjiang_12.STL) | STL | 3D printed part: `part_shengjiang_12` |
| [part_shengjiang_6.STL](3D_Printed_Parts/part_shengjiang_6.STL) | STL | 3D printed part: `part_shengjiang_6` |
| [part_shengjiang_7.STL](3D_Printed_Parts/part_shengjiang_7.STL) | STL | 3D printed part: `part_shengjiang_7` |
| [part_shengjiang_8.STL](3D_Printed_Parts/part_shengjiang_8.STL) | STL | 3D printed part: `part_shengjiang_8` |
| [part_shengjiang_9.STL](3D_Printed_Parts/part_shengjiang_9.STL) | STL | 3D printed part: `part_shengjiang_9` |
| [part_shengjiang_pingtai_1.STL](3D_Printed_Parts/part_shengjiang_pingtai_1.STL) | STL | 3D printed part: `part_shengjiang_pingtai_1` |
| [part_shengjiang_pingtai_2.STL](3D_Printed_Parts/part_shengjiang_pingtai_2.STL) | STL | 3D printed part: `part_shengjiang_pingtai_2` |
| [part_waike_7.STL](3D_Printed_Parts/part_waike_7.STL) | STL | 3D printed part: `part_waike_7` |
| [part_xiangji_1.STL](3D_Printed_Parts/part_xiangji_1.STL) | STL | 3D printed part: `part_xiangji_1` |
| [part_xiangji_2.STL](3D_Printed_Parts/part_xiangji_2.STL) | STL | 3D printed part: `part_xiangji_2` |

## 🧱 Metal / Sheet-Metal Parts

| File | Type | Notes |
| --- | --- | --- |
| [DM_4340P_banjin_falan.STEP](Metal_Parts/DM_4340P_banjin_falan.STEP) | STEP | Metal / sheet-metal part: `DM_4340P_banjin_falan` |
| [part_danpan_dm_zhijia.STEP](Metal_Parts/part_danpan_dm_zhijia.STEP) | STEP | Metal / sheet-metal part: `part_danpan_dm_zhijia` |
| [part_dipan_1.STEP](Metal_Parts/part_dipan_1.STEP) | STEP | Metal / sheet-metal part: `part_dipan_1` |
| [part_shengjiang_falan.STEP](Metal_Parts/part_shengjiang_falan.STEP) | STEP | Metal / sheet-metal part: `part_shengjiang_falan` |
| [part_shengjiang_falan_zhijia.STEP](Metal_Parts/part_shengjiang_falan_zhijia.STEP) | STEP | Metal / sheet-metal part: `part_shengjiang_falan_zhijia` |
| [part_waike_2.STEP](Metal_Parts/part_waike_2.STEP) | STEP | Metal / sheet-metal part: `part_waike_2` |
| [part_waike_3.STEP](Metal_Parts/part_waike_3.STEP) | STEP | Metal / sheet-metal part: `part_waike_3` |
| [part_waike_5.STEP](Metal_Parts/part_waike_5.STEP) | STEP | Metal / sheet-metal part: `part_waike_5` |
| [part_yaobu_1.STEP](Metal_Parts/part_yaobu_1.STEP) | STEP | Metal / sheet-metal part: `part_yaobu_1` |
| [part_yaobu_2.STEP](Metal_Parts/part_yaobu_2.STEP) | STEP | Metal / sheet-metal part: `part_yaobu_2` |
| [part_yaobu_3.STEP](Metal_Parts/part_yaobu_3.STEP) | STEP | Metal / sheet-metal part: `part_yaobu_3` |

## 🦾 Arm Hardware Reference

HEI ReBot Lift uses a dual-arm structure. Each side has 6 joints plus 1 gripper motor. The arm documentation follows the reBot-DevArm open-hardware style. Future documentation should continue to add joint structure, zero calibration, motor IDs, software limits, and gripper fingertip details.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Number of arms | 2 | Left and right arms |
| DOF per arm | 6 DOF + 1 Gripper | 6 joints plus gripper |
| Joints 1-3 | DM4340 | Shoulder and higher-load joints |
| Joints 4-6 | DM4310 | Wrist joints |
| Gripper | DM4310 | Gripper open/close control |
| Communication | U2CAN | Independent boards/ports for left and right arms |
| Control mode | Mainly position control | LeRobot actions use `*.pos` |

## ⬆️ Lift Platform

The lift platform extends the working height of the dual arms. The software supports automatic homing to the upper limit on startup and defines the upper limit as `height.pos = 0`.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Mechanism | Lead-screw lift platform | Structure files are in printed and metal parts |
| Motor communication | U2CAN | Default port `/dev/hei_lift` |
| Limit input | Serial / IO | Default port `/dev/hei_lift_io` |
| Position range | -800 mm to 0 mm | Upper limit is 0, downward is negative |
| Control mode | Position target | LeRobot action uses `height.pos` |

## 🛞 Four-Wheel O-Type Omnidirectional Base

The chassis provides translation and rotation for mobile manipulation tasks. The software supports `x.vel`, `y.vel`, and `theta.vel`, with basic acceleration smoothing to reduce shaking during start and stop.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Base type | Four-wheel O-type omnidirectional | Supports forward/backward, lateral, and yaw motion |
| Communication | U2CAN | Default port `/dev/hei_chassis` |
| Control interface | Velocity control | `x.vel`, `y.vel`, `theta.vel` |
| Smoothing | Acceleration limit | Reduces robot shaking |

## 📷 Three Cameras

Default OpenCV cameras:

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

MJPG is recommended to reduce USB bandwidth usage and improve stability when multiple cameras are running at the same time.

## 🔌 Device Binding

Stable device names are used by default to avoid failures caused by changing `/dev/ttyACM*` or `/dev/video*` order.

```text
/dev/hei_right_arm   Right arm U2CAN
/dev/hei_left_arm    Left arm U2CAN
/dev/hei_chassis     Chassis U2CAN
/dev/hei_lift        Lift motor U2CAN
/dev/hei_lift_io     Lift limit-switch serial port
```

## ✅ Pre-Startup Hardware Checklist

- [ ] Left and right arm mechanical zero positions are correct
- [ ] Lift upper limit switch triggers reliably
- [ ] Chassis wheel directions and ID mapping are correct
- [ ] All U2CAN ports are recognized by the system
- [ ] Three cameras output stable MJPG streams
- [ ] Power voltage, current capacity, and emergency stop are normal
- [ ] Sufficient safety space is available around the robot

## 🧩 To Be Organized

- Full assembly drawing and assembly steps
- Electrical wiring diagram and power distribution diagram
- U2CAN, motor IDs, limit switch, and camera port binding rules
- Arm zero calibration, lift homing, chassis direction, and camera calibration workflows
- More complete BOM categories and alternative part suggestions

## 🙏 References

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm): open robotic arm hardware, BOM, software ecosystem, and reproducible embodied AI hardware documentation.
- [LeRobot](https://github.com/huggingface/lerobot): robot interface, dataset format, training and policy deployment ecosystem.

## Chinese Version

- [README_zh.md](README_zh.md)
