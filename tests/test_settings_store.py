from waytoagi_gesture.settings_store import SettingsStore


def test_settings_store_roundtrip(tmp_path):
    db = tmp_path / "settings.db"
    store = SettingsStore(str(db))

    before = store.load()
    assert "smoothing" in before

    store.save(smoothing=0.6, power_factor=2.3)
    after = store.load()
    assert after["smoothing"] == 0.6
    assert after["power_factor"] == 2.3
