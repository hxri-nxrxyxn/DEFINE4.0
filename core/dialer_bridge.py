#!/usr/bin/env python3
"""
DEFINE Auto-Dialer & Telephony Bridge Daemon
===========================================
Monitors ADB telecom states, triggers calls on device, detects recipient pickup (SET_ACTIVE),
and terminates the call precisely after the designated connected duration (10s from pickup).
Handles early hang-ups, call declines, and busy states gracefully.
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
    "outcome": None,      # completed, declined, unanswered, error
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
    # Send KEYCODE_ENDCALL (6) to hang up
    adb_cmd(["shell", "input", "keyevent", "6"])

def get_telecom_dump():
    return adb_cmd(["shell", "dumpsys", "telecom"])

def extract_latest_call_info(dump):
    """
    Returns (call_id_int, call_chunk_str, has_active_call_in_manager)
    """
    # Check if CallsManager has active calls
    has_active = False
    idx_calls = dump.find("mCalls:")
    idx_audio = dump.find("mCallAudioManager:")
    if idx_calls != -1 and idx_audio != -1 and idx_audio > idx_calls:
        mcalls_section = dump[idx_calls+7:idx_audio].strip()
        if len(mcalls_section) > 0:
            has_active = True

    matches = list(re.finditer(r"CallTC@(\d+)", dump))
    if not matches:
        return None, "", has_active
    last = matches[-1]
    call_num = int(last.group(1))
    chunk = dump[last.start():]
    return call_num, chunk, has_active

def monitor_call_cycle(phone, name, duration_sec):
    global current_call_status
    current_call_status["active"] = True
    current_call_status["current_phone"] = phone
    current_call_status["current_name"] = name
    current_call_status["call_state"] = "DIALING"
    current_call_status["connected_time"] = None
    current_call_status["elapsed_seconds"] = 0
    current_call_status["target_duration"] = duration_sec
    current_call_status["outcome"] = None
    current_call_status["last_error"] = None

    # Snapshot current call ID prior to placement
    initial_dump = get_telecom_dump()
    initial_call_num, _, _ = extract_latest_call_info(initial_dump)

    print(f"[*] Placing call to {name} ({phone}) (previous call_id: {initial_call_num})", flush=True)
    place_call(phone)

    dial_start = time.time()
    call_num = None
    target_chunk = ""
    max_wait_to_register = 8.0 # seconds for CallTC to be created

    # Phase 1: Wait for new CallTC to appear in telecom manager
    while time.time() - dial_start < max_wait_to_register:
        time.sleep(0.4)
        dump = get_telecom_dump()
        c_num, chunk, _ = extract_latest_call_info(dump)
        if c_num is not None and (initial_call_num is None or c_num > initial_call_num):
            call_num = c_num
            target_chunk = chunk
            print(f"[+] New call identified: CallTC@{call_num}", flush=True)
            break

    # If call didn't register a new number, fall back to latest known
    if call_num is None:
        c_num, chunk, _ = extract_latest_call_info(get_telecom_dump())
        call_num = c_num
        target_chunk = chunk

    # Phase 2: Wait for call to either be answered (SET_ACTIVE) or ended (declined/unanswered)
    call_connected = False
    max_ring_time = 45.0 # seconds

    while time.time() - dial_start < max_ring_time:
        time.sleep(0.5)
        dump = get_telecom_dump()
        c_num, chunk, has_active = extract_latest_call_info(dump)

        # Match chunk corresponding to our call
        if c_num == call_num:
            target_chunk = chunk
        elif c_num and call_num and c_num > call_num:
            # Another call occurred
            target_chunk = chunk

        # Check if call answered
        if "SET_ACTIVE" in target_chunk:
            call_connected = True
            current_call_status["call_state"] = "CONNECTED"
            current_call_status["connected_time"] = time.time()
            print(f"[+] Call to {phone} ANSWERED (SET_ACTIVE)! Beginning {duration_sec}s timer from pickup.", flush=True)
            break

        # Check if call was disconnected or declined before answer
        if "SET_DISCONNECTED" in target_chunk or "DESTROYED" in target_chunk:
            # Check elapsed dial time to avoid initial false-positive
            if time.time() - dial_start > 2.0:
                print(f"[-] Call to {phone} was declined / ended before pickup.", flush=True)
                current_call_status["call_state"] = "COMPLETED"
                current_call_status["outcome"] = "declined"
                current_call_status["active"] = False
                return

        # Fallback check if manager has no active call after dialing started
        if not has_active and time.time() - dial_start > 4.0:
            print(f"[-] No active call in Telecom Manager. Call declined/ended.", flush=True)
            current_call_status["call_state"] = "COMPLETED"
            current_call_status["outcome"] = "declined"
            current_call_status["active"] = False
            return

    if not call_connected:
        print(f"[-] Ring timed out for {phone}. Hanging up...", flush=True)
        end_call()
        current_call_status["call_state"] = "COMPLETED"
        current_call_status["outcome"] = "unanswered"
        current_call_status["active"] = False
        return

    # Phase 3: Connected - Count down exact seconds from pickup
    conn_start = time.time()
    while time.time() - conn_start < duration_sec:
        elapsed = round(time.time() - conn_start, 1)
        current_call_status["elapsed_seconds"] = elapsed
        time.sleep(0.4)

        # Check if recipient hung up early
        dump = get_telecom_dump()
        c_num, chunk, has_active = extract_latest_call_info(dump)
        if c_num == call_num:
            target_chunk = chunk

        if "SET_DISCONNECTED" in target_chunk or "DESTROYED" in target_chunk or not has_active:
            print(f"[+] Call ended early by recipient after {elapsed}s active duration.", flush=True)
            current_call_status["call_state"] = "COMPLETED"
            current_call_status["outcome"] = "completed"
            current_call_status["active"] = False
            return

    # Phase 4: Timer reached! Automatically terminate call from our end
    print(f"[*] {duration_sec}s connected timer reached! Automatically hanging up call to {phone}...", flush=True)
    current_call_status["call_state"] = "DISCONNECTING"
    end_call()
    time.sleep(1.0)
    current_call_status["call_state"] = "COMPLETED"
    current_call_status["outcome"] = "completed"
    current_call_status["active"] = False
    print(f"[✓] Call to {name} ({phone}) successfully concluded.", flush=True)

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
        elif self.path == "/api/convai/signed_url":
            try:
                import urllib.request
                api_key = os.environ.get("ELEVENLABS_API_KEY", "sk_d9191a981f7ddca619f2dd4b1787e0cf6fd2e65a3c485e8a")
                agent_id = os.environ.get("ELEVENLABS_AGENT_ID", "agent_8901m4gnv2a6f7xb5n0sbgbznz9f")
                req = urllib.request.Request(
                    f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}",
                    headers={"xi-api-key": api_key}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                    self._send_json(data)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
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

        elif self.path == "/api/convai/configure":
            self._send_json({"ok": True})
        else:
            self._send_json({"error": "not found"}, 404)

if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), BridgeServer)
    print(f"[*] Auto-Dialer Bridge Daemon running on port {PORT} for device {ADB_DEVICE}...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
