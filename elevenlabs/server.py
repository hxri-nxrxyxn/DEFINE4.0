#!/usr/bin/env python3
"""
ElevenLabs Conversational Agent Server
======================================
Serves an interactive Web UI and REST API for interacting with your
ElevenLabs Conversational AI Agent (agentshrek).

Usage:
    python3 server.py [--port 8080] [--host 0.0.0.0]
"""

import os
import re
import sys
import json
import asyncio
import argparse
import base64
from typing import Optional, Dict, Any
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import requests
import websockets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
CRED_FILE = os.path.join(BASE_DIR, "cred.txt")


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """Loads API key and Agent ID from environment variables, .env, or cred.txt."""
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
        try:
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
        except Exception as e:
            print(f"[!] Warning reading cred.txt: {e}")

    return api_key, agent_id


API_KEY, AGENT_ID = load_credentials()
conversation_history: list[dict] = []


def get_agent_info() -> Dict[str, Any]:
    """Fetches agent details from ElevenLabs API."""
    if not API_KEY or not AGENT_ID:
        raise ValueError("Missing ElevenLabs API Key or Agent ID in cred.txt / environment")

    headers = {"xi-api-key": API_KEY}
    url = f"https://api.elevenlabs.io/v1/convai/agents/{AGENT_ID}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_signed_url() -> str:
    """Generates a signed WebSocket URL for safe client or backend connections."""
    if not API_KEY or not AGENT_ID:
        raise ValueError("Missing ElevenLabs API Key or Agent ID in cred.txt / environment")

    headers = {"xi-api-key": API_KEY}
    url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={AGENT_ID}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["signed_url"]


