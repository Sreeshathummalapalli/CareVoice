import datetime
import json

from backend import reminder_worker
from db import carevoice_db as db


def test_parse_multiple_saved_schedule_times():
    assert reminder_worker.parse_schedule_times("08:00 AM, 09:00 PM") == [
        (480, "08:00 AM"),
        (1260, "09:00 PM"),
    ]


def test_medicine_schedule_display_does_not_repeat_times():
    assert reminder_worker.format_medicine_schedule(
        "12:39 PM", "Daily", "12:39 PM: After Food"
    ) == "12:39 PM · Daily · After Food"
    assert reminder_worker.format_medicine_schedule(
        "08:00 AM, 09:00 PM",
        "Twice Daily",
        "08:00 AM: Before Food; 09:00 PM: After Food",
    ) == "08:00 AM (Before Food), 09:00 PM (After Food) · Twice Daily"


def test_due_schedule_uses_real_saved_medicine_and_notifies_once(monkeypatch):
    now = datetime.datetime(2026, 10, 2, 8, 1)
    monkeypatch.setattr(reminder_worker.db, "get_active_reminder_schedules", lambda: [{
        "user_id": 4,
        "user_name": "Sreesha",
        "language": "en-IN",
        "medicine_id": 17,
        "medicine_name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM",
    }])
    monkeypatch.setattr(reminder_worker.db, "get_medicine_logs_for_date", lambda user_id, date: [])
    monkeypatch.setattr(reminder_worker.db, "reminder_was_delivered", lambda *args: False)
    monkeypatch.setattr(reminder_worker.db, "get_push_subscriptions", lambda user_id: [{
        "endpoint": "https://push.example/sub",
        "keys": {"p256dh": "x", "auth": "y"},
    }])
    monkeypatch.setattr(reminder_worker, "_private_key_path", lambda: "test-key.pem")
    sent = []
    monkeypatch.setattr(reminder_worker, "webpush", lambda **kwargs: sent.append(kwargs))
    recorded = []
    monkeypatch.setattr(reminder_worker.db, "record_reminder_delivery", lambda *args: recorded.append(args))

    assert reminder_worker.send_due_reminders(now) == 1
    assert len(sent) == 1
    assert "Sreesha" in sent[0]["data"]
    assert "Paracetamol" in sent[0]["data"]
    assert "08:00 AM" in sent[0]["data"]
    assert recorded[0][-1] == "scheduled:2026-10-02:08:00 AM"


def test_reminder_message_separates_strength_and_tablet_count():
    message = reminder_worker.format_reminder_message(
        "Sreesha", "Paracetamol", "500 mg, 1 tablet", "08:00 AM", "en-IN"
    )

    assert message == (
        "Sreesha, it is time to take your Paracetamol 500 mg. "
        "Please take 1 tablet. Scheduled for 08:00 AM."
    )


def test_reminder_message_uses_saved_instructions_for_tablet_count():
    message = reminder_worker.format_reminder_message(
        "Sreesha", "Paracetamol", "500 mg", "08:00 AM", instructions="Take 1 tablet after breakfast"
    )

    assert "Please take 1 tablet." in message


def test_reminder_message_uses_food_timing_for_matching_dose_in_english_and_telugu():
    timings = "08:00 AM: Before Food; 09:00 PM: After Food"

    english_message = reminder_worker.format_reminder_message(
        "Sreesha", "Medicine", "500 mg, 1 tablet", "08:00 AM",
        "en-IN", before_after_food=timings,
    )
    telugu_message = reminder_worker.format_reminder_message(
        "Sreesha", "Medicine", "500 mg, 1 tablet", "09:00 PM",
        "te-IN", before_after_food=timings,
    )

    assert "Take before food." in english_message
    assert "భోజనం తర్వాత తీసుకోండి." in telugu_message
    assert "అల్పాహారం తర్వాత" not in telugu_message


def test_telugu_reminder_uses_localized_medicine_name():
    message = reminder_worker.format_reminder_message(
        "Sreesha", "Metformin", "500 mg, 1 tablet", "08:00 AM", "te-IN"
    )

    assert "మెట్‌ఫార్మిన్" in message
    assert "Metformin" not in message


def test_in_app_reminders_are_localized_and_skip_completed_doses():
    schedules = [{
        "user_id": 4,
        "medicine_id": 17,
        "medicine_name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM, 09:00 PM",
        "instructions": "",
    }]
    logs = [{
        "id": 5,
        "medicine_id": 17,
        "scheduled_time": "08:00 AM",
        "status": "Taken",
    }]

    reminders = reminder_worker.build_in_app_reminders(
        schedules, logs, 4, "Sreesha", "te-IN", "2026-10-04"
    )

    assert len(reminders) == 1
    assert reminders[0]["scheduled_time"] == "09:00 PM"
    assert reminders[0]["lang"] == "te-IN"
    assert "తీసుకునే సమయం అయింది" in reminders[0]["body"]
    assert reminders[0]["delivery_key"] == "scheduled:2026-10-04:09:00 PM"


