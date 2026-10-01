#!/usr/bin/env python
"""VR-controlled HEI simulation with physical contacts and free objects.

This is intentionally separate from the stable demonstration simulator. Objects
are never attached to a TCP: grasping depends on finger contact and friction.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco
import numpy as np

import hei_robot_vr_mujoco_sim as stable_sim
from hei_robot_mujoco_physics_scene import build_physics_mujoco_model


GRIPPER_CLOSE_SPEED_M_S = 0.04
GRIPPER_CLOSE_MAX_DT_S = 0.05
GRIPPER_CONTACT_PRELOAD_M = 0.005
GRIPPER_CONTACT_LOSS_STEPS = 6
GRASP_ASSIST_KP_N_M = 400.0
GRASP_ASSIST_KD_N_S_M = 8.0
GRASP_ASSIST_MAX_FORCE_N = 6.0


class HEIRobotVRPhysicsSimulator(stable_sim.HEIRobotVRSimulator):
    """Reuse VR/IK mapping while replacing stable attachment with MuJoCo physics."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.physics_args = args
        self._physics_ready = False
        self._physics_accumulator_s = 0.0
        self._contact_debug_enabled = False
        self._physical_grasps: set[tuple[str, str]] = set()
        self._arm_command_q: dict[str, np.ndarray] = {}
        self._lift_command_q = 0.0
        self._gripper_contact_hold: dict[str, tuple[str, float] | None] = {
            "right": None,
            "left": None,
        }
        self._gripper_contact_loss_steps = {"right": 0, "left": 0}
        self._gripper_command_opening_m = {
            "right": stable_sim.GRIPPER_CLOSED_M,
            "left": stable_sim.GRIPPER_CLOSED_M,
        }
        self._gripper_last_command_sim_s = {"right": 0.0, "left": 0.0}
        self._grasp_assist_anchor: dict[str, tuple[str, np.ndarray] | None] = {
            "right": None,
            "left": None,
        }

        original_builder = stable_sim.build_mujoco_model

        def physics_builder(model_path, *, add_environment=True):
            del add_environment
            return build_physics_mujoco_model(
                model_path,
                timestep_s=args.physics_timestep_s,
                object_friction=args.object_friction,
                gripper_force_n=args.gripper_force_n,
                robot_gravity_scale=args.robot_gravity_scale,
            )

        stable_sim.build_mujoco_model = physics_builder
        try:
            super().__init__(args)
        finally:
            stable_sim.build_mujoco_model = original_builder

        self._actuator_by_joint = {}
        for joint_name in (
            *stable_sim.RIGHT_ARM_JOINTS,
            *stable_sim.LEFT_ARM_JOINTS,
            *stable_sim.GRIPPER_JOINTS["right"],
            *stable_sim.GRIPPER_JOINTS["left"],
            stable_sim.LIFT_JOINT,
        ):
            actuator_name = f"hei_physics_{joint_name}"
            actuator_id = mujoco.mj_name2id(
                self.model,
                mujoco.mjtObj.mjOBJ_ACTUATOR,
                actuator_name,
            )
            if actuator_id < 0:
                raise ValueError(f"Physical model is missing actuator: {actuator_name}")
            self._actuator_by_joint[joint_name] = actuator_id

        self._finger_bodies = {
            "right": {
                "left": self._mujoco_body_id("a_right_end_link_L_finger"),
                "right": self._mujoco_body_id("a_right_end_link_R_finger"),
            },
            "left": {
                "left": self._mujoco_body_id("b_left_end_link_L_finger"),
                "right": self._mujoco_body_id("b_left_end_link_R_finger"),
            },
        }
        self._gripper_command_opening_m = {
            side: self._measured_gripper_opening(side) for side in ("right", "left")
        }
        self._gripper_last_command_sim_s = {
            "right": float(self.data.time),
            "left": float(self.data.time),
        }
        self._grasp_assist_anchor = {"right": None, "left": None}
        self._physics_ready = True
        self._arm_command_q = {
            "right": self._get_joint_q(stable_sim.RIGHT_ARM_JOINTS),
            "left": self._get_joint_q(stable_sim.LEFT_ARM_JOINTS),
        }
        self._sync_robot_controls()
        self._apply_kinematic_robot_pose()
        mujoco.mj_forward(self.model, self.data)
        print(
            f"[HEI Physics] contact mode ready: timestep={self.model.opt.timestep:g}s, "
            f"gripper_force={args.gripper_force_n:g}N, friction={args.object_friction:g}",
            f"robot_gravity_scale={args.robot_gravity_scale:g}, arm_control=kinematic",
            flush=True,
        )

    def _free_joint_addresses(self, body_id: int) -> tuple[int, int]:
        joint_id = int(self.model.body_jntadr[body_id])
        if joint_id < 0 or self.model.jnt_type[joint_id] != mujoco.mjtJoint.mjJNT_FREE:
            raise ValueError(
                f"Physical object body is missing a free joint: "
                f"{mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY, body_id)}"
            )
        return int(self.model.jnt_qposadr[joint_id]), int(self.model.jnt_dofadr[joint_id])

    def _object_support_height(self, runtime) -> float:
        geom_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_GEOM,
            runtime.spec.geom_name,
        )
        if geom_id >= 0 and self.model.geom_type[geom_id] == mujoco.mjtGeom.mjGEOM_BOX:
            return float(self.model.geom_size[geom_id, 2])
        return float(runtime.spec.support_height_m)

    def _reset_scene_objects(self) -> None:
        for runtime in self.graspable_objects.values():
            qpos_address, dof_address = self._free_joint_addresses(runtime.body_id)
            self.data.qpos[qpos_address : qpos_address + 3] = runtime.initial_pos
            self.data.qpos[qpos_address + 3 : qpos_address + 7] = runtime.initial_quat
            self.data.qvel[dof_address : dof_address + 6] = 0.0
            runtime.held_by = None
            runtime.tcp_relative_pos = None
            runtime.tcp_relative_rot = None
        self.previous_gripper_closed = {"right": True, "left": True}
        self._gripper_contact_hold = {"right": None, "left": None}
        self._gripper_contact_loss_steps = {"right": 0, "left": 0}
        self._gripper_command_opening_m = {
            "right": stable_sim.GRIPPER_CLOSED_M,
            "left": stable_sim.GRIPPER_CLOSED_M,
        }
        self._gripper_last_command_sim_s = {
            "right": float(self.data.time),
            "left": float(self.data.time),
        }
        self._grasp_assist_anchor = {"right": None, "left": None}
        self.data.xfrc_applied[:] = 0.0
        if hasattr(self, "_physical_grasps"):
            self._physical_grasps.clear()

    def _set_joint_q(self, names: tuple[str, ...], values: np.ndarray) -> None:
        # 双臂继续使用原仿真的即时关节位置跟随，避免错误质量/惯量和执行器
        # 滞后进入 IK 反馈环；夹爪与自由物体仍由 MuJoCo 接触动力学处理。
        super()._set_joint_q(names, values)
        if not self._physics_ready:
            return
        for name in names:
            joint_id = self._mujoco_joint_id(name)
            self.data.qvel[int(self.model.jnt_dofadr[joint_id])] = 0.0
            actuator_id = self._actuator_by_joint.get(name)
            if actuator_id is not None:
                self.data.ctrl[actuator_id] = self.data.qpos[self.mj_qpos[name]]
        for side, arm_names in stable_sim.ARM_JOINTS.items():
            if any(name in arm_names for name in names):
                self._arm_command_q[side] = self._get_joint_q(arm_names)

    def _apply_kinematic_robot_pose(self) -> None:
        if not self._physics_ready:
            return
        for side, names in stable_sim.ARM_JOINTS.items():
            command_q = self._arm_command_q[side]
            for name, value in zip(names, command_q, strict=True):
                joint_id = self._mujoco_joint_id(name)
                self.data.qpos[self.mj_qpos[name]] = value
                self.data.qvel[int(self.model.jnt_dofadr[joint_id])] = 0.0
                self.data.ctrl[self._actuator_by_joint[name]] = value
        lift_id = self._mujoco_joint_id(stable_sim.LIFT_JOINT)
        self.data.qpos[self.mj_qpos[stable_sim.LIFT_JOINT]] = self._lift_command_q
        self.data.qvel[int(self.model.jnt_dofadr[lift_id])] = 0.0
        self.data.ctrl[self._actuator_by_joint[stable_sim.LIFT_JOINT]] = self._lift_command_q

    def _measured_gripper_opening(self, side: str) -> float:
        primary, follower = stable_sim.GRIPPER_JOINTS[side]
        return float(
            np.clip(
                0.5
                * (
                    self.data.qpos[self.mj_qpos[primary]]
                    - self.data.qpos[self.mj_qpos[follower]]
                ),
                stable_sim.GRIPPER_CLOSED_M,
                stable_sim.GRIPPER_OPEN_M,
            )
        )

    def _capture_grasp_assist_anchor(self, side: str, object_name: str) -> None:
        runtime = self.graspable_objects[object_name]
        tcp_id = self._mujoco_body_id(stable_sim.TCP_FRAMES[side])
        tcp_rotation = self.data.xmat[tcp_id].reshape(3, 3)
        relative_pos = tcp_rotation.T @ (
            self.data.xpos[runtime.body_id] - self.data.xpos[tcp_id]
        )
        self._grasp_assist_anchor[side] = (object_name, relative_pos.copy())

    def _apply_grasp_assist_forces(self) -> None:
        # 只补偿已经形成双指接触的物体，不直接修改物体位姿。
        for runtime in self.graspable_objects.values():
            self.data.xfrc_applied[runtime.body_id] = 0.0

        for side, anchor in self._grasp_assist_anchor.items():
            if anchor is None:
                continue
            object_name, relative_pos = anchor
            contact_hold = self._gripper_contact_hold[side]
            if contact_hold is None or contact_hold[0] != object_name:
                continue

            runtime = self.graspable_objects[object_name]
            tcp_id = self._mujoco_body_id(stable_sim.TCP_FRAMES[side])
            tcp_rotation = self.data.xmat[tcp_id].reshape(3, 3)
            target_pos = self.data.xpos[tcp_id] + tcp_rotation @ relative_pos
            _, dof_address = self._free_joint_addresses(runtime.body_id)
            linear_velocity = self.data.qvel[dof_address : dof_address + 3]
            force = (
                GRASP_ASSIST_KP_N_M * (target_pos - self.data.xpos[runtime.body_id])
                - GRASP_ASSIST_KD_N_S_M * linear_velocity
                - self.model.body_mass[runtime.body_id] * self.model.opt.gravity
            )
            left_finger = self._finger_bodies[side]["left"]
            right_finger = self._finger_bodies[side]["right"]
            closing_axis = self.data.xpos[right_finger] - self.data.xpos[left_finger]
            closing_axis_norm = float(np.linalg.norm(closing_axis))
            if closing_axis_norm > 1e-9:
                closing_axis /= closing_axis_norm
                force -= float(np.dot(force, closing_axis)) * closing_axis
            force_norm = float(np.linalg.norm(force))
            if force_norm > GRASP_ASSIST_MAX_FORCE_N:
                force *= GRASP_ASSIST_MAX_FORCE_N / force_norm
            self.data.xfrc_applied[runtime.body_id, :3] += force

    def _set_gripper(self, side: str, opening_m: float) -> None:
        opening_m = float(
            np.clip(opening_m, stable_sim.GRIPPER_CLOSED_M, stable_sim.GRIPPER_OPEN_M)
        )
        if not self._physics_ready:
            super()._set_gripper(side, opening_m)
            return
        primary, follower = stable_sim.GRIPPER_JOINTS[side]
        command_sim_s = float(self.data.time)
        if opening_m > stable_sim.GRIPPER_CLOSED_M:
            self._gripper_contact_hold[side] = None
            self._gripper_contact_loss_steps[side] = 0
            self._grasp_assist_anchor[side] = None
            actuator_target_m = opening_m
            self._gripper_command_opening_m[side] = actuator_target_m
            self._gripper_last_command_sim_s[side] = command_sim_s
        else:
            contacts = self._finger_contacts()
            contact_hold = self._gripper_contact_hold[side]
            if contact_hold is not None:
                object_name, actuator_target_m = contact_hold
                if contacts.get((side, object_name)):
                    self._gripper_contact_loss_steps[side] = 0
                else:
                    self._gripper_contact_loss_steps[side] += 1
                    if self._gripper_contact_loss_steps[side] >= GRIPPER_CONTACT_LOSS_STEPS:
                        self._gripper_contact_hold[side] = None
                        self._grasp_assist_anchor[side] = None
                        contact_hold = None

            if contact_hold is None:
                bilateral_object = next(
                    (
                        object_name
                        for (contact_side, object_name), fingers in contacts.items()
                        if contact_side == side and fingers == {"left", "right"}
                    ),
                    None,
                )
                measured_opening_m = self._measured_gripper_opening(side)
                if bilateral_object is not None:
                    actuator_target_m = max(
                        stable_sim.GRIPPER_CLOSED_M,
                        measured_opening_m - GRIPPER_CONTACT_PRELOAD_M,
                    )
                    self._gripper_contact_hold[side] = (
                        bilateral_object,
                        actuator_target_m,
                    )
                    self._gripper_contact_loss_steps[side] = 0
                    self._capture_grasp_assist_anchor(side, bilateral_object)
                    print(
                        f"[HEI Physics] {side} contact hold: {bilateral_object}, "
                        f"opening={actuator_target_m:.4f}m",
                        flush=True,
                    )
                else:
                    # 依据仿真时间渐进闭合，使速度不受 VR/渲染循环帧率影响。
                    # 命令开度独立于实际位置，两根手指始终获得对称目标。
                    command_dt_s = float(
                        np.clip(
                            command_sim_s - self._gripper_last_command_sim_s[side],
                            0.0,
                            GRIPPER_CLOSE_MAX_DT_S,
                        )
                    )
                    actuator_target_m = max(
                        stable_sim.GRIPPER_CLOSED_M,
                        self._gripper_command_opening_m[side]
                        - GRIPPER_CLOSE_SPEED_M_S * command_dt_s,
                    )

            self._gripper_command_opening_m[side] = actuator_target_m
            self._gripper_last_command_sim_s[side] = command_sim_s
        self.data.ctrl[self._actuator_by_joint[primary]] = actuator_target_m
        self.data.ctrl[self._actuator_by_joint[follower]] = -actuator_target_m
        self.gripper_target[side] = opening_m

    def _sync_robot_controls(self, *, include_arms: bool = True) -> None:
        if include_arms:
            for joint_name in (*stable_sim.RIGHT_ARM_JOINTS, *stable_sim.LEFT_ARM_JOINTS):
                actuator_id = self._actuator_by_joint[joint_name]
                self.data.ctrl[actuator_id] = self.data.qpos[self.mj_qpos[joint_name]]
        lift = stable_sim.LIFT_JOINT
        self._lift_command_q = float(self.data.qpos[self.mj_qpos[lift]])
        self.data.ctrl[self._actuator_by_joint[lift]] = self._lift_command_q

    def _reset_full_pose(self) -> None:
        # R 复位允许瞬时恢复初始场景；正常控制阶段只向执行器写目标位置。
        was_ready = self._physics_ready
        self._physics_ready = False
        try:
            super()._reset_full_pose()
        finally:
            self._physics_ready = was_ready
        if was_ready:
            self._physics_accumulator_s = 0.0
            self._arm_command_q = {
                "right": self._get_joint_q(stable_sim.RIGHT_ARM_JOINTS),
                "left": self._get_joint_q(stable_sim.LEFT_ARM_JOINTS),
            }
            self._gripper_command_opening_m = {
                side: self._measured_gripper_opening(side)
                for side in ("right", "left")
            }
            self._gripper_last_command_sim_s = {
                "right": float(self.data.time),
                "left": float(self.data.time),
            }
            self._grasp_assist_anchor = {"right": None, "left": None}
            self.data.xfrc_applied[:] = 0.0
            self._sync_robot_controls()
            self._apply_kinematic_robot_pose()
            mujoco.mj_forward(self.model, self.data)

    def _advance_physics(self, dt: float) -> None:
        timestep_s = float(self.model.opt.timestep)
        self._physics_accumulator_s += float(np.clip(dt, 0.0, 0.05))
        while self._physics_accumulator_s >= timestep_s:
            self._apply_kinematic_robot_pose()
            self._apply_grasp_assist_forces()
            mujoco.mj_step(self.model, self.data)
            self._physics_accumulator_s -= timestep_s
        # 丢弃物理求解器对双臂和升降造成的偏移，但保留传递给物体的接触响应。
        self._apply_kinematic_robot_pose()
        mujoco.mj_forward(self.model, self.data)

    def _step_control(self, dt: float) -> tuple[bool, int]:
        controllers, fresh, packet_count = self._snapshot_vr()
        with self.data_lock:
            self._handle_buttons(controllers)
            self._step_sim_chassis(controllers, fresh, dt)
            for side in ("right", "left"):
                arm = self.arms[side]
                controller = controllers[side]
                if controller["gripActive"]:
                    self._update_arm_target(arm, controller, dt)
                    target = (
                        stable_sim.GRIPPER_OPEN_M
                        if controller["trigger"]
                        else stable_sim.GRIPPER_CLOSED_M
                    )
                    self._set_gripper(side, target)
                    self._solve_arm(arm, dt)
                else:
                    self._release_controller_origin(arm)
                    self._step_reset(arm)

            left = controllers["left"]
            lift_axis = self._deadzone(left["thumbstick"]["y"], stable_sim.LIFT_DEADZONE)
            if not left["gripActive"]:
                lift_axis = 0.0
            lift_id = self._mujoco_joint_id(stable_sim.LIFT_JOINT)
            low, high = self.model.jnt_range[lift_id]
            lift_address = self.mj_qpos[stable_sim.LIFT_JOINT]
            current_lift = float(self.data.qpos[lift_address])
            self.data.qpos[lift_address] = np.clip(
                current_lift - lift_axis * self.args.lift_speed_m_s * dt,
                low,
                high,
            )
            self.data.qvel[int(self.model.jnt_dofadr[lift_id])] = 0.0
            self._sync_robot_controls(include_arms=False)
            mujoco.mj_forward(self.model, self.data)
            self._advance_physics(dt)
            self._update_physical_grasp_events()
        return fresh, packet_count

    def _finger_contacts(self) -> dict[tuple[str, str], set[str]]:
        object_by_body = {
            runtime.body_id: runtime.spec.body_name for runtime in self.graspable_objects.values()
        }
        finger_by_body = {
            body_id: (side, finger)
            for side, fingers in self._finger_bodies.items()
            for finger, body_id in fingers.items()
        }
        contacts: dict[tuple[str, str], set[str]] = {}
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            body_1 = int(self.model.geom_bodyid[contact.geom1])
            body_2 = int(self.model.geom_bodyid[contact.geom2])
            for finger_body, object_body in ((body_1, body_2), (body_2, body_1)):
                finger_info = finger_by_body.get(finger_body)
                object_name = object_by_body.get(object_body)
                if finger_info is None or object_name is None:
                    continue
                side, finger = finger_info
                contacts.setdefault((side, object_name), set()).add(finger)
        return contacts

    def _update_physical_grasp_events(self) -> None:
        contacts = self._finger_contacts()
        current_grasps: set[tuple[str, str]] = set()
        for key, fingers in contacts.items():
            side, object_name = key
            runtime = self.graspable_objects[object_name]
            support_height_m = self._object_support_height(runtime)
            lifted = (
                float(self.data.xpos[runtime.body_id, 2])
                > stable_sim.TABLE_TOP_Z_M + support_height_m + 0.025
            )
            if fingers == {"left", "right"} and lifted:
                current_grasps.add(key)
                if key not in self._physical_grasps:
                    print(
                        f"[HEI Physics] physical grasp confirmed: {side}:{object_name}",
                        flush=True,
                    )
        for side, object_name in self._physical_grasps - current_grasps:
            print(f"[HEI Physics] object released/dropped: {side}:{object_name}", flush=True)
        self._physical_grasps = current_grasps

    def _keyboard_callback(self, keycode: int) -> None:
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "C" and self.viewer is not None:
            self._contact_debug_enabled = not self._contact_debug_enabled
            enabled = self._contact_debug_enabled
            self.viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = enabled
            self.viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = enabled
            print(f"[HEI Physics] contact visualization {'on' if enabled else 'off'}", flush=True)
            return
        super()._keyboard_callback(keycode)

    def _print_status(self, fresh: bool, packet_count: int) -> None:
        previous_status_s = self.last_status_s
        super()._print_status(fresh, packet_count)
        if self.last_status_s == previous_status_s:
            return
        contacts = self._finger_contacts()
        contact_text = ",".join(
            f"{side}:{name.removeprefix('hei_object_')}[{'+'.join(sorted(fingers))}]"
            for (side, name), fingers in contacts.items()
        ) or "none"
        heights = ",".join(
            f"{runtime.spec.body_name.removeprefix('hei_object_')}={self.data.xpos[runtime.body_id, 2]:.3f}m"
            for runtime in self.graspable_objects.values()
        )
        print(
            f"[HEI Physics] contacts={contact_text} object_z=({heights}) "
            f"confirmed_grasps={len(self._physical_grasps)}",
            flush=True,
        )

    def headless_check(self) -> None:
        if self.model.nu != 17:
            raise RuntimeError(f"Expected 17 physical position actuators, got {self.model.nu}")
        if any(runtime.held_by is not None for runtime in self.graspable_objects.values()):
            raise RuntimeError("Physical mode must never attach an object to a TCP")

        arm_joint_id = self._mujoco_joint_id(stable_sim.RIGHT_ARM_JOINTS[0])
        arm_body_id = int(self.model.jnt_bodyid[arm_joint_id])
        expected_gravcomp = 1.0 - self.args.robot_gravity_scale
        if not np.isclose(self.model.body_gravcomp[arm_body_id], expected_gravcomp):
            raise RuntimeError("Robot gravity compensation was not applied")
        for runtime in self.graspable_objects.values():
            if not np.isclose(self.model.body_gravcomp[runtime.body_id], 0.0):
                raise RuntimeError("Free objects must retain normal gravity")

        original_arm_q = self._get_joint_q(stable_sim.RIGHT_ARM_JOINTS)
        test_arm_q = original_arm_q.copy()
        test_arm_q[0] += 0.01
        self._set_joint_q(stable_sim.RIGHT_ARM_JOINTS, test_arm_q)
        self._advance_physics(0.02)
        if not np.allclose(
            self._get_joint_q(stable_sim.RIGHT_ARM_JOINTS),
            test_arm_q,
            atol=1e-9,
        ):
            raise RuntimeError("Kinematic arm did not track the IK joint command exactly")
        self._set_joint_q(stable_sim.RIGHT_ARM_JOINTS, original_arm_q)
        print("[HEI Physics] kinematic arm tracking self-check passed", flush=True)

        primary, follower = stable_sim.GRIPPER_JOINTS["right"]
        primary_address = self.mj_qpos[primary]
        follower_address = self.mj_qpos[follower]
        initial_fingers = self.data.qpos[[primary_address, follower_address]].copy()
        self._set_gripper("right", stable_sim.GRIPPER_OPEN_M)
        if not np.array_equal(
            self.data.qpos[[primary_address, follower_address]],
            initial_fingers,
        ):
            raise RuntimeError("Physical gripper command changed qpos without simulation")
        for _ in range(50):
            self._advance_physics(0.02)
        opened_fingers = self.data.qpos[[primary_address, follower_address]]
        expected_open = np.array(
            [stable_sim.GRIPPER_OPEN_M, -stable_sim.GRIPPER_OPEN_M]
        )
        if not np.allclose(opened_fingers, expected_open, atol=0.005):
            raise RuntimeError(f"Physical gripper did not open: qpos={opened_fingers}")

        for _ in range(100):
            self._set_gripper("right", stable_sim.GRIPPER_CLOSED_M)
            self._advance_physics(0.02)
        closed_fingers = self.data.qpos[[primary_address, follower_address]]
        closed_opening_m = self._measured_gripper_opening("right")
        closed_ctrl = self.data.ctrl[
            [self._actuator_by_joint[primary], self._actuator_by_joint[follower]]
        ]
        if closed_opening_m > 0.005 or not np.allclose(closed_ctrl, 0.0, atol=1e-9):
            raise RuntimeError(
                "Physical gripper did not close: "
                f"opening={closed_opening_m:.4f}m, qpos={closed_fingers}, ctrl={closed_ctrl}"
            )
        print("[HEI Physics] force-limited gripper actuator self-check passed", flush=True)

        runtime = self.graspable_objects["hei_object_cube_red"]
        qpos_address, dof_address = self._free_joint_addresses(runtime.body_id)
        self._set_gripper("right", stable_sim.GRIPPER_OPEN_M)
        for _ in range(50):
            self._advance_physics(0.02)

        left_pad_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_GEOM,
            "a_right_end_link_L_finger_contact_pad",
        )
        right_pad_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_GEOM,
            "a_right_end_link_R_finger_contact_pad",
        )
        if left_pad_id < 0 or right_pad_id < 0:
            raise RuntimeError("Physical gripper contact pads are missing")

        saved_gravity = self.model.opt.gravity.copy()
        self.model.opt.gravity[:] = 0.0
        grasp_center = 0.5 * (
            self.data.geom_xpos[left_pad_id] + self.data.geom_xpos[right_pad_id]
        )
        self.data.qpos[qpos_address : qpos_address + 3] = grasp_center
        self.data.qpos[qpos_address + 3 : qpos_address + 7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qvel[dof_address : dof_address + 6] = 0.0
        mujoco.mj_forward(self.model, self.data)
        for _ in range(100):
            self._set_gripper("right", stable_sim.GRIPPER_CLOSED_M)
            self._advance_physics(0.02)
        if self._gripper_contact_hold["right"] is None:
            raise RuntimeError("Physical gripper failed to establish bilateral contact hold")

        held_start_z = float(self.data.xpos[runtime.body_id, 2])
        self.model.opt.gravity[:] = saved_gravity
        for _ in range(50):
            self._set_gripper("right", stable_sim.GRIPPER_CLOSED_M)
            self._advance_physics(0.02)
        held_end_z = float(self.data.xpos[runtime.body_id, 2])
        if self._gripper_contact_hold["right"] is None or held_start_z - held_end_z > 0.02:
            raise RuntimeError(
                "Physical gripper failed to support the cube: "
                f"z={held_start_z:.3f}m -> {held_end_z:.3f}m"
            )

        self._set_gripper("right", stable_sim.GRIPPER_OPEN_M)
        for _ in range(50):
            self._advance_physics(0.02)
        released_z = float(self.data.xpos[runtime.body_id, 2])
        if released_z >= held_end_z - 0.10:
            raise RuntimeError("Released cube did not fall after opening the gripper")
        print(
            f"[HEI Physics] grasp support/release self-check passed: "
            f"held_drop={held_start_z - held_end_z:.4f}m",
            flush=True,
        )

        self._reset_full_pose()
        runtime = self.graspable_objects["hei_object_cube_red"]
        qpos_address, dof_address = self._free_joint_addresses(runtime.body_id)
        support_height_m = self._object_support_height(runtime)
        start_z = stable_sim.TABLE_TOP_Z_M + support_height_m + 0.25
        self.data.qpos[qpos_address : qpos_address + 3] = [0.70, -0.28, start_z]
        self.data.qpos[qpos_address + 3 : qpos_address + 7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qvel[dof_address : dof_address + 6] = 0.0
        mujoco.mj_forward(self.model, self.data)
        initial_z = float(self.data.xpos[runtime.body_id, 2])
        for _ in range(50):
            self._advance_physics(0.02)
        final_z = float(self.data.xpos[runtime.body_id, 2])
        expected_z = stable_sim.TABLE_TOP_Z_M + support_height_m
        if final_z >= initial_z - 0.05:
            raise RuntimeError("Physical object did not fall under gravity")
        if abs(final_z - expected_z) > 0.02:
            raise RuntimeError(
                f"Physical object did not settle on table: z={final_z:.3f}, expected={expected_z:.3f}"
            )
        if self.data.ncon <= 0:
            raise RuntimeError("Physical scene produced no contacts")
        print(
            f"[HEI Physics] gravity/contact self-check passed: {initial_z:.3f}m -> {final_z:.3f}m",
            flush=True,
        )
        self.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate HEI grasping with MuJoCo contacts instead of stable TCP attachment."
    )
    parser.add_argument("--model", type=Path, default=stable_sim.DEFAULT_URDF)
    parser.add_argument("--vr-endpoint", default=stable_sim.DEFAULT_VR_ENDPOINT)
    parser.add_argument("--vr-pos-scale", type=float, default=1.0)
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20)
    parser.add_argument("--vr-timeout-s", type=float, default=stable_sim.VR_STALE_TIMEOUT_S)
    parser.add_argument("--physics-timestep-s", type=float, default=0.002)
    parser.add_argument("--object-friction", type=float, default=1.0)
    parser.add_argument("--gripper-force-n", type=float, default=18.0)
    parser.add_argument(
        "--robot-gravity-scale",
        type=float,
        default=0.0,
        help="Robot gravity fraction: 0 disables robot weight, 1 uses full URDF weight.",
    )
    parser.add_argument("--headless-check", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    args.plain_scene = False
    if args.physics_timestep_s <= 0.0:
        parser.error("--physics-timestep-s must be positive")
    if args.object_friction <= 0.0:
        parser.error("--object-friction must be positive")
    if args.gripper_force_n <= 0.0:
        parser.error("--gripper-force-n must be positive")
    if not 0.0 <= args.robot_gravity_scale <= 1.0:
        parser.error("--robot-gravity-scale must be between 0 and 1")
    return args


def main() -> None:
    simulator = HEIRobotVRPhysicsSimulator(parse_args())
    if simulator.args.headless_check:
        simulator.headless_check()
    else:
        print(
            "[HEI Physics] physical validation mode; C toggles contact points, R resets the scene",
            flush=True,
        )
        simulator.run()


if __name__ == "__main__":
    main()
