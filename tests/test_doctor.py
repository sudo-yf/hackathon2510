from waytoagi_gesture.config import AppConfig
from waytoagi_gesture.doctor import run_doctor


def test_doctor_without_camera_check(tmp_path):
    cfg = AppConfig(settings_db_path=str(tmp_path / "settings.db"))
    result = run_doctor(cfg, check_camera=False)
    assert result["failed"] == 0
    assert result["passed"] >= 2
