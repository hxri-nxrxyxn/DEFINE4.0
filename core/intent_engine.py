"""
Dual-Modality Intent Processing Engine
======================================
Captures recipient intent through keypad (DTMF) digits and spoken speech utterances.
Maps multilingual expressions to standardized semantic tokens:
- INTENT_CONFIRMED
- INTENT_RESCHEDULE
- INTENT_DECLINED
- INTENT_QUERY (Escalates to ElevenLabs Conversational Voice Agent)
- OPT_OUT (Triggers DPDPA Right-to-Erasure and suppression)
"""

import re
from typing import Dict, Any, Tuple

# DTMF Keypad Mapping
DTMF_MAPPING = {
    "1": ("INTENT_CONFIRMED", "Recipient confirmed attendance/intent via keypad digit 1."),
    "2": ("INTENT_RESCHEDULE", "Recipient requested rescheduling via keypad digit 2."),
    "3": ("INTENT_QUERY", "Recipient requested live conversational inquiry via keypad digit 3."),
    "9": ("OPT_OUT", "Recipient exercised DPDPA opt-out via keypad digit 9.")
}

# Multilingual Keyword Vocabulary for Acoustic Speech Parsing
SPEECH_PATTERNS = {
    "INTENT_CONFIRMED": [
        # English
        r"\b(yes|yeah|yep|confirm|sure|attend|coming|i will come|definitely|i am in)\b",
        # Hindi
        r"\b(हाँ|हा|हाँजी|ज़रूर|आऊंगा|आऊंगी|पुष्टि|उपस्थित|haan|han|zaroor|aunga|aungi)\b",
        # Tamil
        r"\b(ஆம்|ஆமாம்|கண்டிப்பா|வர்றேன்|உறுதி|aama|aamam|kandippa|varren)\b",
        # Telugu
        r"\b(అవును|వస్తాను|ఖచ్చితంగా|ధృవీకరించు|avunu|vasthanu|vastanu)\b",
        # Malayalam
        r"\b(അതെ|ഉറപ്പാണ്|തീർച്ചയായും|വരാം|എത്തും|athe|athae|varam|urappanu)\b",
        # Marathi
        r"\b(हो|होय|येणार|नक्की|खात्री|ho|hoy|yenar|nakki)\b"
    ],
    "INTENT_RESCHEDULE": [
        # English
        r"\b(reschedule|change|postpone|another time|later|different date|busy)\b",
        # Hindi
        r"\b(बदलो|बाद में|दूसरा समय|व्यस्त|समय बदलो|badlo|baad me|vyast)\b",
        # Tamil
        r"\b(மாற்று|பிறகு|வேற நேரம்|நேரம் மாற்று|maathu|piragu|mathu)\b",
        # Telugu
        r"\b(మార్చండి|తర్వాత|వేరే సమయం|సమయం మార్చు|marchandi|tarvata)\b",
        # Malayalam
        r"\b(മാറ്റുക|പിന്നെ|മറ്റൊരു ദിവസം|സമയം മാറ്റുക|mattuka|pinne)\b",
        # Marathi
        r"\b(बदला|नंतर|वेळ बदला|कामात आहे|badla|nantar)\b"
    ],
    "INTENT_DECLINED": [
        # English
        r"\b(no|nope|cancel|cannot|can't|won't come|decline|not attending|not interested)\b",
        # Hindi
        r"\b(नहीं|ना|नहीं आऊंगा|रद्द|नाही|nahi|nahin|nahi aunga|radd)\b",
        # Tamil
        r"\b(இல்லை|முடியாது|வர முடியாது|ரத்து|illai|mudiyaadhu|varamudiyaadhu)\b",
        # Telugu
        r"\b(లేదు|రాను|రాలేను|రద్దు|ledu|ranu|ralenu)\b",
        # Malayalam
        r"\b(ഇല്ല|വരാൻ കഴിയില്ല|പറ്റില്ല|റദ്ദാക്കുക|illa|varan kazhiyilla|pattilla)\b",
        # Marathi
        r"\b(नाही|येऊ शकत नाही|रद्द करा|nahi|yeu shakat nahi)\b"
    ],
    "OPT_OUT": [
        # English
        r"\b(opt out|stop calling|unsubscribe|do not call|dnc|remove me|delete my data)\b",
        # Hindi
        r"\b(बंद करो|कॉल मत करो|हटाओ|नंबर हटाओ|band karo|call mat karo)\b",
        # Tamil
        r"\b(அழைக்காதே|நீக்கு|விலகு|alaikkathe|neekku)\b",
        # Telugu
        r"\b(కాల్ చేయవద్దు|ఆపండి|తొలగించు|call cheyavaddhu|apandi)\b",
        # Malayalam
        r"\b(വിളിക്കരുത്|ഒഴിവാക്കുക|നിർത്തുക|vilikkaruthu|ozhivakkuka)\b",
        # Marathi
        r"\b(कॉल करू नका|थांबवा|काढून टाका|call karu naka)\b"
    ],
    "INTENT_QUERY": [
        # English
        r"\b(what|where|who|how|parking|location|ticket|cost|fee|directions|detail|details|tell me more)\b",
        # Hindi
        r"\b(कहाँ|क्या|किसका|शुल्क|पार्किंग|कहा|kahan|kaha|kya|fees)\b",
        # Tamil
        r"\b(எங்கே|என்ன|கட்டணம்|விவரம்|enge|enna|kattanam)\b",
        # Telugu
        r"\b(ఎక్కడ|ఏమిటి|రుసుము|వివరాలు|ekkada|emiti|details)\b",
        # Malayalam
        r"\b(എവിടെ|എന്താണ്|ഫീസ്|വിശദാംശങ്ങൾ|evide|enthanu|details)\b",
        # Marathi
        r"\b(कुठे|काय|पत्ता|शुल्क|kuthe|kay|patta)\b"
    ]
}


