import hashlib
import sqlite3

from db import carevoice_db as db


def test_password_hash_is_salted_and_verifiable():
    first_hash = db.hash_password("correct horse battery staple")
    second_hash = db.hash_password("correct horse battery staple")

    assert first_hash.startswith("pbkdf2_sha256$600000$")
    assert first_hash != second_hash
    assert db.verify_password("correct horse battery staple", first_hash)
    assert not db.verify_password("wrong password", first_hash)


def test_legacy_password_is_upgraded_after_successful_login(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "auth" / "carevoice.db"))
    db.init_db()
    user, error = db.register_user(
        "CareVoice User",
        "user@example.com",
        "old-password",
        reset_answer="blue",
    )
    assert error is None

    legacy_hash = hashlib.sha256(
        ("old-passwordcarevoice_secure_salt_2026").encode("utf-8")
    ).hexdigest()
    with sqlite3.connect(db.DB_NAME) as connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (legacy_hash, user["id"]),
        )

    authenticated_user, error = db.authenticate_user(
        "user@example.com", "old-password"
    )

    assert error is None
    assert authenticated_user is not None
    with sqlite3.connect(db.DB_NAME) as connection:
        upgraded_hash = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()[0]
    assert db.is_current_password_hash(upgraded_hash)
    assert db.verify_password("old-password", upgraded_hash)


def test_legacy_security_answer_is_upgraded_during_password_reset(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "reset" / "carevoice.db"))
    db.init_db()
    user, error = db.register_user(
        "CareVoice User",
        "reset@example.com",
        "old-password",
        reset_answer="blue",
    )
    assert error is None
    legacy_answer_hash = hashlib.sha256(
        ("bluecarevoice_secure_salt_2026").encode("utf-8")
    ).hexdigest()
    with sqlite3.connect(db.DB_NAME) as connection:
        connection.execute(
            "UPDATE users SET reset_answer_hash = ? WHERE id = ?",
            (legacy_answer_hash, user["id"]),
        )

    success, _ = db.reset_password(
        "reset@example.com", "blue", "new-password"
    )

    assert success
    with sqlite3.connect(db.DB_NAME) as connection:
        password_hash, answer_hash = connection.execute(
            "SELECT password_hash, reset_answer_hash FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    assert db.verify_password("new-password", password_hash)
    assert db.verify_password("blue", answer_hash)
    assert db.is_current_password_hash(answer_hash)
