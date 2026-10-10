#!/usr/bin/env python3
"""
DEFINE Auto-Dialer & Telephony Bridge Daemon
===========================================
Monitors ADB telecom states, triggers calls on device, detects recipient pickup
(SET_ACTIVE), and keeps the call connected until the recipient hangs up or an
external trigger (POST /end) requests the call to be terminated.

While the call is connected the ElevenLabs Conversational AI agent is attached
to the line exactly like the standalone `elevenlabs/pipewire_agent_call.py`
flow: it is launched as a child process bound to the Bluetooth hands-free
PipeWire nodes and stopped again when the call concludes.
"""

import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ADB_DEVICE = os.environ.get("ADB_DEVICE", "A3SQUT5515003325")
PORT = int(os.environ.get("DIALER_PORT", 8765))

# ---------------------------------------------------------------------------
# ElevenLabs agent (reuse the working elevenlabs/ implementation verbatim)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELEVENLABS_DIR = os.path.join(REPO_ROOT, "elevenlabs")
ELEVENLABS_PYTHON = os.path.join(ELEVENLABS_DIR, ".venv", "bin", "python")
ELEVENLABS_AGENT_SCRIPT = os.path.join(ELEVENLABS_DIR, "pipewire_agent_call.py")

# Import the shared ElevenLabs agent-config helper (works whether the bridge is
# launched from the repo root or as `python3 core/dialer_bridge.py`).
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
try:
    from core.elevenlabs_voice import configure_call_agent
except Exception:
    try:
        from elevenlabs_voice import configure_call_agent
    except Exception:  # pragma: no cover
        configure_call_agent = None

current_call_status = {
    "active": False,
    "current_phone": None,
    "current_name": None,
    "call_state": "IDLE",  # IDLE, DIALING, CONNECTED, DISCONNECTING, COMPLETED
    "connected_time": None,
    "elapsed_seconds": 0,
    "target_duration": 0,  # retained for compatibility; no longer auto-hangs up
    "outcome": None,       # completed, declined, unanswered, error
    "last_error": None,
    "agent_active": False,  # ElevenLabs ConvAI agent attached to the line?
}

# Event set by /end (the future auto-disconnect trigger) to stop the call loop.
call_stop_event = None

# ElevenLabs agent child process, guarded by a lock.
_agent_process = None
_agent_lock = threading.Lock()


# ---------------------------------------------------------------------------
# ElevenLabs agent lifecycle
# ---------------------------------------------------------------------------
def discover_bluetooth_nodes():
    """Find the Bluetooth hands-free PipeWire input/output nodes."""
    try:
        raw = subprocess.check_output(["pw-dump", "Node"], stderr=subprocess.DEVNULL)
        nodes = json.loads(raw)
    except Exception as e:
        print(f"[agent] Could not query PipeWire nodes: {e}", flush=True)
        return None, None, None

    bt_input = None
    bt_output = None
    device_desc = None

    for node in nodes:
        props = node.get("info", {}).get("props", {})
        node_name = props.get("node.name", "")
        desc = props.get("node.description", "")
        media_class = props.get("media.class", "")
        api = props.get("device.api", "")

        is_bluez = ("bluez" in node_name) or (api == "bluez5")
        if not is_bluez:
            continue

        if desc and "BLE MIDI" not in desc:
            device_desc = desc

        if (
            "bluez_input" in node_name
            or media_class in ("Stream/Output/Audio", "Audio/Source")
        ):
            if "bluez_input" in node_name or not bt_input:
                bt_input = node_name

        if (
            "bluez_output" in node_name
            or media_class in ("Stream/Input/Audio", "Audio/Sink")
        ):
            if "bluez_output" in node_name or not bt_output:
                bt_output = node_name

    return bt_input, bt_output, device_desc


