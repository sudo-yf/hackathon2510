from waytoagi_gesture.config import AppConfig


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    cfg = AppConfig.from_env()
    assert cfg.port == 5000
    assert cfg.host == "0.0.0.0"


def test_config_override(monkeypatch):
    monkeypatch.setenv("PORT", "7001")
    monkeypatch.setenv("DISABLE_MOUSE", "1")
    cfg = AppConfig.from_env()
    assert cfg.port == 7001
    assert cfg.disable_mouse is True
