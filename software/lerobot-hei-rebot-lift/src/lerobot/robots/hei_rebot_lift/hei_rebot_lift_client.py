#!/usr/bin/env python

import base64
import json
import logging
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

    def _parse_observation(self, frames: list[bytes]):
        """Accept the LeRobot 0.6 multipart protocol and the legacy HEI JSON protocol."""
        if len(frames) != 1:
            return super()._parse_observation(frames)

        try:
            observation = json.loads(frames[0])
            if "_cams" in observation:
                return super()._parse_observation(frames)

            # Older HEI hosts embedded every JPEG as a Base64 JSON string.
            for camera_name in self._cameras_ft:
                encoded = observation.get(camera_name)
                if isinstance(encoded, str) and encoded:
                    observation[camera_name] = base64.b64decode(encoded)
            return observation
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logging.error("Error decoding HEI observation: %s", exc)
            return None
