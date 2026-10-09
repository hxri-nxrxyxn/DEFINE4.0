import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID } from '#lib/server/elevenlabs.js';

async function updateElevenLabsAgent(promptText: string) {
	try {
		await fetch(`https://api.elevenlabs.io/v1/convai/agents/${ELEVENLABS_AGENT_ID}`, {
			method: 'PATCH',
			headers: {
				'xi-api-key': ELEVENLABS_API_KEY,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				conversation_config: {
					agent: {
						first_message: promptText,
						prompt: {
							prompt: `You are an interactive conversational AI call assistant for DEFINE. Campaign context: '${promptText}'. Respond naturally.`
						}
					}
				}
			})
		});
	} catch (e) {
		console.error('ElevenLabs Agent Patch error:', e);
	}
}

async function queryElevenLabsConvAI(promptText: string): Promise<string> {
	try {
		const signedUrlRes = await fetch(
			`https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id=${ELEVENLABS_AGENT_ID}`,
			{
				headers: { 'xi-api-key': ELEVENLABS_API_KEY }
			}
		);
		if (!signedUrlRes.ok) throw new Error('Failed to get signed URL');
		const { signed_url } = await signedUrlRes.json();

		return new Promise((resolve) => {
			const ws = new WebSocket(signed_url);
			const agentTexts: string[] = [];
			let timeoutTimer: any;

			const finish = () => {
				clearTimeout(timeoutTimer);
				try { ws.close(); } catch {}
				resolve(agentTexts.join(' ').trim());
			};

			timeoutTimer = setTimeout(() => {
				finish();
			}, 8000);

			ws.onopen = () => {};
			ws.onmessage = (evt) => {
				try {
					const data = JSON.parse(String(evt.data));
					if (data.type === 'conversation_initiation_metadata') {
						ws.send(
							JSON.stringify({
								type: 'user_transcript',
								user_transcript: promptText
							})
						);
					} else if (data.type === 'agent_response') {
						const text = data.agent_response_event?.agent_response;
						if (text) agentTexts.push(text);
					} else if (data.type === 'ping') {
						const eid = data.ping_event?.event_id;
						ws.send(JSON.stringify({ type: 'pong', event_id: eid }));
						if (agentTexts.length > 0) {
							finish();
						}
					}
				} catch {}
			};
			ws.onerror = () => finish();
			ws.onclose = () => finish();
		});
	} catch (e) {
		console.error('ElevenLabs ConvAI WS error:', e);
		return '';
	}
}

function composeScript(baseText: string, spokenText: string): string {
	const body = spokenText.trim() || baseText.trim();
	if (!body) {
		return 'Hello! This is your ElevenLabs Conversational Voice AI assistant for DEFINE. How can I help you today?';
	}
	return body;
}

async function synthesizeElevenLabsTTS(text: string): Promise<string> {
	try {
		const cleanText = text.replace(/\{name\}/g, 'Daison').replace(/\n+/g, ' ');
		const res = await fetch('https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM', {
			method: 'POST',
			headers: {
				'xi-api-key': ELEVENLABS_API_KEY,
				'Content-Type': 'application/json',
				'Accept': 'audio/mpeg'
			},
			body: JSON.stringify({
				text: cleanText,
				model_id: 'eleven_multilingual_v2',
				voice_settings: {
					stability: 0.5,
					similarity_boost: 0.75
				}
			})
		});
		if (res.ok) {
			const arrayBuffer = await res.arrayBuffer();
			const buffer = Buffer.from(arrayBuffer);
			return buffer.toString('base64');
		}
	} catch (e) {
		console.error('ElevenLabs TTS synthesis error:', e);
	}
	return '';
}

function generateDynamicScript(userPrompt: string): string {
	const clean = userPrompt.trim();
	if (!clean) {
		return 'Hello {name}, this is an outbound call from DEFINE Voice AI to confirm your upcoming event participation.';
	}
	if (clean.toLowerCase().startsWith('hello ') || clean.includes('confirm your')) {
		return clean;
	}
	return `Hello {name}, this is an important call regarding ${clean}. We would love to confirm your participation. Please let us know if you can attend.`;
}

export const POST: RequestHandler = async ({ request }) => {
	let baseText = '';
	let transcriptText = '';
	let audioBlob: Blob | null = null;

	try {
		const contentType = request.headers.get('content-type') || '';

		if (contentType.includes('multipart/form-data')) {
			const form = await request.formData();
			baseText = String(form.get('text') || '');
			transcriptText = String(form.get('transcript') || '');
			const file = form.get('audio');
			if (file && file instanceof Blob && file.size > 0) {
				audioBlob = file;
			}
		} else {
			const body = await request.json().catch(() => ({}));
			baseText = body.text || '';
			transcriptText = body.transcript || '';
		}

		// 1. STT via ElevenLabs Speech-to-Text if audio present and no transcript
		if (audioBlob && !transcriptText) {
			try {
				const elevenLabsForm = new FormData();
				elevenLabsForm.append('file', audioBlob, 'audio.webm');
				elevenLabsForm.append('model_id', 'scribe_v1');

				const elevenRes = await fetch('https://api.elevenlabs.io/v1/speech-to-text', {
					method: 'POST',
					headers: {
						'xi-api-key': ELEVENLABS_API_KEY
					},
					body: elevenLabsForm
				});

				if (elevenRes.ok) {
					const elevenData = await elevenRes.json();
					if (elevenData.text) {
						transcriptText = elevenData.text;
					}
				}
			} catch (e) {
				console.error('ElevenLabs STT error:', e);
			}
		}

		const promptInput = transcriptText.trim() || baseText.trim() || 'Organize a tech seminar invitation campaign.';

		// 2. Generate dynamic script from exact user prompt
		const dynamicScript = generateDynamicScript(promptInput);

		// 3. Connect to ElevenLabs Conversational AI Agent via WebSocket to query agent
		const agentResponse = await queryElevenLabsConvAI(promptInput);
		const finalScript = agentResponse && agentResponse.length > 10 ? agentResponse : dynamicScript;

		// 4. Update ElevenLabs Conversational Agent config (first_message & prompt)
		await updateElevenLabsAgent(finalScript);

		// 5. Synthesize fresh ElevenLabs audio MP3 as base64 for instant browser audio playback
		const audioBase64 = await synthesizeElevenLabsTTS(finalScript);

		return json({
			status: 'success',
			text: finalScript,
			transcript: finalScript,
			agent_response: agentResponse,
			audio_base_64: audioBase64
		});
	} catch (e) {
		const fallbackScript = generateDynamicScript(transcriptText || baseText);
		const fallbackAudio = await synthesizeElevenLabsTTS(fallbackScript);
		return json({
			status: 'fallback',
			text: fallbackScript,
			transcript: transcriptText,
			audio_base_64: fallbackAudio
		});
	}
};
