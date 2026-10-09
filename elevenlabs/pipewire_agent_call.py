#!/usr/bin/env python3
"""
Permanent Call with ElevenLabs Conversational AI via PipeWire Bluetooth Handsfree
==================================================================================
Connects ElevenLabs Conversational AI directly to your PipeWire audio subsystem:
- Direct capture from Bluetooth handsfree microphone (16kHz PCM)
- Direct playback to Bluetooth handsfree earpiece (16kHz PCM)
- Low-latency local WebRTC Voice Activity Detection (VAD) + RMS energy gating
- Pre-roll circular buffering so speech start is never clipped
- Instant barge-in / interruption (cuts agent speech when user speaks)
- Bluetooth handsfree isolation (prevents laptop mic/speaker feedback loops)
- Permanent call persistence (auto-reconnects on session drops or timeouts)

Usage:
    ./.venv/bin/python pipewire_agent_call.py
    ./.venv/bin/python pipewire_agent_call.py --help
"""

import os
import re
import sys
import json
import time
import math
import base64
import signal
import asyncio
import logging
import argparse
import subprocess
from collections import deque
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import requests
import websockets
import webrtcvad

# ---------------------------------------------------------
# Terminal Formatting Constants
# ---------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RED = "\033[91m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"

ENV_FILE = os.path.join(BASE_DIR, ".env")
CRED_FILE = os.path.join(BASE_DIR, "cred.txt")


# ---------------------------------------------------------
# Credential Loading
# ---------------------------------------------------------
def load_credentials() -> Tuple[Optional[str], Optional[str]]:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")

    # Check .env file
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ELEVENLABS_API_KEY=") and not api_key:
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("ELEVENLABS_AGENT_ID=") and not agent_id:
                        agent_id = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            print(f"{YELLOW}[!] Error reading .env: {e}{RESET}")

    # Check cred.txt file
    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if not agent_id:
                agent_match = (
                    re.search(r"agent_id=([a-zA-Z0-9_-]+)", content)
                    or re.search(r"\b(agent_[a-zA-Z0-9_]+)\b", content)
                )
                if agent_match:
                    agent_id = agent_match.group(1)
            if not api_key:
                key_match = re.search(r"\b(sk_[a-zA-Z0-9]+)\b", content)
                if key_match:
                    api_key = key_match.group(1)
        except Exception as e:
            print(f"{YELLOW}[!] Error reading cred.txt: {e}{RESET}")

    return api_key, agent_id


def get_signed_url(api_key: str, agent_id: str) -> str:
    headers = {"xi-api-key": api_key}
    url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["signed_url"]


# ---------------------------------------------------------
# PipeWire Audio Node Discovery & Isolation
# ---------------------------------------------------------
def discover_pipewire_nodes() -> Tuple[Optional[str], Optional[str], str]:
    """
    Finds Bluetooth Handsfree / Headset nodes in PipeWire:
    Returns (input_node_name, output_node_name, description).
    """
    try:
        raw = subprocess.check_output(["pw-dump", "Node"], stderr=subprocess.DEVNULL)
        nodes = json.loads(raw)
    except Exception as e:
        print(f"{RED}[!] Error querying PipeWire nodes: {e}{RESET}")
        return None, None, "Unknown"

    bt_input = None
    bt_output = None
    device_desc = "Bluetooth Handsfree"

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

        # Audio source coming from bluetooth phone/mic
        if (
            "bluez_input" in node_name
            or media_class in ("Stream/Output/Audio", "Audio/Source")
        ):
            if "bluez_input" in node_name or not bt_input:
                bt_input = node_name

        # Audio sink going to bluetooth phone/headset
        if (
            "bluez_output" in node_name
            or media_class in ("Stream/Input/Audio", "Audio/Sink")
        ):
            if "bluez_output" in node_name or not bt_output:
                bt_output = node_name

    return bt_input, bt_output, device_desc


