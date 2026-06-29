#!/usr/bin/env python

"""Run a trained policy on HEI ReBot Lift without recording.

机器人端需要先启动 ``hei_rebot_lift_host``。这个脚本只负责远程加载策略并执行动作。
需要记录、上传或更复杂的人机协作流程时，优先使用通用 ``lerobot-rollout`` CLI。
"""

import argparse
import json
from pathlib import Path

from lerobot.configs import PreTrainedConfig
from lerobot.robots.hei_rebot_lift import HeiRebotLiftClientConfig
from lerobot.rollout import BaseStrategyConfig, RolloutConfig, build_rollout_context
from lerobot.rollout.inference import RTCInferenceConfig, SyncInferenceConfig
from lerobot.rollout.strategies import BaseStrategy
from lerobot.utils.process import ProcessSignalHandler
from lerobot.utils.utils import init_logging

FPS = 30
DURATION_SEC = 60
TASK_DESCRIPTION = "My task description"
HF_MODEL_ID = "<hf_username>/<model_repo_id>"
REMOTE_IP = "192.168.31.127"
ROBOT_ID = "hei_rebot_lift"
DEFAULT_RENAME_MAP = {
    "observation.images.front": "observation.images.camera1",
    "observation.images.left_wrist": "observation.images.camera2",
    "observation.images.right_wrist": "observation.images.camera3",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run a trained policy on HEI ReBot Lift.")
    parser.add_argument("--model-id", type=str, default=HF_MODEL_ID, help="Local path or Hugging Face policy id.")
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP, help="HEI ReBot Lift host IP address.")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="HEI ReBot Lift robot id.")
    parser.add_argument("--task", type=str, default=TASK_DESCRIPTION, help="Task text used by VLA policies.")
    parser.add_argument("--fps", type=int, default=FPS, help="Control frequency.")
    parser.add_argument("--duration-sec", type=float, default=DURATION_SEC, help="Run duration; 0 means infinite.")
    parser.add_argument("--display-data", action="store_true", help="Visualize observation/action with Rerun.")
    parser.add_argument(
        "--inference",
        choices=("sync", "rtc"),
        default="sync",
        help="Use sync for first bring-up; rtc is smoother for slow VLA models.",
    )
    parser.add_argument(
        "--rename-map",
        type=str,
        default=None,
        help="JSON feature rename map. By default, HEI front/left_wrist/right_wrist is mapped for camera1/2/3 VLA policies.",
    )
    return parser.parse_args()


def resolve_model_id(model_id: str) -> str:
    path = Path(model_id)
    if path.is_dir():
        if (path / "config.json").is_file():
            return str(path)
        checkpoints_dir = path / "checkpoints"
        if checkpoints_dir.is_dir():
            checkpoint_dirs = sorted(p for p in checkpoints_dir.iterdir() if p.is_dir())
            for checkpoint_dir in reversed(checkpoint_dirs):
                pretrained_dir = checkpoint_dir / "pretrained_model"
                if (pretrained_dir / "config.json").is_file():
                    return str(pretrained_dir)

    # LeRobot 当前版本有些训练目录没有生成 checkpoints/last，只有 001000/010000 这种步数目录。
    missing_last = Path(model_id)
    if "last" in missing_last.parts:
        last_index = missing_last.parts.index("last")
        checkpoints_dir = Path(*missing_last.parts[:last_index])
        if checkpoints_dir.is_dir():
            checkpoint_dirs = sorted(p for p in checkpoints_dir.iterdir() if p.is_dir() and p.name != "last")
            for checkpoint_dir in reversed(checkpoint_dirs):
                candidate = checkpoint_dir.joinpath(*missing_last.parts[last_index + 1 :])
                if (candidate / "config.json").is_file():
                    return str(candidate)

    return model_id


def infer_rename_map(policy_config, explicit_rename_map: str | None) -> dict[str, str]:
    if explicit_rename_map:
        return json.loads(explicit_rename_map)

    image_features = getattr(policy_config, "image_features", {})
    expected_images = set(image_features)
    if {
        "observation.images.camera1",
        "observation.images.camera2",
        "observation.images.camera3",
    }.issubset(expected_images):
        return DEFAULT_RENAME_MAP

    return {}


def main():
    args = parse_args()
    init_logging()

    robot_config = HeiRebotLiftClientConfig(remote_ip=args.remote_ip, id=args.robot_id)

    model_id = resolve_model_id(args.model_id)
    policy_config = PreTrainedConfig.from_pretrained(model_id)
    policy_config.pretrained_path = model_id
    inference_config = RTCInferenceConfig() if args.inference == "rtc" else SyncInferenceConfig()

    cfg = RolloutConfig(
        robot=robot_config,
        policy=policy_config,
        strategy=BaseStrategyConfig(),
        inference=inference_config,
        fps=args.fps,
        duration=args.duration_sec,
        task=args.task,
        display_data=args.display_data,
        rename_map=infer_rename_map(policy_config, args.rename_map),
    )

    signal_handler = ProcessSignalHandler(use_threads=True)
    ctx = build_rollout_context(cfg, signal_handler.shutdown_event)

    strategy = BaseStrategy(cfg.strategy)
    try:
        strategy.setup(ctx)
        strategy.run(ctx)
    finally:
        strategy.teardown(ctx)


if __name__ == "__main__":
    main()
