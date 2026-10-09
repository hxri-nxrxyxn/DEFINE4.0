"""
Answering Machine Detection (AMD) Engine
========================================
Classifies call answers into Live Humans vs. Automated Inboxes / Voicemail.
Applies compliant message routing based on domain (HIPAA & DPDPA compliance).
"""

from typing import Dict, Any, Tuple


def evaluate_amd_status(
    answered_by: str,
    call_duration_seconds: int = 0,
    greeting_duration_ms: int = 0,
    silence_duration_ms: int = 0
) -> Tuple[str, str, bool]:
    """
    Evaluates Exotel AMD parameters.
    Returns: (disposition_code, action_taken, is_live_human)
    """
    norm = (answered_by or "").strip().lower()

    if norm in ["human", "live", "person"]:
        return "COMPLETED_LIVE_HUMAN", "Live human answered. Delivered primary interactive call flow.", True

    if norm in ["machine", "answering_machine", "voicemail", "ivr"]:
        return "ANSWERED_MACHINE", "Automated inbox detected. Executing compliant voicemail drop or hangup.", False

    # Heuristic fallback based on acoustic greeting energy:
    # Answering machine greetings typically exceed 3.5 seconds of unbroken audio
    if greeting_duration_ms > 3500:
        return "ANSWERED_MACHINE", "Long continuous acoustic greeting detected (>3.5s). Classified as machine inbox.", False

    # Default to live human if unknown and short greeting
    return "COMPLETED_LIVE_HUMAN", "Defaulted to live human under standard duration threshold.", True


def determine_voicemail_action(
    domain: str,
    disposition_code: str
) -> Dict[str, Any]:
    """
    Determines whether to drop voicemail or disconnect.
    - Clinical & Educational: Drops non-sensitive reminder script.
    - Payment / Events: Hangs up immediately to prevent carrier minute waste, queues for SMS/WhatsApp.
    """
    if disposition_code != "ANSWERED_MACHINE":
        return {"action": "CONTINUE_INTERACTIVE_FLOW", "leave_message": False}

    if domain in ["clinic", "school"]:
        return {
            "action": "LEAVE_COMPLIANT_VOICEMAIL_DROP",
            "leave_message": True,
            "instruction": "Deliver sanitized minimum-necessary operational voicemail message."
        }

    # For general events and debt recovery, terminating and sending SMS is safer and more cost-effective
    return {
        "action": "TERMINATE_CALL_AND_TRIGGER_SMS_OMNICHANNEL",
        "leave_message": False,
        "instruction": "Disconnect to conserve telecom budget and dispatch self-service WhatsApp/SMS link."
    }
