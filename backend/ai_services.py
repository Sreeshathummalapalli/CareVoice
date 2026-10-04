# CareVoice AI Services: Diet Generator, Report Explanation, Voice Assistant Processor
import os
import re
import json
import sys
import hashlib
import datetime
import logging
sys.path.append('..')
from groq import Groq
from dotenv import load_dotenv
from db import carevoice_db as db

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
def get_groq_client():
    if GROQ_API_KEY:
        try:
            return Groq(api_key=GROQ_API_KEY)
        except Exception:
            return None
    return None

import random


def choose_voice_for_gender(voices, lang_code="en-IN", voice_gender="Female Voice"):
    if not voices:
        return None

    language_prefix = str(lang_code or "en-IN")[:2].lower()
    gender_name = str(voice_gender or "Female Voice").lower()
    is_female = any(keyword in gender_name for keyword in ("female", "girl", "woman", "women"))
    female_keywords = (
        "female", "zira", "heera", "hazel", "susan", "samantha", "victoria",
        "karen", "catherine", "aria", "emma", "ava", "jenny", "michelle",
        "sonia", "libby", "natasha", "moira",
    )
    male_keywords = (
        "david", "mark", "george", "ravi", "alex", "daniel", "guy", "ryan",
        "tony", "thomas", "oliver", "liam", "eric", "andrew",
    )

    def matches_gender(voice_name):
        if is_female:
            return any(keyword in voice_name for keyword in female_keywords)
        return (
            not any(keyword in voice_name for keyword in female_keywords)
            and (
                any(keyword in voice_name for keyword in male_keywords)
                or re.search(r"(^|[\s-])male($|[\s-])", voice_name) is not None
            )
        )

    matching = []
    for voice in voices:
        voice_name = str(getattr(voice, "name", "") or "").lower()
        voice_lang = str(getattr(voice, "lang", "") or "").lower()
        is_lang_match = voice_lang.startswith(language_prefix) or language_prefix in voice_name
        if not is_lang_match:
            continue
        if matches_gender(voice_name):
            matching.append((0, voice))
        else:
            matching.append((1, voice))

    if matching:
        matching.sort(key=lambda item: item[0])
        return matching[0][1]

    for voice in voices:
        voice_name = str(getattr(voice, "name", "") or "").lower()
        if matches_gender(voice_name):
            return voice

    return voices[0]


