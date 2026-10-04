from frontend.navigation import NAV_ITEMS, build_mobile_drawer_html


def test_mobile_drawer_contains_every_navigation_page():
    markup = build_mobile_drawer_html("CareVoice User", "Home", False)

    for item in NAV_ITEMS:
        assert f'nav_to={item["page"].replace(" ", "%20")}' in markup
        assert item["label"] in markup
    assert "Sign Out" in markup
    assert "CareVoice User" in markup


def test_mobile_drawer_uses_telugu_labels_and_marks_active_page():
    markup = build_mobile_drawer_html("వినియోగదారు", "Health", True)

    assert "వాయిస్ సహాయకుడు" in markup
    assert "సెట్టింగ్‌లు" in markup
    assert 'class="carevoice-mobile-link active" href="?nav_to=Health"' in markup
    assert "లాగ్ అవుట్" in markup


def test_mobile_drawer_escapes_user_supplied_profile_name():
    markup = build_mobile_drawer_html("<script>alert(1)</script>", "Home", False)

    assert "<script>alert(1)</script>" not in markup
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markup
