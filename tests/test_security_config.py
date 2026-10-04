import sqlite3
from db import carevoice_db as db


def test_database_initializes_without_creating_a_demo_account(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "carevoice.db"))

    db.init_db()

    with sqlite3.connect(db.DB_NAME) as connection:
        users = connection.execute("SELECT id, email FROM users").fetchall()

    assert users == []