"""
Telephony Abstraction Layer (Exotel Integration Engine)
======================================================
Coordinates:
- Exotel Campaigns API (v2) for batch outbound calling
- Exotel Voice API (v1/v3) for instant transactional calls
- App Bazaar applet routing (Passthru, Gather, Voicebot)
- Dual-mode execution (Live Exotel API or High-Fidelity Telecom Simulator)
"""

import os
import time
import uuid
import random
import requests
from typing import Dict, Any, List, Optional

EXOTEL_ACCOUNT_SID = os.environ.get("EXOTEL_ACCOUNT_SID", "mock_exotel_acc_sid")
EXOTEL_API_KEY = os.environ.get("EXOTEL_API_KEY", "mock_exotel_api_key")
EXOTEL_API_TOKEN = os.environ.get("EXOTEL_API_TOKEN", "mock_exotel_token")
EXOTEL_CALLER_ID = os.environ.get("EXOTEL_CALLER_ID", "08047192800")
EXOTEL_SUBDOMAIN = os.environ.get("EXOTEL_SUBDOMAIN", "api.in.exotel.com")

# Mode: SIMULATED or LIVE
TELEPHONY_MODE = os.environ.get("TELEPHONY_MODE", "SIMULATED")


class ExotelClient:
    def __init__(self, mode: str = TELEPHONY_MODE):
        self.mode = mode
        self.account_sid = EXOTEL_ACCOUNT_SID
        self.api_key = EXOTEL_API_KEY
        self.api_token = EXOTEL_API_TOKEN
        self.caller_id = EXOTEL_CALLER_ID
        self.base_url = f"https://{self.api_key}:{self.api_token}@{EXOTEL_SUBDOMAIN}"

    def trigger_batch_campaign(
        self,
        campaign_name: str,
        caller_id: str,
        recipient_numbers: List[str],
        app_id: str,
        retries: int = 2,
        retry_interval_mins: int = 30
    ) -> Dict[str, Any]:
        """
        Invokes Exotel Campaigns API (v2).
        Endpoint: POST https://@api.in.exotel.com/v2/accounts/{AccountSid}/campaigns
        """
        if self.mode == "LIVE" and "mock" not in self.account_sid:
            url = f"{self.base_url}/v2/accounts/{self.account_sid}/campaigns"
            payload = {
                "name": campaign_name,
                "caller_id": caller_id or self.caller_id,
                "url": f"http://my.exotel.com/{self.account_sid}/exoml/start_voice/{app_id}",
                "type": "trans",
                "from": recipient_numbers,
                "retries": {
                    "number_of_retries": retries,
                    "interval_mins": retry_interval_mins
                }
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                return resp.json()
            except Exception as e:
                return {"status": "error", "message": str(e), "mode": "LIVE"}

        # High-Fidelity Simulation
        campaign_id = f"cmp_{uuid.uuid4().hex[:12]}"
        return {
            "status": "success",
            "mode": "SIMULATED",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "recipients_queued": len(recipient_numbers),
            "allocated_lines": min(len(recipient_numbers), 10),
            "telecom_region": "Mumbai (ap-south-1)",
            "carrier_provider": "Exotel Telecom Cloud",
            "timestamp": time.time()
        }

    def trigger_single_call(
        self,
        recipient_phone: str,
        callback_url: str,
        custom_field: str = ""
    ) -> Dict[str, Any]:
        """
        Invokes Exotel Voice API (v1/connect.json).
        Endpoint: POST https://@api.in.exotel.com/v1/Accounts/{AccountSid}/Calls/connect.json
        """
        call_sid = f"call_{uuid.uuid4().hex[:16]}"
        if self.mode == "LIVE" and "mock" not in self.account_sid:
            url = f"{self.base_url}/v1/Accounts/{self.account_sid}/Calls/connect.json"
            data = {
                "From": recipient_phone,
                "CallerId": self.caller_id,
                "Url": callback_url,
                "StatusCallback": callback_url,
                "CustomField": custom_field
            }
            try:
                resp = requests.post(url, data=data, timeout=10)
                return resp.json()
            except Exception as e:
                return {"status": "error", "message": str(e), "mode": "LIVE"}

        # Realistic Telecom Simulation
        # Simulate typical carrier outcomes (Human, Machine, Busy, No-answer)
        outcome_weights = ["Human"] * 70 + ["Machine"] * 15 + ["Busy"] * 8 + ["NoAnswer"] * 7
        picked_outcome = random.choice(outcome_weights)

        duration = random.randint(25, 65) if picked_outcome in ["Human", "Machine"] else 0

        return {
            "status": "completed" if duration > 0 else "failed",
            "mode": "SIMULATED",
            "CallSid": call_sid,
            "To": recipient_phone,
            "CallerId": self.caller_id,
            "Duration": duration,
            "AnsweredBy": picked_outcome,
            "RecordingUrl": f"https://s3-ap-southeast-1.amazonaws.com/exotel-recordings/{call_sid}.wav" if duration > 0 else None,
            "CustomField": custom_field,
            "timestamp": time.time()
        }
