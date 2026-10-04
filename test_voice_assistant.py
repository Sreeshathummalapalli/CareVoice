import datetime
from types import SimpleNamespace

from backend import ai_services


def test_today_medicine_doses_uses_today_logs_instead_of_stale_medicine_status(monkeypatch):
    now = datetime.datetime(2026, 10, 2, 10, 0)
    monkeypatch.setattr(ai_services.db, "get_all_medicines", lambda user_id: [{
        "id": 8,
        "name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "time_slot": "08:00 AM, 09:00 PM",
        "frequency": "Twice Daily",
        "status": "Taken",
    }])
    monkeypatch.setattr(ai_services.db, "get_medicine_history", lambda user_id: [{
        "id": 19,
        "medicine_id": 8,
        "medicine_name": "Paracetamol",
        "status": "Taken",
        "scheduled_time": "08:00 AM",
        "date": "2026-10-02",
    }])

    doses = ai_services.get_today_medicine_doses(3, now)

    assert [(dose["scheduled_time"], dose["status"]) for dose in doses] == [
        ("08:00 AM", "Taken"),
        ("09:00 PM", "Pending"),
    ]


def test_voice_today_schedule_answer_uses_database_dose_data(monkeypatch):
    monkeypatch.setattr(ai_services, "get_today_medicine_doses", lambda user_id: [{
        "name": "Paracetamol",
        "dosage": "500 mg, 1 tablet",
        "scheduled_time": "08:00 AM",
        "status": "Pending",
    }])

    reply, destination = ai_services.process_voice_assistant_query(
        "What medicines do I have today?", 3, "Sreesha", "en-IN"
    )

    assert "Paracetamol (500 mg, 1 tablet) at 08:00 AM" in reply
    assert destination == "Medicines"


def test_voice_assistant_retries_with_supported_model(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs["model"] == "qwen/qwen3.8-27b":
                raise RuntimeError("temporary model failure")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content="CareVoice can help with everyday health questions."
            ))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(ai_services, "get_groq_client", lambda: fake_client)
    monkeypatch.setattr(ai_services, "get_today_medicine_doses", lambda user_id: [])
    monkeypatch.setattr(ai_services.db, "get_latest_health_metrics", lambda user_id: {})
    monkeypatch.setattr(ai_services.db, "get_medicine_history", lambda user_id: [])

    reply, destination = ai_services.process_voice_assistant_query(
        "What can CareVoice help me with?", 3, "Sreesha", "en-IN"
    )

    assert [call["model"] for call in calls] == ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    assert calls[1]["max_completion_tokens"] == 300
    assert "everyday health questions" in reply
    assert destination is None


def test_voice_assistant_unavailable_message_uses_selected_language(monkeypatch):
    monkeypatch.setattr(ai_services, "get_groq_client", lambda: None)
    monkeypatch.setattr(ai_services, "get_today_medicine_doses", lambda user_id: [])
    monkeypatch.setattr(ai_services.db, "get_latest_health_metrics", lambda user_id: {})
    monkeypatch.setattr(ai_services.db, "get_all_diet_plans", lambda user_id: [])
    monkeypatch.setattr(ai_services.db, "get_medicine_history", lambda user_id: [])

    reply, destination = ai_services.process_voice_assistant_query(
        "Tell me something about my health.", 3, "Sreesha", "te-IN"
    )

    assert "కేర్‌వాయిస్" in reply
    assert destination is None


def test_voice_assistant_requires_confirmation_before_saving_bp(monkeypatch):
    recorded = []

    def fake_add(user_id, metric_name, value, unit, status=None, notes=None):
        recorded.append((user_id, metric_name, value, unit, status, notes))

    monkeypatch.setattr(ai_services.db, "add_health_metric", fake_add)

    reply, destination = ai_services.process_voice_assistant_query(
        "My blood pressure is 118 over 80.", 3, "Sreesha", "en-IN"
    )

    assert destination is None
    assert "save it" in reply.lower()
    assert "cancel" in reply.lower()
    assert not recorded


