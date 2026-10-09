import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const ELEVENLABS_API_KEY = 'sk_d9191a981f7ddca619f2dd4b1787e0cf6fd2e65a3c485e8a';
const ELEVENLABS_AGENT_ID = 'agent_8901m4gnv2a6f7xb5n0sbgbznz9f';

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
	const body = spokenText.trim() || baseText.trim() || 'We invite you to join our event this weekend. Please let us know if you will be attending.';
	if (body.includes('Press 1')) {
		return body;
	}
	return [
		'Hello {name},',
		'',
		body,
		'',
		'Press 1 to confirm, press 2 to reschedule, or press 9 to opt out.',
		'This call is processed by DEFINE Voice AI.'
	].join('\n');
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

		// 2. Connect to ElevenLabs Conversational AI Agent via WebSocket to generate agent response
		const agentResponse = await queryElevenLabsConvAI(promptInput);
		const finalTranscript = agentResponse || promptInput;

		// 3. Update ElevenLabs Conversational Agent config (first_message & prompt)
		await updateElevenLabsAgent(finalTranscript);

		const finalScript = composeScript(baseText, finalTranscript);

		// 4. Synthesize ElevenLabs audio MP3 as base64 for instant browser audio playback
		const audioBase64 = await synthesizeElevenLabsTTS(finalScript);

		return json({
			status: 'success',
			text: finalScript,
			transcript: finalTranscript,
			agent_response: agentResponse,
			audio_base_64: audioBase64
		});
	} catch (e) {
		const fallbackScript = composeScript(baseText, transcriptText || 'Please confirm your attendance for our upcoming event.');
		const fallbackAudio = await synthesizeElevenLabsTTS(fallbackScript);
		return json({
			status: 'fallback',
			text: fallbackScript,
			transcript: transcriptText,
			audio_base_64: fallbackAudio
		});
	}
};
