import os
import re
import json
import uuid
import urllib.request
from typing import Dict, Optional

ELEVENLABS_API_KEY = os.environ.get(
    "ELEVENLABS_API_KEY",
    "sk_d9191a981f7ddca619f2dd4b1787e0cf6fd2e65a3c485e8a"
)

# Default voice (Rachel / Multilingual)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

ELEVENLABS_AGENT_ID = os.environ.get(
    "ELEVENLABS_AGENT_ID",
    "agent_8901m4gnv2a6f7xb5n0sbgbznz9f"
)

AUDIO_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


def update_conversational_agent(prompt_text: str, agent_id: str = ELEVENLABS_AGENT_ID) -> bool:
    """
    Dynamically updates ElevenLabs Conversational AI Agent (agentshrek) config:
    - Sets agent's first_message to prompt_text
    - Sets agent's system prompt instructions
    """
    try:
        url = f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}"
        clean_text = prompt_text.strip() or "Hello! I am your DEFINE Conversational AI Agent."
        
        payload = {
            "conversation_config": {
                "agent": {
                    "first_message": clean_text,
                    "prompt": {
                        "prompt": (
                            f"You are an interactive conversational AI call assistant for DEFINE. "
                            f"You are conducting an outbound campaign. Here is the campaign context: '{clean_text}'. "
                            f"Speak naturally, answer recipient questions about dates, time, venue, and confirm RSVPs."
                        )
                    }
                }
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            },
            method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[ElevenLabs ConvAI Agent Update Error]: {e}")
        return False


# ---------------------------------------------------------------------------
# Per-call agent configuration (template -> agent prompt)
# ---------------------------------------------------------------------------
LANG_CODES: Dict[str, str] = {
    "english": "en",
    "hindi": "hi",
    "tamil": "ta",
    "telugu": "te",
    "malayalam": "ml",
    "marathi": "mr",
    "kannada": "kn",
    "bengali": "bn",
}

# Languages the agent is allowed to switch between mid-conversation.
SUPPORTED_LANGUAGES = ["en", "hi", "ta", "te", "ml", "mr", "kn", "bn"]


def _build_call_first_message(script: str, name: Optional[str] = None) -> str:
    base = (script or "").strip()
    if base:
        # Keep a {{name}} placeholder if the script still has one, otherwise the
        # caller has already rendered the recipient's name into the script.
        base = re.sub(r"\{\s*name\s*\}", "{{name}}", base, flags=re.IGNORECASE)

    who = name or "{{name}}"
    if base:
        # Always self-introduce first, no matter what the template is. If the
        # template already opens with a greeting, just add the intro line.
        if re.match(r"^\s*(hello|hi|hey|namaste|namaskar|namaskaram|good\s+(morning|afternoon|evening))\b", base, re.IGNORECASE):
            intro = "This is DEFINE Voice AI calling."
        else:
            intro = f"Hello {who}, this is DEFINE Voice AI calling."
        return f"{intro} {base}"

    return (
        f"Hello {who}, this is DEFINE Voice AI calling with an important "
        "update. Do you have a moment?"
    )


def _build_call_prompt(script: str) -> str:
    script = (script or "").strip()
    if script:
        context = (
            "Deliver this campaign message naturally in the recipient's own "
            f'language: "{script}"'
        )
    else:
        context = "Deliver your campaign message naturally in the recipient's own language."

    return "\n".join(
        [
            "You are a polite, natural outbound voice agent for DEFINE.",
            "The recipient's name is {{name}}. Greet them warmly by name.",
            context,
            "Reply in the SAME language the recipient is currently speaking. If they switch language, switch with them immediately.",
            "Answer their questions and keep the conversation natural and brief.",
            "If the script asks the recipient to press a key (1 to confirm, 2 to reschedule, 9 to opt out), the keypad is captured automatically — do not ask for it again, and never claim they confirmed.",
            "IMPORTANT: never assume or invent the recipient's decision. A greeting like 'hello' is NOT a confirmation. Only call report_outcome once the recipient has explicitly stated their choice (or a keypad digit was pressed):",
            "- confirmed: the recipient explicitly agreed, confirmed, or will attend.",
            "- reschedule: the recipient explicitly asked to reschedule or be called again later.",
            "- not_available: the recipient is busy or cannot talk right now.",
            "- declined: the recipient explicitly said no or is not interested.",
            "- opt_out: the recipient explicitly asked to stop being called.",
            "After reporting the outcome, say one short closing line, then call the end_conversation tool to hang up.",
        ]
    )


_REPORT_OUTCOME_TOOL = {
    "type": "client",
    "name": "report_outcome",
    "description": (
        "Report the final outcome of the outbound call exactly once, as soon as "
        "the outcome is clear."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "outcome": {
                "type": "string",
                "description": "The final outcome of the call.",
                "enum": [
                    "confirmed",
                    "declined",
                    "reschedule",
                    "not_available",
                    "opt_out",
                ],
            }
        },
        "required": ["outcome"],
    },
}

