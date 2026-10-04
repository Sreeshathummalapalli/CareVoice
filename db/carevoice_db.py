import sqlite3
import os
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from backend.storage import DATA_DIR

DB_NAME = str(DATA_DIR / "carevoice.db")
_PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 600_000
_LEGACY_PASSWORD_SALT = "carevoice_secure_salt_2026"

def get_db_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_NAME)), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_HASH_ITERATIONS,
    )
    return "$".join((
        _PASSWORD_HASH_SCHEME,
        str(_PASSWORD_HASH_ITERATIONS),
        salt.hex(),
        digest.hex(),
    ))


def verify_password(password, stored_hash):
    if not isinstance(stored_hash, str):
        return False

    parts = stored_hash.split("$")
    if len(parts) == 4 and parts[0] == _PASSWORD_HASH_SCHEME:
        try:
            iterations = int(parts[1])
            if not 100_000 <= iterations <= 2_000_000:
                return False
            salt = bytes.fromhex(parts[2])
            expected_digest = bytes.fromhex(parts[3])
        except ValueError:
            return False
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    legacy_digest = hashlib.sha256(
        (password + _LEGACY_PASSWORD_SALT).encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(stored_hash, legacy_digest)


def is_current_password_hash(stored_hash):
    return isinstance(stored_hash, str) and stored_hash.startswith(
        f"{_PASSWORD_HASH_SCHEME}$"
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Migration check: if users table exists but lacks reset_answer_hash, recreate tables safely
    cursor.execute("PRAGMA table_info(users)")
    u_cols = [col[1] for col in cursor.fetchall()]
    if u_cols and "reset_answer_hash" not in u_cols:
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("DROP TABLE IF EXISTS prescription_extracted_text")
        cursor.execute("DROP TABLE IF EXISTS prescriptions")
        cursor.execute("DROP TABLE IF EXISTS medicine_schedules")
        cursor.execute("DROP TABLE IF EXISTS medicine_logs")
        cursor.execute("DROP TABLE IF EXISTS medicines")
        cursor.execute("DROP TABLE IF EXISTS reminders")
        cursor.execute("DROP TABLE IF EXISTS reports")
        cursor.execute("DROP TABLE IF EXISTS diet_plans")
        cursor.execute("DROP TABLE IF EXISTS health_metrics")
        cursor.execute("DROP TABLE IF EXISTS family_members")
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            reset_question TEXT DEFAULT 'What is your primary health focus?',
            reset_answer_hash TEXT,
            phone TEXT,
            language TEXT DEFAULT 'en-IN',
            voice_gender TEXT DEFAULT 'Female Voice',
            elderly_mode INTEGER DEFAULT 0,
            onboarding_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]
    if "voice_gender" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN voice_gender TEXT DEFAULT 'Female Voice'")

    # Medicines table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            instructions TEXT NOT NULL,
            image_url TEXT,
            status TEXT DEFAULT 'Upcoming',
            frequency TEXT DEFAULT 'Daily',
            before_after_food TEXT DEFAULT 'After Food',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Medicine Schedules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicine_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_id INTEGER NOT NULL,
            scheduled_time TEXT NOT NULL,
            frequency TEXT DEFAULT 'Daily',
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE CASCADE
        )
    ''')

    # Medicine Logs / History table (What user actually took/skipped/snoozed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_id INTEGER,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            status TEXT NOT NULL,
            scheduled_time TEXT,
            actual_time TEXT,
            date TEXT NOT NULL,
            snooze_until TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Prescriptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Processed',
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Prescription Extracted Text & Structured JSON table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescription_extracted_text (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prescription_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            structured_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Reports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            summary TEXT NOT NULL,
            doctor_name TEXT,
            file_path TEXT,
            extracted_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Diet Plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS diet_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            meal_time TEXT NOT NULL,
            food_item TEXT NOT NULL,
            calories INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Reminders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_id INTEGER,
            medicine_name TEXT,
            dosage TEXT,
            reminder_time TEXT,
            status TEXT DEFAULT 'Active',
            snooze_until TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            subscription_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminder_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_id INTEGER NOT NULL,
            delivery_key TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, medicine_id, delivery_key),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE CASCADE
        )
    ''')

    # Health Metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT NOT NULL,
            recorded_date TEXT NOT NULL,
            recorded_time TEXT,
            status TEXT DEFAULT 'Normal',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Family Members table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            relationship TEXT NOT NULL,
            phone TEXT NOT NULL,
            caregiver_status TEXT DEFAULT 'Caregiver',
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()

    # Check if seed demo user exists
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_data(cursor)
        conn.commit()

    conn.close()

