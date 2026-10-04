import re


_MEDICINE_NAMES_TE = {
    "amlodipine": "అమ్లోడిపిన్",
    "metformin": "మెట్‌ఫార్మిన్",
    "atorvastatin": "అటోర్వాస్టాటిన్",
    "omeprazole": "ఓమెప్రజోల్",
    "losartan": "లోసార్టన్",
    "aspirin": "ఆస్పిరిన్",
    "vitamin d": "విటమిన్ డి",
    "paracetamol": "పారాసిటమాల్",
    "acetaminophen": "అసిటామినోఫెన్",
    "pantoprazole": "పాంటోప్రజోల్",
    "telmisartan": "టెల్మిసార్టన్",
    "rosuvastatin": "రోసువాస్టాటిన్",
    "glimepiride": "గ్లిమిపిరైడ్",
    "levothyroxine": "లెవోథైరాక్సిన్",
    "cetirizine": "సెటిరిజిన్",
    "azithromycin": "అజిత్రోమైసిన్",
    "amoxicillin": "అమోక్సిసిలిన్",
    "calcium": "కాల్షియం",
    "iron": "ఐరన్",
    "insulin": "ఇన్సులిన్",
}

_MEDICINE_NAME_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(name)
        for name in sorted(_MEDICINE_NAMES_TE, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)


def display_medicine_name(name, is_telugu):
    """Translate known medicine names for display without changing stored names."""
    if not is_telugu:
        return name
    return _MEDICINE_NAME_PATTERN.sub(
        lambda match: _MEDICINE_NAMES_TE[match.group(0).lower()],
        str(name),
    )
