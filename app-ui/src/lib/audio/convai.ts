import { apiUrl } from '#lib/config.js';

export type ConvAICallbacks = {
	onAgentMessage?: (text: string) => void;
	onUserMessage?: (text: string) => void;
	onAudioPlay?: () => void;
	onAudioEnd?: () => void;
	onOutcome?: (outcome: string) => void;
	onScript?: (script: string) => void;
	onConfirmScript?: (script: string) => void;
	onError?: (err: any) => void;
	onClose?: () => void;
	onLevel?: (level: number) => void;
};

export type ConvAISessionOptions = {
	/** Recipient context injected as ElevenLabs dynamic variables. */
	name?: string;
	city?: string;
	language?: string;
	/** Milliseconds of mutual silence before the call is treated as "no response". */
	silenceTimeoutMs?: number;
	/**
	 * Allow the user to interrupt the agent mid-sentence. Defaults to false
	 * (half-duplex) because speaker echo otherwise triggers false interruptions
	 * that chop the agent's sentences.
	 */
	bargeIn?: boolean;
};

export type ConvAISession = {
	stop: () => void;
	sendText: (text: string) => void;
};

const TARGET_SAMPLE_RATE = 16000;

function bytesToBase64(bytes: Uint8Array): string {
	let binary = '';
	const chunk = 0x8000;
	for (let i = 0; i < bytes.length; i += chunk) {
		binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
	}
	return btoa(binary);
}

