"""
Platform Orchestrator
=====================
Glues all subsystems together:
- Campaign Management (Templates & Scripts)
- Telephony Dispatcher (Exotel Client)
- Intent Processing (DTMF & Speech)
- AMD & Voicemail Processing
- Data Protection & DPDPA Governance
- Operational Analytics & Algorithmic Retries
"""

import os
import csv
import io
import time
import uuid
from typing import Dict, Any, List, Optional

from core.campaign_manager import render_call_script, SUPPORTED_LANGUAGES, DOMAINS, CALL_TYPES
from core.telephony import ExotelClient
from core.intent_engine import process_dtmf_intent, process_speech_intent
from core.amd_engine import evaluate_amd_status, determine_voicemail_action
from core.data_governance import (
    encrypt_pii, decrypt_pii, mask_phone_number, hash_identifier,
    record_consent, purge_carrier_media, execute_right_to_erasure, is_suppressed
)
from core.analytics import analytics_engine


class OutboundCampaignPlatform:
    def __init__(self):
        self.telephony = ExotelClient()
        self.campaigns: Dict[str, Dict[str, Any]] = {}
        self.contact_registry: Dict[str, List[Dict[str, Any]]] = {}

    def create_campaign(
        self,
        name: str,
        domain: str = "events",
        call_type: str = "invitations",
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates and stores a campaign configuration."""
        cid = f"cmp_{uuid.uuid4().hex[:10]}"
        campaign = {
            "id": cid,
            "name": name,
            "domain": domain if domain in DOMAINS else "events",
            "call_type": call_type if call_type in CALL_TYPES else "invitations",
            "created_at": time.time(),
            "status": "DRAFT",
            "parameters": parameters or {},
            "total_recipients": 0,
            "completed_calls": 0
        }
        self.campaigns[cid] = campaign
        return campaign

    def parse_and_register_csv(
        self,
        campaign_id: str,
        csv_content: str
    ) -> List[Dict[str, Any]]:
        """
        Parses uploaded CSV, validates fields, applies AES-256 field encryption,
        and links contacts to the campaign.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        registered = []

        for row in reader:
            raw_phone = row.get("phone", "").strip()
            name = row.get("name", "").strip()
            if not raw_phone or not name:
                continue

            # Check DPDPA suppression list
            if is_suppressed(raw_phone):
                continue

            language = row.get("language", "English").capitalize()
            if language not in SUPPORTED_LANGUAGES:
                language = "English"

            # Apply envelope encryption to sensitive identifiers
            enc_name = encrypt_pii(name)
            enc_phone = encrypt_pii(raw_phone)
            masked_phone = mask_phone_number(raw_phone)
            phone_hash = hash_identifier(raw_phone)

            contact = {
                "id": f"cnt_{uuid.uuid4().hex[:8]}",
                "name": name,
                "phone": raw_phone,
                "encrypted_name": enc_name,
                "encrypted_phone": enc_phone,
                "masked_phone": masked_phone,
                "phone_token": phone_hash,
                "language": language,
                "city": row.get("city", "Mumbai"),
                "segment": row.get("segment", "General"),
                "metadata": {k: v for k, v in row.items() if k not in ["name", "phone", "language", "city", "segment"]}
            }
            registered.append(contact)

        self.contact_registry[campaign_id] = registered
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]["total_recipients"] = len(registered)

        return registered

    def dispatch_campaign_call(
        self,
        campaign_id: str,
        contact: Dict[str, Any],
        simulated_dtmf: Optional[str] = None,
        simulated_speech: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a single live or simulated call session through the full architecture:
        1. Renders localized scripts (live human + compliant voicemail drop).
        2. Dispatches telephony request via Exotel abstraction.
        3. Analyzes Answering Machine Detection (AMD) status.
        4. If machine: applies HIPAA/DPDPA voicemail drop or hangup.
        5. If human: logs consent notice and parses dual-intent (DTMF / speech).
        6. Purges carrier recording URL from public telecom storage within TTL.
        7. Records Call Detail Record (CDR) to Analytics.
        """
        camp = self.campaigns.get(campaign_id, {})
        domain = camp.get("domain", "events")
        call_type = camp.get("call_type", "invitations")
        lang = contact.get("language", "English")

        # Merge variables for template interpolation
        vars_dict = {
            "name": contact.get("name"),
            "city": contact.get("city"),
            "segment": contact.get("segment"),
            **camp.get("parameters", {}),
            **contact.get("metadata", {})
        }

        # 1. Generate scripts
        scripts = render_call_script(domain, call_type, lang, vars_dict)

        # 2. Trigger call on Exotel
        call_res = self.telephony.trigger_single_call(
            recipient_phone=contact.get("phone"),
            callback_url="http://api.in.exotel.com/callback",
            custom_field=f"{campaign_id}_{contact.get('id')}"
        )

        call_sid = call_res.get("CallSid", f"call_{uuid.uuid4().hex[:12]}")
        answered_by = call_res.get("AnsweredBy", "Human")
        recording_url = call_res.get("RecordingUrl")

        # 3. AMD Classification
        amd_disposition, amd_desc, is_human = evaluate_amd_status(answered_by)

        disposition = amd_disposition
        intent_explanation = amd_desc
        escalated_to_llm = False

        if not is_human:
            # Voicemail route
            vm_action = determine_voicemail_action(domain, amd_disposition)
            intent_explanation = f"Voicemail handled: {vm_action['action']}"
        else:
            # 4. Human route: Record acoustic legal notice consent
            record_consent(
                recipient_token=contact.get("phone_token"),
                consent_state="ACCEPTED",
                notice_version="v1.2-acoustic"
            )

            # 5. Dual-modality intent evaluation
            if simulated_dtmf:
                dtmf_disp, dtmf_desc, esc = process_dtmf_intent(simulated_dtmf)
                disposition = dtmf_disp
                intent_explanation = dtmf_desc
                escalated_to_llm = esc
            elif simulated_speech:
                sp_disp, sp_desc, esc = process_speech_intent(simulated_speech, language=lang)
                disposition = sp_disp
                intent_explanation = sp_desc
                escalated_to_llm = esc
            else:
                # Default live human completed successfully
                disposition = "INTENT_CONFIRMED"
                intent_explanation = "Simulated affirmative recipient acknowledgment."

            # If user opted out, execute DPDPA Right to Erasure immediately
            if disposition == "OPT_OUT":
                execute_right_to_erasure(contact.get("phone"))

        # 6. Purge carrier recording from telecom storage
        purge_receipt = None
        if recording_url:
            purge_receipt = purge_carrier_media(recording_url, call_sid)

        # 7. Record CDR to Analytics
        cdr = {
            "call_sid": call_sid,
            "campaign_id": campaign_id,
            "campaign_name": camp.get("name", "Campaign"),
            "domain": domain,
            "call_type": call_type,
            "name": contact.get("name"),
            "phone": contact.get("masked_phone"),
            "phone_token": contact.get("phone_token"),
            "language": lang,
            "city": contact.get("city"),
            "segment": contact.get("segment"),
            "disposition": disposition,
            "intent_explanation": intent_explanation,
            "escalated_to_llm": escalated_to_llm,
            "carrier_duration_seconds": call_res.get("Duration", 35),
            "carrier_purged": purge_receipt is not None,
            "timestamp": time.time()
        }
        analytics_engine.record_call_event(cdr)

        return {
            "call_sid": call_sid,
            "disposition": disposition,
            "is_human": is_human,
            "script_delivered": scripts["live_prompt"] if is_human else scripts["voicemail_drop_script"],
            "intent_explanation": intent_explanation,
            "escalated_to_llm": escalated_to_llm,
            "carrier_purged": purge_receipt is not None
        }

    def run_campaign_batch(self, campaign_id: str) -> Dict[str, Any]:
        """Dispatches all registered contacts in a campaign."""
        contacts = self.contact_registry.get(campaign_id, [])
        results = []
        for c in contacts:
            res = self.dispatch_campaign_call(campaign_id, c)
            results.append(res)

        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]["status"] = "COMPLETED"
            self.campaigns[campaign_id]["completed_calls"] = len(results)

        return {
            "campaign_id": campaign_id,
            "processed_calls": len(results),
            "results": results
        }


platform = OutboundCampaignPlatform()
