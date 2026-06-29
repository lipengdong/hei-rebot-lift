#!/usr/bin/env python

import importlib
import logging
import time
from contextlib import suppress
from functools import cached_property
from typing import Any

import numpy as np

from lerobot.cameras import make_cameras_from_configs
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from .config_hei_rebot_lift import HeiRebotLiftConfig

logger = logging.getLogger(__name__)

ARM_JOINTS = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6", "gripper")
ARM_JOINT_COUNT = 6
ARM_QPOS_COUNT = 7
TWO_PI = 2.0 * np.pi

# Motor order from the validated u2can scripts: [RF, RR, LR, LF].
O_TYPE_KINEMATICS = np.array(
    [
        [-1.0, -1.0, -1.0],
        [-1.0, 1.0, -1.0],
        [1.0, 1.0, -1.0],
        [1.0, -1.0, -1.0],
    ],
    dtype=float,
)


def _load_dm_can():
    try:
        return importlib.import_module("lerobot.motors.damiao_u2can")
    except ImportError as exc:
        raise ImportError(
            "HEI ReBot Lift requires the u2can Damiao backend in lerobot.motors.damiao_u2can."
        ) from exc


def _load_serial():
    try:
        return importlib.import_module("serial")
    except ImportError as exc:
        raise ImportError("pyserial is required for HEI ReBot Lift u2can/IO ports.") from exc


def _crc16_modbus(data: bytes | bytearray) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


class _LimitSwitchReader:
    def __init__(self, port: str, baudrate: int, upper_bit: int, lower_bit: int, timeout_s: float = 0.0):
        serial = _load_serial()
        self.serial = serial.Serial(port, baudrate, timeout=0.0)
        self.upper_mask = 1 << (upper_bit - 1)
        self.lower_mask = 1 << (lower_bit - 1)
        self.timeout_s = timeout_s
        self.buffer = bytearray()
        self.state = 0
        self.last_update_s = 0.0

    def close(self) -> None:
        self.serial.close()

    def poll(self) -> None:
        data = self.serial.read(256)
        if data:
            self.buffer.extend(data)
        self._parse_buffer()

    def _parse_buffer(self) -> None:
        while len(self.buffer) >= 7:
            start = self._find_frame_start()
            if start is None:
                self.buffer.clear()
                return
            if start > 0:
                del self.buffer[:start]
            if len(self.buffer) < 7:
                return

            frame = bytes(self.buffer[:7])
            del self.buffer[:7]
            if frame[0] != 0x01 or frame[1] != 0x04 or frame[2] != 0x02 or frame[3] != 0x00:
                continue
            frame_crc = frame[5] | (frame[6] << 8)
            if _crc16_modbus(frame[:5]) != frame_crc:
                continue
            if frame[4] not in (0x00, 0x01, 0x02, 0x03):
                continue
            self.state = frame[4]
            self.last_update_s = time.monotonic()

    def _find_frame_start(self) -> int | None:
        for index in range(len(self.buffer) - 3):
            if (
                self.buffer[index] == 0x01
                and self.buffer[index + 1] == 0x04
                and self.buffer[index + 2] == 0x02
                and self.buffer[index + 3] == 0x00
            ):
                return index
        return None

    @property
    def upper_active(self) -> bool:
        return bool(self.state & self.upper_mask)

    @property
    def lower_active(self) -> bool:
        return bool(self.state & self.lower_mask)

    @property
    def both_active(self) -> bool:
        return self.upper_active and self.lower_active

    @property
    def online(self) -> bool:
        if self.timeout_s <= 0.0:
            return self.last_update_s > 0.0
        return self.last_update_s > 0.0 and time.monotonic() - self.last_update_s <= self.timeout_s


class _MultiTurnPositionTracker:
    def __init__(self, wrap_rad: float):
        self.wrap_rad = float(wrap_rad)
        self.half_wrap_rad = self.wrap_rad * 0.5
        self.last_raw_rad: float | None = None
        self.turn_offset_rad = 0.0

    def reset(self, raw_rad: float = 0.0) -> None:
        self.last_raw_rad = float(raw_rad)
        self.turn_offset_rad = -float(raw_rad)

    def update(self, raw_rad: float) -> float:
        raw_rad = float(raw_rad)
        if self.last_raw_rad is None:
            self.reset(raw_rad)
        else:
            delta = raw_rad - self.last_raw_rad
            if delta > self.half_wrap_rad:
                self.turn_offset_rad -= self.wrap_rad
            elif delta < -self.half_wrap_rad:
                self.turn_offset_rad += self.wrap_rad
            self.last_raw_rad = raw_rad
        return raw_rad + self.turn_offset_rad


