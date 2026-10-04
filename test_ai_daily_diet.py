from backend import ai_services
from backend.ai_services import get_daily_fallback_indian_diet


EXPECTED_MEALS = [
    "Breakfast",
    "Mid-morning",
    "Lunch",
    "Evening Snack",
    "Dinner",
    "Hydration",
]


def test_daily_fallback_has_all_requested_sections_and_is_stable_per_date():
    metrics = {"Blood Sugar": {"value": "156 mg/dL"}}

    first = get_daily_fallback_indian_diet(metrics, plan_date="2026-10-02")
    same_day = get_daily_fallback_indian_diet(metrics, plan_date="2026-10-02")
    next_day = get_daily_fallback_indian_diet(metrics, plan_date="2026-10-03")

    assert [meal["meal_time"] for meal in first] == EXPECTED_MEALS
    assert first == same_day
    assert all(
        today_meal["food_item"] != next_meal["food_item"]
        for today_meal, next_meal in zip(first, next_day)
    )
    assert "salad" in first[2]["food_item"].lower()


def test_daily_fallback_telugu_has_six_sections_and_plant_based_choices():
    menu = get_daily_fallback_indian_diet(
        {}, is_telugu=True, plan_date="2026-10-02", dietary_preference="Vegan"
    )

    assert [meal["meal_time"] for meal in menu] == EXPECTED_MEALS
    assert all(meal["food_item"] for meal in menu)
    assert all(meal["notes"] for meal in menu)
    assert not any(
        word in meal["food_item"].lower()
        for meal in menu
        for word in ("paneer", "curd", "buttermilk", "పెరుగు", "పనీర్", "మజ్జిగ")
    )


def test_personalized_diet_uses_only_metrics_for_plan_date(monkeypatch):
    requested_dates = []
    today_metrics = {"Blood Sugar": {"value": "156", "unit": "mg/dL", "recorded_date": "2026-10-04"}}
    monkeypatch.setattr(
        ai_services.db,
        "get_health_metrics_for_date",
        lambda user_id, recorded_date: requested_dates.append(recorded_date) or today_metrics,
    )
    monkeypatch.setattr(ai_services.db, "get_all_medicines", lambda user_id: [])
    monkeypatch.setattr(ai_services, "get_groq_client", lambda: None)
    monkeypatch.setattr(ai_services.db, "save_diet_plan", lambda user_id, diet_items: None)

    plan = ai_services.generate_personalized_diet(
        user_id=3,
        user_name="Sreesha",
        plan_date="2026-10-04",
    )

    assert requested_dates == ["2026-10-04"]
    assert [meal["meal_time"] for meal in plan] == EXPECTED_MEALS


def test_personalized_diet_requires_a_reading_for_plan_date(monkeypatch):
    monkeypatch.setattr(ai_services.db, "get_health_metrics_for_date", lambda user_id, recorded_date: {})
    monkeypatch.setattr(ai_services.db, "get_all_medicines", lambda user_id: [])

    try:
        ai_services.generate_personalized_diet(
            user_id=3,
            user_name="Sreesha",
            plan_date="2026-10-04",
        )
    except ValueError as error:
        assert "2026-10-04" in str(error)
    else:
        raise AssertionError("A diet plan should not be generated from readings on other dates")