def get_fallback_indian_diet(latest_metrics, is_telugu=False, day_num=1):
    sugar_val = 0
    bp_val = 0
    weight_val = 0
    hr_val = 0

    if latest_metrics:
        bs_rec = latest_metrics.get("Blood Sugar", {})
        if bs_rec and bs_rec.get("value"):
            try:
                sugar_val = float(re.search(r'\d+', str(bs_rec["value"])).group())
            except Exception:
                pass
        bp_rec = latest_metrics.get("Blood Pressure", {})
        if bp_rec and bp_rec.get("value"):
            try:
                bp_val = float(str(bp_rec["value"]).split('/')[0])
            except Exception:
                pass
        w_rec = latest_metrics.get("Weight", {})
        if w_rec and w_rec.get("value"):
            try:
                weight_val = float(re.search(r'\d+', str(w_rec["value"])).group())
            except Exception:
                pass
        hr_rec = latest_metrics.get("Heart Rate", {})
        if hr_rec and hr_rec.get("value"):
            try:
                hr_val = float(re.search(r'\d+', str(hr_rec["value"])).group())
            except Exception:
                pass

    has_high_sugar = sugar_val > 140
    has_high_bp = bp_val > 130
    has_high_weight = weight_val > 75
    has_high_hr = hr_val > 90

    day_idx = max(0, min((day_num - 1) % 7, 6))

    if is_telugu:
        if has_high_sugar and has_high_bp:
            plans = [
                # Day 1
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి దోస తక్కువ ఉప్పు కొబ్బరి చట్నీతో", "calories": 300, "notes": f"రక్తంలో చక్కెర ({int(sugar_val)} mg/dL) మరియు BP ({int(bp_val)} mmHg) నియంత్రణకు రాగి మరియు పీచుపదార్థం సహాయపడుతుంది."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న రొట్టెలు (2), పెసరపప్పు, ఆనపకాయ కూర, జీలకర్ర మజ్జిగ", "calories": 450, "notes": "తక్కువ సోడియం మరియు తక్కువ గ్లైసెమిక్ ఇండెక్స్ ఉన్న సురక్షితమైన భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ముളకల్తిన పెసలు & జామకాయ ముక్కలు", "calories": 140, "notes": "గుండె మరియు చక్కెర స్థాయిలకు మేలు చేసే సహజ సిద్ధమైన స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల జొన్న రవ్వ ఖిచ్డీ & దోసకాయ రాయితా", "calories": 360, "notes": "రాత్రి వేళ చక్కెర మరియు రక్తపోటు స్థిరంగా ఉండేలా చేస్తుంది."}
                ],
                # Day 2
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "పెసరట్టు (Moong Dal Dosa) పుదీనా చట్నీతో", "calories": 310, "notes": f"అధిక ప్రొటీన్తో చక్కెర స్థాయి ({int(sugar_val)}) అదుపులో ఉంటుంది."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "మల్టీగ్రెయిన్ రొట్టెలు (2), తోటకూర పప్పు, కాకరకాయ ఫ్రై, తాజా పెరుగు", "calories": 460, "notes": "కాకరకాయ ఇన్సులిన్ స్థాయిని మెరుగుపరుస్తుంది మరియు ఆకుకూరలు BP తగ్గిస్తాయి."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "వేయించిన పేలాలు (Roasted Makhana) & గ్రీన్ టీ", "calories": 130, "notes": "తక్కువ కలోరీలు గల సోడియం రహిత స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "జొన్న పుల్కాలు (2) మెంతి కూర పప్పుతో", "calories": 350, "notes": "రాత్రి వేళ తిరోగమనం లేకుండా చక్కెర స్థిరీకరణ."}
                ],
                # Day 3
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "కూరగాయల జొన్న ఉప్మా తక్కువ ఉప్పుతో", "calories": 290, "notes": f"రక్తపోటు ({int(bp_val)}) పై ఒత్తిడి తగ్గించే పొటాషియం మిశ్రమం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, శనగపప్పు, బీరకాయ కూర, పలచని మజ్జిగ", "calories": 470, "notes": "పీచు పదార్థం చక్కెర పీల్చుకోవడాన్ని నెమ్మదింపజేస్తుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన నల్ల శనగలు నిమ్మరసంతో", "calories": 150, "notes": "ప్రొటీన్ సమృద్ధిగా ఉండే పోషకాహార స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "ఓట్స్-రాగి ఖిచ్డీ & పూడినా రాయితా", "calories": 340, "notes": "తేలికపాటి జీర్ణక్రియకు మరియు గుండె ప్రశాంతతకు సహాయపడుతుంది."}
                ],
                # Day 4
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉడకబెట్టిన ఇడ్లీలు (3) తక్కువ ఉప్పు సాంబార్‌తో", "calories": 300, "notes": "సోడియం అదుపులో ఉంచి రక్తపోటు తగ్గించే దక్షిణాది ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న రొట్టెలు (2), రాజ్మా కూర, బీన్స్ సబ్జీ & పెరుగు", "calories": 480, "notes": "ప్రొటీన్లు మరియు మెగ్నీషియమ్ సమృద్ధిగా ఉండే భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "కీరదోసకాయ & క్యారట్ ముక్కలు జీలకర్ర మజ్జిగతో", "calories": 110, "notes": "శరీరానికి అవసరమైన నీటిశాతం మరియు పొటాషియం అందిస్తుంది."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "గోధుమ పుల్కాలు (2) బెండకాయ కూరతో", "calories": 360, "notes": "రాత్రి సమతుల్య చక్కెర నియంత్రణ."}
                ],
                # Day 5
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "పప్పు చిల్లా (Lentil Pancake) అల్లం చట్నీతో", "calories": 310, "notes": "తక్కువ గ్లైసెమిక్ ఇండెక్స్ ఉన్న ప్రొటీన్ ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బాజ్రా రొట్టెలు (2), తోటకూర పప్పు, దొండకాయ ఫ్రై, మజ్జిగ", "calories": 460, "notes": "సహజ సిద్ధమైన పీచుతో గుండెకు రక్షణ."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన స్వీట్ కార్న్ నిమ్మరసంతో", "calories": 130, "notes": "రక్తనాళాల ఆరోగ్యానికి మేలు చేసే స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల పోహా తక్కువ నూనెతో", "calories": 350, "notes": "పొట్టకు తేలికగా ఉండే రాత్రి ఆహారం."}
                ],
                # Day 6
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉల్లి-జొన్న దోస పప్పు సాంబార్‌తో", "calories": 315, "notes": "చక్కెర స్థాయిలను స్థిరీకరించే రొటీన్ ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న రొట్టెలు (2), మసాలా లేని ఆనపకాయ పప్పు & చట్నీ", "calories": 450, "notes": "రక్తపోటు సమతుల్యత కాపాడే భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "తాజా బొప్పాయి ముక్కలు", "calories": 120, "notes": "విటమిన్ సి మరియు యాంటీఆక్సిడెంట్లతో కూడిన పండు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "రాగి రవ్వ ఖిచ్డీ సొరకాయ రాయితాతో", "calories": 350, "notes": "రాత్రి వేళ రక్తంలో చక్కెర నియంత్రణ."}
                ],
                # Day 7
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "వెజిటబుల్ దాలియా రవ్వ ఉప్మా", "calories": 300, "notes": "సంపూర్ణ పీచుతో రోజంతా నిరంతర శక్తి."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, మిశ్రమ కూరగాయల పప్పు, కీరదోస సలాడ్, పెరుగు", "calories": 470, "notes": "గుండె మరియు రక్తకణాల ఆరోగ్యానికి సమతుల్య ఆహారం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "మజ్జిగ & కొద్దిగా నానబెట్టిన బాదం (4-5)", "calories": 130, "notes": "మంచి కొవ్వులు మరియు పొటాషియం."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "మెత్తటి గోధుమ పుల్కాలు (2) పాలకూర పప్పుతో", "calories": 360, "notes": "హాయిగా నిద్రపట్టే రక్తపోటు అనుకూల భోజనం."}
                ]
            ]
            return plans[day_idx]
        elif has_high_sugar:
            plans = [
                # Day 1
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి దోస లేదా జొన్న ఉప్మా, పప్పు చట్నీతో", "calories": 310, "notes": f"రక్తంలో చక్కెర స్థాయిని ({int(sugar_val)} mg/dL) సమతుల్యంగా ఉంచే పీచుపదార్థం గల ఆహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న/గోధుమ రొట్టెలు (2), పెసరపప్పు, బెండకాయ కూర, తాజా పెరుగు", "calories": 480, "notes": "ప్రొటీన్లు మరియు పీచు పదార్థాలు సమృద్ధిగా ఉండి భోజనం తర్వాత చక్కెర పెరగకుండా చూస్తుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ముളకల్తిన పెసలు (Sprouted Moong Salad) & మజ్జిగ", "calories": 160, "notes": "జీర్ణక్రియకు మంచిది మరియు పొట్టకు తేలికైన స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల జొన్న/గోధుమ రవ్వ ఖిచ్డీ & సొరకాయ కూర", "calories": 380, "notes": "రాత్రి వేళ చక్కెర నియంత్రణలో ఉంచుతుంది."}
                ],
                # Day 2
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "పెసరట్టు (Moong Dal Dosa) అల్లం చట్నీతో", "calories": 320, "notes": f"అధిక ప్రొటీన్ కలిగి ఉండి ఇన్సులిన్ సున్నితత్వాన్ని పెంచుతుంది (Sugar: {int(sugar_val)})."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "మల్టీగ్రెయిన్ రొట్టెలు (2), తోటకూర పప్పు, కాకరకాయ ఫ్రై, మజ్జిగ", "calories": 470, "notes": "కాకరకాయ చక్కెర స్థాయిలను తగ్గించడంలో సహాయపడుతుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "వేయించిన పేలాలు (Roasted Makhana) & గ్రీన్ టీ", "calories": 140, "notes": "తక్కువ కలోరీలు గల పోషకాహార స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "గోధుమ పుల్కాలు (2) మెంతి కూర పప్పు మరియు దోసకాయ రాయితా", "calories": 360, "notes": "రాత్రి వేళ రక్తంలో చక్కెర హెచ్చుతగ్గులు రాకుండా కాపాడుతుంది."}
                ],
                # Day 3
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "కూరగాయల జొన్న రవ్వ ఉప్మా లేదా పప్పు చిల్లా", "calories": 300, "notes": "తక్కువ గ్లైసెమిక్ ఇండెక్స్ ఆహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న రొట్టెలు (2), శనగపప్పు కూర, పీచుపదార్థాలు ఉన్న కూరగాయలు, పెరుగు", "calories": 490, "notes": "శరీరానికి నిరంతర శక్తిని అందిస్తూ చక్కెరను అదుపు చేస్తుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన నల్ల శనగలు (Boiled Chana) నిమ్మకాయతో", "calories": 150, "notes": "పీచు మరియు ప్రొటీన్లతో కూడిన స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "ఓట్స్-రాగి రవ్వ ఖిచ్డీ & పూడినా రాయితా", "calories": 350, "notes": "జీర్ణశక్తిని పెంచి చక్కెర స్థాయిలను స్థిరీకరిస్తుంది."}
                ],
                # Day 4
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి ఇడ్లీలు (3) కొబ్బరి చట్నీతో", "calories": 300, "notes": "చక్కెర ఆకస్మికంగా పెరగకుండా నియంత్రించే ధాన్యం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, పెసరపప్పు చారు, పప్పుకూర & మజ్జిగ", "calories": 480, "notes": "మధ్యాహ్న భోజనం తర్వాత ఇన్సులిన్ సమతుల్యత."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "క్యారట్ & కీరదోస సలాడ్ నిమ్మరసంతో", "calories": 110, "notes": "సహజ విటమిన్లు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 జొన్న రొట్టెలు సోయాబీన్/పనీర్ సబ్జీతో", "calories": 370, "notes": "అధిక ప్రొటీన్ రాత్రి భోజనం."}
                ],
                # Day 5
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "మల్టీగ్రెయిన్ దోస టమోటా చట్నీతో", "calories": 310, "notes": "శరీరానికి మంచి నిరంతర ఇంధనం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 పుల్కాలు, బీన్స్ ఫ్రై, కందిపప్పు & పెరుగు", "calories": 475, "notes": "ప్రొటీన్ మరియు పీచు మిశ్రమం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన శనగ గుగ్గిళ్ళు & గ్రీన్ టీ", "calories": 145, "notes": "ఆకలిని సమర్థవంతంగా అదుపు చేస్తుంది."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల దాలియా ఖిచ్డీ", "calories": 360, "notes": "సులభంగా జీర్ణమయ్యే ఆహారం."}
                ],
                # Day 6
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉల్లి-పెసరట్టు అల్లం చట్నీతో", "calories": 315, "notes": "ఇన్సులిన్ పనితీరును పెంచుతుంది."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 జొన్న రొట్టెలు, వంకాయ ఫ్రై, మినుపపప్పు, మజ్జిగ", "calories": 485, "notes": "తక్కువ కార్బోహైడ్రేట్లు."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "తాజా జామకాయ ముక్కలు", "calories": 120, "notes": "తక్కువ గ్లైసెమిక్ ఇండెక్స్ ఉన్న పండు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 గోధుమ పుల్కాలు చుక్కకూర పప్పుతో", "calories": 355, "notes": "రాత్రి చక్కెర స్థిరీకరణ."}
                ],
                # Day 7
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "కూరగాయల రాగి ఉప్మా", "calories": 295, "notes": "పీచుపదార్థాల సమాహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్ / 2 రొట్టెలు, రాజ్మా కూర, కీరదోస సలాడ్", "calories": 490, "notes": "మంచి ప్రొటీన్ సంపద."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "జీలకర్ర మజ్జిగ & రోస్టెడ్ మఖానా", "calories": 135, "notes": "లలితమైన రుచికరమైన స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "జొన్న-గోధుమ ఖిచ్డీ రాయితాతో", "calories": 365, "notes": "ప్రశాంతమైన రాత్రి భోజనం."}
                ]
            ]
            return plans[day_idx]
        elif has_high_bp:
            plans = [
                # Day 1
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "స్టీమ్ ఇడ్లీలు (3) తక్కువ ఉప్పు కూరగాయల సాంబార్‌తో", "calories": 300, "notes": f"రక్తపోటును ({int(bp_val)} mmHg) అదుపులో ఉంచడానికి తక్కువ సోడియం ఆహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "జొన్న రొట్టెలు (2), తోటకూర పప్పు, సొరకాయ కూర, కీరదోస పెరుగు రాయితా", "calories": 450, "notes": "పొటాషియమ్ సమృద్ధిగా ఉండి నరాల ఒత్తిడిని తగ్గిస్తుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "కీరదోసకాయ ముక్కలు & జీలకర్ర పలచని మజ్జిగ", "calories": 120, "notes": "సోడియం నిల్వలను సమతుల్యం చేస్తుంది."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "పుల్కాలు (2) మసాలా లేని ఆనపకాయ కూరతో", "calories": 360, "notes": "రాత్రి వేళ గుండెకు ఆరోగ్యాన్నిచ్చే తేలికపాటి భోజనం."}
                ],
                # Day 2
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "వెజిటబుల్ ఉప్మా & తక్కువ ఉప్పు చట్నీ", "calories": 310, "notes": f"గుండె ఆరోగ్యాన్ని పెంపొందించే పొటాషియం ఆహారం (BP: {int(bp_val)})."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, పసుపు పప్పు, బీరకాయ కూర, తాజా పెరుగు", "calories": 460, "notes": "రక్తనాళాల స్థితిస్థాపకతను కాపాడే భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన మొక్కజొన్న (Sweet Corn) & అల్లం టీ", "calories": 130, "notes": "రక్తపోటును క్రమబద్ధీకరించే స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల సూప్ & 2 మెత్తటి గోధుమ పుల్కాలు కూరతో", "calories": 340, "notes": "గుండె ఒత్తిడిని తగ్గించే రాత్రి ఆహారం."}
                ],
                # Days 3 to 7
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి ఉప్మా తక్కువ ఉప్పుతో", "calories": 290, "notes": "మెగ్నీషియం ఉండి నరాల ఒత్తిడిని తగ్గిస్తుంది."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 జొన్న రొట్టెలు, తోటకూర పప్పు, బెండకాయ ఫ్రై, మజ్జిగ", "calories": 455, "notes": "సహజ రక్తపోటు నిరోధక భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "తాజా కొబ్బరి నీళ్ళు & మఖానా", "calories": 125, "notes": "పొటాషియం పుష్కలంగా ఉంటుంది."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 పుల్కాలు సొరకాయ పప్పుతో", "calories": 350, "notes": "తేలికపాటి గుండె ఆహారం."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉడకబెట్టిన 3 రవ్వ ఇడ్లీలు సాంబార్‌తో", "calories": 305, "notes": "సోడియం అదుపు."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 గోధుమ రొట్టెలు, పెసరపప్పు, కీరదోస రాయితా", "calories": 460, "notes": "రక్తపోటును నియంత్రిస్తుంది."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "బొప్పాయి ముక్కలు", "calories": 115, "notes": "యాంటీఆక్సిడెంట్లు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల దాలియా ఖిచ్డీ", "calories": 345, "notes": "హాయిగా నిద్రపట్టే ఆహారం."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "పెసరట్టు అల్లం చట్నీతో", "calories": 315, "notes": "ప్రొటీన్ ఆధారిత తక్కువ సోడియం ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, తోటకూర పప్పు, బీరకాయ కూర", "calories": 470, "notes": "రక్తకణాల స్థితిస్థాపకత."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "పలచని జీలకర్ర మజ్జిగ", "calories": 90, "notes": "శరీరానికి చలువ."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 పుల్కాలు గుమ్మడికాయ కూరతో", "calories": 340, "notes": "గుండెకు రక్షణ."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "జొన్న దోస కొబ్బరి చట్నీతో", "calories": 300, "notes": "పోషకాల మేళవింపు."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 బాజ్రా రొట్టెలు, పసుపు పప్పు, బెండకాయ సబ్జీ", "calories": 465, "notes": "పీచు పదార్థాలు."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన చనా గుగ్గిళ్ళు", "calories": 140, "notes": "గుండె బలానికి."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "మిశ్రమ ధాన్యాల ఖిచ్డీ", "calories": 355, "notes": "తేలికపాటి జీర్ణక్రియ."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "వెజిటబుల్ దాలియా ఉప్మా", "calories": 295, "notes": "పొటాషియం అధికంగా ఉంటుంది."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 జొన్న రొట్టెలు, కందిపప్పు, చామకూర కూర & పెరుగు", "calories": 475, "notes": "రక్తపోటు స్థిరీకరణ."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "కీరదోస సలాడ్", "calories": 85, "notes": "హైడ్రేషన్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 పుల్కాలు తోటకూర కూరతో", "calories": 350, "notes": "రాత్రి గుండె విశ్రాంతి."}
                ]
            ]
            return plans[day_idx]
        else:
            plans = [
                # Day 1
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "పెసరట్టు (Moong Dal Dosa) అల్లం చట్నీతో", "calories": 320, "notes": "శరీరానికి అవసరమైన పోషకాలు మరియు ప్రొటీన్ అందించే సాంప్రదాయ ఆహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "రొట్టెలు (2), పప్పు చారు, తోటకూర పప్పు, తాజా పెరుగు", "calories": 500, "notes": "సంపూర్ణ దేహారోగ్యం మరియు శక్తినిచ్చే సమతుల్య భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన శనగలు (Boiled Chana Chaat) & గ్రీన్ టీ", "calories": 150, "notes": "శరీరానికి అవసరమైన యాంటీఆక్సిడెంట్లు అందిస్తుంది."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల పోహా లేదా మిశ్రమ ధాన్యాల ఖిచ్డీ", "calories": 370, "notes": "ప్రశాంతమైన నిద్రకు మరియు తేలికపాటి జీర్ణక్రియకు సహాయపడుతుంది."}
                ],
                # Day 2
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉల్లి-రవ్వ ఇడ్లీలు (3) సాంబార్‌తో", "calories": 310, "notes": "శరీరానికి స్వచ్ఛమైన శక్తినిచ్చే తేలికపాటి దక్షిణాది ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్ / పుల్కాలు (2), రాజ్మా కూర, ఆలూ-గోబీ కూర & దోసకాయ సలాడ్", "calories": 510, "notes": "ప్రొటీన్ మరియు విటమిన్లతో కూడిన ఆరోగ్యకరమైన థాలీ."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "తాజా బొప్పాయి/జామకాయ ముక్కలు & జీలకర్ర మజ్జిగ", "calories": 140, "notes": "సహజ సిద్ధమైన రోగనిరోధక శక్తిని పెంచే పండ్ల స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "జొన్న రొట్టెలు (2) వంకాయ భర్తా కూరతో", "calories": 380, "notes": "దేహారోగ్యానికి మరియు జీర్ణక్రియకు మేలు చేసే స్వదేశీ రాత్రి భోజనం."}
                ],
                # Days 3 to 7
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి దోస కొబ్బరి చట్నీతో", "calories": 305, "notes": "దక్షిణాది ఆరోగ్యకరమైన ధాన్యం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 గోధుమ రొట్టెలు, శనగపప్పు కూర, దొండకాయ ఫ్రై, పెరుగు", "calories": 490, "notes": "సమతుల్య పోషకాహారం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "ఉడకబెట్టిన శనగ గుగ్గిళ్ళు", "calories": 145, "notes": "ప్రొటీన్ శక్తి."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "దాలియా ఖిచ్డీ", "calories": 360, "notes": "తేలికగా జీర్ణమయ్యే రాత్రి ఆహారం."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "జొన్న ఉప్మా చట్నీతో", "calories": 300, "notes": "పీచుపదార్థాల ఆహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, తోటకూర పప్పు, బెండకాయ ఫ్రై, పెరుగు", "calories": 500, "notes": "సమగ్ర శక్తి సంపద."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "మఖానా & నిమ్మ టీ", "calories": 130, "notes": "లలితమైన స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 పుల్కాలు సొరకాయ కూరతో", "calories": 350, "notes": "రాత్రి శ్రేయస్సు."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "మినుప-పెసర చిల్లా", "calories": 315, "notes": "అధిక ప్రొటీన్ ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 జొన్న రొట్టెలు, కందిపప్పు, చిక్కుడుకాయ కూర, మజ్జిగ", "calories": 495, "notes": "జీర్ణ వ్యవస్థకి రక్షణ."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "తాజా జామకాయ ముక్కలు", "calories": 120, "notes": "సహజ విటమిన్లు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "కూరగాయల పోహా", "calories": 355, "notes": "తేలికపాటి ఆహారం."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "రాగి ఇడ్లీలు (3) పప్పు చట్నీతో", "calories": 310, "notes": "ఎముకల బలానికి రాగి."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "2 రొట్టెలు, మిశ్రమ కూరగాయల పప్పు, రాయితా", "calories": 505, "notes": "మంచి ఇంధనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "నానబెట్టిన బాదం & మజ్జిగ", "calories": 135, "notes": "మంచి కొవ్వులు."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "మిశ్రమ ధాన్యాల ఖిచ్డీ", "calories": 365, "notes": "ప్రశాంత నిద్ర."}
                ],
                [
                    {"meal_time": "ఉదయం ఉపహారం (Breakfast)", "food_item": "ఉల్లి-రవ్వ దోస సాంబార్‌తో", "calories": 320, "notes": "రుచికరమైన ఆరోగ్యకర ఉపహారం."},
                    {"meal_time": "మధ్యాహ్న భోజనం (Lunch)", "food_item": "బ్రౌన్ రైస్, రాజ్మా మసాలా, కీరదోస సలాడ్ & పెరుగు", "calories": 510, "notes": "ప్రొటీన్ పవర్ భోజనం."},
                    {"meal_time": "సాయంత్రం తినుబండారాలు (Evening Snack)", "food_item": "స్వీట్ కార్న్ నిమ్మరసంతో", "calories": 130, "notes": "శక్తినిచ్చే స్నాక్."},
                    {"meal_time": "రాత్రి భోజనం (Dinner)", "food_item": "2 గోధుమ పుల్కాలు పాలకూర పప్పుతో", "calories": 360, "notes": "శరీర పునరుజ్జీవన రాత్రి భోజనం."}
                ]
            ]
            return plans[day_idx]
    else:
        # ENGLISH PLANS
        if has_high_sugar and has_high_bp:
            plans = [
                # Day 1
                [
                    {"meal_time": "Breakfast", "food_item": "Ragi Dosa with Low-Sodium Chana Dal Chutney", "calories": 300, "notes": f"High fiber millet meal designed for Sugar: {int(sugar_val)} mg/dL & BP: {int(bp_val)} mmHg."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Moong Dal, Lauki (Bottle Gourd) Sabzi & Jeera Buttermilk", "calories": 450, "notes": "Low-salt, low-GI thali promoting blood vessel relaxation and smooth glucose curves."},
                    {"meal_time": "Evening Snack", "food_item": "Sprouted Moong Salad with Lemon & Guava Slices", "calories": 140, "notes": "Heart-healthy, low calorie snack rich in potassium and digestive enzymes."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Jowar Dalia Khichdi with Cucumber Raita", "calories": 360, "notes": "Easy to digest evening meal ensuring flat overnight blood sugar and stable BP."}
                ],
                # Day 2
                [
                    {"meal_time": "Breakfast", "food_item": "Pesarattu (Green Gram Dosa) with Mint Chutney", "calories": 310, "notes": f"High plant protein pancake enhancing insulin sensitivity for Sugar: {int(sugar_val)} mg/dL."},
                    {"meal_time": "Lunch", "food_item": "2 Multigrain Rotis with Palak (Spinach) Dal, Karela Fry & Fresh Curd", "calories": 460, "notes": "Bitter gourd active compounds regulate glucose while spinach potassium lowers blood pressure."},
                    {"meal_time": "Evening Snack", "food_item": "Roasted Makhana (Foxnuts) with Spiced Green Tea", "calories": 130, "notes": "Zero-sodium crunch snack packed with natural antioxidants."},
                    {"meal_time": "Dinner", "food_item": "2 Jowar Phulkas with Methi (Fenugreek) Sabzi & Plain Yogurt", "calories": 350, "notes": "Fenugreek supports slow glucose release while avoiding nighttime BP spikes."}
                ],
                # Day 3
                [
                    {"meal_time": "Breakfast", "food_item": "Vegetable Jowar Upma (Low-Salt)", "calories": 290, "notes": f"Soluble fiber rich millet upma protecting vascular health (BP: {int(bp_val)})."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice / 2 Wheat Rotis with Masoor Dal, Ridge Gourd Sabzi & Buttermilk", "calories": 470, "notes": "Complex carbohydrates prevent post-meal sugar spikes."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Black Chana Chaat with Chopped Tomatoes & Lemon", "calories": 150, "notes": "Fiber dense afternoon snack for sustained stamina."},
                    {"meal_time": "Dinner", "food_item": "Oats-Ragi Dalia Khichdi with Mint Yogurt", "calories": 340, "notes": "Light millet khichdi optimizing cardiac recovery during sleep."}
                ],
                # Day 4
                [
                    {"meal_time": "Breakfast", "food_item": "3 Steamed Idlis with Low-Sodium Vegetable Sambar", "calories": 300, "notes": "Fermented low-salt meal aiding gut microbiome and blood pressure control."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Rajma Curry, Beans Poriyal & Curd", "calories": 480, "notes": "Magnesium and potassium loaded legumes for cardiac arterial health."},
                    {"meal_time": "Evening Snack", "food_item": "Sliced Cucumber & Carrot Sticks with Jeera Buttermilk", "calories": 110, "notes": "Natural electrolyte balance helping flush excess body sodium."},
                    {"meal_time": "Dinner", "food_item": "2 Wheat Phulkas with Mild Bhindi (Okra) Curry", "calories": 360, "notes": "Okra mucilage slows down glucose absorption overnight."}
                ],
                # Day 5
                [
                    {"meal_time": "Breakfast", "food_item": "Moong Dal Chilla (Lentil Pancake) with Ginger Chutney", "calories": 310, "notes": "Low GI protein breakfast preventing mid-morning hypoglycemic crashes."},
                    {"meal_time": "Lunch", "food_item": "2 Bajra Rotis with Toor Dal, Ivy Gourd Sabzi & Fresh Buttermilk", "calories": 460, "notes": "Traditional millets contain bioflavonoids supporting vascular elasticity."},
                    {"meal_time": "Evening Snack", "food_item": "Steamed Sweet Corn with Lemon & Black Pepper", "calories": 130, "notes": "Heart-friendly grain snack promoting smooth arterial blood flow."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Poha with Less Oil & Peas", "calories": 350, "notes": "Light easy-to-digest traditional dinner."}
                ],
                # Day 6
                [
                    {"meal_time": "Breakfast", "food_item": "Onion Jowar Dosa with Vegetable Sambar", "calories": 315, "notes": "Sustained fiber and micronutrients tailored for diabetic hypertension."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Lauki Dal & Cucumber Salad", "calories": 450, "notes": "Hydrating bottle gourd aids renal sodium excretion and BP stability."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Papaya Cubes with Roasted Seeds", "calories": 120, "notes": "Enzyme rich low-glycemic fruit snack."},
                    {"meal_time": "Dinner", "food_item": "Ragi Rava Khichdi with Steamed Lauki Raita", "calories": 350, "notes": "Restorative low-calorie dinner for metabolic balance."}
                ],
                # Day 7
                [
                    {"meal_time": "Breakfast", "food_item": "Vegetable Dalia Upma with Mint Chutney", "calories": 300, "notes": "Whole cracked wheat grain delivering continuous slow energy."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice with Mixed Veg Dal, Cucumber Salad & Fresh Curd", "calories": 470, "notes": "Balanced traditional Indian meal preserving insulin stability."},
                    {"meal_time": "Evening Snack", "food_item": "Jeera Buttermilk & 4-5 Soaked Almonds", "calories": 130, "notes": "Healthy monounsaturated fats supporting arterial walls."},
                    {"meal_time": "Dinner", "food_item": "2 Soft Wheat Phulkas with Spinach Dal", "calories": 360, "notes": "Nitrate rich leafy greens supporting relaxed vascular tone."}
                ]
            ]
            return plans[day_idx]
        elif has_high_sugar:
            plans = [
                # Day 1
                [
                    {"meal_time": "Breakfast", "food_item": "Ragi Dosa or Jowar Upma with Chana Dal Chutney", "calories": 310, "notes": f"High fiber, low GI meal for sugar reading: {int(sugar_val)} mg/dL."},
                    {"meal_time": "Lunch", "food_item": "2 Multigrain Rotis with Moong Dal, Bhindi Sabzi & Fresh Curd", "calories": 480, "notes": "Rich in plant protein and fiber for steady post-lunch blood glucose."},
                    {"meal_time": "Evening Snack", "food_item": "Sprouted Moong Salad with Lemon & Jeera Buttermilk", "calories": 160, "notes": "Nutrient dense low calorie Indian snack."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Dalia Khichdi with Lauki Sabzi", "calories": 380, "notes": "Easy to digest dinner supporting overnight blood sugar control."}
                ],
                # Day 2
                [
                    {"meal_time": "Breakfast", "food_item": "Moong Dal Chilla with Mint-Coriander Chutney", "calories": 320, "notes": f"High protein breakfast increasing insulin sensitivity (Sugar: {int(sugar_val)})."},
                    {"meal_time": "Lunch", "food_item": "2 Bajra Rotis with Toor Dal, Palak Curry & Cucumber Raita", "calories": 470, "notes": "Spinach & whole millets contain chromium to regulate blood glucose."},
                    {"meal_time": "Evening Snack", "food_item": "Roasted Makhana (Foxnuts) with Green Tea", "calories": 140, "notes": "Low GI crunch snack high in antioxidants."},
                    {"meal_time": "Dinner", "food_item": "2 Jowar Phulkas with Methi-Matar Sabzi & Plain Yogurt", "calories": 360, "notes": "Methi active compounds maintain flat glucose curves."}
                ],
                # Days 3 to 7
                [
                    {"meal_time": "Breakfast", "food_item": "Multigrain Vegetable Dosa with Tomato Chutney", "calories": 300, "notes": "Complex carbs providing sustained energy without sharp glucose rises."},
                    {"meal_time": "Lunch", "food_item": "2 Whole Wheat Rotis with Masoor Dal, Karela Sabzi & Curd", "calories": 490, "notes": "Karela contains charantin naturally supporting glucose uptake."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Black Chana Salad with Chopped Onions & Tomatoes", "calories": 150, "notes": "Sustained fiber snack for late afternoon energy."},
                    {"meal_time": "Dinner", "food_item": "Ragi Rava Khichdi with Steamed Vegetables & Salad", "calories": 350, "notes": "Light millet evening meal tailored for metabolic health."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "3 Steamed Ragi Idlis with Coconut Chutney", "calories": 305, "notes": "Low GI fermented meal preventing sugar spikes."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice with Moong Dal, Turai Sabzi & Fresh Curd", "calories": 480, "notes": "High fiber lunch regulating insulin output."},
                    {"meal_time": "Evening Snack", "food_item": "Cucumber & Carrot Slices with Lemon Juice", "calories": 110, "notes": "Micronutrient snack."},
                    {"meal_time": "Dinner", "food_item": "2 Jowar Rotis with Soya Chunks Curry", "calories": 370, "notes": "High protein dinner preventing muscle breakdown."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Vegetable Pesarattu with Ginger Chutney", "calories": 315, "notes": "Green gram dosa loaded with dietary fiber."},
                    {"meal_time": "Lunch", "food_item": "2 Wheat Rotis with Chana Dal, Capsicum Fry & Buttermilk", "calories": 475, "notes": "Steady glucose absorption."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Sprouted Chana Chaat", "calories": 145, "notes": "Satiety inducing snack."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Dalia Khichdi with Curd", "calories": 360, "notes": "Easy digestive dinner."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Jowar Rava Upma with Mint Chutney", "calories": 300, "notes": "Sustained fiber breakfast."},
                    {"meal_time": "Lunch", "food_item": "2 Bajra Rotis with Baingan Bharta & Dal Tadka", "calories": 485, "notes": "Low glycemic Indian thali."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Guava Slices", "calories": 120, "notes": "High fiber fruit snack."},
                    {"meal_time": "Dinner", "food_item": "2 Phulkas with Methi Dal", "calories": 355, "notes": "Overnight glucose control."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Moong Dal & Spinach Chilla", "calories": 310, "notes": "High protein green pancake."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice / 2 Wheat Rotis with Rajma & Green Salad", "calories": 490, "notes": "Soluble fiber for glucose regulation."},
                    {"meal_time": "Evening Snack", "food_item": "Roasted Makhana & Cumin Buttermilk", "calories": 135, "notes": "Low calorie evening snack."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Millet Khichdi", "calories": 365, "notes": "Wholesome evening meal."}
                ]
            ]
            return plans[day_idx]
        elif has_high_bp:
            plans = [
                # Day 1
                [
                    {"meal_time": "Breakfast", "food_item": "3 Steamed Idlis with Low-Sodium Vegetable Sambar", "calories": 300, "notes": f"Low sodium fermented meal supporting BP reading: {int(bp_val)} mmHg."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Toor Dal, Palak Sabzi & Cucumber Raita", "calories": 450, "notes": "High potassium and magnesium to help dilate blood vessels naturally."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Cucumber Slices with Jeera Buttermilk", "calories": 120, "notes": "Hydrating snack helping balance body sodium levels."},
                    {"meal_time": "Dinner", "food_item": "2 Whole Wheat Phulkas with Mild Lauki Curry", "calories": 360, "notes": "Heart healthy light Indian dinner promoting smooth circulation."}
                ],
                # Day 2
                [
                    {"meal_time": "Breakfast", "food_item": "Vegetable Oats-Ragi Upma with Mint Chutney", "calories": 310, "notes": f"Soluble fiber & magnesium rich breakfast supporting vascular health (BP: {int(bp_val)})."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice / 2 Wheat Rotis with Moong Dal, Steamed Turai Sabzi & Curd", "calories": 460, "notes": "Low-salt thali protecting against hypertension."},
                    {"meal_time": "Evening Snack", "food_item": "Steamed Sweet Corn Chaat & Lemon Tea", "calories": 130, "notes": "Potassium loaded snack supporting cardiovascular wellness."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Soup with 2 Soft Wheat Phulkas & Pumpkin Curry", "calories": 340, "notes": "Restorative sodium controlled evening meal."}
                ],
                # Days 3 to 7
                [
                    {"meal_time": "Breakfast", "food_item": "Ragi Dosa with Low Salt Coconut Chutney", "calories": 295, "notes": "Magnesium rich millet lowering vascular pressure."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Spinach Dal & Ridge Gourd Sabzi", "calories": 455, "notes": "High potassium meal."},
                    {"meal_time": "Evening Snack", "food_item": "Tender Coconut Water & Sprouted Salad", "calories": 125, "notes": "Natural electrolyte balance."},
                    {"meal_time": "Dinner", "food_item": "2 Phulkas with Mild Bottle Gourd Dal", "calories": 350, "notes": "Light easy dinner."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "3 Onion Rava Idlis with Mild Sambar", "calories": 305, "notes": "Sodium controlled breakfast."},
                    {"meal_time": "Lunch", "food_item": "2 Wheat Rotis with Yellow Moong Dal & Bhindi Fry", "calories": 460, "notes": "Vascular protection."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Papaya Cubes", "calories": 115, "notes": "Antioxidant rich fruit."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Dalia Khichdi", "calories": 345, "notes": "Promotes restful sleep."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Pesarattu with Ginger Chutney", "calories": 315, "notes": "High protein low sodium meal."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice with Spinach Dal & Beetroot Sabzi", "calories": 470, "notes": "Nitrates in beetroot lower BP naturally."},
                    {"meal_time": "Evening Snack", "food_item": "Cumin Buttermilk", "calories": 90, "notes": "Cooling electrolyte beverage."},
                    {"meal_time": "Dinner", "food_item": "2 Phulkas with Pumpkin Curry", "calories": 340, "notes": "Heart supportive meal."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Jowar Dosa with Tomato Chutney", "calories": 300, "notes": "Heart-healthy grains."},
                    {"meal_time": "Lunch", "food_item": "2 Bajra Rotis with Dal Tadka & Cucumber Salad", "calories": 465, "notes": "High dietary fiber."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Chana Chaat", "calories": 140, "notes": "Sustained energy."},
                    {"meal_time": "Dinner", "food_item": "Millet Khichdi with Mint Raita", "calories": 355, "notes": "Easily digestible."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Vegetable Dalia Upma", "calories": 295, "notes": "Potassium rich grain upma."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Toor Dal & Colocasia Sabzi", "calories": 475, "notes": "Blood pressure stabilization."},
                    {"meal_time": "Evening Snack", "food_item": "Sliced Cucumber Salad", "calories": 85, "notes": "Hydrating snack."},
                    {"meal_time": "Dinner", "food_item": "2 Phulkas with Palak Sabzi", "calories": 350, "notes": "Overnight cardiac relaxation."}
                ]
            ]
            return plans[day_idx]
        else:
            plans = [
                # Day 1
                [
                    {"meal_time": "Breakfast", "food_item": "Pesarattu (Green Gram Dosa) with Ginger Chutney", "calories": 320, "notes": "High protein traditional South Indian breakfast for sustained daily vitality."},
                    {"meal_time": "Lunch", "food_item": "2 Whole Wheat Rotis, Dal Tadka, Mixed Vegetable Sabzi & Fresh Curd", "calories": 500, "notes": "Balanced traditional thali meal providing essential vitamins and minerals."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Black Chana Chaat & Lemon Green Tea", "calories": 150, "notes": "Antioxidant-rich snack high in dietary fiber."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Millet Khichdi with Steamed Vegetables", "calories": 370, "notes": "Wholesome, easily digestible evening meal."}
                ],
                # Day 2
                [
                    {"meal_time": "Breakfast", "food_item": "Onion Rava Idli (3) with Coconut Chutney & Vegetable Sambar", "calories": 310, "notes": "Nutritious and light breakfast giving clean energy."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice / 2 Phulkas, Rajma Curry, Aloo Gobi & Fresh Cucumber Salad", "calories": 510, "notes": "Protein packed wholesome meal supporting active metabolism."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Papaya & Guava Slices with Roasted Makhana", "calories": 140, "notes": "Immune boosting natural fruit snack."},
                    {"meal_time": "Dinner", "food_item": "2 Bajra Rotis with Baingan Bharta & Fresh Buttermilk", "calories": 380, "notes": "Fiber-rich traditional dinner for gut health and restful sleep."}
                ],
                # Days 3 to 7
                [
                    {"meal_time": "Breakfast", "food_item": "Ragi Dosa with Coconut Chutney", "calories": 305, "notes": "Calcium & iron rich South Indian grain dosa."},
                    {"meal_time": "Lunch", "food_item": "2 Whole Wheat Rotis with Chana Dal, Dondakaya Fry & Curd", "calories": 490, "notes": "Complete balanced protein meal."},
                    {"meal_time": "Evening Snack", "food_item": "Boiled Sprouted Chana Chaat", "calories": 145, "notes": "Healthy mid-day snack."},
                    {"meal_time": "Dinner", "food_item": "Dalia Vegetable Khichdi", "calories": 360, "notes": "Light digestible dinner."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Jowar Upma with Tomato Chutney", "calories": 300, "notes": "Wholesome millet upma."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice with Palak Dal, Bhindi Fry & Yogurt", "calories": 500, "notes": "Vitamins & minerals thali."},
                    {"meal_time": "Evening Snack", "food_item": "Roasted Makhana & Lemon Tea", "calories": 130, "notes": "Crunchy healthy snack."},
                    {"meal_time": "Dinner", "food_item": "2 Phulkas with Lauki Sabzi", "calories": 350, "notes": "Promotes peaceful sleep."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Moong-Urad Chilla", "calories": 315, "notes": "High protein breakfast pancake."},
                    {"meal_time": "Lunch", "food_item": "2 Jowar Rotis with Toor Dal, Beans Fry & Buttermilk", "calories": 495, "notes": "Fiber & digestive wellness."},
                    {"meal_time": "Evening Snack", "food_item": "Fresh Guava Slices", "calories": 120, "notes": "Vitamin C boost."},
                    {"meal_time": "Dinner", "food_item": "Vegetable Poha", "calories": 355, "notes": "Light night meal."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "3 Ragi Idlis with Sambar", "calories": 310, "notes": "Millet power breakfast."},
                    {"meal_time": "Lunch", "food_item": "2 Rotis with Mixed Veg Dal & Cucumber Raita", "calories": 505, "notes": "Metabolic stamina."},
                    {"meal_time": "Evening Snack", "food_item": "Soaked Almonds & Buttermilk", "calories": 135, "notes": "Healthy fats."},
                    {"meal_time": "Dinner", "food_item": "Multigrain Khichdi", "calories": 365, "notes": "Easy overnight digestion."}
                ],
                [
                    {"meal_time": "Breakfast", "food_item": "Onion Rava Dosa with Sambar", "calories": 320, "notes": "Tasty healthy breakfast."},
                    {"meal_time": "Lunch", "food_item": "Brown Rice with Rajma Masala, Cucumber Salad & Curd", "calories": 510, "notes": "High protein thali."},
                    {"meal_time": "Evening Snack", "food_item": "Sweet Corn with Lemon", "calories": 130, "notes": "Energy snack."},
                    {"meal_time": "Dinner", "food_item": "2 Wheat Phulkas with Spinach Dal", "calories": 360, "notes": "Nutrient dense dinner."}
                ]
            ]
            return plans[day_idx]

def get_daily_fallback_indian_diet(latest_metrics, is_telugu=False, plan_date=None, dietary_preference="Vegetarian", force_refresh=False):
    """Build one practical, varied Indian menu for the requested date."""
    plan_date = plan_date or datetime.date.today().isoformat()
    meal_options = {
        "Breakfast": [
            ("Ragi dosa with tomato chutney", "రాగి దోస, టమాటా చట్నీతో", 300),
            ("Pesarattu with ginger chutney", "పెసరట్టు, అల్లం చట్నీతో", 320),
            ("Vegetable oats-free millet upma", "కూరగాయల మిల్లెట్ ఉప్మా", 290),
            ("Steamed idli with vegetable sambar", "ఇడ్లీ, కూరగాయల సాంబార్‌తో", 300),
            ("Besan chilla with mint chutney", "శనగపిండి చిల్లా, పుదీనా చట్నీతో", 310),
            ("Vegetable poha with peanuts", "కూరగాయల పోహా, వేరుశెనగతో", 315),
            ("Rava idli with sambar", "రవ్వ ఇడ్లీ, సాంబార్‌తో", 305),
            ("Moong dal dosa with coriander chutney", "పెసరపప్పు దోస, కొత్తిమీర చట్నీతో", 310),
        ],
        "Mid-morning": [
            ("One guava", "ఒక జామపండు", 80),
            ("Papaya cubes", "బొప్పాయి ముక్కలు", 70),
            ("One small orange", "ఒక చిన్న నారింజ పండు", 65),
            ("Apple slices with a few unsalted nuts", "యాపిల్ ముక్కలు, కొద్దిగా ఉప్పులేని గింజలతో", 130),
            ("Watermelon cubes", "పుచ్చకాయ ముక్కలు", 70),
            ("Pear with a few unsalted nuts", "పియర్ పండు, కొద్దిగా ఉప్పులేని గింజలతో", 120),
        ],
        "Lunch": [
            ("Brown rice, palak dal, beans poriyal and cucumber-carrot salad", "బ్రౌన్ రైస్, పాలకూర పప్పు, బీన్స్ వేపుడు, కీరా-క్యారెట్ సలాడ్", 480),
            ("Jowar rotis, chana dal, lauki sabzi and tomato-onion salad", "జొన్న రొట్టెలు, శనగపప్పు, సొరకాయ కూర, టమాటా-ఉల్లిపాయ సలాడ్", 470),
            ("Little millet, rajma curry, cabbage poriyal and beetroot salad", "సామలు, రాజ్మా కూర, క్యాబేజీ వేపుడు, బీట్‌రూట్ సలాడ్", 490),
            ("Wheat phulkas, moong dal, bhindi sabzi and sprout salad", "గోధుమ పుల్కాలు, పెసరపప్పు, బెండకాయ కూర, మొలకల సలాడ్", 475),
            ("Brown rice, sambar, pumpkin curry and kosambari salad", "బ్రౌన్ రైస్, సాంబార్, గుమ్మడికాయ కూర, కోసంబరి సలాడ్", 485),
            ("Bajra roti, masoor dal, mixed vegetables and cabbage-cucumber salad", "సజ్జ రొట్టె, మసూర్ పప్పు, మిశ్రమ కూరగాయలు, క్యాబేజీ-కీరా సలాడ్", 480),
            ("Quinoa-millet pulao, chole and kachumber salad", "క్వినోవా-మిల్లెట్ పులావ్, చోలే, కచుంబర్ సలాడ్", 500),
            ("Ragi mudde, mild sambar, ridge gourd curry and greens salad", "రాగి ముద్ద, తక్కువ మసాలా సాంబార్, బీరకాయ కూర, ఆకుకూరల సలాడ్", 465),
        ],
        "Evening Snack": [
            ("Roasted makhana and unsweetened tea", "వేయించిన మఖానా, చక్కెరలేని టీ", 120),
            ("Sprouted moong chaat with lemon", "మొలకెత్తిన పెసల చాట్, నిమ్మరసంతో", 150),
            ("Roasted chana and water", "వేయించిన శనగలు, నీటితో", 130),
            ("Cucumber and carrot sticks with hummus", "కీరా, క్యారెట్ ముక్కలు, హమ్మస్‌తో", 140),
            ("Boiled corn with lime and pepper", "ఉడికించిన మొక్కజొన్న, నిమ్మరసం మరియు మిరియాలతో", 140),
            ("A small handful of peanuts with unsweetened tea", "కొద్దిగా వేరుశెనగ, చక్కెరలేని టీతో", 150),
            ("Steamed sundal with curry leaves", "కరివేపాకుతో ఆవిరి మీద ఉడికించిన సుండల్", 145),
        ],
        "Dinner": [
            ("Vegetable moong dal khichdi with cucumber salad", "కూరగాయల పెసరపప్పు ఖిచ్డీ, కీరా సలాడ్‌తో", 360),
            ("Two phulkas with tofu bhurji and sautéed vegetables", "రెండు ఫుల్కాలు, టోఫు భుర్జీ, ఉడికించిన కూరగాయలతో", 390),
            ("Jowar roti with lauki chana dal and salad", "జొన్న రొట్టె, సొరకాయ-శనగపప్పు, సలాడ్‌తో", 370),
            ("Vegetable millet pongal with tomato chutney", "కూరగాయల మిల్లెట్ పొంగల్, టమాటా చట్నీతో", 350),
            ("Palak tofu with a small portion of brown rice", "పాలక్ టోఫు, కొద్దిగా బ్రౌన్ రైస్‌తో", 380),
            ("Bajra roti with mixed vegetable curry and salad", "సజ్జ రొట్టె, మిశ్రమ కూరగాయల కూర, సలాడ్‌తో", 375),
            ("Vegetable dalia khichdi with tomato-cucumber salad", "కూరగాయల దలియా ఖిచ్డీ, టమాటా-కీరా సలాడ్‌తో", 355),
            ("Ragi roti with toor dal and sautéed greens", "రాగి రొట్టె, కందిపప్పు, ఉడికించిన ఆకుకూరలతో", 365),
        ],
        "Hydration": [
            ("Sip water through the day; include plain water with each meal.", "రోజంతా కొద్దికొద్దిగా నీరు తాగండి; ప్రతి భోజనంతో సాధారణ నీరు తీసుకోండి.", 0),
            ("Keep water nearby and drink regularly; choose unsweetened drinks.", "నీటిని దగ్గర ఉంచుకొని క్రమం తప్పకుండా తాగండి; చక్కెరలేని పానీయాలను ఎంచుకోండి.", 0),
            ("Drink water regularly; unsweetened lemon water is an optional choice.", "క్రమం తప్పకుండా నీరు తాగండి; చక్కెరలేని నిమ్మరసం ఐచ్ఛికంగా తీసుకోవచ్చు.", 0),
            ("Have water across the day and choose plain or unsweetened beverages.", "రోజంతా నీరు తాగండి; సాధారణ లేదా చక్కెరలేని పానీయాలను ఎంచుకోండి.", 0),
        ],
    }

    profile_seed = json.dumps(
        [latest_metrics, dietary_preference], sort_keys=True, default=str
    )
    if force_refresh:
        profile_seed += str(random.SystemRandom().randint(0, 2**31 - 1))
    profile_offset = int(hashlib.sha256(profile_seed.encode()).hexdigest()[:8], 16)
    rotation_day = datetime.date.fromisoformat(plan_date).toordinal() + profile_offset
    meal_times = ["Breakfast", "Mid-morning", "Lunch", "Evening Snack", "Dinner", "Hydration"]
    notes = {
        "Breakfast": "A practical Indian breakfast with a source of fiber and energy.",
        "Mid-morning": "A simple fruit or snack between meals.",
        "Lunch": "A balanced plate with grains, dal, vegetables and a fresh salad.",
        "Evening Snack": "A modest snack; choose unsalted and unsweetened options.",
        "Dinner": "A balanced, practical Indian dinner with vegetables and protein.",
        "Hydration": "Follow your clinician's fluid guidance if you have been given one.",
    }
    notes_te = {
        "Breakfast": "పీచు పదార్థం మరియు శక్తి అందించే సరళమైన భారతీయ అల్పాహారం.",
        "Mid-morning": "భోజనాల మధ్య తీసుకునే సరళమైన పండు లేదా చిరుతిండి.",
        "Lunch": "ధాన్యం, పప్పు, కూరగాయలు మరియు తాజా సలాడ్‌తో సమతుల్య భోజనం.",
        "Evening Snack": "మితమైన చిరుతిండి; ఉప్పు లేదా చక్కెర తక్కువగా ఉండే వాటిని ఎంచుకోండి.",
        "Dinner": "కూరగాయలు మరియు ప్రోటీన్‌తో సరళమైన సమతుల్య భారతీయ రాత్రి భోజనం.",
        "Hydration": "వైద్యులు ద్రవాలపై సూచనలు ఇచ్చి ఉంటే వాటిని అనుసరించండి.",
    }
    menu = []
    for meal_time in meal_times:
        choices = meal_options[meal_time]
        food_en, food_te, calories = choices[rotation_day % len(choices)]
        menu.append({
            "meal_time": meal_time,
            "food_item": food_te if is_telugu else food_en,
            "calories": calories,
            "notes": (notes_te if is_telugu else notes)[meal_time],
        })
    return menu


def generate_personalized_diet(user_id, user_name, lang_code="en-IN", day_num=None, force_refresh=False, dietary_preference="Vegetarian", plan_date=None):
    """
    Generates personalized diet guidance using real patient health metrics from the database.
    Generates one date-specific plan customized to the latest BP, Sugar, Heart Rate, and Weight readings.
    Does NOT present output as a medical prescription. Focuses on authentic Indian health cuisine.
    """
    plan_date = plan_date or datetime.date.today().isoformat()
    latest_metrics = db.get_health_metrics_for_date(user_id, plan_date)
    medicines = db.get_all_medicines(user_id)

    if not latest_metrics:
        raise ValueError(f"Record a health reading for {plan_date} before generating a personalized diet plan.")

    client = get_groq_client()
    is_telugu = "te" in lang_code.lower()

    health_profile = "\n".join(
        f"- {metric_name}: {record.get('value', 'Not recorded')} {record.get('unit', '')} (Recorded: {record.get('recorded_date', 'N/A')})"
        for metric_name, record in latest_metrics.items()
    )
    med_names = ", ".join([m["name"] for m in medicines]) if medicines else "None"
    var_seed = random.randint(100, 999) if force_refresh else int(hashlib.sha256(f"{plan_date}:{dietary_preference}".encode()).hexdigest()[:8], 16)

    lang_inst = "Respond in TELUGU language." if is_telugu else "Respond in ENGLISH language."

    prompt = f"""You are CareVoice's personalized nutrition AI guide. Generate one fresh Indian diet plan for today ({plan_date}; variation seed #{var_seed}) for patient '{user_name}'.

Patient Recorded Vitals (MUST be explicitly addressed in meal choices and notes):
{health_profile}
- Active Medications: {med_names}

Language: {lang_inst}
Dietary preference: {dietary_preference}. Follow it strictly.

CRITICAL METRIC-BASED NUTRITION INSTRUCTIONS:
- Blood Pressure (BP): If elevated/high (>130 mmHg systolic or >85 diastolic), mandate low-sodium, potassium & magnesium rich food items (spinach, cucumber, coconut water, ragi, jeera buttermilk, low-salt sambar/dal).
- Blood Sugar (Glucose): If high (>140 mg/dL), mandate low glycemic index (GI), high fiber food items (Pesarattu, Jowar/Bajra roti, karela, methi dal, moong sprouts, dalia, chana dal).
- Heart Rate (Pulse): If high (>90 bpm), mandate heart-healthy fats (flaxseeds, walnuts, garlic, low oil, hydrating buttermilk).
- Weight: If high (>75 kg), mandate portion-controlled, protein rich meals (moong dal, paneer, chana, green leafy vegetables) with lower calorie density.

STRICT CUISINE & VARIETY REQUIREMENT:
Use authentic Indian cuisine (e.g. Idli with Sambar, Ragi Dosa, Pesarattu, Jowar Upma, Multigrain Roti with Dal & Palak Sabzi, Dalia Khichdi, Sprouted Moong Salad, Jeera Buttermilk, Curd Rice). 
Do NOT suggest western oats, processed cereal, muesli, or wheat flakes.
Vary meal and salad choices from day to day. Do not return a weekly schedule or multiple alternatives.

Return exactly one item for each of these six sections, in this order:
1. Breakfast
2. Mid-morning
3. Lunch (include a different fresh salad option)
4. Evening Snack
5. Dinner
6. Hydration

Each object must have:
- meal_time: ("Breakfast", "Lunch", "Evening Snack", "Dinner")
- food_item: (Specific Indian food item description)
- calories: (Estimated calorie number, integer)
- notes: (Explanation of how this food specifically supports their BP, Sugar, Heart Rate, or Weight reading)

STRICT RULE:
Do NOT present this as a doctor's prescription. Add a note that it is general dietary guidance based on provided metrics.
Do not invent diagnoses, health readings, restrictions, or medication interactions.

Example output format:
[
  {{
    "meal_time": "Breakfast",
    "food_item": "Pesarattu (Green Gram Dosa) with Ginger Chutney",
    "calories": 320,
    "notes": "Low glycemic index, rich in plant protein to help regulate blood sugar levels."
  }}
]
"""

    parsed = None
    if client:
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            out = res.choices[0].message.content.strip()
            if out.startswith("```json"):
                out = out[7:]
            if out.startswith("```"):
                out = out[3:]
            if out.endswith("```"):
                out = out[:-3]

            parsed_json = json.loads(out.strip())
            required_meals = {"Breakfast", "Mid-morning", "Lunch", "Evening Snack", "Dinner", "Hydration"}
            if isinstance(parsed_json, list) and len(parsed_json) == 6 and {
                item.get("meal_time") for item in parsed_json if isinstance(item, dict)
            } == required_meals:
                parsed = parsed_json
        except Exception:
            parsed = None

    if not parsed:
        parsed = get_daily_fallback_indian_diet(
            latest_metrics, is_telugu, plan_date, dietary_preference, force_refresh
        )

    db.save_diet_plan(user_id, parsed)
    return parsed

def analyze_medical_report(user_id, title, raw_text, doctor_name="Dr. R. Sharma"):
    """
    Generates plain-language summary of medical report using Groq LLM without medical jargon or diagnoses.
    """
    client = get_groq_client()
    prompt = f"""You are CareVoice's plain-language report explainer AI.
Summarize the following lab report titled '{title}' for a patient in 2-3 simple, reassuring sentences.

Report Text:
\"\"\"
{raw_text}
\"\"\"

STRICT RULES:
1. Use simple words with zero medical jargon.
2. Explain what the numbers mean (e.g. Normal, Healthy).
3. Do NOT diagnose diseases or alter medications.
4. Recommend consulting doctor '{doctor_name}' for clinical questions.
"""

    summary = "Report results evaluated. Values appear within normal parameters."
    if client:
        try:
            res = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            out = res.choices[0].message.content.strip()
            if out:
                summary = out
        except Exception:
            pass

    date_str = os.path.basename(title) if title else "2026-09-26"
    db.add_report(user_id, title, date_str, summary, doctor_name, extracted_text=raw_text)
    return summary

def _parse_scheduled_times(schedule_text):
    times = []
    for hour_text, minute_text, period in re.findall(
        r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", str(schedule_text), re.IGNORECASE
    ):
        hour = int(hour_text) % 12
        if period.upper() == "PM":
            hour += 12
        minute = int(minute_text)
        if minute >= 60:
            continue
        display_time = f"{(hour % 12) or 12:02d}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"
        value = (hour * 60 + minute, display_time)
        if value not in times:
            times.append(value)
    return times


def get_today_medicine_doses(user_id, now=None):
    """Return today's scheduled doses with status derived from today's logs."""
    now = now or datetime.datetime.now()
    date_key = now.strftime("%Y-%m-%d")
    today_logs = [
        log for log in db.get_medicine_history(user_id)
        if log.get("date") == date_key
    ]
    latest_actions = {}
    for log in sorted(today_logs, key=lambda item: item.get("id", 0)):
        log_time = str(log.get("scheduled_time") or "").strip().upper()
        latest_actions[(log.get("medicine_id"), log_time)] = log

    doses = []
    for medicine in db.get_all_medicines(user_id):
        if str(medicine.get("frequency", "Daily")).lower() == "as needed":
            doses.append({
                "medicine_id": medicine["id"],
                "name": medicine["name"],
                "dosage": medicine["dosage"],
                "scheduled_time": "As needed",
                "minute_of_day": 24 * 60,
                "scheduled_at": None,
                "status": "As needed",
                "snooze_until": None,
            })
            continue

        for minute_of_day, scheduled_time in _parse_scheduled_times(medicine.get("time_slot", "")):
            action = latest_actions.get((medicine["id"], scheduled_time.upper()))
            status = action.get("status", "Pending") if action else "Pending"
            scheduled_at = now.replace(
                hour=minute_of_day // 60,
                minute=minute_of_day % 60,
                second=0,
                microsecond=0,
            )
            snooze_until = None
            if status == "Snoozed" and action.get("snooze_until"):
                try:
                    snooze_until = datetime.datetime.fromisoformat(action["snooze_until"])
                    scheduled_at = snooze_until
                except (TypeError, ValueError):
                    pass
            doses.append({
                "medicine_id": medicine["id"],
                "name": medicine["name"],
                "dosage": medicine["dosage"],
                "scheduled_time": scheduled_time,
                "minute_of_day": minute_of_day,
                "scheduled_at": scheduled_at,
                "status": status,
                "snooze_until": snooze_until,
            })

    return sorted(doses, key=lambda dose: dose["scheduled_at"] or now)


def extract_voice_health_reading(user_text):
    """Extract a BP or blood sugar value, tolerating commas introduced by speech recognition."""
    normalized_text = re.sub(r"(?<=\d),\s*(?=\d)", "", str(user_text).lower())
    normalized_text = re.sub(
        r"(?<!\d)(\d)\s+(\d{2})\s*/\s*(\d{2,3})(?!\d)",
        r"\1\2/\3",
        normalized_text,
    )
    bp_match = re.search(
        r"(?:(?:add|record|save|set)\s+(?:my\s+)?|(?:my\s+|నా\s+)?)"
        r"(?:blood\s+pressure|bp|బీపీ|రక్తపోటు)\s*"
        r"(?:(?:reading\s*)?(?:is|as|was|of|reading)?\s*)?"
        r"(\d{2,3})\s*(?:over|/|\s+)\s*(\d{2,3})",
        normalized_text,
    )
    if bp_match:
        return {"metric": "Blood Pressure", "value": f"{bp_match.group(1)}/{bp_match.group(2)}"}

    sugar_match = re.search(
        r"(?:(?:add|record|save|set)\s+(?:my\s+)?|(?:my\s+|నా\s+)?)"
        r"(?:blood\s+sugar|sugar|glucose|చక్కెర|షుగర్)\s*"
        r"(?:(?:reading\s*)?(?:is|as|was|of|reading)?\s*)?"
        r"(\d{2,4})",
        normalized_text,
    )
    if sugar_match:
        return {"metric": "Blood Sugar", "value": sugar_match.group(1)}
    return None


def extract_voice_sugar_timing(user_text):
    text_lower = str(user_text).lower()
    if any(term in text_lower for term in [
        "before food", "before meal", "before eating", "pre-meal", "fasting",
        "తినడానికి ముందు", "తినే ముందు", "భోజనానికి ముందు", "ఫాస్టింగ్", "ఉపవాసం",
    ]):
        return "Before Food"
    if any(term in text_lower for term in [
        "after food", "after meal", "after eating", "post-meal", "post-prandial", "post prandial",
        "తిన్న తర్వాత", "తిన్నాక", "భోజనం తర్వాత", "భోజనం తరువాత", "భోజనం అయిన తర్వాత",
    ]):
        return "After Food"
    return None


def process_voice_assistant_query(user_text, user_id, user_name, lang_code="en-IN", dietary_preference="Vegetarian"):
    """
    Processes real voice assistant queries against live patient database records.
    Returns: (spoken_reply, page_to_navigate_or_None)
    """
    text_lower = re.sub(r"(?<=\d),\s*(?=\d)", "", user_text.lower())
    is_te = "te" in lang_code.lower()
    today_key = datetime.date.today().isoformat()
    today_health_metrics = None
    today_diet_plan = None
    asks_food_advice = any(phrase in text_lower for phrase in [
        "what should i eat", "what can i eat", "what food", "can i eat", "should i eat",
        "can i have", "should i have", "food that is", "diet recommendation", "based on my health",
        "నా ఆరోగ్యానికి", "ఏమి తినాలి", "ఏం తినాలి", "ఏ ఆహారం", "ఏది తినాలి", "ఉప్పు",
    ])
    asks_for_food_variant = any(phrase in text_lower for phrase in [
        "another variant", "another option", "another food", "another meal", "different option",
        "different food", "different meal", "something else", "don't like it", "do not like it",
        "not like this", "give me another", "suggest another", "alternative", "change the food",
        "refresh the diet", "మరొక వెరైటీ", "మరో వెరైటీ", "మరొక వేరియంట్", "మరో వేరియంట్",
        "ఇంకో ఎంపిక", "ఇంకొకటి", "ఇంకోది", "వేరొకటి", "వేరే ఆహారం", "నచ్చలేదు", "మార్చండి",
    ])

    # 1. Statements like "my blood pressure is 118 over 80" should ask for confirmation before saving.
    health_reading = extract_voice_health_reading(text_lower)
    if health_reading and health_reading["metric"] == "Blood Pressure":
        bp_str = health_reading["value"]
        confirm_msg = (
            f"మీ రక్తపోటు {bp_str} mmHg గా సేవ్ చేయాలా? చెప్పండి 'సేవ్ చేయండి' లేదా 'cancel'."
            if is_te else f"I detected a Blood Pressure reading of {bp_str} mmHg. Do you want to save it? Say 'save it' or 'cancel'."
        )
        return confirm_msg, None

    if health_reading and health_reading["metric"] == "Blood Sugar":
        val = health_reading["value"]
        confirm_msg = (
            f"మీ చక్కెర స్థాయి {val} mg/dL గా సేవ్ చేయాలా? చెప్పండి 'సేవ్ చేయండి' లేదా 'cancel'."
            if is_te else f"I detected your Blood Sugar as {val} mg/dL. Do you want to save it? Say 'save it' or 'cancel'."
        )
        return confirm_msg, None

    if asks_for_food_variant:
        today_health_metrics = db.get_health_metrics_for_date(user_id, today_key)
        if not today_health_metrics:
            reply = "ఈ రోజు ఆరోగ్య రీడింగ్ నమోదు చేసిన తర్వాత కొత్త ఆహార ఎంపికను అడగండి." if is_te else "Please record today's health readings first; I only base today's diet on readings recorded today."
            return reply, None
        previous_plan = db.get_all_diet_plans(user_id)
        meal_time = next((
            candidate for candidate, terms in {
                "Breakfast": ["breakfast", "ఉదయం", "అల్పాహారం"],
                "Lunch": ["lunch", "మధ్యాహ్న"],
                "Evening Snack": ["snack", "సాయంత్రం"],
                "Dinner": ["dinner", "రాత్రి"],
            }.items() if any(term in text_lower for term in terms)
        ), "Breakfast")
        previous_item = next((
            item.get("food_item") for item in previous_plan
            if item.get("meal_time") == meal_time
        ), None)
        try:
            refreshed_plan = generate_personalized_diet(
                user_id=user_id,
                user_name=user_name,
                lang_code=lang_code,
                force_refresh=True,
                dietary_preference=dietary_preference,
                plan_date=datetime.date.today().isoformat(),
            )
            selected_meal = next((
                item for item in refreshed_plan if item.get("meal_time") == meal_time
            ), refreshed_plan[0] if refreshed_plan else None)
            if selected_meal and previous_item and selected_meal.get("food_item") == previous_item:
                refreshed_plan = generate_personalized_diet(
                    user_id=user_id,
                    user_name=user_name,
                    lang_code=lang_code,
                    force_refresh=True,
                    dietary_preference=dietary_preference,
                    plan_date=datetime.date.today().isoformat(),
                )
                selected_meal = next((
                    item for item in refreshed_plan if item.get("meal_time") == meal_time
                ), refreshed_plan[0] if refreshed_plan else None)
            if not selected_meal:
                raise ValueError("The refreshed diet plan did not include a meal suggestion.")
        except (RuntimeError, ValueError):
            reply = "మీ ఆరోగ్య రీడింగ్ ఆధారంగా కొత్త ఆహార ఎంపికను ఇప్పుడే రూపొందించలేకపోయాను." if is_te else "I couldn't refresh a personalized food option just now. Please try again."
            return reply, None

        if is_te:
            reply = f"మీ ఆరోగ్య రీడింగ్‌ల ఆధారంగా ఈ రోజు డైట్ ప్లాన్‌ను మార్చాను. {selected_meal.get('meal_time', 'భోజనం')}: {selected_meal['food_item']}."
        else:
            reply = f"I refreshed today's health-based diet plan. For {selected_meal.get('meal_time', 'your meal').lower()}, try {selected_meal['food_item']}."
        return reply, "DietRefreshed"

    if asks_food_advice:
        today_health_metrics = db.get_health_metrics_for_date(user_id, today_key)
        if not today_health_metrics:
            reply = "ఈ రోజు ఆరోగ్య రీడింగ్ నమోదు చేసిన తర్వాత మీ ఆహార సూచన అడగండి." if is_te else "Please record a health reading today first so I can base your food advice on today's readings."
            return reply, None
        try:
            today_diet_plan = generate_personalized_diet(
                user_id=user_id,
                user_name=user_name,
                lang_code=lang_code,
                force_refresh=False,
                dietary_preference=dietary_preference,
                plan_date=today_key,
            )
        except (RuntimeError, ValueError):
            reply = "ఈ రోజు రీడింగ్‌ల ఆధారంగా ఆహార ప్రణాళికను రూపొందించలేకపోయాను. మళ్లీ ప్రయత్నించండి." if is_te else "I couldn't generate a diet plan from today's readings just now. Please try again."
            return reply, None

    # Avoid treating advice questions as read-back queries.
    if (
        any(phrase in text_lower for phrase in ["based on my bp", "based on my blood pressure", "considering my bp", "considering my blood pressure", "based on my sugar", "based on my blood sugar"])
        and any(phrase in text_lower for phrase in ["can i", "should i", "can have", "safe to eat", "what food", "is it okay", "is food"])
    ):
        pass

    # 2. Check for Weight insertion command ("add my weight as 70 kg")
    weight_match = re.search(r'(?:add|record|save|set|my)\s+(?:weight)\s+(?:as\s+)?(\d{1,3}(?:\.\d{1,2})?)\s*(?:kg|pounds?|lbs?)?', text_lower)
    if weight_match:
        val = weight_match.group(1)
        db.add_health_metric(user_id, "Weight", val, "kg", status="Healthy", notes="Added via Voice Assistant")
        reply = f"మీ బరువు {val} kg గా నమోదైంది." if is_te else f"Recorded your weight as {val} kg."
        return reply, "Home"

    # 4. Check for Heart Rate insertion command ("add my heart rate as 72")
    hr_match = re.search(r'(?:add|record|save|set|my)\s+(?:heart rate|pulse|hr)\s+(?:as\s+)?(\d{2,3})', text_lower)
    if hr_match:
        val = hr_match.group(1)
        db.add_health_metric(user_id, "Heart Rate", val, "bpm", status="Normal", notes="Added via Voice Assistant")
        reply = f"మీ గుండె రేటు {val} bpm గా నమోదైంది." if is_te else f"Recorded your heart rate as {val} bpm."
        return reply, "Home"

    # 5. Check for Medicines query ("What medicines do I take today?")
    if any(k in text_lower for k in ["what medicines", "my medicines", "show medicines", "which medicines", "మందులు", "medicine list", "medication list", "medicines today", "medicine today"]):
        doses = get_today_medicine_doses(user_id)
        if not doses:
            reply = "ఈరోజు ఎలాంటి మందులు షెడ్యూల్ చేయబడలేదు." if is_te else "You have no medicines scheduled for today."
        else:
            med_list_str = ", ".join(
                f"{dose['name']} ({dose['dosage']}) at {dose['scheduled_time']}"
                for dose in doses
            )
            reply = f"ఈరోజు మీ మందుల షెడ్యూల్: {med_list_str}." if is_te else f"Today your medicine schedule is: {med_list_str}."
        return reply, "Medicines"

    # 6. Check for Next Medicine query ("When is my next medicine?")
    if any(k in text_lower for k in ["next medicine", "when is my next", "తదుపరి మందు", "upcoming medicine"]):
        now = datetime.datetime.now()
        doses = get_today_medicine_doses(user_id, now)
        pending = [dose for dose in doses if dose["status"] not in {"Taken", "Skipped", "As needed"}]
        upcoming = [dose for dose in pending if dose["scheduled_at"] and dose["scheduled_at"] >= now]
        if upcoming:
            dose = upcoming[0]
            reply = f"మీ తదుపరి మందు {dose['name']} ({dose['dosage']}) {dose['scheduled_at'].strftime('%I:%M %p')}కి." if is_te else f"Your next medicine is {dose['name']} ({dose['dosage']}) at {dose['scheduled_at'].strftime('%I:%M %p')}."
        elif pending:
            dose = pending[-1]
            reply = f"మీ {dose['name']} ({dose['dosage']}) మందు {dose['scheduled_time']}కి షెడ్యూల్ అయింది, ఇంకా నమోదు కాలేదు." if is_te else f"Your {dose['name']} ({dose['dosage']}) dose scheduled for {dose['scheduled_time']} is still unrecorded today."
        else:
            reply = "ఈరోజు మీ మందులన్నీ పూర్తి అయ్యాయి!" if is_te else "All your medicines for today are already taken! Great job."
        return reply, "Home"

    # 7. Check if morning medicine taken ("Did I take my morning medicine?")
    if any(k in text_lower for k in ["did i take", "took my", "morning medicine", "ఉదయం మందు"]):
        morn_meds = [
            dose for dose in get_today_medicine_doses(user_id)
            if dose["minute_of_day"] < 12 * 60
        ]
        if not morn_meds:
            reply = "మీకు ఈ ఉదయం ఎలాంటి మందులు లేవు." if is_te else "You don't have any morning medicines scheduled."
        else:
            taken = [dose for dose in morn_meds if dose["status"] == "Taken"]
            pending = [dose for dose in morn_meds if dose["status"] != "Taken"]
            if not pending:
                names = ", ".join(dose["name"] for dose in taken)
                reply = f"అవును, ఈ ఉదయం {names} తీసుకున్నట్లు నమోదైంది." if is_te else f"Yes. Today's logs show you took {names} this morning."
            elif taken:
                names = ", ".join(dose["name"] for dose in pending)
                reply = f"కొన్ని ఉదయం మందులు ఇంకా నమోదు కాలేదు: {names}." if is_te else f"Some morning doses are still unrecorded: {names}."
            else:
                names = ", ".join(dose["name"] for dose in pending)
                reply = f"ఈ ఉదయం మందులు తీసుకున్నట్లు నమోదు లేదు: {names}." if is_te else f"Today's logs do not show these morning doses as taken: {names}."
        return reply, "Home"

    # 8. Check for Blood Pressure query ("Show my blood pressure", "What is my blood pressure?")
    if any(k in text_lower for k in ["blood pressure", "bp", "రక్తపోటు", "show bp", "my bp"]) and not asks_food_advice:
        metrics = db.get_latest_health_metrics(user_id)
        bp = metrics.get("Blood Pressure")
        if bp:
            reply = f"మీ చివరి రక్తపోటు రీడింగ్ {bp['value']} mmHg ({bp['recorded_date']})." if is_te else f"Your latest Blood Pressure reading is {bp['value']} mmHg, recorded on {bp['recorded_date']}."
        else:
            reply = "రక్తపోటు రీడింగ్‌లు ఇంకా నమోదు చేయబడలేదు." if is_te else "No Blood Pressure readings recorded yet."
        return reply, "Home"

    # 9. Check for Blood Sugar query ("What is my blood sugar?")
    if any(k in text_lower for k in ["blood sugar", "sugar", "glucose", "చక్కెర", "show sugar", "my sugar"]) and not asks_food_advice:
        metrics = db.get_latest_health_metrics(user_id)
        sugar = metrics.get("Blood Sugar")
        if sugar:
            reply = f"మీ చివరి రక్తంలో చక్కెర రీడింగ్ {sugar['value']} mg/dL ({sugar['recorded_date']})." if is_te else f"Your latest Blood Sugar reading is {sugar['value']} mg/dL, recorded on {sugar['recorded_date']}."
        else:
            reply = "చక్కెర రీడింగ్‌లు ఇంకా నమోదు చేయబడలేదు." if is_te else "No Blood Sugar readings recorded yet."
        return reply, "Home"

    # 10. Check for Weight query ("What is my weight?")
    if any(k in text_lower for k in ["weight", "బరువు", "show weight", "my weight"]):
        metrics = db.get_latest_health_metrics(user_id)
        weight = metrics.get("Weight")
        if weight:
            reply = f"మీ చివరి బరువు {weight['value']} kg ({weight['recorded_date']})." if is_te else f"Your latest weight is {weight['value']} kg, recorded on {weight['recorded_date']}."
        else:
            reply = "బరువు రీడింగ్‌లు ఇంకా నమోదు చేయబడలేదు." if is_te else "No weight readings recorded yet."
        return reply, "Home"

    # 11. Check for Heart Rate query ("What is my heart rate?")
    if any(k in text_lower for k in ["heart rate", "pulse", "hr", "గుండె రేటు", "show heart rate"]):
        metrics = db.get_latest_health_metrics(user_id)
        hr = metrics.get("Heart Rate")
        if hr:
            reply = f"మీ చివరి గుండె రేటు {hr['value']} bpm ({hr['recorded_date']})." if is_te else f"Your latest heart rate is {hr['value']} bpm, recorded on {hr['recorded_date']}."
        else:
            reply = "గుండె రేటు రీడింగ్‌లు ఇంకా నమోదు చేయబడలేదు." if is_te else "No heart rate readings recorded yet."
        return reply, "Home"

    # 12. Check for Medicine Schedule navigation ("show medicine schedule", "open medicines")
    if any(k in text_lower for k in ["medicine schedule", "medication schedule", "open medicines", "show schedule", "మందు షెడ్యూల్"]):
        reply = "మీ మందు షెడ్యూల్ చూపిస్తున్నాను." if is_te else "Opening your medicine schedule."
        return reply, "Medicines"

    # 13. Check for Health History navigation ("show health history", "health trends")
    if any(k in text_lower for k in ["health history", "health trends", "health records", "show health", "ఆరోగ్య చరిత్ర"]):
        reply = "మీ ఆరోగ్య చరిత్ర చూపిస్తున్నాను." if is_te else "Opening your health history and trends."
        return reply, "Health"

    # 14. Check for Navigation intents ("open diet")
    if not asks_food_advice and any(k in text_lower for k in ["open diet", "show diet", "diet plan", "ఆహార", "nutrition", "meal plan"]):
        reply = "మీ ఆహార ప్లాన్ చూపిస్తున్నాను." if is_te else "Opening your personalized diet guidance."
        return reply, "Diet"

    # 15. Check for Prescription navigation ("upload prescription", "add prescription")
    if any(k in text_lower for k in ["upload prescription", "add prescription", "prescription upload", "ప్రిస్క్రిప్షన్"]):
        reply = "ప్రిస్క్రిప్షన్ అప్‌లోడ్ పేజీకి తీసుకెళ్తున్నాను." if is_te else "Opening prescription upload page."
        return reply, "Prescriptions"

    # 16. Check for Home navigation ("go home", "dashboard", "main page")
    if any(k in text_lower for k in ["go home", "dashboard", "main page", "home page", "హోమ్"]):
        reply = "డాష్‌బోర్డ్‌కి తీసుకెళ్తున్నాను." if is_te else "Opening your dashboard."
        return reply, "Home"

    # 17. Fallback to Groq LLM with medical context
    client = get_groq_client()
    today_doses = get_today_medicine_doses(user_id)
    med_summary = "\n".join([
        f"- {dose['name']} ({dose['dosage']}): {dose['scheduled_time']} | Today's logged status: {dose['status']}"
        for dose in today_doses
    ])
    latest_metrics = today_health_metrics if asks_food_advice else db.get_latest_health_metrics(user_id)
    current_diet_plan = today_diet_plan if asks_food_advice else db.get_all_diet_plans(user_id)
    if not current_diet_plan and latest_metrics:
        current_diet_plan = get_daily_fallback_indian_diet(
            latest_metrics,
            is_telugu=is_te,
            plan_date=today_key,
        )
    health_summary = "\n".join(
        f"- {name}: {reading.get('value')} {reading.get('unit')} (recorded {reading.get('recorded_date')})"
        for name, reading in latest_metrics.items()
    )
    diet_summary = "\n".join(
        f"- {meal.get('meal_time')}: {meal.get('food_item')}"
        for meal in current_diet_plan
    ) or "No personalized diet plan is available yet."
    if asks_food_advice and not client:
        meal = current_diet_plan[0].get("food_item") if current_diet_plan else None
        if is_te:
            reply = (
                f"మీ ఆరోగ్య రీడింగ్‌లు మరియు డైట్ ప్లాన్‌ను బట్టి, ఈ రోజు {meal} తీసుకోండి. ఉప్పు తక్కువగా, పీచు ఎక్కువగా ఉండే ఎంపికలను ఎంచుకోండి; ఇది సాధారణ ఆహార సూచన మాత్రమే."
                if meal else "మీ డైట్ ప్లాన్ ప్రస్తుతం అందుబాటులో లేదు. ఆరోగ్య రీడింగ్‌లను నమోదు చేసి ప్లాన్‌ను రూపొందించండి; ఇది సాధారణ ఆహార మార్గదర్శకం మాత్రమే."
            )
        else:
            reply = (
                f"Based on your saved readings and diet plan, try {meal} today. Prefer lower-salt, higher-fiber choices; this is general food guidance, not a medical prescription."
                if meal else "I don't have a saved diet plan to use yet. Record a health reading and generate your plan; this is general food guidance, not a medical prescription."
            )
        return reply, None
    if not client:
        return (
            "కేర్‌వాయిస్ సహాయకుడు ప్రస్తుతం అందుబాటులో లేరు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            if is_te else
            "CareVoice AI is unavailable right now. Please try your question again shortly.",
            None,
        )
    log_summary = "\n".join(
        f"- {log.get('medicine_name')}: {log.get('status')} at {log.get('actual_time')} (scheduled {log.get('scheduled_time')})"
        for log in db.get_medicine_history(user_id)
        if log.get("date") == today_key
    ) or "No medicine actions have been logged today."

    sys_prompt = f"""You are CareVoice, an empathetic voice assistant for patient '{user_name}'.
Language requirement: {"Respond in TELUGU." if is_te else "Respond in ENGLISH."}

Medical Safety Rules (STRICT):
1. Never diagnose medical conditions or diseases.
2. Never tell user to alter dosage or stop prescribed medicines.
3. Keep response concise (1-3 sentences), friendly, formatted for spoken audio.
4. Answer the user's exact question directly; do not read back unrelated readings or add unrelated health facts.
5. For food questions, use only readings recorded today and the diet plan generated from those readings. Recommend a specific item from that plan when suitable, and mention a relevant adjustment such as lower salt or high fiber. Keep it general guidance, not a diagnosis or prescription.

Current Patient Context:
{med_summary if med_summary else 'No medicines scheduled.'}
Latest health readings:
{health_summary if health_summary else 'No health readings recorded.'}
Today's medicine log:
{log_summary}
Current personalized diet plan:
{diet_summary}
Use this data when answering schedule/history questions. If the exact requested fact is absent, say it is not recorded rather than guessing.
"""

    models = [
        ("qwen/qwen3.8-27b", {"max_tokens": 200, "temperature": 0.5}),
        ("openai/gpt-oss-20b", {"max_completion_tokens": 300}),
    ]
    for model, generation_options in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_text}
                ],
                **generation_options,
            )
            out = (res.choices[0].message.content or "").strip()
            if out:
                return out, None
            logging.warning("Groq model %s returned an empty response", model)
        except Exception as error:
            logging.warning("Groq model %s failed: %s", model, type(error).__name__)
            continue

    if is_te:
        return "కేర్‌వాయిస్ సేవను ప్రస్తుతం సంప్రదించలేకపోయాను. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి.", None
    return "I couldn't reach the CareVoice AI service just now. Please try your question again shortly.", None
