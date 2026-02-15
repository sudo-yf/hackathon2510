"""Backward-compatible entrypoint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from waytoagi_gesture.web import create_default_app, socketio

app, _config = create_default_app()


if __name__ == "__main__":
    print("🚀 WayToAGI 手势控制系统启动中...")
    print(f"📱 访问地址: http://localhost:{_config.port}")
    socketio.run(app, host=_config.host, port=_config.port, debug=False)
