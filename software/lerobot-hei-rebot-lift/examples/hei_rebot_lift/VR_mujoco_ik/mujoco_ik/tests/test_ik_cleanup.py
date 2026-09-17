"""Exercise IK output contracts without motors, sockets, or a viewer."""

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import pinocchio_kinematic


class FakeOpti:
    def __init__(self, solution):
        self.solution = solution.copy()
        self.fail = False
        self.debug = self
        self.initial = None
        self.parameters = {}

    def set_initial(self, variable, value):
        self.initial = value.copy()

    def set_value(self, parameter, value):
        self.parameters[parameter] = value.copy()

    def solve(self):
        if self.fail:
            raise RuntimeError("simulated solve failure")

    def value(self, variable):
        return self.solution.copy()


class IKCleanupTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "IK_MAX_STEP_FIRST_TWO": "0.06",
            "IK_MAX_STEP_OTHER": "0.12",
        })
        env.start()
        self.addCleanup(env.stop)
        dynamics = patch.object(
            pinocchio_kinematic.pin,
            "rnea",
            side_effect=AssertionError("position-only IK must not calculate torque"),
        )
        self.rnea = dynamics.start()
        self.addCleanup(dynamics.stop)
        self.solver = pinocchio_kinematic.Kinematics("test_tcp")
        self.solver.model = SimpleNamespace(
            nq=6,
            nv=6,
            lowerPositionLimit=np.full(6, -1.4),
            upperPositionLimit=np.full(6, 1.57),
        )
        self.solver.init_data = np.zeros(6)
        self.raw_q = np.array([0.3, -0.3, 0.4, -0.4, 0.5, -0.5])
        self.solver.opti = FakeOpti(self.raw_q)
        self.solver.var_q = object()
        self.solver.var_q_last = object()
        self.solver.param_tf = object()

    def tearDown(self):
        self.rnea.assert_not_called()

    def test_success_keeps_step_limits_and_raw_diagnostics(self):
        q, info = self.solver.ik(np.eye(4), np.zeros(6))
        expected = np.array([0.06, -0.06, 0.12, -0.12, 0.12, -0.12])
        np.testing.assert_allclose(q, expected)
        np.testing.assert_allclose(self.solver.init_data, expected)
        np.testing.assert_array_equal(info["raw_solution"], self.raw_q)
        np.testing.assert_array_equal(info["sol_tauff"], np.zeros(6))
        self.assertTrue(info["success"])
        self.assertTrue(info["clamped"])

    def test_small_solution_is_not_clamped(self):
        self.solver.opti.solution = np.full(6, 0.01)
        q, info = self.solver.ik(np.eye(4), np.zeros(6))
        np.testing.assert_array_equal(q, np.full(6, 0.01))
        self.assertTrue(info["success"])
        self.assertFalse(info["clamped"])

    def test_feedback_still_sets_warm_start_and_joint_bounds(self):
        current = np.full(6, 1.56)
        self.solver.opti.solution = np.full(6, 1.7)
        q, info = self.solver.ik(np.eye(4), current)
        np.testing.assert_array_equal(self.solver.opti.initial, current)
        np.testing.assert_array_equal(
            self.solver.opti.parameters[self.solver.var_q_last], current
        )
        np.testing.assert_allclose(q, np.full(6, 1.57))
        self.assertTrue(info["clamped"])

    def test_legacy_velocity_argument_does_not_change_position_output(self):
        q, info = self.solver.ik(np.eye(4), np.zeros(6))
        with_velocity, velocity_info = self.solver.ik(
            np.eye(4), np.zeros(6), np.full(6, 0.5)
        )
        np.testing.assert_array_equal(q, with_velocity)
        np.testing.assert_array_equal(info["raw_solution"], velocity_info["raw_solution"])

    def test_failure_with_feedback_holds_current_position(self):
        self.solver.opti.fail = True
        current = np.linspace(-0.1, 0.1, 6)
        with contextlib.redirect_stdout(io.StringIO()):
            q, info = self.solver.ik(np.eye(4), current)
        np.testing.assert_array_equal(q, current)
        np.testing.assert_array_equal(self.solver.init_data, current)
        np.testing.assert_array_equal(info["sol_tauff"], np.zeros(6))
        self.assertFalse(info["success"])
        self.assertFalse(info["clamped"])
        self.assertNotIn("raw_solution", info)

    def test_failure_without_feedback_keeps_existing_debug_fallback(self):
        self.solver.opti.fail = True
        with contextlib.redirect_stdout(io.StringIO()):
            q, info = self.solver.ik(np.eye(4))
        np.testing.assert_array_equal(q, self.raw_q)
        np.testing.assert_array_equal(self.solver.init_data, self.raw_q)
        self.assertFalse(info["success"])

    def test_reduced_model_preserves_inactive_joint_values(self):
        self.solver.full_model_nq = 10
        self.solver.active_q_indices = np.array([1, 2, 4, 5, 7, 9])
        self.solver.reference_q = np.zeros(10)
        current = np.linspace(-0.2, 0.2, 10)
        q, info = self.solver.ik(np.eye(4), current)
        active = self.solver.active_q_indices
        expected = current.copy()
        steps = np.array([0.06, 0.06, 0.12, 0.12, 0.12, 0.12])
        expected[active] += np.clip(self.raw_q - current[active], -steps, steps)
        np.testing.assert_allclose(q, expected)
        expected_raw = current.copy()
        expected_raw[active] = self.raw_q
        np.testing.assert_array_equal(info["raw_solution"], expected_raw)
        np.testing.assert_array_equal(info["sol_tauff"], np.zeros(6))


if __name__ == "__main__":
    unittest.main()
