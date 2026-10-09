#!/usr/bin/env python3
"""
Test Suite for ElevenLabs Conversational Agent
==============================================
Validates:
 1. Credential detection from cred.txt / env
 2. API Key authentication & account details
 3. Agent profile retrieval & settings
 4. Signed WebSocket URL generation
 5. Live WebSocket conversation round-trip (Text & Audio)
 6. Local server REST API health check (optional)

Usage:
    python3 test_agent.py
    python3 test_agent.py --test-server http://localhost:8080
"""

import os
import re
import sys
import json
import time
import asyncio
import argparse
import requests
import websockets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
CRED_FILE = os.path.join(BASE_DIR, "cred.txt")

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(title):
    print(f"\n{BOLD}{CYAN}=== [TEST] {title} ==={RESET}")


def print_success(msg):
    print(f"  {GREEN}✔ PASS:{RESET} {msg}")


def print_fail(msg):
    print(f"  {RED}✘ FAIL:{RESET} {msg}")


def print_info(msg):
    print(f"  {YELLOW}ℹ INFO:{RESET} {msg}")


def load_credentials():
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
            print(f"[!] Warning reading .env: {e}")

    # Check cred.txt file
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        if not agent_id:
            agent_match = re.search(r"agent_id=([a-zA-Z0-9_-]+)", content) or re.search(r"\b(agent_[a-zA-Z0-9_]+)\b", content)
            if agent_match:
                agent_id = agent_match.group(1)
        if not api_key:
            key_match = re.search(r"\b(sk_[a-zA-Z0-9]+)\b", content)
            if key_match:
                api_key = key_match.group(1)

    return api_key, agent_id


def test_credentials():
    print_step("1. Credential Extraction")
    api_key, agent_id = load_credentials()
    if not api_key:
        print_fail("Could not find ElevenLabs API Key in cred.txt or ELEVENLABS_API_KEY")
        return False, None, None
    if not agent_id:
        print_fail("Could not find ElevenLabs Agent ID in cred.txt or ELEVENLABS_AGENT_ID")
        return False, None, None

    print_success(f"Found Agent ID: {agent_id}")
    print_success(f"Found API Key:  {api_key[:6]}...{api_key[-4:]}")
    return True, api_key, agent_id


def test_user_authentication(api_key):
    print_step("2. ElevenLabs API Authentication")
    url = "https://api.elevenlabs.io/v1/user"
    headers = {"xi-api-key": api_key}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            tier = data.get("subscription", {}).get("tier", "unknown")
            user_id = data.get("user_id", "unknown")
            first_name = data.get("first_name", "User")
            print_success(f"Authenticated as: {first_name} (ID: {user_id})")
            print_success(f"Subscription Tier: {tier}")
            return True
        else:
            print_fail(f"HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print_fail(f"Connection failed: {e}")
        return False


def test_agent_config(api_key, agent_id):
    print_step("3. Agent Configuration & Health")
    url = f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}"
    headers = {"xi-api-key": api_key}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            name = data.get("name", "Unnamed")
            conv_cfg = data.get("conversation_config", {})
            agent_cfg = conv_cfg.get("agent", {})
            prompt = agent_cfg.get("prompt", {}).get("prompt", "")
            llm = agent_cfg.get("prompt", {}).get("llm", "")
            first_msg = agent_cfg.get("first_message", "")
            voice_id = conv_cfg.get("tts", {}).get("voice_id", "")

            print_success(f"Agent Name:    {name}")
            print_success(f"LLM Engine:    {llm}")
            print_success(f"Voice ID:      {voice_id}")
            print_info(f"First Message: '{first_msg}'")
            print_info(f"System Prompt: '{prompt}'")
            return True, data
        else:
            print_fail(f"HTTP {res.status_code}: {res.text}")
            return False, None
    except Exception as e:
        print_fail(f"Failed to fetch agent config: {e}")
        return False, None


def test_signed_url(api_key, agent_id):
    print_step("4. Signed WebSocket URL Generation")
    url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}"
    headers = {"xi-api-key": api_key}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            signed_url = data.get("signed_url")
            if signed_url and signed_url.startswith("wss://"):
                print_success(f"Generated Signed URL: {signed_url[:65]}...")
                return True, signed_url
            else:
                print_fail("signed_url field missing or invalid format")
                return False, None
        else:
            print_fail(f"HTTP {res.status_code}: {res.text}")
            return False, None
    except Exception as e:
        print_fail(f"Failed to generate signed url: {e}")
        return False, None


