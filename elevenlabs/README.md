# ElevenLabs Conversational AI Server & Test Suite

This directory contains a server and test harness for your **ElevenLabs Conversational AI Agent** (`agentshrek`), configured using the credentials in `cred.txt`.

---

## 📌 Agent Profile (from `cred.txt`)

- **Agent Name**: `agentshrek`
- **Agent ID**: `agent_8901m4gnv2a6f7xb5n0sbgbznz9f`
- **Branch ID**: `agtbrch_6701m4gnv3n3f0ksvc5exh983h9x`
- **LLM Engine**: `qwen35-397b-a17b`
- **Default Voice ID**: `j33FKwn3yd055HQ1DQKY`
- **Greeting**: *"Hey I'm Shrek,What could I do for you today"*
- **Account Tier**: `Creator`

---

## 🚀 Quick Start

### 1. Run Automated Test Suite
To verify credentials, WebSocket connectivity, audio generation, and the local server endpoints:

```bash
python3 test_agent.py --test-server http://localhost:8080
```

All 6 test stages will execute:
1. **Credential Extraction**: Parses `cred.txt` or environment variables.
2. **ElevenLabs Authentication**: Validates API key and user quotas.
3. **Agent Configuration Check**: Fetches LLM model, prompt, and voice settings.
4. **Signed URL Generation**: Tests backend signed URL creation.
5. **Direct WebSocket Conversation**: Exchanges real-time messages and PCM audio with `agentshrek`.
6. **Local Server REST API Verification**: Tests `/api/status`, `/api/signed-url`, and `/api/chat`.

---

### 2. Launch the Web Server

Start the local server on port 8080 (or any custom port):

```bash
python3 server.py --port 8080
```

Then open your browser at:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 🖥️ Web Interface Features

- **🎙️ ElevenLabs Real-Time Voice Widget**: Embedded official `<elevenlabs-convai>` widget allowing you to speak directly into your microphone and hear `agentshrek` reply in real time.
- **💬 Interactive Text & Audio Chat**: Text conversation interface with instant audio playback of synthesized speech (PCM 16kHz rendered via browser Web Audio API).
- **⚡ Quick Action Chips**: Preset prompts to quickly test greeting, capabilities, jokes, and personality.
- **🧪 Live Diagnostics Tool**: In-browser health check button for instant agent status and WebSocket connectivity tests.

---

## 🔌 REST API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Interactive Web Dashboard |
| `/api/status` | `GET` | Health check & agent metadata |
| `/api/agent` | `GET` | Full raw ElevenLabs agent configuration |
| `/api/signed-url` | `GET` | Generates a signed WebSocket URL for safe client connections |
| `/api/chat` | `POST` | Sends a message via WebSocket and returns agent transcript & audio chunks |
| `/api/history` | `GET` | Returns recent chat history |

### Example `POST /api/chat` Request:
```bash
curl -X POST http://localhost:8080/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello Shrek!"}'
```

Response:
```json
{
  "user_message": "Hello Shrek!",
  "agent_response": "Hey I'm Shrek,What could I do for you today",
  "conversation_id": "conv_...",
  "audio_chunks_count": 9,
  "audio_base64": "<base64_pcm>",
  "all_audio_base64": ["..."]
}
```

---

## 🎧 PipeWire Bluetooth Handsfree Permanent Call (with VAD)

Run a continuous, low-latency live telephone call with your ElevenLabs agent directly through your connected Bluetooth handsfree headset (e.g., `HONOR 400 Pro`).

### Features
- **👀 WirePlumber Export Watcher (Default)**: Continuously monitors PipeWire for the Bluetooth handsfree headset. It automatically turns **ON** the ElevenLabs call when the handsfree device opens, and immediately closes the connection when the device turns off or disconnects.
- **🎙️ Direct PipeWire Integration**: Zero-latency capture via `pw-record` and playback via `pw-play` at native 16kHz PCM mono.
- **⚡ WebRTC Voice Activity Detection (VAD)**: Multi-stage speech detection (WebRTC VAD + RMS energy gating + circular pre-roll buffer) ensures speech onset is never clipped and background silence doesn't waste bandwidth.
- **🛑 Instant Barge-In**: Interrupt the agent mid-sentence just by speaking into your headset. Playback cuts off instantly and the agent listens.
- **🔇 Echo Cancellation & Feedback Isolation**: Automatically mutes the default Linux ALSA laptop mic/speaker loopback during the call so you hear only the agent and room noise is not piped into your ear.
- **📞 Permanent Call Loop**: Automatically reconnects if the network or WebSocket session drops while the headset is active.

### Quick Start
To launch the watcher daemon:

```bash
./start_call.sh
```

The script will sit in standby listening for WirePlumber export:
```
╔══════════════════════════════════════════════════════════════════════╗
║     WIREPLUMBER EXPORT WATCHER · BLUETOOTH HANDSFREE DAEMON          ║
╚══════════════════════════════════════════════════════════════════════╝
  Status:  Listening for WirePlumber export of Bluetooth Handsfree...
  Policy:  Turn ON call when handsfree opens | Close connection when closed

[22:24:17] ⏳ Standby: Listening for WirePlumber export of Bluetooth handsfree...
```
As soon as your Bluetooth handsfree opens, the call turns **ON** automatically!

### Options
- `--watch`: Always watch WirePlumber export and auto-connect when handsfree opens (default: enabled).
- `--direct`: Connect immediately to existing nodes, bypassing the watcher loop.
- `--vad-mode {0,1,2,3}`: WebRTC VAD aggressiveness (`0` = relaxed, `3` = strict, default: `2`).
- `--rms-threshold`: Minimum audio RMS energy for speech (default: `220.0`).
- `--hangover-ms`: Silence duration in milliseconds before concluding a speech turn (default: `650ms`).
- `--input-target`: Custom PipeWire input node (auto-detects bluetooth by default).
- `--output-target`: Custom PipeWire output node (auto-detects bluetooth by default).
- `--no-isolate`: Keep default system ALSA-to-Bluetooth routing active.
- `--default-audio`: Route through default system audio sink/source instead of Bluetooth.


