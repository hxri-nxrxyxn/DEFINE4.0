#!/usr/bin/env python3
"""
DEFINE Auto-Dialer & Telephony Bridge Daemon
===========================================
Monitors ADB telecom states, triggers calls on device, detects recipient pickup (SET_ACTIVE),
and terminates the call precisely after the designated connected duration (10s from pickup).
"""

import http.server
import json
import os
import re
import subprocess
import threading
import time

ADB_DEVICE = os.environ.get("ADB_DEVICE", "A3SQUT5515003325")
PORT = int(os.environ.get("DIALER_PORT", 8765))

current_call_status = {
    "active": False,
    "current_phone": None,
    "current_name": None,
    "call_state": "IDLE", # IDLE, DIALING, CONNECTED, DISCONNECTING, COMPLETED
    "connected_time": None,
    "elapsed_seconds": 0,
    "target_duration": 10,
    "last_error": None
}

def adb_cmd(cmd_list):
    full_cmd = ["adb", "-s", ADB_DEVICE] + cmd_list
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=8)
        return res.stdout
    except Exception as e:
        return ""

def place_call(phone):
    clean = re.sub(r"[^\d+]", "", phone)
    adb_cmd(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean}"])

def end_call():
    # Send KEYCODE_ENDCALL (6) to immediately hang up
    adb_cmd(["shell", "input", "keyevent", "6"])

def get_telecom_dump():
    return adb_cmd(["shell", "dumpsys", "telecom"])

def get_audio_mode():
    out = adb_cmd(["shell", "dumpsys", "audio"])
    for line in out.splitlines():
        if "Actual mode =" in line:
            return line.strip()
    return ""

def monitor_call_cycle(phone, name, duration_sec):
    global current_call_status
    current_call_status["active"] = True
    current_call_status["current_phone"] = phone
    current_call_status["current_name"] = name
    current_call_status["call_state"] = "DIALING"
    current_call_status["connected_time"] = None
    current_call_status["elapsed_seconds"] = 0
    current_call_status["target_duration"] = duration_sec
    current_call_status["last_error"] = None

    print(f"[*] Placing call to {name} ({phone}), target active duration: {duration_sec}s", flush=True)
    place_call(phone)

    # Wait for call to either become active (answered) or be ended/canceled
    dial_start = time.time()
    call_connected = False
    max_ring_time = 50 # seconds before giving up

    while time.time() - dial_start < max_ring_time:
        time.sleep(0.6)
        dump = get_telecom_dump()
        audio = get_audio_mode()
        
        last_idx = dump.rfind("CallTC@")
        chunk = dump[last_idx:] if last_idx != -1 else ""

        # Check if call is answered (SET_ACTIVE in chunk)
        if "SET_ACTIVE" in chunk:
            call_connected = True
            current_call_status["call_state"] = "CONNECTED"
            current_call_status["connected_time"] = time.time()
            print(f"[+] Call to {phone} ANSWERED! Starting {duration_sec}s countdown from pickup.", flush=True)
            break
        
        # Check if call was disconnected before answer (rejected, busy, user cancelled)
        if "SET_DISCONNECTED" in chunk or "DESTROYED" in chunk:
            if "MODE_NORMAL" in audio and (time.time() - dial_start > 3):
                print(f"[-] Call to {phone} was ended/declined before answer.", flush=True)
                current_call_status["call_state"] = "COMPLETED"
                current_call_status["active"] = False
                return

    if not call_connected:
        print(f"[-] Call timed out without answer ({phone}). Terminating.", flush=True)
        end_call()
        current_call_status["call_state"] = "COMPLETED"
        current_call_status["active"] = False
        return

    # Count down the exact seconds from pickup
    conn_start = time.time()
    while time.time() - conn_start < duration_sec:
        elapsed = round(time.time() - conn_start, 1)
        current_call_status["elapsed_seconds"] = elapsed
        time.sleep(0.4)

        # Check if recipient hung up early
        dump = get_telecom_dump()
        last_idx = dump.rfind("CallTC@")
        chunk = dump[last_idx:] if last_idx != -1 else ""
        if "SET_DISCONNECTED" in chunk or "DESTROYED" in chunk:
            print(f"[+] Call ended early by recipient after {elapsed}s.", flush=True)
            current_call_status["call_state"] = "COMPLETED"
            current_call_status["active"] = False
            return

    # Time reached! Automatically terminate call
    print(f"[*] {duration_sec}s active call duration elapsed! Hanging up call to {phone}...", flush=True)
    current_call_status["call_state"] = "DISCONNECTING"
    end_call()
    time.sleep(1.0)
    current_call_status["call_state"] = "COMPLETED"
    current_call_status["active"] = False
    print(f"[✓] Call to {name} ({phone}) completed.", flush=True)

class BridgeServer(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({"status": "ok"})

    def do_GET(self):
        if self.path == "/status" or self.path == "/":
            self._send_json(current_call_status)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if self.path == "/call":
            phone = data.get("phone", "")
            name = data.get("name", "Recipient")
            duration = int(data.get("duration", 10))

            if not phone:
                self._send_json({"error": "phone required"}, 400)
                return

            if current_call_status["active"]:
                self._send_json({"error": "call already in progress", "status": current_call_status}, 409)
                return

            t = threading.Thread(target=monitor_call_cycle, args=(phone, name, duration), daemon=True)
            t.start()
            self._send_json({"status": "started", "phone": phone, "name": name, "target_duration": duration})

        elif self.path == "/end":
            end_call()
            current_call_status["active"] = False
            current_call_status["call_state"] = "COMPLETED"
            self._send_json({"status": "ended"})
        else:
            self._send_json({"error": "not found"}, 404)

if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), BridgeServer)
    print(f"[*] Auto-Dialer Bridge Daemon running on port {PORT} for device {ADB_DEVICE}...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