def start_agent(input_target=None, output_target=None):
    """Launch the ElevenLabs ConvAI agent bound to the call audio."""
    global _agent_process
    with _agent_lock:
        if _agent_process is not None and _agent_process.poll() is None:
            return True
        if not os.path.isfile(ELEVENLABS_PYTHON):
            print(
                f"[agent] ElevenLabs venv python not found at {ELEVENLABS_PYTHON}. "
                "Run elevenlabs/start_call.sh once to create it.",
                flush=True,
            )
            return False

        cmd = [ELEVENLABS_PYTHON, ELEVENLABS_AGENT_SCRIPT, "--direct"]
        cmd += ["--bridge-url", f"http://127.0.0.1:{PORT}"]
        if input_target:
            cmd += ["--input-target", input_target]
        if output_target:
            cmd += ["--output-target", output_target]

        try:
            _agent_process = subprocess.Popen(cmd, cwd=ELEVENLABS_DIR)
        except Exception as e:
            print(f"[agent] Failed to start ElevenLabs agent: {e}", flush=True)
            _agent_process = None
            return False

        current_call_status["agent_active"] = True
        print(f"[agent] ElevenLabs agent attached (pid {_agent_process.pid})", flush=True)
        return True


def start_agent_when_ready(timeout=25.0):
    """Wait for the Bluetooth hands-free nodes (they usually appear when the
    phone's call audio opens the SCO link), then attach the agent."""
    deadline = time.time() + timeout
    in_node = out_node = None
    last_note = 0.0
    while time.time() < deadline:
        in_node, out_node, _ = discover_bluetooth_nodes()
        if in_node and out_node:
            break
        now = time.time()
        if now - last_note > 5.0:
            last_note = now
            print(
                "[agent] Waiting for Bluetooth hands-free audio nodes "
                "(bluez_input/bluez_output)...",
                flush=True,
            )
        time.sleep(0.5)

    if in_node and out_node:
        print(f"[agent] Bluetooth hands-free: in={in_node} out={out_node}", flush=True)
    else:
        print(
            "[agent] WARNING: no bluez_input/bluez_output nodes appeared after "
            f"{timeout:.0f}s. The phone is probably not routing its call audio to "
            "this laptop over Bluetooth HFP. Falling back to default audio.",
            flush=True,
        )
    return start_agent(in_node, out_node)


def stop_agent():
    """Stop the ElevenLabs agent process (its SIGTERM handler restores links)."""
    global _agent_process
    with _agent_lock:
        proc = _agent_process
        _agent_process = None
    current_call_status["agent_active"] = False
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print("[agent] ElevenLabs agent detached.", flush=True)


# ---------------------------------------------------------------------------
# ADB helpers
# ---------------------------------------------------------------------------
def adb_cmd(cmd_list):
    full_cmd = ["adb", "-s", ADB_DEVICE] + cmd_list
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=8)
        return res.stdout
    except Exception:
        return ""


def wake_screen():
    # Wake up screen and dismiss keyguard
    adb_cmd(["shell", "input", "keyevent", "224"])  # KEYCODE_WAKEUP
    adb_cmd(["shell", "wm", "dismiss-keyguard"])


def bring_app_to_front():
    # Bring our app back to foreground immediately after call concludes
    adb_cmd(["shell", "am", "start", "-n", "com.define.voiceai/.MainActivity", "--activity-brought-to-front"])


def place_call(phone):
    wake_screen()
    clean = re.sub(r"[^\d+]", "", phone)
    adb_cmd(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean}"])


def end_call():
    # Telecom end call via adb telecom or KEYCODE_ENDCALL (6)
    res = adb_cmd(["shell", "telecom", "end-call"])
    if not res or "error" in res.lower():
        adb_cmd(["shell", "input", "keyevent", "6"])
    wake_screen()
    bring_app_to_front()


def get_telecom_dump():
    return adb_cmd(["shell", "dumpsys", "telecom"])


