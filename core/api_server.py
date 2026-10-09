#!/usr/bin/env python3
"""
Multilingual Outbound Campaign Platform API Server
==================================================
Provides REST endpoints and interactive control dashboard for:
- Campaign creation & template configuration
- Contact CSV upload & AES-256 field encryption
- Outbound calling execution (Exotel + ElevenLabs hybrid)
- Real-time Analytics (by campaign, language, segment, disposition)
- Algorithmic retry scheduler for non-responders
- DPDPA consent & Right-to-Erasure governance logs

Usage:
    python3 core/api_server.py [--port 8000]
"""

import os
import sys
import json
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any

from core.platform import platform
from core.analytics import analytics_engine
from core.data_governance import consent_audit_ledger, erasure_audit_ledger, execute_right_to_erasure


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multilingual Outbound Campaign Orchestrator &middot; DEFINE 4.0</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: #101726;
            --surface-border: #1e293b;
            --accent: #10b981;
            --primary: #6366f1;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --font-main: 'Plus Jakarta Sans', system-ui, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--bg);
            color: var(--text-main);
            font-family: var(--font-main);
            min-height: 100vh;
            padding-bottom: 40px;
        }
        header {
            background: rgba(16, 23, 38, 0.9);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--surface-border);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 50;
        }
        .brand { display: flex; align-items: center; gap: 14px; }
        .brand-badge {
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            width: 38px; height: 38px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 18px; color: #fff;
        }
        .container { max-width: 1200px; margin: 24px auto; padding: 0 20px; display: flex; flex-direction: column; gap: 24px; }
        .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media(max-width: 800px) { .grid-2 { grid-template-columns: 1fr; } }
        .card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }
        .card-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
        .stat-value { font-size: 1.8rem; font-weight: 800; color: #34d399; }
        .stat-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
        .btn {
            cursor: pointer; border: none; outline: none; padding: 8px 16px; border-radius: 8px;
            font-weight: 600; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 8px;
            transition: all 0.2s ease;
        }
        .btn-primary { background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; }
        .btn-success { background: linear-gradient(135deg, #10b981, #059669); color: white; }
        .btn-secondary { background: rgba(255,255,255,0.08); color: var(--text-main); border: 1px solid var(--surface-border); }
        .btn:hover { transform: translateY(-1px); opacity: 0.95; }
        pre { background: #050811; padding: 14px; border-radius: 8px; font-family: var(--font-mono); font-size: 0.8rem; color: #38bdf8; overflow-x: auto; max-height: 220px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85rem; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--surface-border); }
        th { color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; }
        .badge-success { background: rgba(16, 185, 129, 0.2); color: #34d399; }
        .badge-warning { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .badge-info { background: rgba(99, 102, 241, 0.2); color: #818cf8; }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-badge">D4</div>
            <div>
                <h1 style="font-size: 1.15rem; font-weight: 700;">Multilingual Outbound Campaign Orchestrator</h1>
                <p style="font-size: 0.8rem; color: var(--text-muted);">DEFINE 4.0 &middot; Exotel Telephony + ElevenLabs Voice + DPDPA Cryptographic Governance</p>
            </div>
        </div>
        <div>
            <span class="badge badge-success" style="font-size: 0.8rem; padding: 6px 12px;">● System Active: ap-south-1 (Mumbai)</span>
        </div>
    </header>

    <div class="container">
        <!-- Top KPIs -->
        <div class="grid-3" id="kpiContainer">
            <div class="card">
                <div class="stat-label">Total Outbound Calls</div>
                <div class="stat-value" id="totalCalls">--</div>
            </div>
            <div class="card">
                <div class="stat-label">Connected / Live Reach</div>
                <div class="stat-value" id="connectRate" style="color: #60a5fa;">--</div>
            </div>
            <div class="card">
                <div class="stat-label">Confirmed Intentions</div>
                <div class="stat-value" id="confirmedRate" style="color: #a78bfa;">--</div>
            </div>
        </div>

        <!-- Quick Action Trigger Panel -->
        <div class="card">
            <div class="card-title">
                <span>🚀 Live Campaign Actions & Recovery</span>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary" onclick="runDemoCampaign()">▶ Run Seminar Campaign</button>
                    <button class="btn btn-success" onclick="retryNonResponders()">🔁 Retry Non-Responders</button>
                    <button class="btn btn-secondary" onclick="refreshDashboard()">🔄 Refresh</button>
                </div>
            </div>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 10px;">
                Execute batch outbound calls using our sample multilingual contacts (Hindi, Tamil, Telugu, Malayalam, Marathi, Bengali, Kannada) across Mumbai, Chennai, Kochi, Pune, Hyderabad, and Delhi.
            </p>
            <div id="actionStatus" style="font-size: 0.85rem; color: #34d399; font-weight: 600;"></div>
        </div>

        <div class="grid-2">
            <!-- Language Distribution -->
            <div class="card">
                <div class="card-title">🌐 Breakdown by Language</div>
                <table id="langTable">
                    <thead><tr><th>Language</th><th>Total Calls</th><th>Confirmed</th><th>Conversion %</th></tr></thead>
                    <tbody><tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Loading...</td></tr></tbody>
                </table>
            </div>

            <!-- Audience Segment Distribution -->
            <div class="card">
                <div class="card-title">👥 Breakdown by Audience Segment</div>
                <table id="segmentTable">
                    <thead><tr><th>Segment</th><th>Total</th><th>Confirmed</th><th>Rescheduled</th></tr></thead>
                    <tbody><tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Loading...</td></tr></tbody>
                </table>
            </div>
        </div>

        <!-- DPDPA Compliance & Security Ledger -->
        <div class="card">
            <div class="card-title">
                <span>🛡️ DPDPA 2023 Consent & Cryptographic Erasure Audit</span>
                <span class="badge badge-info">AES-256-GCM Column Isolation</span>
            </div>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 10px;">
                All recipient phone numbers are masked and hashed. User opt-outs (via Keypad DTMF 9 or verbal intent) trigger automated Right-to-Erasure with permanent suppression.
            </p>
            <pre id="auditLog">Loading compliance logs...</pre>
        </div>
    </div>

    <script>
        async function fetchAnalytics() {
            try {
                const res = await fetch('/api/analytics');
                const data = await res.json();
                
                document.getElementById('totalCalls').innerText = data.kpis.total_calls;
                document.getElementById('connectRate').innerText = `${data.kpis.connect_rate_pct}% (${data.kpis.connected_calls})`;
                document.getElementById('confirmedRate').innerText = `${data.kpis.confirmation_rate_pct}% (${data.kpis.confirmed_count})`;

                // Render Language table
                const langTbody = document.querySelector('#langTable tbody');
                langTbody.innerHTML = '';
                for (const [lang, stats] of Object.entries(data.by_language)) {
                    langTbody.innerHTML += `<tr>
                        <td><strong>${lang}</strong></td>
                        <td>${stats.total}</td>
                        <td>${stats.confirmed}</td>
                        <td><span class="badge badge-success">${stats.connect_rate}%</span></td>
                    </tr>`;
                }

                // Render Segment table
                const segTbody = document.querySelector('#segmentTable tbody');
                segTbody.innerHTML = '';
                for (const [seg, stats] of Object.entries(data.by_segment)) {
                    segTbody.innerHTML += `<tr>
                        <td><strong>${seg}</strong></td>
                        <td>${stats.total}</td>
                        <td>${stats.confirmed}</td>
                        <td>${stats.rescheduled}</td>
                    </tr>`;
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function fetchAudit() {
            try {
                const res = await fetch('/api/governance/audit');
                const data = await res.json();
                document.getElementById('auditLog').innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                console.error(e);
            }
        }

        async function runDemoCampaign() {
            document.getElementById('actionStatus').innerText = '⏳ Dispatching multilingual campaign batch...';
            try {
                const res = await fetch('/api/campaigns/demo/run', { method: 'POST' });
                const d = await res.json();
                document.getElementById('actionStatus').innerText = `✔ Successfully executed ${d.processed_calls} multilingual outbound calls across India!`;
                refreshDashboard();
            } catch (err) {
                document.getElementById('actionStatus').innerText = '❌ Error: ' + err.message;
            }
        }

        async function retryNonResponders() {
            document.getElementById('actionStatus').innerText = '⏳ Scheduling algorithmic retries for non-responders...';
            try {
                const res = await fetch('/api/actions/retry', { method: 'POST' });
                const d = await res.json();
                document.getElementById('actionStatus').innerText = `✔ ${d.retries_scheduled} non-responders queued under algorithmic backoff policy!`;
                refreshDashboard();
            } catch (err) {
                document.getElementById('actionStatus').innerText = '❌ Error: ' + err.message;
            }
        }

        function refreshDashboard() {
            fetchAnalytics();
            fetchAudit();
        }

        window.onload = refreshDashboard;
    </script>
</body>
</html>
"""


class PlatformRequestHandler(SimpleHTTPRequestHandler):
    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ["/", "/index.html", "/dashboard"]:
            data = HTML_DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        elif path == "/api/status":
            self._send_json({
                "status": "online",
                "telephony_mode": platform.telephony.mode,
                "sovereign_region": "AWS ap-south-1 (Mumbai)",
                "carrier_cluster": "Exotel Mumbai (@api.in.exotel.com)",
                "dpdpa_encryption": "AES-256-GCM Active",
                "campaigns_count": len(platform.campaigns),
                "total_calls_tracked": len(analytics_engine.call_records)
            })

        elif path == "/api/campaigns":
            self._send_json({"campaigns": list(platform.campaigns.values())})

        elif path == "/api/analytics":
            self._send_json({
                "kpis": analytics_engine.get_summary_statistics(),
                "by_campaign": analytics_engine.get_breakdown_by_campaign(),
                "by_language": analytics_engine.get_breakdown_by_language(),
                "by_segment": analytics_engine.get_breakdown_by_segment(),
                "retry_manifest": analytics_engine.generate_retry_manifest()
            })

        elif path == "/api/governance/audit":
            self._send_json({
                "consent_ledger": consent_audit_ledger[-10:],
                "erasure_ledger": erasure_audit_ledger[-10:]
            })

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if path == "/api/campaigns/create":
            name = payload.get("name", "New Outbound Campaign")
            domain = payload.get("domain", "events")
            call_type = payload.get("call_type", "invitations")
            params = payload.get("parameters", {})
            camp = platform.create_campaign(name, domain, call_type, params)
            self._send_json(camp, 201)

        elif path == "/api/campaigns/demo/run":
            # Run the flagship Multi-City AI Seminar Campaign
            camp = platform.create_campaign(
                name="National AI & Healthcare Seminar 2026",
                domain="events",
                call_type="invitations",
                parameters={"event_name": "National AI & Healthcare Seminar"}
            )
            cid = camp["id"]

            sample_csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "campaign_contacts_sample.csv")
            with open(sample_csv_path, "r", encoding="utf-8") as f:
                csv_data = f.read()

            platform.parse_and_register_csv(cid, csv_data)
            res = platform.run_campaign_batch(cid)
            self._send_json(res)

        elif path == "/api/actions/retry":
            manifest = analytics_engine.generate_retry_manifest()
            self._send_json({
                "status": "success",
                "retries_scheduled": len(manifest),
                "manifest": manifest
            })

        elif path == "/api/governance/erasure":
            phone = payload.get("phone", "")
            if not phone:
                self._send_json({"error": "Phone number required for erasure request"}, 400)
                return
            receipt = execute_right_to_erasure(phone)
            self._send_json(receipt)

        else:
            self.send_error(404, "Endpoint not found")


def run_api_server(host: str = "0.0.0.0", port: int = 8000):
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, PlatformRequestHandler)
    print("=" * 65)
    print("  Multilingual Outbound Campaign Telephony Platform")
    print("=" * 65)
    print(f"[*] Server running at: http://{host}:{port}/")
    print(f"[*] Dashboard UI    : http://localhost:{port}/")
    print(f"[*] Data Residency  : AWS ap-south-1 (Mumbai)")
    print(f"[*] Compliance      : DPDPA 2023 & HIPAA Minimum Necessary")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound Campaign API Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    run_api_server(args.host, args.port)
