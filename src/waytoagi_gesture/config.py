import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    secret_key: str = "gesture_control_v2_0"
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    frame_fps: int = 30
    cors_origin: str = "*"
    disable_mouse: bool = False
    settings_db_path: str = "data/waytoagi.db"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            secret_key=os.getenv("SECRET_KEY", "gesture_control_v2_0"),
            camera_index=int(os.getenv("CAMERA_INDEX", "0")),
            frame_width=int(os.getenv("FRAME_WIDTH", "1280")),
            frame_height=int(os.getenv("FRAME_HEIGHT", "720")),
            frame_fps=int(os.getenv("FRAME_FPS", "30")),
            cors_origin=os.getenv("CORS_ORIGIN", "*"),
            disable_mouse=os.getenv("DISABLE_MOUSE", "0") in {"1", "true", "True"},
            settings_db_path=os.getenv("SETTINGS_DB_PATH", "data/waytoagi.db"),
        )
