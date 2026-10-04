from contextlib import nullcontext
from types import SimpleNamespace

from frontend import navigation


def test_navigation_labels_include_my_prefix_in_english_and_telugu():
    for item in navigation.NAV_ITEMS:
        assert navigation.navigation_label(item).startswith("My ")
        assert navigation.navigation_label(item, is_te=True).startswith("నా ")


def test_mobile_navigation_uses_streamlit_buttons_without_full_page_links(monkeypatch):
    session_state = SimpleNamespace(mobile_nav_open=True, current_page="Home")
    button_calls = []
    rendered_markup = []

    def fake_button(label, key, **kwargs):
        button_calls.append((label, key))
        return key == "carevoice_mobile_nav_medicines"

    monkeypatch.setattr(navigation.st, "session_state", session_state)
    monkeypatch.setattr(navigation.st, "markdown", lambda markup, **kwargs: rendered_markup.append(markup))
    monkeypatch.setattr(navigation.st, "container", lambda **kwargs: nullcontext())
    monkeypatch.setattr(navigation.st, "columns", lambda *args, **kwargs: [nullcontext(), nullcontext()])
    monkeypatch.setattr(navigation.st, "button", fake_button)
    monkeypatch.setattr(navigation.st, "rerun", lambda: None)

    navigation.render_mobile_drawer("CareVoice User", "Home", False)

    assert session_state.current_page == "Medicines"
    assert session_state.mobile_nav_open is False
    assert "nav_to=" not in "".join(rendered_markup)
    assert {key for _, key in button_calls if key.startswith("carevoice_mobile_nav_")} == {
        f'carevoice_mobile_nav_{item["page"].lower().replace(" ", "_")}'
        for item in navigation.NAV_ITEMS
    }


def test_mobile_drawer_has_no_underlines_on_feature_buttons(monkeypatch):
    rendered_markup = []
    monkeypatch.setattr(navigation.st, "session_state", SimpleNamespace(mobile_nav_open=False))
    monkeypatch.setattr(navigation.st, "markdown", lambda markup, **kwargs: rendered_markup.append(markup))
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)

    navigation.render_mobile_drawer("CareVoice User", "Home", False)

    assert "text-decoration:none !important" in rendered_markup[0]
    assert "border-bottom:0 !important" in rendered_markup[0]
