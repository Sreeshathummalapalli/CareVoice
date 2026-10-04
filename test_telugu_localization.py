from backend.telugu_localization import display_medicine_name


def test_displays_known_medicine_names_in_telugu_without_changing_dose():
    assert display_medicine_name("Amlodipine 5 mg", True) == "అమ్లోడిపిన్ 5 mg"
    assert display_medicine_name("Vitamin D", True) == "విటమిన్ డి"


def test_keeps_unknown_medicine_names_and_english_display_unchanged():
    assert display_medicine_name("MyBrand XR 20 mg", True) == "MyBrand XR 20 mg"
    assert display_medicine_name("Amlodipine 5 mg", False) == "Amlodipine 5 mg"


def test_localizes_multiple_known_names_in_a_combination():
    assert display_medicine_name("Metformin + Losartan", True) == "మెట్‌ఫార్మిన్ + లోసార్టన్"
