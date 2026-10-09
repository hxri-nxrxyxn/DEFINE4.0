import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const ELEVENLABS_API_KEY = 'sk_d9191a981f7ddca619f2dd4b1787e0cf6fd2e65a3c485e8a';

function composeScript(baseText: string, spokenText: string): string {
	const body = spokenText.trim() || baseText.trim() || 'We invite you to join our event this weekend. Please let us know if you will be attending.';
	
	// If script already contains formatting, return clean text
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

		// Try ElevenLabs Speech-to-Text API if audio blob is present
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

		const finalTranscript = transcriptText.trim() || baseText.trim() || 'We are organizing an upcoming seminar for all registered participants. We would love to confirm your participation.';
		const finalScript = composeScript(baseText, finalTranscript);

		return json({
			status: 'success',
			text: finalScript,
			transcript: finalTranscript
		});
	} catch (e) {
		return json({
			status: 'fallback',
			text: composeScript(baseText, transcriptText || 'Please confirm your attendance for our upcoming event.'),
			transcript: transcriptText
		});
	}
};
