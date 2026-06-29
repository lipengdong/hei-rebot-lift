"""Run the minimal Telegrip VR bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .camera import ZmqObservationCameraHub, ZmqObservationCameraRuntimeConfig
from .config import TelegripConfig, get_config_data
from .inputs.vr_ws_server import VRWebSocketServer


def build_vr_image_runtime(config_data: dict):
    image_config = config_data.get("vr_images") or config_data.get("vr_image", {})
    if not bool(image_config.get("enabled", False)):
        return {}, []

    if "cameras" in image_config:
        camera_configs = image_config.get("cameras") or []
    else:
        camera_configs = [{**image_config, "id": "front"}]

    runtime_configs = []
    for slot in camera_configs:
        if not bool(slot.get("enabled", True)):
            continue
        camera_id = str(slot.get("id") or slot.get("image_key") or "front")
        endpoint = str(slot.get("endpoint", image_config.get("endpoint", "tcp://127.0.0.1:6556")))
        if endpoint.startswith("tcp://*:") or endpoint.startswith("tcp://0.0.0.0:"):
            raise ValueError(
                "vr_images endpoint is used with ZMQ connect, so it must be a robot IP or hostname, "
                "not '*' or 0.0.0.0."
            )
        runtime_configs.append(
            ZmqObservationCameraRuntimeConfig(
                id=camera_id,
                name=str(slot.get("name", camera_id)),
                endpoint=endpoint,
                image_key=str(slot.get("image_key", camera_id)),
                color_order=str(slot.get("color_order", image_config.get("color_order", "rgb"))),
                socket_type=str(slot.get("socket_type", image_config.get("socket_type", "pull"))),
                topic=str(slot.get("topic", image_config.get("topic", ""))),
                width=int(slot.get("width", image_config.get("width", 640))),
                height=int(slot.get("height", image_config.get("height", 480))),
                fps=int(slot.get("fps", image_config.get("fps", 30))),
                jpeg_quality=int(slot.get("jpeg_quality", image_config.get("jpeg_quality", 95))),
                enabled=True,
            )
        )

    grouped_configs: dict[tuple[str, str, str], list[ZmqObservationCameraRuntimeConfig]] = {}
    for runtime_config in runtime_configs:
        group_key = (runtime_config.endpoint, runtime_config.socket_type, runtime_config.topic)
        grouped_configs.setdefault(group_key, []).append(runtime_config)

    managers = {}
    hubs = []
    for configs in grouped_configs.values():
        hub = ZmqObservationCameraHub(configs)
        hubs.append(hub)
        for runtime_config in configs:
            managers[runtime_config.id] = hub.manager(runtime_config.id)

    return managers, hubs


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = TelegripConfig()
    if not config.ssl_files_exist and not config.ensure_ssl_certificates():
        raise RuntimeError("SSL certificates are required for WebXR over HTTPS")

    config_data = get_config_data()
    image_managers, image_hubs = build_vr_image_runtime(config_data)
    vr_server = None

    class RequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(config.get_absolute_path(config.webapp_dir)), **kwargs)

        def log_message(self, format, *args):
            pass

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.end_headers()

        def _send_json(self, payload: dict, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        def do_GET(self):
            parsed_path = urlparse(self.path)

            if parsed_path.path == "/api/config":
                self._send_json(get_config_data())
                return

            if parsed_path.path == "/api/status":
                self._send_json(
                    {
                        "status": "running",
                        "vrConnected": bool(vr_server and vr_server.is_running),
                        "vrImageEnabled": bool(image_managers),
                        "vrImageCameras": list(image_managers.keys()),
                    }
                )
                return

            if parsed_path.path == "/api/camera/status":
                if not image_managers:
                    self._send_json({"enabled": False, "stream_ready": False})
                    return
                camera_id = parse_qs(parsed_path.query).get("camera", ["front"])[0]
                manager = image_managers.get(camera_id) or next(iter(image_managers.values()))
                self._send_json(manager.get_status())
                return

            if parsed_path.path == "/api/camera/stream.mjpg":
                if not image_managers:
                    self._send_json({"error": "VR image display is disabled"}, status=404)
                    return
                camera_id = parse_qs(parsed_path.query).get("camera", ["front"])[0]
                manager = image_managers.get(camera_id)
                if manager is None:
                    self._send_json({"error": f"Unknown camera: {camera_id}"}, status=404)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                try:
                    for chunk in manager.stream_mjpeg():
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError):
                    logger.info("VR image stream client disconnected: %s", camera_id)
                return

            if parsed_path.path == "/api/camera/frame.jpg":
                if not image_managers:
                    self._send_json({"error": "VR image display is disabled"}, status=404)
                    return
                camera_id = parse_qs(parsed_path.query).get("camera", ["front"])[0]
                manager = image_managers.get(camera_id)
                if manager is None:
                    self._send_json({"error": f"Unknown camera: {camera_id}"}, status=404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(manager.get_jpeg_frame())
                return

            super().do_GET()

    cert_path, key_path = config.get_absolute_ssl_paths()
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)

    http_server = ThreadingHTTPServer((config.host_ip, config.https_port), RequestHandler)
    http_server.socket = ssl_context.wrap_socket(http_server.socket, server_side=True)
    vr_server = VRWebSocketServer(asyncio.Queue(), config)
    http_thread = threading.Thread(target=http_server.serve_forever, name="telegrip-http", daemon=True)
    http_thread.start()

    logger.info("HTTPS server running on https://%s:%s", config.host_ip, config.https_port)
    if not image_managers:
        logger.info("VR ZMQ image display is disabled")
    else:
        logger.info("VR ZMQ image display is enabled for: %s", ", ".join(image_managers.keys()))

    try:
        await vr_server.start()
        while vr_server.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Telegrip")
    finally:
        if vr_server is not None:
            await vr_server.stop()
        http_server.shutdown()
        http_server.server_close()
        for hub in image_hubs:
            hub.stop()


if __name__ == "__main__":
    asyncio.run(main())
