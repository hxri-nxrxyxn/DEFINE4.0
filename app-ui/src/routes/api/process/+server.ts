import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ELEVENLABS_API_KEY } from '#lib/server/elevenlabs.js';

const VOICE_ID = '21m00Tcm4TlvDq8ikWAM';

async function synthesize(text: string): Promise<string> {
	try {
		const cleanText = text.replace(/\{\s*name\s*\}/gi, 'there').replace(/\n+/g, ' ').trim();
		if (!cleanText) return '';

		const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}`, {
			method: 'POST',
			headers: {
				'xi-api-key': ELEVENLABS_API_KEY,
				'Content-Type': 'application/json',
				Accept: 'audio/mpeg'
			},
			body: JSON.stringify({
				text: cleanText,
				model_id: 'eleven_multilingual_v2',
				voice_settings: { stability: 0.5, similarity_boost: 0.75 }
			})
		});

		if (!res.ok) return '';
		const arrayBuffer = await res.arrayBuffer();
		return Buffer.from(arrayBuffer).toString('base64');
	} catch (e) {
		console.error('ElevenLabs TTS synthesis error:', e);
		return '';
	}
}

async function transcribe(blob: Blob): Promise<string> {
	try {
		const form = new FormData();
		form.append('file', blob, 'audio.webm');
		form.append('model_id', 'scribe_v1');

		const res = await fetch('https://api.elevenlabs.io/v1/speech-to-text', {
			method: 'POST',
			headers: { 'xi-api-key': ELEVENLABS_API_KEY },
			body: form
		});
		if (!res.ok) return '';
		const data = await res.json();
		return data?.text ?? '';
	} catch (e) {
		console.error('ElevenLabs STT error:', e);
		return '';
	}
}

export const POST: RequestHandler = async ({ request }) => {
	let text = '';
	let audio: Blob | null = null;

	try {
		const contentType = request.headers.get('content-type') || '';
		if (contentType.includes('multipart/form-data')) {
			const form = await request.formData();
			text = String(form.get('text') || '');
			const file = form.get('audio');
			if (file && file instanceof Blob && file.size > 0) audio = file;
		} else {
			const body = await request.json().catch(() => ({}));
			text = body.text || '';
		}
	} catch (e) {
		return json({ status: 'error', text: '', audio_base_64: '' }, { status: 400 });
	}

	const finalText = text.trim() || (audio ? await transcribe(audio) : '');
	const audioBase64 = finalText ? await synthesize(finalText) : '';

	return json({
		status: 'success',
		text: finalText,
		audio_base_64: audioBase64
	});
};
