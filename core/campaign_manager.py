"""
Core Campaign Management Service
=================================
Handles template creation, variable interpolation, multilingual localization,
and compliant script generation across:
- 4 Call Types: invitations, rsvps, reminders, event_updates
- 4 Enterprise Domains: events (seminars/workshops), clinic, school, payment
"""

from typing import Dict, Any, List, Optional
import json

# Supported Languages
SUPPORTED_LANGUAGES = [
    "English",
    "Hindi",
    "Tamil",
    "Telugu",
    "Malayalam",
    "Marathi",
    "Kannada",
    "Bengali"
]

# Supported Call Types
CALL_TYPES = ["invitations", "rsvps", "reminders", "event_updates"]

# Supported Domains
DOMAINS = ["events", "clinic", "school", "payment"]


# Multilingual template dictionary
LOCALIZED_TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "events": {
        "invitations": {
            "English": "Hello {name}, you are cordially invited to the {event_name} on {event_date} at {event_time}, held at {event_location}, {city}.",
            "Hindi": "नमस्ते {name}, आपको {city} में {event_location} पर {event_date} को सुबह/शाम {event_time} बजे आयोजित होने वाले {event_name} में सादर आमंत्रित किया जाता है।",
            "Tamil": "வணக்கம் {name}, {city} இல் {event_location} இல் {event_date} அன்று {event_time} மணிக்கு நடைபெறும் {event_name} நிகழ்விற்கு உங்களை அன்புடன் அழைக்கிறோம்.",
            "Telugu": "నమస్కారం {name}, {city} లోని {event_location} లో {event_date} న {event_time} గంటలకు జరిగే {event_name} కు మిమ్మల్ని సాదరంగా ఆహ్వానిస్తున్నాము.",
            "Malayalam": "നമസ്കാരം {name}, {city}-ലെ {event_location}-ൽ {event_date} തീയതി {event_time}-ന് നടക്കുന്ന {event_name}-ലേക്ക് താങ്കളെ സാദരം ക്ഷണിക്കുന്നു.",
            "Marathi": "नमस्कार {name}, {city} येथील {event_location} येथे {event_date} रोजी {event_time} वाजता होणाऱ्या {event_name} साठी आपले हार्दिक निमंत्रण आहे.",
            "Kannada": "ನಮಸ್ಕಾರ {name}, {city}ಯ {event_location}ನಲ್ಲಿ {event_date}ರಂದು {event_time}ಕ್ಕೆ ನಡೆಯಲಿರುವ {event_name}ಗೆ ನಿಮ್ಮನ್ನು ಆತ್ಮೀಯವಾಗಿ ಆಹ್ವಾನಿಸುತ್ತೇವೆ.",
            "Bengali": "নমস্কার {name}, {city}-র {event_location}-এ {event_date} তারিখে {event_time} সময়ে অনুষ্ঠিত {event_name}-এ আপনাকে আন্তরিকভাবে আমন্ত্রণ জানানো হচ্ছে।"
        },
        "rsvps": {
            "English": "Hello {name}, this is an RSVP confirmation call for the {event_name} in {city} scheduled for {event_date} at {event_time}.",
            "Hindi": "नमस्ते {name}, यह {city} में {event_date} को {event_time} बजे होने वाले {event_name} के लिए आपकी उपस्थिति पुष्टि कॉल है।",
            "Tamil": "வணக்கம் {name}, {city} இல் {event_date} அன்று {event_time} மணிக்கு நடைபெறவிருக்கும் {event_name}க்கான உங்கள் வருகை உறுதிப்படுத்தல் அழைப்பு இது.",
            "Telugu": "నమస్కారం {name}, {city} లో {event_date} న {event_time} గంటలకు జరిగే {event_name} కోసం మీ హాజరు ధృవీకరణ కాల్ ఇది.",
            "Malayalam": "നമസ്കാരം {name}, {city}-ൽ {event_date}-ന് {event_time}-ന് നടക്കുന്ന {event_name}-ൽ താങ്കളുടെ സാന്നിധ്യം ഉറപ്പാക്കാനുള്ള കോളാണിത്.",
            "Marathi": "नमस्कार {name}, {city} मधील {event_date} रोजी {event_time} वाजता होणाऱ्या {event_name} साठी आपल्या उपस्थितीची खात्री करण्यासाठी हा कॉल आहे.",
            "Kannada": "ನಮಸ್ಕಾರ {name}, {city}ನಲ್ಲಿ {event_date}ರಂದು {event_time}ಕ್ಕೆ ನಡೆಯುವ {event_name}ಗೆ ನಿಮ್ಮ ಉಪಸ್ಥಿತಿ ದೃಢೀಕರಣ ಕರೆ ಇದಾಗಿದೆ.",
            "Bengali": "নমস্কার {name}, {city}-তে {event_date} তারিখে {event_time} সময়ে {event_name}-এ আপনার উপস্থিতি নিশ্চিত করার জন্য এই কল।"
        },
        "reminders": {
            "English": "Friendly reminder for {name}: The {event_name} at {event_location}, {city} begins tomorrow on {event_date} at {event_time}.",
            "Hindi": "{name} के लिए आवश्यक सूचना: {city} में {event_location} पर {event_name} {event_date} को {event_time} बजे शुरू होगा।",
            "Tamil": "{name} அவர்களுக்கு நினைவூட்டல்: {city} இல் {event_location} இல் {event_name} {event_date} அன்று {event_time} மணிக்கு தொடங்குகிறது.",
            "Telugu": "{name} గారికి గుర్తుచేస్తున్నాము: {city} లోని {event_location} వద్ద {event_name} {event_date} న {event_time} గంటలకు ప్రారంభమవుతుంది.",
            "Malayalam": "{name} അറിയുന്നതിനായുള്ള ഓർമ്മപ്പെടുത്തൽ: {city}-ലെ {event_location}-ൽ {event_name} {event_date} {event_time}-ന് ആരംഭിക്കുന്നതാണ്.",
            "Marathi": "{name} यांच्यासाठी स्मरणपत्र: {city} येथील {event_location} येथे {event_name} {event_date} रोजी {event_time} वाजता सुरू होईल.",
            "Kannada": "{name} ಅವರಿಗೆ ನೆನಪೋಲೆ: {city}ಯ {event_location}ನಲ್ಲಿ {event_name} {event_date}ರಂದು {event_time}ಕ್ಕೆ ಪ್ರಾರಂಭವಾಗಲಿದೆ.",
            "Bengali": "{name}-এর জন্য স্মারক: {city}-র {event_location}-এ {event_name} {event_date} তারিখে {event_time} সময়ে শুরু হবে।"
        },
        "event_updates": {
            "English": "Important update for {name}: The schedule for {event_name} in {city} at {event_location} has been finalized for {event_date} at {event_time}.",
            "Hindi": "{name} के लिए महत्वपूर्ण सूचना: {city} में {event_location} पर {event_name} का समय {event_date} को {event_time} बजे निश्चित किया गया है।",
            "Tamil": "{name} அவர்களுக்கு முக்கிய தகவல்: {city} இல் {event_location} இல் நடைபெறும் {event_name} நேரம் {event_date} அன்று {event_time} என உறுதி செய்யப்பட்டுள்ளது.",
            "Telugu": "{name} గారికి ముఖ్య గమనిక: {city} లో {event_location} వద్ద జరిగే {event_name} సమయం {event_date} న {event_time} కు ఖరారైంది.",
            "Malayalam": "{name} അറിയുന്നതിനായുള്ള പ്രധാന അറിയിപ്പ്: {city}-ൽ {event_location}-ൽ നടക്കുന്ന {event_name} സമയം {event_date} {event_time}-ന് നിശ്ചയിച്ചിരിക്കുന്നു.",
            "Marathi": "{name} यांच्यासाठी महत्त्वाची सूचना: {city} येथील {event_location} मध्ये होणाऱ्या {event_name} ची वेळ {event_date} रोजी {event_time} निश्चित झाली आहे.",
            "Kannada": "{name} ಅವರಿಗೆ ಮುಖ್ಯ ಮಾಹಿತಿ: {city}ಯ {event_location}ನಲ್ಲಿ ನಡೆಯುವ {event_name} ಸಮಯ {event_date}ರಂದು {event_time}ಕ್ಕೆ ನಿಗದಿಯಾಗಿದೆ.",
            "Bengali": "{name}-এর জন্য গুরুত্বপূর্ণ আপডেট: {city}-র {event_location}-এ {event_name}-এর সময়সূচী {event_date} তারিখে {event_time}-এ নির্ধারিত হয়েছে।"
        }
    },
    "clinic": {
        "reminders": {
            "English": "Hello {name}, this is a health appointment reminder with {doctor_name} at {clinic_name}, {city} on {appointment_date} at {appointment_time}.",
            "Hindi": "नमस्ते {name}, {city} में {clinic_name} में {doctor_name} के साथ आपका अपॉइंटमेंट {appointment_date} को {appointment_time} बजे निर्धारित है।",
            "Tamil": "வணக்கம் {name}, {city} இல் {clinic_name} இல் {doctor_name} அவர்களுடன் உங்கள் மருத்துவ சந்திப்பு {appointment_date} அன்று {appointment_time} மணிக்கு உள்ளது.",
            "Telugu": "నమస్కారం {name}, {city} లోని {clinic_name} లో {doctor_name} తో మీ అపాయింట్‌మెంట్ {appointment_date} న {appointment_time} గంటలకు ఉంది.",
            "Malayalam": "നമസ്കാരം {name}, {city}-ലെ {clinic_name}-ൽ {doctor_name}-മായി താങ്കൾക്കുള്ള അപ്പോയിന്റ്മെന്റ് {appointment_date} തീയതി {appointment_time}-നാണ്.",
            "Marathi": "नमस्कार {name}, {city} येथील {clinic_name} मध्ये {doctor_name} यांच्यासोबत आपली भेट {appointment_date} रोजी {appointment_time} वाजता आहे."
        }
    },
    "school": {
        "reminders": {
            "English": "Hello {name}, this is an important school notice regarding student {student_name} ({grade}). The parent meeting is on {meeting_date} at {meeting_time}.",
            "Hindi": "नमस्ते {name}, विद्यार्थी {student_name} ({grade}) के संबंध में विद्यालय सूचना: अभिभावक बैठक {meeting_date} को {meeting_time} बजे है।",
            "Tamil": "வணக்கம் {name}, மாணவர் {student_name} ({grade}) பற்றிய பள்ளி தகவல்: பெற்றோர் சந்திப்பு {meeting_date} அன்று {meeting_time} மணிக்கு நடைபெறும்.",
            "Telugu": "నమస్కారం {name}, విద్యార్థి {student_name} ({grade}) గురించిన పాఠశాల సమాచారం: తల్లిదండ్రుల సమావేశం {meeting_date} న {meeting_time} గంటలకు ఉంది.",
            "Malayalam": "നമസ്കാരം {name}, വിദ്യാർത്ഥി {student_name} ({grade}) സംബന്ധിച്ച സ്കൂൾ അറിയിപ്പ്: പിടിഎ മീറ്റിംഗ് {meeting_date}-ന് {meeting_time}-നാണ്."
        }
    },
    "payment": {
        "reminders": {
            "English": "Hello {name}, friendly reminder for invoice {invoice_no} regarding {service_name}. An amount of {amount_due} is due on {due_date}.",
            "Hindi": "नमस्ते {name}, {service_name} के बिल संख्या {invoice_no} का भुगतान {due_date} तक देय है। कुल राशि {amount_due} है।",
            "Tamil": "வணக்கம் {name}, {service_name} கட்டண எண் {invoice_no} நினைவூட்டல்: {due_date} க்குள் செலுத்த வேண்டிய தொகை {amount_due}.",
            "Telugu": "నమస్కారం {name}, {service_name} ఇన్వాయిస్ {invoice_no} గుర్తుచేస్తున్నాము: {due_date} నాటికి చెల్లించాల్సిన మొత్తం {amount_due}.",
            "Malayalam": "നമസ്കാരം {name}, {service_name} സംബന്ധിച്ച ഇൻവോയ്സ് {invoice_no} തുകയായ {amount_due} {due_date}-ന് മുമ്പ് അടയ്ക്കണമെന്ന് ഓർമ്മിപ്പിക്കുന്നു."
        }
    }
}