class BluetoothLinkManager:
    """
    Manages unlinking and restoring default PipeWire loopback connections
    between the PC built-in mic/speakers and Bluetooth headset, preventing
    audio feedback or room noise bleed during calls.
    """

    def __init__(self, bt_input: Optional[str], bt_output: Optional[str]):
        self.bt_input = bt_input
        self.bt_output = bt_output
        self.unlinked_pairs: List[Tuple[str, str]] = []

    def isolate(self):
        if not self.bt_input and not self.bt_output:
            return

        try:
            raw = subprocess.check_output(["pw-link", "-l"], stderr=subprocess.DEVNULL, text=True)
        except Exception:
            return

        lines = raw.splitlines()
        current_source = None

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            if not line.startswith(" ") and not line.startswith("\t"):
                current_source = line_str
            elif "|->" in line_str or "|<-" in line_str:
                parts = line_str.split(" ", 1)
                if len(parts) == 2:
                    target = parts[1].strip()
                    # Check if this link connects ALSA and Bluetooth
                    if current_source and target:
                        src = current_source
                        dst = target
                        if "|<-" in line_str:
                            src, dst = dst, src

                        # ALSA mic -> BT output
                        is_alsa_to_bt = ("alsa_input" in src) and (self.bt_output and self.bt_output in dst)
                        # BT input -> ALSA speaker
                        is_bt_to_alsa = (self.bt_input and self.bt_input in src) and ("alsa_output" in dst)

                        if (is_alsa_to_bt or is_bt_to_alsa) and (src, dst) not in self.unlinked_pairs:
                            try:
                                subprocess.run(["pw-link", "-d", src, dst], check=True, stderr=subprocess.DEVNULL)
                                self.unlinked_pairs.append((src, dst))
                            except Exception:
                                pass

        if self.unlinked_pairs:
            print(f"{CYAN}🔇 Isolated Bluetooth handsfree ({len(self.unlinked_pairs)} loopback links muted for echo cancellation){RESET}")

    def restore(self):
        if not self.unlinked_pairs:
            return

        print(f"\n{CYAN}🔄 Restoring PipeWire audio links...{RESET}")
        for src, dst in self.unlinked_pairs:
            try:
                subprocess.run(["pw-link", src, dst], check=True, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        self.unlinked_pairs.clear()


# ---------------------------------------------------------
# Voice Activity Detection (VAD) & Processing
# ---------------------------------------------------------
class AudioVADProcessor:
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        vad_mode: int = 2,
        rms_threshold: float = 200.0,
        pre_roll_ms: int = 300,
        hangover_ms: int = 650,
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_bytes = int(sample_rate * (frame_duration_ms / 1000.0) * 2)  # 16-bit = 2 bytes
        self.vad = webrtcvad.Vad(vad_mode)
        self.rms_threshold = rms_threshold

        self.pre_roll_count = max(1, int(pre_roll_ms / frame_duration_ms))
        self.hangover_count = max(1, int(hangover_ms / frame_duration_ms))

        self.pre_roll_buffer: deque = deque(maxlen=self.pre_roll_count)
        self.in_speech: bool = False
        self.silent_frames_count: int = 0
        self.recent_vad_decisions: deque = deque(maxlen=3)

    def process_frame(self, raw_bytes: bytes) -> Tuple[bool, float, Optional[str], Optional[List[bytes]]]:
        """
        Processes a single PCM audio frame.
        Returns:
            - is_speech (bool)
            - rms (float)
            - event (None | 'speech_start' | 'speech_end')
            - frames_to_send (Optional[List[bytes]])
        """
        if len(raw_bytes) != self.frame_bytes:
            return False, 0.0, None, None

        # Calculate RMS energy
        samples = np.frombuffer(raw_bytes, dtype=np.int16)
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

        vad_speech = self.vad.is_speech(raw_bytes, self.sample_rate)
        is_speech = vad_speech and (rms >= self.rms_threshold)
        self.recent_vad_decisions.append(is_speech)

        event = None
        frames_to_send = None

        if not self.in_speech:
            self.pre_roll_buffer.append(raw_bytes)
            # Require at least 2 speech detections in last 3 frames to initiate speech
            speech_votes = sum(1 for v in self.recent_vad_decisions if v)
            if speech_votes >= 2:
                self.in_speech = True
                self.silent_frames_count = 0
                event = "speech_start"
                # Send buffered pre-roll audio + current frame
                frames_to_send = list(self.pre_roll_buffer)
                self.pre_roll_buffer.clear()
        else:
            if is_speech:
                self.silent_frames_count = 0
                frames_to_send = [raw_bytes]
            else:
                self.silent_frames_count += 1
                frames_to_send = [raw_bytes]

                if self.silent_frames_count >= self.hangover_count:
                    self.in_speech = False
                    event = "speech_end"
                    # Add 3 frames of silence padding to cleanly terminate turn
                    silence_pad = b"\x00" * self.frame_bytes
                    frames_to_send.extend([silence_pad] * 3)

        return is_speech, rms, event, frames_to_send


# ---------------------------------------------------------
# Audio Playback Worker (PipeWire pw-play)
# ---------------------------------------------------------
class AudioPlaybackWorker:
    def __init__(self, target_node: Optional[str], sample_rate: int = 16000):
        self.target_node = target_node
        self.sample_rate = sample_rate
        self.process: Optional[subprocess.Popen] = None
        self.queue: asyncio.Queue = asyncio.Queue()
        self.is_playing: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self):
        self._stop_event.clear()
        self._worker_task = asyncio.create_task(self._playback_loop())

    async def _ensure_process(self):
        if self.process is None or self.process.poll() is not None:
            cmd = [
                "pw-play",
                "--rate", str(self.sample_rate),
                "--channels", "1",
                "--format", "s16",
                "-a",
                "-"
            ]
            if self.target_node:
                cmd.extend(["--target", self.target_node])

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

    async def _playback_loop(self):
        while not self._stop_event.is_set():
            try:
                chunk = await self.queue.get()
                if chunk is None:
                    continue

                await self._ensure_process()
                self.is_playing = True

                # Write chunk in executor to prevent event loop blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._write_chunk, chunk)

                # If queue is empty, mark playing finished after a brief drain interval
                if self.queue.empty():
                    await asyncio.sleep(0.05)
                    if self.queue.empty():
                        self.is_playing = False

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"{YELLOW}[!] Playback error: {e}{RESET}")
                self.is_playing = False

    def _write_chunk(self, chunk: bytes):
        try:
            if self.process and self.process.stdin:
                self.process.stdin.write(chunk)
                self.process.stdin.flush()
        except Exception:
            self.stop_playback_immediately()

    def feed_audio(self, pcm_bytes: bytes):
        self.queue.put_nowait(pcm_bytes)

    def stop_playback_immediately(self):
        """Immediately aborts current playback for barge-in / interruption."""
        self.is_playing = False
        # Drain queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception:
                break

        # Terminate active pw-play process
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=0.2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    async def stop(self):
        self._stop_event.set()
        self.stop_playback_immediately()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass


