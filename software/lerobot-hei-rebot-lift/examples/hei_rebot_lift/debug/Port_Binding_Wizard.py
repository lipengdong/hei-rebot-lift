#!/usr/bin/env python
"""Interactively identify HEI ReBot Lift serial devices and create udev rules."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import serial

from lerobot.motors.damiao_u2can import DM_Motor_Type, Motor, MotorControl
from lerobot.robots.hei_rebot_lift.hei_rebot_lift import _LimitSwitchReader


U2CAN_USB_ID = ("2e88", "4603")
LIFT_IO_USB_ID = ("1a86", "7523")
MOTOR_BAUD = 921600
IO_BAUD = 115200
MAX_MOTOR_ID = 7
RULE_NAME = "99-nx-robot.rules"
DEFAULT_RULES_FILE = Path(__file__).resolve().parents[1] / "rules" / RULE_NAME

ROLE_ORDER = ("right_arm", "left_arm", "lift", "chassis", "lift_io")
ROLE_LABELS = {
    "right_arm": "右臂 U2CAN（临时只连接关节 ID 1-3）",
    "left_arm": "左臂 U2CAN（完整连接 ID 1-7）",
    "lift": "升降 DM4310 U2CAN（ID 1）",
    "chassis": "底盘四轮 U2CAN（ID 1-4）",
    "lift_io": "升降上下限位 IO 串口",
}
EXPECTED_MOTOR_IDS = {
    "right_arm": frozenset(range(1, 4)),
    "left_arm": frozenset(range(1, 8)),
    "lift": frozenset({1}),
    "chassis": frozenset(range(1, 5)),
}


@dataclass
class PortInfo:
    device: Path
    vendor_id: str = ""
    product_id: str = ""
    serial_short: str = ""
    id_path: str = ""
    devpath: str = ""
    usb_kernel: str = ""
    motor_ids: set[int] = field(default_factory=set)
    motor_scan_error: str = ""
    io_valid: bool = False
    io_state: int | None = None
    io_scan_error: str = ""

    @property
    def usb_id(self) -> tuple[str, str]:
        return self.vendor_id.lower(), self.product_id.lower()

    @property
    def is_u2can(self) -> bool:
        return self.usb_id == U2CAN_USB_ID

    @property
    def is_lift_io(self) -> bool:
        return self.usb_id == LIFT_IO_USB_ID


class ProbeMotor(Motor):
    """Motor object that records whether a status response was decoded."""

    def __init__(self, motor_id: int):
        super().__init__(DM_Motor_Type.DM4310, motor_id, 0x10 + motor_id)
        self.responded = False

    def recv_data(self, q: float, dq: float, tau: float, err: int):
        super().recv_data(q, dq, tau, err)
        self.responded = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify HEI ReBot Lift serial ports by connected motor count and create udev rules."
    )
    parser.add_argument("--rules-file", type=Path, default=DEFAULT_RULES_FILE, help="Project udev rules file.")
    parser.add_argument("--motor-baud", type=int, default=MOTOR_BAUD, help="Damiao U2CAN baud rate.")
    parser.add_argument("--io-baud", type=int, default=IO_BAUD, help="Lift limit-switch IO baud rate.")
    parser.add_argument("--probe-attempts", type=int, default=3, help="Status requests sent to each motor ID.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Accept an unambiguous scan without interactive mapping prompts.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install the generated file into /etc/udev/rules.d after writing it.",
    )
    return parser.parse_args()


def print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def ask_enter(prompt: str) -> None:
    try:
        input(prompt)
    except EOFError as exc:
        raise RuntimeError("This guided tool requires an interactive terminal.") from exc


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input(f"{prompt} {suffix} ").strip().lower()
        except EOFError as exc:
            raise RuntimeError("This guided tool requires an interactive terminal.") from exc
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def run_udevadm_properties(device: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name={device}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 udevadm。该向导只支持使用 udev 的 Linux 系统。") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or f"exit={exc.returncode}"
        raise RuntimeError(f"udevadm 查询失败：{message}") from exc

    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


def usb_kernel_from_devpath(devpath: str) -> str:
    """Extract the deepest physical USB node, for example 1-2.1.2."""
    matches = re.findall(r"(?:^|/)(\d+-\d+(?:\.\d+)*)(?=[:/]|$)", devpath)
    return matches[-1] if matches else ""


def discover_serial_ports() -> list[PortInfo]:
    devices = sorted({*Path("/dev").glob("ttyACM*"), *Path("/dev").glob("ttyUSB*")}, key=str)
    ports: list[PortInfo] = []
    for device in devices:
        try:
            properties = run_udevadm_properties(device)
            devpath = properties.get("DEVPATH", "")
            ports.append(
                PortInfo(
                    device=device,
                    vendor_id=properties.get("ID_VENDOR_ID", "").lower(),
                    product_id=properties.get("ID_MODEL_ID", "").lower(),
                    serial_short=properties.get("ID_SERIAL_SHORT", ""),
                    id_path=properties.get("ID_PATH", ""),
                    devpath=devpath,
                    usb_kernel=usb_kernel_from_devpath(devpath),
                )
            )
        except RuntimeError as exc:
            ports.append(PortInfo(device=device, motor_scan_error=str(exc)))
    return ports


def scan_motor_ids(port: PortInfo, baud: int, attempts: int) -> None:
    serial_device = None
    try:
        serial_device = serial.Serial(str(port.device), baud, timeout=0.05)
        serial_device.reset_input_buffer()
        serial_device.reset_output_buffer()
        # MotorControl 会打印一次串口信息，这里收起它，避免破坏向导表格。
        with contextlib.redirect_stdout(io.StringIO()):
            motor_control = MotorControl(serial_device)
        motors = [ProbeMotor(motor_id) for motor_id in range(1, MAX_MOTOR_ID + 1)]
        for motor in motors:
            motor_control.addMotor(motor)

        for motor in motors:
            for _ in range(max(1, attempts)):
                motor_control.refresh_motor_status(motor)
                time.sleep(0.015)
                motor_control.recv()
                if motor.responded:
                    port.motor_ids.add(motor.SlaveID)
                    break
        if not port.motor_ids:
            port.motor_scan_error = (
                "U2CAN 串口可打开，但 ID 1-7 均无状态响应；检查电机供电、CAN_H/CAN_L、"
                "终端电阻、电机 ID 和波特率。"
            )
    except serial.SerialException as exc:
        message = str(exc)
        if "busy" in message.lower() or "resource" in message.lower():
            message += "；串口可能被 hei-rebot-lift-host 或其他调试程序占用。"
        port.motor_scan_error = message
    except Exception as exc:
        port.motor_scan_error = f"电机扫描异常：{type(exc).__name__}: {exc}"
    finally:
        if serial_device is not None and serial_device.is_open:
            serial_device.close()


def scan_limit_io(port: PortInfo, baud: int) -> None:
    reader = None
    try:
        reader = _LimitSwitchReader(str(port.device), baud, upper_bit=1, lower_bit=2, timeout_s=0.5)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and not reader.online:
            reader.poll()
            time.sleep(0.01)
        port.io_valid = reader.online
        port.io_state = reader.state if reader.online else None
        if not reader.online:
            port.io_scan_error = "USB 设备存在，但 1.5 秒内未收到有效限位 Modbus 帧。"
    except serial.SerialException as exc:
        message = str(exc)
        if "busy" in message.lower() or "resource" in message.lower():
            message += "；串口可能被机器人 host 占用。"
        port.io_scan_error = message
    except Exception as exc:
        port.io_scan_error = f"限位 IO 扫描异常：{type(exc).__name__}: {exc}"
    finally:
        if reader is not None:
            with contextlib.suppress(Exception):
                reader.close()


def format_ids(ids: set[int]) -> str:
    return ",".join(str(value) for value in sorted(ids)) if ids else "-"


def print_scan_table(ports: list[PortInfo]) -> None:
    print_header("步骤 2/5：串口与设备响应扫描结果")
    print("%-3s %-14s %-11s %-13s %-16s %-8s %-10s" % (
        "No", "DEVICE", "USB ID", "USB KERNEL", "MOTOR IDS", "IO", "RESULT"
    ))
    print("-" * 94)
    for index, port in enumerate(ports, 1):
        usb_id = f"{port.vendor_id}:{port.product_id}" if port.vendor_id else "unknown"
        if port.is_u2can:
            result = "OK" if port.motor_ids else "ERROR"
            io_result = "-"
        elif port.is_lift_io:
            result = "OK" if port.io_valid else "ERROR"
            io_result = f"0x{port.io_state:02X}" if port.io_state is not None else "invalid"
        else:
            result = "IGNORED"
            io_result = "-"
        print(
            "%-3d %-14s %-11s %-13s %-16s %-8s %-10s"
            % (index, port.device.name, usb_id, port.usb_kernel or "?", format_ids(port.motor_ids), io_result, result)
        )

    errors = [port for port in ports if port.motor_scan_error or port.io_scan_error]
    if errors:
        print("\n详细诊断：")
        for port in errors:
            if port.motor_scan_error:
                print(f"  [ERROR] {port.device}: {port.motor_scan_error}")
            if port.io_scan_error:
                print(f"  [ERROR] {port.device}: {port.io_scan_error}")


def automatic_assignments(ports: list[PortInfo]) -> tuple[dict[str, PortInfo], list[str]]:
    assignments: dict[str, PortInfo] = {}
    problems: list[str] = []
    u2can_ports = [port for port in ports if port.is_u2can]

    if len(u2can_ports) != 4:
        problems.append(f"应检测到 4 块 U2CAN，目前检测到 {len(u2can_ports)} 块。")

    for role, expected_ids in EXPECTED_MOTOR_IDS.items():
        matches = [port for port in u2can_ports if frozenset(port.motor_ids) == expected_ids]
        if len(matches) == 1:
            assignments[role] = matches[0]
        elif not matches:
            problems.append(f"{ROLE_LABELS[role]}：没有端口精确响应电机 ID {sorted(expected_ids)}。")
        else:
            names = ", ".join(str(port.device) for port in matches)
            problems.append(f"{ROLE_LABELS[role]}：有多个候选端口 {names}。")

    io_matches = [port for port in ports if port.is_lift_io]
    valid_io_matches = [port for port in io_matches if port.io_valid]
    if len(valid_io_matches) == 1:
        assignments["lift_io"] = valid_io_matches[0]
    elif len(valid_io_matches) > 1:
        problems.append("升降限位 IO：检测到多个能输出有效状态帧的候选端口。")
    elif len(io_matches) == 1:
        assignments["lift_io"] = io_matches[0]
        problems.append("升降限位 IO USB ID 匹配，但没有读到有效状态帧。")
    elif not io_matches:
        problems.append("未检测到 USB ID 1a86:7523 的升降限位 IO 串口。")
    else:
        problems.append("升降限位 IO：检测到多个 USB ID 相同的候选端口，且均无有效帧。")

    selected_devices = [port.device for port in assignments.values()]
    if len(selected_devices) != len(set(selected_devices)):
        problems.append("自动识别结果把同一个串口分配给了多个模块。")
    return assignments, problems


def choose_port(role: str, candidates: list[PortInfo], default: PortInfo | None, used: set[Path]) -> PortInfo:
    print(f"\n{ROLE_LABELS[role]}")
    for index, port in enumerate(candidates, 1):
        marker = " (auto)" if default is port else ""
        details = f"motor IDs={format_ids(port.motor_ids)}" if role != "lift_io" else f"IO valid={port.io_valid}"
        print(f"  {index}. {port.device}  USB={port.vendor_id}:{port.product_id}  {details}{marker}")

    while True:
        default_index = candidates.index(default) + 1 if default in candidates else None
        suffix = f" [{default_index}]" if default_index is not None else ""
        answer = input(f"请选择 1-{len(candidates)}{suffix}，输入 q 退出：").strip().lower()
        if answer == "q":
            raise KeyboardInterrupt
        if not answer and default_index is not None:
            selected = default
        elif answer.isdigit() and 1 <= int(answer) <= len(candidates):
            selected = candidates[int(answer) - 1]
        else:
            print("输入无效，请重新选择。")
            continue
        if selected.device in used:
            print(f"{selected.device} 已分配给其他模块，不能重复使用。")
            continue
        return selected


def confirm_assignments(
    ports: list[PortInfo],
    automatic: dict[str, PortInfo],
    problems: list[str],
    assume_yes: bool,
) -> dict[str, PortInfo]:
    print_header("步骤 3/5：模块识别与确认")
    if problems:
        print("自动识别发现以下问题：")
        for problem in problems:
            print(f"  [WARNING] {problem}")
    else:
        print("自动识别完整且唯一。")

    if assume_yes:
        if problems or set(automatic) != set(ROLE_ORDER):
            raise RuntimeError("--yes 只能用于完整且无歧义的扫描；请去掉 --yes 后人工处理。")
        return automatic

    if not problems:
        for role in ROLE_ORDER:
            print(f"  {role:10s} -> {automatic[role].device}")
        if ask_yes_no("是否接受以上自动识别结果？", default=True):
            return automatic

    print("\n进入人工确认。请根据电机 ID、USB 位置和实际接线逐项选择。")
    u2can_candidates = [port for port in ports if port.is_u2can]
    io_candidates = [port for port in ports if port.is_lift_io]
    if len(u2can_candidates) < 4 or not io_candidates:
        raise RuntimeError(
            "候选串口数量不足，无法完成五个模块的绑定。请修复接线后重新运行。"
        )

    assignments: dict[str, PortInfo] = {}
    used: set[Path] = set()
    for role in ROLE_ORDER:
        candidates = io_candidates if role == "lift_io" else u2can_candidates
        selected = choose_port(role, candidates, automatic.get(role), used)
        assignments[role] = selected
        used.add(selected.device)

    print("\n人工分配结果：")
    warnings: list[str] = []
    for role in ROLE_ORDER:
        port = assignments[role]
        print(f"  {role:10s} -> {port.device}  USB kernel={port.usb_kernel or '?'}")
        if role in EXPECTED_MOTOR_IDS and frozenset(port.motor_ids) != EXPECTED_MOTOR_IDS[role]:
            warnings.append(
                f"{role} 实测 ID={sorted(port.motor_ids)}，期望 ID={sorted(EXPECTED_MOTOR_IDS[role])}"
            )
        if role == "lift_io" and not port.io_valid:
            warnings.append("lift_io 没有读到有效限位状态帧")

    if warnings:
        print("\n[WARNING] 当前分配仍有风险：")
        for warning in warnings:
            print(f"  - {warning}")
        answer = input("确认硬件情况无误并继续时，请输入大写 YES：").strip()
        if answer != "YES":
            raise RuntimeError("用户取消：未写入规则文件。")
    elif not ask_yes_no("确认写入以上映射？", default=True):
        raise RuntimeError("用户取消：未写入规则文件。")
    return assignments


def validate_rule_attributes(assignments: dict[str, PortInfo]) -> None:
    errors: list[str] = []
    for role, port in assignments.items():
        missing = []
        if not port.vendor_id:
            missing.append("idVendor")
        if not port.product_id:
            missing.append("idProduct")
        if not port.usb_kernel:
            missing.append("KERNELS USB topology")
        if missing:
            errors.append(f"{role} ({port.device}) 缺少 {', '.join(missing)}")
    if errors:
        raise RuntimeError("无法生成可靠规则：\n  " + "\n  ".join(errors))


def make_rule(role: str, port: PortInfo) -> str:
    return (
        f'SUBSYSTEM=="tty", KERNELS=="{port.usb_kernel}", '
        f'ATTRS{{idVendor}}=="{port.vendor_id}", ATTRS{{idProduct}}=="{port.product_id}", '
        f'MODE:="0777", SYMLINK+="hei_{role}"'
    )


def merge_project_rules(existing: str, assignments: dict[str, PortInfo]) -> str:
    managed_pattern = re.compile(r'SYMLINK\+="hei_(?:right_arm|left_arm|lift|chassis|lift_io)"')
    generated_comments = {
        "# HEI ReBot Lift ports generated by debug/Port_Binding_Wizard.py",
        "# Binding uses physical USB topology; keep each adapter in the same USB socket.",
        "# Existing unrelated devices (IMU/lidar) are preserved below.",
    }
    preserved = [
        line
        for line in existing.splitlines()
        if not managed_pattern.search(line) and line.strip() not in generated_comments
    ]
    while preserved and not preserved[0].strip():
        preserved.pop(0)

    generated = [make_rule(role, assignments[role]) for role in ROLE_ORDER]
    lines = [
        "# HEI ReBot Lift ports generated by debug/Port_Binding_Wizard.py",
        "# Binding uses physical USB topology; keep each adapter in the same USB socket.",
        *generated,
    ]
    if preserved:
        lines.extend(["", "# Existing unrelated devices (IMU/lidar) are preserved below.", *preserved])
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_with_backup(path: Path, content: str) -> Path | None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing == content:
        print(f"规则内容没有变化：{path}")
        return None

    backup = None
    if path.exists():
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.{timestamp}.bak")
        shutil.copy2(path, backup)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return backup


def install_rules(project_rules: Path, assignments: dict[str, PortInfo]) -> None:
    print_header("步骤 5/5：安装规则并验证软链接")
    destination = Path("/etc/udev/rules.d") / RULE_NAME
    commands = [
        ["sudo", "install", "-m", "0644", str(project_rules), str(destination)],
        ["sudo", "udevadm", "control", "--reload-rules"],
        ["sudo", "udevadm", "trigger", "--subsystem-match=tty", "--action=add"],
        ["sudo", "udevadm", "settle"],
    ]
    for command in commands:
        print("$ " + " ".join(command))
        subprocess.run(command, check=True)

    print("\n软链接验证：")
    all_ok = True
    for role in ROLE_ORDER:
        link = Path("/dev") / f"hei_{role}"
        expected = assignments[role].device.resolve()
        if link.is_symlink():
            actual = link.resolve()
            ok = actual == expected
            all_ok &= ok
            print(f"  [{'OK' if ok else 'ERROR'}] {link} -> {actual}  expected={expected}")
        else:
            all_ok = False
            print(f"  [ERROR] {link} 未生成")
    if not all_ok:
        print("\n部分软链接未生效。请保持 USB 插口不变，拔插对应设备后重新运行验证。")
    else:
        print("\n全部 HEI ReBot Lift 串口软链接已正确生效。")


def main() -> None:
    args = parse_args()
    if args.probe_attempts <= 0:
        raise RuntimeError("--probe-attempts 必须是大于 0 的整数。")

    print_header("HEI ReBot Lift 串口自动识别与 udev 绑定向导")
    print("本程序不会使能电机、不会写零位、不会发送运动命令。")
    print("识别依据：")
    print("  右臂：只连接电机 ID 1-3（请临时断开右臂 ID 4-7）")
    print("  左臂：连接电机 ID 1-7")
    print("  底盘：连接电机 ID 1-4")
    print("  升降：连接电机 ID 1")
    print("  限位：USB ID 1a86:7523，并能读取有效 IO 帧")
    print("  IMU 和雷达：本次忽略，原规则会原样保留")

    if not args.yes:
        print_header("步骤 1/5：接线准备")
        print("1. 停止 hei-rebot-lift-host 和所有电机/串口调试程序。")
        print("2. 四块 U2CAN、升降限位 IO 和所有需要识别的电机均上电。")
        print("3. 仅将右臂电机 4-7 与右臂总线断开，保留右臂 ID 1-3。")
        print("4. 不要在扫描和规则安装过程中移动 USB 插口。")
        ask_enter("准备完成后按 Enter 开始扫描，Ctrl+C 退出：")

    ports = discover_serial_ports()
    if not ports:
        raise RuntimeError(
            "没有发现 /dev/ttyACM* 或 /dev/ttyUSB* 串口。请检查 USB 连接和系统驱动。"
        )

    for port in ports:
        if port.is_u2can:
            scan_motor_ids(port, args.motor_baud, args.probe_attempts)
        elif port.is_lift_io:
            scan_limit_io(port, args.io_baud)
    print_scan_table(ports)

    automatic, problems = automatic_assignments(ports)
    assignments = confirm_assignments(ports, automatic, problems, args.yes)
    validate_rule_attributes(assignments)

    print_header("步骤 4/5：生成项目规则文件")
    rules_path = args.rules_file.expanduser().resolve()
    existing = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    content = merge_project_rules(existing, assignments)
    print(content)
    backup = atomic_write_with_backup(rules_path, content)
    print(f"已写入：{rules_path}")
    if backup is not None:
        print(f"旧规则备份：{backup}")

    should_install = args.install
    if not args.install and not args.yes:
        should_install = ask_yes_no("是否现在安装到 /etc/udev/rules.d 并重新加载？", default=True)
    if should_install:
        install_rules(rules_path, assignments)
    else:
        print("\n已跳过系统安装。之后可重新运行并添加 --install。")

    print("\n完成。现在可以重新接回右臂电机 4-7；端口绑定不会因此改变。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户取消，没有继续操作。")
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\n[FAILED] {exc}")
        raise SystemExit(1) from exc