async def query_agent_ws(prompt: str) -> Dict[str, Any]:
    """Communicates with ElevenLabs Conversational WebSocket agent."""
    signed_url = get_signed_url()
    
    agent_texts = []
    audio_chunks = []
    conversation_id = None

    async with websockets.connect(signed_url) as ws:
        # Wait for conversation_initiation_metadata
        try:
            init_raw = await asyncio.wait_for(ws.recv(), timeout=8)
            init_data = json.loads(init_raw)
            if init_data.get("type") == "conversation_initiation_metadata":
                conversation_id = init_data.get("conversation_initiation_metadata_event", {}).get("conversation_id")
        except Exception as e:
            print(f"[!] Warning waiting for metadata: {e}")

        # Send user text transcript
        user_msg = {
            "type": "user_transcript",
            "user_transcript": prompt
        }
        await ws.send(json.dumps(user_msg))

        # Listen for replies
        start_time = asyncio.get_event_loop().time()
        max_duration = 12.0
        silence_timeout = 5.0

        while (asyncio.get_event_loop().time() - start_time) < max_duration:
            try:
                # If we already have response text and audio, use a quick timeout
                current_timeout = 1.8 if (agent_texts and audio_chunks) else silence_timeout
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=current_timeout)
                event = json.loads(msg_raw)
                etype = event.get("type")

                if etype == "agent_response":
                    text = event.get("agent_response_event", {}).get("agent_response", "")
                    if text:
                        agent_texts.append(text)
                elif etype == "audio":
                    chunk = event.get("audio_event", {}).get("audio_base_64", "")
                    if chunk:
                        audio_chunks.append(chunk)
                elif etype == "ping":
                    # If we already received agent text and audio, a ping indicates ElevenLabs finished streaming this turn
                    if agent_texts and audio_chunks:
                        break
                    eid = event.get("ping_event", {}).get("event_id")
                    pong = {"type": "pong", "event_id": eid}
                    await ws.send(json.dumps(pong))
            except asyncio.TimeoutError:
                # If we have response text, finish turn
                if agent_texts:
                    break
                # If nothing received yet and timed out, exit
                break

    reply_text = " ".join(agent_texts).strip()
    return {
        "user_message": prompt,
        "agent_response": reply_text if reply_text else "(No response received)",
        "conversation_id": conversation_id,
        "audio_chunks_count": len(audio_chunks),
        "audio_base64": audio_chunks[0] if audio_chunks else None,
        "all_audio_base64": audio_chunks
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ElevenLabs Agent Console &middot; {agent_name}</title>
    <script src="https://elevenlabs.io/convai-widget/index.js" async type="text/javascript"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #090d16;
            --surface: #101726;
            --surface-border: #1e293b;
            --accent: #10b981;
            --accent-glow: rgba(16, 185, 129, 0.25);
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.25);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --chat-user-bg: #312e81;
            --chat-agent-bg: #1e293b;
            --font-main: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: var(--font-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.1) 0%, transparent 40%);
        }}
        header {{
            background: rgba(16, 23, 38, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--surface-border);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 50;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .brand-badge {{
            background: linear-gradient(135deg, #10b981, #059669);
            width: 38px;
            height: 38px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 20px;
            color: #fff;
            box-shadow: 0 0 15px var(--accent-glow);
        }}
        .brand-title h1 {{
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .brand-title p {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.9); }}
        }}
        main {{
            flex: 1;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 24px;
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 24px;
        }}
        @media (max-width: 900px) {{
            main {{
                grid-template-columns: 1fr;
            }}
        }}
        .sidebar {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}
        .card-header {{
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            color: var(--text-main);
        }}
        .meta-item {{
            margin-bottom: 12px;
        }}
        .meta-item:last-child {{
            margin-bottom: 0;
        }}
        .meta-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .meta-value {{
            font-size: 0.85rem;
            font-family: var(--font-mono);
            background: rgba(0,0,0,0.3);
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.05);
            word-break: break-all;
        }}
        .btn {{
            cursor: pointer;
            border: none;
            outline: none;
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s ease;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: white;
            box-shadow: 0 2px 10px var(--primary-glow);
        }}
        .btn-primary:hover {{
            background: linear-gradient(135deg, #4f46e5, #4338ca);
            transform: translateY(-1px);
        }}
        .btn-secondary {{
            background: rgba(255,255,255,0.06);
            color: var(--text-main);
            border: 1px solid var(--surface-border);
        }}
        .btn-secondary:hover {{
            background: rgba(255,255,255,0.1);
        }}
        .btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}
        .chat-container {{
            display: flex;
            flex-direction: column;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 16px;
            height: calc(100vh - 140px);
            min-height: 550px;
            box-shadow: 0 4px 25px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .chat-header {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(16, 23, 38, 0.5);
        }}
        .chat-header-info h2 {{
            font-size: 1.05rem;
            font-weight: 700;
        }}
        .chat-header-info p {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        .chat-messages {{
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .msg {{
            display: flex;
            flex-direction: column;
            max-width: 80%;
            animation: fadeIn 0.3s ease;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(6px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .msg.user {{
            align-self: flex-end;
        }}
        .msg.agent {{
            align-self: flex-start;
        }}
        .msg-bubble {{
            padding: 14px 18px;
            border-radius: 14px;
            font-size: 0.92rem;
            line-height: 1.5;
        }}
        .msg.user .msg-bubble {{
            background: linear-gradient(135deg, #4f46e5, #6366f1);
            color: white;
            border-bottom-right-radius: 4px;
        }}
        .msg.agent .msg-bubble {{
            background: var(--chat-agent-bg);
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            border-bottom-left-radius: 4px;
        }}
        .msg-meta {{
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-top: 4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .msg.user .msg-meta {{
            align-self: flex-end;
        }}
        .quick-prompts {{
            padding: 8px 20px;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            border-top: 1px solid var(--surface-border);
            background: rgba(0,0,0,0.15);
        }}
        .quick-chip {{
            white-space: nowrap;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--surface-border);
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 0.75rem;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
        }}
        .quick-chip:hover {{
            background: rgba(99, 102, 241, 0.15);
            color: #fff;
            border-color: #6366f1;
        }}
        .chat-input-area {{
            padding: 16px 20px;
            border-top: 1px solid var(--surface-border);
            display: flex;
            gap: 12px;
            background: rgba(16, 23, 38, 0.5);
        }}
        .chat-input {{
            flex: 1;
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 12px 16px;
            border-radius: 10px;
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        .chat-input:focus {{
            border-color: #6366f1;
            box-shadow: 0 0 0 2px var(--primary-glow);
        }}
        .audio-player-btn {{
            background: none;
            border: none;
            color: #10b981;
            cursor: pointer;
            font-size: 0.75rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 6px;
            border-radius: 4px;
            background: rgba(16, 185, 129, 0.1);
        }}
        .audio-player-btn:hover {{
            background: rgba(16, 185, 129, 0.2);
        }}
        .typing-indicator {{
            display: none;
            align-items: center;
            gap: 4px;
            padding: 12px 18px;
            background: var(--chat-agent-bg);
            border-radius: 14px;
            width: fit-content;
            margin-bottom: 12px;
            border: 1px solid var(--surface-border);
        }}
        .typing-dot {{
            width: 6px;
            height: 6px;
            background: var(--text-muted);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }}
        .typing-dot:nth-child(1) {{ animation-delay: -0.32s; }}
        .typing-dot:nth-child(2) {{ animation-delay: -0.16s; }}
        @keyframes bounce {{
            0%, 80%, 100% {{ transform: scale(0); }}
            40% {{ transform: scale(1.0); }}
        }}
        /* Voice Call Card */
        .voice-section {{
            background: linear-gradient(145deg, rgba(16, 185, 129, 0.08), rgba(99, 102, 241, 0.08));
            border: 1px solid rgba(16, 185, 129, 0.25);
            text-align: center;
        }}
        .voice-section p {{
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 12px;
        }}
        .test-console {{
            font-family: var(--font-mono);
            font-size: 0.78rem;
            background: #050811;
            padding: 12px;
            border-radius: 8px;
            color: #38bdf8;
            max-height: 140px;
            overflow-y: auto;
            border: 1px solid rgba(255,255,255,0.06);
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-badge">E</div>
            <div class="brand-title">
                <h1>ElevenLabs Agent Server</h1>
                <p>Conversational AI Live Gateway</p>
            </div>
        </div>
        <div class="header-actions">
            <span class="status-pill">
                <span class="status-dot"></span>
                Connected: {agent_name}
            </span>
        </div>
    </header>

    <main>
        <div class="sidebar">
            <div class="card voice-section">
                <div class="card-header" style="justify-content: center; margin-bottom: 8px;">
                    <span>🎙️ Live Voice Interaction</span>
                </div>
                <p>Talk directly with your agent using ElevenLabs official WebRTC widget</p>
                <elevenlabs-convai agent-id="{agent_id}"></elevenlabs-convai>
                <button class="btn" onclick="new Audio('/i_love_you_daison.mp3').play()" style="background: linear-gradient(135deg, #ec4899, #f43f5e); color: white; width: 100%; margin-top: 12px; font-weight: bold; box-shadow: 0 2px 10px rgba(244, 63, 94, 0.3);">
                    ❤️ Play "I love you Daison"
                </button>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>⚙️ Agent Configuration</span>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Agent Name</div>
                    <div class="meta-value" style="color: #34d399; font-weight: bold;">{agent_name}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Agent ID</div>
                    <div class="meta-value">{agent_id}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Voice ID</div>
                    <div class="meta-value">{voice_id}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">LLM Model</div>
                    <div class="meta-value">{llm_model}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">First Message</div>
                    <div class="meta-value" style="font-size: 0.78rem;">{first_message}</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>🧪 Diagnostics</span>
                    <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;" onclick="runDiagnostics()">Test</button>
                </div>
                <div id="diagConsole" class="test-console">Ready to test agent backend...</div>
            </div>
        </div>

        <div class="chat-container">
            <div class="chat-header">
                <div class="chat-header-info">
                    <h2>Chat with {agent_name}</h2>
                    <p>Real-time conversational transcript & voice synthesis</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <label style="font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; cursor: pointer;">
                        <input type="checkbox" id="autoplayAudio" checked> Autoplay voice
                    </label>
                    <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 0.78rem;" onclick="clearChat()">Clear</button>
                </div>
            </div>

            <div class="chat-messages" id="chatMessages">
                <div class="msg agent">
                    <div class="msg-bubble">{first_message}</div>
                    <div class="msg-meta">
                        <span>{agent_name}</span> &middot; <span>Initial greeting</span>
                    </div>
                </div>
                <div id="typingIndicator" class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>

            <div class="quick-prompts">
                <span class="quick-chip" onclick="sendQuick('Hello, who are you and what do you do?')">👋 Introduce yourself</span>
                <span class="quick-chip" onclick="sendQuick('Tell me a short funny joke')">😄 Tell a joke</span>
                <span class="quick-chip" onclick="sendQuick('What are your special skills?')">⚡ Skills</span>
                <span class="quick-chip" onclick="sendQuick('What is the weather in the swamp?')">🐸 The swamp</span>
            </div>

            <form class="chat-input-area" id="chatForm" onsubmit="handleSend(event)">
                <input type="text" id="userInput" class="chat-input" placeholder="Type a message to talk to {agent_name}..." autocomplete="off">
                <button type="submit" id="sendBtn" class="btn btn-primary">
                    <span>Send</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </form>
        </div>
    </main>

    <script>
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: 16000 }});

        // Function to play PCM 16-bit 16kHz audio returned from ElevenLabs
        function playPcmBase64(base64Data) {{
            try {{
                const binaryString = atob(base64Data);
                const len = binaryString.length;
                const bytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {{
                    bytes[i] = binaryString.charCodeAt(i);
                }}
                const int16Array = new Int16Array(bytes.buffer);
                const float32Array = new Float32Array(int16Array.length);
                for (let i = 0; i < int16Array.length; i++) {{
                    float32Array[i] = int16Array[i] / 32768.0;
                }}

                const buffer = audioCtx.createBuffer(1, float32Array.length, 16000);
                buffer.copyToChannel(float32Array, 0);

                const source = audioCtx.createBufferSource();
                source.buffer = buffer;
                source.connect(audioCtx.destination);
                source.start();
            }} catch (err) {{
                console.error("Audio playback error:", err);
            }}
        }}

        function playChunks(chunks) {{
            if (!chunks || chunks.length === 0) return;
            // Concatenate all base64 PCM chunks
            try {{
                let totalLen = 0;
                const byteArrays = chunks.map(c => {{
                    const bin = atob(c);
                    const bytes = new Uint8Array(bin.length);
                    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                    totalLen += bytes.length;
                    return bytes;
                }});

                const merged = new Uint8Array(totalLen);
                let offset = 0;
                for (const arr of byteArrays) {{
                    merged.set(arr, offset);
                    offset += arr.length;
                }}

                const int16 = new Int16Array(merged.buffer);
                const float32 = new Float32Array(int16.length);
                for (let i = 0; i < int16.length; i++) {{
                    float32[i] = int16[i] / 32768.0;
                }}

                const buffer = audioCtx.createBuffer(1, float32.length, 16000);
                buffer.copyToChannel(float32, 0);
                const src = audioCtx.createBufferSource();
                src.buffer = buffer;
                src.connect(audioCtx.destination);
                src.start();
            }} catch (e) {{
                console.error("Error playing combined audio:", e);
            }}
        }}

        const messagesContainer = document.getElementById("chatMessages");
        const typingIndicator = document.getElementById("typingIndicator");
        const userInput = document.getElementById("userInput");
        const sendBtn = document.getElementById("sendBtn");
        const autoplayAudio = document.getElementById("autoplayAudio");

        function scrollToBottom() {{
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }}

        function appendMessage(role, text, audioChunks = null) {{
            const div = document.createElement("div");
            div.className = `msg ${{role}}`;
            
            const time = new Date().toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
            let audioBtnHtml = "";
            if (audioChunks && audioChunks.length > 0) {{
                audioBtnHtml = `&middot; <button class="audio-player-btn" onclick="window.__playLastAudio()">🔊 Play voice</button>`;
                window.__lastAudioChunks = audioChunks;
                window.__playLastAudio = () => playChunks(window.__lastAudioChunks);
            }}

            div.innerHTML = `
                <div class="msg-bubble">${{text}}</div>
                <div class="msg-meta">
                    <span>${{role === 'user' ? 'You' : '{agent_name}'}}</span> &middot; <span>${{time}}</span>
                    ${{audioBtnHtml}}
                </div>
            `;
            messagesContainer.insertBefore(div, typingIndicator);
            scrollToBottom();
        }}

        async function handleSend(e) {{
            if (e) e.preventDefault();
            const text = userInput.value.trim();
            if (!text) return;

            appendMessage("user", text);
            userInput.value = "";
            userInput.disabled = true;
            sendBtn.disabled = true;
            typingIndicator.style.display = "flex";
            scrollToBottom();

            if (audioCtx.state === 'suspended') {{
                audioCtx.resume();
            }}

            try {{
                const res = await fetch("/api/chat", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ message: text }})
                }});
                const data = await res.json();
                typingIndicator.style.display = "none";

                if (data.agent_response) {{
                    appendMessage("agent", data.agent_response, data.all_audio_base64);
                    if (autoplayAudio.checked && data.all_audio_base64 && data.all_audio_base64.length > 0) {{
                        playChunks(data.all_audio_base64);
                    }}
                }} else if (data.error) {{
                    appendMessage("agent", "⚠️ Error: " + data.error);
                }}
            }} catch (err) {{
                typingIndicator.style.display = "none";
                appendMessage("agent", "⚠️ Connection error: " + err.message);
            }} finally {{
                userInput.disabled = false;
                sendBtn.disabled = false;
                userInput.focus();
            }}
        }}

        function sendQuick(txt) {{
            userInput.value = txt;
            handleSend();
        }}

        function clearChat() {{
            messagesContainer.querySelectorAll(".msg:not(:first-child)").forEach(el => el.remove());
        }}

        async function runDiagnostics() {{
            const consoleEl = document.getElementById("diagConsole");
            consoleEl.textContent = "Running diagnostics...\n";

            try {{
                const res = await fetch("/api/status");
                const data = await res.json();
                consoleEl.textContent += `[OK] Agent Status: ${{data.status}}\\n`;
                consoleEl.textContent += `[OK] Agent: ${{data.agent_name}} (ID: ${{data.agent_id}})\\n`;
                
                const urlRes = await fetch("/api/signed-url");
                const urlData = await urlRes.json();
                if (urlData.signed_url) {{
                    consoleEl.textContent += `[OK] Signed WebSocket URL verified!\\n`;
                    consoleEl.textContent += `All checks passed! Server is operating normally.`;
                }} else {{
                    consoleEl.textContent += `[ERR] Failed to get signed URL: ${{JSON.stringify(urlData)}}\\n`;
                }}
            }} catch (err) {{
                consoleEl.textContent += `[FAIL] Diagnostic error: ${{err.message}}\\n`;
            }}
        }}
    </script>
</body>
</html>
"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class AgentRequestHandler(SimpleHTTPRequestHandler):
    agent_info_cache: Optional[Dict[str, Any]] = None

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
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
        if self.path == "/" or self.path.startswith("/index"):
            self.serve_dashboard()
        elif self.path == "/api/status":
            try:
                info = self.get_cached_agent_info()
                self._send_json({
                    "status": "online",
                    "agent_id": AGENT_ID,
                    "agent_name": info.get("name", "Unknown"),
                    "voice_id": info.get("conversation_config", {}).get("tts", {}).get("voice_id"),
                    "llm": info.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("llm")
                })
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
        elif self.path == "/api/agent":
            try:
                info = self.get_cached_agent_info()
                self._send_json(info)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif self.path == "/api/signed-url":
            try:
                signed_url = get_signed_url()
                self._send_json({"signed_url": signed_url, "agent_id": AGENT_ID})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif self.path == "/api/history":
            self._send_json({"history": conversation_history})
        elif self.path.endswith(".mp3") or self.path.endswith(".wav"):
            filename = os.path.basename(self.path.split("?")[0])
            filepath = os.path.join(BASE_DIR, filename)
            if os.path.isfile(filepath):
                ctype = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
                with open(filepath, "rb") as af:
                    content = af.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Audio file not found")
        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                user_msg = data.get("message", "").strip()
                if not user_msg:
                    self._send_json({"error": "Empty message provided"}, 400)
                    return

                # Execute async conversation via websockets
                result = asyncio.run(query_agent_ws(user_msg))
                conversation_history.append({
                    "user": user_msg,
                    "agent": result.get("agent_response"),
                    "conversation_id": result.get("conversation_id")
                })
                self._send_json(result)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_error(404, "Endpoint not found")

    def get_cached_agent_info(self) -> Dict[str, Any]:
        if AgentRequestHandler.agent_info_cache is None:
            AgentRequestHandler.agent_info_cache = get_agent_info()
        return AgentRequestHandler.agent_info_cache

    def serve_dashboard(self):
        try:
            info = self.get_cached_agent_info()
            conv_cfg = info.get("conversation_config", {})
            agent_cfg = conv_cfg.get("agent", {})
            prompt_cfg = agent_cfg.get("prompt", {})
            tts_cfg = conv_cfg.get("tts", {})

            agent_name = info.get("name", "ElevenLabs Agent")
            first_message = agent_cfg.get("first_message") or "Hello! How can I help you today?"
            voice_id = tts_cfg.get("voice_id", "Default")
            llm_model = prompt_cfg.get("llm", "Default LLM")

            page = HTML_TEMPLATE.format(
                agent_name=agent_name,
                agent_id=AGENT_ID,
                voice_id=voice_id,
                llm_model=llm_model,
                first_message=first_message
            )
            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            err_html = f"<h1>Failed to load agent</h1><p>{str(e)}</p>"
            data = err_html.encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


def run_server(host: str = "0.0.0.0", port: int = 8080):
    if not API_KEY or not AGENT_ID:
        print("[!] ERROR: Could not find API Key or Agent ID in cred.txt or environment variables.")
        sys.exit(1)

    print("=" * 65)
    print("      ElevenLabs Conversational AI Agent Server")
    print("=" * 65)
    print(f"[*] Agent ID : {AGENT_ID}")
    print(f"[*] API Key  : {API_KEY[:6]}...{API_KEY[-4:]}")

    try:
        info = get_agent_info()
        name = info.get("name", "Unknown")
        print(f"[*] Connected: Found agent '{name}'")
    except Exception as e:
        print(f"[!] Warning: Could not verify agent with API: {e}")

    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, AgentRequestHandler)
    print(f"[*] Server running at http://{host}:{port}/")
    print(f"[*] Web Interface: http://localhost:{port}/")
    print(f"[*] Press Ctrl+C to stop.")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping server...")
        httpd.server_close()
        print("[*] Server stopped gracefully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ElevenLabs ConvAI Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    args = parser.parse_args()

    run_server(args.host, args.port)
