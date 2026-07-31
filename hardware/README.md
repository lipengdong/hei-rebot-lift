# HEI ReBot Lift Hardware

This directory contains the hardware release package for **HEI ReBot Lift**, a dual-arm mobile manipulation robot with a lift platform and a four-wheel O-type omnidirectional chassis.

The goal of this hardware folder is to make the robot easier to reproduce: not only software, but also the practical files needed for sourcing, machining, 3D printing, assembly review, and later maintenance.

## 📁 Directory Layout

```text
hardware/
├── README.md                         # English hardware guide
├── README_zh.md                      # Chinese hardware guide
├── HEI_ReBot_Lift_BOM.xlsx                      # Overall robot BOM / purchasing checklist
├── Hei_robot_lift.STEP               # Full robot STEP assembly
├── 3D_Printed_Parts/                 # STL files for printed parts
└── Metal_Parts/
    ├── HEI_Metal_Body_Parts_List.xlsx       # Metal body parts list
    ├── step/                         # STEP files for metal/CNC/sheet-metal parts
    └── dwg/                          # DWG drawings for manufacturing reference
```

## 🧾 Main Files

| File | Purpose | Notes |
| --- | --- | --- |
| [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx) | Overall robot BOM | Main purchasing and preparation checklist for the whole robot |
| [Hei_robot_lift.STEP](Hei_robot_lift.STEP) | Full robot assembly model | Use this first to inspect the complete mechanical structure and spatial layout |
| [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) | Metal body parts list | Used with `Metal_Parts/step/` and `Metal_Parts/dwg/` for machining |
| [3D_Printed_Parts/](3D_Printed_Parts/) | 3D printed parts | STL files for printed covers, brackets, lift and camera-related parts |
| [Metal_Parts/step/](Metal_Parts/step/) | Metal STEP files | 3D CAD files for CNC/sheet-metal communication and assembly check |
| [Metal_Parts/dwg/](Metal_Parts/dwg/) | Metal DWG drawings | 2D drawing files for manufacturing reference |

## 🧭 Recommended Reproduction Order

1. Open [Hei_robot_lift.STEP](Hei_robot_lift.STEP) to understand the full robot structure.
2. Use [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx) to prepare motors, electronics, sensors, fasteners, power parts, cables, cameras, and other purchased parts.
3. Review [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) before sending metal parts for machining.
4. Use `Metal_Parts/step/` and `Metal_Parts/dwg/` together when communicating with the manufacturer.
5. Print the STL files in [3D_Printed_Parts/](3D_Printed_Parts/) and test-fit them before final assembly.
6. Assemble the chassis, lift, dual arms, cameras, wiring, and emergency-stop/power system.
7. After assembly, continue with the software-side checks: motor IDs, port binding, lift homing, chassis direction, arm zero position, and camera streams.

## 🦾 Arm Hardware Reference

The dual arms follow the open-hardware spirit of [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm), while HEI ReBot Lift extends the system into a mobile dual-arm platform with lift and real-robot learning workflows.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Arm count | 2 | Left and right arms |
| DOF per arm | 6 DOF + 1 gripper | 6 arm joints and one gripper motor |
| Joints 1-3 | DM4340P series | Higher-load shoulder/elbow joints |
| Joints 4-6 | DM4310 series | Wrist joints, tuned separately in software |
| Gripper | DM4310 series | Open/close control |
| Communication | U2CAN | Separate driver boards/ports are used by the system |
| Main control mode | Position control | LeRobot actions use joint position targets |

## ⬆️ Lift Platform

The lift platform expands the working height of the dual arms. In the software stack, the lift homes to the upper limit during startup and defines the upper limit as `height.pos = 0`.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Mechanism | Lead-screw lift platform | Related files are included in printed and metal parts |
| Motor | DM4310 series | Lift motor, controlled through U2CAN |
| Position range | -800 mm to 0 mm | Upper limit is 0; downward motion is negative |
| Control interface | Position target | LeRobot action key: `height.pos` |
| Homing | Upper limit switch | Required before reliable height control |

## 🛞 Four-Wheel O-Type Omnidirectional Base

The chassis supports translation and rotation for mobile manipulation tasks.

| Item | Current Configuration | Notes |
| --- | --- | --- |
| Base type | Four-wheel O-type omnidirectional chassis | Supports forward/backward, lateral, and yaw motion |
| Wheel motors | 4 x DM4310 series | Four chassis motors are configured as DM4310 in software |
| Control interface | Velocity control | `x.vel`, `y.vel`, `theta.vel` |
| Smoothing | Acceleration/deceleration limit | Reduces shaking during start and stop |

## 🖨️ 3D Printed Parts

Current release: **25 STL files**.

Typical groups include:

- Base/chassis printed parts: `part_dipan_*`
- Lift platform printed parts: `part_shengjiang_*`, `part_shengjiang_pingtai_*`
- Battery/case parts: `part_dianchi_ke_*`, `part_waike_7`
- Camera parts: `part_xiangji_*`
- Motor/bracket printed parts: `part_danpan_dm_zhijia_dayin*`

Printing notes:

- Print one set first for fit checking before batch printing.
- Check screw holes, cable clearance, motor mounting direction, and camera angle before final assembly.
- Material and infill should be selected according to the actual load and mounting position.

## 🧱 Metal / CNC / Sheet-Metal Parts

Current release:

| Type | Count | Directory |
| --- | ---: | --- |
| STEP | 11 | [Metal_Parts/step/](Metal_Parts/step/) |
| DWG | 9 | [Metal_Parts/dwg/](Metal_Parts/dwg/) |
| Metal list | 1 | [Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) |

Metal STEP files:

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

DWG files are provided for manufacturing communication and drawing review. Please verify tolerances, bending direction, surface treatment, hole size, and threaded holes with your manufacturer before production.

## 📷 Cameras and Sensors

The software side currently supports a multi-camera setup, typically:

```text
front       head/front camera
left_wrist  left wrist camera
right_wrist right wrist camera
```

For USB cameras, MJPG is recommended to reduce bandwidth usage and improve stability. For D435 RGB-D usage, see the software examples under `software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/D435/`.

## ✅ Hardware Checklist Before Power-On

- [ ] The full assembly has been reviewed using [Hei_robot_lift.STEP](Hei_robot_lift.STEP)
- [ ] Purchased parts match [HEI_ReBot_Lift_BOM.xlsx](HEI_ReBot_Lift_BOM.xlsx)
- [ ] Metal parts match the metal list and CAD files
- [ ] 3D printed parts are test-fitted before final assembly
- [ ] Left/right arm zero positions are mechanically safe
- [ ] Lift upper limit switch triggers reliably
- [ ] Chassis wheel direction and motor ID mapping are correct
- [ ] Emergency stop and power distribution are checked
- [ ] USB/CAN/serial cables are fixed and strain-relieved
- [ ] Cameras stream reliably before robot motion tests

## ⚠️ Notes

- The BOM, CAD files, and drawings are released for reproduction reference. Please re-check stock, price, mechanical tolerances, motor versions, and electrical compatibility before purchasing or machining.
- Keep enough physical clearance during first power-on and first motion tests.
- For the latest motor parameters, port mapping, camera configuration, and control commands, use the software documentation as the source of truth.

## 🙏 References

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm): open robotic arm hardware and reproducible embodied AI hardware documentation.
- [LeRobot](https://github.com/huggingface/lerobot): robot interface, dataset format, training, and real-robot policy deployment ecosystem.

## Chinese Version

- [README_zh.md](README_zh.md)