# ---------------------------------------------------------
# Terminal Status Rendering & VU Meter
# ---------------------------------------------------------
def render_vu_meter(rms: float, max_rms: float = 3000.0, is_speech: bool = False, in_speech_turn: bool = False) -> str:
    bars = 10
    level = min(1.0, max(0.0, rms / max_rms))
    filled = int(level * bars)
    empty = bars - filled

    if in_speech_turn or is_speech:
        meter = f"{GREEN}{'█' * filled}{DIM}{'░' * empty}{RESET}"
        status = f"{BOLD}{GREEN}🗣️  [TALKING]{RESET}"
    else:
        meter = f"{CYAN}{'█' * filled}{DIM}{'░' * empty}{RESET}"
        status = f"{DIM}🎙️  [LISTENING]{RESET}"

    return f"[{meter}] {status}"


# ---------------------------------------------------------
# Main ElevenLabs PipeWire Call Session
# ---------------------------------------------------------
class PermanentCallSession:
    def __init__(
        self,
        api_key: str,
        agent_id: str,
        input_target: Optional[str],
        output_target: Optional[str],
        device_name: str,
        vad_mode: int = 2,
        rms_threshold: float = 200.0,
        hangover_ms: int = 650,
        isolate_links: bool = True,
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.input_target = input_target
        self.output_target = output_target
        self.device_name = device_name
        self.vad_mode = vad_mode
        self.rms_threshold = rms_threshold
        self.hangover_ms = hangover_ms
        self.isolate_links = isolate_links

        self.link_manager = BluetoothLinkManager(input_target, output_target)
        self.player = AudioPlaybackWorker(output_target, sample_rate=16000)
        self.vad_processor = AudioVADProcessor(
            sample_rate=16000,
            frame_duration_ms=30,
            vad_mode=vad_mode,
            rms_threshold=rms_threshold,
            hangover_ms=hangover_ms,
        )

        self.record_proc: Optional[subprocess.Popen] = None
        self.running: bool = True
        self.call_start_time: float = time.time()
        self.last_status_time: float = 0.0
        self._cleaned_up: bool = False

    def print_banner(self):
        print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║     ELEVENLABS CONVERSATIONAL AI &middot; PERMANENT BLUETOOTH CALL         ║{RESET}")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  {BOLD}Device Name:{RESET}       {WHITE}{self.device_name}{RESET}")
        print(f"  {BOLD}Input Stream:{RESET}      {CYAN}{self.input_target or 'Default Source'}{RESET}")
        print(f"  {BOLD}Output Stream:{RESET}     {CYAN}{self.output_target or 'Default Sink'}{RESET}")
        print(f"  {BOLD}VAD Sensitivity:{RESET}   Mode {self.vad_mode} (WebRTC) | Min RMS: {self.rms_threshold}")
        print(f"  {BOLD}Audio Codec:{RESET}       16,000 Hz, 16-bit PCM Mono (Native MSBC Handsfree)")
        print(f"  {BOLD}Call Mode:{RESET}         Permanent (Auto-reconnecting)")
        print(f"{DIM}────────────────────────────────────────────────────────────────────────{RESET}\n")

    async def run(self):
        self.print_banner()

        if self.isolate_links:
            self.link_manager.isolate()

        self.player.start()

        reconnect_count = 0
        while self.running:
            try:
                reconnect_count += 1
                if reconnect_count > 1:
                    print(f"\n{YELLOW}📞 Re-establishing permanent call connection (attempt #{reconnect_count})...{RESET}")

                signed_url = get_signed_url(self.api_key, self.agent_id)
                await self._run_single_call(signed_url)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.running:
                    break
                print(f"\n{RED}[!] Call session interrupted: {e}{RESET}")
                print(f"{YELLOW}⏳ Reconnecting in 2 seconds... (Press Ctrl+C to stop){RESET}")
                await asyncio.sleep(2.0)

        # Cleanup
        await self.cleanup()

    async def _run_single_call(self, signed_url: str):
        call_session_start = time.time()
        print(f"{GREEN}📞 CONNECTING TO AGENT...{RESET}")

        async with websockets.connect(
            signed_url,
            ping_interval=20,
            ping_timeout=20,
            max_size=10_000_000
        ) as ws:
            print(f"{BOLD}{GREEN}✔ CALL CONNECTED! Speak into your handsfree anytime.{RESET}\n")

            # Spawn PipeWire recording process
            cmd = [
                "pw-record",
                "--rate", "16000",
                "--channels", "1",
                "--format", "s16",
                "-a",
                "-"
            ]
            if self.input_target:
                cmd.extend(["--target", self.input_target])

            self.record_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            # Start concurrent audio capture, server event listener, and device liveness monitor
            capture_task = asyncio.create_task(self._capture_audio_loop(ws))
            events_task = asyncio.create_task(self._handle_server_events(ws))
            liveness_task = asyncio.create_task(self._monitor_device_liveness())

            done, pending = await asyncio.wait(
                [capture_task, events_task, liveness_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            # Ensure capture process stops for this session
            if self.record_proc:
                try:
                    self.record_proc.terminate()
                    self.record_proc.wait(timeout=0.5)
                except Exception:
                    pass
                self.record_proc = None

    async def _monitor_device_liveness(self):
        """Monitors if Bluetooth handsfree device is still exported in PipeWire."""
        while self.running:
            await asyncio.sleep(0.8)
            if self.input_target and "bluez" in self.input_target:
                in_node, out_node, _ = discover_pipewire_nodes()
                if not in_node or not out_node:
                    print(f"\n{YELLOW}[!] Bluetooth handsfree disconnected / closed in WirePlumber.{RESET}")
                    self.running = False
                    break

    async def _capture_audio_loop(self, ws: Any):
        """Reads audio from PipeWire pw-record, runs VAD, streams speech chunks to WebSocket."""
        frame_bytes = self.vad_processor.frame_bytes
        loop = asyncio.get_running_loop()

        while self.running:
            if not self.record_proc or not self.record_proc.stdout:
                break

            # Read frame asynchronously
            try:
                raw_chunk = await loop.run_in_executor(None, self.record_proc.stdout.read, frame_bytes)
                if not raw_chunk or len(raw_chunk) < frame_bytes:
                    await asyncio.sleep(0.01)
                    continue
            except Exception:
                break

            is_speech, rms, event, frames_to_send = self.vad_processor.process_frame(raw_chunk)

            # Terminal VU Meter update (throttled ~10 times per second)
            now = time.time()
            if now - self.last_status_time > 0.12:
                self.last_status_time = now
                duration_sec = int(now - self.call_start_time)
                mins, secs = divmod(duration_sec, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                vu = render_vu_meter(rms, rms_threshold := self.rms_threshold * 8, is_speech, self.vad_processor.in_speech)
                sys.stdout.write(f"\r  {DIM}[Call {time_str}]{RESET} {vu}   ")
                sys.stdout.flush()

            # Speech onset: Local Barge-In Interruption
            if event == "speech_start":
                if self.player.is_playing:
                    # User interrupted the agent!
                    self.player.stop_playback_immediately()
                    sys.stdout.write(f"\n  {YELLOW}⚡ [BARGE-IN]{RESET} Agent interrupted by user speech\n")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\n  {GREEN}🎙️  [Speech Started]{RESET}\n")
                    sys.stdout.flush()

            elif event == "speech_end":
                sys.stdout.write(f"\n  {CYAN}⏳ [Processing reply...]{RESET}\n")
                sys.stdout.flush()

            # Transmit audio frames
            if frames_to_send:
                for frame in frames_to_send:
                    b64_data = base64.b64encode(frame).decode("ascii")
                    msg = json.dumps({"user_audio_chunk": b64_data})
                    try:
                        await ws.send(msg)
                    except (websockets.exceptions.ConnectionClosed, Exception):
                        return

    async def _handle_server_events(self, ws: Any):
        """Processes events from ElevenLabs Conversational AI."""
        while self.running:
            try:
                raw_msg = await ws.recv()
                event = json.loads(raw_msg)
                etype = event.get("type")

                if etype == "conversation_initiation_metadata":
                    meta = event.get("conversation_initiation_metadata_event", {})
                    conv_id = meta.get("conversation_id", "unknown")
                    print(f"\n{BOLD}{BLUE}💬 Session ID:{RESET} {conv_id}")

                elif etype == "user_transcript":
                    user_text = event.get("user_transcription_event", {}).get("user_transcript", "").strip()
                    if user_text:
                        print(f"\n{BOLD}{CYAN}👤 YOU:{RESET} \"{user_text}\"")

                elif etype == "agent_response":
                    agent_text = event.get("agent_response_event", {}).get("agent_response", "").strip()
                    if agent_text:
                        print(f"\n{BOLD}{MAGENTA}🤖 AGENT:{RESET} \"{agent_text}\"")

                elif etype == "audio":
                    chunk_b64 = event.get("audio_event", {}).get("audio_base_64", "")
                    if chunk_b64:
                        pcm_bytes = base64.b64decode(chunk_b64)
                        self.player.feed_audio(pcm_bytes)

                elif etype == "interruption":
                    # Server confirmed interruption event
                    self.player.stop_playback_immediately()

                elif etype == "ping":
                    event_id = event.get("ping_event", {}).get("event_id")
                    pong = {"type": "pong", "event_id": event_id}
                    await ws.send(json.dumps(pong))

            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                if self.running:
                    print(f"\n{YELLOW}[!] Event parsing error: {e}{RESET}")
                break

    async def cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True
        print(f"\n{YELLOW}🛑 Stopping call and cleaning up resources...{RESET}")
        self.running = False
        if self.record_proc:
            try:
                self.record_proc.terminate()
            except Exception:
                pass

        await self.player.stop()

        if self.isolate_links:
            self.link_manager.restore()

        print(f"{GREEN}✔ Call ended cleanly.{RESET}\n")



# ---------------------------------------------------------
# WirePlumber Export Watcher Daemon
# ---------------------------------------------------------
class WirePlumberExportWatcher:
    """
    Monitors WirePlumber export for Bluetooth handsfree devices:
    - Auto-turns ON the ElevenLabs call when handsfree opens / turns on.
    - Closes ElevenLabs connection when handsfree closes / turns off.
    - Always listens in standby for the next time the device opens.
    """

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        vad_mode: int = 2,
        rms_threshold: float = 220.0,
        hangover_ms: int = 650,
        isolate_links: bool = True,
        check_interval_sec: float = 0.8,
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.vad_mode = vad_mode
        self.rms_threshold = rms_threshold
        self.hangover_ms = hangover_ms
        self.isolate_links = isolate_links
        self.check_interval_sec = check_interval_sec
        self.running = True
        self.active_session: Optional[PermanentCallSession] = None

    async def run(self):
        print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║     WIREPLUMBER EXPORT WATCHER &middot; BLUETOOTH HANDSFREE DAEMON         ║{RESET}")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  {BOLD}Status:{RESET}  {YELLOW}Listening for WirePlumber export of Bluetooth Handsfree...{RESET}")
        print(f"  {BOLD}Policy:{RESET}  Turn ON call when handsfree opens | Close connection when closed\n")

        last_standby_msg = 0.0

        while self.running:
            in_node, out_node, dev_desc = discover_pipewire_nodes()

            if in_node and out_node:
                print(f"\n{BOLD}{GREEN}🎧 [WirePlumber Export Detected]{RESET} Handsfree opened: {WHITE}{dev_desc}{RESET}")
                print(f"   Input Node:  {CYAN}{in_node}{RESET}")
                print(f"   Output Node: {CYAN}{out_node}{RESET}")
                print(f"   {BOLD}{GREEN}🚀 Turning ON ElevenLabs call connection...{RESET}\n")

                session = PermanentCallSession(
                    api_key=self.api_key,
                    agent_id=self.agent_id,
                    input_target=in_node,
                    output_target=out_node,
                    device_name=dev_desc,
                    vad_mode=self.vad_mode,
                    rms_threshold=self.rms_threshold,
                    hangover_ms=self.hangover_ms,
                    isolate_links=self.isolate_links,
                )
                self.active_session = session

                try:
                    await session.run()
                finally:
                    self.active_session = None

                print(f"\n{YELLOW}📴 [WirePlumber Export Closed]{RESET} Handsfree disconnected / turned off.")
                print(f"{CYAN}🛑 ElevenLabs connection closed.{RESET}")
                print(f"{DIM}⏳ Returning to standby: Waiting for Bluetooth handsfree to open...{RESET}\n")
                last_standby_msg = time.time()
            else:
                now = time.time()
                if now - last_standby_msg > 10.0:
                    last_standby_msg = now
                    print(f"{DIM}[{time.strftime('%H:%M:%S')}] ⏳ Standby: Listening for WirePlumber export of Bluetooth handsfree...{RESET}")
                await asyncio.sleep(self.check_interval_sec)

    async def cleanup(self):
        self.running = False
        if self.active_session:
            self.active_session.running = False
            await self.active_session.cleanup()
        print(f"{GREEN}✔ WirePlumber watcher stopped cleanly.{RESET}\n")


# ---------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ElevenLabs Conversational AI - Permanent Bluetooth Call")
    parser.add_argument("--watch", action="store_true", default=True, help="Always watch WirePlumber export and auto-connect when handsfree opens (default: True)")
    parser.add_argument("--direct", action="store_true", help="Connect immediately without WirePlumber export watcher loop")
    parser.add_argument("--input-target", default=None, help="PipeWire node for mic input (default: auto-detected bluetooth)")
    parser.add_argument("--output-target", default=None, help="PipeWire node for speaker playback (default: auto-detected bluetooth)")
    parser.add_argument("--vad-mode", type=int, choices=[0, 1, 2, 3], default=2, help="WebRTC VAD aggressiveness (0-3, default 2)")
    parser.add_argument("--rms-threshold", type=float, default=220.0, help="Minimum audio RMS energy for VAD (default 220.0)")
    parser.add_argument("--hangover-ms", type=int, default=650, help="Silence hangover time before ending speech turn (default 650ms)")
    parser.add_argument("--no-isolate", action="store_true", help="Do not isolate Bluetooth from laptop ALSA mic/speakers")
    parser.add_argument("--default-audio", action="store_true", help="Use default PipeWire audio instead of Bluetooth nodes")
    args = parser.parse_args()

    api_key, agent_id = load_credentials()
    if not api_key:
        print(f"{RED}Error: ElevenLabs API Key not found in cred.txt or ELEVENLABS_API_KEY environment variable.{RESET}")
        sys.exit(1)
    if not agent_id:
        print(f"{RED}Error: ElevenLabs Agent ID not found in cred.txt or ELEVENLABS_AGENT_ID environment variable.{RESET}")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Direct connection mode (bypasses watcher daemon)
    if args.direct or args.default_audio:
        in_target = args.input_target
        out_target = args.output_target
        device_name = "System Audio"

        if not args.default_audio and (not in_target or not out_target):
            detected_in, detected_out, dev_desc = discover_pipewire_nodes()
            if not in_target:
                in_target = detected_in
            if not out_target:
                out_target = detected_out
            device_name = dev_desc

        session = PermanentCallSession(
            api_key=api_key,
            agent_id=agent_id,
            input_target=in_target,
            output_target=out_target,
            device_name=device_name,
            vad_mode=args.vad_mode,
            rms_threshold=args.rms_threshold,
            hangover_ms=args.hangover_ms,
            isolate_links=not args.no_isolate,
        )

        def sig_handler(sig, frame):
            session.running = False
            for task in asyncio.all_tasks(loop):
                task.cancel()

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        try:
            loop.run_until_complete(session.run())
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            loop.run_until_complete(session.cleanup())
            loop.close()

    else:
        # Default: Watch WirePlumber export continuously
        watcher = WirePlumberExportWatcher(
            api_key=api_key,
            agent_id=agent_id,
            vad_mode=args.vad_mode,
            rms_threshold=args.rms_threshold,
            hangover_ms=args.hangover_ms,
            isolate_links=not args.no_isolate,
        )

        def sig_handler(sig, frame):
            watcher.running = False
            if watcher.active_session:
                watcher.active_session.running = False
            for task in asyncio.all_tasks(loop):
                task.cancel()

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        try:
            loop.run_until_complete(watcher.run())
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            loop.run_until_complete(watcher.cleanup())
            loop.close()


if __name__ == "__main__":
    main()