def seed_data(cursor):
    # Create Demo User
    demo_password = os.getenv("CAREVOICE_DEMO_PASSWORD") or secrets.token_urlsafe(32)
    demo_security_answer = os.getenv("CAREVOICE_DEMO_SECURITY_ANSWER") or secrets.token_urlsafe(32)
    demo_pw = hash_password(demo_password)
    demo_ans = hash_password(demo_security_answer.strip().lower())
    cursor.execute('''
        INSERT INTO users (name, email, password_hash, reset_question, reset_answer_hash, phone, language, elderly_mode, onboarding_completed)
        VALUES ('Ramesh Kumar', 'demo@carevoice.health', ?, 'What is your primary health focus?', ?, '+91 98765 43210', 'en-IN', 0, 1)
    ''', (demo_pw, demo_ans))
    demo_user_id = cursor.lastrowid

    amlodipine_img = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23f0fdf4' rx='16'/><circle cx='100' cy='100' r='50' fill='%23166534'/><line x1='100' y1='50' x2='100' y2='150' stroke='white' stroke-width='4'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%23166534' font-family='sans-serif' font-weight='bold'>Amlodipine 5mg</text></svg>"
    metformin_img = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23fef3c7' rx='16'/><rect x='40' y='75' width='120' height='50' rx='25' fill='%23d97706'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%2392400e' font-family='sans-serif' font-weight='bold'>Metformin 500mg</text></svg>"
    atorvastatin_img = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23dcfce7' rx='16'/><circle cx='100' cy='100' r='45' fill='%2316a34a'/><path d='M75 100 L125 100' stroke='white' stroke-width='3'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%2315803d' font-family='sans-serif' font-weight='bold'>Atorvastatin 10mg</text></svg>"
    multivitamin_img = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23f3e8ff' rx='16'/><rect x='45' y='80' width='110' height='40' rx='20' fill='%239333ea'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%236b21a8' font-family='sans-serif' font-weight='bold'>Multivitamin</text></svg>"

    medicines = [
        (demo_user_id, "Amlodipine", "5 mg (1 Tablet)", "Morning - 8:00 AM", "Take after breakfast with water for Blood Pressure.", amlodipine_img, "Upcoming", "Daily", "After breakfast"),
        (demo_user_id, "Metformin", "500 mg (1 Tablet)", "Afternoon - 1:00 PM", "Take with lunch for Blood Sugar control.", metformin_img, "Upcoming", "Daily", "With lunch"),
        (demo_user_id, "Atorvastatin", "10 mg (1 Tablet)", "Night - 9:00 PM", "Take before bed for Cholesterol.", atorvastatin_img, "Upcoming", "Daily", "Before bed"),
        (demo_user_id, "Multivitamin", "1 Capsule", "Morning - 8:30 AM", "Take after morning meal with water.", multivitamin_img, "Taken", "Daily", "After breakfast")
    ]

    cursor.executemany('''
        INSERT INTO medicines (user_id, name, dosage, time_slot, instructions, image_url, status, frequency, before_after_food)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', medicines)

    today_str = datetime.now().strftime("%Y-%m-%d")
    med_logs = [
        (demo_user_id, 4, "Multivitamin", "1 Capsule", "Taken", "08:30 AM", "08:32 AM", today_str),
        (demo_user_id, 1, "Amlodipine", "5 mg", "Taken", "08:00 AM", "08:04 AM", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")),
        (demo_user_id, 2, "Metformin", "500 mg", "Taken", "01:00 PM", "01:10 PM", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")),
        (demo_user_id, 3, "Atorvastatin", "10 mg", "Skipped", "09:00 PM", "09:15 PM", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
    ]

    cursor.executemany('''
        INSERT INTO medicine_logs (user_id, medicine_id, medicine_name, dosage, status, scheduled_time, actual_time, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', med_logs)

    reports = [
        (demo_user_id, "Complete Blood Count (CBC)", "2026-09-15", "Hemoglobin: 13.5 g/dL (Normal). WBC: 6,800 /mcL. Platelets: 250,000 /mcL. Overall cell count is healthy.", "Dr. R. Sharma", "cbc_report_sep.pdf", "WBC: 6.8, RBC: 4.5, Hb: 13.5, Platelets: 250k"),
        (demo_user_id, "HbA1c Glucose Test", "2026-09-10", "HbA1c level: 6.4%. Indicates good glycemic control with current Metformin medication.", "Dr. K. Patel", "hba1c_sep.pdf", "HbA1c: 6.4%, Fasting Glucose: 110 mg/dL"),
        (demo_user_id, "Lipid Profile Report", "2026-08-28", "Total Cholesterol: 185 mg/dL. HDL: 48 mg/dL. LDL: 110 mg/dL (Desirable). Heart risk low.", "Dr. R. Sharma", "lipid_profile.pdf", "Total Cholesterol: 185, HDL: 48, LDL: 110, Triglycerides: 135")
    ]

    cursor.executemany('''
        INSERT INTO reports (user_id, title, date, summary, doctor_name, file_path, extracted_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', reports)

    diet_plans = [
        (demo_user_id, "Breakfast", "Oatmeal with sliced banana, almonds, and low-fat milk", 320, "High fiber, good for blood pressure & sugar control"),
        (demo_user_id, "Lunch", "Brown rice, lentil dal, spinach curry, and fresh curd", 450, "Balanced protein and complex carbohydrates"),
        (demo_user_id, "Evening Snack", "Green tea with roasted chana (chickpeas)", 120, "Antioxidant rich light snack"),
        (demo_user_id, "Dinner", "2 Multigrain rotis with bottle gourd (lauki) vegetable soup", 310, "Light and easy to digest before bedtime")
    ]

    cursor.executemany('''
        INSERT INTO diet_plans (user_id, meal_time, food_item, calories, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', diet_plans)

    reminders = [
        (demo_user_id, 1, "Amlodipine", "5 mg", "08:00 AM", "Active"),
        (demo_user_id, 2, "Metformin", "500 mg", "01:00 PM", "Active"),
        (demo_user_id, 3, "Atorvastatin", "10 mg", "09:00 PM", "Active")
    ]

    cursor.executemany('''
        INSERT INTO reminders (user_id, medicine_id, medicine_name, dosage, reminder_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', reminders)

    now = datetime.now()
    dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    dates.reverse()

    bp_values = ["122/80", "120/80", "124/82", "118/78", "121/79", "119/80", "120/80"]
    sugar_values = ["102", "100", "99", "97", "98", "96", "98"]
    weight_values = ["69.0", "68.8", "68.7", "68.6", "68.5", "68.5", "68.5"]

    health_metrics = []
    for d, bp, sugar, weight in zip(dates, bp_values, sugar_values, weight_values):
        health_metrics.append((demo_user_id, "Blood Pressure", bp, "mmHg", d, "08:00 AM", "Optimal", "Morning Reading"))
        health_metrics.append((demo_user_id, "Blood Sugar", sugar, "mg/dL", d, "08:15 AM", "Normal", "Fasting"))
        health_metrics.append((demo_user_id, "Weight", weight, "kg", d, "08:30 AM", "Healthy", "Morning Weight"))

    cursor.executemany('''
        INSERT INTO health_metrics (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', health_metrics)

    family_members = [
        (demo_user_id, "Priya Sharma", "Daughter", "+91 98765 43210", "Primary Caregiver"),
        (demo_user_id, "Rajesh Kumar", "Son", "+91 98765 12345", "Emergency Contact")
    ]

    cursor.executemany('''
        INSERT INTO family_members (user_id, name, relationship, phone, caregiver_status)
        VALUES (?, ?, ?, ?, ?)
    ''', family_members)

# AUTHENTICATION & USER MANAGEMENT

def register_user(name, email, password, phone="", language="en-IN", reset_question="What is your primary health focus?", reset_answer="wellness"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clean_email = email.strip().lower()
    cursor.execute("SELECT id FROM users WHERE email = ?", (clean_email,))
    if cursor.fetchone():
        conn.close()
        return None, "An account with this email already exists."

    pw_hash = hash_password(password)
    ans_hash = hash_password(reset_answer.strip().lower())
    try:
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, reset_question, reset_answer_hash, phone, language, elderly_mode, onboarding_completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        ''', (name.strip(), clean_email, pw_hash, reset_question, ans_hash, phone.strip(), language))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
        user = dict(cursor.fetchone())
        conn.close()
        return user, None
    except Exception as e:
        conn.close()
        return None, f"Failed to register account: {e}"

def authenticate_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clean_email = email.strip().lower()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return None, "No account found with this email."

    if not verify_password(password, user["password_hash"]):
        conn.close()
        return None, "Incorrect password. Please check and try again."

    if not is_current_password_hash(user["password_hash"]):
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), user["id"]),
        )
        conn.commit()
    conn.close()
    return dict(user), None

def reset_password(email, security_answer, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    clean_email = email.strip().lower()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return False, "No account found with this email."

    if not user["reset_answer_hash"] or not verify_password(
        security_answer.strip().lower(), user["reset_answer_hash"]
    ):
        conn.close()
        return False, "Incorrect security answer."

    new_pw_hash = hash_password(new_password)
    new_answer_hash = (
        user["reset_answer_hash"]
        if is_current_password_hash(user["reset_answer_hash"])
        else hash_password(security_answer.strip().lower())
    )
    cursor.execute(
        "UPDATE users SET password_hash = ?, reset_answer_hash = ? WHERE email = ?",
        (new_pw_hash, new_answer_hash, clean_email),
    )
    conn.commit()
    conn.close()
    return True, "Password reset successfully! You can now log in."

def update_user_preferences(user_id, language=None, elderly_mode=None, onboarding_completed=None, voice_gender=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if language is not None:
        cursor.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
    if elderly_mode is not None:
        cursor.execute("UPDATE users SET elderly_mode = ? WHERE id = ?", (1 if elderly_mode else 0, user_id))
    if onboarding_completed is not None:
        cursor.execute("UPDATE users SET onboarding_completed = ? WHERE id = ?", (1 if onboarding_completed else 0, user_id))
    if voice_gender is not None:
        cursor.execute("UPDATE users SET voice_gender = ? WHERE id = ?", (voice_gender, user_id))

    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# MEDICINES & SCHEDULES

def get_all_medicines(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicines WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_active_reminder_schedules():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.user_id, u.name AS user_name, u.language,
               m.id AS medicine_id, m.name AS medicine_name, m.dosage,
               m.time_slot, m.frequency, m.instructions, m.before_after_food
        FROM medicines m
        JOIN users u ON u.id = m.user_id
        JOIN reminders r ON r.medicine_id = m.id AND r.user_id = m.user_id
        WHERE r.status = 'Active' AND LOWER(m.frequency) != 'as needed'
        ORDER BY m.user_id, m.id
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_medicine_by_id(user_id, med_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicines WHERE id = ? AND user_id = ?", (med_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_medicine(user_id, name, dosage, time_slot, instructions, frequency="Daily", before_after_food="After Food", image_url=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not image_url:
        image_url = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23f0fdf4' rx='16'/><circle cx='100' cy='100' r='45' fill='%23166534'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%23166534' font-family='sans-serif' font-weight='bold'>Tablet</text></svg>"

    cursor.execute('''
        INSERT INTO medicines (user_id, name, dosage, time_slot, instructions, image_url, status, frequency, before_after_food)
        VALUES (?, ?, ?, ?, ?, ?, 'Upcoming', ?, ?)
    ''', (user_id, name, dosage, time_slot, instructions, image_url, frequency, before_after_food))
    med_id = cursor.lastrowid

    # Create schedule record
    cursor.execute('''
        INSERT INTO medicine_schedules (user_id, medicine_id, scheduled_time, frequency, status)
        VALUES (?, ?, ?, ?, 'Active')
    ''', (user_id, med_id, time_slot, frequency))

    # Create reminder record
    cursor.execute('''
        INSERT INTO reminders (user_id, medicine_id, medicine_name, dosage, reminder_time, status)
        VALUES (?, ?, ?, ?, ?, 'Active')
    ''', (user_id, med_id, name, dosage, time_slot))

    conn.commit()
    conn.close()
    return med_id

def update_medicine(user_id, med_id, name, dosage, time_slot, instructions, frequency, before_after_food, image_url=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE medicines
        SET name = ?, dosage = ?, time_slot = ?, instructions = ?, frequency = ?,
            before_after_food = ?, image_url = COALESCE(?, image_url)
        WHERE id = ? AND user_id = ?
    ''', (name, dosage, time_slot, instructions, frequency, before_after_food, image_url, med_id, user_id))
    updated = cursor.rowcount > 0
    if updated:
        cursor.execute('''
            UPDATE medicine_schedules
            SET scheduled_time = ?, frequency = ?
            WHERE medicine_id = ? AND user_id = ?
        ''', (time_slot, frequency, med_id, user_id))
        cursor.execute('''
            UPDATE reminders
            SET medicine_name = ?, dosage = ?, reminder_time = ?
            WHERE medicine_id = ? AND user_id = ?
        ''', (name, dosage, time_slot, med_id, user_id))
    conn.commit()
    conn.close()
    return updated

def update_medicine_status(user_id, med_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE medicines SET status = ? WHERE id = ? AND user_id = ?", (new_status, med_id, user_id))
    conn.commit()
    conn.close()

def delete_medicine(user_id, med_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medicines WHERE id = ? AND user_id = ?", (med_id, user_id))
    cursor.execute("DELETE FROM medicine_schedules WHERE medicine_id = ? AND user_id = ?", (med_id, user_id))
    cursor.execute("DELETE FROM reminders WHERE medicine_id = ? AND user_id = ?", (med_id, user_id))
    conn.commit()
    conn.close()

# MEDICINE LOGS / HISTORY

def log_medicine_action(user_id, medicine_id, medicine_name, dosage, status, scheduled_time=None, actual_time=None, date_str=None, snooze_until=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if not actual_time:
        actual_time = datetime.now().strftime("%I:%M %p")

    cursor.execute('''
        INSERT INTO medicine_logs (user_id, medicine_id, medicine_name, dosage, status, scheduled_time, actual_time, date, snooze_until)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, medicine_id, medicine_name, dosage, status, scheduled_time, actual_time, date_str, snooze_until))
    conn.commit()

    if status in ['Taken', 'Skipped']:
        cursor.execute("UPDATE medicines SET status = ? WHERE id = ? AND user_id = ?", (status, medicine_id, user_id))
        conn.commit()

    conn.close()

def get_medicine_history(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicine_logs WHERE user_id = ? ORDER BY date DESC, actual_time DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_medicine_logs_for_date(user_id, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM medicine_logs WHERE user_id = ? AND date = ? ORDER BY id ASC",
        (user_id, date_str),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_push_subscription(user_id, subscription):
    endpoint = subscription.get("endpoint") if isinstance(subscription, dict) else None
    if not endpoint:
        raise ValueError("A valid browser push subscription is required.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO push_subscriptions (user_id, endpoint, subscription_json)
        VALUES (?, ?, ?)
        ON CONFLICT(endpoint) DO UPDATE SET
            user_id = excluded.user_id,
            subscription_json = excluded.subscription_json,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, endpoint, json.dumps(subscription)))
    conn.commit()
    conn.close()

def get_push_subscriptions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT subscription_json FROM push_subscriptions WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row["subscription_json"]) for row in rows]

def delete_push_subscription(endpoint):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()

def reminder_was_delivered(user_id, medicine_id, delivery_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 1 FROM reminder_deliveries
        WHERE user_id = ? AND medicine_id = ? AND delivery_key = ?
        LIMIT 1
    ''', (user_id, medicine_id, delivery_key))
    delivered = cursor.fetchone() is not None
    conn.close()
    return delivered

def record_reminder_delivery(user_id, medicine_id, delivery_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO reminder_deliveries (user_id, medicine_id, delivery_key)
        VALUES (?, ?, ?)
    ''', (user_id, medicine_id, delivery_key))
    conn.commit()
    inserted = cursor.rowcount == 1
    conn.close()
    return inserted

# PRESCRIPTIONS & OCR DATA

def add_prescription(user_id, filename, file_path, raw_text, structured_json_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO prescriptions (user_id, filename, file_path, status)
        VALUES (?, ?, ?, 'Processed')
    ''', (user_id, filename, file_path))
    rx_id = cursor.lastrowid

    json_str = json.dumps(structured_json_list)
    cursor.execute('''
        INSERT INTO prescription_extracted_text (prescription_id, user_id, raw_text, structured_json)
        VALUES (?, ?, ?, ?)
    ''', (rx_id, user_id, raw_text, json_str))

    conn.commit()
    conn.close()
    return rx_id

def get_user_prescriptions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, e.raw_text, e.structured_json 
        FROM prescriptions p
        LEFT JOIN prescription_extracted_text e ON p.id = e.prescription_id
        WHERE p.user_id = ? ORDER BY p.upload_date DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# HEALTH METRICS & TRACKING

def add_health_metric(user_id, metric_name, value, unit, recorded_date=None, recorded_time=None, status="Normal", notes=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    if not recorded_date:
        recorded_date = datetime.now().strftime("%Y-%m-%d")
    if not recorded_time:
        recorded_time = datetime.now().strftime("%I:%M %p")

    cursor.execute('''
        INSERT INTO health_metrics (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes))
    conn.commit()
    conn.close()

def save_health_vitals(user_id, bp_value, bp_status, sugar_value, sugar_status, sugar_type, recorded_date):
    """Save a paired blood-pressure and blood-sugar reading atomically."""
    recorded_time = datetime.now().strftime("%I:%M %p")
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO health_metrics
                    (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (user_id, "Blood Pressure", bp_value, "mmHg", recorded_date, recorded_time, bp_status, "User manual log"),
                (user_id, "Blood Sugar", sugar_value, "mg/dL", recorded_date, recorded_time, sugar_status, sugar_type),
            ])
        return True
    finally:
        conn.close()

def save_or_update_voice_health_metric(user_id, metric_name, value, unit, recorded_date=None, recorded_time=None, status="Normal", notes=""):
    recorded_date = recorded_date or datetime.now().strftime("%Y-%m-%d")
    recorded_time = recorded_time or datetime.now().strftime("%I:%M %p")
    conn = get_db_connection()
    cursor = conn.cursor()
    row = None

    if metric_name == "Blood Sugar" and notes:
        cursor.execute('''
            SELECT id FROM health_metrics
            WHERE user_id = ? AND metric_name = ? AND recorded_date = ? AND LOWER(notes) = LOWER(?)
            ORDER BY id DESC LIMIT 1
        ''', (user_id, metric_name, recorded_date, notes))
        row = cursor.fetchone()
        if not row:
            cursor.execute('''
                SELECT id FROM health_metrics
                WHERE user_id = ? AND metric_name = ? AND recorded_date = ?
                    AND notes = 'Added via Voice Assistant'
                ORDER BY id DESC LIMIT 1
            ''', (user_id, metric_name, recorded_date))
            row = cursor.fetchone()
    else:
        cursor.execute('''
            SELECT id FROM health_metrics
            WHERE user_id = ? AND metric_name = ? AND recorded_date = ?
            ORDER BY id DESC LIMIT 1
        ''', (user_id, metric_name, recorded_date))
        row = cursor.fetchone()

    if row:
        cursor.execute('''
            UPDATE health_metrics
            SET value = ?, unit = ?, recorded_time = ?, status = ?, notes = ?
            WHERE id = ? AND user_id = ?
        ''', (value, unit, recorded_time, status, notes, row["id"], user_id))
        metric_id = row["id"]
    else:
        cursor.execute('''
            INSERT INTO health_metrics (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, metric_name, value, unit, recorded_date, recorded_time, status, notes))
        metric_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return metric_id

def get_all_health_metrics(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM health_metrics WHERE user_id = ? ORDER BY recorded_date DESC, id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_latest_health_metrics(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    metrics = {}
    for metric_name in ["Blood Pressure", "Blood Sugar", "Weight", "Heart Rate"]:
        cursor.execute('''
            SELECT * FROM health_metrics 
            WHERE user_id = ? AND metric_name = ? 
            ORDER BY recorded_date DESC, id DESC LIMIT 1
        ''', (user_id, metric_name))
        row = cursor.fetchone()
        if row:
            metrics[metric_name] = dict(row)
    conn.close()
    return metrics

def get_health_metrics_for_date(user_id, recorded_date=None):
    target_date = recorded_date or datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM health_metrics WHERE user_id = ? AND recorded_date = ? ORDER BY id ASC",
        (user_id, target_date),
    )
    rows = cursor.fetchall()
    conn.close()
    metrics = {}
    for row in rows:
        record = dict(row)
        metrics[record["metric_name"]] = record
    return metrics

def get_health_history_for_charts(user_id, days=30):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT * FROM health_metrics 
        WHERE user_id = ? AND recorded_date >= ? 
        ORDER BY recorded_date ASC
    ''', (user_id, cutoff))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# REPORTS

def get_all_reports(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE user_id = ? ORDER BY date DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_report(user_id, title, date_str, summary, doctor_name, file_path=None, extracted_text=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reports (user_id, title, date, summary, doctor_name, file_path, extracted_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, title, date_str, summary, doctor_name, file_path, extracted_text))
    conn.commit()
    conn.close()

# DIET PLANS

def get_all_diet_plans(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_plans WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_diet_plan(user_id, diet_items):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM diet_plans WHERE user_id = ?", (user_id,))
    for d in diet_items:
        cursor.execute('''
            INSERT INTO diet_plans (user_id, meal_time, food_item, calories, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, d["meal_time"], d["food_item"], d.get("calories", 250), d.get("notes", "")))
    conn.commit()
    conn.close()

# FAMILY MEMBERS

def get_all_family_members(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM family_members WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_family_member(user_id, name, relationship, phone, caregiver_status="Caregiver"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO family_members (user_id, name, relationship, phone, caregiver_status)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, name, relationship, phone, caregiver_status))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("CareVoice Database initialized with full schema and multi-user isolation.")
