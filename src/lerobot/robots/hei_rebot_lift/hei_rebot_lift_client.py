#!/usr/bin/env python

from functools import cached_property

from lerobot.robots.lekiwi.lekiwi_client import LeKiwiClient

from .config_hei_rebot_lift import HeiRebotLiftClientConfig

ARM_JOINTS = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6", "gripper")


class HeiRebotLiftClient(LeKiwiClient):
    config_class = HeiRebotLiftClientConfig
    name = "hei_rebot_lift_client"

    @cached_property
    def _state_ft(self) -> dict[str, type]:
        features = {}
        for side in ("right", "left"):
            for joint in ARM_JOINTS:
                features[f"{side}_{joint}.pos"] = float
        features.update({"x.vel": float, "y.vel": float, "theta.vel": float, "height.pos": float})
        return features
