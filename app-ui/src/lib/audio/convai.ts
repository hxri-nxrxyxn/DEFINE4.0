export type ConvAICallbacks = {
	onAgentMessage?: (text: string) => void;
	onUserMessage?: (text: string) => void;
	onAudioPlay?: () => void;
	onError?: (err: any) => void;
	onClose?: () => void;
	onLevel?: (level: number) => void;
};

export type ConvAISession = {
	stop: () => void;
	sendText: (text: string) => void;
};

export async function startConvAISession(callbacks: ConvAICallbacks): Promise<ConvAISession> {
	// 1. Get signed URL from backend
	const res = await fetch('/api/convai/signed_url');
	const { signed_url } = await res.json();
	if (!signed_url) {
		throw new Error('Could not obtain ElevenLabs signed URL');
	}

	// 2. Open WebSocket connection directly to ElevenLabs ConvAI Agent
	const socket = new WebSocket(signed_url);
	let audioCtx: AudioContext | null = null;
	let micStream: MediaStream | null = null;
	let processor: ScriptProcessorNode | null = null;
	let audioQueue: Uint8Array[] = [];
	let isPlaying = false;

	const audioPlayerCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });

	const playNextChunk = async () => {
		if (audioQueue.length === 0) {
			isPlaying = false;
			return;
		}
		isPlaying = true;
		const chunk = audioQueue.shift()!;
		try {
			const decoded = await audioPlayerCtx.decodeAudioData(chunk.buffer.slice(0));
			const source = audioPlayerCtx.createBufferSource();
			source.buffer = decoded;
			source.connect(audioPlayerCtx.destination);
			source.onended = () => playNextChunk();
			source.start();
			callbacks.onAudioPlay?.();
		} catch (e) {
			playNextChunk();
		}
	};

	socket.onopen = async () => {
		try {
			micStream = await navigator.mediaDevices.getUserMedia({
				audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
			});
			audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
			const micSource = audioCtx.createMediaStreamSource(micStream);
			processor = audioCtx.createScriptProcessor(2048, 1, 1);

			micSource.connect(processor);
			processor.connect(audioCtx.destination);

			processor.onaudioprocess = (evt) => {
				if (socket.readyState !== WebSocket.OPEN) return;
				const inputData = evt.inputBuffer.getChannelData(0);

				let sum = 0;
				for (let i = 0; i < inputData.length; i++) {
					sum += inputData[i] * inputData[i];
				}
				const rms = Math.sqrt(sum / inputData.length);
				callbacks.onLevel?.(Math.min(1, rms * 5));

				const pcm16 = new Int16Array(inputData.length);
				for (let i = 0; i < inputData.length; i++) {
					const s = Math.max(-1, Math.min(1, inputData[i]));
					pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
				}
				const u8 = new Uint8Array(pcm16.buffer);
				let binary = '';
				for (let i = 0; i < u8.length; i++) {
					binary += String.fromCharCode(u8[i]);
				}
				const base64Audio = btoa(binary);

				socket.send(
					JSON.stringify({
						user_audio_chunk: base64Audio
					})
				);
			};
		} catch (e) {
			callbacks.onError?.(e);
		}
	};

	socket.onmessage = (evt) => {
		try {
			const data = JSON.parse(evt.data);
			if (data.type === 'agent_response') {
				const text = data.agent_response_event?.agent_response;
				if (text) callbacks.onAgentMessage?.(text);
			} else if (data.type === 'user_transcript') {
				const text = data.user_transcript_event?.user_transcript;
				if (text) callbacks.onUserMessage?.(text);
			} else if (data.type === 'audio') {
				const base64 = data.audio_event?.audio_base_64;
				if (base64) {
					const binaryStr = atob(base64);
					const len = binaryStr.length;
					const bytes = new Uint8Array(len);
					for (let i = 0; i < len; i++) {
						bytes[i] = binaryStr.charCodeAt(i);
					}
					audioQueue.push(bytes);
					if (!isPlaying) playNextChunk();
				}
			} else if (data.type === 'ping') {
				const eid = data.ping_event?.event_id;
				socket.send(JSON.stringify({ type: 'pong', event_id: eid }));
			}
		} catch (e) {}
	};

	socket.onerror = (err) => callbacks.onError?.(err);
	socket.onclose = () => callbacks.onClose?.();

	const stop = () => {
		try {
			processor?.disconnect();
		} catch {}
		try {
			if (audioCtx && audioCtx.state !== 'closed') {
				void audioCtx.close().catch(() => {});
			}
		} catch {}
		try {
			if (audioPlayerCtx && audioPlayerCtx.state !== 'closed') {
				void audioPlayerCtx.close().catch(() => {});
			}
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
			socket.send(JSON.stringify({ type: 'user_transcript', user_transcript: text }));
		}
	};

	return { stop, sendText };
}
