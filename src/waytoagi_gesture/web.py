import logging
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from .config import AppConfig
from .service import GestureControlService
from .settings_store import SettingsStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def create_app(config: AppConfig, service: GestureControlService | None = None):
    root = Path(__file__).resolve().parent
    static_dir = root / "static"

    app = Flask(__name__, static_folder=str(static_dir), static_url_path="")
    app.config["SECRET_KEY"] = config.secret_key
    CORS(app, resources={r"/*": {"origins": config.cors_origin}})
    socketio.init_app(app, cors_allowed_origins=config.cors_origin)

    service = service or GestureControlService(config)
    settings_store = SettingsStore(config.settings_db_path)
    service.apply_settings(**settings_store.load())

    def on_frame(payload):
        socketio.emit("video_frame", payload)

    service.on_frame = on_frame

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "running": service.running})

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.post("/api/camera/start")
    def start_camera():
        return jsonify(service.start())

    @app.post("/api/camera/stop")
    def stop_camera():
        return jsonify(service.stop())

    @app.post("/api/mouse/toggle")
    def toggle_mouse():
        with service.state_lock:
            if not service.running:
                return jsonify({"success": False, "enabled": False, "message": "请先启动摄像头"}), 400
            service.mouse_enabled = not service.mouse_enabled
            enabled = service.mouse_enabled
        return jsonify({"success": True, "enabled": enabled, "message": f"鼠标控制已{'启用' if enabled else '禁用'}"})

    @app.post("/api/settings/flip")
    def toggle_flip():
        with service.state_lock:
            service.flip_horizontal = not service.flip_horizontal
            flipped = service.flip_horizontal
        return jsonify({"success": True, "flipped": flipped})

    @app.post("/api/settings")
    def update_settings():
        data = request.get_json(silent=True) or {}
        try:
            update_payload = {
                "smoothing": data["smoothing"] if "smoothing" in data else None,
                "power_factor": data["power_factor"] if "power_factor" in data else None,
                "edge_boost": data["edge_boost"] if "edge_boost" in data else None,
            }
            service.apply_settings(**update_payload)
            persisted = {k: v for k, v in update_payload.items() if v is not None}
            settings_store.save(**persisted)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "参数格式错误"}), 400
        return jsonify({"success": True, "settings": service.get_runtime_settings()})

    @app.get("/api/settings")
    def get_settings():
        return jsonify({"success": True, "settings": service.get_runtime_settings()})

    @socketio.on("connect")
    def handle_connect():
        emit("status", {"message": "已连接到服务器"})

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info("客户端断开连接")

    app.gesture_service = service
    app.gesture_config = config
    return app


def create_default_app():
    config = AppConfig.from_env()
    app = create_app(config)
    return app, config


def run():
    app, config = create_default_app()
    print("🚀 WayToAGI 手势控制系统启动中...")
    print(f"📱 访问地址: http://localhost:{config.port}")
    socketio.run(app, host=config.host, port=config.port, debug=False)