# Standardized Interaction Appendices
INTERACTION_PROMPT = {
    "English": "Press 1 or say 'Confirm' to attend. Press 2 or say 'Reschedule' to change. Press 3 to ask questions. Press 9 to opt out.",
    "Hindi": "उपस्थिति दर्ज करने के लिए 1 दबाएं या 'हाँ' कहें। समय बदलने के लिए 2 दबाएं। जानकारी के लिए 3 दबाएं। कॉल बंद करने के लिए 9 दबाएं।",
    "Tamil": "உறுதிப்படுத்த 1 ஐ அழுத்தவும் அல்லது 'ஆம்' என்று கூறவும். மாற்ற 2 ஐ அழுத்தவும். கேள்விகளுக்கு 3 ஐ அழுத்தவும். விலக 9 ஐ அழுத்தவும்.",
    "Telugu": "ధృవీకరించడానికి 1 నొక్కండి లేదా 'అవును' అనండి. మార్చడానికి 2 నొక్కండి. వివరాలకు 3 నొక్కండి. నిలిపివేయడానికి 9 నొక్కండి.",
    "Malayalam": "ഉറപ്പാക്കാൻ 1 അമർത്തുക അല്ലെങ്കിൽ 'ഉറപ്പാണ്' എന്ന് പറയുക. മാറ്റാൻ 2 അമർത്തുക. സംശയങ്ങൾക്ക് 3 അമർത്തുക. ഒഴിവാക്കാൻ 9 അമർത്തുക.",
    "Marathi": "पुष्टी करण्यासाठी 1 दाबा किंवा 'होय' म्हणा. बदलण्यासाठी 2 दाबा. चौकशीसाठी 3 दाबा. थांबवण्यासाठी 9 दाबा."
}

