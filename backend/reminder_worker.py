import base64
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from db import carevoice_db as db
from backend.storage import DATA_DIR
from backend.telugu_localization import display_medicine_name


_TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", re.IGNORECASE)
_worker_thread = None
_worker_lock = threading.Lock()
_action_server = None
_action_server_thread = None


def parse_schedule_times(schedule_text):
    times = []
    for hour_text, minute_text, period in _TIME_PATTERN.findall(str(schedule_text)):
        hour = int(hour_text) % 12
        if period.upper() == "PM":
            hour += 12
        minute = int(minute_text)
        if minute < 60:
            result = (hour * 60 + minute, f"{(hour % 12) or 12:02d}:{minute:02d} {'PM' if hour >= 12 else 'AM'}")
            if result not in times:
                times.append(result)
    return times


def format_medicine_schedule(time_slot, frequency, before_after_food):
    times = [display_time for _, display_time in parse_schedule_times(time_slot)]
    food_pairs = re.findall(
        r"(\d{1,2}:\d{2}\s*(?:AM|PM))\s*:\s*([^;]+)",
        str(before_after_food or ""),
        re.IGNORECASE,
    )
    food_by_time = {time_value.upper(): timing.strip() for time_value, timing in food_pairs}
    if times and all(time_value.upper() in food_by_time for time_value in times):
        timings = [food_by_time[time_value.upper()] for time_value in times]
        if len(set(timing.casefold() for timing in timings)) == 1:
            return " · ".join(part for part in [", ".join(times), str(frequency or "").strip(), timings[0]] if part)
        dose_schedule = ", ".join(
            f"{time_value} ({food_by_time[time_value.upper()]})"
            for time_value in times
        )
        return " · ".join(part for part in [dose_schedule, str(frequency or "").strip()] if part)

    return " · ".join(
        part for part in [str(time_slot or "").strip(), str(frequency or "").strip(), str(before_after_food or "").strip()]
        if part
    )


def format_reminder_message(user_name, medicine_name, dosage, scheduled_time, lang_code="en-IN", instructions="", before_after_food=""):
    parts = [part.strip() for part in str(dosage).split(",") if part.strip()]
    strength = parts[0] if parts else str(dosage)
    quantity = next(
        (part for part in parts[1:] if re.search(r"\b(tablet|capsule|drop|dose)s?\b", part, re.IGNORECASE)),
        None,
    )
    if not quantity:
        quantity_match = re.search(
            r"\b\d+(?:\.\d+)?\s*(?:tablets?|capsules?|drops?)\b",
            str(instructions),
            re.IGNORECASE,
        )
        quantity = quantity_match.group(0) if quantity_match else None
    timing = ""
    for entry in str(before_after_food or "").split(";"):
        match = re.match(r"\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*:\s*(.+?)\s*$", entry, re.IGNORECASE)
        if match and match.group(1).upper() == scheduled_time.upper():
            timing = match.group(2)
            break
    if not timing and ":" not in str(before_after_food or ""):
        timing = str(before_after_food or "").strip()
    is_telugu = str(lang_code).lower().startswith("te")
    telugu_timing = {
        "before food": "భోజనానికి ముందు తీసుకోండి.",
        "after food": "భోజనం తర్వాత తీసుకోండి.",
        "with food": "భోజనంతో పాటు తీసుకోండి.",
        "empty stomach": "ఖాళీ కడుపుతో తీసుకోండి.",
        "before breakfast": "అల్పాహారానికి ముందు తీసుకోండి.",
        "after breakfast": "అల్పాహారం తర్వాత తీసుకోండి.",
        "before lunch": "మధ్యాహ్న భోజనానికి ముందు తీసుకోండి.",
        "after lunch": "మధ్యాహ్న భోజనం తర్వాత తీసుకోండి.",
        "before dinner": "రాత్రి భోజనానికి ముందు తీసుకోండి.",
        "after dinner": "రాత్రి భోజనం తర్వాత తీసుకోండి.",
        "before bed": "పడుకునే ముందు తీసుకోండి.",
    }.get(timing.lower(), "")
    if is_telugu:
        display_name = display_medicine_name(medicine_name, True)
        dose_text = f"దయచేసి {quantity} తీసుకోండి." if quantity else f"దయచేసి మీ సూచించిన {strength} మోతాదు తీసుకోండి."
        return f"{user_name}, {display_name} {strength} తీసుకునే సమయం అయింది. {dose_text} {telugu_timing} షెడ్యూల్ సమయం {scheduled_time}."
    dose_text = f"Please take {quantity}." if quantity else f"Please take your prescribed {strength} dose."
    food_text = f" Take {timing.lower()}." if timing else ""
    return f"{user_name}, it is time to take your {medicine_name} {strength}. {dose_text}{food_text} Scheduled for {scheduled_time}."