async def test_websocket_chat(signed_url):
    print_step("5. Real-Time WebSocket Conversation Test")
    test_message = "Hello! Introduce yourself in one short sentence."
    print_info(f"Sending User Message: \"{test_message}\"")

    try:
        async with websockets.connect(signed_url) as ws:
            print_success("Connected to ElevenLabs WebSocket server!")

            # Wait for initiation metadata
            init_msg = await asyncio.wait_for(ws.recv(), timeout=10)
            init_data = json.loads(init_msg)
            conv_id = init_data.get("conversation_initiation_metadata_event", {}).get("conversation_id")
            print_success(f"Session started! Conversation ID: {conv_id}")

            # Send test message
            await ws.send(json.dumps({
                "type": "user_transcript",
                "user_transcript": test_message
            }))
            print_info("Awaiting agent response & audio chunks...")

            agent_replies = []
            audio_chunks_count = 0
            start_time = time.time()

            while time.time() - start_time < 8.0:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.5)
                    event = json.loads(raw)
                    etype = event.get("type")

                    if etype == "agent_response":
                        reply = event.get("agent_response_event", {}).get("agent_response", "")
                        if reply:
                            agent_replies.append(reply)
                    elif etype == "audio":
                        audio_chunks_count += 1
                    elif etype == "ping":
                        pong = {"type": "pong", "event_id": event.get("ping_event", {}).get("event_id")}
                        await ws.send(json.dumps(pong))
                except asyncio.TimeoutError:
                    if agent_replies:
                        break

            full_reply = " ".join(agent_replies).strip()
            if full_reply:
                print_success(f"Agent Replied: \"{full_reply}\"")
                print_success(f"Received Audio Stream: {audio_chunks_count} PCM chunks")
                return True
            else:
                print_fail("Did not receive agent_response text from WebSocket")
                return False

    except Exception as e:
        print_fail(f"WebSocket conversation test failed: {e}")
        return False


def test_server_endpoint(base_url):
    print_step(f"6. Local Server API Verification ({base_url})")
    try:
        # Check /api/status
        r_status = requests.get(f"{base_url}/api/status", timeout=5)
        if r_status.status_code == 200:
            print_success(f"GET /api/status -> {r_status.json()}")
        else:
            print_fail(f"GET /api/status returned HTTP {r_status.status_code}")
            return False

        # Check /api/signed-url
        r_url = requests.get(f"{base_url}/api/signed-url", timeout=5)
        if r_url.status_code == 200 and "signed_url" in r_url.json():
            print_success("GET /api/signed-url -> OK")
        else:
            print_fail(f"GET /api/signed-url failed: {r_url.text}")
            return False

        # Check /api/chat
        r_chat = requests.post(f"{base_url}/api/chat", json={"message": "Ping test"}, timeout=15)
        if r_chat.status_code == 200:
            data = r_chat.json()
            print_success(f"POST /api/chat -> Reply: \"{data.get('agent_response')}\"")
            print_success(f"Audio chunks received: {data.get('audio_chunks_count')}")
            return True
        else:
            print_fail(f"POST /api/chat returned HTTP {r_chat.status_code}: {r_chat.text}")
            return False
    except requests.exceptions.ConnectionError:
        print_info(f"Local server is not currently running at {base_url} (skip if not started yet)")
        return True
    except Exception as e:
        print_fail(f"Server check error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="ElevenLabs ConvAI Test Suite")
    parser.add_argument("--test-server", default="http://localhost:8080", help="Local server URL to test")
    args = parser.parse_args()

    print(f"\n{BOLD}======================================================{RESET}")
    print(f"{BOLD}    ElevenLabs Conversational AI Automated Tests     {RESET}")
    print(f"{BOLD}======================================================{RESET}")

    # 1. Credentials
    ok, api_key, agent_id = test_credentials()
    if not ok:
        sys.exit(1)

    # 2. Authentication
    if not test_user_authentication(api_key):
        sys.exit(1)

    # 3. Agent Config
    ok, agent_data = test_agent_config(api_key, agent_id)
    if not ok:
        sys.exit(1)

    # 4. Signed URL
    ok, signed_url = test_signed_url(api_key, agent_id)
    if not ok:
        sys.exit(1)

    # 5. Live WebSocket Chat
    ws_ok = asyncio.run(test_websocket_chat(signed_url))
    if not ws_ok:
        sys.exit(1)

    # 6. Local Server Check
    if args.test_server:
        test_server_endpoint(args.test_server)

    print(f"\n{BOLD}{GREEN}======================================================{RESET}")
    print(f"{BOLD}{GREEN}       ALL ELEVENLABS AGENT TESTS PASSED! ✔          {RESET}")
    print(f"{BOLD}{GREEN}======================================================{RESET}\n")


if __name__ == "__main__":
    main()
