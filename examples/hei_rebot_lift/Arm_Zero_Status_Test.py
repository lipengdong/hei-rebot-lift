#!/usr/bin/env python

import argparse
import time

import serial

from lerobot.motors.damiao_u2can import DM_Motor_Type, Motor, MotorControl

# 默认使用 udev 绑定后的稳定端口名；临时调试可以用 --port /dev/ttyACM? 覆盖。
DEFAULT_PORT = "/dev/hei_right_arm"
BAUDRATE = 921600


def parse_args():
    parser = argparse.ArgumentParser(description="Set Damiao arm motors zero position and print status.")
    parser.add_argument("--port", type=str, default=DEFAULT_PORT, help="U2CAN serial port for the arm driver board.")
    return parser.parse_args()


def print_motor_table(motors,status):
    """刷新终端表格，显示最近一次从驱动板读回的电机状态缓存。"""
    print("\033[H\033[J",end="")
    print(status)
    print("%-8s %-12s %-12s %-12s %-8s" % ("Motor","POS","VEL","TORQUE","ERROR"))
    print("-" * 58)
    for index,motor in enumerate(motors,1):
        print(
            "%-8s %-12.6f %-12.6f %-12.6f %-8d" % (
                "Motor%d" % index,
                motor.getPosition(),
                motor.getVelocity(),
                motor.getTorque(),
                motor.getError(),
            )
        )


def create_arm_motors():
    # 每个 Motor 参数依次为：电机型号、达妙电机 CAN ID、主机接收 ID。
    # 当前机械臂约定：1-3 关节为 DM4340，4-6 关节和夹爪为 DM4310。
    return [
        Motor(DM_Motor_Type.DM4340,0x01,0x11),
        Motor(DM_Motor_Type.DM4340,0x02,0x12),
        Motor(DM_Motor_Type.DM4340,0x03,0x13),
        Motor(DM_Motor_Type.DM4310,0x04,0x14),
        Motor(DM_Motor_Type.DM4310,0x05,0x15),
        Motor(DM_Motor_Type.DM4310,0x06,0x16),
        Motor(DM_Motor_Type.DM4310,0x07,0x17),
    ]


def main():
    args = parse_args()
    motors = create_arm_motors()
    serial_device = serial.Serial(args.port, BAUDRATE, timeout=0.5)
    motor_control = MotorControl(serial_device)

    for motor in motors:
        motor_control.addMotor(motor)

    try:
        for index,motor in enumerate(motors,1):
            # 写零位前先失能，避免电机带力矩时误把当前受力姿态写成零点。
            motor_control.disable(motor)
            motor_control.set_zero_position(motor)
            motor_control.refresh_motor_status(motor)
            print_motor_table(motors,"Setting zero position... Motor%d done" % index)

        while True:
            for index,motor in enumerate(motors,1):
                # 这里只看零位写入后的状态，不给任何运动命令，所以循环保持失能并主动刷新状态。
                motor_control.disable(motor)
                motor_control.refresh_motor_status(motor)
            print_motor_table(motors,"Motor status, disabled. Press Ctrl+C to stop.")
            time.sleep(0.1)

    finally:
        # 无论正常退出还是 Ctrl+C 中断，都确保电机失能并关闭串口。
        for motor in motors:
            motor_control.disable(motor)
        serial_device.close()


if __name__ == "__main__":
    main()
