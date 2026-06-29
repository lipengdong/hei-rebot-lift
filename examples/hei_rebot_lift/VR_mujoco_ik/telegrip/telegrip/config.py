"""Configuration for the minimal Telegrip VR bridge."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .utils import get_absolute_path

logger = logging.getLogger(__name__)


DEFAULT_CONFIG: dict[str, Any] = {
    "network": {
        "https_port": 8443,
        "websocket_port": 8442,
        "host_ip": "0.0.0.0",
    },
    "ssl": {
        "certfile": "cert.pem",
        "keyfile": "key.pem",
    },
    "vr": {
        "enabled": True,
        "zmq_publish_endpoint": "tcp://*:5567",
        "zmq_topic": "vr_data",
        "controller_axes": {
            "enabled": True,
        },
    },
    "vr_images": {
        "enabled": False,
        "opacity": 0.82,
        "endpoint": "tcp://127.0.0.1:6556",
        "color_order": "rgb",
        "socket_type": "pull",
        "topic": "",
        "width": 640,
        "height": 480,
        "fps": 30,
        "jpeg_quality": 95,
        "cameras": [
            {
                "id": "front",
                "enabled": True,
                "name": "Front",
                "image_key": "front",
            },
            {
                "id": "left_wrist",
                "enabled": True,
                "name": "Left Wrist",
                "image_key": "left_wrist",
            },
            {
                "id": "right_wrist",
                "enabled": True,
                "name": "Right Wrist",
                "image_key": "right_wrist",
            },
        ],
    },
}


def _deep_merge(base: dict, update: dict) -> None:
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_config(config_path: str = "config.yaml") -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    abs_config_path = get_absolute_path(config_path)

    if not abs_config_path.exists():
        logger.info("Config file %s not found, using defaults", abs_config_path)
        return config

    try:
        with abs_config_path.open("r", encoding="utf-8") as config_file:
            yaml_config = yaml.safe_load(config_file)
        if yaml_config:
            _deep_merge(config, yaml_config)
    except Exception as exc:
        logger.warning("Could not load config from %s: %s", abs_config_path, exc)
    return config


def save_config(config: dict, config_path: str = "config.yaml") -> bool:
    abs_config_path = get_absolute_path(config_path)
    try:
        with abs_config_path.open("w", encoding="utf-8") as config_file:
            yaml.safe_dump(config, config_file, default_flow_style=False, sort_keys=False)
        return True
    except Exception as exc:
        logger.error("Error saving config to %s: %s", abs_config_path, exc)
        return False


_config_data = load_config()


def get_config_data() -> dict:
    return copy.deepcopy(_config_data)


def update_config_data(new_config: dict) -> None:
    global _config_data
    merged = copy.deepcopy(DEFAULT_CONFIG)
    _deep_merge(merged, _config_data)
    _deep_merge(merged, new_config)
    _config_data = merged
    save_config(_config_data)


@dataclass
class TelegripConfig:
    https_port: int = int(_config_data["network"]["https_port"])
    websocket_port: int = int(_config_data["network"]["websocket_port"])
    host_ip: str = str(_config_data["network"]["host_ip"])
    certfile: str = str(_config_data["ssl"]["certfile"])
    keyfile: str = str(_config_data["ssl"]["keyfile"])
    webapp_dir: str = "web-ui"

    @property
    def ssl_files_exist(self) -> bool:
        cert_path, key_path = self.get_absolute_ssl_paths()
        return Path(cert_path).exists() and Path(key_path).exists()

    def ensure_ssl_certificates(self) -> bool:
        from .utils import ensure_ssl_certificates

        return ensure_ssl_certificates(self.certfile, self.keyfile)

    def get_absolute_ssl_paths(self) -> tuple[str, str]:
        return str(get_absolute_path(self.certfile)), str(get_absolute_path(self.keyfile))

    def get_absolute_path(self, relative_path: str) -> Path:
        return get_absolute_path(relative_path)