def _write_motor_param_with_fallback(motor_control: Any, motor: Any, variable: Any, values: list[float]) -> None:
    for value in values:
        motor.temp_param_dict.pop(variable, None)
        if motor_control.change_motor_param(motor, variable, float(value)):
            return
        time.sleep(0.02)
    logger.warning("Failed to write motor parameter %s with candidates %s", variable, values)


class _ArmRuntime:
    def __init__(
        self,
        name: str,
        port: str,
        baud: int,
        sign: tuple[float, ...],
        offset_rad: tuple[float, ...],
        min_rad: tuple[float, ...],
        max_rad: tuple[float, ...],
        config: HeiRebotLiftConfig,
    ):
        self.name = name
        self.port = port
        self.baud = baud
        self.sign = np.asarray(sign, dtype=float)
        self.offset_rad = np.asarray(offset_rad, dtype=float)
        self.min_rad = np.asarray(min_rad, dtype=float)
        self.max_rad = np.asarray(max_rad, dtype=float)
        self.config = config
        self.serial_device = None
        self.motor_control = None
        self.motors: list[Any] = []

    @property
    def is_connected(self) -> bool:
        return self.motor_control is not None

    def connect(self) -> None:
        dm_can = _load_dm_can()
        serial = _load_serial()
        self.motors = [
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x01, 0x11),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x02, 0x12),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x03, 0x13),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4310, 0x04, 0x14),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4310, 0x05, 0x15),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4310, 0x06, 0x16),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4310, 0x07, 0x17),
        ]
        self.serial_device = serial.Serial(self.port, self.baud, timeout=0.5)
        self.motor_control = dm_can.MotorControl(self.serial_device)
        for motor in self.motors:
            self.motor_control.addMotor(motor)

        for motor in self.motors[:ARM_JOINT_COUNT]:
            self.motor_control.switchControlMode(motor, dm_can.Control_Type.POS_VEL)
        self.motor_control.switchControlMode(self.motors[6], dm_can.Control_Type.Torque_Pos)

        for motor in self.motors[:ARM_JOINT_COUNT]:
            _write_motor_param_with_fallback(
                self.motor_control, motor, dm_can.DM_variable.KP_APR, [self.config.arm_kp_apr]
            )
            _write_motor_param_with_fallback(
                self.motor_control, motor, dm_can.DM_variable.ACC, [self.config.arm_acc]
            )
            _write_motor_param_with_fallback(
                self.motor_control, motor, dm_can.DM_variable.DEC, [self.config.arm_dec, 12.0, 8.0, 5.0]
            )

        for motor in self.motors:
            self.motor_control.enable(motor)

    def set_zero_position(self) -> None:
        if self.motor_control is None:
            return
        for motor in self.motors:
            self.motor_control.disable(motor)
            self.motor_control.set_zero_position(motor)
            self.motor_control.refresh_motor_status(motor)

    def command(self, target_rad: np.ndarray) -> dict[str, float]:
        if self.motor_control is None:
            return {}
        target = np.asarray(target_rad, dtype=float)
        target = np.clip(target * self.sign + self.offset_rad, self.min_rad, self.max_rad)
        for motor, pos in zip(self.motors[:ARM_JOINT_COUNT], target[:ARM_JOINT_COUNT], strict=True):
            self.motor_control.control_Pos_Vel(motor, float(pos), float(self.config.arm_velocity_limit_rad_s))
        self.motor_control.control_pos_force(
            self.motors[6],
            float(target[6]),
            float(self.config.gripper_force_velocity),
            float(self.config.gripper_current),
        )
        return {f"{self.name}_{joint}.pos": float(target[i]) for i, joint in enumerate(ARM_JOINTS)}

    def read_positions(self) -> dict[str, float]:
        if self.motor_control is None:
            return {f"{self.name}_{joint}.pos": 0.0 for joint in ARM_JOINTS}
        obs = {}
        for i, (joint, motor) in enumerate(zip(ARM_JOINTS, self.motors, strict=True)):
            with suppress(Exception):
                self.motor_control.refresh_motor_status(motor)
            raw = float(motor.getPosition())
            model_value = (raw - self.offset_rad[i]) / self.sign[i]
            obs[f"{self.name}_{joint}.pos"] = model_value
        return obs

    def disconnect(self, disable_torque: bool) -> None:
        if self.motor_control is not None and disable_torque:
            for motor in self.motors:
                with suppress(Exception):
                    self.motor_control.disable(motor)
        if self.serial_device is not None:
            self.serial_device.close()
        self.motor_control = None
        self.serial_device = None


