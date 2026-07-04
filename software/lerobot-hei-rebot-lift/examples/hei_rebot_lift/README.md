# HEI ReBot Lift Examples

This directory is the real-robot entry point for HEI ReBot Lift. It covers hardware checks, VR/MuJoCo teleoperation, data recording, dataset cleanup, training, replay, evaluation, and policy rollout.

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
Arm_Zero_Status_Test.py   Damiao arm zero-writing and status check
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
Terminal 3: MuJoCo IK
Terminal 4: record.py data recording
```

Default robot IP:

```text
192.168.31.127
```

If the IP changes, pass `--remote-ip NEW_IP` to the scripts.

## Minimal End-to-End Flow

1. On the robot side, check udev ports, cameras, and Damiao motors.
2. Start `hei-rebot-lift-host` and wait for lift homing to finish.
3. On the computer, start `VR_mujoco_ik/run_telegrip.sh`.
4. Open `https://COMPUTER_IP:8443` in the VR headset browser and enter VR.
5. Start `VR_mujoco_ik/run_mujoco_ik.sh`.
6. Run `teleoperate.py` first to verify arm, base, and lift directions.
7. Run `record.py` to collect data.
8. Use `lerobot-dataset-viz` to inspect data, and use `lerobot-edit-dataset` to delete bad episodes if needed.
9. Train ACT or SmolVLA.
10. Use `rollout.py` for real-robot inference.

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

Damiao arm zero-writing and status check:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/Arm_Zero_Status_Test.py   --port /dev/hei_right_arm
```

Temporary debugging with a raw port:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/Arm_Zero_Status_Test.py   --port /dev/ttyACM1
```

## 2. Start Robot-Side Host

Run on the robot side:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

The host connects the arms, chassis, lift, and cameras; homes the lift to `height.pos = 0`; listens for commands on `6555`; and publishes observations/images on `6556`.

## 3. Start VR + MuJoCo IK

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

Start MuJoCo IK:

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

Default data flow:

```text
Telegrip -> MuJoCo IK: tcp://localhost:5567
MuJoCo IK -> record.py: tcp://*:6558
```

Pinocchio/CasADi dependencies are provided by conda-forge packages in `environment.yml`. Do not install `pin` separately with pip.

## 4. Teleoperation Test

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py
```

Control logic:

- Arms are generated from VR controller poses through MuJoCo IK.
- Right grip pressed: right joystick controls the chassis; releasing the grip stops the chassis.
- Left grip pressed: left joystick Y controls lift direction; releasing the grip stops the lift.
- The lift action is sent as target `height.pos`, not as raw velocity integration.

## 5. Record Data

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py   --repo-id HGM/hei_rebot_lift_task1   --num-episodes 5   --episode-time-sec 120   --reset-time-sec 30   --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

By default, data is saved locally and is not pushed to the Hugging Face Hub. Add `--push-to-hub` only when needed.

## 6. Visualize and Clean Data

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-dataset-viz   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-edit-dataset   --repo_id HGM/hei_rebot_lift_task1   --new_repo_id HGM/hei_rebot_lift_task1   --operation.type delete_episodes   --operation.episode_indices "[57]"
```

## 7. Train ACT

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train   --dataset.repo_id=HGM/hei_rebot_lift_task1   --policy.type=act   --policy.device=cuda   --policy.push_to_hub=false   --output_dir=outputs/train/act_hei_rebot_lift_task1   --job_name=act_hei_rebot_lift_task1   --batch_size=8   --steps=10000   --save_freq=10000   --log_freq=200   --num_workers=4   --wandb.enable=false
```

## 8. Train SmolVLA

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

ACT and SmolVLA both use `rollout.py`:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --task "Pick up the yellow block from the floor and put it on the table in front"   --duration-sec 30   --inference sync
```

## 10. Replay and Evaluate

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/replay.py   --repo-id HGM/hei_rebot_lift_task1   --episode-index 0   --display-data
```

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/evaluate.py   --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model   --dataset-id HGM/hei_rebot_lift_task1_eval   --num-episodes 5   --episode-time-sec 60
```

## Troubleshooting

- `Failed to connect to Speech Dispatcher` is usually a voice notification issue and does not affect data saving or robot control.
- Camera timeout: check `fourcc="MJPG"`, USB bandwidth, FPS, and resolution.
- Empty episode: check Telegrip, MuJoCo IK, the `6558` publisher, and whether `saved_frames` is increasing.
- ACT image KeyError: camera names used for training do not match the current robot config.

## Chinese Version

- [README_zh.md](README_zh.md)