def process_dtmf_intent(digit: str) -> Tuple[str, str, bool]:
    """
    Processes DTMF digit input.
    Returns: (disposition_code, explanation, should_escalate_to_llm)
    """
    cleaned = str(digit).strip()
    if cleaned in DTMF_MAPPING:
        code, desc = DTMF_MAPPING[cleaned]
        escalate = (code == "INTENT_QUERY")
        return code, desc, escalate

    return "INTENT_AMBIGUOUS", f"Unrecognized keypad digit '{cleaned}'.", True


def process_speech_intent(transcript: str, language: str = "English") -> Tuple[str, str, bool]:
    """
    Processes spoken acoustic speech transcript.
    Returns: (disposition_code, explanation, should_escalate_to_llm)
    """
    clean_text = transcript.strip().lower()
    if not clean_text:
        return "NO_SPEECH_DETECTED", "No intelligible acoustic energy registered.", False

    # Check for DPDPA Opt-Out first (highest priority)
    for pattern in SPEECH_PATTERNS["OPT_OUT"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return "OPT_OUT", f"User explicitly opted out verbally: '{transcript}'", False

    # Check for Confirmation
    for pattern in SPEECH_PATTERNS["INTENT_CONFIRMED"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return "INTENT_CONFIRMED", f"User confirmed attendance: '{transcript}'", False

    # Check for Reschedule
    for pattern in SPEECH_PATTERNS["INTENT_RESCHEDULE"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return "INTENT_RESCHEDULE", f"User requested reschedule: '{transcript}'", False

    # Check for Decline
    for pattern in SPEECH_PATTERNS["INTENT_DECLINED"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return "INTENT_DECLINED", f"User declined: '{transcript}'", False

    # Check for Query/Question -> Escalate to ElevenLabs ConvAI
    for pattern in SPEECH_PATTERNS["INTENT_QUERY"]:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return "INTENT_QUERY", f"User requested specific details ('{transcript}'). Escalating to conversational voice agent.", True

    # Ambiguous speech -> escalate to conversational agent
    return "INTENT_AMBIGUOUS", f"Ambiguous natural utterance ('{transcript}'). Escalating to multi-turn agent.", True
