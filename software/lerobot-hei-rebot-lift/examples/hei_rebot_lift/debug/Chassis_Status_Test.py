#!/usr/bin/env python
"""Independently drive and inspect the HEI ReBot Lift omnidirectional chassis."""

from __future__ import annotations

import argparse
import os
import select
import sys
import termios
import time
import tty
from contextlib import suppress

import numpy as np

from lerobot.robots.hei_rebot_lift.config_hei_rebot_lift import HeiRebotLiftConfig
from lerobot.robots.hei_rebot_lift.hei_rebot_lift import _ChassisRuntime


DEFAULT_CONTROL_HZ = 30.0
DEFAULT_DISPLAY_HZ = 10.0
DEFAULT_KEY_TIMEOUT_S = 0.65
GEAR_NAMES = ("LOW", "MEDIUM", "HIGH")
LINEAR_GEARS = (0.20, 0.50, 1.00)
ANGULAR_GEARS = (1.00, 2.50, 4.50)
WHEEL_NAMES = ("RF", "RR", "LR", "LF")


class TerminalKeyReader:
    """Read single keys without blocking; works in a local terminal or over SSH."""

    def __init__(self) -> None:
        self.fd: int | None = None
        self.original_settings = None

    def __enter__(self):
        if not sys.stdin.isatty():
            raise RuntimeError("Keyboard control requires an interactive terminal (TTY).")
        self.fd = sys.stdin.fileno()
        self.original_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        print("\033[?25l", end="", flush=True)
        return self

    def read_keys(self) -> list[str]:
        keys: list[str] = []
        while self.fd is not None and select.select([self.fd], [], [], 0.0)[0]:
            data = os.read(self.fd, 32)
            if not data:
                raise EOFError("Terminal input closed.")
            keys.extend(data.decode(errors="ignore"))
        return keys

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.fd is not None and self.original_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original_settings)
        print("\033[?25h", end="", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug only the HEI ReBot Lift chassis.")
    parser.add_argument("--port", default="/dev/hei_chassis", help="Chassis U2CAN serial port.")
    parser.add_argument("--control-hz", type=float, default=DEFAULT_CONTROL_HZ, help="Motor command frequency.")
    parser.add_argument("--display-hz", type=float, default=DEFAULT_DISPLAY_HZ, help="Dashboard refresh frequency.")
    parser.add_argument(
        "--key-timeout-s",
        type=float,
        default=DEFAULT_KEY_TIMEOUT_S,
        help="Stop command after this time without a repeated direction key.",
    )
    return parser.parse_args()


def body_command_for_key(key: str | None, gear_index: int) -> np.ndarray:
    linear = LINEAR_GEARS[gear_index]
    angular = ANGULAR_GEARS[gear_index]
    commands = {
        "w": (linear, 0.0, 0.0),
        "s": (-linear, 0.0, 0.0),
        "a": (0.0, linear, 0.0),
        "d": (0.0, -linear, 0.0),
        "q": (0.0, 0.0, angular),
        "e": (0.0, 0.0, -angular),
    }
    return np.asarray(commands.get(key, (0.0, 0.0, 0.0)), dtype=float)


def render_dashboard(
    chassis: _ChassisRuntime,
    gear_index: int,
    requested_body: np.ndarray,
    measured_body: dict[str, float],
    status: str,
    key_timeout_s: float,
) -> None:
    measured_wheels = np.asarray([float(motor.getVelocity()) for motor in chassis.motors], dtype=float)
    target_wheels = chassis.last_wheel_speeds

    print("\033[H\033[J", end="")
    print("HEI ReBot Lift - Chassis Status Test")
    print("=" * 86)
    print(f"Status          : {status}")
    print(f"U2CAN port      : {chassis.port}")
    print(
        f"Speed gear      : {gear_index + 1} / {GEAR_NAMES[gear_index]}  "
        f"linear={LINEAR_GEARS[gear_index]:.2f}, theta={ANGULAR_GEARS[gear_index]:.2f}"
    )
    print(f"Key watchdog    : {key_timeout_s:.2f} s")
    print()
    print("Body velocity (command units; feedback reconstructed from measured wheel speeds)")
    print("-" * 86)
    print("%-12s %14s %14s" % ("Axis", "Requested", "Measured"))
    print("%-12s %14.4f %14.4f" % ("x.vel", requested_body[0], measured_body["x.vel"]))
    print("%-12s %14.4f %14.4f" % ("y.vel", requested_body[1], measured_body["y.vel"]))
    print("%-12s %14.4f %14.4f" % ("theta.vel", requested_body[2], measured_body["theta.vel"]))
    print()
    print("Wheel motor feedback (order is identical to the production chassis driver)")
    print("-" * 86)
    print(
        "%-8s %-8s %12s %12s %12s %12s %8s"
        % ("Wheel", "CAN ID", "TARGET", "VELOCITY", "POSITION", "TORQUE", "ERROR")
    )
    for name, motor, target, measured in zip(
        WHEEL_NAMES,
        chassis.motors,
        target_wheels,
        measured_wheels,
        strict=True,
    ):
        print(
            "%-8s 0x%-6X %12.4f %12.4f %12.4f %12.4f %8d"
            % (
                name,
                motor.SlaveID,
                target,
                measured,
                float(motor.getPosition()),
                float(motor.getTorque()),
                int(motor.getError()),
            )
        )
    print()
    print(
        "Keys: W/S forward/back | A/D left/right | Q/E rotate | "
        "1/2/3 gear | Space emergency stop | X exit"
    )
    print("Hold/repeat a direction key to keep moving; key watchdog stops stale commands.")
    sys.stdout.flush()


def main() -> None:
    args = parse_args()
    if args.control_hz <= 0.0 or args.display_hz <= 0.0 or args.key_timeout_s <= 0.0:
        raise ValueError("control-hz, display-hz, and key-timeout-s must all be positive.")

    # 只创建底盘运行时，不初始化双臂、升降或相机。
    # 运动学、限速和加减速均复用正式驱动。
    # 正式配置的 X/Y 负号用于 VR 输入方向；键盘 W/A 已定义为前进/左移，
    # 此处使用正号，避免平移反向，并让反馈表与按键方向一致。转向沿用正式配置。
    config = HeiRebotLiftConfig(
        cameras={},
        chassis_port=args.port,
        chassis_x_sign=1.0,
        chassis_y_sign=1.0,
    )
    chassis = _ChassisRuntime(config.chassis_port, config.u2can_baud, config)
    control_period_s = 1.0 / args.control_hz
    display_period_s = 1.0 / args.display_hz
    gear_index = 0
    active_key: str | None = None
    active_until_s = 0.0
    status = "Connecting..."

    print(status, flush=True)
    try:
        chassis.connect()
        status = "Ready; chassis stopped"
        last_display_s = 0.0

        with TerminalKeyReader() as keyboard:
            running = True
            while running:
                loop_start_s = time.monotonic()
                now_s = loop_start_s
                for key in keyboard.read_keys():
                    key = key.lower()
                    if key in "wasdqe":
                        active_key = key
                        active_until_s = now_s + args.key_timeout_s
                        status = f"Direction key: {key.upper()}"
                    elif key in "123":
                        gear_index = int(key) - 1
                        status = f"Speed gear changed to {key} / {GEAR_NAMES[gear_index]}"
                    elif key == " ":
                        active_key = None
                        active_until_s = 0.0
                        chassis.stop()
                        status = "Emergency stop"
                    elif key == "x":
                        running = False

                if not running:
                    break

                if active_key is not None and now_s >= active_until_s:
                    active_key = None
                    status = "Key watchdog stopped the chassis"

                requested_body = body_command_for_key(active_key, gear_index)
                chassis.command(*requested_body)

                now_s = time.monotonic()
                if now_s - last_display_s >= display_period_s:
                    measured_body = chassis.read_body_velocity()
                    render_dashboard(chassis, gear_index, requested_body, measured_body, status, args.key_timeout_s)
                    last_display_s = now_s

                time.sleep(max(control_period_s - (time.monotonic() - loop_start_s), 0.0))
    finally:
        # 任意异常或 Ctrl+C 都立即给四轮发零速，然后失能并关闭串口。
        with suppress(Exception):
            chassis.stop()
        with suppress(Exception):
            chassis.disconnect(config.disable_torque_on_disconnect)
        print("\n[Chassis test] stopped safely")


if __name__ == "__main__":
    main()
