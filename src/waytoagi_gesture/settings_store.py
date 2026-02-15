from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

DEFAULT_SETTINGS = {
    "smoothing": 0.3,
    "power_factor": 2.0,
    "edge_boost": 1.5,
}


class SettingsStore:
    def __init__(self, db_path: str = "data/waytoagi.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL
                )
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                    (key, value),
                )

    def load(self) -> Dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        settings = {row[0]: float(row[1]) for row in rows}
        for key, value in DEFAULT_SETTINGS.items():
            settings.setdefault(key, value)
        return settings

    def save(self, **values: float):
        if not values:
            return
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, float(value)),
                )