function base64ToBytes(base64: string): Uint8Array {
	const binary = atob(base64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes;
}

/** Convert float samples to little-endian PCM16. */
function floatsToPcm16(input: Float32Array): Int16Array {
	const out = new Int16Array(input.length);
	for (let i = 0; i < input.length; i++) {
		const s = Math.max(-1, Math.min(1, input[i]));
		out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
	}
	return out;
}

/** Linear-interpolated downsample fallback for devices that ignore the 16kHz request. */
function downsampleTo16k(input: Float32Array, from: number): Int16Array {
	const ratio = from / TARGET_SAMPLE_RATE;
	const outLen = Math.max(1, Math.round(input.length / ratio));
	const out = new Int16Array(outLen);
	for (let i = 0; i < outLen; i++) {
		const pos = i * ratio;
		const i0 = Math.floor(pos);
		const i1 = Math.min(i0 + 1, input.length - 1);
		const frac = pos - i0;
		const s = input[i0] * (1 - frac) + input[i1] * frac;
		out[i] = Math.max(-1, Math.min(1, s)) * (s < 0 ? 0x8000 : 0x7fff);
	}
	return out;
}

export async function startConvAISession(
	callbacks: ConvAICallbacks,
	options: ConvAISessionOptions = {}
): Promise<ConvAISession> {
	const silenceTimeoutMs = options.silenceTimeoutMs ?? 15000;
	const bargeIn = options.bargeIn ?? false;

	// 1. Get signed URL from backend or bridge
	let signed_url = '';
	const endpoints = [
		'http://x1carbon:8765/api/convai/signed_url',
		'http://10.80.0.48:8765/api/convai/signed_url',
		'http://localhost:8765/api/convai/signed_url',
		apiUrl('/api/convai/signed_url')
	];

	for (const ep of endpoints) {
		try {
			const res = await fetch(ep, { signal: AbortSignal.timeout(2000) });
			if (res.ok) {
				const data = await res.json();
				if (data.signed_url) {
					signed_url = data.signed_url;
					break;
				}
			}
		} catch {
			// try next
		}
	}
	if (!signed_url) {
		throw new Error('Could not obtain ElevenLabs signed URL');
	}

	const AudioContextCtor: typeof AudioContext =
		window.AudioContext || (window as any).webkitAudioContext;

	// 2. Open WebSocket connection directly to ElevenLabs ConvAI Agent
	const socket = new WebSocket(signed_url);

	// --- Microphone capture (sent as 16kHz PCM16 "user_audio_chunk") ---
	let micCtx: AudioContext | null = null;
	let micStream: MediaStream | null = null;
	let processor: ScriptProcessorNode | null = null;
	let muteGain: GainNode | null = null;

	// --- Playback: ElevenLabs streams raw PCM16 @16kHz (not a decodable container) ---
	let playerCtx: AudioContext | null = null;
	let nextPlaybackTime = 0;
	let lastScheduled: AudioBufferSourceNode | null = null;
	let audioEndTimer: ReturnType<typeof setTimeout> | undefined;
	const activeSources = new Set<AudioBufferSourceNode>();
	// True while the agent's audio is playing (plus a short tail). Used to gate
	// the microphone so the agent doesn't hear itself and interrupt.
	let agentSpeaking = false;
	let lastAgentAudioAt = 0;

	// --- Outcome detection ---
	let outcomeReported = false;
	let lastUserAt = Date.now();
	const reportOutcome = (outcome: string) => {
		if (outcomeReported || !outcome) return;
		outcomeReported = true;
		clearInterval(silenceTimer);
		callbacks.onOutcome?.(outcome);
	};

	const getPlayerCtx = () => {
		if (!playerCtx || playerCtx.state === 'closed') {
			playerCtx = new AudioContextCtor();
			nextPlaybackTime = 0;
		}
		return playerCtx;
	};

	const stopPlayback = () => {
		clearTimeout(audioEndTimer);
		for (const source of activeSources) {
			try {
				source.onended = null;
				source.stop();
			} catch {}
		}
		activeSources.clear();
		lastScheduled = null;
		if (playerCtx) nextPlaybackTime = playerCtx.currentTime;
	};

	const enqueuePcm = (bytes: Uint8Array) => {
		const ctx = getPlayerCtx();
		if (ctx.state === 'suspended') void ctx.resume().catch(() => {});
		clearTimeout(audioEndTimer);
		agentSpeaking = true;
		lastAgentAudioAt = Date.now();

		const sampleCount = Math.floor(bytes.byteLength / 2);
		if (sampleCount === 0) return;

		const view = new DataView(bytes.buffer, bytes.byteOffset, sampleCount * 2);
		const buffer = ctx.createBuffer(1, sampleCount, TARGET_SAMPLE_RATE);
		const channel = buffer.getChannelData(0);
		for (let i = 0; i < sampleCount; i++) {
			channel[i] = view.getInt16(i * 2, true) / 0x8000;
		}

		const source = ctx.createBufferSource();
		source.buffer = buffer;
		source.connect(ctx.destination);

		const startAt = Math.max(ctx.currentTime, nextPlaybackTime);
		source.start(startAt);
		nextPlaybackTime = startAt + buffer.duration;

		activeSources.add(source);
		lastScheduled = source;
		source.onended = () => {
			activeSources.delete(source);
			if (source === lastScheduled && activeSources.size === 0) {
				audioEndTimer = setTimeout(() => {
					if (activeSources.size === 0) {
						agentSpeaking = false;
						callbacks.onAudioEnd?.();
					}
				}, 500);
			}
		};
		callbacks.onAudioPlay?.();
	};

	// If neither side speaks for a while and the agent is idle, count it as no response.
	const silenceTimer = setInterval(() => {
		if (outcomeReported) return;
		if (activeSources.size > 0) {
			lastUserAt = Date.now();
			return;
		}
		// Safety: clear the speaking flag if audio was force-stopped.
		if (agentSpeaking && Date.now() - lastAgentAudioAt > 900) agentSpeaking = false;
		if (!agentSpeaking && Date.now() - lastUserAt > silenceTimeoutMs) reportOutcome('no_response');
	}, 1000);

	const dynamicVariables: Record<string, string> = {};
	if (options.name) dynamicVariables.name = options.name;
	if (options.city) dynamicVariables.city = options.city;
	if (options.language) dynamicVariables.language = options.language;

	socket.onopen = async () => {
		// Provide dynamic variables up front (the first message requires them).
		socket.send(
			JSON.stringify({
				type: 'conversation_initiation_client_data',
				dynamic_variables: dynamicVariables
			})
		);

		try {
			micStream = await navigator.mediaDevices.getUserMedia({
				audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
			});

			try {
				micCtx = new AudioContextCtor({ sampleRate: TARGET_SAMPLE_RATE });
			} catch {
				micCtx = new AudioContextCtor();
			}
			if (micCtx.state === 'suspended') await micCtx.resume().catch(() => {});
			const inputRate = micCtx.sampleRate;

			const micSource = micCtx.createMediaStreamSource(micStream);
			processor = micCtx.createScriptProcessor(2048, 1, 1);

			muteGain = micCtx.createGain();
			muteGain.gain.value = 0;
			micSource.connect(processor);
			processor.connect(muteGain);
			muteGain.connect(micCtx.destination);

			processor.onaudioprocess = (evt) => {
				if (socket.readyState !== WebSocket.OPEN) return;

				// Half-duplex: stay silent while the agent talks so speaker echo
				// can't be mistaken for a barge-in (which chops the agent's speech).
				if (!bargeIn && agentSpeaking) {
					callbacks.onLevel?.(0);
					return;
				}

				const input = evt.inputBuffer.getChannelData(0);

				let sum = 0;
				for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
				callbacks.onLevel?.(Math.min(1, Math.sqrt(sum / input.length) * 5));

				const pcm16 =
					inputRate === TARGET_SAMPLE_RATE ? floatsToPcm16(input) : downsampleTo16k(input, inputRate);

				socket.send(
					JSON.stringify({ user_audio_chunk: bytesToBase64(new Uint8Array(pcm16.buffer)) })
				);
			};
		} catch (e) {
			callbacks.onError?.(e);
		}
	};

	socket.onmessage = (evt) => {
		let data: any;
		try {
			data = JSON.parse(evt.data);
		} catch {
			return;
		}

		switch (data.type) {
			case 'agent_response': {
				const text = data.agent_response_event?.agent_response;
				if (text) callbacks.onAgentMessage?.(text);
				break;
			}
			case 'user_transcript': {
				const text =
					data.user_transcription_event?.user_transcript ??
					data.user_transcript_event?.user_transcript;
				if (text) {
					lastUserAt = Date.now();
					callbacks.onUserMessage?.(text);
				}
				break;
			}
			case 'audio': {
				const base64 = data.audio_event?.audio_base_64;
				if (base64) enqueuePcm(base64ToBytes(base64));
				break;
			}
			case 'interruption': {
				stopPlayback();
				break;
			}
			case 'client_tool_call': {
				const tool = data.client_tool_call;
				if (tool?.tool_name === 'report_outcome') {
					reportOutcome(tool.parameters?.outcome ?? '');
				} else if (tool?.tool_name === 'set_script') {
					const script = tool.parameters?.script;
					if (script) callbacks.onScript?.(String(script));
				} else if (tool?.tool_name === 'confirm_script') {
					const script = tool.parameters?.script;
					callbacks.onConfirmScript?.(script ? String(script) : '');
				}
				socket.send(
					JSON.stringify({
						type: 'client_tool_result',
						tool_call_id: tool?.tool_call_id,
						result: 'ok',
						is_error: false
					})
				);
				break;
			}
			case 'ping': {
				socket.send(JSON.stringify({ type: 'pong', event_id: data.ping_event?.event_id }));
				break;
			}
		}
	};

	socket.onerror = (err) => callbacks.onError?.(err);
	socket.onclose = () => {
		clearInterval(silenceTimer);
		callbacks.onClose?.();
	};

	const stop = () => {
		clearInterval(silenceTimer);
		clearTimeout(audioEndTimer);
		stopPlayback();
		try {
			processor?.disconnect();
		} catch {}
		try {
			muteGain?.disconnect();
		} catch {}
		try {
			if (micCtx && micCtx.state !== 'closed') void micCtx.close().catch(() => {});
		} catch {}
		try {
			micStream?.getTracks().forEach((t) => t.stop());
		} catch {}
		try {
			if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
				socket.close();
			}
		} catch {}
	};

	const sendText = (text: string) => {
		if (socket.readyState === WebSocket.OPEN) {
			socket.send(JSON.stringify({ type: 'user_message', text }));
		}
	};

	return { stop, sendText };
}