def build_in_app_reminders(schedules, medicine_logs, user_id, user_name, lang_code="en-IN", today=None):
    today = today or datetime.datetime.now().strftime("%Y-%m-%d")
    latest_actions = {}
    for log in sorted(medicine_logs, key=lambda item: int(item.get("id") or 0)):
        key = (log.get("medicine_id"), str(log.get("scheduled_time") or "").strip().upper())
        latest_actions[key] = log

    reminders = []
    for schedule in schedules:
        if int(schedule.get("user_id", -1)) != int(user_id):
            continue
        for minute_of_day, scheduled_time in parse_schedule_times(schedule.get("time_slot", "")):
            action = latest_actions.get((schedule["medicine_id"], scheduled_time.upper()))
            if action and action.get("status") in {"Taken", "Skipped"}:
                continue
            reminder_date = today
            delivery_key = f"scheduled:{today}:{scheduled_time}"
            if action and action.get("status") == "Snoozed":
                try:
                    snooze_at = datetime.datetime.fromisoformat(action["snooze_until"])
                except (KeyError, TypeError, ValueError):
                    continue
                reminder_date = snooze_at.strftime("%Y-%m-%d")
                minute_of_day = snooze_at.hour * 60 + snooze_at.minute
                delivery_key = f"snooze:{action['id']}"
            reminders.append({
                "minute_of_day": minute_of_day,
                "reminder_date": reminder_date,
                "scheduled_time": scheduled_time,
                "delivery_key": delivery_key,
                "body": format_reminder_message(
                    user_name,
                    schedule["medicine_name"],
                    schedule["dosage"],
                    scheduled_time,
                    lang_code,
                    schedule.get("instructions", ""),
                    schedule.get("before_after_food", ""),
                ),
                "lang": lang_code,
                "user_id": int(user_id),
                "medicine_id": schedule["medicine_id"],
            })
    return reminders


def get_due_in_app_reminders(schedules, medicine_logs, user_id, user_name, lang_code="en-IN", now=None):
    now = now or datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_minute = now.hour * 60 + now.minute
    return [
        reminder for reminder in build_in_app_reminders(
            schedules, medicine_logs, user_id, user_name, lang_code, today
        )
        if 0 <= current_minute - reminder["minute_of_day"] <= 2
    ]


