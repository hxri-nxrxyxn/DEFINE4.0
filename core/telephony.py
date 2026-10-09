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

def _load_exotel_config():
    sid = os.environ.get("EXOTEL_ACCOUNT_SID", "")
    key = os.environ.get("EXOTEL_API_KEY", "")
    token = os.environ.get("EXOTEL_API_TOKEN", "")
    caller_id = os.environ.get("EXOTEL_CALLER_ID", "")
    subdomain = os.environ.get("EXOTEL_SUBDOMAIN", "api.in.exotel.com")
    mode = os.environ.get("TELEPHONY_MODE", "")

    # Look for exotel_cred.txt or .env in root
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_path = os.path.join(root_dir, "exotel_cred.txt")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k == "EXOTEL_ACCOUNT_SID" and not sid: sid = v
                        elif k == "EXOTEL_API_KEY" and not key: key = v
                        elif k == "EXOTEL_API_TOKEN" and not token: token = v
                        elif k == "EXOTEL_CALLER_ID" and not caller_id: caller_id = v
        except Exception:
            pass

    if not caller_id:
        caller_id = "08048332543"

    if not mode:
        mode = "LIVE" if (sid and key and token and "mock" not in sid) else "SIMULATED"

    return {
        "sid": sid or "mock_exotel_acc_sid",
        "key": key or "mock_exotel_api_key",
        "token": token or "mock_exotel_token",
        "caller_id": caller_id,
        "subdomain": subdomain,
        "mode": mode
    }

cfg = _load_exotel_config()
EXOTEL_ACCOUNT_SID = cfg["sid"]
EXOTEL_API_KEY = cfg["key"]
EXOTEL_API_TOKEN = cfg["token"]
EXOTEL_CALLER_ID = cfg["caller_id"]
EXOTEL_SUBDOMAIN = cfg["subdomain"]
TELEPHONY_MODE = cfg["mode"]


class ExotelClient:
    def __init__(self, mode: str = None):
        cfg = _load_exotel_config()
        self.mode = mode or cfg["mode"]
        self.account_sid = cfg["sid"]
        self.api_key = cfg["key"]
        self.api_token = cfg["token"]
        self.caller_id = cfg["caller_id"]
        self.base_url = f"https://{self.api_key}:{self.api_token}@{cfg['subdomain']}"

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
            
            # Format phone number for Exotel India (10-digit -> 09995283835)
            formatted_phone = recipient_phone.strip().replace(" ", "").replace("-", "")
            if len(formatted_phone) == 10 and not formatted_phone.startswith("0"):
                formatted_phone = "0" + formatted_phone
            elif formatted_phone.startswith("+91"):
                formatted_phone = "0" + formatted_phone[3:]

            exoml_url = callback_url if (callback_url and ("my.exotel.com" in callback_url or callback_url.startswith("https://"))) else f"http://my.exotel.com/{self.account_sid}/exoml/start_voice/41956"

            data = {
                "From": formatted_phone,
                "CallerId": self.caller_id,
                "Url": exoml_url,
                "StatusCallback": exoml_url,
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