_END_CALL_TOOL = {
    "type": "client",
    "name": "end_conversation",
    "description": (
        "Hang up the phone call once the conversation has definitely ended "
        "(after your short closing line)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Optional short reason for ending the call.",
            }
        },
    },
}

# System tool that lets the agent switch language when the caller does.
_LANGUAGE_DETECTION_TOOL = {
    "type": "system",
    "name": "language_detection",
    "description": "",
    "params": {"system_tool_type": "language_detection"},
}


def configure_call_agent(
    script: str,
    name: Optional[str] = None,
    language: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> bool:
    """
    Points the ElevenLabs Conversational AI agent at the operator's campaign
    template. Called per outbound call so the agent always speaks the script
    typed in the Template panel instead of a stale, previously-set message.
    """
    agent_id = agent_id or ELEVENLABS_AGENT_ID
    first_message = _build_call_first_message(script, name)
    prompt_text = _build_call_prompt(script)
    lang_code = LANG_CODES.get((language or "").strip().lower(), "en")

    payload = {
        "conversation_config": {
            "agent": {
                "first_message": first_message,
                "language": lang_code,
                "disable_first_message_interruptions": True,
                "dynamic_variables": {
                    "dynamic_variable_placeholders": {"name": name or "there"}
                },
                "prompt": {
                    "prompt": prompt_text,
                    "tools": [
                        _REPORT_OUTCOME_TOOL,
                        _END_CALL_TOOL,
                        _LANGUAGE_DETECTION_TOOL,
                    ],
                },
            },
            # Register the switchable languages so the language_detection tool
            # can adapt when the caller changes language mid-conversation.
            "language_presets": {
                code: {"overrides": {"agent": {"first_message": first_message}}}
                for code in SUPPORTED_LANGUAGES
                if code != lang_code
            },
        }
    }

    try:
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
        print(
            f"[ElevenLabs] Agent configured | first_message={first_message[:60]!r} "
            f"| language={lang_code}",
            flush=True,
        )
        return ok
    except Exception as e:
        print(f"[ElevenLabs ConvAI Agent Configure Error]: {e}", flush=True)
        return False


def synthesize_prompt_audio(text: str, call_id: Optional[str] = None, voice_id: str = DEFAULT_VOICE_ID) -> str:
    """
    Synthesizes text prompt into MP3 audio via ElevenLabs TTS API (eleven_multilingual_v2).
    Returns relative audio file path.
    """
    if not call_id:
        call_id = f"call_{uuid.uuid4().hex[:12]}"

    out_file_path = os.path.join(AUDIO_CACHE_DIR, f"{call_id}.mp3")

    # Clean prompt text
    clean_text = text.strip() or "Hello! This is an outbound campaign notification from DEFINE Voice AI."

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": clean_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            audio_bytes = resp.read()
            with open(out_file_path, "wb") as f:
                f.write(audio_bytes)
            return out_file_path
    except Exception as e:
        print(f"[ElevenLabs Voice] Synthesis error: {e}")
        return ""


def get_exoml_response(audio_url: str, text_fallback: str = "") -> str:
    """
    Generates Exotel-compliant ExoML XML.
    If audio_url is present, plays the ElevenLabs synthesized audio.
    Otherwise falls back to <Say> voice synthesis.
    """
    if audio_url:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="/api/calls/webhook/intent" method="POST" numDigits="1" timeout="10">
    </Gather>
</Response>"""
    
    clean_fallback = text_fallback.replace("<", "&lt;").replace(">", "&gt;") or "Hello! This is a live campaign call."
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="woman">{clean_fallback}</Say>
    <Gather action="/api/calls/webhook/intent" method="POST" numDigits="1" timeout="10">
    </Gather>
</Response>"""
