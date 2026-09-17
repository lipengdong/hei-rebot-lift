"""Offline regression tests: no viewer, sockets, or motor commands are created."""

import argparse
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hei_robot_vr_mujoco_sim import ArmRuntime, HEIRobotVRSimulator, MAX_MUJOCO_JOINT_STEP_RAD


class FakeSolver:
    def __init__(self):
        self.solution = np.zeros(6)
        self.raw_solution = np.zeros(6)
        self.init_data = np.zeros(6)

    def fk(self, q):
        transform = np.eye(4)
        transform[:3, 3] = np.asarray(q)[:3]
        return transform

    def ik(self, target, current):
        self.init_data = self.solution.copy()
        return self.solution.copy(), {"success": True, "raw_solution": self.raw_solution.copy()}


class BoundedWorkspaceSolver(FakeSolver):
    """用一维工作空间模拟真实 IK：x <= 15 mm 可达，超出后产生跳解。"""

    def ik(self, target, current):
        target_x = float(target[0, 3])
        candidate = np.zeros(6)
        candidate[0] = min(target_x, 0.015)
        if target_x > 0.015 + 1e-9:
            candidate[5] = 1.0
        self.solution = candidate.copy()
        self.raw_solution = candidate.copy()
        self.init_data = candidate.copy()
        return candidate.copy(), {"success": True, "raw_solution": candidate.copy()}