MANDATORY_LEGAL_NOTICE = {
    "English": "This automated call is processed by AI and may be recorded for compliance.",
    "Hindi": "यह स्वचालित कॉल एआई द्वारा संचालित है और गुणवत्ता के लिए रिकॉर्ड की जा सकती है।",
    "Tamil": "இந்த தானியங்கி அழைப்பு AI மூலம் இயக்கப்படுகிறது மற்றும் பதிவு செய்யப்படலாம்.",
    "Telugu": "ఈ స్వయంచాలక కాల్ AI ద్వారా ప్రాసెస్ చేయబడుతుంది మరియు రికార్డ్ చేయబడవచ్చు.",
    "Malayalam": "ഈ ഓട്ടോമേറ്റഡ് കോൾ എഐ സാങ്കേതികവിദ്യ വഴി നിയന്ത്രിക്കപ്പെടുന്നതും റെക്കോർഡ് ചെയ്യപ്പെടുന്നതുമാണ്.",
    "Marathi": "हा स्वयंचलित कॉल एआय द्वारे संचलित आहे आणि रेकॉर्ड केला जाऊ शकतो."
}

# HIPAA / DPDPA Compliant Voicemail Drop Scripts (No medical conditions or sensitive data)
COMPLIANT_VOICEMAIL_SCRIPTS = {
    "events": "This is an automated notification for {name} regarding {event_name}. Please check your SMS or visit our portal for full details.",
    "clinic": "This is a confidential message for {name} from {clinic_name}. You have an appointment scheduled for {appointment_date} at {appointment_time}. Please call back at your earliest convenience to confirm.",
    "school": "This is an automated notice for {name} regarding student {student_name}. Please contact the school administrative office for the upcoming schedule.",
    "payment": "This is a payment notification for {name} regarding invoice {invoice_no}. Please visit the secure payment portal to review your account."
}