def _private_key_path():
    configured_path = os.getenv("CAREVOICE_VAPID_PRIVATE_KEY_FILE")
    if configured_path:
        return Path(configured_path)
    data_directory = DATA_DIR
    data_directory.mkdir(parents=True, exist_ok=True)
    key_path = data_directory / "vapid_private.pem"
    if not key_path.exists():
        private_key = ec.generate_private_key(ec.SECP256R1())
        key_path.write_bytes(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    return key_path


def get_vapid_public_key():
    private_key = serialization.load_pem_private_key(_private_key_path().read_bytes(), password=None)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(public_bytes).decode("ascii").rstrip("=")


def _action_secret_path():
    configured_path = os.getenv("CAREVOICE_ACTION_SECRET_FILE")
    if configured_path:
        return Path(configured_path)
    data_directory = DATA_DIR
    data_directory.mkdir(parents=True, exist_ok=True)
    secret_path = data_directory / "reminder_action_secret"
    if not secret_path.exists():
        secret_path.write_bytes(secrets.token_bytes(32))
    return secret_path


def create_reminder_action_token(event, now=None):
    now = now or datetime.datetime.now()
    payload = {
        "user_id": event["user_id"],
        "medicine_id": event["medicine_id"],
        "scheduled_time": event["scheduled_time"],
        "delivery_key": event["delivery_key"],
        "date": now.strftime("%Y-%m-%d"),
        "expires_at": int((now + datetime.timedelta(days=1)).timestamp()),
    }
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(
        _action_secret_path().read_bytes(), encoded_payload.encode(), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{encoded_payload}.{encoded_signature}"


def _decode_action_token(token, now=None):
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = hmac.new(
            _action_secret_path().read_bytes(), encoded_payload.encode(), hashlib.sha256
        ).digest()
        provided = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, provided):
            return None
        payload_bytes = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        payload = json.loads(payload_bytes)
        now = now or datetime.datetime.now()
        if int(payload["expires_at"]) < int(now.timestamp()):
            return None
        if payload["date"] != now.strftime("%Y-%m-%d"):
            return None
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def perform_reminder_action(token, action, now=None):
    now = now or datetime.datetime.now()
    payload = _decode_action_token(token, now)
    if not payload or action not in {"take", "snooze", "skip"}:
        return False, "This reminder action is invalid or expired."

    user_id = int(payload["user_id"])
    medicine_id = int(payload["medicine_id"])
    medicine = db.get_medicine_by_id(user_id, medicine_id)
    scheduled_time = str(payload["scheduled_time"])
    if not medicine or scheduled_time not in {
        display_time for _, display_time in parse_schedule_times(medicine.get("time_slot", ""))
    }:
        return False, "The medicine schedule no longer matches this reminder."

    dose_logs = [
        log for log in db.get_medicine_logs_for_date(user_id, payload["date"])
        if log.get("medicine_id") == medicine_id
        and str(log.get("scheduled_time") or "").strip().upper() == scheduled_time.upper()
    ]
    latest_action = dose_logs[-1] if dose_logs else None
    if latest_action and latest_action.get("status") in {"Taken", "Skipped"}:
        return False, "This medicine dose has already been recorded."
    expected_delivery = (
        f"snooze:{latest_action['id']}"
        if latest_action and latest_action.get("status") == "Snoozed"
        else f"scheduled:{payload['date']}:{scheduled_time}"
    )
    if payload.get("delivery_key") != expected_delivery:
        return False, "This reminder has already been handled or replaced."

    status = {"take": "Taken", "snooze": "Snoozed", "skip": "Skipped"}[action]
    snooze_until = (now + datetime.timedelta(minutes=5)).isoformat(timespec="seconds") if action == "snooze" else None
    db.log_medicine_action(
        user_id,
        medicine_id,
        medicine["name"],
        medicine["dosage"],
        status,
        scheduled_time,
        now.strftime("%I:%M %p"),
        payload["date"],
        snooze_until=snooze_until,
    )
    return True, status


class _ReminderActionHandler(BaseHTTPRequestHandler):
    @staticmethod
    def _allowed_origins():
        configured_origins = os.getenv("CAREVOICE_ALLOWED_WEB_ORIGINS")
        if configured_origins:
            return {value.strip() for value in configured_origins.split(",") if value.strip()}
        external_url = os.getenv("RENDER_EXTERNAL_URL")
        if external_url:
            return {external_url.rstrip("/")}
        return {"http://localhost:8501", "http://127.0.0.1:8501"}

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode()
        origin = self.headers.get("Origin", "")
        allowed_origins = self._allowed_origins()
        self.send_response(status_code)
        if origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        allowed_origins = self._allowed_origins()
        self.send_response(204)
        if origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/action":
            self._send_json(404, {"ok": False, "message": "Not found"})
            return
        try:
            content_length = min(int(self.headers.get("Content-Length", "0")), 4096)
            request = json.loads(self.rfile.read(content_length))
            ok, message = perform_reminder_action(request.get("token", ""), request.get("action", ""))
            self._send_json(200 if ok else 400, {"ok": ok, "message": message})
        except (TypeError, ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "message": "Invalid request"})

    def log_message(self, format_string, *args):
        return


def _start_action_server():
    global _action_server, _action_server_thread
    if _action_server_thread and _action_server_thread.is_alive():
        return
    bind_host = os.getenv("CAREVOICE_ACTION_BIND", "127.0.0.1")
    port = int(os.getenv("CAREVOICE_ACTION_PORT", "8765"))
    _action_server = ThreadingHTTPServer((bind_host, port), _ReminderActionHandler)
    _action_server.daemon_threads = True
    _action_server_thread = threading.Thread(
        target=_action_server.serve_forever,
        name="carevoice-reminder-action-api",
        daemon=True,
    )
    _action_server_thread.start()


