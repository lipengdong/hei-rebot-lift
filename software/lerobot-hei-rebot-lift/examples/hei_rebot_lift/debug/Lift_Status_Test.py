#!/usr/bin/env python
"""Independently home, control, and inspect the HEI ReBot Lift platform."""

from __future__ import annotations

import argparse
import os
import select
import sys
import termios
import time
import tty
from contextlib import suppress

from lerobot.robots.hei_rebot_lift.config_hei_rebot_lift import HeiRebotLiftConfig
from lerobot.robots.hei_rebot_lift.hei_rebot_lift import _LiftRuntime


# 每次 I/K 按键只推进 2 mm，减小长按重复事件造成的目标高度累积。
DEFAULT_HEIGHT_STEP_MM = 2.0
DEFAULT_CONTROL_HZ = 30.0
DEFAULT_DISPLAY_HZ = 10.0


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
    parser = argparse.ArgumentParser(description="Debug only the HEI ReBot Lift platform.")
    parser.add_argument("--motor-port", default="/dev/hei_lift", help="Lift DM4310 U2CAN serial port.")
    parser.add_argument("--io-port", default="/dev/hei_lift_io", help="Upper/lower limit-switch serial port.")
    parser.add_argument(
        "--height-step-mm",
        type=float,
        default=DEFAULT_HEIGHT_STEP_MM,
        help="Target-height change for each I/K key event.",
    )
    parser.add_argument("--control-hz", type=float, default=DEFAULT_CONTROL_HZ, help="Position control frequency.")
    parser.add_argument("--display-hz", type=float, default=DEFAULT_DISPLAY_HZ, help="Dashboard refresh frequency.")
    return parser.parse_args()


def render_dashboard(lift: _LiftRuntime, status: str, height_step_mm: float) -> None:
    reader = lift.reader
    motor = lift.motor
    now = time.monotonic()

    io_online = bool(reader and reader.online)
    upper_active = bool(reader and reader.upper_active)
    lower_active = bool(reader and reader.lower_active)
    io_state = reader.state if reader is not None else 0
    io_age_ms = (
        (now - reader.last_update_s) * 1000.0
        if reader and reader.last_update_s > 0.0
        else float("inf")
    )
    io_status = "ONLINE" if io_online and io_age_ms < 500.0 else "STALE/OFFLINE"

    motor_position = float(motor.getPosition()) if motor is not None else 0.0
    motor_velocity = float(motor.getVelocity()) if motor is not None else 0.0
    motor_torque = float(motor.getTorque()) if motor is not None else 0.0
    motor_error = int(motor.getError()) if motor is not None else -1
    height_velocity_mm_s = lift._motor_rad_to_mm(motor_velocity)
    target_error_mm = lift.target_height_mm - lift.height_mm

    if abs(lift.last_velocity_rad_s) < 1e-3:
        motion_state = "HOLD"
    elif lift._motor_rad_to_mm(lift.last_velocity_rad_s) > 0.0:
        motion_state = "UP"
    else:
        motion_state = "DOWN"

    print("\033[H\033[J", end="")
    print("HEI ReBot Lift - Lift Status Test")
    print("=" * 72)
    print(f"Status          : {status}")
    print(f"Motor port      : {lift.motor_port}")
    print(f"Limit IO port   : {lift.io_port}")
    print(f"Control state   : {motion_state}")
    print()
    print("Height position control")
    print("-" * 72)
    print(f"Current height  : {lift.height_mm:10.2f} mm")
    print(f"Target height   : {lift.target_height_mm:10.2f} mm")
    print(f"Position error  : {target_error_mm:10.2f} mm")
    print(f"Height velocity : {height_velocity_mm_s:10.2f} mm/s (measured)")
    print(f"Motor command   : {lift.last_velocity_rad_s:10.3f} rad/s")
    print(f"Valid range     : {lift.config.lift_min_height_mm:.1f} .. {lift.config.lift_max_height_mm:.1f} mm")
    print()
    print("Limit-switch IO")
    print("-" * 72)
    print(f"Module status   : {io_status:13s} frame age: {io_age_ms:8.1f} ms")
    print(f"Raw IO state    : 0x{io_state:02X}")
    print(f"Upper limit     : {'ACTIVE' if upper_active else 'released'}")
    print(f"Lower limit     : {'ACTIVE' if lower_active else 'released'}")
    print(f"Both active     : {'FAULT' if upper_active and lower_active else 'NO'}")
    print()
    print("DM4310 feedback")
    print("-" * 72)
    print(f"Position        : {motor_position:10.4f} rad")
    print(f"Velocity        : {motor_velocity:10.4f} rad/s")
    print(f"Torque          : {motor_torque:10.4f}")
    print(f"Error code      : {motor_error}")
    print(f"Motor enabled   : {'YES' if motor is not None and motor.isEnable else 'NO'}")
    print()
    print(
        f"Keys: I up (+{height_step_mm:g} mm) | K down (-{height_step_mm:g} mm) | "
        "Space stop | H home | X exit"
    )
    sys.stdout.flush()


def main() -> None:
    args = parse_args()
    if args.height_step_mm <= 0.0 or args.control_hz <= 0.0 or args.display_hz <= 0.0:
        raise ValueError("height-step-mm, control-hz, and display-hz must all be positive.")

    # 只创建升降运行时，不初始化双臂、底盘或相机；内部控制逻辑与正式机器人一致。
    config = HeiRebotLiftConfig(
        cameras={},
        lift_motor_port=args.motor_port,
        lift_io_port=args.io_port,
    )
    lift = _LiftRuntime(config.lift_motor_port, config.lift_io_port, config)
    control_period_s = 1.0 / args.control_hz
    display_period_s = 1.0 / args.display_hz
    status = "Connecting; lift will home upward to the upper limit..."

    print(status, flush=True)
    try:
        lift.connect()
        target_height_mm = lift.read_height()["height.pos"]
        status = "Homing complete; ready"
        last_display_s = 0.0

        with TerminalKeyReader() as keyboard:
            running = True
            while running:
                loop_start_s = time.monotonic()
                for key in keyboard.read_keys():
                    key = key.lower()
                    if key == "i":
                        target_height_mm = min(target_height_mm + args.height_step_mm, config.lift_max_height_mm)
                        status = "Target moved upward"
                    elif key == "k":
                        target_height_mm = max(target_height_mm - args.height_step_mm, config.lift_min_height_mm)
                        status = "Target moved downward"
                    elif key == " ":
                        target_height_mm = lift.read_height()["height.pos"]
                        lift.stop()
                        status = "Stopped; target locked to current height"
                    elif key == "h":
                        lift.stop()
                        print("\033[H\033[JHoming upward to the upper limit...", flush=True)
                        lift.home()
                        target_height_mm = lift.read_height()["height.pos"]
                        status = "Homing complete; zero reset"
                    elif key == "x":
                        running = False

                if not running:
                    break

                lift.command_position(target_height_mm)
                now_s = time.monotonic()
                if now_s - last_display_s >= display_period_s:
                    render_dashboard(lift, status, args.height_step_mm)
                    last_display_s = now_s

                time.sleep(max(control_period_s - (time.monotonic() - loop_start_s), 0.0))
    finally:
        # 任意异常或 Ctrl+C 都先发零速，再失能并关闭电机和 IO 串口。
        with suppress(Exception):
            lift.stop()
        with suppress(Exception):
            lift.disconnect(config.disable_torque_on_disconnect)
        print("\n[Lift test] stopped safely")


if __name__ == "__main__":
    main()
