#!/usr/bin/env python
"""Standalone MuJoCo validator/viewer for the complete HEI ReBot Lift URDF."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_URDF = MODEL_DIR / "urdf" / "HEI_robot_urdf.urdf"

RIGHT_ARM_JOINTS = tuple(f"a_right_joint{i}" for i in range(1, 7))
LEFT_ARM_JOINTS = tuple(f"b_left_joint{i}" for i in range(1, 7))
WHEEL_JOINTS = (
    "front_left_wheel_joint",
    "front_right_wheel_joint",
    "rear_left_wheel_joint",
    "rear_right_wheel_joint",
)
LIFT_JOINT = "lift_joint"
BASE_FRAME = "base_footprint"
TCP_FRAMES = ("a_right_tcp", "b_left_tcp")
GRIPPER_PAIRS = {
    "a_right_end_joint_L_finger": "a_right_end_joint_R_finger",
    "b_left_end_joint_L_finger": "b_left_end_joint_R_finger",
}

# 仿真检查只控制每侧左手指，右手指由程序按相反位移同步。
CONTROLLED_JOINTS = (
    *WHEEL_JOINTS,
    LIFT_JOINT,
    *RIGHT_ARM_JOINTS,
    "a_right_end_joint_L_finger",
    *LEFT_ARM_JOINTS,
    "b_left_end_joint_L_finger",
)

NEUTRAL_QPOS = {
    "lift_joint": 0.0,
    "a_right_joint1": 0.0,
    "a_right_joint2": -0.5,
    "a_right_joint3": -0.5,
    "a_right_joint4": 0.0,
    "a_right_joint5": 0.0,
    "a_right_joint6": 0.0,
    "b_left_joint1": 0.0,
    "b_left_joint2": -0.5,
    "b_left_joint3": -0.5,
    "b_left_joint4": 0.0,
    "b_left_joint5": 0.0,
    "b_left_joint6": 0.0,
    "a_right_end_joint_L_finger": 0.0,
    "b_left_end_joint_L_finger": 0.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and visualize the complete HEI robot URDF in MuJoCo.")
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF, help="URDF model path.")
    parser.add_argument("--headless-check", action="store_true", help="Compile and validate without opening a window.")
    parser.add_argument("--save-mjcf", type=Path, help="Save MuJoCo's compiled model as an MJCF XML file.")
    return parser.parse_args()


def joint_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if value < 0:
        raise ValueError(f"MuJoCo model is missing required joint: {name}")
    return value


def qpos_address(model: mujoco.MjModel, name: str) -> int:
    return int(model.jnt_qposadr[joint_id(model, name)])


def body_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if value < 0:
        raise ValueError(f"MuJoCo model is missing required body/frame: {name}")
    return value


def validate_model(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    required = set(CONTROLLED_JOINTS) | set(GRIPPER_PAIRS.values())
    for name in sorted(required):
        joint_id(model, name)
    for name in (BASE_FRAME, *TCP_FRAMES, *(name.replace("_joint", "_link") for name in WHEEL_JOINTS)):
        body_id(model, name)

    mujoco.mj_forward(model, data)

    # 标准底盘坐标检查：X 前、Y 左、Z 上，四个轮子必须位于正确象限。
    expected_quadrants = {
        "front_left_wheel_link": (1, 1),
        "front_right_wheel_link": (1, -1),
        "rear_left_wheel_link": (-1, 1),
        "rear_right_wheel_link": (-1, -1),
    }
    for name, (x_sign, y_sign) in expected_quadrants.items():
        x, y, _ = data.xpos[body_id(model, name)]
        if x * x_sign <= 0 or y * y_sign <= 0:
            raise ValueError(f"Wheel {name} is not in its expected X/Y quadrant: ({x:.4f}, {y:.4f})")

    lift_axis_world = data.xaxis[joint_id(model, LIFT_JOINT)]
    if float(np.dot(lift_axis_world, np.array([0.0, 0.0, 1.0]))) < 0.999:
        raise ValueError(f"Lift axis is not world +Z: {lift_axis_world}")

    print(
        "[HEI MuJoCo] compiled successfully: "
        f"nbody={model.nbody}, njnt={model.njnt}, nq={model.nq}, "
        f"nv={model.nv}, ngeom={model.ngeom}, nu={model.nu}"
    )
    print("[HEI MuJoCo] joints:")
    for index in range(model.njnt):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index)
        low, high = model.jnt_range[index]
        limited = bool(model.jnt_limited[index])
        range_text = f"[{low:.4f}, {high:.4f}]" if limited else "continuous"
        axis = np.array2string(model.jnt_axis[index], precision=3, suppress_small=True)
        print(
            f"  {index:02d} {name:<38} qpos={int(model.jnt_qposadr[index]):>2} "
            f"axis={axis} range={range_text}"
        )
    print("[HEI MuJoCo] base convention verified: +X forward, +Y left, +Z up")
    for name in TCP_FRAMES:
        position = np.array2string(data.xpos[body_id(model, name)], precision=4, suppress_small=True)
        print(f"[HEI MuJoCo] {name} world position at zero pose: {position}")


def clamp_joint_value(model: mujoco.MjModel, name: str, value: float) -> float:
    index = joint_id(model, name)
    if bool(model.jnt_limited[index]):
        low, high = model.jnt_range[index]
        return float(np.clip(value, low, high))
    return value


def sync_grippers(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    # MuJoCo 的 URDF 导入器不会执行 mimic，这里显式保持平行夹爪同步。
    for primary, follower in GRIPPER_PAIRS.items():
        primary_value = float(data.qpos[qpos_address(model, primary)])
        data.qpos[qpos_address(model, follower)] = clamp_joint_value(model, follower, -primary_value)


def reset_pose(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    for name, value in NEUTRAL_QPOS.items():
        data.qpos[qpos_address(model, name)] = clamp_joint_value(model, name, value)
    sync_grippers(model, data)
    mujoco.mj_forward(model, data)


def joint_step(name: str) -> float:
    if name == LIFT_JOINT:
        return 0.02
    if name in WHEEL_JOINTS:
        return 0.20
    if name in GRIPPER_PAIRS:
        return 0.002
    return 0.05


def run_viewer(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    selected = 0

    def print_selected() -> None:
        name = CONTROLLED_JOINTS[selected]
        value = float(data.qpos[qpos_address(model, name)])
        unit = "m" if name == LIFT_JOINT or name in GRIPPER_PAIRS else "rad"
        print(f"[HEI MuJoCo] selected {selected + 1:02d}/{len(CONTROLLED_JOINTS)}: {name} = {value:.4f} {unit}")

    def key_callback(keycode: int) -> None:
        nonlocal selected
        # N/P 选择关节，-/= 改变位置，R 恢复检查姿态，O/C 控制两侧夹爪。
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "N":
            selected = (selected + 1) % len(CONTROLLED_JOINTS)
            print_selected()
            return
        if key == "P":
            selected = (selected - 1) % len(CONTROLLED_JOINTS)
            print_selected()
            return
        if key == "R":
            reset_pose(model, data)
            print("[HEI MuJoCo] pose reset")
            print_selected()
            return
        if key in ("O", "C"):
            target = 0.05 if key == "O" else 0.0
            for primary in GRIPPER_PAIRS:
                data.qpos[qpos_address(model, primary)] = clamp_joint_value(model, primary, target)
            sync_grippers(model, data)
            mujoco.mj_forward(model, data)
            print(f"[HEI MuJoCo] both grippers {'opened' if key == 'O' else 'closed'}")
            return
        if key not in ("-", "=", "+"):
            return

        name = CONTROLLED_JOINTS[selected]
        direction = -1.0 if key == "-" else 1.0
        address = qpos_address(model, name)
        data.qpos[address] = clamp_joint_value(
            model,
            name,
            float(data.qpos[address]) + direction * joint_step(name),
        )
        sync_grippers(model, data)
        mujoco.mj_forward(model, data)
        print_selected()

    reset_pose(model, data)
    print("[HEI MuJoCo] controls: N/P select joint, -/= move, O open grippers, C close, R reset")
    print_selected()

    # 只做运动学可视化，不调用 mj_step，避免重力和未配置执行器干扰模型检查。
    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        viewer.cam.lookat[:] = (0.0, 0.0, 0.75)
        viewer.cam.distance = 2.8
        viewer.cam.azimuth = 135
        viewer.cam.elevation = -20
        while viewer.is_running():
            sync_grippers(model, data)
            mujoco.mj_forward(model, data)
            viewer.sync()
            time.sleep(0.01)


def main() -> None:
    args = parse_args()
    model_path = args.model.expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"URDF not found: {model_path}")

    print(f"[HEI MuJoCo] loading: {model_path}")
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    validate_model(model, data)
    reset_pose(model, data)

    if args.save_mjcf is not None:
        output = args.save_mjcf.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        mujoco.mj_saveLastXML(str(output), model)
        print(f"[HEI MuJoCo] compiled MJCF saved: {output}")

    if not args.headless_check:
        run_viewer(model, data)


if __name__ == "__main__":
    main()
