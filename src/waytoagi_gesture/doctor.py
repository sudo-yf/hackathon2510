"""Runtime readiness checks for WayToAGI Gesture Control."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig


@dataclass
class Check:
    name: str
    status: str
    detail: str


def run_doctor(config: AppConfig, check_camera: bool = False) -> dict[str, Any]:
    checks: list[Check] = [
        _check_db_path(config),
        _check_runtime_range(config),
        _check_camera(check_camera, config.camera_index),
    ]
    return {
        "total": len(checks),
        "passed": sum(1 for c in checks if c.status == "pass"),
        "warned": sum(1 for c in checks if c.status == "warn"),
        "failed": sum(1 for c in checks if c.status == "fail"),
        "checks": [asdict(c) for c in checks],
    }


def _check_db_path(config: AppConfig) -> Check:
    db = Path(config.settings_db_path)
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute("SELECT 1")
        return Check("settings_db", "pass", f"ready: {db}")
    except Exception as exc:
        return Check("settings_db", "fail", f"{db}: {exc}")


def _check_runtime_range(config: AppConfig) -> Check:
    if config.frame_width <= 0 or config.frame_height <= 0 or config.frame_fps <= 0:
        return Check("video_config", "fail", "frame_width/frame_height/frame_fps must be > 0")
    return Check(
        "video_config",
        "pass",
        f"{config.frame_width}x{config.frame_height}@{config.frame_fps}",
    )


def _check_camera(check_camera: bool, camera_index: int) -> Check:
    if not check_camera:
        return Check("camera", "warn", "skipped")
    try:
        import cv2
    except ImportError:
        return Check("camera", "fail", "opencv-python is not installed")

    cap = cv2.VideoCapture(camera_index)
    try:
        if not cap.isOpened():
            return Check("camera", "fail", f"cannot open camera index {camera_index}")
        return Check("camera", "pass", f"camera index {camera_index} is available")
    finally:
        cap.release()

