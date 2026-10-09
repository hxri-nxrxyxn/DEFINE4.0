"""
Analytics Engine & Algorithmic Recovery Workflows
=================================================
Calculates:
- Outcomes broken down by Campaign
- Outcomes broken down by Language
- Outcomes broken down by Audience Segment
- Granular disposition distribution
- Algorithmic Retry Scheduler for Non-Responders with omnichannel fallback
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

# Disposition taxonomy
# 1. Successful Live: INTENT_CONFIRMED, INTENT_RESCHEDULE, INTENT_DECLINED, INTENT_QUERY
# 2. Voicemail: ANSWERED_MACHINE
# 3. Non-responder retryable: NETWORK_BUSY, NO_ANSWER_TIMEOUT
# 4. Terminal suppression: INVALID_NUMBER, OPT_OUT


class AnalyticsService:
    def __init__(self):
        self.call_records: List[Dict[str, Any]] = []

    def record_call_event(self, event: Dict[str, Any]):
        """Records a normalized CDR event."""
        self.call_records.append(event)

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Calculates overarching KPIs."""
        total = len(self.call_records)
        if total == 0:
            return {
                "total_calls": 0,
                "connected_calls": 0,
                "connect_rate_pct": 0,
                "confirmed_count": 0,
                "confirmation_rate_pct": 0,
                "voicemail_count": 0,
                "retryable_non_responders": 0
            }

        connected = sum(1 for c in self.call_records if c.get("disposition") in [
            "COMPLETED_LIVE_HUMAN", "INTENT_CONFIRMED", "INTENT_RESCHEDULE", "INTENT_DECLINED", "INTENT_QUERY"
        ])
        confirmed = sum(1 for c in self.call_records if c.get("disposition") == "INTENT_CONFIRMED")
        voicemails = sum(1 for c in self.call_records if c.get("disposition") == "ANSWERED_MACHINE")
        retryable = sum(1 for c in self.call_records if c.get("disposition") in ["NETWORK_BUSY", "NO_ANSWER_TIMEOUT"])

        return {
            "total_calls": total,
            "connected_calls": connected,
            "connect_rate_pct": round((connected / total) * 100, 1),
            "confirmed_count": confirmed,
            "confirmation_rate_pct": round((confirmed / total) * 100, 1) if total > 0 else 0,
            "voicemail_count": voicemails,
            "retryable_non_responders": retryable
        }

    def get_breakdown_by_campaign(self) -> Dict[str, Dict[str, Any]]:
        """Outcomes grouped by campaign."""
        breakdown = defaultdict(lambda: {"total": 0, "confirmed": 0, "rescheduled": 0, "declined": 0, "voicemail": 0, "retryable": 0})
        for c in self.call_records:
            camp = c.get("campaign_name", "Default Campaign")
            disp = c.get("disposition")
            b = breakdown[camp]
            b["total"] += 1
            if disp == "INTENT_CONFIRMED":
                b["confirmed"] += 1
            elif disp == "INTENT_RESCHEDULE":
                b["rescheduled"] += 1
            elif disp == "INTENT_DECLINED":
                b["declined"] += 1
            elif disp == "ANSWERED_MACHINE":
                b["voicemail"] += 1
            elif disp in ["NETWORK_BUSY", "NO_ANSWER_TIMEOUT"]:
                b["retryable"] += 1

        return dict(breakdown)

    def get_breakdown_by_language(self) -> Dict[str, Dict[str, Any]]:
        """Outcomes grouped by language."""
        breakdown = defaultdict(lambda: {"total": 0, "confirmed": 0, "declined": 0, "connect_rate": 0})
        for c in self.call_records:
            lang = c.get("language", "English")
            disp = c.get("disposition")
            b = breakdown[lang]
            b["total"] += 1
            if disp == "INTENT_CONFIRMED":
                b["confirmed"] += 1
            elif disp == "INTENT_DECLINED":
                b["declined"] += 1

        for lang, b in breakdown.items():
            b["connect_rate"] = round((b["confirmed"] / b["total"]) * 100, 1) if b["total"] > 0 else 0

        return dict(breakdown)

    def get_breakdown_by_segment(self) -> Dict[str, Dict[str, Any]]:
        """Outcomes grouped by audience segment."""
        breakdown = defaultdict(lambda: {"total": 0, "confirmed": 0, "rescheduled": 0, "declined": 0})
        for c in self.call_records:
            seg = c.get("segment", "General")
            disp = c.get("disposition")
            b = breakdown[seg]
            b["total"] += 1
            if disp == "INTENT_CONFIRMED":
                b["confirmed"] += 1
            elif disp == "INTENT_RESCHEDULE":
                b["rescheduled"] += 1
            elif disp == "INTENT_DECLINED":
                b["declined"] += 1

        return dict(breakdown)

    def generate_retry_manifest(self) -> List[Dict[str, Any]]:
        """
        Executes Algorithmic Retry Policies for non-responders:
        - NETWORK_BUSY: Retry interval Delta_t = 20 mins
        - NO_ANSWER_TIMEOUT: Retry interval Delta_t = 120 mins
        - Attempts >= 2: Triggers Omnichannel WhatsApp/SMS Fallback
        - OPT_OUT / INVALID: Suppressed (Infinite interval)
        """
        manifest = []
        now = time.time()

        for c in self.call_records:
            disp = c.get("disposition")
            attempts = c.get("attempts", 1)
            phone = c.get("phone", "")

            if disp == "NETWORK_BUSY":
                if attempts >= 2:
                    action = "FALLBACK_WHATSAPP_SMS_LINK"
                    delay_mins = 0
                else:
                    action = "VOICE_RETRY_SCHEDULED"
                    delay_mins = 20
                manifest.append({
                    "recipient_name": c.get("name"),
                    "phone": phone,
                    "disposition": disp,
                    "attempts": attempts,
                    "action": action,
                    "retry_after_timestamp": now + (delay_mins * 60),
                    "retry_window_mins": delay_mins,
                    "channel": "Voice" if action == "VOICE_RETRY_SCHEDULED" else "WhatsApp/SMS Link"
                })

            elif disp == "NO_ANSWER_TIMEOUT":
                if attempts >= 2:
                    action = "FALLBACK_WHATSAPP_SMS_LINK"
                    delay_mins = 0
                else:
                    action = "VOICE_RETRY_SCHEDULED"
                    delay_mins = 120
                manifest.append({
                    "recipient_name": c.get("name"),
                    "phone": phone,
                    "disposition": disp,
                    "attempts": attempts,
                    "action": action,
                    "retry_after_timestamp": now + (delay_mins * 60),
                    "retry_window_mins": delay_mins,
                    "channel": "Voice" if action == "VOICE_RETRY_SCHEDULED" else "WhatsApp/SMS Link"
                })

        return manifest


analytics_engine = AnalyticsService()