def test_voice_assistant_requires_confirmation_for_telugu_bp_and_save_command(monkeypatch):
    recorded = []
    monkeypatch.setattr(ai_services.db, "add_health_metric", lambda *args, **kwargs: recorded.append((args, kwargs)))

    reply, destination = ai_services.process_voice_assistant_query(
        "నా బీపీ 118/80", 3, "Sreesha", "te-IN"
    )
    command_reply, command_destination = ai_services.process_voice_assistant_query(
        "add my BP as 120 over 82", 3, "Sreesha", "en-IN"
    )

    assert destination is None
    assert command_destination is None
    assert "సేవ్ చేయాలా" in reply
    assert "save it" in command_reply.lower()
    assert not recorded


def test_voice_health_reading_parser_handles_split_digits_and_telugu_labels():
    bp_reading = ai_services.extract_voice_health_reading(
        "నా బీపీ 1, 20/80 ఉంది. ఇది సేవ్ చేసుకో."
    )
    screenshot_reading = ai_services.extract_voice_health_reading(
        "మీ BP 1 20/80 ఉంది సేవ్ చేసుకో."
    )
    sugar_reading = ai_services.extract_voice_health_reading(
        "నా షుగర్ 1, 25 ఉంది"
    )

    assert bp_reading == {"metric": "Blood Pressure", "value": "120/80"}
    assert screenshot_reading == {"metric": "Blood Pressure", "value": "120/80"}
    assert sugar_reading == {"metric": "Blood Sugar", "value": "125"}


def test_voice_sugar_timing_is_explicit_and_chart_compatible():
    assert ai_services.extract_voice_sugar_timing("fasting") == "Before Food"
    assert ai_services.extract_voice_sugar_timing("after food") == "After Food"
    assert ai_services.extract_voice_sugar_timing("భోజనానికి ముందు") == "Before Food"
    assert ai_services.extract_voice_sugar_timing("భోజనం తర్వాత") == "After Food"
    assert ai_services.extract_voice_sugar_timing("my sugar is 125") is None


def test_voice_assistant_does_not_confuse_bp_question_with_latest_reading(monkeypatch):
    monkeypatch.setattr(ai_services, "get_today_medicine_doses", lambda user_id: [])
    monkeypatch.setattr(ai_services.db, "get_health_metrics_for_date", lambda user_id, recorded_date: {"Blood Pressure": {"value": "118/80", "unit": "mmHg", "recorded_date": recorded_date}})
    monkeypatch.setattr(ai_services.db, "get_all_diet_plans", lambda user_id: [{
        "meal_time": "Lunch", "food_item": "Low-salt moong dal with cucumber salad"
    }])
    monkeypatch.setattr(ai_services, "generate_personalized_diet", lambda **kwargs: [{
        "meal_time": "Lunch", "food_item": "Low-salt moong dal with cucumber salad"
    }])
    monkeypatch.setattr(ai_services.db, "get_medicine_history", lambda user_id: [])
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content="For salty food, it is best to keep your intake light because your blood pressure is 118/80."
            ))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(ai_services, "get_groq_client", lambda: fake_client)

    reply, destination = ai_services.process_voice_assistant_query(
        "Based on my BP, can I have food that is salty?", 3, "Sreesha", "en-IN"
    )

    assert "salty" in reply.lower()
    assert "118/80" in reply or "blood pressure" in reply.lower()
    assert "Low-salt moong dal with cucumber salad" in calls[0]["messages"][0]["content"]
    assert destination is None