class _ChassisRuntime:
    def __init__(self, port: str, baud: int, config: HeiRebotLiftConfig):
        self.port = port
        self.baud = baud
        self.config = config
        self.serial_device = None
        self.motor_control = None
        self.motors: list[Any] = []
        self.last_body_vel = np.zeros(3, dtype=float)
        self.last_wheel_speeds = np.zeros(4, dtype=float)
        self.last_command_time_s: float | None = None

    @property
    def is_connected(self) -> bool:
        return self.motor_control is not None

    def connect(self) -> None:
        dm_can = _load_dm_can()
        serial = _load_serial()
        self.motors = [
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x01, 0x11),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x02, 0x12),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x03, 0x13),
            dm_can.Motor(dm_can.DM_Motor_Type.DM4340, 0x04, 0x14),
        ]
        self.serial_device = serial.Serial(self.port, self.baud, timeout=0.5)
        self.motor_control = dm_can.MotorControl(self.serial_device)
        for motor in self.motors:
            self.motor_control.addMotor(motor)
            self.motor_control.switchControlMode(motor, dm_can.Control_Type.VEL)
            self.motor_control.enable(motor)

    def _body_to_wheel_speeds(self, x: float, y: float, theta: float) -> np.ndarray:
        scaled = np.array(
            [
                x * self.config.chassis_x_sign * self.config.chassis_linear_speed_scale,
                y * self.config.chassis_y_sign * self.config.chassis_linear_speed_scale,
                theta * self.config.chassis_theta_sign * self.config.chassis_yaw_speed_scale,
            ],
            dtype=float,
        )
        wheel_speeds = O_TYPE_KINEMATICS @ scaled
        max_abs = float(np.max(np.abs(wheel_speeds)))
        if max_abs > self.config.chassis_max_wheel_speed_rad_s:
            wheel_speeds *= self.config.chassis_max_wheel_speed_rad_s / max_abs
        return wheel_speeds * np.asarray(self.config.chassis_wheel_sign, dtype=float)

    def _wheel_to_body_vel(self, wheel_speeds: np.ndarray) -> np.ndarray:
        signed = wheel_speeds / np.asarray(self.config.chassis_wheel_sign, dtype=float)
        scale = np.array(
            [
                self.config.chassis_x_sign * self.config.chassis_linear_speed_scale,
                self.config.chassis_y_sign * self.config.chassis_linear_speed_scale,
                self.config.chassis_theta_sign * self.config.chassis_yaw_speed_scale,
            ],
            dtype=float,
        )
        body_scaled, *_ = np.linalg.lstsq(O_TYPE_KINEMATICS, signed, rcond=None)
        return body_scaled / scale

    def command(self, x: float, y: float, theta: float) -> dict[str, float]:
        if self.motor_control is None:
            return {"x.vel": 0.0, "y.vel": 0.0, "theta.vel": 0.0}
        wheel_speeds = self._body_to_wheel_speeds(x, y, theta)
        now = time.monotonic()
        if self.last_command_time_s is None:
            limited_wheel_speeds = wheel_speeds
        else:
            dt = max(now - self.last_command_time_s, 0.0)
            max_delta = self.config.chassis_max_wheel_accel_rad_s2 * dt
            limited_wheel_speeds = self.last_wheel_speeds + np.clip(
                wheel_speeds - self.last_wheel_speeds,
                -max_delta,
                max_delta,
            )
        self.last_command_time_s = now
        self.last_wheel_speeds = limited_wheel_speeds.copy()
        for motor, speed in zip(self.motors, limited_wheel_speeds, strict=True):
            self.motor_control.control_Vel(motor, float(speed))
        self.last_body_vel = np.array([x, y, theta], dtype=float)
        return {"x.vel": float(x), "y.vel": float(y), "theta.vel": float(theta)}

    def read_body_velocity(self) -> dict[str, float]:
        if self.motor_control is None:
            x, y, theta = self.last_body_vel
            return {"x.vel": float(x), "y.vel": float(y), "theta.vel": float(theta)}
        wheel_speeds = []
        for motor in self.motors:
            with suppress(Exception):
                self.motor_control.refresh_motor_status(motor)
            wheel_speeds.append(float(motor.getVelocity()))
        body = self._wheel_to_body_vel(np.asarray(wheel_speeds, dtype=float))
        return {"x.vel": float(body[0]), "y.vel": float(body[1]), "theta.vel": float(body[2])}

    def stop(self) -> None:
        if self.motor_control is not None:
            for motor in self.motors:
                with suppress(Exception):
                    self.motor_control.control_Vel(motor, 0.0)
        self.last_body_vel[:] = 0.0
        self.last_wheel_speeds[:] = 0.0
        self.last_command_time_s = None

    def disconnect(self, disable_torque: bool) -> None:
        self.stop()
        if self.motor_control is not None and disable_torque:
            for motor in self.motors:
                with suppress(Exception):
                    self.motor_control.disable(motor)
        if self.serial_device is not None:
            self.serial_device.close()
        self.motor_control = None
        self.serial_device = None


