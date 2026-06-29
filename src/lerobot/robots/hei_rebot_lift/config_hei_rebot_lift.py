#!/usr/bin/env python

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig, Cv2Rotation
from lerobot.cameras.opencv import OpenCVCameraConfig

from ..config import RobotConfig

# 可用命令： lerobot-find-cameras      查找相机
def hei_rebot_lift_cameras_config() -> dict[str, CameraConfig]:
    return {
        "front": OpenCVCameraConfig(
            index_or_path="/dev/video0", fps=30, width=640, height=480, rotation=Cv2Rotation.NO_ROTATION, fourcc="MJPG",
        ),
        "left_wrist": OpenCVCameraConfig(
            index_or_path="/dev/video2", fps=30, width=640, height=480, rotation=Cv2Rotation.NO_ROTATION, fourcc="MJPG",
        ),
        "right_wrist": OpenCVCameraConfig(
            index_or_path="/dev/video4", fps=30, width=640, height=480, rotation=Cv2Rotation.NO_ROTATION, fourcc="MJPG",
        ),
    }


@RobotConfig.register_subclass("hei_rebot_lift")
@dataclass
class HeiRebotLiftConfig(RobotConfig):
    # Udev-stable names. Bind these to the physical ttyACM*/ttyUSB* ports later.
    right_arm_port: str = "/dev/hei_right_arm"
    left_arm_port: str = "/dev/hei_left_arm"
    chassis_port: str = "/dev/hei_chassis"
    lift_motor_port: str = "/dev/hei_lift"
    lift_io_port: str = "/dev/hei_lift_io"

    u2can_baud: int = 921600
    lift_io_baud: int = 115200

    disable_torque_on_disconnect: bool = True

    arm_velocity_limit_rad_s: float = 8.0
    arm_kp_apr: float = 100.0
    arm_acc: float = 20.0
    arm_dec: float = -50.0
    gripper_force_velocity: float = 1000.0
    gripper_current: float = 500.0

    # Software clamps in motor radians. First 6 are arm joints, last is gripper.
    right_arm_min_rad: tuple[float, ...] = (-0.3, -3.14, -3.14, -1.4, -1.57, -3.14, -4.5)
    right_arm_max_rad: tuple[float, ...] = (1.5, 0.0, 0.0, 1.57, 1.57, 3.14, 0.0)
    left_arm_min_rad: tuple[float, ...] = (-1.5, -3.14, -3.14, -1.4, -1.57, -3.14, -4.5)
    left_arm_max_rad: tuple[float, ...] = (0.3, 0.0, 0.0, 1.57, 1.57, 3.14, 0.0)
    right_arm_sign: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    left_arm_sign: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    right_arm_offset_rad: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    left_arm_offset_rad: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    chassis_x_sign: float = -1.0
    chassis_y_sign: float = -1.0
    chassis_theta_sign: float = 1.0
    chassis_linear_speed_scale: float = 5.0
    chassis_yaw_speed_scale: float = 1.0
    chassis_max_wheel_speed_rad_s: float = 6.0
    chassis_max_wheel_accel_rad_s2: float = 8.0
    chassis_wheel_sign: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)

    lift_upper_bit: int = 1
    lift_lower_bit: int = 2
    lift_up_sign: float = -1.0
    lift_lead_mm_per_rev: float = 10.0
    lift_position_wrap_rad: float = 25.0
    lift_home_speed_rad_s: float = 10.0
    lift_io_wait_timeout_s: float = 3.0
    lift_home_timeout_s: float = 30.0
    lift_max_speed_rad_s: float = 18.0
    lift_max_accel_rad_s2: float = 30.0
    lift_position_kp_rad_s_per_mm: float = 0.45
    lift_position_tolerance_mm: float = 1.0
    lift_min_height_mm: float = -800.0
    lift_max_height_mm: float = 0.0
    lift_default_height_mm: float = 0.0
    lift_home_on_connect: bool = True
    lift_set_zero_on_home: bool = True

    cameras: dict[str, CameraConfig] = field(default_factory=hei_rebot_lift_cameras_config)


@dataclass
class HeiRebotLiftHostConfig:
    port_zmq_cmd: int = 6555
    port_zmq_observations: int = 6556
    connection_time_s: int = 30000
    watchdog_timeout_ms: int = 500
    max_loop_freq_hz: int = 30


@RobotConfig.register_subclass("hei_rebot_lift_client")
@dataclass
class HeiRebotLiftClientConfig(RobotConfig):
    remote_ip: str
    port_zmq_cmd: int = 6555
    port_zmq_observations: int = 6556
    teleop_keys: dict[str, str] = field(
        default_factory=lambda: {
            "forward": "w",
            "backward": "s",
            "left": "a",
            "right": "d",
            "rotate_left": "z",
            "rotate_right": "x",
            "speed_up": "r",
            "speed_down": "f",
            "quit": "q",
            "height_up": "i",
            "height_down": "k",
        }
    )
    cameras: dict[str, CameraConfig] = field(default_factory=hei_rebot_lift_cameras_config)
    polling_timeout_ms: int = 15
    connect_timeout_s: int = 5