def test_food_advice_uses_saved_plan_when_ai_service_is_unavailable(monkeypatch):
    monkeypatch.setattr(ai_services, "get_groq_client", lambda: None)
    monkeypatch.setattr(ai_services, "get_today_medicine_doses", lambda user_id: [])
    monkeypatch.setattr(ai_services.db, "get_health_metrics_for_date", lambda user_id, recorded_date: {
        "Blood Sugar": {"value": "156", "unit": "mg/dL", "recorded_date": recorded_date}
    })
    monkeypatch.setattr(ai_services.db, "get_all_diet_plans", lambda user_id: [{
        "meal_time": "Breakfast", "food_item": "Pesarattu with mint chutney"
    }])
    monkeypatch.setattr(ai_services, "generate_personalized_diet", lambda **kwargs: [{
        "meal_time": "Breakfast", "food_item": "Pesarattu with mint chutney"
    }])
    monkeypatch.setattr(ai_services.db, "get_medicine_history", lambda user_id: [])

    reply, destination = ai_services.process_voice_assistant_query(
        "What should I eat based on my health and diet plan?", 3, "Sreesha", "en-IN"
    )

    assert "Pesarattu with mint chutney" in reply
    assert "higher-fiber" in reply
    assert destination is None


def test_voice_request_for_another_food_variant_refreshes_personalized_plan(monkeypatch):
    previous_plan = [{"meal_time": "Breakfast", "food_item": "Idli with sambar"}]
    refreshed_plan = [{"meal_time": "Breakfast", "food_item": "Pesarattu with ginger chutney"}]
    monkeypatch.setattr(ai_services.db, "get_health_metrics_for_date", lambda user_id, recorded_date: {
        "Blood Sugar": {"value": "118", "unit": "mg/dL", "recorded_date": recorded_date}
    })
    monkeypatch.setattr(ai_services.db, "get_all_diet_plans", lambda user_id: previous_plan)
    refresh_calls = []

    def fake_generate_personalized_diet(**kwargs):
        refresh_calls.append(kwargs)
        return refreshed_plan

    monkeypatch.setattr(ai_services, "generate_personalized_diet", fake_generate_personalized_diet)

    reply, destination = ai_services.process_voice_assistant_query(
        "I don't like this breakfast. Give me another variant.",
        3,
        "Sreesha",
        "en-IN",
        "Vegan",
    )

    assert "Pesarattu with ginger chutney" in reply
    assert destination == "DietRefreshed"
    assert refresh_calls[0]["force_refresh"] is True
    assert refresh_calls[0]["dietary_preference"] == "Vegan"


def test_voice_food_advice_requires_health_reading_from_today(monkeypatch):
    monkeypatch.setattr(ai_services.db, "get_health_metrics_for_date", lambda user_id, recorded_date: {})
    monkeypatch.setattr(
        ai_services.db,
        "get_latest_health_metrics",
        lambda user_id: (_ for _ in ()).throw(AssertionError("Old readings must not be used for today's diet")),
    )

    reply, destination = ai_services.process_voice_assistant_query(
        "What should I eat based on my health?", 3, "Sreesha", "en-IN"
    )

    assert "record a health reading today" in reply.lower()
    assert destination is None


def test_choose_voice_for_gender_prefers_female_match():
    voices = [
        SimpleNamespace(name="Microsoft David Desktop - English (United States)", lang="en-US"),
        SimpleNamespace(name="Microsoft Zira Desktop - English (United States)", lang="en-US"),
    ]

    selected = ai_services.choose_voice_for_gender(voices, "en-IN", "Female Voice")

    assert "zira" in selected.name.lower()


def test_choose_voice_for_gender_prefers_male_match():
    voices = [
        SimpleNamespace(name="Microsoft Zira Desktop - English (United States)", lang="en-US"),
        SimpleNamespace(name="Microsoft David Desktop - English (United States)", lang="en-US"),
    ]

    selected = ai_services.choose_voice_for_gender(voices, "en-IN", "Male Voice")

    assert "david" in selected.name.lower()


def test_choose_voice_for_male_does_not_match_google_female_voice_as_male():
    voices = [
        SimpleNamespace(name="Google US English Female", lang="en-US"),
        SimpleNamespace(name="Google UK English Male", lang="en-GB"),
    ]

    selected = ai_services.choose_voice_for_gender(voices, "en-IN", "Male Voice")

    assert "male" in selected.name.lower()