def test_in_app_snooze_reminder_is_scheduled_for_snooze_time():
    schedules = [{
        "user_id": 4,
        "medicine_id": 17,
        "medicine_name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM",
    }]
    logs = [{
        "id": 12,
        "medicine_id": 17,
        "scheduled_time": "08:00 AM",
        "status": "Snoozed",
        "snooze_until": "2026-10-04T08:06:00",
    }]

    reminders = reminder_worker.build_in_app_reminders(
        schedules, logs, 4, "Sreesha", "en-IN", "2026-10-04"
    )

    assert len(reminders) == 1
    assert reminders[0]["minute_of_day"] == 8 * 60 + 6
    assert reminders[0]["reminder_date"] == "2026-10-04"
    assert reminders[0]["delivery_key"] == "snooze:12"


def test_due_in_app_reminders_appear_near_scheduled_time_only():
    schedules = [{
        "user_id": 4,
        "medicine_id": 17,
        "medicine_name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM",
    }]

    due = reminder_worker.get_due_in_app_reminders(
        schedules, [], 4, "Sreesha", "en-IN",
        datetime.datetime(2026, 10, 4, 8, 1),
    )
    not_due = reminder_worker.get_due_in_app_reminders(
        schedules, [], 4, "Sreesha", "en-IN",
        datetime.datetime(2026, 10, 4, 7, 59),
    )

    assert len(due) == 1
    assert due[0]["scheduled_time"] == "08:00 AM"
    assert not_due == []


def test_signed_snooze_action_updates_saved_medicine_log(monkeypatch, tmp_path):
    now = datetime.datetime(2026, 10, 2, 8, 1)
    secret_file = tmp_path / "action-secret"
    secret_file.write_bytes(b"test-action-secret-32-bytes-long")
    monkeypatch.setattr(reminder_worker, "_action_secret_path", lambda: secret_file)
    medicine = {
        "id": 17,
        "name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM",
    }
    monkeypatch.setattr(reminder_worker.db, "get_medicine_by_id", lambda user_id, medicine_id: medicine)
    logged = []
    monkeypatch.setattr(reminder_worker.db, "log_medicine_action", lambda *args, **kwargs: logged.append((args, kwargs)))
    monkeypatch.setattr(
        reminder_worker.db,
        "get_medicine_logs_for_date",
        lambda user_id, date: [
            {
                "id": index + 1,
                "medicine_id": args[0][1],
                "status": args[0][4],
                "scheduled_time": args[0][5],
                "snooze_until": args[1].get("snooze_until"),
            }
            for index, args in enumerate(logged)
        ],
    )
    event = {
        "user_id": 4,
        "medicine_id": 17,
        "scheduled_time": "08:00 AM",
        "delivery_key": "scheduled:2026-10-02:08:00 AM",
    }
    token = reminder_worker.create_reminder_action_token(event, now)

    ok, status = reminder_worker.perform_reminder_action(token, "snooze", now)

    assert (ok, status) == (True, "Snoozed")
    assert logged[0][0][1:5] == (17, "Paracetamol", "500 mg, 1 tablet", "Snoozed")
    assert logged[0][1]["snooze_until"] == "2026-10-02T08:06:00"
    assert reminder_worker.perform_reminder_action(token, "take", now)[0] is False
    assert reminder_worker.perform_reminder_action(token + "x", "take", now)[0] is False


