# HEI ReBot Lift Examples

[English](README.md) | [中文](README_zh.md)

This directory is the real-robot entry point for HEI ReBot Lift. It covers hardware checks, VR/MuJoCo teleoperation, data recording, dataset cleanup, training, replay, evaluation, and policy rollout.

Unless noted otherwise, run each command block in a new terminal at
`software/lerobot-hei-rebot-lift/`, not in this examples folder. Install the
LeRobot environment using the [project setup guide](../../../../README.md) first.

Robot driver code:

```text
src/lerobot/robots/hei_rebot_lift/
```

VR/MuJoCo IK subsystem:

```text
examples/hei_rebot_lift/VR_mujoco_ik/
```

## Scripts

```text
debug/Arm_Zero_Status_Test.py   Damiao arm zero-writing and status check
debug/Lift_Status_Test.py       Lift homing, I/K position control, limit IO, and motor status
debug/Chassis_Status_Test.py    Keyboard chassis control, speed gears, and four-wheel status
debug/Port_Binding_Wizard.py    Guided serial discovery, diagnosis, and udev port binding
teleoperate.py            Teleoperate only, without recording data
record.py                 Record LeRobotDataset with VR teleoperation
replay.py                 Replay actions from a recorded episode
evaluate.py               Evaluate an ACT policy on the real robot and record eval data
rollout.py                Run ACT / SmolVLA policies on the real robot without recording
vr_control.py             Convert MuJoCo/VR ZMQ data to LeRobot actions
VR_mujoco_ik/             Telegrip + MuJoCo + Pinocchio IK integrated VR control stack
```

## Recommended Terminal Layout

Real-robot recording usually uses four terminals:

```text
Terminal 1: robot-side host
Terminal 2: Telegrip VR page
Terminal 3: complete-model MuJoCo IK + real-robot bridge
Terminal 4: record.py data recording
```

Example robot IP (script defaults may differ; always pass `--remote-ip`):

```text
192.168.31.127
```

If the IP changes, pass `--remote-ip NEW_IP` to `teleoperate.py`, `record.py`, `replay.py`, `evaluate.py`, or `rollout.py`. The scripts print the effective `host=...` before connecting.

## Minimal End-to-End Flow

