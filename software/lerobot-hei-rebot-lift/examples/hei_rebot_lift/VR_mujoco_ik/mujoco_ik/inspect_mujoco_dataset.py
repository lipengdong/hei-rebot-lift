#!/usr/bin/env python
"""Print one HEI MuJoCo dataset sample and export its three camera frames."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from lerobot.datasets import LeRobotDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect one HEI MuJoCo dataset episode.")
    parser.add_argument("--repo-id", default="HGM/hei_rebot_lift_mujoco")
    parser.add_argument("--root", type=Path, default=None, help="Local dataset root.")
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--frame-index", type=int, default=0, help="Frame within the selected episode.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/mujoco_dataset_sample"))
    return parser.parse_args()


def tensor_image_to_rgb(image) -> np.ndarray:
    array = image.detach().cpu().numpy() if hasattr(image, "detach") else np.asarray(image)
    if array.ndim == 3 and array.shape[0] in (1, 3, 4):
        array = np.moveaxis(array, 0, -1)
    if np.issubdtype(array.dtype, np.floating):
        array = np.clip(array * 255.0, 0.0, 255.0).astype(np.uint8)
    return array[..., :3]


def print_action_coverage(dataset: LeRobotDataset) -> None:
    """Report which action dimensions actually changed in the recorded dataset."""
    stats = dataset.meta.stats
    action_stats = stats.get("action") if stats is not None else None
    if action_stats is None:
        print("[HEI Sim Inspect] WARNING: action statistics are unavailable", flush=True)
        return

    names = dataset.features["action"].get("names") or []
    minimum = np.asarray(action_stats["min"], dtype=float).reshape(-1)
    maximum = np.asarray(action_stats["max"], dtype=float).reshape(-1)
    if len(names) != len(minimum):
        print("[HEI Sim Inspect] WARNING: action names/statistics length mismatch", flush=True)
        return

    spans = maximum - minimum
    moving = [name for name, span in zip(names, spans, strict=True) if span > 1e-5]
    constant = [name for name, span in zip(names, spans, strict=True) if span <= 1e-5]
    print(
        f"[HEI Sim Inspect] moving action fields ({len(moving)}/{len(names)}): "
        f"{', '.join(moving) if moving else 'none'}",
        flush=True,
    )
    print(
        f"[HEI Sim Inspect] constant action fields ({len(constant)}/{len(names)}): "
        f"{', '.join(constant) if constant else 'none'}",
        flush=True,
    )
    if not moving:
        print(
            "[HEI Sim Inspect] WARNING: every action field is constant. "
            "A policy trained on this dataset will only learn to hold the initial pose.",
            flush=True,
        )


def main() -> None:
    args = parse_args()
    dataset = LeRobotDataset(
        repo_id=args.repo_id,
        root=args.root,
        episodes=[args.episode_index],
        return_uint8=True,
    )
    if not 0 <= args.frame_index < len(dataset):
        raise IndexError(f"frame index {args.frame_index} is outside [0, {len(dataset) - 1}]")
    sample = dataset[args.frame_index]
    print(
        f"[HEI Sim Inspect] root={dataset.root}, episode={args.episode_index}, "
        f"frames={len(dataset)}, fps={dataset.fps}",
        flush=True,
    )
    print(f"[HEI Sim Inspect] observation.state={sample['observation.state']}", flush=True)
    print(f"[HEI Sim Inspect] action={sample['action']}", flush=True)
    print(f"[HEI Sim Inspect] task={sample.get('task', '')}", flush=True)
    print_action_coverage(dataset)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("front", "left_wrist", "right_wrist"):
        key = f"observation.images.{name}"
        rgb = tensor_image_to_rgb(sample[key])
        path = args.output_dir / f"episode_{args.episode_index:03d}_frame_{args.frame_index:04d}_{name}.png"
        if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
            raise RuntimeError(f"Failed to save {path}")
        print(f"[HEI Sim Inspect] {name} -> {path}", flush=True)


if __name__ == "__main__":
    main()