def test_database_schedule_push_and_action_round_trip(monkeypatch, tmp_path):
    original_database = db.DB_NAME
    db.DB_NAME = str(tmp_path / "reminders.db")
    db.init_db()
    user, error = db.register_user("Sreesha", "sreesha@example.test", "test-password")
    assert error is None
    medicine_id = db.add_medicine(
        user["id"],
        "Paracetamol",
        "500 mg, 1 tablet",
        "08:00 AM",
        "Take 1 tablet",
        frequency="Daily",
    )
    db.save_push_subscription(user["id"], {
        "endpoint": "https://push.example.test/sreesha",
        "keys": {"p256dh": "test-key", "auth": "test-auth"},
    })
    action_secret = tmp_path / "action-secret"
    action_secret.write_bytes(b"integration-test-action-secret")
    monkeypatch.setattr(reminder_worker, "_action_secret_path", lambda: action_secret)
    monkeypatch.setattr(reminder_worker, "_private_key_path", lambda: tmp_path / "vapid.pem")
    pushed = []
    monkeypatch.setattr(reminder_worker, "webpush", lambda **kwargs: pushed.append(kwargs))
    now = datetime.datetime(2026, 10, 2, 8, 1)

    try:
        assert reminder_worker.send_due_reminders(now) == 1
        payload = json.loads(pushed[0]["data"])
        assert "Sreesha" in payload["body"]
        assert "Paracetamol 500 mg" in payload["body"]
        assert "1 tablet" in payload["body"]

        ok, status = reminder_worker.perform_reminder_action(
            payload["action_token"], "snooze", now
        )
        assert (ok, status) == (True, "Snoozed")
        logs = db.get_medicine_logs_for_date(user["id"], "2026-10-02")
        dose_log = next(log for log in logs if log["medicine_id"] == medicine_id)
        assert dose_log["snooze_until"] == "2026-10-02T08:06:00"
        assert reminder_worker.send_due_reminders(now + datetime.timedelta(minutes=5)) == 1
        assert len(pushed) == 2
        snooze_payload = json.loads(pushed[1]["data"])
        assert snooze_payload["delivery_key"] == f"snooze:{dose_log['id']}"
    finally:
        db.DB_NAME = original_database


def test_update_medicine_updates_details_schedule_and_reminder(monkeypatch, tmp_path):
    original_database = db.DB_NAME
    db.DB_NAME = str(tmp_path / "medicine-edit.db")
    db.init_db()
    user, error = db.register_user("Sreesha", "medicine-edit@example.test", "test-password")
    assert error is None
    medicine_id = db.add_medicine(
        user["id"], "Paracetamol", "500 mg, 1 tablet", "08:00 AM",
        "Take after breakfast", frequency="Daily", before_after_food="After Food",
    )

    try:
        assert db.update_medicine(
            user["id"], medicine_id, "Paracetamol Plus", "650 mg, 1 tablet",
            "09:00 AM, 09:00 PM", "Take with water", "Twice Daily",
            "09:00 AM: After Food; 09:00 PM: Before Food", "data:image/png;base64,updated",
        )
        medicine = db.get_medicine_by_id(user["id"], medicine_id)
        schedule = next(
            item for item in db.get_active_reminder_schedules()
            if item["medicine_id"] == medicine_id
        )

        assert medicine["dosage"] == "650 mg, 1 tablet"
        assert medicine["time_slot"] == "09:00 AM, 09:00 PM"
        assert medicine["before_after_food"] == "09:00 AM: After Food; 09:00 PM: Before Food"
        assert medicine["image_url"] == "data:image/png;base64,updated"
        assert schedule["dosage"] == "650 mg, 1 tablet"
        assert schedule["time_slot"] == "09:00 AM, 09:00 PM"
        assert not db.update_medicine(
            user["id"] + 1, medicine_id, "Other", "1 mg", "10:00 AM", "", "Daily", "After Food"
        )
    finally:
        db.DB_NAME = original_database


def test_voice_health_save_updates_newest_bp_and_matching_sugar_category(tmp_path):
    original_database = db.DB_NAME
    db.DB_NAME = str(tmp_path / "voice-health.db")
    db.init_db()
    user, error = db.register_user("Sreesha", "voice-health@example.test", "test-password")
    assert error is None
    today = "2026-10-04"

    try:
        db.add_health_metric(user["id"], "Blood Pressure", "118/80", "mmHg", recorded_date=today, notes="Added via Voice Assistant")
        db.save_or_update_voice_health_metric(user["id"], "Blood Pressure", "124/82", "mmHg", recorded_date=today, notes="Added via Voice Assistant")
        db.add_health_metric(user["id"], "Blood Sugar", "120", "mg/dL", recorded_date=today, notes="Added via Voice Assistant")
        db.save_or_update_voice_health_metric(user["id"], "Blood Sugar", "130", "mg/dL", recorded_date=today, notes="After Food")
        db.save_or_update_voice_health_metric(user["id"], "Blood Sugar", "135", "mg/dL", recorded_date=today, notes="After Food")
        db.save_or_update_voice_health_metric(user["id"], "Blood Sugar", "105", "mg/dL", recorded_date=today, notes="Before Food")

        today_rows = [row for row in db.get_all_health_metrics(user["id"]) if row["recorded_date"] == today]
        bp_rows = [row for row in today_rows if row["metric_name"] == "Blood Pressure"]
        sugar_rows = [row for row in today_rows if row["metric_name"] == "Blood Sugar"]

        assert [(row["value"], row["notes"]) for row in bp_rows] == [("124/82", "Added via Voice Assistant")]
        assert {(row["value"], row["notes"]) for row in sugar_rows} == {
            ("135", "After Food"),
            ("105", "Before Food"),
        }
    finally:
        db.DB_NAME = original_database