class _LiftRuntime:
    def __init__(self, motor_port: str, io_port: str, config: HeiRebotLiftConfig):
        self.motor_port = motor_port
        self.io_port = io_port
        self.config = config
        self.reader: _LimitSwitchReader | None = None
        self.serial_device = None
        self.motor_control = None
        self.motor = None
        self.tracker = _MultiTurnPositionTracker(config.lift_position_wrap_rad)
        self.target_height_mm = config.lift_default_height_mm
        self.height_mm = config.lift_default_height_mm
        self.last_velocity_rad_s = 0.0
        self.last_command_time_s: float | None = None

    @property
    def is_connected(self) -> bool:
        return self.motor_control is not None and self.reader is not None

    def connect(self) -> None:
        dm_can = _load_dm_can()
        serial = _load_serial()
        self.reader = _LimitSwitchReader(
            self.io_port,
            self.config.lift_io_baud,
            self.config.lift_upper_bit,
            self.config.lift_lower_bit,
        )
        self.motor = dm_can.Motor(dm_can.DM_Motor_Type.DM4310, 0x01, 0x11)
        self.serial_device = serial.Serial(self.motor_port, self.config.u2can_baud, timeout=0.5)
        self.motor_control = dm_can.MotorControl(self.serial_device)
        self.motor_control.addMotor(self.motor)
        self.motor_control.switchControlMode(self.motor, dm_can.Control_Type.VEL)
        self.motor_control.enable(self.motor)
        with suppress(Exception):
            self.motor_control.refresh_motor_status(self.motor)
        self.tracker.reset(float(self.motor.getPosition()))
        if self.config.lift_home_on_connect:
            self.home()
        self.target_height_mm = self.height_mm

    def _motor_rad_to_mm(self, rad: float) -> float:
        return self.config.lift_up_sign * rad / TWO_PI * self.config.lift_lead_mm_per_rev

    def _mm_s_to_motor_rad_s(self, mm_s: float) -> float:
        return mm_s / self.config.lift_lead_mm_per_rev * TWO_PI / self.config.lift_up_sign

    def _poll_height(self) -> float:
        if self.reader is not None:
            self.reader.poll()
        if self.motor_control is not None and self.motor is not None:
            with suppress(Exception):
                self.motor_control.refresh_motor_status(self.motor)
            raw_rad = float(self.motor.getPosition())
            self.height_mm = self._motor_rad_to_mm(self.tracker.update(raw_rad))
        return self.height_mm

    def home(self) -> None:
        if self.reader is None or self.motor_control is None or self.motor is None:
            return
        home_vel = self.config.lift_up_sign * abs(self.config.lift_home_speed_rad_s)
        logger.info("Homing lift upward to the upper limit switch...")

        io_wait_start = time.monotonic()
        while not self.reader.online and time.monotonic() - io_wait_start < self.config.lift_io_wait_timeout_s:
            self.reader.poll()
            time.sleep(0.01)
        if not self.reader.online:
            self.motor_control.control_Vel(self.motor, 0.0)
            raise RuntimeError("No valid lift limit-switch IO frame received before homing.")

        homed = False
        start = time.monotonic()
        while time.monotonic() - start < self.config.lift_home_timeout_s:
            self.reader.poll()
            if not self.reader.online:
                self.motor_control.control_Vel(self.motor, 0.0)
                raise RuntimeError("Lift limit-switch IO timed out during homing.")
            if self.reader.both_active:
                self.motor_control.control_Vel(self.motor, 0.0)
                logger.warning("Both lift limit switches are active during homing; waiting for a valid state.")
                time.sleep(0.01)
                continue
            if self.reader.upper_active and not self.reader.both_active:
                self.motor_control.control_Vel(self.motor, 0.0)
                homed = True
                break
            self.motor_control.control_Vel(self.motor, float(home_vel))
            time.sleep(0.01)
        if not homed:
            self.motor_control.control_Vel(self.motor, 0.0)
            raise RuntimeError("Lift homing timed out before the upper limit switch was reached.")

        if self.config.lift_set_zero_on_home:
            self.motor_control.disable(self.motor)
            self.motor_control.set_zero_position(self.motor)
            self.motor_control.refresh_motor_status(self.motor)
            self.motor_control.enable(self.motor)
            self.tracker.reset(float(self.motor.getPosition()))
            self.height_mm = 0.0
            self.target_height_mm = 0.0
            self.last_velocity_rad_s = 0.0
            self.last_command_time_s = None
            logger.info("Lift upper limit reached and zero position set.")

    def command_position(self, target_height_mm: float) -> dict[str, float]:
        if self.motor_control is None or self.motor is None:
            return {"height.pos": self.height_mm}
        self.target_height_mm = float(
            np.clip(target_height_mm, self.config.lift_min_height_mm, self.config.lift_max_height_mm)
        )
        current = self._poll_height()
        error_mm = self.target_height_mm - current
        velocity_rad_s = 0.0
        if abs(error_mm) >= self.config.lift_position_tolerance_mm:
            velocity_rad_s = np.clip(
                self.config.lift_position_kp_rad_s_per_mm * error_mm / self.config.lift_up_sign,
                -self.config.lift_max_speed_rad_s,
                self.config.lift_max_speed_rad_s,
            )
        if self.reader is not None:
            if self.reader.both_active:
                velocity_rad_s = 0.0
            elif self.reader.upper_active and velocity_rad_s * self.config.lift_up_sign > 0:
                velocity_rad_s = 0.0
            elif self.reader.lower_active and velocity_rad_s * self.config.lift_up_sign < 0:
                velocity_rad_s = 0.0
        now = time.monotonic()
        if self.last_command_time_s is None:
            limited_velocity_rad_s = velocity_rad_s
        else:
            dt = max(now - self.last_command_time_s, 0.0)
            max_delta = self.config.lift_max_accel_rad_s2 * dt
            limited_velocity_rad_s = self.last_velocity_rad_s + float(
                np.clip(velocity_rad_s - self.last_velocity_rad_s, -max_delta, max_delta)
            )
        self.last_command_time_s = now
        self.last_velocity_rad_s = limited_velocity_rad_s
        self.motor_control.control_Vel(self.motor, float(limited_velocity_rad_s))
        return {"height.pos": float(self.target_height_mm)}

    def read_height(self) -> dict[str, float]:
        return {"height.pos": float(self._poll_height())}

    def stop(self) -> None:
        if self.motor_control is not None and self.motor is not None:
            with suppress(Exception):
                self.motor_control.control_Vel(self.motor, 0.0)
        self.last_velocity_rad_s = 0.0
        self.last_command_time_s = None

    def disconnect(self, disable_torque: bool) -> None:
        self.stop()
        if self.motor_control is not None and self.motor is not None and disable_torque:
            with suppress(Exception):
                self.motor_control.disable(self.motor)
        if self.serial_device is not None:
            self.serial_device.close()
        if self.reader is not None:
            self.reader.close()
        self.motor_control = None
        self.serial_device = None
        self.reader = None


