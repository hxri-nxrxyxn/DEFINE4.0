import os
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
