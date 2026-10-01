#!/usr/bin/env python
"""Build an independent HEI MuJoCo scene for contact-rich grasp testing."""

from __future__ import annotations

from pathlib import Path

import mujoco

from hei_robot_mujoco_scene import (
    GRASPABLE_OBJECTS,
    SCENE_GEOMS,
    TABLE_TOP_Z_M,
    _add_floor_and_sky,
    _add_floor_markings,
    _add_graspable_objects,
    _add_lights,
    _add_robot_cameras,
    _add_table,
    _add_world_axes,
)


PHYSICS_CUBE_HALF_SIZE_M = 0.03


ARM_JOINTS = tuple(
    f"{prefix}_joint{index}"
    for prefix in ("a_right", "b_left")
    for index in range(1, 7)
)
GRIPPER_JOINTS = (
    "a_right_end_joint_L_finger",
    "a_right_end_joint_R_finger",
    "b_left_end_joint_L_finger",
    "b_left_end_joint_R_finger",
)
LIFT_JOINT = "lift_joint"
FINGER_BODIES = (
    "a_right_end_link_L_finger",
    "a_right_end_link_R_finger",
    "b_left_end_link_L_finger",
    "b_left_end_link_R_finger",
)


def _enable_contact(
    geom,
    *,
    friction: tuple[float, float, float],
    condim: int = 4,
    margin: float = 0.001,
) -> None:
    geom.contype = 1
    geom.conaffinity = 1
    geom.condim = condim
    geom.friction = list(friction)
    geom.margin = margin
    geom.solref = [0.01, 1.0]
    geom.solimp = [0.90, 0.95, 0.001, 0.5, 2.0]


def _configure_environment_contacts(spec: mujoco.MjSpec, object_friction: float) -> None:
    _enable_contact(spec.geom("hei_ground"), friction=(0.9, 0.01, 0.001))

    for name in SCENE_GEOMS:
        if not name.startswith("hei_table_"):
            continue
        _enable_contact(spec.geom(name), friction=(0.8, 0.01, 0.001))

    object_masses = (0.10, 0.10, 0.10, 0.12)
    for index, (object_spec, mass) in enumerate(
        zip(GRASPABLE_OBJECTS, object_masses, strict=True)
    ):
        body = spec.body(object_spec.body_name)
        if index < 3:
            body.pos = [
                float(body.pos[0]),
                float(body.pos[1]),
                TABLE_TOP_Z_M + PHYSICS_CUBE_HALF_SIZE_M,
            ]
        body.add_freejoint(name=f"{object_spec.body_name}_free")
        geom = spec.geom(object_spec.geom_name)
        if index < 3:
            geom.size = [PHYSICS_CUBE_HALF_SIZE_M] * 3
        _enable_contact(
            geom,
            friction=(float(object_friction), 0.02, 0.002),
            condim=6,
        )
        geom.mass = mass

    # URDF 同时包含 visual 和 collision geom，只提高真正参与碰撞的手指 geom 摩擦。
    for body_name in FINGER_BODIES:
        body = spec.body(body_name)
        for geom in body.geoms:
            if int(geom.contype) == 0:
                continue
            _enable_contact(geom, friction=(1.6, 0.03, 0.003), condim=6)


def _joint_range(spec: mujoco.MjSpec, joint_name: str) -> tuple[float, float]:
    joint = spec.joint(joint_name)
    if joint is None:
        raise ValueError(f"Physical scene is missing joint: {joint_name}")
    low, high = (float(value) for value in joint.range)
    return low, high


def _add_position_actuator(
    spec: mujoco.MjSpec,
    joint_name: str,
    *,
    kp: float,
    kv: float,
    force: float,
) -> None:
    low, high = _joint_range(spec, joint_name)
    actuator = spec.add_actuator(
        name=f"hei_physics_{joint_name}",
        trntype=mujoco.mjtTrn.mjTRN_JOINT,
        target=joint_name,
        ctrllimited=True,
        ctrlrange=[low, high],
        forcelimited=True,
        forcerange=[-force, force],
    )
    actuator.set_to_position(kp=kp, kv=kv)


def _add_robot_position_actuators(spec: mujoco.MjSpec, gripper_force_n: float) -> None:
    for index, joint_name in enumerate(ARM_JOINTS):
        local_index = index % 6
        kp = (320.0, 300.0, 260.0, 110.0, 85.0, 65.0)[local_index]
        kv = (32.0, 30.0, 26.0, 12.0, 9.0, 7.0)[local_index]
        force = (120.0, 120.0, 100.0, 45.0, 35.0, 25.0)[local_index]
        _add_position_actuator(spec, joint_name, kp=kp, kv=kv, force=force)

    for joint_name in GRIPPER_JOINTS:
        _add_position_actuator(
            spec,
            joint_name,
            kp=700.0,
            kv=12.0,
            force=float(gripper_force_n),
        )

    _add_position_actuator(spec, LIFT_JOINT, kp=1200.0, kv=80.0, force=1500.0)


def build_physics_mujoco_model(
    urdf_path: str | Path,
    *,
    timestep_s: float = 0.002,
    object_friction: float = 1.0,
    gripper_force_n: float = 18.0,
    robot_gravity_scale: float = 0.0,
) -> mujoco.MjModel:
    """Compile a contact-enabled model without changing the stable demo scene."""
    urdf_path = Path(urdf_path).expanduser().resolve()
    spec = mujoco.MjSpec.from_file(str(urdf_path))
    _add_robot_cameras(spec)
    _add_floor_and_sky(spec)
    _add_lights(spec)
    _add_floor_markings(spec)
    _add_world_axes(spec)
    _add_table(spec)
    _add_graspable_objects(spec)
    _configure_environment_contacts(spec, object_friction)
    _add_robot_position_actuators(spec, gripper_force_n)

    spec.option.timestep = float(timestep_s)
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    spec.option.iterations = 80
    spec.option.ls_iterations = 20
    model = spec.compile()

    # 机器人 URDF 的质量误差较大，默认完全补偿机器人自身重力；自由物体仍保留
    # 正常重力。gravcomp 只抵消重力，不会关闭惯性、执行器力或碰撞响应。
    robot_gravcomp = 1.0 - float(robot_gravity_scale)
    for body_id in range(1, model.nbody):
        body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id) or ""
        model.body_gravcomp[body_id] = (
            0.0 if body_name.startswith("hei_object_") else robot_gravcomp
        )
    return model