def render_call_script(
    domain: str,
    call_type: str,
    language: str,
    variables: Dict[str, Any]
) -> Dict[str, str]:
    """
    Renders complete multilingual speech scripts for live humans and voicemail drops.
    """
    lang = language if language in SUPPORTED_LANGUAGES else "English"
    dom = domain if domain in DOMAINS else "events"
    ctype = call_type if call_type in CALL_TYPES else "invitations"

    # Fallback to English if specific domain/call_type not in requested language
    domain_templates = LOCALIZED_TEMPLATES.get(dom, LOCALIZED_TEMPLATES["events"])
    type_templates = domain_templates.get(ctype, domain_templates.get("reminders", {}))
    template_str = type_templates.get(lang, type_templates.get("English", "Notification for {name}."))

    try:
        body = template_str.format(**variables)
    except KeyError:
        # Graceful variable fallback
        body = template_str
        for k, v in variables.items():
            body = body.replace(f"{{{k}}}", str(v))

    interaction = INTERACTION_PROMPT.get(lang, INTERACTION_PROMPT["English"])
    legal = MANDATORY_LEGAL_NOTICE.get(lang, MANDATORY_LEGAL_NOTICE["English"])

    full_live_script = f"{legal}\n\n{body}\n\n{interaction}"

    # Voicemail script
    vm_template = COMPLIANT_VOICEMAIL_SCRIPTS.get(dom, COMPLIANT_VOICEMAIL_SCRIPTS["events"])
    try:
        vm_script = vm_template.format(**variables)
    except KeyError:
        vm_script = vm_template
        for k, v in variables.items():
            vm_script = vm_script.replace(f"{{{k}}}", str(v))

    return {
        "language": lang,
        "domain": dom,
        "call_type": ctype,
        "live_prompt": full_live_script,
        "body_text": body,
        "interaction_prompt": interaction,
        "legal_notice": legal,
        "voicemail_drop_script": vm_script
    }