Before this real-robot flow, complete [pure simulation practice](VR_mujoco_ik/README.md#2a-test-vr-with-the-complete-robot-model). Do not run the host/client/real bridge during practice.

1. On the robot side, check udev ports, cameras, and Damiao motors.
2. Start `hei-rebot-lift-host` and wait for lift homing to finish.
3. On the computer, start `VR_mujoco_ik/run_telegrip.sh`.
4. Open `https://COMPUTER_IP:8443` in the VR headset browser and enter VR.
5. Start `teleoperate.py` to supply robot feedback; it waits for VR actions.
6. Start `VR_mujoco_ik/run_hei_robot_vr_real.sh --enable-real-publish`, release both grips together, and wait for `command bridge ARMED`; then verify directions slowly.
7. Stop `teleoperate.py`, start `record.py`, and release both grips to re-arm after feedback reconnects.
8. Use `lerobot-dataset-viz` to inspect data, and use `lerobot-edit-dataset` to delete bad episodes if needed.
9. Train ACT or SmolVLA.
10. Stop VR command publishing and recording before using `rollout.py` for real-robot inference; leave the host running.

## 1. Hardware Check

Find cameras:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-find-cameras
```

List supported formats for one camera:

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

Default three-camera setup:

```text
front       /dev/video0
left_wrist  /dev/video2
right_wrist /dev/video4
```

Cameras use `MJPG` by default for better stability with multiple USB cameras.

### Serial port binding wizard

Run on the **robot-side Jetson**, with the host and all serial debug tools stopped.
Power down and support the arms before changing wiring. Temporarily disconnect
right-arm IDs 4-7, leaving IDs 1-3; keep left-arm IDs 1-7, chassis IDs 1-4, and
lift ID 1 connected. Power the four U2CAN boards, motors, and limit IO for scanning.

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  python -u examples/hei_rebot_lift/debug/Port_Binding_Wizard.py
```

The wizard identifies motor IDs and valid limit IO frames, reports missing/busy
or ambiguous devices, and asks for confirmation before writing
`examples/hei_rebot_lift/rules/99-nx-robot.rules`. It can install the rules into
`/etc/udev/rules.d/` with sudo and preserves existing lidar/IMU rules.
It does not enable motors, write zeros, or command motion. Keep USB sockets
unchanged; bindings use physical topology. Use `--yes --install` only for
verified, unambiguous repeat binding.

```bash
ls -l /dev/hei_right_arm /dev/hei_left_arm /dev/hei_chassis /dev/hei_lift /dev/hei_lift_io
```

After verification, power down, reconnect right-arm IDs 4-7, then power up.
For detailed diagnosis and hardware test precautions, see the
[project device mapping guide](../../../../README.md#-device-mapping).

### Arm mechanical zero calibration

> [!WARNING]
> **The zero-writing script immediately disables and writes zeros to IDs 1-7,
> without confirmation. It is not a read-only status tool.** Support the arm,
> position it at the designed mechanical zero, and close the gripper to its
> physical zero (`0 rad`) without forcing it. Do not use an arbitrary VR pose.
> Confirm all seven motors are connected before starting.

<p align="center">
  <a href="../../../../media/arm_zero.png"><img src="../../../../media/arm_zero.png" alt="Designed mechanical zero posture of both arms" width="70%"></a>
  <br>
  <em>Designed mechanical zero posture reference. Verify each joint against the assembly design before writing zeros; this is not the VR working pose.</em>
</p>

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Arm_Zero_Status_Test.py \
  --port /dev/hei_right_arm
```

Exit with `Ctrl+C`, correctly position the left arm, then repeat with
`--port /dev/hei_left_arm`. The dashboard shows cached POS/VEL/TORQUE/state.
A displayed zero does not prove motor connectivity or successful calibration.
This procedure is for assembly/maintenance, not every startup.

### Independent lift test

Run only on the robot, with the host and other serial tools stopped.
**Startup automatically homes upward; verify both limit switches and clear the
travel path.** Use an interactive terminal; for SSH allocate a TTY (`ssh -t`).
The tool reuses production homing, feedback-based height control, and limits.

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Lift_Status_Test.py \
  --motor-port /dev/hei_lift --io-port /dev/hei_lift_io --height-step-mm 5
```

`I/K` raises/lowers the target by 5 mm per key event in this example
(the program default is 10 mm). `Space` stops and holds the reported height,
`H` homes again, and `X` or `Ctrl+C` exits and disables.
Check height `-800..0 mm`, IO freshness, both limits, and motor state.
Stop for offline IO or inconsistent limits; software stop keys are not an
emergency stop.

### Independent chassis test

Secure the wheels off the ground and clear cables/people first. Run on the robot
with the host stopped, in an interactive terminal.

```bash
conda activate lerobot5
PYTHONPATH=src python -u examples/hei_rebot_lift/debug/Chassis_Status_Test.py \
  --port /dev/hei_chassis
```

`W/S/A/D` translates, `Q/E` rotates, `1/2/3` selects low/medium/high gear.
Start with gear 1. `Space` commands zero wheel speed; `X` or `Ctrl+C` exits.
Hold/repeat direction keys; the watchdog clears stale requests after 0.65 s.

**All four wheels use chassis kinematics; there is no individual-wheel jog mode.**
IDs: 1 right front, 2 right rear, 3 left rear, 4 left front.
The fixed dashboard shows requested/reconstructed body velocity, wheel
target/measured angular velocity, position, torque, and state codes.
Body values are driver command units, not directly measured m/s.
Exit all debug tools before starting the host.

## 2. Start Robot-Side Host

Run on the robot side:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

The host connects the arms, chassis, lift, and cameras; homes the lift to `height.pos = 0`; listens for commands on `6555`; and publishes observations/images on `6556`.

## 3. Start VR + MuJoCo IK

Run this section on your computer. Start the client in section 4 before the real
bridge so feedback is available. For button diagrams, **Meta Quest recentering
(hold about 3 seconds)**, grip/trigger behavior, and all three 1-second safety
links, follow the [VR controller guide](VR_mujoco_ik/README.md#vr-controller-tutorial).
VR image streaming is currently disabled; enable it explicitly only if needed.

Create the unified environment:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

Start Telegrip:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

Open in the VR headset browser:

```text
https://COMPUTER_IP:8443
```

Start the complete-model MuJoCo IK real-robot bridge:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

Start one client (`teleoperate.py` or `record.py`) in a separate terminal to
provide fresh feedback on `6559`. With fresh VR data, release both grips together
and wait for `command bridge ARMED`; grip release alone cannot unlock it.
For the legacy dual-arm model, use `./run_mujoco_ik.sh` instead.

Default data flow:

```text
Telegrip -> MuJoCo IK: tcp://localhost:5567
MuJoCo IK -> record.py: tcp://*:6558
```

Pinocchio/CasADi dependencies are provided by conda-forge packages in `environment.yml`. Do not install `pin` separately with pip.

## 4. Teleoperation Test

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py   --remote-ip 192.168.31.127
```

Control logic:

- Arms are generated from VR controller poses through MuJoCo IK.
- Right grip pressed: right joystick controls the chassis; releasing the grip stops the chassis.
- Left grip pressed: left joystick Y controls lift direction; releasing the grip stops the lift.
- The lift action is sent as target `height.pos`, not as raw velocity integration.

## 5. Record Data

Stop `teleoperate.py` before starting this script; both would compete for the
feedback port and robot control. Re-arm the real bridge after feedback reconnects.

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --remote-ip 192.168.31.127   --repo-id HGM/hei_rebot_lift_task1   --num-episodes 5   --episode-time-sec 120   --reset-time-sec 30   --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

By default, data is saved locally and is not pushed to the Hugging Face Hub. Add `--push-to-hub` only when needed.

Resume an existing dataset (`--root` is required):

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py \
  --remote-ip 192.168.31.127 \
  --repo-id HGM/hei_rebot_lift_task1 \
  --root ~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1 \
  --resume --num-episodes 5
```

Use the actual path printed by `Dataset ready at ...` if your cache location is
different. Keep camera names, shapes, and FPS consistent; use a new dataset after
schema changes. `--num-episodes 5` adds five episodes during this run.

## 6. Visualize and Clean Data

Episode indices start at zero. Back up the dataset before editing; deletion
renumbers remaining episodes. Do not edit a dataset while recording into it.

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-dataset-viz   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-edit-dataset   --repo_id HGM/hei_rebot_lift_task1   --new_repo_id HGM/hei_rebot_lift_task1   --operation.type delete_episodes   --operation.episode_indices "[57]"
```

## 7. Train ACT

Training does not require the robot host or VR stack. Short runs below are
pipeline checks, not proof of policy quality. For data recorded with a custom `--root`, add `--dataset.root=YOUR_DATASET_PATH`
to training so it reads the correct local dataset. The repo ID must also match.

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=act   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/act_hei_rebot_lift_task1   --job_name=act_hei_rebot_lift_task1   --batch_size=8   --steps=10000   --save_freq=10000   --log_freq=200   --num_workers=4   --wandb.enable=false
```

## 8. Train SmolVLA

Install its extra dependencies from the software root first:

```bash
conda run --no-capture-output -n lerobot5 python -m pip install -e ".[smolvla]"
```

The generic `training` extra does not include every VLA policy dependency.
The first run may download the vision-language backbone and tokenizer; offline
mode works only after all required files have been cached. Set
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1` in that
terminal when an entirely local run is intended. Missing files still cause an error.

Three-camera data is automatically mapped during rollout:

```text
front       -> camera1
left_wrist  -> camera2
right_wrist -> camera3
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=smolvla   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/smolvla_hei_rebot_lift_task1   --job_name=smolvla_hei_rebot_lift_task1   --batch_size=1   --steps=1000   --save_freq=1000   --log_freq=50   --num_workers=2   --wandb.enable=false
```

## 9. Policy Rollout

Keep the host running but stop VR real publishing, teleoperation, recording,
and replay first. Run only one command source. Check that `--model-id` points to
an existing pretrained model directory, camera names match training, and the task
describes the demonstrated behavior. `--fps` changes control timing, not model
inference performance; lowering it changes how recorded trajectories are executed.

ACT and SmolVLA both use `rollout.py`:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --remote-ip 192.168.31.127   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 30   --inference sync
```

SmolVLA example:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py \
  --remote-ip 192.168.31.127 \
  --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model \
  --task "Pick up the yellow block from the floor and put it on the table in front" \
  --duration-sec 60 --fps 10 --inference rtc
```

`sync` executes inference inline; `rtc` uses the project's real-time chunking
engine. Check camera compatibility and control timing; a slower FPS does not
make inference faster. Rollout normally attempts to return to the captured
initial joint/lift position during shutdown; keep that path clear too.

## 10. Replay and Evaluate

Keep the host, but stop all other robot command sources, including VR publishing.
Replay reproduces recorded actions; evaluate runs an **ACT** policy and saves
new local episodes. It does not automatically calculate a task success rate,
and is not the SmolVLA entry. Set the actual dataset/model path and task text.

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/replay.py   --remote-ip 192.168.31.127   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0   --display-data
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/evaluate.py   --remote-ip 192.168.31.127   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --dataset-id HGM/hei_rebot_lift_task1_eval   --num-episodes 5   --episode-time-sec 60
```

## Troubleshooting

- `Failed to connect to Speech Dispatcher` is usually a voice notification issue and does not affect data saving or robot control.
- Camera timeout: check `fourcc="MJPG"`, USB bandwidth, FPS, and resolution.
- Empty episode: check Telegrip, MuJoCo IK, the `6558` publisher, and whether `saved_frames` is increasing.
- ACT image KeyError: camera names used for training do not match the current robot config.

## Chinese Version

- [README_zh.md](README_zh.md)
