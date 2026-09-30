# MuJoCo Dataset, Training, and Rollout

[English](SIM_DATASET_WORKFLOW.md) | [中文](SIM_DATASET_WORKFLOW_zh.md)

This workflow uses two independent processes and Conda environments. MuJoCo owns simulation, IK, camera rendering, and action execution. LeRobot owns dataset writing, training, and policy inference. ZMQ carries synchronized observations and actions between them; no physical robot is connected.

## 1. Architecture

| Process | Conda environment | Entry point | Responsibility |
| --- | --- | --- | --- |
| VR demonstration simulation | `hei-rebot-vr` | `run_hei_robot_vr_dataset_sim.sh` | Receive VR input, run MuJoCo, publish observations and demonstration actions |
| Keyboard demonstration simulation | `hei-rebot-vr` | `run_hei_robot_keyboard_dataset_sim.sh` | Receive keyboard input, run MuJoCo, and publish demonstration samples |
| VR dataset recorder | `lerobot5` | `run_hei_robot_mujoco_record.sh` | Receive VR simulation samples and write a LeRobotDataset |
| Keyboard dataset recorder | `lerobot5` | `run_hei_robot_keyboard_record.sh` | Receive keyboard simulation samples and write a LeRobotDataset |
| Policy simulation | `hei-rebot-vr` | `run_hei_robot_policy_sim.sh` | Run MuJoCo and execute policy actions |
| Policy inference | `lerobot5` | `run_hei_robot_mujoco_rollout.sh` | Load a policy, infer actions, and send them to simulation |

The default observation and command ports are TCP `6565` and `6566`. Use `--sim-ip 127.0.0.1` when both processes run on the same computer.

Keep the environments separate: do not install the LeRobot training stack into `hei-rebot-vr`.

## 2. Record VR Simulation Data

Start Telegrip and open its control page in the headset. Hold the **Meta Quest Button for three seconds** whenever the headset position/orientation changes or controller directions no longer match the robot.

Terminal 1, start the VR simulation:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_dataset_sim.sh --publish-fps 30
```

Terminal 2, start the LeRobot recorder:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_mujoco_record.sh \
  --repo-id HGM/hei_rebot_lift_mujoco \
  --root datasets/hei_rebot_lift_mujoco \
  --num-episodes 10 \
  --episode-time-sec 30 \
  --fps 30 \
  --task "Pick up the red cube with the right gripper and place it in the center of the table."
```

Recorder keys:

| Key | Action |
| --- | --- |
| Right arrow | Finish and save the current episode early |
| Left arrow | Discard and re-record the current episode |
| `Esc` | Stop and finalize the dataset |

Use matching FPS values on both sides. The simulation control loop remains unrestricted and only publishes synchronized samples at `--publish-fps`; the recorder never starts MuJoCo.

To append data, use the same explicit `--root` and add `--resume`. If the processes run on different computers, pass the simulation computer address through `--sim-ip` and allow TCP ports `6565/6566`.

## 3. Record Keyboard Simulation Data

Keyboard recording does not require Telegrip. The existing `run_hei_robot_keyboard_sim.sh` is for control practice only and does not publish dataset samples. Use `run_hei_robot_keyboard_dataset_sim.sh` when recording.

Terminal 1:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_dataset_sim.sh --publish-fps 30
```

Terminal 2:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_keyboard_record.sh \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --num-episodes 10 \
  --episode-time-sec 30 \
  --fps 30 \
  --task "Pick up the red cube with the right gripper and place it in the center of the table."
```

Use `1` for chassis, `2` for lift, `3/4` for left/right arm, and `5/6` to reset the arms. Chassis uses `W/S A/D Q/E`; lift uses `I/K`; arm translation uses `W/S A/D R/F`; arm rotation uses `U/J I/K O/L`; `Z/X` opens/closes the active gripper. Hold `Shift` for fine control, `Space` to stop/hold, and `Backspace` to reset the complete scene.

The recorder still uses Right Arrow to save early, Left Arrow to discard/re-record, and `Esc` to stop. Both processes listen for `Esc`, so the keyboard simulation also exits as a safety behavior.

## 4. Inspect Data

Enter the software repository root first:

```bash
cd software/lerobot-hei-rebot-lift
```

Visualize a complete keyboard-simulation episode in Rerun:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  lerobot-dataset-viz \
  --repo-id HGM/hei_rebot_lift_keyboard_mujoco \
  --root datasets/hei_rebot_lift_keyboard_mujoco \
  --episode-index 0
```

Episode index `0` is the first episode. `--root` must point to the local dataset directory containing `meta/info.json`; otherwise LeRobot attempts to download the repository from Hugging Face.

Inspect one frame and export all three camera images:

```bash
PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  python -u examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/inspect_mujoco_dataset.py \
  --repo-id HGM/hei_rebot_lift_mujoco \
  --root datasets/hei_rebot_lift_mujoco \
  --episode-index 0 --frame-index 0
```

The command exports all three camera frames under `outputs/mujoco_dataset_sample/`. Before a full recording session, verify the 18-D state/action vectors, camera names, gripper units, lift range, and normalized yaw command.

The inspector also prints `moving action fields` and `constant action fields`.
Before training, every arm, gripper, base, or lift field required by the task
must appear in the moving list. If all 18 action fields are constant, a policy
can only learn to hold the initial pose. If the task says right arm while only
left-arm fields move, re-record the demonstration or correct the task text.

## 5. Train ACT

Training runs only in `lerobot5`. This example trains the **keyboard simulation dataset**:

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_keyboard_mujoco \
  --dataset.root=datasets/hei_rebot_lift_keyboard_mujoco \
  --policy.type=act --policy.device=cuda --policy.push_to_hub=false \
  --output_dir=outputs/train/act_hei_rebot_lift_keyboard_mujoco \
  --job_name=act_hei_rebot_lift_keyboard_mujoco \
  --batch_size=8 --steps=100000 --save_freq=10000 --log_freq=200 \
  --num_workers=4 --wandb.enable=false
```

Use `--steps=1000` for an initial pipeline check.

For a VR simulation dataset, replace `keyboard_mujoco` with `mujoco` in
`repo_id`, `root`, `output_dir`, and `job_name`. Do not mix keyboard and VR
dataset names. The checkpoint's `train_config.json` records the dataset that
was actually used.

## 6. Run a Policy in MuJoCo

Stop the VR demonstration simulation first. Terminal 1:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_policy_sim.sh --publish-fps 30
```

Terminal 2:

```bash
./run_hei_robot_mujoco_rollout.sh \
  --model-id outputs/train/act_hei_rebot_lift_keyboard_mujoco \
  --task "Use exactly the same task description that was recorded in the dataset" \
  --duration-sec 30 --fps 30 --device cuda
```

Inference only computes actions. The policy simulation process owns the MuJoCo
window and execution. `requested=hold` means the model currently requests no
visible motion. If it never requests motion for three seconds, rollout prints a
dataset/task mismatch warning. If inference stops or times out, the server holds
arm/lift positions and zeros chassis velocity.

## 7. Compatibility Boundary

Simulation and hardware use the same 18-D field names, units, order, and three camera names. The stable grasp is still deterministic and does not reproduce real contact, friction, load, or imaging. Validate the task in simulation, then fine-tune with real demonstrations for sim-to-real use.
