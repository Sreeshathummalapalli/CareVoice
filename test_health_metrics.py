import sqlite3

import pytest

from db import carevoice_db


@pytest.fixture
def health_database(tmp_path, monkeypatch):
    database_path = tmp_path / "health.sqlite3"
    monkeypatch.setattr(carevoice_db, "DB_NAME", str(database_path))
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE health_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                value TEXT NOT NULL,
                unit TEXT NOT NULL,
                recorded_date TEXT NOT NULL,
                recorded_time TEXT,
                status TEXT,
                notes TEXT
            )
        """)
    return database_path


def test_save_health_vitals_persists_both_values_on_selected_date(health_database):
    saved = carevoice_db.save_health_vitals(
        7, "128/82", "Elevated", "106", "Normal", "Fasting", "2026-10-01"
    )

    readings = carevoice_db.get_health_metrics_for_date(7, "2026-10-01")

    assert saved is True
    assert readings["Blood Pressure"]["value"] == "128/82"
    assert readings["Blood Sugar"]["value"] == "106"
    assert readings["Blood Sugar"]["notes"] == "Fasting"
    assert carevoice_db.get_health_metrics_for_date(7, "2026-10-04") == {}


def test_save_health_vitals_rolls_back_pair_if_either_insert_fails(health_database):
    with sqlite3.connect(health_database) as connection:
        connection.execute("""
            CREATE TRIGGER reject_sugar BEFORE INSERT ON health_metrics
            WHEN NEW.metric_name = 'Blood Sugar'
            BEGIN
                SELECT RAISE(ABORT, 'test insert failure');
            END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="test insert failure"):
        carevoice_db.save_health_vitals(
            7, "128/82", "Elevated", "106", "Normal", "Fasting", "2026-10-01"
        )

    assert carevoice_db.get_health_metrics_for_date(7, "2026-10-01") == {}


def test_consecutive_voice_readings_are_appended_not_replaced(health_database):
    carevoice_db.add_health_metric(
        7, "Blood Pressure", "128/82", "mmHg", "2026-10-04",
        status="Normal", notes="Added via Voice Assistant",
    )
    carevoice_db.add_health_metric(
        7, "Blood Pressure", "135/88", "mmHg", "2026-10-04",
        status="Normal", notes="Added via Voice Assistant",
    )

    readings = carevoice_db.get_all_health_metrics(7)
    blood_pressure_readings = [
        reading for reading in readings
        if reading["metric_name"] == "Blood Pressure"
    ]

    assert [reading["value"] for reading in blood_pressure_readings] == ["135/88", "128/82"]
