import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ELEVENLABS_API_KEY } from '#lib/server/elevenlabs.js';

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
		return (data?.text ?? '').trim();
	} catch (e) {
		console.error('STT error:', e);
		return '';
	}
}

/**
 * Turn a spoken instruction into a short call script.
 * Handles instruction-style phrasing ("send a reminder to parents that ...")
 * and passes through messages that already read like one.
 */
function composeScript(raw: string): string {
	let t = raw.trim().replace(/\s+/g, ' ');
	if (!t) return '';

	// Already phrased as a message.
	if (/^(hello|hi|hey|dear|good (morning|afternoon|evening))\b/i.test(t)) {
		return t.charAt(0).toUpperCase() + t.slice(1);
	}

	// Instruction phrasing: prefer the clause after "that ...".
	const thatIdx = t.toLowerCase().indexOf(' that ');
	if (thatIdx > 0) {
		t = t.slice(thatIdx + 6).trim();
	} else {
		// Strip leading imperative framing ("send a reminder to class 8", etc.).
		t = t.replace(
			/^(please\s+)?(send|tell|ask|call|remind|inform|notify|give)\b[^,]*?(to|for)\b[^,]*?[,]?\s*/i,
			''
		);
		t = t.replace(/^(a\s+)?(reminder|message|note|call)\b[^,]*?[,]?\s*/i, '');
	}

	if (!t) t = raw.trim();
	if (!/[.!?]$/.test(t)) t += '.';
	const body = /^I(\b|')/.test(t) ? t : t.charAt(0).toLowerCase() + t.slice(1);
	return `Hello {name}, ${body}`;
}

export const POST: RequestHandler = async ({ request }) => {
	let transcript = '';

	try {
		const contentType = request.headers.get('content-type') || '';
		if (contentType.includes('multipart/form-data')) {
			const form = await request.formData();
			const file = form.get('audio');
			const provided = String(form.get('text') || '').trim();
			transcript = provided || (file instanceof Blob ? await transcribe(file) : '');
		} else {
			const body = await request.json().catch(() => ({}));
			transcript = String(body.text || '').trim();
		}
	} catch (e) {
		return json({ transcript: '', script: '', error: 'Could not process input' }, { status: 400 });
	}

	if (!transcript) {
		return json({ transcript: '', script: '', error: 'No speech detected' }, { status: 422 });
	}

	return json({ transcript, script: composeScript(transcript) });
};
