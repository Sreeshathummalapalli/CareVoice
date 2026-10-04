import secrets

from db import carevoice_db as db


def test_demo_seed_credentials_come_from_environment(monkeypatch, tmp_path):
    original_database = db.DB_NAME
    password = secrets.token_urlsafe(32)
    security_answer = secrets.token_urlsafe(32)
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "seed.db"))
    monkeypatch.setenv("CAREVOICE_DEMO_PASSWORD", password)
    monkeypatch.setenv("CAREVOICE_DEMO_SECURITY_ANSWER", security_answer)

    db.init_db()
    user, error = db.authenticate_user("demo@carevoice.health", password)

    assert error is None
    assert user is not None
    assert db.verify_password(
        security_answer.strip().lower(), user["reset_answer_hash"]
    )
    db.DB_NAME = original_database