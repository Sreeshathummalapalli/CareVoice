# CareVoice — Complete Working Healthcare Web Application & Voice Assistant
import streamlit as st
import streamlit.components.v1 as components
import os
import time
import hashlib
import base64
import secrets
import tempfile
import json
import datetime
import logging
import re
import sqlite3
import textwrap
import pandas as pd
import altair as alt
import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv
from gtts import gTTS

load_dotenv()

# Import Custom Healthcare Modules
import sys
sys.path.append('.')
from db import carevoice_db as db
from backend import ocr_service as ocr
from backend import ai_services as ai
from backend import reminder_worker
from backend import storage
from backend.telugu_localization import display_medicine_name
from frontend import navigation as nav

voice_mic_component = components.declare_component(
    "carevoice_voice_mic",
    path=os.path.join(os.path.dirname(__file__), "frontend", "voice_mic"),
)
push_setup_component = components.declare_component(
    "carevoice_push_setup",
    path=os.path.join(os.path.dirname(__file__), "frontend", "push_setup"),
)
auth_cookie_component = components.declare_component(
    "carevoice_auth_cookie",
    path=os.path.join(os.path.dirname(__file__), "frontend", "auth_cookie"),
)

st.set_page_config(
    page_title="CareVoice — Complete Healthcare Management System",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

@st.cache_resource
def start_carevoice_reminder_worker():
    return reminder_worker.start_background_worker()


start_carevoice_reminder_worker()

storage.ensure_storage_dirs()


@st.cache_resource
def get_recognizer():
    return sr.Recognizer()


recognizer = get_recognizer()


@st.cache_data(show_spinner=False, max_entries=128)
def generate_offline_tts_data(text, lang_code="en-IN", voice_gender=None):
    if not text:
        return ""
    if voice_gender is None:
        voice_gender = st.session_state.get("voice_gender", "Female Voice")
    if str(lang_code).lower().startswith("te"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as audio_file:
                audio_path = audio_file.name
            gTTS(text=text, lang="te").save(audio_path)
            with open(audio_path, "rb") as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode("ascii")
            os.unlink(audio_path)
            if audio_data:
                return f"data:audio/mpeg;base64,{audio_data}"
        except Exception:
            try:
                os.unlink(audio_path)
            except Exception:
                pass
        return ""
    try:
        engine = pyttsx3.init()
        language = str(lang_code)[:2].lower()
        voices = engine.getProperty("voices")
        selected_voice = ai.choose_voice_for_gender(voices, lang_code, voice_gender)
        if selected_voice:
            engine.setProperty("voice", getattr(selected_voice, "id", selected_voice.id if hasattr(selected_voice, "id") else None))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as audio_file:
            audio_path = audio_file.name
        engine.save_to_file(text, audio_path)
        engine.runAndWait()
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("ascii")
        os.unlink(audio_path)
        if audio_data:
            return f"data:audio/wav;base64,{audio_data}"
    except Exception:
        pass

    try:
        language = "te" if str(lang_code).lower().startswith("te") else "en"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as audio_file:
            audio_path = audio_file.name
        gTTS(text=text, lang=language).save(audio_path)
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("ascii")
        os.unlink(audio_path)
        return f"data:audio/mpeg;base64,{audio_data}"
    except Exception:
        return ""


def required_daily_reminder_count(frequency):
    normalized = str(frequency).strip().lower()
    if "three" in normalized or normalized.startswith("3"):
        return 3
    if "twice" in normalized or normalized.startswith("2"):
        return 2
    if "once" in normalized or "daily" in normalized or normalized.startswith("1"):
        return 1
    return None


def count_clock_times(schedule_text):
    matches = re.findall(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", str(schedule_text), re.IGNORECASE)
    return len({(int(hour) % 12 + (12 if period.lower() == "pm" else 0), int(minute)) for hour, minute, period in matches})


def health_chart_date_labels(date_keys, is_te=False):
    parsed_dates = {
        date_key: pd.to_datetime(date_key, errors="coerce")
        for date_key in date_keys
    }
    labels = {
        date_key: date_value.strftime("%d-%m" if is_te else "%b %d")
        for date_key, date_value in parsed_dates.items()
        if not pd.isna(date_value)
    }
    if len(set(labels.values())) != len(labels):
        labels = {
            date_key: date_value.strftime("%d-%m-%Y" if is_te else "%b %d %Y")
            for date_key, date_value in parsed_dates.items()
            if not pd.isna(date_value)
        }
    return labels


def health_chart_x_axis(is_te=False):
    return alt.Axis(
        title="తేదీ" if is_te else "Date",
        labelAngle=-35,
        labelOverlap="greedy",
        labelFontSize=13,
        titleFontSize=15,
        labelColor="#142536",
        titleColor="#142536",
        domainColor="#9aa8b5",
        tickColor="#9aa8b5",
    )


def style_health_chart(chart):
    return (
        chart.configure(background="#ffffff")
        .configure_view(fill="#ffffff", stroke=None)
        .configure_axis(
            gridColor="#e5eaf0",
            gridOpacity=0.8,
            labelColor="#142536",
            titleColor="#142536",
            domainColor="#9aa8b5",
            tickColor="#9aa8b5",
            titleFontSize=15,
        )
        .configure_legend(labelColor="#142536", titleColor="#142536", labelFontSize=13)
    )


def render_blood_pressure_chart(chart_df, is_te=False):
    if chart_df is None or chart_df.empty:
        return
    date_order = chart_df["Date"].tolist()
    melted = chart_df.melt("Date", ["Systolic", "Diastolic"], var_name="Reading", value_name="Value")
    if is_te:
        melted["Reading"] = melted["Reading"].map({
            "Systolic": "సిస్టోలిక్",
            "Diastolic": "డయాస్టోలిక్",
        })
    chart = alt.Chart(melted).mark_line(point=alt.OverlayMarkDef(size=85), strokeWidth=3).encode(
        x=alt.X("Date:N", sort=date_order, axis=health_chart_x_axis(is_te)),
        y=alt.Y(
            "Value:Q",
            title="రక్తపోటు (mmHg)" if is_te else "Blood Pressure (mmHg)",
            axis=alt.Axis(titleFontSize=15),
        ),
        color=alt.Color(
            "Reading:N",
            title=None,
            scale=alt.Scale(
                domain=["సిస్టోలిక్", "డయాస్టోలిక్"] if is_te else ["Systolic", "Diastolic"],
                range=["#16834b", "#28708a"],
            ),
        ),
        tooltip=[
            alt.Tooltip("Date:N", title="తేదీ" if is_te else "Date"),
            alt.Tooltip("Reading:N", title="రీడింగ్" if is_te else "Reading"),
            alt.Tooltip("Value:Q", title="mmHg"),
        ],
    ).properties(height=310)
    st.altair_chart(style_health_chart(chart), use_container_width=True)


def render_blood_sugar_chart(chart_df, is_te=False):
    if chart_df is None or chart_df.empty:
        return
    date_order = list(dict.fromkeys(chart_df["Date"].tolist()))
    chart = alt.Chart(chart_df).mark_bar(size=26, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Date:N", sort=date_order, axis=health_chart_x_axis(is_te)),
        xOffset=alt.XOffset(
            "Reading:N",
            sort=["భోజనానికి ముందు", "భోజనం తర్వాత"] if is_te else ["Before Food", "After Food"],
        ),
        y=alt.Y(
            "Value:Q",
            title="రక్తంలో చక్కెర (mg/dL)" if is_te else "Blood Sugar (mg/dL)",
            scale=alt.Scale(zero=True),
            axis=alt.Axis(titleFontSize=15),
        ),
        color=alt.Color(
            "Reading:N",
            title=None,
            scale=alt.Scale(
                domain=["భోజనానికి ముందు", "భోజనం తర్వాత"] if is_te else ["Before Food", "After Food"],
                range=["#16834b", "#71ad45"],
            ),
        ),
        tooltip=[
            alt.Tooltip("Date:N", title="తేదీ" if is_te else "Date"),
            alt.Tooltip("Reading:N", title="రీడింగ్" if is_te else "Reading"),
            alt.Tooltip("Value:Q", title="mg/dL"),
        ],
    ).properties(height=310)
    st.altair_chart(style_health_chart(chart), use_container_width=True)


def clean_speech_text(text):
    if text is None:
        return ""
    cleaned = str(text)
    cleaned = re.sub(r"\*\*|__|`", "", cleaned)
    cleaned = re.sub(r"\s*\n\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*(\d+)\.\s*", r"\1. ", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    if not cleaned:
        return ""
    if re.fullmatch(r"[\d\s\-/.,%:]+", cleaned):
        return f"సమాధానం {cleaned}" if st.session_state.get("lang_code", "en-IN").lower().startswith("te") else f"The answer is {cleaned}"
    return cleaned


def generate_audio_player(text, lang_code="en-IN", voice_gender=None):
    if not text:
        return ""
    if voice_gender is None:
        voice_gender = st.session_state.get("voice_gender", "Female Voice")
    normalized_text = clean_speech_text(text)
    safe_text = json.dumps(normalized_text, ensure_ascii=True).replace("<", "\\u003c")
    safe_lang = json.dumps("te-IN" if "te" in lang_code.lower() else "en-IN")
    safe_gender = json.dumps(str(voice_gender).lower())
    audio_source = generate_offline_tts_data(normalized_text, lang_code, voice_gender)
    safe_audio_source = json.dumps(audio_source).replace("<", "\\u003c")

    return f"""
        <audio id="carevoice-fallback-audio" autoplay style="display:none;"></audio>
        <script>
          (() => {{
            const replyText = {safe_text};
            const replyLanguage = {safe_lang};
            const replyGender = {safe_gender};
            const audioSource = {safe_audio_source};
            const playFallback = () => {{
              const audio = document.getElementById("carevoice-fallback-audio");
              if (!audioSource || !audio) return;
              audio.src = audioSource;
              audio.play().catch(() => {{}});
            }};
            const speakReply = () => {{
              if (!("speechSynthesis" in window)) {{
                playFallback();
                return;
              }}
              const voices = window.speechSynthesis.getVoices();
              window.speechSynthesis.cancel();
              const utterance = new SpeechSynthesisUtterance(replyText);
              utterance.lang = replyLanguage;
                            const languagePrefix = replyLanguage.slice(0, 2).toLowerCase();

              const isFemale = replyGender.includes("female") || replyGender.includes("girl") || replyGender.includes("woman");
              const femaleKeywords = ["female", "zira", "heera", "hazel", "susan", "catherine", "samantha", "victoria", "karen", "aria", "emma", "ava", "jenny", "michelle", "sonia", "libby", "natasha", "moira"];
              const maleKeywords = ["david", "mark", "george", "ravi", "alex", "daniel", "guy", "ryan", "tony", "thomas", "oliver", "liam", "eric", "andrew"];

                            const preferredVoice = voices.find(voice => {{
                const name = voice.name.toLowerCase();
                                const matchesLang = voice.lang.toLowerCase().startsWith(languagePrefix);
                if (!matchesLang) return false;
                if (isFemale) return femaleKeywords.some(k => name.includes(k));
                return !femaleKeywords.some(k => name.includes(k)) &&
                  (maleKeywords.some(k => name.includes(k)) || /(^|[\s-])male($|[\s-])/.test(name));
              }}) || voices.find(voice => {{
                const name = voice.name.toLowerCase();
                                if (!voice.lang.toLowerCase().startsWith(languagePrefix)) return false;
                if (isFemale) return femaleKeywords.some(k => name.includes(k));
                return !femaleKeywords.some(k => name.includes(k)) &&
                  (maleKeywords.some(k => name.includes(k)) || /(^|[\s-])male($|[\s-])/.test(name));
              }});
                            const languageVoice = voices.find(voice => voice.lang.toLowerCase().startsWith(languagePrefix));
                            const selectedVoice = preferredVoice || languageVoice;

                            if (!selectedVoice && languagePrefix === "te") {{
                                playFallback();
                                return;
                            }}
                            if (selectedVoice) utterance.voice = selectedVoice;
                            utterance.onerror = playFallback;
                            window.speechSynthesis.speak(utterance);
            }};
                        window.setTimeout(speakReply, 200);
          }})();
        </script>
    """

def trigger_web_notification(title, body):
    """Fires HTML5 Web Push Notification in supported browsers."""
    js_code = f"""
    <script>
    if (window.Notification) {{
        if (Notification.permission === "granted") {{
            new Notification("{title}", {{ body: "{body}", icon: "🌿" }});
        }} else if (Notification.permission !== "denied") {{
            Notification.requestPermission().then(permission => {{
                if (permission === "granted") {{
                    new Notification("{title}", {{ body: "{body}", icon: "🌿" }});
                }}
            }});
        }}
    }}
    </script>
    """
    return js_code

def listen_to_speech(lang_code="en-IN"):
    is_te = str(lang_code).lower().startswith("te")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            st.toast("🎙️ వింటున్నాను... ఇప్పుడు మాట్లాడండి" if is_te else "🎙️ Listening... Speak now", icon="🎤")
            audio = recognizer.listen(source, phrase_time_limit=7)
            st.toast("⚡ మాటలను విశ్లేషిస్తున్నాను..." if is_te else "⚡ Processing speech...", icon="⚙️")
            text = recognizer.recognize_google(audio, language=lang_code)
            return text
    except sr.UnknownValueError:
        st.warning("స్పష్టంగా వినిపించలేదు. దయచేసి మళ్లీ మాట్లాడండి." if is_te else "I couldn't hear clearly. Please speak again.")
        return None
    except sr.RequestError:
        st.warning("మాట్లాడినదాన్ని గుర్తించే సేవ ప్రస్తుతం అందుబాటులో లేదు." if is_te else "Speech recognition service unavailable.")
        return None
    except Exception as e:
        err_msg = str(e)
        if "pyaudio" in err_msg.lower() or "attributeerror" in err_msg.lower() or "find" in err_msg.lower():
            st.info(
                "💡 సర్వర్‌లో మైక్రోఫోన్ గుర్తించబడలేదు. బ్రౌజర్ మైక్రోఫోన్‌ను ఉపయోగించండి లేదా మీ ప్రశ్నను క్రింద టైప్ చేయండి."
                if is_te else
                "💡 Server mic hardware (PyAudio) not detected. Please use the Browser Microphone button or type your query below!"
            )
        else:
            st.warning(f"వాయిస్ ఇన్‌పుట్ లోపం: {err_msg}" if is_te else f"Voice input error: {err_msg}")
        return None

# SESSION STATE INITIALIZATION
if "user" not in st.session_state:
    st.session_state.user = None

if "view" not in st.session_state:
    st.session_state.view = "landing"  # landing, login, signup, reset_password, onboarding, app

requested_view = st.query_params.get("view")
if requested_view in {"login", "signup"}:
    st.session_state.view = requested_view
    st.query_params.clear()

if "lang_code" not in st.session_state:
    st.session_state.lang_code = "en-IN"

requested_language = st.query_params.get("lang")
if requested_language in {"en-IN", "te-IN"}:
    st.session_state.lang_code = requested_language
    del st.query_params["lang"]

if "elderly_mode" not in st.session_state:
    st.session_state.elderly_mode = False

if "voice_gender" not in st.session_state:
    st.session_state.voice_gender = "Female Voice"

if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

requested_page = st.query_params.get("nav_to")
if requested_page in {item["page"] for item in nav.NAV_ITEMS}:
    st.session_state.current_page = requested_page
    del st.query_params["nav_to"]

if "auth_session_token" not in st.session_state:
    st.session_state.auth_session_token = ""
if "pending_auth_cookie" not in st.session_state:
    st.session_state.pending_auth_cookie = None

logout_requested = st.query_params.get("logout") == "1"
if logout_requested:
    del st.query_params["logout"]
    db.revoke_auth_session(st.session_state.auth_session_token)
    st.session_state.auth_session_token = ""
    st.session_state.user = None
    st.session_state.view = "landing"
    st.session_state.current_page = "Home"
    st.session_state.pending_auth_cookie = {
        "action": "clear",
        "nonce": secrets.token_urlsafe(12),
    }

cookie_command = st.session_state.pending_auth_cookie
auth_cookie_value = auth_cookie_component(
    command=cookie_command or {},
    key="carevoice_auth_cookie",
    default=None,
)
browser_auth_token = (
    auth_cookie_value.get("token", "")
    if isinstance(auth_cookie_value, dict)
    else ""
)

if cookie_command:
    if (
        cookie_command["action"] == "set"
        and isinstance(auth_cookie_value, dict)
        and auth_cookie_value.get("error")
    ):
        db.revoke_auth_session(cookie_command.get("token", ""))
        st.session_state.auth_session_token = ""
        st.session_state.user = None
        st.session_state.view = "login"
        st.session_state.pending_auth_cookie = {
            "action": "clear",
            "nonce": secrets.token_urlsafe(12),
        }
        st.session_state.auth_cookie_error = auth_cookie_value["error"]
    elif cookie_command["action"] == "clear" and not browser_auth_token:
        st.session_state.pending_auth_cookie = None
    elif (
        cookie_command["action"] == "set"
        and browser_auth_token == cookie_command.get("token")
    ):
        st.session_state.pending_auth_cookie = None
        st.session_state.auth_session_token = browser_auth_token
elif (
    not logout_requested
    and not st.session_state.user
    and browser_auth_token
    and requested_view not in {"login", "signup"}
):
    restored_user = db.get_user_by_auth_session(browser_auth_token)
    if restored_user:
        st.session_state.user = restored_user
        st.session_state.auth_session_token = browser_auth_token
        st.session_state.voice_gender = restored_user.get("voice_gender", "Female Voice")
        st.session_state.lang_code = restored_user.get("language", "en-IN")
        st.session_state.elderly_mode = bool(restored_user.get("elderly_mode", 0))
        st.session_state.view = (
            "app" if restored_user.get("onboarding_completed", 0) else "onboarding"
        )
    else:
        st.session_state.pending_auth_cookie = {
            "action": "clear",
            "nonce": secrets.token_urlsafe(12),
        }

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_health_save" not in st.session_state:
    st.session_state.pending_health_save = None

if "active_audio_html" not in st.session_state:
    st.session_state.active_audio_html = ""

if "web_notif_html" not in st.session_state:
    st.session_state.web_notif_html = ""

if "reminder_alert" not in st.session_state:
    st.session_state.reminder_alert = None

if "rx_step" not in st.session_state:
    st.session_state.rx_step = 1

if "rx_extracted_list" not in st.session_state:
    st.session_state.rx_extracted_list = []

if "rx_raw_text" not in st.session_state:
    st.session_state.rx_raw_text = ""

if "rx_file_path" not in st.session_state:
    st.session_state.rx_file_path = ""

if st.session_state.get("rx_flow_version") != 2:
    st.session_state.rx_step = 1
    st.session_state.rx_extracted_list = []
    st.session_state.rx_raw_text = ""
    st.session_state.rx_file_path = ""
    st.session_state.rx_uploaded_digest = ""
    st.session_state.rx_flow_version = 2

if "skip_confirm_med_id" not in st.session_state:
    st.session_state.skip_confirm_med_id = None

if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 1

# CSS Design System (White background, Green accents, Inter typography, Sage green sections)
def apply_custom_css():
    """
    Comprehensive UI Design System for CareVoice
    Implements healthcare green color palette, Inter typography, spacing system,
    button styles, card styles, input field styles, badge/pill styles,
    responsive breakpoints, and elderly mode adjustments.
    
    Requirements: 3.1, 3.2, 3.3, 3.7, 14.1-14.7, 19.1-19.8
    """
    elderly = st.session_state.elderly_mode
    
    # Typography Scale with Elderly Mode (+33% increase)
    base_font = "20px" if elderly else "15px"
    h1_size = "64px" if elderly else "48px"
    h2_size = "48px" if elderly else "36px"
    h3_size = "37px" if elderly else "28px"
    h4_size = "27px" if elderly else "20px"
    large_body = "24px" if elderly else "18px"
    small_text = "19px" if elderly else "14px"
    tiny_text = "17px" if elderly else "13px"
    
    # Line height adjustment for elderly mode
    line_height = "1.7" if elderly else "1.6"
    
    # Touch target sizes (48px minimum for elderly mode, 44px standard)
    touch_target = "48px" if elderly else "44px"
    
    # Spacing system based on 4px base unit
    spacing_xs = "4px"
    spacing_sm = "8px"
    spacing_md = "12px"
    spacing_lg = "16px"
    spacing_xl = "24px"
    spacing_2xl = "32px"
    spacing_3xl = "48px"
    spacing_4xl = "64px"
    spacing_5xl = "96px"

    st.markdown(f"""
        <style>
        /* ===== TYPOGRAPHY - Inter Font Family ===== */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background-color: #ffffff !important;
            color: #0f172a !important;
            font-size: {base_font};
            line-height: {line_height};
        }}

        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"],
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"],
        [data-testid="stHeader"] {{
            background-color: #ffffff !important;
            color: #0f172a !important;
        }}

        header[data-testid="stHeader"] {{
            display: none !important;
            height: 0px !important;
            min-height: 0px !important;
        }}

        @media (max-width: 767px) {{
            section[data-testid="stSidebar"] {{
                display: none !important;
            }}
        }}

        .block-container,
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0.5rem !important;
        }}

        section[data-testid="stSidebar"] > div:first-child {{
            padding-top: 0.5rem !important;
        }}

        /* ===== COLOR PALETTE - CSS Variables ===== */
        :root {{
            /* Primary Healthcare Green */
            --primary-green: #166534;
            --primary-green-dark: #14532d;
            --primary-green-light: #16a34a;
            --primary-green-hover: #15803d;
            
            /* Sage Green Variants */
            --sage-bg: #ffffff;
            --sage-border: #e2e8f0;
            --sage-light: #f8fafc;
            
            /* Background Colors */
            --bg-white: #ffffff;
            --bg-off-white: #ffffff;
            --bg-light-gray: #ffffff;
            
            /* Border Colors */
            --border-color: #e2e8f0;
            --border-color-dark: #cbd5e1;
            --border-focus: #166534;
            
            /* Text Colors */
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-tertiary: #64748b;
            --text-muted: #94a3b8;
            
            /* Status Colors */
            --status-success-bg: #ffffff;
            --status-success-text: #166534;
            --status-warning-bg: #ffffff;
            --status-warning-text: #92400e;
            --status-error-bg: #ffffff;
            --status-error-text: #991b1b;
            --status-info-bg: #ffffff;
            --status-info-text: #1e40af;
            
            /* Spacing Scale (4px base unit) */
            --spacing-xs: {spacing_xs};
            --spacing-sm: {spacing_sm};
            --spacing-md: {spacing_md};
            --spacing-lg: {spacing_lg};
            --spacing-xl: {spacing_xl};
            --spacing-2xl: {spacing_2xl};
            --spacing-3xl: {spacing_3xl};
            --spacing-4xl: {spacing_4xl};
            --spacing-5xl: {spacing_5xl};
            
            /* Touch Targets */
            --touch-target-min: {touch_target};
            
            /* Border Radius */
            --radius-sm: 8px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --radius-xl: 20px;
            --radius-full: 9999px;
            
            /* Shadows */
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
            --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.03);
            --shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.06);
            --shadow-xl: 0 8px 24px rgba(0, 0, 0, 0.08);
            --shadow-green: 0 4px 12px rgba(22, 101, 52, 0.15);
            
            /* Transitions */
            --transition-fast: 150ms ease;
            --transition-normal: 200ms ease;
            --transition-slow: 300ms ease;
        }}

        /* ===== HEADING STYLES ===== */
        h1 {{ 
            font-size: {h1_size} !important; 
            font-weight: 700 !important; 
            color: var(--text-primary) !important;
            letter-spacing: -0.02em;
            line-height: 1.1 !important;
            margin-bottom: var(--spacing-lg) !important;
        }}
        
        h2 {{ 
            font-size: {h2_size} !important; 
            font-weight: 700 !important; 
            color: var(--text-primary) !important;
            letter-spacing: -0.01em;
            line-height: 1.2 !important;
            margin-bottom: var(--spacing-md) !important;
        }}
        
        h3 {{ 
            font-size: {h3_size} !important; 
            font-weight: 600 !important; 
            color: var(--text-primary) !important;
            letter-spacing: -0.01em;
            line-height: 1.3 !important;
            margin-bottom: var(--spacing-md) !important;
        }}
        
        h4 {{ 
            font-size: {h4_size} !important; 
            font-weight: 600 !important; 
            color: var(--text-primary) !important;
            line-height: 1.4 !important;
            margin-bottom: var(--spacing-sm) !important;
        }}

        /* ===== BUTTON STYLES ===== */
        
        /* Primary Button - Healthcare Green */
        .stButton>button {{
            background-color: var(--primary-green) !important;
            color: #ffffff !important;
            border: 1px solid var(--primary-green) !important;
            border-radius: var(--radius-md) !important;
            font-weight: 600 !important;
            font-size: {base_font} !important;
            min-height: var(--touch-target-min) !important;
            padding: {spacing_md} {spacing_xl} !important;
            transition: all var(--transition-normal) !important;
            box-shadow: var(--shadow-sm) !important;
            cursor: pointer;
        }}
        
        .stButton>button:hover {{
            background-color: var(--primary-green-dark) !important;
            box-shadow: var(--shadow-green) !important;
            transform: translateY(-1px);
        }}
        
        .stButton>button:active {{
            transform: translateY(0);
            box-shadow: var(--shadow-sm) !important;
        }}
        
        .stButton>button:focus {{
            outline: 2px solid var(--primary-green) !important;
            outline-offset: 2px !important;
        }}

        /* Secondary Button - Light Gray */
        div[data-testid="stButton"] button[kind="secondary"] {{
            background-color: var(--bg-off-white) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: var(--radius-md) !important;
            font-weight: 600 !important;
            font-size: {base_font} !important;
            min-height: var(--touch-target-min) !important;
            padding: {spacing_md} {spacing_xl} !important;
            transition: all var(--transition-normal) !important;
        }}
        
        div[data-testid="stButton"] button[kind="secondary"]:hover {{
            background-color: var(--bg-light-gray) !important;
            border-color: var(--border-color-dark) !important;
        }}

        /* ===== CARD STYLES ===== */
        
        /* Standard White Card with Subtle Shadow */
        .cv-card {{
            background: var(--bg-white);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: var(--spacing-xl);
            margin-bottom: var(--spacing-lg);
            box-shadow: var(--shadow-md);
            transition: box-shadow var(--transition-normal);
        }}
        
        .cv-card:hover {{
            box-shadow: var(--shadow-lg);
        }}

        /* Soft Sage Green Card - Highlighted Sections */
        .cv-card-sage {{
            background: var(--sage-bg);
            border: 1px solid var(--sage-border);
            border-radius: var(--radius-lg);
            padding: var(--spacing-xl);
            margin-bottom: var(--spacing-lg);
        }}
        
        .cv-card-sage h3 {{
            color: var(--primary-green) !important;
        }}

        /* ===== INPUT FIELD STYLES ===== */
        
        /* Text Input, Textarea, Select, Number Input */
        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox select,
        .stNumberInput input,
        .stNumberInput div[data-baseweb="input"],
        .stNumberInput div[data-baseweb="base-input"],
        [data-testid="stNumberInput"] div[data-baseweb="input"],
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        input[type="number"],
        input {{
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }}

        [data-testid="stTextInputRootElement"] button[aria-label="Show password text"],
        [data-testid="stTextInputRootElement"] button[aria-label="Hide password text"] {{
            color: #526477 !important;
            opacity: 1 !important;
            background: transparent !important;
        }}

        [data-testid="stTextInputRootElement"] button[aria-label="Show password text"] svg,
        [data-testid="stTextInputRootElement"] button[aria-label="Hide password text"] svg {{
            fill: #526477 !important;
            color: #526477 !important;
            opacity: 1 !important;
        }}

        /* Number Input +/- step buttons */
        .stNumberInput button,
        [data-testid="stNumberInput"] button,
        [data-testid="stNumberInput"] button * {{
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            border: none !important;
        }}

        /* Force black text for body elements, widgets, labels, markdown, inputs, expanders, tabs, menus, listboxes, and dialogs */
        .stApp p,
        .stApp label,
        .stApp [data-testid="stWidgetLabel"],
        .stApp [data-testid="stWidgetLabel"] *,
        .stApp [data-testid="stMarkdownContainer"] p,
        .stApp [data-testid="stMarkdownContainer"] span,
        .stApp [data-testid="stMarkdownContainer"] li,
        .stApp [data-testid="stCaptionContainer"] *,
        .stApp [data-baseweb="select"] *,
        .stApp [data-baseweb="popover"] *,
        .stApp [data-baseweb="menu"] *,
        .stApp [data-baseweb="tab"] *,
        .stApp [data-testid="stExpander"] summary *,
        .stApp [data-testid="stExpander"] details *,
        .stApp [data-testid="stPopoverBody"] *,
        .stApp input,
        .stApp textarea,
        .stApp select,
        body [role="listbox"] *,
        body [role="option"] * {{
            color: #0f172a !important;
        }}

        /* Fix File Uploader (Dropzone, Browse & Upload Button) */
        [data-testid="stFileUploaderDropzone"],
        section[data-testid="stFileUploaderDropzone"] {{
            background-color: #ffffff !important;
            border: 2px dashed #cbd5e1 !important;
            border-radius: 12px !important;
        }}

        [data-testid="stFileUploaderDropzone"] button,
        [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
        [data-testid="stFileUploaderDropzone"] button *,
        [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] * {{
            background-color: #166534 !important;
            color: #ffffff !important;
            border: 1px solid #166534 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}

        [data-testid="stFileUploaderDropzone"] label,
        [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stFileUploaderDropzone"] div,
        [data-testid="stFileUploaderDropzone"] small {{
            color: #0f172a !important;
        }}

        /* Fix Popover Buttons */
        [data-testid="stPopover"] button,
        [data-testid="stPopover"] button * {{
            background-color: #166534 !important;
            color: #ffffff !important;
            border: 1px solid #166534 !important;
            font-weight: 600 !important;
        }}

        /* Fix Streamlit Toggle Switches (Elderly Mode Toggle) */
        [data-testid="stToggle"] label,
        [data-testid="stToggle"] label * {{
            color: #0f172a !important;
            font-weight: 600 !important;
        }}

        [data-testid="stToggle"] [data-baseweb="switch"] > div {{
            background-color: #111827 !important;
            border: 1px solid #111827 !important;
        }}

        [data-testid="stToggle"] [data-baseweb="switch"] input:checked + div,
        [data-testid="stToggle"] [data-baseweb="switch"]:has(input:checked) > div {{
            background-color: #000000 !important;
            border-color: #000000 !important;
        }}

        [data-testid="stToggle"] [data-baseweb="switch"] div > div {{
            background-color: #ffffff !important;
            border: 1px solid #d1d5db !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.24) !important;
        }}

        [data-testid="stToggle"] [data-testid="stTooltipIcon"],
        [data-testid="stToggle"] [data-testid="stTooltipIcon"] svg {{
            color: #526477 !important;
            fill: #526477 !important;
            opacity: 1 !important;
        }}

        /* Preserve white text for primary green filled buttons and brand badges */
        .stApp .stButton > button[kind="primary"],
        .stApp .stButton > button[type="submit"],
        .stApp button[kind="primary"] *,
        .stApp .cv-brand-mark * {{
            color: #ffffff !important;
        }}

        /* Background colors for dropdowns, popovers, expanders, listboxes */
        .stApp div[data-baseweb="select"] > div,
        .stApp [data-testid="stExpander"] summary,
        .stApp [data-testid="stExpander"] details > div,
        .stApp [data-testid="stPopoverBody"],
        body [role="listbox"],
        body [role="option"] {{
            background-color: #ffffff !important;
        }}
        
        /* Input Focus State */
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus,
        .stSelectbox>div>div>select:focus {{
            border-color: var(--border-focus) !important;
            outline: 2px solid rgba(22, 101, 52, 0.1) !important;
            outline-offset: 0 !important;
            box-shadow: 0 0 0 3px rgba(22, 101, 52, 0.05) !important;
        }}
        
        /* Input Placeholder */
        .stTextInput>div>div>input::placeholder,
        .stTextArea>div>div>textarea::placeholder {{
            color: var(--text-muted) !important;
        }}

        /* ===== BADGE & PILL STYLES ===== */
        
        /* Medicine Status: Taken (Green) */
        .badge-taken {{ 
            background: var(--status-success-bg); 
            color: var(--status-success-text); 
            padding: {spacing_xs} {spacing_md}; 
            border-radius: var(--radius-full); 
            font-weight: 600; 
            font-size: {tiny_text};
            display: inline-block;
            white-space: nowrap;
        }}
        
        /* Medicine Status: Pending (Yellow) */
        .badge-pending {{ 
            background: var(--status-warning-bg); 
            color: var(--status-warning-text); 
            padding: {spacing_xs} {spacing_md}; 
            border-radius: var(--radius-full); 
            font-weight: 600; 
            font-size: {tiny_text};
            display: inline-block;
            white-space: nowrap;
        }}
        
        /* Medicine Status: Skipped (Red) */
        .badge-skipped {{ 
            background: var(--status-error-bg); 
            color: var(--status-error-text); 
            padding: {spacing_xs} {spacing_md}; 
            border-radius: var(--radius-full); 
            font-weight: 600; 
            font-size: {tiny_text};
            display: inline-block;
            white-space: nowrap;
        }}
        
        /* Info Badge (Blue) */
        .badge-info {{ 
            background: var(--status-info-bg); 
            color: var(--status-info-text); 
            padding: {spacing_xs} {spacing_md}; 
            border-radius: var(--radius-full); 
            font-weight: 600; 
            font-size: {tiny_text};
            display: inline-block;
            white-space: nowrap;
        }}

        /* ===== VOICE ASSISTANT BOX ===== */
        .siri-mic-box {{
            background: var(--bg-white);
            border: 2px solid var(--sage-border);
            border-radius: var(--radius-xl);
            padding: var(--spacing-xl);
            text-align: center;
            box-shadow: var(--shadow-md);
        }}

        /* ===== RESPONSIVE BREAKPOINTS ===== */
        
        /* Mobile: 320px - 640px (Base styles above) */
        
        /* Large Mobile: 640px+ */
        @media (min-width: 640px) {{
            .cv-card, .cv-card-sage {{
                padding: var(--spacing-2xl);
            }}
        }}
        
        /* Tablet: 768px+ */
        @media (min-width: 768px) {{
            html, body {{
                font-size: {base_font};
            }}
            
            .cv-card, .cv-card-sage {{
                padding: var(--spacing-xl);
            }}
        }}
        
        /* Desktop: 1024px+ */
        @media (min-width: 1024px) {{
            .cv-card:hover {{
                box-shadow: var(--shadow-xl);
            }}
        }}
        
        /* Large Desktop: 1280px+ */
        @media (min-width: 1280px) {{
            /* Additional spacing for large screens */
        }}

        /* ===== ELDERLY MODE ADJUSTMENTS ===== */
        /* Applied when elderly_mode is enabled */
        /* - Font size +33% (implemented via variables above) */
        /* - Touch targets 48px minimum (implemented via variables above) */
        /* - Line height 1.7 for better readability */

        /* ===== WCAG 2.1 LEVEL AA COMPLIANCE ===== */
        /* Color contrast ratios:
         * - Text on white (#0f172a on #ffffff): 16.8:1 ✓
         * - Primary green buttons (#ffffff on #166534): 4.7:1 ✓
         * - Secondary text (#475569 on #ffffff): 9.1:1 ✓
         * - Badge text meets 4.5:1 minimum ✓
         * - Touch targets: 44px standard, 48px elderly mode ✓
         * - Focus indicators: 2px outline with offset ✓
         */

        /* ===== UTILITY CLASSES ===== */
        
        /* Hide Streamlit Branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        
        /* Spacing Utilities */
        .mb-sm {{ margin-bottom: var(--spacing-sm) !important; }}
        .mb-md {{ margin-bottom: var(--spacing-md) !important; }}
        .mb-lg {{ margin-bottom: var(--spacing-lg) !important; }}
        .mb-xl {{ margin-bottom: var(--spacing-xl) !important; }}
        
        .mt-sm {{ margin-top: var(--spacing-sm) !important; }}
        .mt-md {{ margin-top: var(--spacing-md) !important; }}
        .mt-lg {{ margin-top: var(--spacing-lg) !important; }}
        .mt-xl {{ margin-top: var(--spacing-xl) !important; }}
        
        /* Text Utilities */
        .text-muted {{ color: var(--text-tertiary) !important; }}
        .text-small {{ font-size: {small_text} !important; }}
        .text-center {{ text-align: center !important; }}
        
        /* Flex Utilities */
        .flex {{ display: flex !important; }}
        .flex-center {{ display: flex; align-items: center; justify-content: center; }}
        .gap-sm {{ gap: var(--spacing-sm); }}
        .gap-md {{ gap: var(--spacing-md); }}
        .gap-lg {{ gap: var(--spacing-lg); }}
        
        </style>
    """, unsafe_allow_html=True)

apply_custom_css()

# Handle User Voice or Text Query
def process_user_query(text):
    if not text or text.startswith("ERROR_"):
        if text == "ERROR_NOT_UNDERSTOOD":
            err = "నాకు సరిగ్గా వినపడలేదు. దయచేసి మళ్ళీ మాట్లాడండి." if st.session_state.lang_code == "te-IN" else "I couldn't hear clearly. Please speak again."
            st.warning(err)
            st.session_state.active_audio_html = generate_audio_player(err, st.session_state.lang_code)
            st.session_state.latest_spoken_reply = err
        return

    text_lower = text.lower()
    health_reading = ai.extract_voice_health_reading(text)
    explicit_health_save = bool(re.search(r'\b(save|record|log)\b', text_lower)) or any(
        phrase in text_lower for phrase in ["సేవ్", "నమోదు", "దాచు", "చేసుకో", "చేయండి"]
    )

    if st.session_state.get("pending_health_save") and not health_reading:
        pending = st.session_state.pending_health_save
        if re.search(r'\b(cancel|discard|ignore|not now)\b', text_lower) or any(
            phrase in text_lower for phrase in ["క్యాన్సిల్", "వదిలివేయండి"]
        ):
            st.session_state.pending_health_save = None
            spoken_reply = "Health reading cancelled." if st.session_state.lang_code != "te-IN" else "ఆరోగ్య రీడింగ్ రద్దు చేయబడింది."
            st.session_state.messages.append({"role": "assistant", "content": spoken_reply})
            st.session_state.latest_spoken_reply = spoken_reply
            st.session_state.latest_reply_nonce = str(time.time_ns())
            st.session_state.active_audio_html = generate_audio_player(spoken_reply, st.session_state.lang_code)
            return

        if pending.get("awaiting_timing"):
            meal_timing = ai.extract_voice_sugar_timing(text)
            if not meal_timing:
                spoken_reply = "Was this reading before food or after food?" if st.session_state.lang_code != "te-IN" else "ఈ రీడింగ్ భోజనానికి ముందు తీసుకున్నదా, తర్వాత తీసుకున్నదా?"
                st.session_state.latest_spoken_reply = spoken_reply
                st.session_state.latest_reply_nonce = str(time.time_ns())
                st.session_state.active_audio_html = generate_audio_player(spoken_reply, st.session_state.lang_code)
                return

            db.add_health_metric(
                st.session_state.user["id"], "Blood Sugar", pending["value"], "mg/dL",
                status="Normal", notes=meal_timing,
            )
            st.session_state.pending_health_save = None
            spoken_reply = (
                f"మీ రక్తంలో చక్కెర {pending['value']} mg/dL ({meal_timing}) గా Health లో సేవ్ చేశాను."
                if st.session_state.lang_code == "te-IN"
                else f"Saved your Blood Sugar as {pending['value']} mg/dL, {meal_timing.lower()}, in Health."
            )
            st.session_state.messages.append({"role": "assistant", "content": spoken_reply})
            st.session_state.latest_spoken_reply = spoken_reply
            st.session_state.latest_reply_nonce = str(time.time_ns())
            st.session_state.active_audio_html = generate_audio_player(spoken_reply, st.session_state.lang_code)
            return

        if re.search(r'\b(save it|save this|record it|confirm save|yes|confirm|save this reading)\b', text_lower) or any(
            phrase in text_lower for phrase in ["సేవ్", "నమోదు", "అవును", "చేసుకో", "చేయండి"]
        ):
            metric_name = pending["metric"]
            value = pending["value"]
            meal_timing = ai.extract_voice_sugar_timing(text) or pending.get("meal_timing")
            if metric_name == "Blood Sugar" and not meal_timing:
                pending["awaiting_timing"] = True
                spoken_reply = "Was this reading before food or after food?" if st.session_state.lang_code != "te-IN" else "ఈ రీడింగ్ భోజనానికి ముందు తీసుకున్నదా, తర్వాత తీసుకున్నదా?"
                st.session_state.latest_spoken_reply = spoken_reply
                st.session_state.latest_reply_nonce = str(time.time_ns())
                st.session_state.active_audio_html = generate_audio_player(spoken_reply, st.session_state.lang_code)
                return
            db.add_health_metric(
                st.session_state.user["id"], metric_name, value,
                "mmHg" if metric_name == "Blood Pressure" else "mg/dL",
                status="Normal",
                notes=meal_timing if metric_name == "Blood Sugar" else "Added via Voice Assistant",
            )
            st.session_state.pending_health_save = None
            spoken_reply = (
                f"మీ {metric_name.lower()} {value} గా Health లో సేవ్ చేశాను."
                if st.session_state.lang_code == "te-IN" else f"Saved your {metric_name} as {value} in Health."
            )
            st.session_state.messages.append({"role": "assistant", "content": spoken_reply})
            st.session_state.latest_spoken_reply = spoken_reply
            st.session_state.latest_reply_nonce = str(time.time_ns())
            st.session_state.active_audio_html = generate_audio_player(spoken_reply, st.session_state.lang_code)
            return

    if not st.session_state.user:
        return
    user_id = st.session_state.user["id"]
    user_name = st.session_state.user["name"]

    if health_reading and explicit_health_save:
        metric_name = health_reading["metric"]
        value = health_reading["value"]
        unit = "mmHg" if metric_name == "Blood Pressure" else "mg/dL"
        meal_timing = ai.extract_voice_sugar_timing(text)
        if metric_name == "Blood Sugar" and not meal_timing:
            st.session_state.pending_health_save = {
                **health_reading,
                "awaiting_timing": True,
            }
            spoken_reply = "Was this reading before food or after food?" if st.session_state.lang_code != "te-IN" else "ఈ రీడింగ్ భోజనానికి ముందు తీసుకున్నదా, తర్వాత తీసుకున్నదా?"
            st.session_state.messages.extend([
                {"role": "user", "content": text},
                {"role": "assistant", "content": spoken_reply},
            ])
            st.session_state.latest_user_query = text
            st.session_state.latest_spoken_reply = spoken_reply
            st.session_state.latest_reply_nonce = str(time.time_ns())
            st.session_state.active_audio_html = ""
            return
        db.add_health_metric(
            user_id, metric_name, value, unit, status="Normal",
            notes=meal_timing if metric_name == "Blood Sugar" else "Added via Voice Assistant",
        )
        st.session_state.pending_health_save = None
        spoken_reply = (
            f"మీ {metric_name.lower()} {value} గా నమోదైంది."
            if st.session_state.lang_code == "te-IN" else f"Saved your {metric_name} as {value}."
        )
        st.session_state.messages.extend([
            {"role": "user", "content": text},
            {"role": "assistant", "content": spoken_reply},
        ])
        st.session_state.latest_user_query = text
        st.session_state.latest_spoken_reply = spoken_reply
        st.session_state.latest_reply_nonce = str(time.time_ns())
        st.session_state.active_audio_html = ""
        return

    if health_reading:
        st.session_state.pending_health_save = {
            **health_reading,
            **({"meal_timing": ai.extract_voice_sugar_timing(text)} if health_reading["metric"] == "Blood Sugar" else {}),
        }

    st.session_state.messages.append({"role": "user", "content": text})

    spoken_reply, nav_page = ai.process_voice_assistant_query(
        text,
        user_id,
        user_name,
        st.session_state.lang_code,
        st.session_state.get("dietary_preference", "Vegetarian"),
    )

    st.session_state.messages.append({"role": "assistant", "content": spoken_reply})
    st.session_state.active_audio_html = ""
    st.session_state.latest_user_query = text
    st.session_state.latest_spoken_reply = spoken_reply
    st.session_state.latest_reply_nonce = str(time.time_ns())

    if nav_page == "DietRefreshed":
        diet_date = datetime.date.today()
        refreshed_health = db.get_health_metrics_for_date(user_id, diet_date.isoformat())
        diet_preference = st.session_state.get("dietary_preference", "Vegetarian")
        st.session_state["diet_plan_today"] = db.get_all_diet_plans(user_id)
        st.session_state["diet_plan_today_key"] = json.dumps({
            "date": diet_date.isoformat(),
            "dietary_preference": diet_preference,
            "metrics": {
                name: {
                    "value": reading.get("value"),
                    "unit": reading.get("unit"),
                    "recorded_date": reading.get("recorded_date"),
                }
                for name, reading in refreshed_health.items()
            },
        }, sort_keys=True)
        st.session_state.current_page = "Diet"

    navigation_phrases = ("open ", "go to ", "navigate to", "take me to", "show schedule", "medicine schedule")
    if nav_page and any(phrase in text.lower() for phrase in navigation_phrases):
        st.session_state.current_page = nav_page

# Handle a medicine reminder notification opened from a browser notification.
if "due_med_id" in st.query_params:
    try:
        med_id = int(st.query_params.get("due_med_id"))
        med_time = st.query_params.get("due_med_time", "")
        current_user = st.session_state.get("user")
        medicine = db.get_medicine_by_id(current_user["id"], med_id) if current_user else None
        scheduled_times = {
            display_time for _, display_time in reminder_worker.parse_schedule_times(
                medicine.get("time_slot", "") if medicine else ""
            )
        }
        if medicine and med_time in scheduled_times:
            st.session_state.active_med_reminder = {
                "id": med_id,
                "name": medicine["name"],
                "dosage": medicine["dosage"],
                "before_after_food": medicine.get("before_after_food", ""),
                "time_slot": med_time,
            }
    except Exception:
        pass
    if "reminder_action" not in st.query_params:
        for parameter in ("due_med_id", "due_med_time"):
            if parameter in st.query_params:
                del st.query_params[parameter]

if "reminder_action" in st.query_params:
    action = st.query_params.get("reminder_action", "").lower()
    current_user = st.session_state.get("user")
    try:
        med_id = int(st.query_params.get("due_med_id", ""))
        scheduled_time = st.query_params.get("due_med_time", "")
        medicine = db.get_medicine_by_id(current_user["id"], med_id) if current_user else None
        scheduled_times = {
            display_time for _, display_time in reminder_worker.parse_schedule_times(
                medicine.get("time_slot", "") if medicine else ""
            )
        }
        if medicine and scheduled_time in scheduled_times and action in {"take", "snooze", "skip"}:
            now = datetime.datetime.now()
            action_status = {"take": "Taken", "snooze": "Snoozed", "skip": "Skipped"}[action]
            snooze_until = (now + datetime.timedelta(minutes=5)).isoformat(timespec="seconds") if action == "snooze" else None
            db.log_medicine_action(
                current_user["id"], med_id, medicine["name"], medicine["dosage"],
                action_status, scheduled_time, now.strftime("%I:%M %p"),
                now.strftime("%Y-%m-%d"), snooze_until=snooze_until,
            )
            st.session_state.active_med_reminder = None
            st.session_state.active_audio_html = generate_audio_player(
                f"{medicine['name']} recorded as {action_status.lower()}.",
                st.session_state.lang_code,
            )
    except (TypeError, ValueError):
        pass
    for parameter in ("reminder_action", "due_med_id", "due_med_time"):
        if parameter in st.query_params:
            del st.query_params[parameter]

# Render queued speech after microphone transcripts have been processed.
if st.session_state.active_audio_html:
    if st.session_state.view in {"app", "onboarding"}:
        st.components.v1.html(st.session_state.active_audio_html, height=58)
    st.session_state.active_audio_html = ""

if st.session_state.web_notif_html:
    st.components.v1.html(st.session_state.web_notif_html, height=0)
    st.session_state.web_notif_html = ""

def render_browser_voice_component(key_prefix="v_comp"):
    render_session_voice_component(key_prefix)


def render_session_voice_component(key_prefix="va"):
    reply_text = st.session_state.get("latest_spoken_reply", "")
    reply_audio = ""
    if reply_text:
        reply_audio = generate_offline_tts_data(
            clean_speech_text(reply_text), st.session_state.lang_code,
            st.session_state.get("voice_gender", "Female Voice"),
        )
    event = voice_mic_component(
        lang_code=st.session_state.lang_code,
        user_id=st.session_state.user["id"] if st.session_state.user else "",
        user_text=st.session_state.get("latest_user_query", ""),
        reply_text=reply_text,
        reply_audio=reply_audio,
        reply_nonce=st.session_state.get("latest_reply_nonce", ""),
        voice_gender=st.session_state.get("voice_gender", "Female Voice"),
        key=key_prefix,
        default=None,
    )
    if isinstance(event, dict) and event.get("text"):
        event_id = event.get("event_id")
        if event_id and event_id != st.session_state.get("last_voice_event_id"):
            st.session_state.last_voice_event_id = event_id
            process_user_query(event["text"])
            st.rerun()


def render_medicine_reminder_scheduler(medicines, user_id, user_name="User", show_controls=False):
    if show_controls:
        render_push_subscription_control(user_id)

def render_push_subscription_control(user_id):
    is_te = st.session_state.lang_code == "te-IN"
    try:
        public_key = reminder_worker.get_vapid_public_key()
    except Exception:
        public_key = ""
    event = push_setup_component(
        public_key=public_key,
        lang_code=st.session_state.lang_code,
        service_worker_url=os.getenv(
            "CAREVOICE_SERVICE_WORKER_URL", "/app/static/carevoice-sw.js"
        ),
        key=f"push-setup-{user_id}",
        default=None,
    )
    if isinstance(event, dict) and event.get("subscription"):
        event_id = event.get("event_id")
        if event_id and event_id != st.session_state.get("last_push_event_id"):
            try:
                db.save_push_subscription(user_id, event["subscription"])
                st.session_state.last_push_event_id = event_id
                st.session_state.push_setup_message = (
                    "బ్రౌజర్ మందుల నోటిఫికేషన్లు ప్రారంభించబడ్డాయి."
                    if is_te else "Browser medicine notifications are enabled."
                )
            except ValueError as error:
                st.session_state.push_setup_message = str(error)


@st.dialog("Medicine Reminder / మందుల జ్ఞాపిక", dismissible=False, width="large")
def show_medicine_reminder_popup(rem):
    user = st.session_state.get("user")
    if not user:
        return
    user_id = user["id"]
    user_name = user["name"]
    is_te = st.session_state.lang_code.lower().startswith("te")
    m_id = rem["id"]
    m_name = rem["name"]
    display_m_name = display_medicine_name(m_name, is_te)
    m_dos = rem["dosage"]
    m_food = rem.get("before_after_food", "")
    m_time = rem.get("time_slot", "")
    now_time = datetime.datetime.now().strftime("%I:%M %p")
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    st.markdown("### 🔔 మందుల జ్ఞాపిక" if is_te else "### 🔔 Medicine Reminder")
    st.markdown(
        f"**{user_name}, {display_m_name} {m_dos} తీసుకునే సమయం అయింది.**"
        if is_te else f"**{user_name}, it is time to take {m_name} {m_dos}.**"
    )
    st.caption(
        f"షెడ్యూల్ సమయం: {m_time}" + (f" · {m_food}" if m_food else "")
        if is_te else f"Scheduled: {m_time}" + (f" · {m_food}" if m_food else "")
    )

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        take_label = "తీసుకున్నాను" if is_te else "Taken"
        if st.button(f"✅ {take_label}", key=f"notif_take_{m_id}", type="primary", use_container_width=True):
            db.log_medicine_action(user_id, m_id, m_name, m_dos, "Taken", m_time, now_time, today_date)
            st.session_state.active_med_reminder = None
            msg = f"{display_m_name} తీసుకున్నట్లు నమోదైంది." if is_te else f"{user_name}, recorded {m_name} as taken."
            st.session_state.active_audio_html = generate_audio_player(msg, st.session_state.lang_code)
            st.rerun()

    with btn_col2:
        snooze_label = "5 నిమిషాలు వాయిదా" if is_te else "Snooze 5m"
        if st.button(f"⏰ {snooze_label}", key=f"notif_snooze_{m_id}", type="secondary", use_container_width=True):
            snooze_until = (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat(timespec="seconds")
            db.log_medicine_action(user_id, m_id, m_name, m_dos, "Snoozed", m_time, now_time, today_date, snooze_until=snooze_until)
            st.session_state.active_med_reminder = None
            msg = "రిమైండర్ 5 నిమిషాలు వాయిదా వేయబడింది." if is_te else f"{user_name}, reminder snoozed for 5 minutes."
            st.session_state.active_audio_html = generate_audio_player(msg, st.session_state.lang_code)
            st.rerun()


@st.fragment(run_every="5s")
def render_active_medicine_reminder_banner():
    current_user = st.session_state.get("user")
    if current_user and not st.session_state.get("active_med_reminder"):
        reminder_now = datetime.datetime.now()
        reminder_date = reminder_now.strftime("%Y-%m-%d")
        due_reminders = reminder_worker.get_due_in_app_reminders(
            db.get_active_reminder_schedules(),
            db.get_medicine_logs_for_date(current_user["id"], reminder_date),
            current_user["id"],
            current_user["name"],
            st.session_state.lang_code,
            reminder_now,
        )
        if due_reminders:
            due = due_reminders[0]
            medicine = db.get_medicine_by_id(current_user["id"], due["medicine_id"])
            if medicine:
                st.session_state.active_med_reminder = {
                    "id": medicine["id"],
                    "name": medicine["name"],
                    "dosage": medicine["dosage"],
                    "before_after_food": medicine.get("before_after_food", ""),
                    "time_slot": due["scheduled_time"],
                }
    if st.session_state.get("active_med_reminder"):
        show_medicine_reminder_popup(st.session_state.active_med_reminder)

def render_voice_assistant_box(key_prefix="va"):
    is_te = st.session_state.lang_code == "te-IN"
    render_session_voice_component(key_prefix=key_prefix)

    if st.session_state.get("latest_spoken_reply"):
        reply_label = "CareVoice సమాధానం" if is_te else "CareVoice"
        st.markdown(f"**{reply_label}:** {st.session_state.latest_spoken_reply}")

# -----------------------------------------------------------------------------
# 1. LANDING PAGE VIEW
# -----------------------------------------------------------------------------
def render_landing_page():
    is_te = str(st.session_state.get("lang_code", "en-IN")).lower().startswith("te")
    landing_markup = textwrap.dedent("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        .stApp:has(.cv-landing), [data-testid="stAppViewContainer"]:has(.cv-landing) {background:#fff !important; color:#142536 !important;}
        .block-container:has(.cv-landing) {max-width:100%; padding:0 0 2rem; background:#fff !important;}
        .cv-landing {--green:#08784f; --green-dark:#075d40; --mint:#eaf6f0; --ink:#142536; --muted:#536477; color:var(--ink); background:#fff;}
        .cv-landing * {box-sizing:border-box;}
        .cv-topbar {max-width:1510px; min-height:78px; padding:12px 28px; margin:auto; display:flex; align-items:center; justify-content:space-between; gap:24px; border-bottom:1px solid #e8eeeb;}
        .cv-brand {display:flex; align-items:center; gap:12px; text-decoration:none; color:var(--ink); white-space:nowrap;}
        .cv-brand-mark {width:48px; height:48px; display:grid; place-items:center; border-radius:13px; color:white; background:var(--green); box-shadow:0 5px 12px #08784f22;}
        .cv-brand-name {font-size:25px; font-weight:750; letter-spacing:0;}
        .cv-brand-name span {color:var(--green);}
        .cv-nav {display:flex; align-items:center; justify-content:center; gap:clamp(18px,3vw,48px); flex:1;}
        .cv-nav a {color:#26384a; text-decoration:none; font-size:15px; font-weight:600; white-space:nowrap; transition:color .15s ease;}
        .cv-nav a:hover {color:var(--green);}
        .cv-top-actions {display:flex; align-items:center; gap:12px; white-space:nowrap;}
        .cv-top-actions form,.cv-hero-actions form {margin:0;}
        .cv-top-actions button,.cv-hero-actions button {min-height:46px; display:inline-flex; align-items:center; justify-content:center; padding:0 21px; border:1px solid var(--green); border-radius:14px; color:var(--green); background:#fff; font-family:inherit; font-size:14px; font-weight:700; cursor:pointer; transition:transform .15s ease,background .15s ease;}
        .cv-top-actions button:hover,.cv-hero-actions button:hover {transform:translateY(-1px); background:#f2faf5;}
        .cv-top-actions button.cv-action-primary,.cv-hero-actions button.cv-action-primary {color:#fff; background:var(--green);}
        .cv-top-actions button.cv-action-primary:hover,.cv-hero-actions button.cv-action-primary:hover {background:var(--green-dark);}
        .cv-hero {max-width:1510px; min-height:590px; margin:auto; padding:38px 28px 28px; display:grid; grid-template-columns:minmax(390px,.95fr) minmax(560px,1.05fr); align-items:center; gap:20px; overflow:hidden;}
        .cv-hero-copy {position:relative; z-index:2; padding:16px 0 26px;}
        .cv-eyebrow {display:inline-flex; align-items:center; gap:8px; padding:10px 17px; margin-bottom:20px; border:1px solid #dcebe2; border-radius:999px; background:#fff; color:var(--green); font-size:13px; font-weight:750; letter-spacing:1px;}
        .cv-hero h1 {max-width:700px; margin:0 0 17px; color:#152536; font-size:clamp(48px,5vw,70px); line-height:1.05; font-weight:780; letter-spacing:0;}
        .cv-hero h1 span {color:#0d9662;}
        .cv-hero-copy>p {max-width:600px; margin:0; color:var(--muted); font-size:20px; line-height:1.55;}
        .cv-hero-actions {display:flex; flex-wrap:wrap; align-items:center; gap:14px; margin-top:24px;}
        .cv-hero-actions button {min-height:54px; padding:0 25px; border-radius:15px; font-size:16px;}
        .cv-trust {display:flex; align-items:center; gap:12px; margin-top:25px; color:#27384a; font-size:14px; line-height:1.5;}
        .cv-trust-mark {width:42px; height:42px; flex:0 0 42px; display:grid; place-items:center; border:1px solid #dcebe2; border-radius:50%; color:var(--green); background:#fff;}
        .cv-visual {height:535px; min-width:0; position:relative; isolation:isolate;}
        .cv-photo {position:absolute; right:0; bottom:0; width:78%; height:94%; border-radius:46% 46% 0 0 / 36% 36% 0 0; overflow:hidden; background:#fff;}
        .cv-photo img {width:100%; height:100%; display:block; object-fit:cover; object-position:center 38%;}
        .cv-photo:after {content:""; position:absolute; inset:0; background:transparent;}
        .cv-phone {position:absolute; z-index:2; left:21%; bottom:2%; width:246px; height:474px; padding:9px; border:3px solid #101413; border-radius:38px; background:#111; box-shadow:0 20px 45px #14253640;}
        .cv-phone-screen {height:100%; position:relative; overflow:hidden; padding:24px 10px 8px; border-radius:28px; background:#fff;}
        .cv-phone-island {position:absolute; top:8px; left:50%; width:83px; height:20px; transform:translateX(-50%); border-radius:99px; background:#0b0c0d;}
        .cv-phone-greeting {margin:5px 0 7px; color:#263747; font-size:9px; line-height:1.3;}
        .cv-phone-greeting strong {display:block; color:var(--green); font-size:14px;}
        .cv-phone-title {display:flex; justify-content:space-between; margin:0 0 5px; font-size:9px; font-weight:700;}
        .cv-phone-title span {color:var(--green);}
        .cv-med {min-height:54px; padding:6px 7px; margin-bottom:4px; border:1px solid #edf0f1; border-radius:7px; color:#526171; font-size:8px; line-height:1.2;}
        .cv-med strong {display:block; margin-top:2px; color:#152536; font-size:9px;}
        .cv-med-status {float:right; color:var(--green); font-size:8px; font-weight:700;}
        .cv-phone-nav {position:absolute; right:0; bottom:0; left:0; display:flex; justify-content:space-around; padding:7px 2px 4px; border-top:1px solid #edf0f1; color:#697989; font-size:7px; line-height:1.05;}
        .cv-phone-nav svg {width:10px; height:10px; margin-bottom:0;}
        .cv-phone-nav span:first-child {color:var(--green); font-weight:700;}
        .cv-float {position:absolute; z-index:3; display:flex; align-items:center; gap:12px; padding:14px 16px; border:1px solid #eff3f0; border-radius:17px; background:#ffffffed; box-shadow:0 12px 30px #20372a16; color:#152536;}
        .cv-float-voice {left:0; top:31%; width:195px; flex-direction:column; text-align:center; gap:9px;}
        .cv-float-reminder {right:1%; top:10%; width:223px;}
        .cv-float strong {display:block; font-size:13px; line-height:1.4;}
        .cv-float small {display:block; margin-top:3px; color:#657487; font-size:11px; line-height:1.4;}
        .cv-float-icon {width:44px; height:44px; flex:0 0 44px; display:grid; place-items:center; border:1px solid #dcebe2; border-radius:50%; color:var(--green); background:#fff;}
        .cv-section {max-width:1260px; margin:auto; padding:86px 28px; scroll-margin-top:24px;}
        .cv-section-kicker {margin:0 0 10px; color:var(--green); font-size:12px; font-weight:750; letter-spacing:1px; text-transform:uppercase;}
        .cv-section h2 {max-width:720px; margin:0 0 14px; color:#152536; font-size:38px; line-height:1.18; letter-spacing:0;}
        .cv-section-intro {max-width:690px; margin:0; color:var(--muted); font-size:17px; line-height:1.6;}
        .cv-steps {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:28px; margin-top:38px;}
        .cv-step {padding:24px 0; border-top:2px solid #cce6d8;}
        .cv-step-number {color:var(--green); font-size:13px; font-weight:750;}
        .cv-step h3 {margin:14px 0 8px; color:#152536; font-size:20px;}
        .cv-step p {margin:0; color:var(--muted); font-size:15px; line-height:1.6;}
        .cv-pricing {display:flex; align-items:center; justify-content:space-between; gap:24px; padding-top:30px; border-top:1px solid #e5ece8;}
        .cv-pricing p {max-width:720px; color:var(--muted); font-size:15px; line-height:1.6;}
        .cv-footer {padding:25px 28px; border-top:1px solid #e8eeeb; color:#657487; text-align:center; font-size:13px;}
        @media (max-width:1050px) {
            .cv-topbar {padding-right:20px; padding-left:20px;}
            .cv-nav {gap:16px;}
            .cv-nav a {font-size:13px;}
            .cv-hero {grid-template-columns:minmax(330px,.9fr) minmax(430px,1.1fr); padding-right:20px; padding-left:20px;}
            .cv-phone {left:19%; width:220px;}
            .cv-float-voice {width:165px;}
            .cv-float-reminder {width:195px;}
            .cv-feature {gap:11px; padding:0 15px;}
            .cv-feature-icon {width:52px; height:52px; flex-basis:52px;}
        }
        @media (max-width:760px) {
            .cv-topbar {min-height:68px; padding:10px 18px; flex-wrap:wrap; gap:10px;}
            .cv-brand-mark {width:42px; height:42px;}
            .cv-brand-name {font-size:22px;}
            .cv-nav {order:3; flex:0 0 100%; width:100%; justify-content:flex-start; overflow-x:auto; padding:8px 0 4px;}
            .cv-nav a {font-size:13px;}
            .cv-hero {min-height:0; grid-template-columns:1fr; gap:2px; padding:40px 20px 16px;}
            .cv-hero-copy {padding:0;}
            .cv-hero h1 {font-size:clamp(43px,11vw,62px);}
            .cv-hero-copy>p {font-size:17px;}
            .cv-visual {height:480px; margin-top:8px;}
            .cv-photo {width:76%; height:91%;}
            .cv-phone {left:25%; width:220px; height:426px;}
            .cv-float-voice {left:0; top:30%; width:155px;}
            .cv-float-reminder {right:0; top:8%; width:180px;}
            .cv-feature-rail {grid-template-columns:1fr 1fr; gap:4px; padding:14px 20px;}
            .cv-feature {padding:14px 8px; border-right:0;}
            .cv-feature:first-child {padding-left:8px;}
            .cv-feature-icon {width:46px; height:46px; flex-basis:46px;}
            .cv-feature h3 {font-size:14px;}
            .cv-feature p {font-size:12px;}
            .cv-section {padding:62px 20px;}
            .cv-section h2 {font-size:31px;}
            .cv-steps {grid-template-columns:1fr; gap:8px; margin-top:25px;}
            .cv-step {padding:17px 0;}
            .cv-pricing {align-items:flex-start; flex-direction:column;}
        }
        @media (max-width:430px) {
            .cv-hero {padding-right:16px; padding-left:16px;}
            .cv-visual {height:420px;}
            .cv-phone {left:24%; width:192px; height:376px; padding:7px; border-radius:31px;}
            .cv-phone-screen {border-radius:23px; padding-right:9px; padding-left:9px;}
            .cv-float {gap:8px; padding:10px;}
            .cv-float-voice {width:132px;}
            .cv-float-reminder {width:160px;}
            .cv-float strong {font-size:11px;}
            .cv-float small {font-size:10px;}
            .cv-feature-rail {padding-right:12px; padding-left:12px;}
            .cv-feature {gap:8px; padding-right:4px; padding-left:4px;}
            .cv-feature-icon {width:40px; height:40px; flex-basis:40px;}
        }
        @media (prefers-reduced-motion:reduce) { .cv-landing * {scroll-behavior:auto!important; transition:none!important;} }
                .cv-landing {--green:#087f5b; --green-dark:#066447; --green-bright:#159a6c; --mint:#eaf7f1; --pale:#f4fbf8; --ink:#14213d; --muted:#59697b; --line:#e1ece6; width:100%; font-family:'Manrope',sans-serif; color:var(--ink); overflow:hidden;}
                .cv-landing a {color:inherit;}
                    .cv-landing header.cv-topbar,.cv-landing footer.cv-footer {visibility:visible !important;}
                .cv-topbar {max-width:1440px; min-height:76px; padding:12px 34px; border-color:var(--line);}
                .cv-brand-mark {width:46px; height:46px; border-radius:12px; background:var(--green); box-shadow:0 5px 14px #087f5b25;}
                .cv-brand-name {font-size:24px; font-weight:800;}
                .cv-nav {gap:clamp(16px,2.5vw,38px);}
                .cv-nav a {font-size:14px; font-weight:650;}
                .cv-top-actions button,.cv-hero-actions button {border-radius:12px; font-family:'Manrope',sans-serif;}
                .cv-top-actions button.cv-action-primary,.cv-hero-actions button.cv-action-primary {background:var(--green); border-color:var(--green);}
                .cv-top-actions button.cv-action-primary:hover,.cv-hero-actions button.cv-action-primary:hover {background:var(--green-dark);}
                .cv-mobile-menu {display:none; position:relative;}
                .cv-mobile-menu summary {width:44px; height:44px; display:grid; place-items:center; border:1px solid var(--line); border-radius:10px; color:var(--green); cursor:pointer; list-style:none;}
                .cv-mobile-menu summary::-webkit-details-marker {display:none;}
                .cv-mobile-menu nav {position:absolute; z-index:8; top:52px; right:0; min-width:210px; padding:9px; border:1px solid var(--line); border-radius:10px; background:white; box-shadow:0 12px 30px #14213d18;}
                .cv-mobile-menu nav a {display:block; padding:11px 12px; border-radius:7px; color:var(--ink); font-size:14px; font-weight:650; text-decoration:none;}
                .cv-mobile-menu nav a:hover {background:var(--pale); color:var(--green);}
                .cv-hero {max-width:1440px; min-height:570px; grid-template-columns:minmax(390px,.96fr) minmax(540px,1.04fr); padding:35px 34px 26px; gap:12px;}
                .cv-hero-copy {padding:8px 0 18px; animation:cv-reveal .55s ease both;}
                .cv-eyebrow {padding:9px 15px; margin-bottom:19px; border:0; background:var(--mint); color:var(--green); font-size:12px; letter-spacing:0;}
                .cv-hero h1 {max-width:620px; margin-bottom:16px; color:var(--ink); font-size:64px; line-height:1.04; font-weight:800;}
                    .cv-hero h1 {font-size:64px !important; color:var(--ink) !important;}
                .cv-hero h1 span {color:var(--green-bright);}
                    .cv-hero h1 span {color:var(--green-bright) !important;}
                    .cv-hero h1 span {color:#159a6c !important;}
                    .cv-landing .cv-hero h1 span {color:#159a6c !important;}
                .cv-hero-copy>p {max-width:530px; color:#536477; font-size:18px; line-height:1.55;}
                .cv-hero-actions {gap:14px; margin-top:23px;}
                .cv-hero-actions button {min-height:54px; padding:0 24px;}
                .cv-hero-actions>a {min-height:54px; display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:0 23px; border:1px solid #8ccab0; border-radius:12px; color:var(--green); font-size:15px; font-weight:700; text-decoration:none;}
                .cv-hero-actions>a:hover {background:var(--pale);}
                .cv-trust {margin-top:23px; color:#526276; font-size:13px;}
                .cv-trust-mark {border:0; color:var(--green); background:var(--mint);}
                .cv-trust strong {color:var(--ink); font-weight:750;}
                .cv-visual {height:518px; animation:cv-reveal .65s .08s ease both;}
                .cv-photo {right:-1%; width:78%; height:94%; border-radius:48% 48% 0 0 / 34% 34% 0 0; background:var(--mint);}
                .cv-photo img {object-position:center 40%;}
                .cv-photo:after {background:linear-gradient(90deg,#eaf7f11c,transparent 42%);}
                .cv-phone {left:19%; bottom:15%; width:210px; height:400px; border-radius:37px; box-shadow:0 24px 48px #14213d35;}
                .cv-phone-screen {padding:24px 10px 8px;}
                .cv-phone-greeting {margin:5px 0 7px;}
                .cv-phone-date {margin:2px 0 7px; font-size:8px;}
                .cv-phone-title {margin-bottom:5px;}
                .cv-med {padding:6px 7px; margin-bottom:4px; border-radius:7px; background:#fff; font-size:8px; line-height:1.2;}
                .cv-med strong {margin-top:2px; font-size:9px;}
                .cv-med-status {font-size:8px;}
                .cv-phone-nav {padding:7px 2px 4px; font-size:7px; line-height:1.05;}
                .cv-phone-nav svg {width:10px; height:10px; margin-bottom:0;}
                .cv-phone-status {position:absolute; top:12px; right:16px; color:#172532; font-size:8px; font-weight:800;}
                .cv-phone-date {display:flex; justify-content:space-between; margin:3px 0 15px; color:#788694; font-size:9px;}
                .cv-float {border-color:#e9f0ec; border-radius:12px; box-shadow:0 10px 26px #20372a16;}
                .cv-float-voice {left:-2%; top:34%; width:170px;}
                .cv-float-reminder {right:0; top:9%; width:226px;}
                .cv-float-icon {border:0; background:var(--mint); color:var(--green);}
                .cv-wave {width:84px; height:19px; display:flex; align-items:center; justify-content:center; gap:3px; margin:0 auto;}
                .cv-wave i {width:2px; height:7px; border-radius:4px; background:#57b78c;}
                .cv-wave i:nth-child(2n) {height:13px;}.cv-wave i:nth-child(3n) {height:17px;}
                .cv-section {max-width:1240px; padding:72px 34px; scroll-margin-top:24px;}
                .cv-section-kicker {margin-bottom:9px; color:var(--green); font-size:11px; letter-spacing:0;}
                .cv-section h2 {margin-bottom:12px; color:var(--ink); font-size:36px; font-weight:800; letter-spacing:0;}
                .cv-section-intro {font-size:15px;}
                .cv-steps {gap:27px; margin-top:29px;}
                .cv-step {padding:19px 0 8px; border-top:1px solid #cfe5d8;}
                .cv-step-number {font-size:12px;}.cv-step h3 {margin:11px 0 0; font-size:16px; font-weight:750;}.cv-step p {display:none;}
                .cv-family-section {max-width:none; padding:0; background:var(--pale);}
                .cv-family-inner {max-width:1240px; min-height:390px; display:grid; grid-template-columns:1fr 1fr; align-items:center; gap:56px; padding:44px 34px; margin:auto;}
                .cv-family-photo {height:300px; overflow:hidden; border-radius:8px; background:#dceee3;}
                .cv-family-photo img {width:100%; height:100%; display:block; object-fit:cover; object-position:center 55%; transform:scale(1.1);}
                .cv-family-copy h2 {max-width:430px; margin:0 0 12px; color:var(--ink); font-size:36px; line-height:1.18; font-weight:800;}
                .cv-family-copy p {max-width:440px; margin:0; color:var(--muted); font-size:15px; line-height:1.6;}
                .cv-family-languages {display:flex; gap:9px; margin-top:19px;}
                .cv-family-languages span {padding:7px 12px; border:1px solid #c9e4d5; border-radius:7px; color:var(--green); background:white; font-size:13px; font-weight:750;}
                .cv-cta {max-width:1440px; padding:58px 34px; text-align:center;}
                .cv-cta-inner {padding:39px 22px; border:1px solid #dcece3; border-radius:8px; background:var(--pale);}
                .cv-cta h2 {margin:0 0 9px; color:var(--ink); font-size:32px; font-weight:800;}
                .cv-cta p {margin:0 auto 19px; color:var(--muted); font-size:14px; line-height:1.5;}
                .cv-cta .cv-action-primary {min-height:48px; padding:0 22px; border:1px solid var(--green); border-radius:10px; color:white; background:var(--green); font-family:'Manrope',sans-serif; font-size:14px; font-weight:750; cursor:pointer;}
                .cv-footer {max-width:1440px; display:flex; align-items:center; justify-content:space-between; gap:22px; padding:22px 34px; margin:auto; border-color:var(--line); text-align:left;}
                .cv-footer-brand {display:flex; align-items:center; gap:9px; color:var(--ink); font-size:16px; font-weight:800; white-space:nowrap;}
                .cv-footer-brand .cv-brand-mark {width:30px; height:30px; border-radius:8px;}
                .cv-footer nav {display:flex; flex-wrap:wrap; justify-content:center; gap:18px;}
                .cv-footer nav a {color:#5c6b79; font-size:12px; font-weight:650; text-decoration:none;}
                .cv-footer nav a:hover {color:var(--green);}
                .cv-copyright {color:#718091; font-size:11px; white-space:nowrap;}
                @keyframes cv-reveal {from {opacity:0; transform:translateY(12px);} to {opacity:1; transform:translateY(0);}}
                @media (max-width:1050px) {
                        .cv-topbar {padding-right:24px; padding-left:24px;}
                        .cv-nav {gap:15px;}.cv-nav a {font-size:12px;}
                        .cv-hero {grid-template-columns:minmax(330px,.92fr) minmax(430px,1.08fr); padding-right:24px; padding-left:24px;}
                        .cv-hero h1 {font-size:56px;}.cv-phone {left:19%; bottom:15%; width:200px; height:381px;}
                        .cv-float-voice {width:160px;}.cv-float-reminder {width:200px;}
                        .cv-feature-rail {padding-right:24px; padding-left:24px;}
                        .cv-family-inner {gap:36px;}
                }
                @media (max-width:820px) {
                        .cv-topbar {min-height:68px; flex-wrap:nowrap; padding:10px 20px;}
                        .cv-nav {display:none;}.cv-mobile-menu {display:block; margin-left:auto;}
                        .cv-top-actions {gap:7px;}.cv-top-actions button {min-height:42px; padding:0 13px; font-size:12px;}
                        .cv-hero {min-height:0; grid-template-columns:1fr; padding:35px 24px 15px;}
                        .cv-hero-copy {padding:0;}.cv-hero h1 {font-size:54px !important;}
                        .cv-visual {height:470px; max-width:680px; width:100%; margin:0 auto;}
                        .cv-photo {width:75%;}.cv-phone {left:33%; width:226px; height:430px;}
                                    .cv-photo {width:75%;}.cv-phone {left:33%; bottom:2%; width:226px; height:430px;}
                        .cv-float-voice {left:4%; top:35%;}.cv-float-reminder {right:2%;}
                        .cv-section {padding:60px 24px;}
                        .cv-family-inner {grid-template-columns:1fr 1fr; gap:25px; padding:36px 24px;}
                        .cv-family-photo {height:265px;}.cv-family-copy h2 {font-size:30px;}
                        .cv-footer {flex-wrap:wrap; padding:20px 24px;}
                }
                @media (max-width:560px) {
                        .cv-topbar {gap:8px; padding-right:14px; padding-left:14px;}
                        .cv-brand {gap:8px;}.cv-brand-mark {width:39px; height:39px;}.cv-brand-name {font-size:20px;}
                        .cv-top-actions form:first-child {display:none;}.cv-top-actions button {min-height:39px; padding:0 11px;}
                        .cv-mobile-menu summary {width:39px; height:39px;}
                        .cv-hero {padding:34px 18px 12px; gap:0;}.cv-eyebrow {margin-bottom:14px; font-size:10px;}
                        .cv-hero h1 {font-size:38px !important; line-height:1.08;}.cv-hero-copy>p {font-size:15px; line-height:1.55;}
                        .cv-hero-actions {gap:9px; margin-top:18px;}.cv-hero-actions button,.cv-hero-actions>a {min-height:48px; padding:0 15px; font-size:13px;}
                        .cv-trust {gap:9px; margin-top:18px; font-size:11px;}.cv-trust-mark {width:36px; height:36px; flex-basis:36px;}
                        .cv-visual {height:385px; margin-top:4px;}.cv-photo {right:-8px; width:77%; height:93%;}
                        .cv-phone {left:30%; bottom:0; width:183px; height:352px; padding:7px; border-width:2px; border-radius:29px;}
                        .cv-phone-screen {padding:23px 9px 10px; border-radius:21px;}.cv-phone-island {top:6px; width:66px; height:15px;}
                        .cv-phone-greeting {margin:5px 0 7px; font-size:8px;}.cv-phone-greeting strong {font-size:12px;}
                        .cv-phone-title {font-size:8px;}.cv-med {min-height:48px; padding:5px 6px; margin-bottom:3px; font-size:7px;}.cv-med strong {font-size:8px;}.cv-med-status {font-size:7px;}
                        .cv-phone-nav {padding:6px 2px 4px; font-size:6px;}.cv-float {gap:7px; padding:9px;}.cv-float-voice {left:0; top:33%; width:124px;}.cv-float-reminder {right:-3px; top:7%; width:158px;}
                        .cv-float strong {font-size:10px;}.cv-float small {font-size:9px;}.cv-float-icon {width:34px; height:34px; flex-basis:34px;}
                        .cv-wave {width:65px; height:13px;}
                        .cv-section {padding:48px 18px;}.cv-section h2 {font-size:28px;}
                        .cv-steps {grid-template-columns:1fr; gap:5px; margin-top:20px;}.cv-step {padding:13px 0 5px;}.cv-step h3 {margin-top:6px; font-size:15px;}
                        .cv-family-inner {grid-template-columns:1fr; gap:22px; padding:28px 18px 32px;}.cv-family-photo {height:230px;}.cv-family-copy h2 {font-size:28px;}
                        .cv-family-copy p {font-size:14px;}.cv-cta {padding:38px 18px;}.cv-cta-inner {padding:29px 16px;}.cv-cta h2 {font-size:26px;}.cv-cta p {font-size:12px;}
                        .cv-footer {align-items:flex-start; flex-direction:column; gap:15px; padding:20px 18px;}.cv-footer nav {justify-content:flex-start; gap:12px 16px;}.cv-copyright {white-space:normal;}
                }
                @media (prefers-reduced-motion:reduce) {.cv-landing * {animation:none!important; scroll-behavior:auto!important; transition:none!important;}}
        </style>
                <div class="cv-landing">
                    <div id="top"></div>
                    <header class="cv-topbar">
                        <a class="cv-brand" href="#top" aria-label="CareVoice home"><span class="cv-brand-mark"><svg width="27" height="27" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 20V10m0 6c-4.5 0-7-2-7-6 4.5 0 7 2 7 6Zm0-3c0-4.2 2.1-6.4 6.5-7-.1 4.5-2.1 7-6.5 7Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="m4 21 16-18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></span><span class="cv-brand-name">Care<span>Voice</span></span></a>
                        <div class="cv-top-actions"><form action="/" method="get"><input type="hidden" name="view" value="login"><button type="submit">Sign In</button></form><form action="/" method="get"><input type="hidden" name="view" value="signup"><button type="submit" class="cv-action-primary">Get Started</button></form></div>
                    </header>
                    <main>
                        <section class="cv-hero" id="features" aria-labelledby="cv-hero-title">
                            <div class="cv-hero-copy"><div class="cv-eyebrow">SMART HEALTHCARE ASSISTANT</div><h1 id="cv-hero-title">Your health speaks.<br><span>We listen.</span></h1><p>Manage medicines, understand health reports, and stay connected with your care using simple voice and intelligent assistance.</p>
                                <div class="cv-hero-actions"><form action="/" method="get"><input type="hidden" name="view" value="signup"><button type="submit" class="cv-action-primary">Get Started <span aria-hidden="true">&nbsp; →</span></button></form><a href="#how-it-works">Learn More <span aria-hidden="true">&nbsp; →</span></a></div>
                                <div class="cv-trust"><span class="cv-trust-mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 21s8-4 8-11V5l-8-3-8 3v5c0 7 8 11 8 11Z" stroke="currentColor" stroke-width="1.8"/><path d="m9 12 2 2 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span><strong>Designed for everyday care</strong><br>Clear tools for patients and the people beside them.</span></div>
                            </div>
                            <div class="cv-visual" aria-label="CareVoice dashboard and family preview"><div class="cv-photo"><img src="https://images.pexels.com/photos/6975192/pexels-photo-6975192.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1100" alt="An elderly Indian couple using a smartphone together"></div>
                                <div class="cv-phone"><div class="cv-phone-screen"><div class="cv-phone-island"></div><span class="cv-phone-status"><svg width="30" height="10" viewBox="0 0 30 10" fill="none" aria-hidden="true"><path d="M1 9h2V7H1v2Zm4 0h2V5H5v4Zm4 0h2V3H9v6Zm7-1a5 5 0 0 1 7 0m-5 0a2 2 0 0 1 3 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><rect x="24" y="2" width="5" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/></svg></span><div class="cv-phone-greeting">Good morning,<strong>Ramesh</strong></div><div class="cv-phone-date"><span>Today · Wednesday</span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.7"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg></div><div class="cv-phone-title">Today's Medicines <span>View all</span></div><div class="cv-med">08:00 AM <span class="cv-med-status">Taken</span><strong>Blood Pressure Medicine</strong>1 tablet · After breakfast</div><div class="cv-med">01:00 PM <span class="cv-med-status">Take</span><strong>Vitamin D</strong>1 tablet · After lunch</div><div class="cv-med">08:00 PM <span class="cv-med-status">Upcoming</span><strong>Cholesterol Medicine</strong>1 tablet · After dinner</div><div class="cv-phone-nav"><span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-6v-7h-4v7H4a1 1 0 0 1-1-1V10Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg><br>Home</span><span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 3h8l5 5v13H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.8"/><path d="M14 3v6h5M8 13h8m-8 4h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg><br>Medicines</span><span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 3v18h18M7 14l4-4 4 3 5-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg><br>Health</span><span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/></svg><br>More</span></div></div></div>
                                <div class="cv-float cv-float-voice"><span class="cv-float-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3" stroke="currentColor" stroke-width="2"/><path d="M5 11a7 7 0 0 0 14 0m-7 7v3m-4 0h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></span><div class="cv-wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><strong>How can I help today?</strong><small>English · తెలుగు</small></div>
                                <div class="cv-float cv-float-reminder"><span class="cv-float-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m4.8 14.7 9.9-9.9a3.2 3.2 0 0 1 4.5 4.5l-9.9 9.9a3.2 3.2 0 0 1-4.5-4.5Z" stroke="currentColor" stroke-width="2"/><path d="m8 11.5 4.5 4.5" stroke="currentColor" stroke-width="2"/></svg></span><span><strong>Medicine reminder</strong><small>It's time for your 8:00 PM dose</small></span></div>
                            </div>
                        </section>
                        <section class="cv-section" id="how-it-works"><p class="cv-section-kicker">How it works</p><h2>Three simple steps.</h2><div class="cv-steps"><article class="cv-step"><span class="cv-step-number">01</span><h3>Add your medicines</h3></article><article class="cv-step"><span class="cv-step-number">02</span><h3>Track your health</h3></article><article class="cv-step"><span class="cv-step-number">03</span><h3>Get reminders and assistance</h3></article></div></section>
                        <section class="cv-family-section" id="families"><div class="cv-family-inner"><div class="cv-family-photo"><img src="/app/static/elderly-family-medicine.jpg" alt="Elderly Indian couple using a smartphone together"></div><div class="cv-family-copy"><p class="cv-section-kicker">For you and your family</p><h2>Healthcare that is easier to use.</h2><p>Simple navigation, voice assistance, English and Telugu support, and clear medicine reminders.</p><div class="cv-family-languages"><span>English</span><span lang="te">తెలుగు</span></div></div></div></section>
                        <section class="cv-section cv-cta" id="pricing"><div class="cv-cta-inner"><h2>Take control of your daily health.</h2><p>CareVoice brings medicines, health tracking, reports, and voice assistance together.</p><form action="/" method="get"><input type="hidden" name="view" value="signup"><button class="cv-action-primary" type="submit">Get Started <span aria-hidden="true">&nbsp; →</span></button></form></div></section>
                    </main>
                    <footer class="cv-footer"><a class="cv-footer-brand" href="#top"><span class="cv-brand-mark"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 20V10m0 6c-4.5 0-7-2-7-6 4.5 0 7 6Zm0-3c0-4.2 2.1-6.4 6.5-7-.1 4.5-2.1 7-6.5 7Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>CareVoice</a><span class="cv-copyright">© 2026 CareVoice. All rights reserved.</span></footer>
                </div>
    """)
    english_style = "font-weight:750;background:#eaf7f1;" if not is_te else ""
    telugu_style = "font-weight:750;background:#eaf7f1;" if is_te else ""
    language_switch = (
        '<div aria-label="Language selector" style="display:flex;gap:4px;padding:4px;'
        'border:1px solid #c9e4d5;border-radius:10px;background:#fff;">'
        '<form action="/" method="get" style="margin:0"><input type="hidden" name="lang" value="en-IN">'
        f'<button type="submit" lang="en" style="min-height:30px;padding:0 8px;border:0;'
        f'border-radius:7px;color:#08784f;font:600 13px Manrope,sans-serif;{english_style}">English</button></form>'
        '<form action="/" method="get" style="margin:0"><input type="hidden" name="lang" value="te-IN">'
        f'<button type="submit" lang="te" style="min-height:30px;padding:0 8px;border:0;'
        f'border-radius:7px;color:#08784f;font:600 13px Manrope,sans-serif;{telugu_style}">తెలుగు</button></form></div>'
    )
    landing_markup = landing_markup.replace(
        '<div class="cv-top-actions">',
        f'<div class="cv-top-actions">{language_switch}',
        1,
    )
    if is_te:
        landing_translations = {
            "Sign In": "లాగిన్",
            "Get Started": "ప్రారంభించండి",
            "SMART HEALTHCARE ASSISTANT": "స్మార్ట్ ఆరోగ్య సహాయకుడు",
            "Your health speaks.": "మీ ఆరోగ్యం చెబుతుంది.",
            "We listen.": "మేము వింటాము.",
            "Manage medicines, understand health reports, and stay connected with your care using simple voice and intelligent assistance.": "సులభమైన వాయిస్ మరియు తెలివైన సహాయంతో మందులను నిర్వహించండి, ఆరోగ్య నివేదికలను అర్థం చేసుకోండి, మీ ఆరోగ్య సంరక్షణతో అనుసంధానంగా ఉండండి.",
            "Learn More": "మరింత తెలుసుకోండి",
            "Designed for everyday care": "రోజువారీ ఆరోగ్య సంరక్షణ కోసం రూపొందించబడింది",
            "Clear tools for patients and the people beside them.": "రోగులకు మరియు వారికి తోడుగా ఉండేవారికి సులభమైన సాధనాలు.",
            "An elderly Indian couple using a smartphone together": "స్మార్ట్‌ఫోన్‌ను కలిసి ఉపయోగిస్తున్న వృద్ధ భారతీయ జంట",
            "CareVoice dashboard and family preview": "CareVoice డాష్‌బోర్డ్ మరియు కుటుంబ ప్రివ్యూ",
            "Good morning,": "శుభోదయం,",
            "Today · Wednesday": "ఈరోజు · బుధవారం",
            "Today's Medicines": "ఈరోజు మందులు",
            "View all": "అన్నీ చూడండి",
            "Taken": "తీసుకున్నారు",
            "Take": "తీసుకోండి",
            "Upcoming": "తదుపరి",
            "Blood Pressure Medicine": "రక్తపోటు మందు",
            "1 tablet · After breakfast": "1 మాత్ర · అల్పాహారం తర్వాత",
            "1 tablet · After lunch": "1 మాత్ర · మధ్యాహ్న భోజనం తర్వాత",
            "Cholesterol Medicine": "కొలెస్ట్రాల్ మందు",
            "1 tablet · After dinner": "1 మాత్ర · రాత్రి భోజనం తర్వాత",
            "<br>Home</span>": "<br>హోమ్</span>",
            "<br>Medicines</span>": "<br>మందులు</span>",
            "<br>Health</span>": "<br>ఆరోగ్యం</span>",
            "<br>More</span>": "<br>ఇతరాలు</span>",
            "How can I help today?": "ఈరోజు నేను ఎలా సహాయపడగలను?",
            "English · తెలుగు": "తెలుగు · ఇంగ్లీష్",
            "Medicine reminder": "మందుల రిమైండర్",
            "It's time for your 8:00 PM dose": "రాత్రి 8:00 గంటల మందు తీసుకునే సమయం",
            "How it works": "ఇది ఎలా పనిచేస్తుంది",
            "Three simple steps.": "మూడు సులభమైన దశలు.",
            "Add your medicines": "మీ మందులను జోడించండి",
            "Track your health": "మీ ఆరోగ్యాన్ని నమోదు చేయండి",
            "Get reminders and assistance": "రిమైండర్లు మరియు సహాయం పొందండి",
            "For you and your family": "మీకు మరియు మీ కుటుంబానికి",
            "Healthcare that is easier to use.": "ఉపయోగించడానికి సులభమైన ఆరోగ్య సంరక్షణ.",
            "Simple navigation, voice assistance, English and Telugu support, and clear medicine reminders.": "సులభమైన నావిగేషన్, వాయిస్ సహాయం, తెలుగు మరియు ఇంగ్లీష్ మద్దతు, స్పష్టమైన మందుల రిమైండర్లు.",
            "Take control of your daily health.": "మీ రోజువారీ ఆరోగ్యాన్ని మీరే నిర్వహించండి.",
            "CareVoice brings medicines, health tracking, reports, and voice assistance together.": "CareVoice మందులు, ఆరోగ్య నమోదు, నివేదికలు మరియు వాయిస్ సహాయాన్ని ఒకేచోట అందిస్తుంది.",
            "© 2026 CareVoice. All rights reserved.": "© 2026 CareVoice. అన్ని హక్కులు ప్రత్యేకించబడ్డాయి.",
        }
        for english, telugu in landing_translations.items():
            landing_markup = landing_markup.replace(english, telugu)
    st.markdown("\n".join(line.lstrip() for line in landing_markup.splitlines()), unsafe_allow_html=True)


def _sync_language_preference(widget_key):
    st.session_state.lang_code = "te-IN" if st.session_state[widget_key] == "తెలుగు" else "en-IN"


def _localized_auth_message(message, is_te):
    if not is_te:
        return message
    translations = {
        "No account found with this email.": "ఈ ఇమెయిల్‌తో ఖాతా కనుగొనబడలేదు.",
        "Incorrect password. Please check and try again.": "పాస్‌వర్డ్ తప్పుగా ఉంది. తనిఖీ చేసి మళ్లీ ప్రయత్నించండి.",
        "Incorrect security answer.": "భద్రతా సమాధానం తప్పుగా ఉంది.",
        "Password reset successfully! You can now log in.": "పాస్‌వర్డ్ విజయవంతంగా రీసెట్ చేయబడింది. ఇప్పుడు లాగిన్ కావచ్చు.",
        "An account with this email already exists.": "ఈ ఇమెయిల్‌తో ఇప్పటికే ఒక ఖాతా ఉంది.",
    }
    return translations.get(message, message)


def start_authenticated_session(user, view):
    token = db.create_auth_session(user["id"])
    st.session_state.user = user
    st.session_state.auth_session_token = token
    st.session_state.pending_auth_cookie = {
        "action": "set",
        "token": token,
        "nonce": secrets.token_urlsafe(12),
    }
    st.session_state.voice_gender = user.get("voice_gender", "Female Voice")
    st.session_state.lang_code = user.get("language", st.session_state.lang_code)
    st.session_state.elderly_mode = bool(user.get("elderly_mode", 0))
    st.session_state.view = view


def clear_authenticated_session():
    db.revoke_auth_session(st.session_state.get("auth_session_token", ""))
    st.session_state.auth_session_token = ""
    st.session_state.user = None
    st.session_state.view = "landing"
    st.session_state.current_page = "Home"
    st.session_state.pending_auth_cookie = {
        "action": "clear",
        "nonce": secrets.token_urlsafe(12),
    }


# -----------------------------------------------------------------------------
# 2. LOGIN & PASSWORD RESET VIEW
# -----------------------------------------------------------------------------
def render_login_page():
    if st.session_state.get("auth_cookie_error"):
        st.error(st.session_state.pop("auth_cookie_error"))
    if "public_language" not in st.session_state:
        st.session_state.public_language = "తెలుగు" if str(st.session_state.lang_code).startswith("te") else "English"
    public_language = st.radio(
        "భాష" if str(st.session_state.lang_code).startswith("te") else "Language",
        ["English", "తెలుగు"],
        horizontal=True,
        key="public_language",
        on_change=_sync_language_preference,
        args=("public_language",),
    )
    st.session_state.lang_code = "te-IN" if public_language == "తెలుగు" else "en-IN"
    is_te = public_language == "తెలుగు"
    st.markdown("<br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 2, 1])

    with c2:
        st.markdown(f"""
            <div style='text-align:center; margin-bottom:24px;'>
                <div style='background:#166534; color:white; width:56px; height:56px; border-radius:16px; display:inline-flex; align-items:center; justify-content:center; font-size:28px; margin-bottom:12px;'>🌿</div>
                <h2 style='margin:0;'>{'తిరిగి స్వాగతం' if is_te else 'Welcome back'}</h2>
                <p style='color:#64748b; margin-top:4px;'>{'మీ CareVoice ఆరోగ్య ఖాతాలోకి సైన్ ఇన్ చేయండి.' if is_te else 'Sign in to your CareVoice healthcare account.'}</p>
            </div>
        """, unsafe_allow_html=True)

        email = st.text_input("ఇమెయిల్ చిరునామా" if is_te else "Email Address", placeholder="name@example.com")
        password = st.text_input("పాస్‌వర్డ్" if is_te else "Password", type="password", placeholder="••••••••")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("సైన్ ఇన్ →" if is_te else "Sign In →", type="primary", use_container_width=True):
            if not email or not password:
                st.error("దయచేసి ఇమెయిల్ మరియు పాస్‌వర్డ్ రెండింటినీ నమోదు చేయండి." if is_te else "Please enter both email and password.")
            else:
                user, err = db.authenticate_user(email, password)
                if err:
                    st.error(_localized_auth_message(err, is_te))
                else:
                    start_authenticated_session(
                        user,
                        "app" if user.get("onboarding_completed", 0) else "onboarding",
                    )
                    st.success("విజయవంతంగా సైన్ ఇన్ అయ్యారు!" if is_te else "Successfully signed in!")
                    st.rerun()

        st.markdown("---")
        if st.button("పాస్‌వర్డ్ మర్చిపోయారా?" if is_te else "Forgot Password?", type="secondary", use_container_width=True):
            st.session_state.view = "reset_password"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("ఖాతా లేదా? కొత్త ఖాతా సృష్టించండి" if is_te else "Need an Account? Create New Account", type="secondary", use_container_width=True):
            st.session_state.view = "signup"
            st.rerun()

        if st.button("← ప్రారంభ పేజీకి తిరిగి వెళ్లండి" if is_te else "← Back to Landing Page", type="secondary"):
            st.session_state.view = "landing"
            st.rerun()

def render_reset_password_page():
    is_te = str(st.session_state.get("lang_code", "en-IN")).startswith("te")
    st.markdown("<br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 2, 1])

    with c2:
        st.markdown(f"""
            <div style='text-align:center; margin-bottom:24px;'>
                <div style='background:#166534; color:white; width:56px; height:56px; border-radius:16px; display:inline-flex; align-items:center; justify-content:center; font-size:28px;'>🌿</div>
                <h2>{'పాస్‌వర్డ్‌ను రీసెట్ చేయండి' if is_te else 'Reset Password'}</h2>
                <p style='color:#64748b;'>{'పాస్‌వర్డ్ రీసెట్ చేయడానికి మీ ఖాతా ఇమెయిల్ మరియు భద్రతా సమాధానాన్ని నమోదు చేయండి.' if is_te else 'Enter your account email and security answer to reset your password.'}</p>
            </div>
        """, unsafe_allow_html=True)

        r_email = st.text_input("ఖాతా ఇమెయిల్ చిరునామా" if is_te else "Account Email Address", placeholder="name@example.com")
        r_ans = st.text_input("భద్రతా సమాధానం ('మీ ప్రధాన ఆరోగ్య లక్ష్యం ఏమిటి?')" if is_te else "Security Answer ('What is your primary health focus?')", value="wellness")
        r_new_pw = st.text_input("కొత్త పాస్‌వర్డ్" if is_te else "New Password", type="password", placeholder="••••••••")

        if st.button("ఇప్పుడే పాస్‌వర్డ్ రీసెట్ చేయండి" if is_te else "Reset Password Now", type="primary", use_container_width=True):
            if not r_email or not r_ans or not r_new_pw:
                st.error("దయచేసి అన్ని వివరాలను పూరించండి." if is_te else "Please fill in all fields.")
            else:
                ok, msg = db.reset_password(r_email, r_ans, r_new_pw)
                if ok:
                    st.success(_localized_auth_message(msg, is_te))
                    time.sleep(1.5)
                    st.session_state.view = "login"
                    st.rerun()
                else:
                    st.error(_localized_auth_message(msg, is_te))

        st.markdown("---")
        if st.button("← సైన్ ఇన్‌కు తిరిగి వెళ్లండి" if is_te else "← Back to Sign In", type="secondary", use_container_width=True):
            st.session_state.view = "login"
            st.rerun()

# -----------------------------------------------------------------------------
# 3. SIGN UP VIEW
# -----------------------------------------------------------------------------
def render_signup_page():
    is_te = str(st.session_state.get("lang_code", "en-IN")).startswith("te")
    if "signup_language" not in st.session_state:
        st.session_state.signup_language = "తెలుగు" if is_te else "English"
    st.markdown("<br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 2, 1])

    with c2:
        st.markdown("""
            <style>
            .stApp:has(.cv-signup-page) [data-testid="stTextInputRootElement"] {
                min-height: 44px;
                border: 1px solid #d3e2da !important;
                border-radius: 9px !important;
                background: #fff !important;
                box-shadow: 0 1px 2px rgba(20, 33, 61, .04) !important;
                transition: border-color .15s ease, box-shadow .15s ease;
            }
            .stApp:has(.cv-signup-page) [data-testid="stTextInputRootElement"]:focus-within {
                border-color: #087f5b !important;
                box-shadow: 0 0 0 3px rgba(8, 127, 91, .12) !important;
            }
            .stApp:has(.cv-signup-page) [data-testid="stTextInputRootElement"] input {
                min-height: 42px;
                padding: 0 12px !important;
                border: 0 !important;
                border-radius: 8px !important;
                background: transparent !important;
                box-shadow: none !important;
            }
            .stApp:has(.cv-signup-page) [data-testid="stSelectbox"] [data-baseweb="select"] > div {
                min-height: 44px;
                border: 1px solid #d3e2da !important;
                border-radius: 9px !important;
                background: #fff !important;
                box-shadow: 0 1px 2px rgba(20, 33, 61, .04) !important;
            }
            .stApp:has(.cv-signup-page) [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
                border-color: #087f5b !important;
                box-shadow: 0 0 0 3px rgba(8, 127, 91, .12) !important;
            }
            </style>
            <span class="cv-signup-page" aria-hidden="true"></span>
            <div style='text-align:center; margin-bottom:24px;'>
                <div style='background:#166534; color:white; width:56px; height:56px; border-radius:16px; display:inline-flex; align-items:center; justify-content:center; font-size:28px;'>🌿</div>
                <h2>Create Your Account</h2>
                <p style='color:#64748b;'>Start managing your personal health with simple voice assistance.</p>
            </div>
        """.replace(
            "Create Your Account",
            "మీ ఖాతాను సృష్టించండి" if is_te else "Create Your Account",
        ).replace(
            "Start managing your personal health with simple voice assistance.",
            "సులభమైన వాయిస్ సహాయంతో మీ ఆరోగ్యాన్ని నిర్వహించడం ప్రారంభించండి." if is_te else "Start managing your personal health with simple voice assistance.",
        ), unsafe_allow_html=True)

        s_name = st.text_input("పూర్తి పేరు" if is_te else "Full Name", placeholder="ఉదా. రమేష్ కుమార్" if is_te else "e.g. Ramesh Kumar")
        s_email = st.text_input("ఇమెయిల్ చిరునామా" if is_te else "Email Address", placeholder="name@example.com")
        s_phone = st.text_input("ఫోన్ నంబర్ (ఐచ్ఛికం)" if is_te else "Phone Number (Optional)", placeholder="+91 98765 43210")
        
        sp1, sp2 = st.columns(2)
        with sp1:
            s_pw = st.text_input("పాస్‌వర్డ్" if is_te else "Password", type="password", placeholder="••••••••")
        with sp2:
            s_pw_confirm = st.text_input("పాస్‌వర్డ్‌ను నిర్ధారించండి" if is_te else "Confirm Password", type="password", placeholder="••••••••")

        # Password strength indicator
        if s_pw:
            strength = 0
            if len(s_pw) >= 8:
                strength += 1
            if any(c.isupper() for c in s_pw):
                strength += 1
            if any(c.islower() for c in s_pw):
                strength += 1
            if any(c.isdigit() for c in s_pw):
                strength += 1
            
            strength_labels = (["బలహీనమైనది", "సాధారణం", "మంచిది", "బలమైనది"] if is_te else ["Weak", "Fair", "Good", "Strong"])
            strength_colors = ["#fee2e2", "#fef3c7", "#dcfce7", "#166534"]
            strength_label = strength_labels[min(strength - 1, 3)] if strength > 0 else ("చాలా బలహీనమైనది" if is_te else "Very Weak")
            strength_color = strength_colors[min(strength - 1, 3)] if strength > 0 else "#fee2e2"
            
            st.markdown(f"""
                <div style='margin-top:8px;'>
                    <div style='display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;'>
                        <span>{'పాస్‌వర్డ్ బలం' if is_te else 'Password Strength'}</span>
                        <span style='color:{strength_color}; font-weight:600;'>{strength_label}</span>
                    </div>
                    <div style='background:#e2e8f0; height:6px; border-radius:3px; overflow:hidden;'>
                        <div style='background:{strength_color}; height:100%; width:{strength * 25}%; transition:width 0.3s ease;'></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        s_lang = st.selectbox(
            "ప్రాధాన్య భాష" if is_te else "Preferred Language / భాష",
            ["English", "తెలుగు"],
            key="signup_language",
            on_change=_sync_language_preference,
            args=("signup_language",),
        )
        lang_code = "te-IN" if "తెలుగు" in s_lang else "en-IN"
        st.session_state.lang_code = lang_code

        agree = st.checkbox("సేవా నిబంధనలు మరియు ఆరోగ్య గోప్యతా విధానానికి అంగీకరిస్తున్నాను." if is_te else "I agree to the Terms of Service & Health Privacy Policy.", label_visibility="visible")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("ఖాతా సృష్టించి కొనసాగించండి →" if is_te else "Create Account & Continue →", type="primary", use_container_width=True):
            if not s_name or not s_email or not s_pw:
                st.error("దయచేసి అవసరమైన అన్ని వివరాలను పూరించండి." if is_te else "Please fill in all required fields.")
            elif s_pw != s_pw_confirm:
                st.error("పాస్‌వర్డ్‌లు సరిపోలడం లేదు." if is_te else "Passwords do not match.")
            elif not agree:
                st.warning("కొనసాగించడానికి నిబంధనలను అంగీకరించండి." if is_te else "Please accept the Terms to continue.")
            else:
                user, err = db.register_user(s_name, s_email, s_pw, s_phone, lang_code)
                if err:
                    st.error(_localized_auth_message(err, is_te))
                else:
                    start_authenticated_session(user, "onboarding")
                    st.success("ఖాతా విజయవంతంగా సృష్టించబడింది!" if is_te else "Account created successfully!")
                    st.rerun()

        st.markdown("---")
        if st.button("ఇప్పటికే ఖాతా ఉందా? సైన్ ఇన్ చేయండి" if is_te else "Already have an account? Sign In", type="secondary", use_container_width=True):
            st.session_state.view = "login"
            st.rerun()

# -----------------------------------------------------------------------------
# 4. ONBOARDING WIZARD VIEW
# -----------------------------------------------------------------------------
def render_onboarding_page():
    user = st.session_state.user
    user_name = user["name"] if user else "User"
    is_te = str(st.session_state.get("lang_code", "en-IN")).startswith("te")

    st.markdown("<br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 2, 1])

    with c2:
        step = st.session_state.onboard_step
        
        # Visual progress indicator
        progress_percent = (step / 4) * 100
        st.markdown(f"""
            <div style='text-align:center; margin-bottom:24px;'>
                <div style='background:#166534; color:white; width:50px; height:50px; border-radius:14px; display:inline-flex; align-items:center; justify-content:center; font-size:24px; margin-bottom:12px;'>🌿</div>
                <h2 style='margin:0;'>{'స్వాగతం, ' if is_te else 'Welcome, '}{user_name}!</h2>
                <p style='color:#64748b; margin:4px 0 16px 0;'>{'దశ' if is_te else 'Step'} {step} / 4 — {'CareVoice‌ను మీకు అనుకూలంగా మార్చండి' if is_te else 'Personalize CareVoice'}</p>
                <div style='background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden; margin:0 auto; max-width:300px;'>
                    <div style='background:#166534; height:100%; width:{progress_percent}%; transition:width 0.3s ease;'></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if step == 1:
            st.markdown("### 👋 CareVoice‌కు స్వాగతం" if is_te else "### 👋 Welcome to CareVoice")
            st.markdown(f"""
                <p style='color:#475569; line-height:1.6;'>
                    {'CareVoice మీ వ్యక్తిగత ఆరోగ్య సహాయకుడు. ఇది మందులను నిర్వహించడానికి, ఆరోగ్య కొలతలను నమోదు చేయడానికి మరియు సులభమైన వాయిస్ ఆదేశాలతో ప్రిస్క్రిప్షన్‌లను అర్థం చేసుకోవడానికి సహాయపడుతుంది.' if is_te else 'CareVoice is your personal healthcare companion that helps you manage medicines, track health vitals, and understand prescriptions using simple voice commands.'}
                </p>
                <p style='color:#475569; line-height:1.6;'>
                    {'మీ అనుభవాన్ని వ్యక్తిగతీకరించడానికి కొన్ని దశల్లో మీ ఖాతాను సిద్ధం చేద్దాం.' if is_te else "Let's set up your account in just a few steps to personalize your experience."}
                </p>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("ప్రారంభించండి →" if is_te else "Get Started →", type="primary", use_container_width=True):
                st.session_state.onboard_step = 2
                st.rerun()

        elif step == 2:
            st.markdown("### 🌐 భాషా ప్రాధాన్యత" if is_te else "### 🌐 Language Preference")
            st.markdown(
                "<p style='color:#64748b; margin-bottom:16px;'>వాయిస్ అసిస్టెంట్ మరియు యాప్ ఇంటర్‌ఫేస్ కోసం మీ భాషను ఎంచుకోండి.</p>" if is_te else
                "<p style='color:#64748b; margin-bottom:16px;'>Choose your preferred language for voice assistant and app interface.</p>",
                unsafe_allow_html=True,
            )
            
            if "onboard_language" not in st.session_state:
                st.session_state.onboard_language = "English" if st.session_state.lang_code == "en-IN" else "తెలుగు"
            lang_choice = st.radio(
                "ప్రధాన భాష" if is_te else "Primary Language",
                ["English", "తెలుగు"],
                index=0 if st.session_state.lang_code == "en-IN" else 1,
                label_visibility="collapsed",
                key="onboard_language",
                on_change=_sync_language_preference,
                args=("onboard_language",),
            )
            st.session_state.lang_code = "te-IN" if "తెలుగు" in lang_choice else "en-IN"
            
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← వెనుకకు" if is_te else "← Back", type="secondary", use_container_width=True):
                    st.session_state.onboard_step = 1
                    st.rerun()
            with b2:
                if st.button("తదుపరి దశ →" if is_te else "Next Step →", type="primary", use_container_width=True):
                    st.session_state.onboard_step = 3
                    st.rerun()

        elif step == 3:
            st.markdown("### 👵 అందుబాటు మోడ్" if is_te else "### 👵 Accessibility Mode")
            st.markdown(
                "<p style='color:#64748b; margin-bottom:16px;'>పెద్ద అక్షరాలు మరియు సులభంగా తాకగల బటన్ల కోసం పెద్దల మోడ్‌ను ప్రారంభించండి.</p>" if is_te else
                "<p style='color:#64748b; margin-bottom:16px;'>Enable Elderly Mode for larger fonts and easier touch targets.</p>",
                unsafe_allow_html=True,
            )
            
            st.markdown("""
                <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:16px;'>
                    <div style='display:flex; align-items:center; gap:12px;'>
                        <div style='font-size:24px;'>🔤</div>
                        <div>
                            <div style='font-weight:600; color:#0f172a;'>Font Size +33%</div>
                            <div style='font-size:13px; color:#64748b;'>Larger text for better readability</div>
                        </div>
                    </div>
                </div>
                <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:16px;'>
                    <div style='display:flex; align-items:center; gap:12px;'>
                        <div style='font-size:24px;'>👆</div>
                        <div>
                            <div style='font-weight:600; color:#0f172a;'>Touch Targets 48px</div>
                            <div style='font-size:13px; color:#64748b;'>Larger buttons for easier tapping</div>
                        </div>
                    </div>
                </div>
            """.replace("Font Size +33%", "అక్షరాల పరిమాణం +33%" if is_te else "Font Size +33%")
               .replace("Larger text for better readability", "సులభంగా చదవడానికి పెద్ద అక్షరాలు" if is_te else "Larger text for better readability")
               .replace("Touch Targets 48px", "టచ్ బటన్ల పరిమాణం 48px" if is_te else "Touch Targets 48px")
               .replace("Larger buttons for easier tapping", "సులభంగా తాకడానికి పెద్ద బటన్లు" if is_te else "Larger buttons for easier tapping"),
                unsafe_allow_html=True)
            
            st.session_state.elderly_mode = st.toggle(
                "పెద్దల మోడ్‌ను ప్రారంభించండి" if is_te else "Enable Elderly Mode",
                value=st.session_state.elderly_mode,
                help="అక్షరాల పరిమాణాన్ని 33% పెంచి బటన్లను పెద్దవిగా చేస్తుంది." if is_te else "Increases font size by 33% and makes touch targets larger"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← వెనుకకు" if is_te else "← Back", type="secondary", use_container_width=True):
                    st.session_state.onboard_step = 2
                    st.rerun()
            with b2:
                if st.button("తదుపరి దశ →" if is_te else "Next Step →", type="primary", use_container_width=True):
                    st.session_state.onboard_step = 4
                    st.rerun()

        elif step == 4:
            st.markdown("### 🎙️ వాయిస్ సెటప్" if is_te else "### 🎙️ Voice Setup")
            st.markdown(
                "<p style='color:#64748b; margin-bottom:16px;'>వాయిస్ అసిస్టెంట్ కోసం మీకు నచ్చిన వాయిస్‌ను ఎంచుకోండి.</p>" if is_te else
                "<p style='color:#64748b; margin-bottom:16px;'>Choose your preferred voice for the voice assistant.</p>",
                unsafe_allow_html=True,
            )
            
            st.session_state.voice_gender = st.selectbox(
                "వాయిస్ రకం" if is_te else "Voice Gender Preference",
                ["Female Voice", "Male Voice"],
                format_func=lambda voice: (
                    "మహిళా వాయిస్" if voice == "Female Voice" else "పురుష వాయిస్"
                ) if is_te else voice,
                index=0 if "female" in str(st.session_state.voice_gender).lower() else 1,
                key="onboarding_voice_gender",
                label_visibility="collapsed"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔊 వాయిస్ వినండి" if is_te else "🔊 Preview Voice", type="secondary", use_container_width=True):
                preview_text = "Hello! This is a preview of your voice assistant."
                if st.session_state.lang_code == "te-IN":
                    preview_text = "నమస్కారం! ఇది మీ వాయిస్ అసిస్టెంట్ యొక్క ప్రివ్యూ."
                st.session_state.active_audio_html = generate_audio_player(
                    preview_text, st.session_state.lang_code, st.session_state.voice_gender
                )
            
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← వెనుకకు" if is_te else "← Back", type="secondary", use_container_width=True):
                    st.session_state.onboard_step = 3
                    st.rerun()
            with b2:
                if st.button("🚀 సెటప్ పూర్తి చేసి డాష్‌బోర్డ్ తెరవండి" if is_te else "🚀 Complete Setup & Launch Dashboard", type="primary", use_container_width=True):
                    if user:
                        updated_user = db.update_user_preferences(
                            user["id"],
                            st.session_state.lang_code,
                            st.session_state.elderly_mode,
                            onboarding_completed=1,
                            voice_gender=st.session_state.voice_gender,
                        )
                        st.session_state.user = updated_user
                    st.session_state.view = "app"
                    st.rerun()

# -----------------------------------------------------------------------------
# 5. AUTHENTICATED PATIENT APP VIEW
# -----------------------------------------------------------------------------
def render_reminder_audio_listener(user_id, user_name, lang_code, voice_gender):
        safe_user_id = json.dumps(str(user_id))
        reminder_date = datetime.datetime.now().strftime("%Y-%m-%d")
        schedules = db.get_active_reminder_schedules()
        medicine_logs = db.get_medicine_logs_for_date(user_id, reminder_date)
        reminders = reminder_worker.build_in_app_reminders(
                schedules,
                medicine_logs,
                user_id,
                user_name,
                lang_code,
                reminder_date,
        )
        for reminder in reminders:
                reminder["audio"] = generate_offline_tts_data(
                        reminder["body"], lang_code, voice_gender
                )
        safe_reminders = json.dumps(reminders, ensure_ascii=True).replace("<", "\\u003c")
        safe_lang = json.dumps(lang_code)
        safe_gender = json.dumps(str(voice_gender).lower())
        st.components.v1.html(f"""
                <script>
                    (() => {{
                        const userId = {safe_user_id};
                        const selectedLanguage = {safe_lang};
                        const voiceGender = {safe_gender};
                        const scheduledReminders = {safe_reminders};
                        const speakReminder = (reminder, attempts = 0) => {{
                            const lang = reminder.lang || selectedLanguage || "en-IN";
                            const languagePrefix = lang.slice(0, 2).toLowerCase();
                            const fallbackAudio = () => {{
                                if (!reminder.audio) return;
                                const audio = new Audio(reminder.audio);
                                audio.play().catch(() => {{}});
                            }};
                            if (!("speechSynthesis" in window)) {{ fallbackAudio(); return; }}
                            const voices = window.speechSynthesis.getVoices();
                            const languageVoices = voices.filter(voice => voice.lang.toLowerCase().startsWith(languagePrefix));
                            if (!voices.length && attempts < 8) {{
                                window.setTimeout(() => speakReminder(reminder, attempts + 1), 150);
                                return;
                            }}
                            const femaleHints = ["female", "zira", "heera", "samantha", "susan", "hazel", "catherine", "victoria", "karen", "aria", "emma", "ava", "jenny", "michelle", "sonia", "libby", "natasha", "moira"];
                            const maleHints = ["david", "mark", "george", "ravi", "alex", "daniel", "guy", "ryan", "tony", "thomas", "oliver", "liam", "eric", "andrew"];
                            const hints = voiceGender.includes("female") ? femaleHints : maleHints;
                            const matchesGender = voice => {{
                                const name = voice.name.toLowerCase();
                                if (voiceGender.includes("female")) return hints.some(hint => name.includes(hint));
                                return !femaleHints.some(hint => name.includes(hint)) &&
                                    (hints.some(hint => name.includes(hint)) || /(^|[\\s-])male($|[\\s-])/.test(name));
                            }};
                            const selectedVoice = languageVoices.find(matchesGender) || voices.find(matchesGender);
                            if (!selectedVoice) {{ fallbackAudio(); return; }}
                            const utterance = new SpeechSynthesisUtterance(reminder.body);
                            utterance.lang = lang;
                            if (selectedVoice) utterance.voice = selectedVoice;
                            utterance.onerror = fallbackAudio;
                            window.speechSynthesis.speak(utterance);
                        }};
                        const playOnce = (reminder) => {{
                            if (!reminder || String(reminder.user_id) !== String(userId)) return;
                            const spokenKey = `carevoice-spoken-${{reminder.delivery_key}}`;
                            try {{ if (localStorage.getItem(spokenKey)) return; localStorage.setItem(spokenKey, "spoken"); }} catch (error) {{}}
                            speakReminder(reminder);
                        }};
                        const checkScheduledReminders = () => {{
                            const now = new Date();
                            const localDate = `${{now.getFullYear()}}-${{String(now.getMonth() + 1).padStart(2, "0")}}-${{String(now.getDate()).padStart(2, "0")}}`;
                            const currentMinute = now.getHours() * 60 + now.getMinutes();
                            for (const reminder of scheduledReminders) {{
                                const dueNow = currentMinute >= reminder.minute_of_day && currentMinute - reminder.minute_of_day <= 2;
                                const dateMatches = reminder.reminder_date === localDate;
                                const isSchedule = reminder.delivery_key.startsWith(`scheduled:${{localDate}}:`);
                                const isSnooze = reminder.delivery_key.startsWith("snooze:");
                                if (dueNow && dateMatches && (isSchedule || isSnooze)) playOnce(reminder);
                            }}
                        }};
                        checkScheduledReminders();
                        window.setInterval(checkScheduledReminders, 5000);
                        if ("BroadcastChannel" in window) {{
                            const channel = new BroadcastChannel("carevoice-reminders");
                            channel.addEventListener("message", (event) => {{
                                const reminder = event.data;
                                if (!reminder || reminder.type !== "carevoice-reminder") return;
                                const scheduled = scheduledReminders.find(
                                    item => item.delivery_key === reminder.delivery_key
                                );
                                playOnce({{ ...scheduled, ...reminder, audio: reminder.audio || scheduled?.audio }});
                            }});
                        }}
                    }})();
                </script>
        """, height=1)


def render_authenticated_app():
    user = st.session_state.user
    user_id = user["id"]
    user_name = user["name"]
    is_te = st.session_state.lang_code == "te-IN"
    all_medicines = db.get_all_medicines(user_id)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    render_medicine_reminder_scheduler(
        all_medicines,
        user_id,
        user_name=user_name,
        show_controls=st.session_state.current_page == "Settings"
    )
    render_reminder_audio_listener(
        user_id,
        user_name,
        st.session_state.lang_code,
        st.session_state.get("voice_gender", "Female Voice"),
    )
    render_active_medicine_reminder_banner()
    nav.render_mobile_drawer(
        user_name,
        st.session_state.current_page,
        is_te,
    )

    # SIDEBAR NAVIGATION
    with st.sidebar:
        st.markdown(f"""
            <div style='display:flex; align-items:center; gap:12px; margin-bottom:20px;'>
                <div style='background:#166534; color:white; width:40px; height:40px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold;'>🌿</div>
                <div>
                    <h2 style='margin:0; font-size:20px; color:#166534;'>CareVoice</h2>
                    <p style='margin:0; font-size:12px; color:#64748b;'>{user_name}</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

        nav_items = [
            ("Home" if not is_te else "హోమ్", "🏠", "ముఖ్య వివరాలు" if is_te else "Dashboard", "Home"),
            ("Medicines" if not is_te else "నా మందులు", "💊", "మందుల పట్టిక" if is_te else "My Active Medicines", "Medicines"),
            ("Prescriptions" if not is_te else "ప్రిస్క్రిప్షన్", "📋", "ప్రిస్క్రిప్షన్ అప్‌లోడ్" if is_te else "OCR Prescription Upload", "Prescriptions"),
            ("Health" if not is_te else "నా ఆరోగ్యం", "🩺", "ఆరోగ్య రీడింగ్స్" if is_te else "My Health & Vitals", "Health"),
            ("Diet" if not is_te else "ఆహార సలహాలు", "🥗", "పోషకాహార ప్లాన్" if is_te else "Nutrition Guidance", "Diet"),
            ("Voice Assistant" if not is_te else "వాయిస్ అసిస్టెంట్", "🎙️", "వాయిస్ హెల్ప్" if is_te else "CareVoice Siri Hub", "Voice Assistant"),
            ("Settings" if not is_te else "సెట్టింగ్స్", "⚙️", "ఖాతా అమరికలు" if is_te else "Account Preferences", "Settings")
        ]

        for display_label, icon, desc, target_page in nav_items:
            is_active = st.session_state.current_page == target_page
            btn_label = f"{icon}  {display_label}"
            if st.button(btn_label, use_container_width=True, type="primary" if is_active else "secondary", key=f"sb_nav_{target_page}"):
                st.session_state.current_page = target_page
                st.rerun()

        st.markdown("---")
        st.caption("🌐 Language / భాష")
        lang_sel = st.radio("Lang", ["English", "తెలుగు"], index=1 if is_te else 0, label_visibility="collapsed", key="sb_lang")
        new_lang = "te-IN" if "తెలుగు" in lang_sel else "en-IN"
        if new_lang != st.session_state.lang_code:
            st.session_state.lang_code = new_lang
            db.update_user_preferences(user_id, language=new_lang)
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        el_label = "👵 పెద్దల మోడ్ (Elderly Mode)" if is_te else "👵 Elderly Mode (Large Text)"
        st.caption(f"**{el_label}**")
        el_c1, el_c2 = st.columns(2)
        with el_c1:
            if st.button("ఆఫ్" if is_te else "OFF", type="secondary" if st.session_state.elderly_mode else "primary", use_container_width=True, key="sb_el_off"):
                if st.session_state.elderly_mode:
                    st.session_state.elderly_mode = False
                    db.update_user_preferences(user_id, elderly_mode=False)
                    st.rerun()
        with el_c2:
            if st.button("ఆన్" if is_te else "ON", type="primary" if st.session_state.elderly_mode else "secondary", use_container_width=True, key="sb_el_on"):
                if not st.session_state.elderly_mode:
                    st.session_state.elderly_mode = True
                    db.update_user_preferences(user_id, elderly_mode=True)
                    st.rerun()

        st.markdown("---")
        signout_label = "🚪 లాగ్ అవుట్" if is_te else "🚪 Sign Out"
        if st.button(signout_label, use_container_width=True, type="secondary", key="sb_signout"):
            clear_authenticated_session()
            st.rerun()

    if st.session_state.current_page == "Home":
        # Keep the shared greeting/status header on Home only.
        h_c1, h_c2 = st.columns([3, 1])
        with h_c1:
            greeting = f"నమస్కారం, {user_name} గారు 👋" if is_te else f"Hello, {user_name} 👋"
            st.markdown(f"<h1 style='margin:0;'>{greeting}</h1>", unsafe_allow_html=True)
            st.caption("వ్యక్తిగత ఆరోగ్య సమాచారం మరియు మందుల సహాయకుడు" if is_te else "Personalized healthcare overview & medication assistant")

        with h_c2:
            pending_cnt = sum(1 for m in all_medicines if m['status'] != 'Taken')
            st.markdown(f"""
                <div style='display:flex; gap:10px; justify-content:flex-end; align-items:center;'>
                    <div style='background:#ffffff; border:1px solid #e2e8f0; padding:6px 14px; border-radius:20px; font-size:13px; color:#166534; font-weight:600;'>
                        🔔 {pending_cnt} {'పెండింగ్' if is_te else 'Pending'}
                    </div>
                    <div style='background:#166534; color:white; width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:bold;'>
                        {user_name[:2].upper()}
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

    # SCHEDULED REMINDER ANNOUNCEMENT BANNER
    if st.session_state.reminder_alert:
        med = st.session_state.reminder_alert
        display_reminder_name = display_medicine_name(med["name"], is_te)
        st.markdown("### ⏰ " + ("మందుల రిమైండర్" if is_te else "MEDICINE REMINDER ANNOUNCEMENT"))
        r_c1, r_c2 = st.columns([1, 3])

        with r_c1:
            if med.get("image_url"):
                st.image(med["image_url"], width=130)

        with r_c2:
            st.markdown(f"## **{display_reminder_name} ({med['dosage']})**")
            st.markdown(f"**{'సమయం' if is_te else 'Timing'}:** `{med['time_slot']}` | **{'సూచనలు' if is_te else 'Instructions'}:** {med['instructions']}")

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("✓ ఇప్పుడే తీసుకోండి" if is_te else "✓ TAKE NOW", type="primary", use_container_width=True, key="rem_take"):
                    now_time = datetime.datetime.now().strftime("%I:%M %p")
                    now_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    db.log_medicine_action(user_id, med["id"], med["name"], med["dosage"], "Taken", med["time_slot"], now_time, now_date)
                    txt = f"{display_reminder_name} మందు తీసుకున్నట్లు నమోదైంది." if is_te else f"{med['name']} marked as taken."
                    st.success(txt)
                    st.session_state.active_audio_html = generate_audio_player(txt, st.session_state.lang_code)
                    st.session_state.reminder_alert = None
                    time.sleep(1)
                    st.rerun()

            with b2:
                if st.button("15 నిమిషాలు వాయిదా" if is_te else "SNOOZE (15m)", use_container_width=True, key="rem_snooze"):
                    txt = "15 నిమిషాల తర్వాత మళ్ళీ గుర్తు చేస్తాను." if is_te else "Reminder snoozed for 15 minutes."
                    st.info(txt)
                    st.session_state.active_audio_html = generate_audio_player(txt, st.session_state.lang_code)
                    st.session_state.reminder_alert = None
                    time.sleep(1)
                    st.rerun()

            with b3:
                if st.button("వదిలేయండి" if is_te else "SKIP", use_container_width=True, key="rem_skip"):
                    st.session_state.skip_confirm_med_id = med["id"]

            if st.session_state.skip_confirm_med_id == med["id"]:
                st.warning("ఈ రోజు ఈ మందును తీసుకోకుండా వదిలేయాలనుకుంటున్నారా?" if is_te else "Are you sure you want to skip taking this medicine today?")
                sk1, sk2 = st.columns(2)
                with sk1:
                    if st.button("అవును, వదిలేయండి" if is_te else "Yes, Confirm Skip", type="primary", key="skip_yes"):
                        now_time = datetime.datetime.now().strftime("%I:%M %p")
                        now_date = datetime.datetime.now().strftime("%Y-%m-%d")
                        db.log_medicine_action(user_id, med["id"], med["name"], med["dosage"], "Skipped", med["time_slot"], now_time, now_date)
                        txt = f"{display_reminder_name} మందు వదిలేశారు." if is_te else f"{med['name']} marked as skipped."
                        st.session_state.active_audio_html = generate_audio_player(txt, st.session_state.lang_code)
                        st.session_state.skip_confirm_med_id = None
                        st.session_state.reminder_alert = None
                        time.sleep(1)
                        st.rerun()
                with sk2:
                    if st.button("రద్దు" if is_te else "Cancel", key="skip_no"):
                        st.session_state.skip_confirm_med_id = None
                        st.rerun()

    # -------------------------------------------------------------------------
    # PAGE ROUTER
    # -------------------------------------------------------------------------
    page = st.session_state.current_page

    # --- 1. DASHBOARD PAGE ---
    if page == "Home":
        # Quick Stats Cards (3-column responsive grid)
        medicines = all_medicines
        metrics = db.get_latest_health_metrics(user_id)
        
        stats_c1, stats_c2 = st.columns(2)
        
        with stats_c1:
            st.markdown(f"""
                <div class='cv-card' style='text-align:center;'>
                    <div style='font-size:32px; margin-bottom:8px;'>💊</div>
                    <div style='font-size:13px; color:#64748b; font-weight:500;'>{'ఈరోజు మందులు' if is_te else 'Medicines Today'}</div>
                    <div style='font-size:32px; color:#0f172a; font-weight:700; margin:4px 0;'>{len(medicines)}</div>
                    <div style='font-size:13px; color:#166534;'>{'మీ షెడ్యూల్‌లో ఉన్నాయి' if is_te else 'Saved in your schedule'}</div>
                </div>
            """, unsafe_allow_html=True)
        
        with stats_c2:
            metrics_count = len(metrics) if metrics else 0
            st.markdown(f"""
                <div class='cv-card' style='text-align:center;'>
                    <div style='font-size:32px; margin-bottom:8px;'>🩺</div>
                    <div style='font-size:13px; color:#64748b; font-weight:500;'>{'ఆరోగ్య కొలతలు' if is_te else 'Health Metrics'}</div>
                    <div style='font-size:32px; color:#0f172a; font-weight:700; margin:4px 0;'>{metrics_count}</div>
                    <div style='font-size:13px; color:#166534;'>{'ఈరోజు నమోదు చేశారు' if is_te else 'Recorded today'}</div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # Empty state for new users
        if not medicines and not metrics:
            st.markdown(f"""
                <div style='text-align:center; padding:48px 24px; color:#64748b;'>
                    <div style='font-size:64px; margin-bottom:16px;'>🌿</div>
                    <h3 style='color:#0f172a; font-size:24px; font-weight:600; margin-bottom:8px;'>{'కేర్‌వాయిస్‌కు స్వాగతం!' if is_te else 'Welcome to CareVoice!'}</h3>
                    <p style='font-size:15px; line-height:1.6; margin:0;'>{'మీ మొదటి మందును జోడించండి లేదా ఆరోగ్య కొలతలను నమోదు చేసి ప్రారంభించండి.' if is_te else 'Get started by adding your first medicine or recording your health metrics.'}</p>
                </div>
            """, unsafe_allow_html=True)
    # --- 2. MEDICINES MANAGEMENT PAGE ---
    elif page == "Medicines":
        st.markdown(
            """
            <style>
                .stApp {
                    background: #ffffff !important;
                    color: #0f172a !important;
                }
                .stApp [data-testid="stVerticalBlock"] > div {
                    background: transparent !important;
                }
                div[data-testid="stForm"] {
                    background: #ffffff !important;
                    border: 1px solid #d8e8db !important;
                    border-radius: 18px !important;
                    padding: 1.25rem !important;
                    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04) !important;
                }
                .stTextInput label, .stSelectbox label, .stTextArea label, .stFileUploader label,
                .stTabs [role="tab"], .stButton > button, .stMarkdown h3, .stMarkdown h2 {
                    color: #0f172a !important;
                }
                .stTextInput input, .stTextArea textarea, .stSelectbox select,
                .stFileUploader div[data-baseweb="base-input"] {
                    background: #ffffff !important;
                    color: #0f172a !important;
                    border: 1px solid #cbd5e1 !important;
                    border-radius: 10px !important;
                }
                .stTextInput input::placeholder, .stTextArea textarea::placeholder {
                    color: #64748b !important;
                }
                .stButton > button {
                    background: #166534 !important;
                    color: #ffffff !important;
                    border: 1px solid #166534 !important;
                    border-radius: 10px !important;
                    font-weight: 600 !important;
                    box-shadow: none !important;
                }
                .stButton > button:hover {
                    background: #14532d !important;
                    border-color: #14532d !important;
                }
                .stButton button[kind="secondary"] {
                    background: #f8fafc !important;
                    color: #0f172a !important;
                    border: 1px solid #dbe4ee !important;
                }
                .stTabs [role="tablist"] {
                    background: #f8fafc !important;
                    border-radius: 12px !important;
                    padding: 0.25rem !important;
                }
                .stTabs [role="tab"] {
                    color: #0f172a !important;
                    font-weight: 600 !important;
                    border-radius: 10px !important;
                }
                .stTabs [role="tab"][aria-selected="true"] {
                    background: #dcfce7 !important;
                    color: #166534 !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("## 💊 నా మందులు మరియు షెడ్యూల్ నిర్వహణ" if is_te else "## 💊 My Medicines & Schedule Management")

        if "add_medicine_success" not in st.session_state:
            st.session_state.add_medicine_success = ""
        if "show_add_medicine_form" not in st.session_state:
            st.session_state.show_add_medicine_form = False

        button_col, status_col = st.columns([1, 3])
        with button_col:
            if st.button("➕ మందు జోడించండి" if is_te else "➕ Add Medicine", type="primary", use_container_width=True, key="toggle_add_medicine"):
                st.session_state.show_add_medicine_form = not st.session_state.show_add_medicine_form
                if st.session_state.show_add_medicine_form:
                    st.session_state.add_medicine_success = ""
                st.rerun()

        if st.session_state.get("add_medicine_success"):
            st.success(st.session_state.add_medicine_success)

        if st.session_state.show_add_medicine_form:
            st.markdown("### జోడించే విధానాన్ని ఎంచుకోండి" if is_te else "### Choose Add Method")
            add_tab1, add_tab2 = st.tabs(["📝 చేతితో జోడించండి", "📋 ప్రిస్క్రిప్షన్ నుండి"] if is_te else ["📝 Add Manually", "📋 Add from Prescription"])

            with add_tab1:
                st.markdown("### మోతాదు తరచుదనాన్ని ఎంచుకోండి" if is_te else "### Set dose frequency")
                st.caption("ఈ మందును ఎంత తరచుగా తీసుకుంటారో ఎంచుకోండి. ప్రతి మోతాదుకు సమయం మరియు ఆహారానికి సంబంధించిన ఎంపిక కనిపిస్తుంది." if is_te else "Choose how often this medicine is taken. A time and food-timing row appears for each dose.")
                medicine_frequency_labels = {
                    "Daily": "రోజుకు ఒకసారి",
                    "Twice Daily": "రోజుకు రెండుసార్లు",
                    "Three Times Daily": "రోజుకు మూడుసార్లు",
                    "As Needed": "అవసరమైనప్పుడు",
                }
                m_freq = st.selectbox(
                    "తరచుదనం *" if is_te else "Frequency *",
                    ["Daily", "Twice Daily", "Three Times Daily", "As Needed"],
                    format_func=lambda value: medicine_frequency_labels.get(value, value) if is_te else value,
                    key="manual_medicine_frequency",
                )
                m_req_cnt = required_daily_reminder_count(m_freq)
                with st.form("manual_add_form", clear_on_submit=False):
                    st.markdown("### మందుల వివరాలు" if is_te else "### Medicine Details")

                    m_name = st.text_input("మందు పేరు *" if is_te else "Medicine Name *", placeholder="ఉదా. Amlodipine, Metformin" if is_te else "e.g. Amlodipine, Metformin")
                    if m_name:
                        common_meds = ["Amlodipine", "Metformin", "Atorvastatin", "Omeprazole", "Losartan", "Aspirin"]
                        suggestions = [med for med in common_meds if med.lower() in m_name.lower()]
                        if suggestions:
                            suggestions_display = [display_medicine_name(med, is_te) for med in suggestions[:3]]
                            st.caption(
                                f"💡 మీరు వీటిలో ఒకదాన్ని ఉద్దేశించారా: {', '.join(suggestions_display)}"
                                if is_te else f"💡 Did you mean: {', '.join(suggestions[:3])}"
                            )

                    dos_col1, dos_col2, dos_col3 = st.columns([2, 1, 1])
                    with dos_col1:
                        m_dos_value = st.text_input("బలం *" if is_te else "Strength *", placeholder="ఉదా. 500" if is_te else "e.g. 500")
                    with dos_col2:
                        m_dos_unit = st.selectbox("బలం యూనిట్" if is_te else "Strength unit", ["mg", "g", "ml", "mcg", "IU"])
                    with dos_col3:
                        m_dose_quantity = st.text_input("మోతాదు పరిమాణం *" if is_te else "Dose quantity *", value="1 మాత్ర" if is_te else "1 tablet", placeholder="ఉదా. 1 మాత్ర" if is_te else "e.g. 1 tablet")

                    m_dos = f"{m_dos_value} {m_dos_unit}, {m_dose_quantity}" if m_dos_value else ""
                    st.markdown("#### మోతాదు షెడ్యూల్" if is_te else "#### Dose schedule")
                    m_times = []
                    m_food_timings = []
                    default_dose_times = [
                        datetime.time(9, 0),
                        datetime.time(21, 0),
                        datetime.time(13, 30),
                    ]
                    default_food_timings = ["After Food", "After Food", "After Food"]
                    m_food_labels = {
                        "Before Food": "భోజనానికి ముందు",
                        "After Food": "భోజనం తర్వాత",
                        "With Food": "భోజనంతో పాటు",
                        "Empty Stomach": "ఖాళీ కడుపుతో",
                    }
                    m_food_opts = list(m_food_labels)

                    if m_req_cnt:
                        for dose_index in range(m_req_cnt):
                            time_col, food_col = st.columns(2)
                            with time_col:
                                dose_time = st.time_input(
                                    f"మోతాదు {dose_index + 1} సమయం *" if is_te else f"Dose {dose_index + 1} Time *",
                                    value=default_dose_times[dose_index],
                                    key=f"manual_dose_time_{dose_index}",
                                )
                            with food_col:
                                food_timing = st.selectbox(
                                    f"మోతాదు {dose_index + 1} ఆహారానికి ముందు / తర్వాత *" if is_te else f"Dose {dose_index + 1} Before / After Food *",
                                    m_food_opts,
                                    format_func=lambda value: m_food_labels.get(value, value) if is_te else value,
                                    index=m_food_opts.index(default_food_timings[dose_index]),
                                    key=f"manual_dose_food_{dose_index}",
                                )
                            m_times.append(dose_time.strftime("%I:%M %p"))
                            m_food_timings.append(food_timing)
                    else:
                        st.caption("అవసరమైనప్పుడు తీసుకునే మందులకు ముందుగా రిమైండర్ సమయాలు ఉండవు." if is_te else "As-needed medicines do not have scheduled reminder times.")

                    m_time = ", ".join(m_times)
                    m_food = "; ".join(
                        f"{dose_time}: {food_timing}"
                        for dose_time, food_timing in zip(m_times, m_food_timings)
                    ) or "As needed"
                    m_inst = st.text_area("సూచనలు" if is_te else "Instructions", placeholder="ఉదా. అల్పాహారం తర్వాత నీటితో తీసుకోండి; మాత్రను నలపవద్దు" if is_te else "e.g. Take after breakfast with water, do not crush")
                    m_photo = st.file_uploader("మాత్ర ఫోటోను అప్‌లోడ్ చేయండి (ఐచ్ఛికం)" if is_te else "Upload Tablet Photo (Optional)", type=["png", "jpg", "jpeg"], help="మీ మందును సులభంగా గుర్తించడానికి ఫోటో జోడించండి." if is_te else "Add a photo to easily identify your medicine")

                    st.markdown("<br>", unsafe_allow_html=True)

                    submitted = st.form_submit_button("💾 మందును సేవ్ చేయండి" if is_te else "💾 Save Medicine", type="primary", use_container_width=True)
                    if submitted:
                        validation_errors = []
                        if not m_name or len(m_name) < 2:
                            validation_errors.append("మందు పేరు కనీసం 2 అక్షరాలు ఉండాలి" if is_te else "Medicine name must be at least 2 characters")
                        if not m_dos_value:
                            validation_errors.append("మందు బలం తప్పనిసరి" if is_te else "Medicine strength is required")
                        if not m_dose_quantity.strip():
                            validation_errors.append("మోతాదు పరిమాణం తప్పనిసరి" if is_te else "Dose quantity is required")
                        required_times = required_daily_reminder_count(m_freq)
                        saved_times = count_clock_times(m_time)
                        if required_times is None and m_freq != "As Needed":
                            validation_errors.append("అందుబాటులో ఉన్న తరచుదనాన్ని ఎంచుకోండి" if is_te else "Choose a supported frequency")
                        elif required_times and saved_times != required_times:
                            validation_errors.append(f"{m_freq} కోసం ఖచ్చితంగా {required_times} సమయాలను నమోదు చేయండి" if is_te else f"Enter exactly {required_times} clock time(s) for {m_freq.lower()}")

                        if validation_errors:
                            for error in validation_errors:
                                st.error(f"❌ {error}")
                        else:
                            try:
                                img_url = None
                                if m_photo:
                                    t_filename = f"tablet_{int(time.time())}_{m_photo.name}"
                                    t_path = storage.upload_path("tablets", t_filename)
                                    with open(t_path, "wb") as f:
                                        f.write(m_photo.read())
                                    b64_img = base64.b64encode(open(t_path, "rb").read()).decode()
                                    img_url = f"data:image/jpeg;base64,{b64_img}"

                                db.add_medicine(user_id, m_name, m_dos, m_time, m_inst, m_freq, m_food, img_url)
                                st.session_state.show_add_medicine_form = False
                                st.session_state.add_medicine_success = "మందు విజయవంతంగా జోడించబడింది." if is_te else "Medicine added successfully."
                                st.rerun()
                            except Exception as exc:
                                st.error(f"మందును సేవ్ చేయలేకపోయాం: {exc}" if is_te else f"Failed to save medicine: {exc}")
                                st.info("ఫారమ్‌ను సమీక్షించి మళ్లీ ప్రయత్నించండి. మీరు నమోదు చేసిన వివరాలు సవరణ కోసం అలాగే ఉంచబడ్డాయి." if is_te else "Please review the form and try again. Your entered data has been kept for editing.")

            with add_tab2:
                st.info("డాక్టర్ ప్రిస్క్రిప్షన్‌ను అప్‌లోడ్ చేయండి; CareVoice AI వివరాలను గుర్తించి రిమైండర్‌లను సిద్ధం చేస్తుంది." if is_te else "Upload your doctor's prescription and CareVoice AI will extract text and structure reminders.")
                if st.button("ప్రిస్క్రిప్షన్ అప్‌లోడ్‌కు వెళ్లండి →" if is_te else "Go to Prescription Upload Wizard →", type="primary", use_container_width=True):
                    st.session_state.current_page = "Prescriptions"
                    st.session_state.rx_step = 1
                    st.rerun()

        medicines = db.get_all_medicines(user_id)
        
        if not medicines:
            st.markdown("""
                <div style='text-align:center; padding:48px 24px; color:#64748b;'>
                    <div style='font-size:48px; margin-bottom:16px;'>💊</div>
                    <h3 style='color:#0f172a; font-size:20px; font-weight:600; margin-bottom:8px;'>{'ఇంకా మందులు జోడించలేదు' if is_te else 'No medicines added yet'}</h3>
                    <p style='font-size:14px; line-height:1.5; margin:0;'>{'మందుల షెడ్యూల్‌ను నమోదు చేయడానికి మీ మొదటి మందును జోడించండి.' if is_te else 'Add your first medicine to start tracking your medication schedule.'}</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            display_medicines = medicines
            
            if not display_medicines:
                st.info("మందులు అందుబాటులో లేవు." if is_te else "No medicines available.")
            else:
                # Display medicines in card grid
                for m in display_medicines:
                    clean_name = re.sub(r'^(?:Medicine\s*\d+:?|\d+[\.\)]\s*|Rx:?\s*|Tab(?:let)?\.?\s*|Cap(?:sule)?\.?\s*)', '', m['name'], flags=re.IGNORECASE).strip()
                    if not clean_name:
                        clean_name = m['name']
                    display_name = display_medicine_name(clean_name, is_te)

                    with st.container():
                        img_col, info_col, status_col = st.columns([1, 4, 2])
                        with img_col:
                            img_url = m.get('image_url')
                            if img_url and (str(img_url).startswith("data:image") or str(img_url).startswith("http") or os.path.exists(str(img_url))):
                                st.image(img_url, width=64)
                            else:
                                st.markdown("<div style='font-size:36px; text-align:center;'>💊</div>", unsafe_allow_html=True)
                        with info_col:
                            st.markdown(f"### **{display_name}** ({m['dosage']})")
                            schedule_display = reminder_worker.format_medicine_schedule(
                                m.get("time_slot", ""),
                                m.get("frequency", ""),
                                m.get("before_after_food", ""),
                            )
                            if is_te:
                                schedule_labels = {
                                    "Three Times Daily": "రోజుకు మూడుసార్లు",
                                    "Twice Daily": "రోజుకు రెండుసార్లు",
                                    "Four times daily": "రోజుకు నాలుగుసార్లు",
                                    "Three times daily": "రోజుకు మూడుసార్లు",
                                    "Twice daily": "రోజుకు రెండుసార్లు",
                                    "Once daily": "రోజుకు ఒకసారి",
                                    "Before Food": "భోజనానికి ముందు",
                                    "After Food": "భోజనం తర్వాత",
                                    "With Food": "భోజనంతో పాటు",
                                    "Empty Stomach": "ఖాళీ కడుపుతో",
                                    "As Needed": "అవసరమైనప్పుడు",
                                    "As needed": "అవసరమైనప్పుడు",
                                    "Daily": "రోజుకు ఒకసారి",
                                }
                                for english_label, telugu_label in schedule_labels.items():
                                    schedule_display = re.sub(
                                        re.escape(english_label),
                                        telugu_label,
                                        schedule_display,
                                        flags=re.IGNORECASE,
                                    )
                            st.markdown(f"⏰ **{schedule_display}**")
                            if m.get('instructions') and m['instructions'].strip():
                                st.caption(m['instructions'])
                            if st.button("✏ మందును సవరించండి" if is_te else "✏ Edit medicine", key=f"edit_medicine_{m['id']}"):
                                st.session_state.edit_medicine_id = m["id"]
                                st.rerun()
                        with status_col:
                            if m['status'] == 'Taken':
                                st.success("✓ తీసుకున్నారు" if is_te else "✓ Taken")
                            elif m['status'] == 'Skipped':
                                st.warning("⏭ వదిలేశారు" if is_te else "⏭ Skipped")
                            else:
                                st.info("⏰ పెండింగ్‌లో ఉంది" if is_te else "⏰ Pending")

                        act_col1, act_col2, act_col3, act_col4 = st.columns(4)
                        with act_col1:
                            if m['status'] != 'Taken':
                                if st.button("✓ తీసుకోండి" if is_te else "✓ Take", key=f"take_{m['id']}", type="primary", use_container_width=True):
                                    now_time = datetime.datetime.now().strftime("%I:%M %p")
                                    now_date = datetime.datetime.now().strftime("%Y-%m-%d")
                                    db.log_medicine_action(user_id, m['id'], m['name'], m['dosage'], "Taken", m['time_slot'], now_time, now_date)
                                    display_action_name = display_medicine_name(m["name"], is_te)
                                    st.success(f"{display_action_name} మందు తీసుకున్నట్లు గుర్తించబడింది!" if is_te else f"Marked {m['name']} as taken!")
                                    time.sleep(0.5)
                                    st.rerun()
                        with act_col2:
                            if m['status'] == 'Pending':
                                if st.button("⏭ వదిలేయండి" if is_te else "⏭ Skip", key=f"skip_{m['id']}", use_container_width=True):
                                    now_time = datetime.datetime.now().strftime("%I:%M %p")
                                    now_date = datetime.datetime.now().strftime("%Y-%m-%d")
                                    db.log_medicine_action(user_id, m['id'], m['name'], m['dosage'], "Skipped", m['time_slot'], now_time, now_date)
                                    display_action_name = display_medicine_name(m["name"], is_te)
                                    st.warning(f"{display_action_name} మందును వదిలేశారు" if is_te else f"Skipped {m['name']}")
                                    time.sleep(0.5)
                                    st.rerun()
                        with act_col3:
                            if m['status'] != 'Pending':
                                if st.button("↺ మళ్లీ సెట్ చేయండి" if is_te else "↺ Reset", key=f"reset_{m['id']}", use_container_width=True):
                                    db.update_medicine_status(user_id, m['id'], "Pending")
                                    display_action_name = display_medicine_name(m["name"], is_te)
                                    st.info(f"{display_action_name} మందును పెండింగ్‌లోకి మార్చారు" if is_te else f"Reset {m['name']} to pending")
                                    time.sleep(0.5)
                                    st.rerun()
                        with act_col4:
                            if st.button("🗑 తొలగించండి" if is_te else "🗑 Delete", key=f"del_{m['id']}", use_container_width=True):
                                db.delete_medicine(user_id, m['id'])
                                display_action_name = display_medicine_name(m["name"], is_te)
                                st.success(f"{display_action_name} తొలగించబడింది" if is_te else f"Deleted {m['name']}")
                                time.sleep(0.5)
                                st.rerun()

                        if st.session_state.get("edit_medicine_id") == m["id"]:
                            st.markdown(f"#### {display_name} సవరించండి" if is_te else f"#### Edit {clean_name}")
                            if m.get("image_url") and (
                                str(m["image_url"]).startswith("data:image")
                                or str(m["image_url"]).startswith("http")
                                or os.path.exists(str(m["image_url"]))
                            ):
                                st.image(m["image_url"], width=96, caption="ప్రస్తుత మందు ఫోటో" if is_te else "Current medicine photo")

                            with st.form(f"edit_medicine_form_{m['id']}"):
                                edited_name = st.text_input("మందు పేరు *" if is_te else "Medicine Name *", value=m["name"], key=f"edit_name_{m['id']}")
                                edited_dosage = st.text_input("మోతాదు *" if is_te else "Dosage *", value=m["dosage"], key=f"edit_dosage_{m['id']}")
                                edited_times = st.text_input(
                                    "రిమైండర్ సమయాలు *" if is_te else "Reminder time(s) *",
                                    value=m.get("time_slot", ""),
                                    placeholder="08:00 AM, 09:00 PM",
                                    key=f"edit_times_{m['id']}",
                                )
                                edited_instructions = st.text_area(
                                    "సూచనలు" if is_te else "Instructions",
                                    value=m.get("instructions", ""),
                                    key=f"edit_instructions_{m['id']}",
                                )
                                replacement_photo = st.file_uploader(
                                    "మందు ఫోటోను మార్చండి (ఐచ్ఛికం)" if is_te else "Replace medicine photo (optional)",
                                    type=["png", "jpg", "jpeg"],
                                    key=f"edit_photo_{m['id']}",
                                )
                                save_edit, cancel_edit = st.columns(2)
                                with save_edit:
                                    save_edit_clicked = st.form_submit_button("మార్పులను సేవ్ చేయండి" if is_te else "Save Changes", type="primary", use_container_width=True)
                                with cancel_edit:
                                    cancel_edit_clicked = st.form_submit_button("రద్దు చేయండి" if is_te else "Cancel", use_container_width=True)

                            if cancel_edit_clicked:
                                st.session_state.edit_medicine_id = None
                                st.rerun()

                            if save_edit_clicked:
                                parsed_times = reminder_worker.parse_schedule_times(edited_times)
                                expected_time_count = required_daily_reminder_count(m.get("frequency", ""))
                                validation_errors = []
                                if not edited_name.strip():
                                    validation_errors.append("మందు పేరు తప్పనిసరి." if is_te else "Medicine name is required.")
                                if not edited_dosage.strip():
                                    validation_errors.append("మోతాదు తప్పనిసరి." if is_te else "Dosage is required.")
                                if expected_time_count and len(parsed_times) != expected_time_count:
                                    validation_errors.append(f"{m['frequency']} కోసం ఖచ్చితంగా {expected_time_count} వేర్వేరు సమయాలను నమోదు చేయండి." if is_te else f"Enter exactly {expected_time_count} unique time(s) for {m['frequency']}.")
                                if expected_time_count is None and str(m.get("frequency", "")).lower() != "as needed" and not parsed_times:
                                    validation_errors.append("కనీసం ఒక సరైన రిమైండర్ సమయాన్ని నమోదు చేయండి." if is_te else "Enter at least one valid reminder time.")

                                if validation_errors:
                                    for validation_error in validation_errors:
                                        st.error(validation_error)
                                else:
                                    old_food_pairs = re.findall(
                                        r"(\d{1,2}:\d{2}\s*(?:AM|PM))\s*:\s*([^;]+)",
                                        str(m.get("before_after_food", "")),
                                        re.IGNORECASE,
                                    )
                                    old_food_by_time = {time_value.upper(): timing.strip() for time_value, timing in old_food_pairs}
                                    old_food_in_order = [
                                        old_food_by_time.get(time_value.upper())
                                        for _, time_value in reminder_worker.parse_schedule_times(m.get("time_slot", ""))
                                    ]
                                    legacy_food_timing = "" if old_food_pairs else str(m.get("before_after_food", "")).strip()
                                    food_mapping = (
                                        "; ".join(
                                            f"{time_value}: {old_food_by_time.get(time_value.upper()) or (old_food_in_order[index] if index < len(old_food_in_order) and old_food_in_order[index] else 'After Food')}"
                                            for index, (_, time_value) in enumerate(parsed_times)
                                        )
                                        if old_food_pairs else legacy_food_timing
                                    ) or "As needed"
                                    replacement_photo_data = None
                                    if replacement_photo:
                                        photo_bytes = base64.b64encode(replacement_photo.getvalue()).decode("ascii")
                                        replacement_photo_data = f"{replacement_photo.type};base64,{photo_bytes}"
                                        replacement_photo_data = f"data:{replacement_photo_data}"

                                    updated = db.update_medicine(
                                        user_id,
                                        m["id"],
                                        edited_name.strip(),
                                        edited_dosage.strip(),
                                        ", ".join(time_value for _, time_value in parsed_times),
                                        edited_instructions.strip(),
                                        m.get("frequency", "Daily"),
                                        food_mapping,
                                        replacement_photo_data,
                                    )
                                    if updated:
                                        st.session_state.edit_medicine_id = None
                                        st.success(f"{edited_name.strip()} వివరాలు నవీకరించబడ్డాయి." if is_te else f"Updated {edited_name.strip()}.")
                                        st.rerun()
                                    else:
                                        st.error("మందును నవీకరించలేకపోయాం. పేజీని రిఫ్రెష్ చేసి మళ్లీ ప్రయత్నించండి." if is_te else "Medicine could not be updated. Refresh and try again.")

                        st.divider()

    # --- 3. PRESCRIPTION OCR & AI PARSING PAGE ---
    elif page == "Prescriptions":
        st.markdown("## 📋 ప్రిస్క్రిప్షన్ అప్‌లోడ్ చేయండి" if is_te else "## 📋 Upload Prescription")

        if st.session_state.rx_step == 1:
            rx_tab1, rx_tab2 = st.tabs(["📎 ఫైల్ జోడించండి", "📷 ఫోటో తీయండి"] if is_te else ["📎 Attach File", "📷 Take Photo"])
            
            rx_file_tuple = None
            
            with rx_tab1:
                uploaded_f = st.file_uploader("ప్రిస్క్రిప్షన్ ఫైల్‌ను అప్‌లోడ్ చేయండి (JPG, JPEG, PNG, PDF)" if is_te else "Upload Prescription File (JPG, JPEG, PNG, PDF)", type=["jpg", "jpeg", "png", "pdf"], key="rx_attach_uploader")
                if uploaded_f:
                    rx_file_tuple = (uploaded_f, uploaded_f.name)
            
            with rx_tab2:
                camera_f = st.camera_input("ప్రిస్క్రిప్షన్ ఫోటో తీయండి" if is_te else "Take Photo of Prescription", key="rx_camera_capture")
                if camera_f:
                    rx_file_tuple = (camera_f, "camera_prescription.jpg")
            
            if rx_file_tuple:
                file_obj, file_name = rx_file_tuple
                rx_file_bytes = file_obj.getvalue()
                upload_digest = hashlib.sha256(rx_file_bytes).hexdigest()
                
                if upload_digest != st.session_state.get("rx_uploaded_digest"):
                    st.session_state.rx_extracted_list = []
                    st.session_state.rx_raw_text = ""
                    st.session_state.rx_uploaded_digest = upload_digest
                    saved_path = storage.upload_path(
                        "prescriptions", f"rx_{upload_digest[:12]}_{file_name}"
                    )
                    with open(saved_path, "wb") as f:
                        f.write(rx_file_bytes)
                    st.session_state.rx_file_path = saved_path

                saved_path = st.session_state.rx_file_path

                st.success("✅ ప్రిస్క్రిప్షన్ నుంచి వివరాలు తీసుకోవడానికి సిద్ధంగా ఉంది!" if is_te else "✅ Prescription ready for extraction!")
                if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    st.image(file_obj, caption="ప్రిస్క్రిప్షన్ ప్రివ్యూ" if is_te else "Prescription Preview", width=300)
                else:
                    st.info(f"📄 పత్రం జోడించబడింది: {file_name}" if is_te else f"📄 Document attached: {file_name}")

                if st.button("AIతో మందుల వివరాలను గుర్తించండి ✨" if is_te else "Extract Medicines with AI ✨", type="primary", use_container_width=True):
                    with st.spinner("ప్రిస్క్రిప్షన్‌లోని పాఠ్యాన్ని తీసుకుని AIతో విశ్లేషిస్తున్నాం..." if is_te else "Extracting prescription text and analyzing with AI..."):
                        try:
                            raw_text = ocr.extract_raw_text(saved_path, file_name)
                            extracted_list = ocr.parse_prescription_text_with_llm(raw_text, file_name)
                            
                            st.session_state.rx_raw_text = raw_text
                            st.session_state.rx_extracted_list = extracted_list
                            st.session_state.rx_step = 2
                            st.rerun()
                        except Exception as e:
                            st.error(f"ప్రిస్క్రిప్షన్ నుంచి వివరాలను చదవలేకపోయాం: {str(e)}" if is_te else f"OCR extraction failed: {str(e)}")
                            st.info("మరింత స్పష్టమైన చిత్రాన్ని ప్రయత్నించండి లేదా మందులను చేతితో నమోదు చేయండి." if is_te else "Please try a clearer image or enter medicines manually.")

        elif st.session_state.rx_step == 2:
            st.markdown("### 📋 గుర్తించిన మందులను సమీక్షించండి" if is_te else "### 📋 Review Extracted Medicines")
            st.caption("నా మందులలో సేవ్ చేయడానికి ముందు గుర్తించిన వివరాలను పరిశీలించండి:" if is_te else "Review extracted fields before saving to My Medicines:")

            updated_list = []
            for idx, med_item in enumerate(st.session_state.rx_extracted_list):
                clean_default_name = re.sub(r'^(?:Medicine\s*\d+:?|\d+[\.\)]\s*|Rx:?\s*|Tab(?:let)?\.?\s*|Cap(?:sule)?\.?\s*)', '', med_item.get("name", ""), flags=re.IGNORECASE).strip() or med_item.get("name", "")
                
                with st.expander(f"💊 మందు {idx + 1}: {clean_default_name}" if is_te else f"💊 Medicine {idx + 1}: {clean_default_name}", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_name = st.text_input(
                            "మందు పేరు *" if is_te else "Medicine Name *",
                            value=clean_default_name,
                            key=f"rx_e_name_{idx}"
                        )
                        
                        frequency_options = ["Once daily", "Twice daily", "Three times daily", "Four times daily", "As Needed", "Not specified"]
                        prescription_frequency_labels = {
                            "Once daily": "రోజుకు ఒకసారి",
                            "Twice daily": "రోజుకు రెండుసార్లు",
                            "Three times daily": "రోజుకు మూడుసార్లు",
                            "Four times daily": "రోజుకు నాలుగుసార్లు",
                            "As Needed": "అవసరమైనప్పుడు",
                            "Not specified": "పేర్కొనలేదు",
                        }
                        curr_freq = med_item.get("frequency", "Once daily")
                        freq_index = next((i for i, opt in enumerate(frequency_options) if opt.casefold() == curr_freq.casefold()), 0)
                        
                        e_freq = st.selectbox(
                            "తరచుదనం *" if is_te else "Frequency *",
                            frequency_options,
                            format_func=lambda value: prescription_frequency_labels.get(value, value) if is_te else value,
                            index=freq_index,
                            key=f"rx_e_freq_{idx}"
                        )

                    with col2:
                        e_dos = st.text_input(
                            "మోతాదు *" if is_te else "Dosage *",
                            value=med_item.get("dosage", "Not specified"),
                            key=f"rx_e_dos_{idx}"
                        )

                        f_lower = e_freq.lower()
                        num_slots = 4 if "four" in f_lower or "4" in f_lower else (3 if "three" in f_lower or "3" in f_lower else (2 if "twice" in f_lower or "2" in f_lower else 1))

                    times_list = re.findall(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", str(med_item.get("time_slot", "")), re.IGNORECASE)
                    preset_choices = ["08:00 AM", "09:00 AM", "12:00 PM", "12:30 PM", "01:30 PM", "05:00 PM", "08:00 PM", "09:00 PM"]

                    st.markdown(f"**⏰ సమయాలు ({num_slots}):**" if is_te else f"**⏰ Time Slots ({num_slots}):**")
                    
                    slot_cols = st.columns(num_slots)
                    new_times = []
                    for s_i in range(num_slots):
                        default_t = "09:00 AM" if s_i == 0 else ("09:00 PM" if s_i == 1 else ("01:30 PM" if s_i == 2 else "05:00 PM"))
                        if num_slots == 3:
                            default_t = "08:00 AM" if s_i == 0 else ("01:30 PM" if s_i == 1 else "09:00 PM")
                        elif num_slots == 4:
                            default_t = "08:00 AM" if s_i == 0 else ("12:00 PM" if s_i == 1 else ("05:00 PM" if s_i == 2 else "09:00 PM"))

                        curr_t = times_list[s_i] if s_i < len(times_list) else default_t
                        def_idx = 0
                        for p_idx, p_val in enumerate(preset_choices):
                            if p_val.upper() in curr_t.upper():
                                def_idx = p_idx
                                break
                        
                        with slot_cols[s_i]:
                            t_sel = st.selectbox(
                                f"సమయం {s_i + 1} *" if is_te else f"Time {s_i + 1} *",
                                preset_choices,
                                index=def_idx,
                                key=f"rx_slot_sel_{idx}_{s_i}"
                            )
                            new_times.append(t_sel)

                    e_slot = ", ".join(list(dict.fromkeys(new_times)))

                    rx_m_photo = st.file_uploader(
                        f"📷 {e_name} కోసం మందు / మాత్ర ఫోటో అప్‌లోడ్ చేయండి (ఐచ్ఛికం)" if is_te else f"📷 Upload Medicine / Tablet Image (Optional) for {e_name}",
                        type=["png", "jpg", "jpeg"],
                        key=f"rx_img_upload_{idx}"
                    )

                    rx_img_url = None
                    if rx_m_photo:
                        t_filename = f"tablet_rx_{int(time.time())}_{idx}_{rx_m_photo.name}"
                        t_path = storage.upload_path("tablets", t_filename)
                        os.makedirs(os.path.dirname(t_path), exist_ok=True)
                        with open(t_path, "wb") as f:
                            f.write(rx_m_photo.read())
                        b64_img = base64.b64encode(open(t_path, "rb").read()).decode()
                        rx_img_url = f"data:image/jpeg;base64,{b64_img}"

                    updated_list.append({
                        "name": e_name,
                        "dosage": e_dos,
                        "frequency": e_freq,
                        "time_slot": e_slot,
                        "before_after_food": "",
                        "instructions": "",
                        "image_url": rx_img_url
                    })

            st.markdown("<br>", unsafe_allow_html=True)
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if st.button("← రద్దు చేసి మళ్లీ అప్‌లోడ్ చేయండి" if is_te else "← Cancel & Re-upload", type="secondary", use_container_width=True):
                    st.session_state.rx_step = 1
                    st.session_state.rx_file_path = ""
                    st.session_state.rx_uploaded_digest = ""
                    st.session_state.rx_extracted_list = []
                    st.session_state.rx_raw_text = ""
                    st.rerun()

            with btn_c2:
                if st.button("అన్ని మందులను సేవ్ చేయండి ✅" if is_te else "Save All Medicines ✅", type="primary", use_container_width=True):
                    validation_passed = True
                    for med in updated_list:
                        if not med.get("name"):
                            validation_passed = False
                            st.error("ప్రతి మందుకు పేరు తప్పనిసరిగా ఉండాలి." if is_te else "Every medicine must have a name.")
                            break
                    
                    if validation_passed:
                        file_path = st.session_state.rx_file_path
                        fn = os.path.basename(file_path) if file_path else "Prescription"
                        rx_db_id = db.add_prescription(user_id, fn, file_path, st.session_state.rx_raw_text, updated_list)

                        def_img = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23f0fdf4' rx='16'/><circle cx='100' cy='100' r='45' fill='%23166534'/><text x='100' y='180' font-size='14' text-anchor='middle' fill='%23166534' font-family='sans-serif' font-weight='bold'>Rx</text></svg>"
                        for med_data in updated_list:
                            med_img = med_data.get("image_url") or def_img
                            db.add_medicine(user_id, med_data["name"], med_data["dosage"], med_data["time_slot"], "", med_data["frequency"], "", med_img)

                        st.session_state.rx_step = 3
                        st.rerun()

        elif st.session_state.rx_step == 3:
            st.success("🎉 ప్రిస్క్రిప్షన్ నిర్ధారించబడింది! మందులు నా మందుల జాబితాలో జోడించబడ్డాయి, షెడ్యూల్‌లు కూడా సిద్ధమయ్యాయి." if is_te else "🎉 Prescription confirmed! Confirmed medicines have been added to My Medicines and schedules created.")
            if st.button("నా మందులను చూడండి →" if is_te else "View My Medicines →", type="primary"):
                st.session_state.rx_step = 1
                st.session_state.current_page = "Medicines"
                st.rerun()

    # --- 4. HEALTH VITALS & TRACKING PAGE ---
    elif page == "Health":
        is_te = st.session_state.lang_code == "te-IN"
        st.markdown("## 🩺 " + ("నా ఆరోగ్యం మరియు రోజువారీ ఆరోగ్య కొలతలు" if is_te else "My Health & Daily Vitals Tracking"))
        st.caption("మీ రక్తపోటు మరియు రక్తంలో చక్కెర రీడింగ్‌లను నమోదు చేసి ట్రాక్ చేయండి." if is_te else "Record and track your Blood Pressure and Blood Sugar readings.")

        # Vitals Input Form with enhanced validation
        st.markdown("### " + ("కొత్త ఆరోగ్య రీడింగ్ నమోదు చేయండి" if is_te else "Record New Vitals Reading"))
        
        with st.form("health_metrics_form"):
            h_col1, h_col2 = st.columns(2)
            
            with h_col1:
                st.markdown("#### 🩸 " + ("రక్తపోటు" if is_te else "Blood Pressure"))
                sys_val = st.number_input("సిస్టోలిక్ (పై సంఖ్య) *" if is_te else "Systolic (top number) *", min_value=70, max_value=220, value=120, key="bp_sys")
                dia_val = st.number_input("డయాస్టోలిక్ (కింది సంఖ్య) *" if is_te else "Diastolic (bottom number) *", min_value=40, max_value=140, value=80, key="bp_dia")
                
                # Real-time status calculation
                bp_status = "Optimal"
                bp_color = "#166534"
                if sys_val >= 140 or dia_val >= 90:
                    bp_status = "High"
                    bp_color = "#dc2626"
                elif sys_val < 90 or dia_val < 60:
                    bp_status = "Low"
                    bp_color = "#ea580c"
                elif sys_val > 120 or dia_val > 80:
                    bp_status = "Elevated"
                    bp_color = "#ca8a04"
                
                st.markdown(f"""
                    <div style='margin-top:8px; padding:8px 12px; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px;'>
                        <span style='font-size:12px; color:#64748b;'>{'స్థితి:' if is_te else 'Status:'}</span>
                        <span style='font-size:13px; font-weight:600; color:{bp_color}; margin-left:8px;'>{({'Optimal': 'సరైన స్థాయి', 'High': 'అధికం', 'Low': 'తక్కువ', 'Elevated': 'పెరిగింది'}.get(bp_status, bp_status) if is_te else bp_status)}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            with h_col2:
                st.markdown("#### 🍬 " + ("రక్తంలో చక్కెర" if is_te else "Blood Sugar"))
                bs_val = st.number_input("రక్తంలో చక్కెర (mg/dL) *" if is_te else "Blood Sugar (mg/dL) *", min_value=50, max_value=400, value=98, key="bs_val")
                bs_type_labels = {
                    "Fasting": "ఉపవాసం",
                    "Post-prandial (After meal)": "భోజనం తర్వాత",
                }
                bs_type = st.selectbox(
                    "రీడింగ్ రకం *" if is_te else "Reading Type *",
                    ["Fasting", "Post-prandial (After meal)"],
                    format_func=lambda value: bs_type_labels.get(value, value) if is_te else value,
                    key="bs_type",
                )
                bs_note = bs_type
                
                # Real-time status calculation
                bs_status = "Normal"
                bs_color = "#166534"
                if bs_note == "Fasting":
                    if bs_val >= 126:
                        bs_status = "High"
                        bs_color = "#dc2626"
                    elif bs_val < 70:
                        bs_status = "Low"
                        bs_color = "#ea580c"
                else:
                    if bs_val >= 200:
                        bs_status = "High"
                        bs_color = "#dc2626"
                    elif bs_val < 140:
                        bs_status = "Low"
                        bs_color = "#ea580c"
                
                st.markdown(f"""
                    <div style='margin-top:8px; padding:8px 12px; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px;'>
                        <span style='font-size:12px; color:#64748b;'>{'స్థితి:' if is_te else 'Status:'}</span>
                        <span style='font-size:13px; font-weight:600; color:{bs_color}; margin-left:8px;'>{({'Normal': 'సాధారణం', 'High': 'అధికం', 'Low': 'తక్కువ'}.get(bs_status, bs_status) if is_te else bs_status)}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            # Date field (auto-populated with today)
            record_date = st.date_input("రీడింగ్ తేదీ" if is_te else "Record Date", value=datetime.datetime.now().date(), key="record_date")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.form_submit_button("💾 అన్ని రీడింగ్‌లను సేవ్ చేయండి" if is_te else "💾 Save All Readings", type="primary", use_container_width=True):
                # Validation
                if not sys_val or not dia_val or not bs_val:
                    st.error("దయచేసి అవసరమైన అన్ని వివరాలను నమోదు చేయండి (*)." if is_te else "Please fill in all required fields (*)")
                else:
                    try:
                        db.save_health_vitals(
                            user_id,
                            f"{sys_val}/{dia_val}",
                            bp_status,
                            str(bs_val),
                            bs_status,
                            bs_note,
                            record_date.isoformat(),
                        )
                        saved = db.get_health_metrics_for_date(user_id, record_date.isoformat())
                    except sqlite3.Error:
                        logging.exception("Failed to save health vitals for user %s", user_id)
                        st.error("ఆరోగ్య వివరాలను సేవ్ చేయలేకపోయాం. మళ్లీ ప్రయత్నించండి." if is_te else "Could not save the health readings. Please try again.")
                    else:
                        if saved.get("Blood Pressure", {}).get("value") != f"{sys_val}/{dia_val}" or saved.get("Blood Sugar", {}).get("value") != str(bs_val):
                            st.error("ఆరోగ్య రీడింగ్‌లను ధృవీకరించలేకపోయాం. మళ్లీ ప్రయత్నించండి." if is_te else "The saved readings could not be verified. Please try again.")
                        else:
                            st.success("✅ ఆరోగ్య రీడింగ్‌లు విజయవంతంగా సేవ్ అయ్యాయి!" if is_te else "✅ All health readings saved successfully!")
                            time.sleep(1)
                            st.rerun()

        st.markdown("---")
        st.markdown("### " + ("ఆరోగ్య కొలతల చరిత్ర చార్ట్‌లు" if is_te else "Health Metrics History Charts"))
        
        # Date range selector
        time_options = ["7 Days", "30 Days", "90 Days", "All Time"]
        time_labels_te = {
            "7 Days": "గత 7 రోజులు",
            "30 Days": "గత 30 రోజులు",
            "90 Days": "గత 90 రోజులు",
            "All Time": "మొత్తం కాలం",
        }
        time_filter = st.selectbox(
            "కాల వ్యవధి" if is_te else "Time Range",
            time_options,
            format_func=lambda value: time_labels_te.get(value, value) if is_te else value,
            key="time_filter",
        )
        days_cnt = {time_options[0]: 7, time_options[1]: 30, time_options[2]: 90, time_options[3]: 365}[time_filter]

        history_rows = db.get_health_history_for_charts(user_id, days=days_cnt)

        if not history_rows:
            st.markdown(f"""
                <div style='text-align:center; padding:48px 24px; color:#64748b;'>
                    <div style='font-size:48px; margin-bottom:16px;'>📊</div>
                    <h4 style='color:#0f172a; font-size:18px; font-weight:600; margin-bottom:8px;'>{'ఇంకా ఆరోగ్య వివరాలు లేవు' if is_te else 'No health data yet'}</h4>
                    <p style='font-size:14px; line-height:1.5; margin:0;'>{'ఆరోగ్య ధోరణులను చూడటానికి మీ రీడింగ్‌లను నమోదు చేయండి.' if is_te else 'Start recording your vitals to see your health trends here.'}</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            bp_records = [r for r in history_rows if r['metric_name'] == 'Blood Pressure']
            sugar_records = [r for r in history_rows if r['metric_name'] == 'Blood Sugar']

            st.markdown("#### " + ("రక్తపోటు ధోరణి" if is_te else "BLOOD PRESSURE TREND"))
            daily_bp = {}
            for reading in sorted(bp_records, key=lambda row: (str(row.get("recorded_date", "")), int(row.get("id") or 0))):
                date_value = pd.to_datetime(reading.get("recorded_date"), errors="coerce")
                bp_match = re.fullmatch(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", str(reading.get("value", "")))
                if pd.isna(date_value) or not bp_match:
                    continue
                date_key = date_value.strftime("%Y-%m-%d")
                daily_bp[date_key] = {
                    "Systolic": int(bp_match.group(1)),
                    "Diastolic": int(bp_match.group(2)),
                }
            if daily_bp:
                date_labels = health_chart_date_labels(daily_bp, is_te)
                chart_data = [
                    {"Date": date_labels[date_key], **reading}
                    for date_key, reading in daily_bp.items()
                ]
                render_blood_pressure_chart(pd.DataFrame(chart_data), is_te)
            else:
                st.info("ఈ కాలానికి సరైన రక్తపోటు రీడింగ్‌లు నమోదు కాలేదు." if is_te else "No valid Blood Pressure readings recorded for this time range.")

            st.markdown("#### " + ("రక్తంలో చక్కెర ధోరణి" if is_te else "BLOOD SUGAR TREND"))
            daily_sugar = {}
            for reading in sorted(sugar_records, key=lambda row: (str(row.get("recorded_date", "")), int(row.get("id") or 0))):
                date_value = pd.to_datetime(reading.get("recorded_date"), errors="coerce")
                if pd.isna(date_value):
                    continue
                notes = str(reading.get("notes", "")).lower()
                if "fasting" in notes or "before food" in notes or "before meal" in notes:
                    reading_type = "Before Food"
                elif any(term in notes for term in ["post-prandial", "post prandial", "after food", "after meal"]):
                    reading_type = "After Food"
                else:
                    continue
                try:
                    sugar_value = float(re.sub(r"[^\d.]", "", str(reading.get("value", ""))))
                except ValueError:
                    continue
                date_key = date_value.strftime("%Y-%m-%d")
                daily_sugar[(date_key, reading_type)] = {
                    "DateKey": date_key,
                    "Reading": reading_type,
                    "Value": sugar_value,
                }
            if daily_sugar:
                date_keys = list(dict.fromkeys(row["DateKey"] for row in daily_sugar.values()))
                date_labels = health_chart_date_labels(date_keys, is_te)
                chart_data = [
                    {"Date": date_labels[reading["DateKey"]], "Reading": reading["Reading"], "Value": reading["Value"]}
                    for reading in daily_sugar.values()
                ]
                if is_te:
                    for entry in chart_data:
                        entry["Reading"] = "భోజనానికి ముందు" if entry["Reading"] == "Before Food" else "భోజనం తర్వాత"
                render_blood_sugar_chart(pd.DataFrame(chart_data), is_te)
            else:
                st.info("ఈ కాలానికి భోజనానికి ముందు లేదా తర్వాత తీసుకున్న చక్కెర రీడింగ్‌లు లేవు." if is_te else "No Blood Sugar readings with before-food or after-food timing recorded for this time range.")
            
            st.markdown("<br>", unsafe_allow_html=True)

    # --- 6. DIET GUIDANCE PAGE ---
    elif page == "Diet":
        is_te = st.session_state.lang_code == "te-IN"
        diet_title = "🥗 వ్యక్తిగతీకరించిన భారతీయ పోషకాహార ప్లాన్" if is_te else "🥗 Personalized Indian Nutrition & Diet Guidance"
        diet_sub = "మీ ప్రతిరోజూ మారే రక్తపోటు మరియు రక్తంలో చక్కెర ఆధారంగా ఈ ఆహార ప్లాన్ అందించబడుతుంది." if is_te else "CareVoice customizes your daily Indian meals based on your specific Blood Pressure and Blood Sugar readings."
        
        st.markdown(f"## {diet_title}")
        st.caption(diet_sub)

        today = datetime.date.today()
        health_profile = db.get_health_metrics_for_date(user_id, today.isoformat())

        if not health_profile:
            no_rec_msg = "ఈ రోజు ఆరోగ్య రీడింగ్ నమోదు చేయండి; ఈ రోజు రీడింగ్‌ల ఆధారంగానే ఆహార ప్రణాళిక రూపొందుతుంది." if is_te else "Record a health reading today. Your diet plan is based only on readings recorded today."
            st.info(no_rec_msg)
        else:
            # Display Health Vitals Summary Banner
            bp_val = health_profile.get("Blood Pressure", {}).get("value", "N/A")
            bs_val = health_profile.get("Blood Sugar", {}).get("value", "N/A")

            st.markdown(f"""
                <div style='background:#ffffff; border:1px solid #166534; border-radius:12px; padding:16px; margin:16px 0; box-shadow:0 2px 8px rgba(0,0,0,0.04);'>
                    <div style='font-size:14px; font-weight:700; color:#166534; margin-bottom:10px;'>📊 {"మీ తాజా ఆరోగ్య రీడింగ్స్ (భోజన ప్రణాళిక ఆధారం):" if is_te else "Your Recorded Vitals (Diet Plan Target):"}</div>
                    <div style='display:flex; flex-wrap:wrap; gap:16px; justify-content:space-between;'>
                        <div style='background:#f0fdf4; padding:8px 16px; border-radius:8px; border:1px solid #bbf7d0;'>
                            <span style='font-size:12px; color:#166534; font-weight:600;'>🩸 BP:</span> 
                            <span style='font-size:14px; font-weight:700; color:#0f172a;'>{bp_val} mmHg</span>
                        </div>
                        <div style='background:#f0fdf4; padding:8px 16px; border-radius:8px; border:1px solid #bbf7d0;'>
                            <span style='font-size:12px; color:#166534; font-weight:600;'>🍬 Sugar:</span> 
                            <span style='font-size:14px; font-weight:700; color:#0f172a;'>{bs_val} mg/dL</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("### " + ("ఈ రోజు ఆహార ప్రణాళిక" if is_te else "Today's Diet"))
            st.caption(today.strftime("%A, %B %d, %Y"))

            preference_options = ["Vegetarian", "Vegan", "Eggetarian", "No restrictions"]
            preference_labels_te = {
                "Vegetarian": "శాకాహారం",
                "Vegan": "పూర్తి శాకాహారం",
                "Eggetarian": "గుడ్లతో కూడిన శాకాహారం",
                "No restrictions": "ప్రత్యేక పరిమితులు లేవు",
            }
            dietary_preference = st.selectbox(
                "ఆహార అభిరుచి" if is_te else "Dietary preference",
                preference_options,
                format_func=lambda value: preference_labels_te.get(value, value) if is_te else value,
                key="dietary_preference",
            )
            force_new = st.button(
                "🔄 " + ("కొత్త వెరైటీ" if is_te else "Refresh today's menu"),
                type="secondary",
            )

            profile_key = json.dumps({
                "date": today.isoformat(),
                "dietary_preference": dietary_preference,
                "metrics": {
                    name: {
                        "value": reading.get("value"),
                        "unit": reading.get("unit"),
                        "recorded_date": reading.get("recorded_date"),
                    }
                    for name, reading in health_profile.items()
                },
            }, sort_keys=True)

            cached_plan = st.session_state.get("diet_plan_today", [])
            diet_items = cached_plan if (st.session_state.get("diet_plan_today_key") == profile_key and not force_new) else []

            if not diet_items or force_new:
                try:
                    with st.spinner("సాంప్రదాయ భారతీయ ఆరోగ్యకరమైన ఆహారాన్ని సిద్ధం చేస్తోంది..." if is_te else "Preparing today's Indian menu from your latest readings..."):
                        diet_items = ai.generate_personalized_diet(
                            user_id=user_id,
                            user_name=user_name,
                            lang_code=st.session_state.lang_code,
                            force_refresh=force_new,
                            dietary_preference=dietary_preference,
                            plan_date=today.isoformat(),
                        )
                    st.session_state["diet_plan_today"] = diet_items
                    st.session_state["diet_plan_today_key"] = profile_key
                except (RuntimeError, ValueError) as error:
                    st.error(f"ఆహార ప్రణాళికను సిద్ధం చేయలేకపోయాం: {error}" if is_te else str(error))

            if diet_items:
                meal_icons = {"Breakfast": "🌅", "Mid-morning": "🍎", "ఉదయం ఉపహారం (Breakfast)": "🌅", "Lunch": "☀️", "మధ్యాహ్న భోజనం (Lunch)": "☀️", "Evening Snack": "☕", "సాయంత్రం తినుబండారాలు (Evening Snack)": "☕", "Dinner": "🌙", "రాత్రి భోజనం (Dinner)": "🌙", "Hydration": "💧"}
                meal_labels_te = {"Breakfast": "ఉదయం అల్పాహారం", "Mid-morning": "మధ్యాహ్నానికి ముందు", "Lunch": "మధ్యాహ్న భోజనం", "Evening Snack": "సాయంత్రం చిరుతిండి", "Dinner": "రాత్రి భోజనం", "Hydration": "నీరు / హైడ్రేషన్"}
                
                for index, d in enumerate(diet_items):
                    m_time = d.get('meal_time', 'Meal')
                    icon = meal_icons.get(m_time, "🍲")
                    display_meal_time = meal_labels_te.get(m_time, m_time) if is_te else m_time
                    meal_col, calories_col = st.columns([5, 1])
                    with meal_col:
                        st.markdown(f"##### {icon} {display_meal_time}")
                        st.markdown(f"**{d['food_item']}**")
                        st.caption(f"💡 **{'ఆరోగ్య ప్రయోజనం:' if is_te else 'Health Benefit:'}** {d['notes']}")
                    if d.get('calories'):
                        calories_col.markdown(
                            f"<p style='text-align:right; color:#166534; font-weight:600; margin:8px 0 0;'>{d['calories']} kcal</p>",
                            unsafe_allow_html=True,
                        )
                    if index < len(diet_items) - 1:
                        st.divider()

            st.caption(
                "ℹ️ గమనిక: ఇది మీ తాజా ఆరోగ్య రీడింగ్స్ ఆధారంగా రూపొందించిన సాధారణ ఆహార మార్గదర్శకం. వైద్య లేదా పోషకాహార నిపుణుల సూచనలను అనుసరించండి."
                if is_te else
                "ℹ️ General dietary guidance based on your latest health readings. Follow advice from your doctor or nutritionist."
            )

    # --- 5. VOICE ASSISTANT PAGE ---
    elif page == "Voice Assistant":
        render_voice_assistant_box("hub")

    # --- 10. SETTINGS PAGE ---
    elif page == "Settings":
        is_te = st.session_state.lang_code == "te-IN"
        st.markdown("## ⚙️ " + ("ఖాతా మరియు యాప్ సెట్టింగ్‌లు" if is_te else "Account & Application Settings"))
        
        st.markdown("### 👤 " + ("వినియోగదారు ప్రొఫైల్" if is_te else "User Profile"))
        st.write(f"{'పేరు' if is_te else 'Name'}: **{user_name}**")
        st.write(f"{'ఇమెయిల్' if is_te else 'Email'}: **{user['email']}**")
        st.write(f"{'ఎంచుకున్న భాష' if is_te else 'Active Language'}: **{'తెలుగు' if is_te and st.session_state.lang_code == 'te-IN' else st.session_state.lang_code}**")
        st.write(f"{'వృద్ధుల మోడ్' if is_te else 'Elderly Mode'}: **{('ప్రారంభించబడింది' if st.session_state.elderly_mode else 'నిలిపివేయబడింది') if is_te else ('Enabled' if st.session_state.elderly_mode else 'Disabled')}**")
        st.write(f"{'వాయిస్ రకం' if is_te else 'Voice Gender'}: **{('మహిళా వాయిస్' if 'female' in str(st.session_state.voice_gender).lower() else 'పురుష వాయిస్') if is_te else st.session_state.voice_gender}**")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🎙️ " + ("వాయిస్ ప్రాధాన్యత" if is_te else "Voice Preference"))
        cur_gender_idx = 0 if "female" in str(st.session_state.voice_gender).lower() or "girl" in str(st.session_state.voice_gender).lower() else 1
        voice_options = ["Female Voice", "Male Voice"]
        voice_labels_te = {"Female Voice": "మహిళా వాయిస్", "Male Voice": "పురుష వాయిస్"}
        sel_v = st.selectbox(
            "వాయిస్ సహాయకుడి వాయిస్" if is_te else "Voice Assistant Gender",
            voice_options,
            index=cur_gender_idx,
            format_func=lambda value: voice_labels_te.get(value, value) if is_te else value,
            key="settings_voice_gender_sel",
        )
        if sel_v != st.session_state.voice_gender:
            st.session_state.voice_gender = sel_v
            db.update_user_preferences(user_id, voice_gender=sel_v)
            st.success(f"వాయిస్ ప్రాధాన్యత {voice_labels_te.get(sel_v, sel_v)}గా మార్చబడింది." if is_te else f"Voice preference updated to {sel_v}!")
            st.rerun()

        st.markdown("---")
        st.markdown("### 🔔 " + ("వాయిస్ రిమైండర్‌లు" if is_te else "Voice Reminders"))
        st.caption("ఈ ట్యాబ్ క్రియాశీలంగా లేకున్నా షెడ్యూల్ చేసిన మందుల రిమైండర్‌ల కోసం బ్రౌజర్ నోటిఫికేషన్‌లను ప్రారంభించండి." if is_te else "Enable browser notifications for scheduled medicine reminders, including when this tab is inactive.")
        if st.session_state.get("push_setup_message"):
            st.success(st.session_state.push_setup_message)

        st.markdown("---")
        st.markdown("### 🔒 భద్రత మరియు పాస్‌వర్డ్ రీసెట్" if is_te else "### 🔒 Security & Password Reset")
        with st.expander("ఖాతా పాస్‌వర్డ్ మార్చండి" if is_te else "Change Account Password"):
            with st.form("change_pw_form"):
                c_ans = st.text_input("భద్రతా సమాధానం ('మీ ప్రధాన ఆరోగ్య లక్ష్యం ఏమిటి?')" if is_te else "Security Answer ('What is your primary health focus?')", value="wellness")
                c_new_pw = st.text_input("కొత్త పాస్‌వర్డ్" if is_te else "New Password", type="password")
                if st.form_submit_button("పాస్‌వర్డ్‌ను నవీకరించండి" if is_te else "Update Password", type="primary"):
                    if not c_new_pw:
                        st.error("దయచేసి కొత్త పాస్‌వర్డ్‌ను నమోదు చేయండి." if is_te else "Please enter a new password.")
                    else:
                        ok, msg = db.reset_password(user['email'], c_ans, c_new_pw)
                        if ok:
                            st.success(_localized_auth_message(msg, is_te))
                        else:
                            st.error(_localized_auth_message(msg, is_te))

# MAIN ROUTER ACCORDING TO VIEW STATE
if st.session_state.view == "landing":
    render_landing_page()
elif st.session_state.view == "login":
    render_login_page()
elif st.session_state.view == "signup":
    render_signup_page()
elif st.session_state.view == "reset_password":
    render_reset_password_page()
elif st.session_state.view == "onboarding":
    render_onboarding_page()
elif st.session_state.view == "app":
    if not st.session_state.user:
        st.session_state.view = "landing"
        st.rerun()
    else:
        render_authenticated_app()

st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#94a3b8; font-size:13px;'>CareVoice • ఆరోగ్య సేవా యాప్</p>" if str(st.session_state.lang_code).startswith("te") else
    "<p style='text-align:center; color:#94a3b8; font-size:13px;'>CareVoice • Real Healthcare Web Application</p>",
    unsafe_allow_html=True,
)