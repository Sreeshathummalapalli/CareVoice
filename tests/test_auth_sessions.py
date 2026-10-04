import hashlib
import sqlite3

from db import carevoice_db as db


def _new_user(name, email):
    user, error = db.register_user(
        name,
        email,
        "secure-test-password",
        reset_answer="test-answer",
    )
    assert error is None
    return user


def test_database_auth_session_survives_a_new_session_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "carevoice.db"))
    db.init_db()
    user = _new_user("Account One", "one@example.test")

    token = db.create_auth_session(user["id"])
    restored_user = db.get_user_by_auth_session(token)

    assert restored_user["id"] == user["id"]
    assert restored_user["email"] == user["email"]
    with sqlite3.connect(db.DB_NAME) as connection:
        stored_hash, = connection.execute(
            "SELECT token_hash FROM auth_sessions WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
    assert stored_hash != token


def test_auth_session_rejects_expired_and_revoked_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "carevoice.db"))
    db.init_db()
    user = _new_user("Account Two", "two@example.test")
    token = db.create_auth_session(user["id"])
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with sqlite3.connect(db.DB_NAME) as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00' WHERE token_hash = ?",
            (token_hash,),
        )
    assert db.get_user_by_auth_session(token) is None

    active_token = db.create_auth_session(user["id"])
    db.revoke_auth_session(active_token)
    assert db.get_user_by_auth_session(active_token) is None


def test_health_medicines_prescriptions_reports_and_profiles_are_user_scoped(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "carevoice.db"))
    db.init_db()
    first = _new_user("First Account", "first@example.test")
    second = _new_user("Second Account", "second@example.test")

    db.add_medicine(first["id"], "First medicine", "10 mg", "08:00 AM", "Daily")
    db.add_health_metric(first["id"], "Blood Pressure", "120/80", "mmHg")
    db.add_prescription(first["id"], "first.pdf", "uploads/first.pdf", "text", [])
    db.add_report(first["id"], "First report", "2026-10-04", "Summary", "Doctor")

    assert [row["name"] for row in db.get_all_medicines(first["id"])] == ["First medicine"]
    assert db.get_all_medicines(second["id"]) == []
    assert [row["value"] for row in db.get_all_health_metrics(first["id"])] == ["120/80"]
    assert db.get_all_health_metrics(second["id"]) == []
    assert [row["filename"] for row in db.get_user_prescriptions(first["id"])] == ["first.pdf"]
    assert db.get_user_prescriptions(second["id"]) == []
    assert [row["title"] for row in db.get_all_reports(first["id"])] == ["First report"]
    assert db.get_all_reports(second["id"]) == []
    assert db.get_user_by_id(first["id"])["email"] == first["email"]
    assert db.get_user_by_id(second["id"])["email"] == second["email"]
