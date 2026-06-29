#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
from functools import cached_property
from itertools import chain
from typing import Any

import draccus
import numpy as np

from lerobot.cameras import make_cameras_from_configs
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import (
    FeetechMotorsBus,
    OperatingMode,
)
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from ..utils import ensure_safe_goal_position
from .config_lekiwi import LeKiwiConfig

logger = logging.getLogger(__name__)


class LeKiwi(Robot):
    """
    The robot includes a three omniwheel mobile base and a remote follower arm.
    The leader arm is connected locally (on the laptop) and its joint positions are recorded and then
    forwarded to the remote follower arm (after applying a safety clamp).
    In parallel, keyboard teleoperation is used to generate raw velocity commands for the wheels.
    """

    config_class = LeKiwiConfig
    name = "lekiwi"

    def __init__(self, config: LeKiwiConfig):
        super().__init__(config)
        self.config = config

        self.height_goal_vel = 0.0
        self.yao_goal_vel = 0.0

        self.left_calibration_fpath = self.calibration_dir / f"{self.id}_left.json"
        self.right_calibration_fpath = self.calibration_dir / f"{self.id}_right.json"

        self.left_calibration: dict[str, MotorCalibration] = {}
        if self.left_calibration_fpath.is_file():
            self._load_left_calibration()

        self.right_calibration: dict[str, MotorCalibration] = {}
        if self.right_calibration_fpath.is_file():
            self._load_right_calibration()

        norm_mode_body = MotorNormMode.DEGREES if config.use_degrees else MotorNormMode.RANGE_M100_100
        self.bus = FeetechMotorsBus(
            port=self.config.left_port,
            motors={
                # left arm
                "left_arm_shoulder_pan": Motor(1, "sts3230", norm_mode_body),
                "left_arm_shoulder_lift": Motor(2, "sts3230", norm_mode_body),
                "left_arm_elbow_flex": Motor(3, "sts3230", norm_mode_body),
                "left_arm_wrist_flex": Motor(4, "sts3230", norm_mode_body),
                "left_arm_wrist_roll": Motor(5, "sts3250", norm_mode_body),
                "left_arm_wrist_x": Motor(6, "sts3250", norm_mode_body),
                "left_arm_wrist_y": Motor(7, "sts3250", norm_mode_body),
                "left_arm_gripper": Motor(8, "sts3250", MotorNormMode.RANGE_0_100),
                # base
                "base_left_wheel": Motor(9, "sts3230", MotorNormMode.RANGE_M100_100),
                "base_back_wheel": Motor(10, "sts3230", MotorNormMode.RANGE_M100_100),
                "base_right_wheel": Motor(11, "sts3230", MotorNormMode.RANGE_M100_100),
            },
            calibration=self.left_calibration,
        )
        self.left_arm_motors = [motor for motor in self.bus.motors if motor.startswith("left_arm")]
        self.base_motors = [motor for motor in self.bus.motors if motor.startswith("base")]
        self.cameras = make_cameras_from_configs(config.cameras)
        self.right_arm_bus = FeetechMotorsBus(
            port=self.config.right_port,
            motors={
                "right_arm_shoulder_pan": Motor(1, "sts3230", norm_mode_body),
                "right_arm_shoulder_lift": Motor(2, "sts3230", norm_mode_body),
                "right_arm_elbow_flex": Motor(3, "sts3230", norm_mode_body),
                "right_arm_wrist_flex": Motor(4, "sts3230", norm_mode_body),
                "right_arm_wrist_roll": Motor(5, "sts3250", norm_mode_body),
                "right_arm_wrist_x": Motor(6, "sts3250", norm_mode_body),
                "right_arm_wrist_y": Motor(7, "sts3250", norm_mode_body),
                "right_arm_gripper": Motor(8, "sts3250", MotorNormMode.RANGE_0_100),
            },
            calibration=self.right_calibration,
        )
        self.right_arm_motors = [
            motor for motor in self.right_arm_bus.motors if motor.startswith("right_arm")
        ]

    @property
    def _state_ft(self) -> dict[str, type]:
        return dict.fromkeys(
            (
                "left_arm_shoulder_pan.pos",
                "left_arm_shoulder_lift.pos",
                "left_arm_elbow_flex.pos",
                "left_arm_wrist_flex.pos",
                "left_arm_wrist_roll.pos",
                "left_arm_wrist_x.pos",
                "left_arm_wrist_y.pos",
                "left_arm_gripper.pos",
                "right_arm_shoulder_pan.pos",
                "right_arm_shoulder_lift.pos",
                "right_arm_elbow_flex.pos",
                "right_arm_wrist_flex.pos",
                "right_arm_wrist_roll.pos",
                "right_arm_wrist_x.pos",
                "right_arm_wrist_y.pos",
                "right_arm_gripper.pos",
                "x.vel",
                "y.vel",
                "theta.vel",
                "height.vel",
                "yao.vel",
            ),
            float,
        )

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3) for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._state_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._state_ft

    @property
    def is_connected(self) -> bool:
        return (
            self.bus.is_connected
            and self.right_arm_bus.is_connected
            and all(cam.is_connected for cam in self.cameras.values())
        )

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        self.bus.connect()
        self.right_arm_bus.connect()
        if not self.is_calibrated and calibrate:
            logger.info(
                "Mismatch between calibration values in the motor and the calibration file or no calibration file found"
            )
            self.calibrate()

        for cam in self.cameras.values():
            cam.connect()

        self.configure()
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        return self.bus.is_calibrated and self.right_arm_bus.is_calibrated

    def calibrate(self) -> None:
        print("\n=== Start left arm calibration ===")
        if self.left_calibration:
            user_input = input(
                f"Press ENTER to use existing left calibration file {self.left_calibration_fpath.name}, or type 'c' and press ENTER to run a new calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(f"Writing left calibration file {self.left_calibration_fpath.name} to motors")
                self.bus.write_calibration(self.left_calibration)
            else:
                self._calibrate_left_arm()
        else:
            self._calibrate_left_arm()

        print("\n=== Start right arm calibration ===")
        if self.right_calibration:
            user_input = input(
                f"Press ENTER to use existing right calibration file {self.right_calibration_fpath.name}, or type 'c' and press ENTER to run a new calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(
                    f"Writing right calibration file {self.right_calibration_fpath.name} to motors"
                )
                self.right_arm_bus.write_calibration(self.right_calibration)
            else:
                self._calibrate_right_arm()
        else:
            self._calibrate_right_arm()

    def _load_left_calibration(self) -> None:
        with open(self.left_calibration_fpath) as f, draccus.config_type("json"):
            self.left_calibration = draccus.load(dict[str, MotorCalibration], f)

    def _load_right_calibration(self) -> None:
        with open(self.right_calibration_fpath) as f, draccus.config_type("json"):
            self.right_calibration = draccus.load(dict[str, MotorCalibration], f)

    def _save_left_calibration(self) -> None:
        with open(self.left_calibration_fpath, "w") as f, draccus.config_type("json"):
            draccus.dump(self.left_calibration, f, indent=4)

    def _save_right_calibration(self) -> None:
        with open(self.right_calibration_fpath, "w") as f, draccus.config_type("json"):
            draccus.dump(self.right_calibration, f, indent=4)

    def _calibrate_left_arm(self) -> None:
        logger.info(f"\nRunning left arm calibration of {self}")

        motors = self.left_arm_motors + self.base_motors

        self.bus.disable_torque(self.left_arm_motors)
        for name in self.left_arm_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.POSITION.value)

        input("Move robot to the middle of its range of motion and press ENTER....")
        homing_offsets = self.bus.set_half_turn_homings(self.left_arm_motors)

        homing_offsets.update(dict.fromkeys(self.base_motors, 0))

        full_turn_motor = [
            motor for motor in motors if any(keyword in motor for keyword in ["wheel", "wrist_roll"])
        ]
        unknown_range_motors = [motor for motor in motors if motor not in full_turn_motor]

        print(
            f"Move all arm joints except '{full_turn_motor}' sequentially through their "
            "entire ranges of motion.\nRecording positions. Press ENTER to stop..."
        )
        range_mins, range_maxes = self.bus.record_ranges_of_motion(unknown_range_motors)
        for name in full_turn_motor:
            range_mins[name] = 0
            range_maxes[name] = 4095

        self.left_calibration = {}
        for name, motor in self.bus.motors.items():
            self.left_calibration[name] = MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=homing_offsets[name],
                range_min=range_mins[name],
                range_max=range_maxes[name],
            )

        self.bus.write_calibration(self.left_calibration)
        self._save_left_calibration()
        print("Left calibration saved to", self.left_calibration_fpath)

    def _calibrate_right_arm(self) -> None:
        logger.info(f"\nRunning right arm calibration of {self}")

        motors = self.right_arm_motors

        self.right_arm_bus.disable_torque(self.right_arm_motors)
        for name in self.right_arm_motors:
            self.right_arm_bus.write("Operating_Mode", name, OperatingMode.POSITION.value)

        input("Move right arm to the middle of its range of motion and press ENTER....")
        homing_offsets = self.right_arm_bus.set_half_turn_homings(self.right_arm_motors)

        full_turn_motor = [motor for motor in motors if "wrist_roll" in motor]
        unknown_range_motors = [motor for motor in motors if motor not in full_turn_motor]

        print(
            f"Move all right arm joints except '{full_turn_motor}' sequentially through their "
            "entire ranges of motion.\nRecording positions. Press ENTER to stop..."
        )
        range_mins, range_maxes = self.right_arm_bus.record_ranges_of_motion(unknown_range_motors)
        for name in full_turn_motor:
            range_mins[name] = 0
            range_maxes[name] = 4095

        self.right_calibration = {}
        for name, motor in self.right_arm_bus.motors.items():
            self.right_calibration[name] = MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=homing_offsets[name],
                range_min=range_mins[name],
                range_max=range_maxes[name],
            )

        self.right_arm_bus.write_calibration(self.right_calibration)
        self._save_right_calibration()
        print("Right calibration saved to", self.right_calibration_fpath)

    def configure(self):
        # Set-up arm actuators (position mode)
        # We assume that at connection time, arm is in a rest position,
        # and torque can be safely disabled to run calibration.
        self.bus.disable_torque()
        self.bus.configure_motors()
        for name in self.left_arm_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.POSITION.value)
            self.bus.write("P_Coefficient", name, 10)
            self.bus.write("I_Coefficient", name, 0)
            self.bus.write("D_Coefficient", name, 0)

        for name in self.base_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)

        self.bus.enable_torque()

        self.right_arm_bus.disable_torque()
        self.right_arm_bus.configure_motors()
        for name in self.right_arm_motors:
            self.right_arm_bus.write("Operating_Mode", name, OperatingMode.POSITION.value)
            self.right_arm_bus.write("P_Coefficient", name, 10)
            self.right_arm_bus.write("I_Coefficient", name, 0)
            self.right_arm_bus.write("D_Coefficient", name, 0)

        self.right_arm_bus.enable_torque()

    def setup_motors(self) -> None:
        for motor in chain(reversed(self.left_arm_motors), reversed(self.base_motors)):
            input(f"Connect the left controller board to the '{motor}' motor only and press enter.")
            self.bus.setup_motor(motor)
            print(f"'{motor}' motor id set to {self.bus.motors[motor].id}")
        for motor in reversed(self.right_arm_motors):
            input(f"Connect the right controller board to the '{motor}' motor only and press enter.")
            self.right_arm_bus.setup_motor(motor)
            print(f"'{motor}' motor id set to {self.right_arm_bus.motors[motor].id}")

    @staticmethod
    def _degps_to_raw(degps: float) -> int:
        steps_per_deg = 4096.0 / 360.0
        speed_in_steps = degps * steps_per_deg
        speed_int = int(round(speed_in_steps))
        # Cap the value to fit within signed 16-bit range (-32768 to 32767)
        if speed_int > 0x7FFF:
            speed_int = 0x7FFF  # 32767 -> maximum positive value
        elif speed_int < -0x8000:
            speed_int = -0x8000  # -32768 -> minimum negative value
        return speed_int

    @staticmethod
    def _raw_to_degps(raw_speed: int) -> float:
        steps_per_deg = 4096.0 / 360.0
        magnitude = raw_speed
        degps = magnitude / steps_per_deg
        return degps

    def _body_to_wheel_raw(
        self,
        x: float,
        y: float,
        theta: float,
        wheel_radius: float = 0.05,
        base_radius: float = 0.125,
        max_raw: int = 3000,
    ) -> dict:
        """
        Convert desired body-frame velocities into wheel raw commands.

        Parameters:
          x_cmd      : Linear velocity in x (m/s).
          y_cmd      : Linear velocity in y (m/s).
          theta_cmd  : Rotational velocity (deg/s).
          wheel_radius: Radius of each wheel (meters).
          base_radius : Distance from the center of rotation to each wheel (meters).
          max_raw    : Maximum allowed raw command (ticks) per wheel.

        Returns:
          A dictionary with wheel raw commands:
             {"base_left_wheel": value, "base_back_wheel": value, "base_right_wheel": value}.

        Notes:
          - Internally, the method converts theta_cmd to rad/s for the kinematics.
          - The raw command is computed from the wheels angular speed in deg/s
            using _degps_to_raw(). If any command exceeds max_raw, all commands
            are scaled down proportionally.
        """
        # Convert rotational velocity from deg/s to rad/s.
        theta_rad = theta * (np.pi / 180.0)
        # Create the body velocity vector [x, y, theta_rad].
        velocity_vector = np.array([x, y, theta_rad])

        # Define the wheel mounting angles with a -90° offset.
        angles = np.radians(np.array([240, 0, 120]) - 90)
        # Build the kinematic matrix: each row maps body velocities to a wheel’s linear speed.
        # The third column (base_radius) accounts for the effect of rotation.
        m = np.array([[np.cos(a), np.sin(a), base_radius] for a in angles])

        # Compute each wheel’s linear speed (m/s) and then its angular speed (rad/s).
        wheel_linear_speeds = m.dot(velocity_vector)
        wheel_angular_speeds = wheel_linear_speeds / wheel_radius

        # Convert wheel angular speeds from rad/s to deg/s.
        wheel_degps = wheel_angular_speeds * (180.0 / np.pi)

        # Scaling
        steps_per_deg = 4096.0 / 360.0
        raw_floats = [abs(degps) * steps_per_deg for degps in wheel_degps]
        max_raw_computed = max(raw_floats)
        if max_raw_computed > max_raw:
            scale = max_raw / max_raw_computed
            wheel_degps = wheel_degps * scale

        # Convert each wheel’s angular speed (deg/s) to a raw integer.
        wheel_raw = [self._degps_to_raw(deg) for deg in wheel_degps]

        return {
            "base_left_wheel": wheel_raw[0],
            "base_back_wheel": wheel_raw[1],
            "base_right_wheel": wheel_raw[2],
        }

    def _wheel_raw_to_body(
        self,
        left_wheel_speed,
        back_wheel_speed,
        right_wheel_speed,
        wheel_radius: float = 0.05,
        base_radius: float = 0.125,
    ) -> dict[str, Any]:
        """
        Convert wheel raw command feedback back into body-frame velocities.

        Parameters:
          wheel_raw   : Vector with raw wheel commands ("base_left_wheel", "base_back_wheel", "base_right_wheel").
          wheel_radius: Radius of each wheel (meters).
          base_radius : Distance from the robot center to each wheel (meters).

        Returns:
          A dict (x.vel, y.vel, theta.vel) all in m/s
        """

        # Convert each raw command back to an angular speed in deg/s.
        wheel_degps = np.array(
            [
                self._raw_to_degps(left_wheel_speed),
                self._raw_to_degps(back_wheel_speed),
                self._raw_to_degps(right_wheel_speed),
            ]
        )

        # Convert from deg/s to rad/s.
        wheel_radps = wheel_degps * (np.pi / 180.0)
        # Compute each wheel’s linear speed (m/s) from its angular speed.
        wheel_linear_speeds = wheel_radps * wheel_radius

        # Define the wheel mounting angles with a -90° offset.
        angles = np.radians(np.array([240, 0, 120]) - 90)
        m = np.array([[np.cos(a), np.sin(a), base_radius] for a in angles])

        # Solve the inverse kinematics: body_velocity = M⁻¹ · wheel_linear_speeds.
        m_inv = np.linalg.inv(m)
        velocity_vector = m_inv.dot(wheel_linear_speeds)
        x, y, theta_rad = velocity_vector
        theta = theta_rad * (180.0 / np.pi)
        return {
            "x.vel": x,
            "y.vel": y,
            "theta.vel": theta,
        }  # m/s and deg/s

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        # Read actuators position for arm and vel for base
        start = time.perf_counter()
        arm_pos = self.bus.sync_read("Present_Position", self.left_arm_motors)
        right_arm_pos = self.right_arm_bus.sync_read("Present_Position", self.right_arm_motors)
        base_wheel_vel = self.bus.sync_read("Present_Velocity", self.base_motors)

        base_vel = self._wheel_raw_to_body(
            base_wheel_vel["base_left_wheel"],
            base_wheel_vel["base_back_wheel"],
            base_wheel_vel["base_right_wheel"],
        )

        base_extra_vel = {
            "height.vel": self.height_goal_vel,
            "yao.vel": self.yao_goal_vel,
        }

        arm_state = {f"{k}.pos": v for k, v in arm_pos.items()}
        right_arm_state = {f"{k}.pos": v for k, v in right_arm_pos.items()}

        obs_dict = {**arm_state, **right_arm_state, **base_vel, **base_extra_vel}

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read state: {dt_ms:.1f}ms")

        # Capture images from cameras
        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.read_latest()
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read {cam_key}: {dt_ms:.1f}ms")

        return obs_dict

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        """Command lekiwi to move to a target joint configuration.

        The relative action magnitude may be clipped depending on the configuration parameter
        `max_relative_target`. In this case, the action sent differs from original action.
        Thus, this function always returns the action actually sent.

        Raises:
            RobotDeviceNotConnectedError: if robot is not connected.

        Returns:
            RobotAction: the action sent to the motors, potentially clipped.
        """

        left_arm_goal_pos = {
            k: v for k, v in action.items() if k.startswith("left_arm") and k.endswith(".pos")
        }
        right_arm_goal_pos = {
            k: v for k, v in action.items() if k.startswith("right_arm") and k.endswith(".pos")
        }
        base_goal_vel = {k: v for k, v in action.items() if k.endswith(".vel")}

        base_wheel_goal_vel = self._body_to_wheel_raw(
            base_goal_vel["x.vel"], base_goal_vel["y.vel"], base_goal_vel["theta.vel"]
        )
        self.height_goal_vel = base_goal_vel["height.vel"]
        self.yao_goal_vel = base_goal_vel["yao.vel"]

        # Cap goal position when too far away from present position.
        # /!\ Slower fps expected due to reading from the follower.
        if self.config.max_relative_target is not None:
            present_pos = self.bus.sync_read("Present_Position", self.left_arm_motors)
            goal_present_pos = {
                key: (g_pos, present_pos[key]) for key, g_pos in left_arm_goal_pos.items()
            }
            left_arm_goal_pos = ensure_safe_goal_position(goal_present_pos, self.config.max_relative_target)

            present_pos = self.right_arm_bus.sync_read("Present_Position", self.right_arm_motors)
            goal_present_pos = {
                key: (g_pos, present_pos[key]) for key, g_pos in right_arm_goal_pos.items()
            }
            right_arm_goal_pos = ensure_safe_goal_position(goal_present_pos, self.config.max_relative_target)

        # Send goal position to the actuators
        left_arm_goal_pos_raw = {k.replace(".pos", ""): v for k, v in left_arm_goal_pos.items()}
        right_arm_goal_pos_raw = {k.replace(".pos", ""): v for k, v in right_arm_goal_pos.items()}
        self.right_arm_bus.sync_write("Goal_Position", right_arm_goal_pos_raw)
        self.bus.sync_write("Goal_Position", left_arm_goal_pos_raw)
        self.bus.sync_write("Goal_Velocity", base_wheel_goal_vel)

        return {**left_arm_goal_pos, **right_arm_goal_pos, **base_goal_vel}

    def stop_base(self):
        self.bus.sync_write("Goal_Velocity", dict.fromkeys(self.base_motors, 0), num_retry=5)
        logger.info("Base motors stopped")

    @check_if_not_connected
    def disconnect(self):
        self.stop_base()
        self.bus.disconnect(self.config.disable_torque_on_disconnect)
        self.right_arm_bus.disconnect(self.config.disable_torque_on_disconnect)
        for cam in self.cameras.values():
            cam.disconnect()

        logger.info(f"{self} disconnected.")