def extract_latest_call_info(dump):
    """
    Returns (call_id_int, call_chunk_str, has_active_call_in_manager)
    """
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

    # Isolate chunk specifically for this call id (from CallTC@X up to next CallTC@ or end)
    start = last.start()
    chunk = dump[start:]
    return call_num, chunk, has_active


def get_call_chunk_by_id(call_id, dump):
    pattern = rf"(CallTC@{call_id}\b.*?)(?=\n\s*CallTC@|\Z)"
    match = re.search(pattern, dump, re.DOTALL)
    return match.group(1) if match else ""


def monitor_call_cycle(phone, name, duration_sec=0, native_dialed=False, script="", language=""):
    global current_call_status, call_stop_event
    call_stop_event = threading.Event()
    current_call_status["active"] = True
    current_call_status["current_phone"] = phone
    current_call_status["current_name"] = name
    current_call_status["call_state"] = "DIALING"
    current_call_status["connected_time"] = None
    current_call_status["elapsed_seconds"] = 0
    current_call_status["target_duration"] = duration_sec
    current_call_status["outcome"] = None
    current_call_status["last_error"] = None
    current_call_status["agent_active"] = False

    # Point the ElevenLabs agent at the operator's template BEFORE it connects,
    # so it speaks the script typed in the UI instead of a stale message.
    if script and configure_call_agent is not None:
        try:
            configure_call_agent(script, name, language)
        except Exception as e:
            print(f"[agent] Could not configure ElevenLabs agent: {e}", flush=True)

    # Snapshot current call ID prior to placement
    initial_dump = get_telecom_dump()
    initial_call_num, _, _ = extract_latest_call_info(initial_dump)

    if not native_dialed:
        print(f"[*] Placing call via ADB to {name} ({phone}) (previous call_id: {initial_call_num})", flush=True)
        place_call(phone)
    else:
        print(f"[*] App placed call directly to {name} ({phone}) (previous call_id: {initial_call_num})", flush=True)

    dial_start = time.time()
    call_num = None
    target_chunk = ""
    max_wait_to_register = 8.0  # seconds for CallTC to be created

    # Phase 1: Wait for new CallTC to appear in telecom manager
    while time.time() - dial_start < max_wait_to_register:
        time.sleep(0.4)
        dump = get_telecom_dump()
        c_num, _, _ = extract_latest_call_info(dump)
        if c_num is not None and (initial_call_num is None or c_num > initial_call_num):
            call_num = c_num
            target_chunk = get_call_chunk_by_id(call_num, dump)
            print(f"[+] New call identified: CallTC@{call_num}", flush=True)
            break

    # If call didn't register a new number, fall back to latest known
    if call_num is None:
        c_num, _, _ = extract_latest_call_info(get_telecom_dump())
        call_num = c_num
        target_chunk = get_call_chunk_by_id(call_num, get_telecom_dump())

    # Phase 2: Wait for call to either be answered (SET_ACTIVE) or ended (declined/unanswered)
    call_connected = False
    max_ring_time = 45.0  # seconds

    while time.time() - dial_start < max_ring_time:
        time.sleep(0.4)
        dump = get_telecom_dump()
        _, _, has_active = extract_latest_call_info(dump)
        target_chunk = get_call_chunk_by_id(call_num, dump)

        # Check if call answered
        if "SET_ACTIVE" in target_chunk:
            call_connected = True
            current_call_status["call_state"] = "CONNECTED"
            current_call_status["connected_time"] = time.time()
            print(f"[+] Call to {phone} ANSWERED (SET_ACTIVE)!", flush=True)
            break

        # Check if call was disconnected or declined before answer
        # Must only check the chunk belonging to call_num!
        if ("SET_DISCONNECTED" in target_chunk or "DESTROYED" in target_chunk) and time.time() - dial_start > 3.0:
            print(f"[-] Call to {phone} was declined / ended before pickup.", flush=True)
            current_call_status["call_state"] = "COMPLETED"
            current_call_status["outcome"] = "declined"
            current_call_status["active"] = False
            return

        # Fallback check if manager has no active call after dialing started
        if not has_active and time.time() - dial_start > 5.0:
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

    # Phase 3: Connected. No automatic hang-up timer — the AI agent stays on the
    # line until the recipient hangs up or an external trigger calls POST /end.
    conn_start = time.time()
    print(
        "[*] Call connected. ElevenLabs agent is now on the line; "
        "no auto-hangup — waiting for the recipient to hang up or /end to be called.",
        flush=True,
    )

    start_agent_when_ready()

    try:
        while not call_stop_event.is_set():
            current_call_status["elapsed_seconds"] = round(time.time() - conn_start, 1)
            time.sleep(0.4)

            dump = get_telecom_dump()
            _, _, has_active = extract_latest_call_info(dump)
            target_chunk = get_call_chunk_by_id(call_num, dump)

            # Recipient hung up on their side.
            if "SET_DISCONNECTED" in target_chunk or "DESTROYED" in target_chunk or not has_active:
                print(
                    f"[+] Call ended by recipient after {current_call_status['elapsed_seconds']}s active duration.",
                    flush=True,
                )
                wake_screen()
                bring_app_to_front()
                current_call_status["outcome"] = "completed"
                break
    finally:
        # Detach the agent first so the line goes quiet, then finalize state.
        stop_agent()
        current_call_status["call_state"] = "COMPLETED"
        if current_call_status["outcome"] is None:
            current_call_status["outcome"] = "completed"
        current_call_status["active"] = False
        print(f"[✓] Call to {name} ({phone}) concluded ({current_call_status['outcome']}).", flush=True)


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
            duration = int(data.get("duration", 0) or 0)
            native_dialed = bool(data.get("native_dialed", False))
            script = data.get("script", "") or ""
            language = data.get("language", "") or ""

            if not phone:
                self._send_json({"error": "phone required"}, 400)
                return

            if current_call_status["active"]:
                self._send_json({"error": "call already in progress", "status": current_call_status}, 409)
                return

            t = threading.Thread(
                target=monitor_call_cycle,
                args=(phone, name, duration, native_dialed, script, language),
                daemon=True,
            )
            t.start()
            self._send_json({"status": "started", "phone": phone, "name": name, "target_duration": duration})

        elif self.path == "/end":
            # Interim external trigger point: the future auto-disconnect will call
            # this same endpoint to terminate the call + agent without a human.
            if call_stop_event is not None:
                call_stop_event.set()
            stop_agent()
            end_call()
            current_call_status["call_state"] = "COMPLETED"
            self._send_json({"status": "ended"})

        elif self.path == "/agent/outcome":
            # Called by the agent subprocess when it has a definite outcome.
            outcome = (data.get("outcome", "") or "").strip()
            end_now = bool(data.get("end", False))
            if outcome:
                current_call_status["outcome"] = outcome
            if end_now:
                if call_stop_event is not None:
                    call_stop_event.set()
                end_call()
                current_call_status["call_state"] = "DISCONNECTING"
            self._send_json({
                "ok": True,
                "outcome": current_call_status.get("outcome"),
                "ended": end_now,
            })

        elif self.path == "/api/convai/configure":
            script = data.get("script", "") or ""
            name = data.get("name", "there") or "there"
            language = data.get("language", "") or ""
            ok = False
            if configure_call_agent is not None:
                try:
                    ok = configure_call_agent(script, name, language)
                except Exception as e:
                    print(f"[agent] Could not configure ElevenLabs agent: {e}", flush=True)
            self._send_json({"ok": bool(ok), "configured": bool(ok)})
        else:
            self._send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), BridgeServer)
    print(f"[*] Auto-Dialer Bridge Daemon running on port {PORT} for device {ADB_DEVICE}...", flush=True)
    print(f"[*] ElevenLabs agent will attach via: {ELEVENLABS_AGENT_SCRIPT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_agent()
