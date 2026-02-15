"""CLI entrypoint for WayToAGI Gesture Control."""

from __future__ import annotations

import argparse

from .config import AppConfig
from .doctor import run_doctor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WayToAGI Gesture Control CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="启动 Web 服务")

    doctor = subparsers.add_parser("doctor", help="运行环境自检")
    doctor.add_argument("--check-camera", action="store_true", help="检查摄像头可用性")
    return parser


def _print_doctor(result: dict) -> None:
    print("\nWayToAGI Doctor")
    print("=" * 56)
    for item in result["checks"]:
        print(f"[{item['status'].upper():4s}] {item['name']:14s} {item['detail']}")
    print("-" * 56)
    print(f"Summary: pass={result['passed']} warn={result['warned']} fail={result['failed']}")


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"
    config = AppConfig.from_env()

    if command == "run":
        from .web import create_app, socketio

        app = create_app(config)
        print("🚀 WayToAGI 手势控制系统启动中...")
        print(f"📱 访问地址: http://localhost:{config.port}")
        socketio.run(app, host=config.host, port=config.port, debug=False)
        return 0

    if command == "doctor":
        result = run_doctor(config, check_camera=bool(args.check_camera))
        _print_doctor(result)
        return 1 if result["failed"] > 0 else 0

    return 1