class HeiRebotLift(Robot):
    config_class = HeiRebotLiftConfig
    name = "hei_rebot_lift"

    def __init__(self, config: HeiRebotLiftConfig):
        super().__init__(config)
        self.config = config
        self.right_arm = _ArmRuntime(
            "right",
            config.right_arm_port,
            config.u2can_baud,
            config.right_arm_sign,
            config.right_arm_offset_rad,
            config.right_arm_min_rad,
            config.right_arm_max_rad,
            config,
        )
        self.left_arm = _ArmRuntime(
            "left",
            config.left_arm_port,
            config.u2can_baud,
            config.left_arm_sign,
            config.left_arm_offset_rad,
            config.left_arm_min_rad,
            config.left_arm_max_rad,
            config,
        )
        self.chassis = _ChassisRuntime(config.chassis_port, config.u2can_baud, config)
        self.lift = _LiftRuntime(config.lift_motor_port, config.lift_io_port, config)
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def _state_ft(self) -> dict[str, type]:
        features = {}
        for side in ("right", "left"):
            for joint in ARM_JOINTS:
                features[f"{side}_{joint}.pos"] = float
        features.update({"x.vel": float, "y.vel": float, "theta.vel": float, "height.pos": float})
        return features

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
            self.right_arm.is_connected
            and self.left_arm.is_connected
            and self.chassis.is_connected
            and self.lift.is_connected
            and all(cam.is_connected for cam in self.cameras.values())
        )

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        self.right_arm.connect()
        self.left_arm.connect()
        self.chassis.connect()
        self.lift.connect()
        for cam in self.cameras.values():
            cam.connect()
        logger.info("%s connected.", self)

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        logger.info("Set arm zero positions from the current pose.")
        self.right_arm.set_zero_position()
        self.left_arm.set_zero_position()
        self.lift.home()

    def configure(self) -> None:
        pass

    def setup_motors(self) -> None:
        raise NotImplementedError("Use the Damiao tools/u2can setup flow to assign motor IDs.")

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        obs_dict: RobotObservation = {}
        obs_dict.update(self.right_arm.read_positions())
        obs_dict.update(self.left_arm.read_positions())
        obs_dict.update(self.chassis.read_body_velocity())
        obs_dict.update(self.lift.read_height())
        for cam_key, cam in self.cameras.items():
            obs_dict[cam_key] = cam.read_latest()
        return obs_dict

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        right_target = np.array([action.get(f"right_{joint}.pos", 0.0) for joint in ARM_JOINTS], dtype=float)
        left_target = np.array([action.get(f"left_{joint}.pos", 0.0) for joint in ARM_JOINTS], dtype=float)

        action_sent: RobotAction = {}
        action_sent.update(self.right_arm.command(right_target))
        action_sent.update(self.left_arm.command(left_target))
        action_sent.update(
            self.chassis.command(
                float(action.get("x.vel", 0.0)),
                float(action.get("y.vel", 0.0)),
                float(action.get("theta.vel", 0.0)),
            )
        )
        action_sent.update(self.lift.command_position(float(action.get("height.pos", self.lift.target_height_mm))))
        return action_sent

    def stop_base(self) -> None:
        self.chassis.stop()

    def stop_motion(self) -> None:
        self.chassis.stop()
        self.lift.stop()

    @check_if_not_connected
    def disconnect(self) -> None:
        self.stop_motion()
        self.right_arm.disconnect(self.config.disable_torque_on_disconnect)
        self.left_arm.disconnect(self.config.disable_torque_on_disconnect)
        self.chassis.disconnect(self.config.disable_torque_on_disconnect)
        self.lift.disconnect(self.config.disable_torque_on_disconnect)
        for cam in self.cameras.values():
            cam.disconnect()
        logger.info("%s disconnected.", self)