def _collect_due_events(now=None):
    now = now or datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    due_events = []
    logs_by_user = {}

    for schedule in db.get_active_reminder_schedules():
        user_id = schedule["user_id"]
        if user_id not in logs_by_user:
            logs_by_user[user_id] = db.get_medicine_logs_for_date(user_id, today)
        logs = logs_by_user[user_id]
        latest_actions = {}
        for log in logs:
            key = (log.get("medicine_id"), str(log.get("scheduled_time") or "").strip().upper())
            latest_actions[key] = log

        for minute_of_day, scheduled_time in parse_schedule_times(schedule.get("time_slot", "")):
            action = latest_actions.get((schedule["medicine_id"], scheduled_time.upper()))
            if action and action.get("status") in {"Taken", "Skipped", "Snoozed"}:
                continue
            scheduled_at = now.replace(
                hour=minute_of_day // 60,
                minute=minute_of_day % 60,
                second=0,
                microsecond=0,
            )
            delivery_key = f"scheduled:{today}:{scheduled_time}"
            if datetime.timedelta(0) <= now - scheduled_at <= datetime.timedelta(minutes=2):
                due_events.append({
                    **schedule,
                    "scheduled_time": scheduled_time,
                    "due_at": scheduled_at,
                    "delivery_key": delivery_key,
                })

        for action in logs:
            if action.get("medicine_id") != schedule["medicine_id"] or action.get("status") != "Snoozed":
                continue
            try:
                snooze_at = datetime.datetime.fromisoformat(action["snooze_until"])
            except (KeyError, TypeError, ValueError):
                continue
            latest = latest_actions.get((schedule["medicine_id"], str(action.get("scheduled_time") or "").strip().upper()))
            if latest is not action:
                continue
            if datetime.timedelta(0) <= now - snooze_at <= datetime.timedelta(minutes=2):
                due_events.append({
                    **schedule,
                    "scheduled_time": action.get("scheduled_time") or "Snoozed dose",
                    "due_at": snooze_at,
                    "delivery_key": f"snooze:{action['id']}",
                })

    return due_events


def send_due_reminders(now=None):
    now = now or datetime.datetime.now()
    sent_count = 0
    for event in _collect_due_events(now):
        if db.reminder_was_delivered(event["user_id"], event["medicine_id"], event["delivery_key"]):
            continue
        payload = {
            "title": "CareVoice మందుల రిమైండర్" if str(event.get("language", "en-IN")).lower().startswith("te") else "CareVoice Medicine Reminder",
            "body": format_reminder_message(
                event["user_name"],
                event["medicine_name"],
                event["dosage"],
                event["scheduled_time"],
                event.get("language", "en-IN"),
                event.get("instructions", ""),
                event.get("before_after_food", ""),
            ),
            "lang": event.get("language", "en-IN"),
            "user_id": event["user_id"],
            "medicine_id": event["medicine_id"],
            "scheduled_time": event["scheduled_time"],
            "delivery_key": event["delivery_key"],
            "action_token": create_reminder_action_token(event, now),
            "action_endpoint": os.getenv("CAREVOICE_REMINDER_ACTION_URL")
            or (
                f"{os.environ['RENDER_EXTERNAL_URL'].rstrip('/')}/action"
                if os.getenv("RENDER_EXTERNAL_URL")
                else "http://127.0.0.1:8765/action"
            ),
            "app_url": os.getenv("CAREVOICE_APP_URL")
            or (f"{os.environ['RENDER_EXTERNAL_URL'].rstrip('/')}/" if os.getenv("RENDER_EXTERNAL_URL") else "http://localhost:8501/"),
        }
        subscriptions = db.get_push_subscriptions(event["user_id"])
        if not subscriptions:
            continue

        delivered = False
        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info=subscription,
                    data=json.dumps(payload),
                    vapid_private_key=str(_private_key_path()),
                    vapid_claims={"sub": os.getenv("CAREVOICE_VAPID_SUBJECT", "mailto:carevoice@localhost")},
                    ttl=300,
                )
                delivered = True
            except WebPushException as error:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
                if status_code in {404, 410}:
                    db.delete_push_subscription(subscription.get("endpoint", ""))
                else:
                    logging.warning("CareVoice push delivery failed: %s", error)
            except Exception:
                logging.exception("CareVoice push delivery failed")

        if delivered:
            db.record_reminder_delivery(
                event["user_id"], event["medicine_id"], event["delivery_key"]
            )
            sent_count += 1
    return sent_count


def _worker_loop(stop_event, interval_seconds):
    while not stop_event.is_set():
        try:
            send_due_reminders()
        except Exception:
            logging.exception("CareVoice reminder worker iteration failed")
        stop_event.wait(interval_seconds)


def start_background_worker(interval_seconds=10):
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return _worker_thread
        try:
            _start_action_server()
        except OSError:
            logging.exception("CareVoice reminder action API could not start")
        stop_event = threading.Event()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            args=(stop_event, interval_seconds),
            name="carevoice-reminder-worker",
            daemon=True,
        )
        _worker_thread.start()
        return _worker_thread