class IKTargetGuardTest(unittest.TestCase):
    def setUp(self):
        self.q = np.zeros(6)
        self.solver = FakeSolver()
        self.controller = object.__new__(HEIRobotVRSimulator)
        self.controller.args = argparse.Namespace(vr_pos_scale=1.0)
        self.controller._get_joint_q = lambda names: self.q.copy()
        self.controller._set_joint_q = self.set_q
        self.arm = ArmRuntime(
            side="right",
            solver=self.solver,
            pin_q_indices=np.arange(6),
            target_tf=np.eye(4),
            controller_origin_pos={"x": 0.0, "y": 0.0, "z": 0.0},
            controller_origin_quat={"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            robot_origin_tf=np.eye(4),
            controller_origin_q=np.zeros(6),
            settle_steps_remaining=8,
            last_accepted_ik_q=np.zeros(6),
            last_accepted_target_tf=np.eye(4),
        )

    def set_q(self, names, values):
        self.q = np.asarray(values).copy()

    def test_normal_command_keeps_original_step_limit(self):
        candidate = np.array([0.01, 0.01, 0.01, 0.12, 0.12, 0.12])
        self.solver.solution = candidate
        self.solver.raw_solution = candidate
        self.arm.target_tf = self.solver.fk(candidate)
        self.controller._solve_arm(self.arm)
        np.testing.assert_allclose(
            self.q, np.clip(candidate, -MAX_MUJOCO_JOINT_STEP_RAD, MAX_MUJOCO_JOINT_STEP_RAD)
        )
        np.testing.assert_array_equal(self.arm.last_accepted_ik_q, candidate)

    def test_clipped_output_cannot_hide_raw_wrist_jump(self):
        self.solver.solution[5] = -0.12
        self.solver.raw_solution[5] = -1.7
        self.controller._solve_arm(self.arm)
        np.testing.assert_array_equal(self.q, np.zeros(6))
        np.testing.assert_array_equal(self.solver.init_data, self.q)
        np.testing.assert_array_equal(self.arm.last_accepted_ik_q, np.zeros(6))
        self.assertEqual(self.arm.settle_steps_remaining, 0)

    def test_reject_helper_holds_current_pose(self):
        self.arm.target_tf[0, 3] = 0.03
        self.controller._reject_arm_target(self.arm, self.q, "test rejection")
        np.testing.assert_array_equal(self.q, np.zeros(6))
        np.testing.assert_allclose(self.arm.target_tf, self.solver.fk(self.q))

    def test_position_error_at_twenty_mm_is_allowed(self):
        self.arm.target_tf[0, 3] = 0.02
        self.controller._solve_arm(self.arm)
        np.testing.assert_array_equal(self.arm.last_accepted_ik_q, np.zeros(6))

    def test_return_to_workspace_resumes_without_grip_release(self):
        self.arm.target_tf[0, 3] = 0.03
        self.controller._solve_arm(self.arm)
        controller = {
            "position": {"x": 0.0, "y": 0.0, "z": -0.01},
            "quaternion": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        self.solver.solution[0] = 0.01
        self.solver.raw_solution[0] = 0.01
        self.controller._update_arm_target(self.arm, controller)
        self.controller._solve_arm(self.arm)
        self.assertAlmostEqual(self.q[0], 0.01)
        self.assertIsNotNone(self.arm.controller_origin_pos)
        self.assertAlmostEqual(self.arm.last_accepted_ik_q[0], 0.01)

    def test_rejected_target_is_retried_immediately(self):
        self.arm.target_tf[0, 3] = 0.03
        rejected_target = self.arm.target_tf.copy()
        self.controller._solve_arm(self.arm)
        self.assertTrue(self.controller._target_changed(self.arm, rejected_target))

    def test_rejection_continues_toward_last_safe_solution(self):
        self.arm.last_accepted_ik_q[0] = 0.16
        self.arm.target_tf[0, 3] = 0.03
        self.controller._reject_arm_target(self.arm, self.q, "test rejection")
        self.assertAlmostEqual(self.q[0], MAX_MUJOCO_JOINT_STEP_RAD)

    def test_unreachable_target_is_projected_to_workspace_boundary(self):
        solver = BoundedWorkspaceSolver()
        self.arm.solver = solver
        self.arm.target_tf[0, 3] = 0.03
        self.controller._solve_arm(self.arm)
        self.assertGreater(self.arm.last_accepted_target_tf[0, 3], 0.0)
        self.assertLessEqual(self.arm.last_accepted_target_tf[0, 3], 0.015 + 1e-9)
        self.assertAlmostEqual(self.arm.last_accepted_target_tf[0, 3], 0.015, places=6)
        self.assertAlmostEqual(self.q[0], 0.015, places=6)
        requested = np.eye(4)
        requested[0, 3] = 0.03
        self.assertTrue(self.controller._target_changed(self.arm, requested))

    def test_target_interpolation_uses_shortest_rotation_path(self):
        start = np.eye(4)
        end = np.eye(4)
        end[0, 3] = 0.10
        end[:3, :3] = np.array(
            [
                [0.0, -1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        midpoint = self.controller._interpolate_target(start, end, 0.5)
        self.assertAlmostEqual(midpoint[0, 3], 0.05)
        self.assertAlmostEqual(self.controller._rotation_delta_angle(start, midpoint), np.pi / 4)

    def test_fast_return_toward_grip_origin_bypasses_jump_rejection(self):
        self.arm.last_accepted_target_tf[0, 3] = 0.20
        self.arm.last_accepted_ik_q[4] = 1.0
        self.arm.target_tf[0, 3] = 0.05
        candidate = np.zeros(6)
        candidate[0] = 0.05
        candidate[4] = 0.10
        self.assertIsNone(self.controller._candidate_rejection_reason(self.arm, self.q, candidate))

    def test_fast_return_extends_settling_without_changing_step_size(self):
        self.controller._rotation_delta_angle = lambda first, second: 1.0
        self.q[4] = 1.0
        self.arm.last_accepted_target_tf[0, 3] = 0.20
        self.arm.last_accepted_ik_q[4] = 1.0
        self.arm.target_tf[0, 3] = 0.05
        self.solver.solution[0] = 0.05
        self.solver.solution[4] = 0.10
        self.solver.raw_solution = self.solver.solution.copy()
        self.controller._solve_arm(self.arm)
        self.assertGreater(self.arm.settle_steps_remaining, 8)
        self.assertAlmostEqual(self.q[4], 1.0 - MAX_MUJOCO_JOINT_STEP_RAD)

    def test_nonfinite_raw_solution_is_rejected(self):
        candidate = np.zeros(6)
        candidate[5] = np.nan
        self.assertIsNotNone(self.controller._candidate_rejection_reason(self.arm, self.q, candidate))


if __name__ == "__main__":
    unittest.main()
