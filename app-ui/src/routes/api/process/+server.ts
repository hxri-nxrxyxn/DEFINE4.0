import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const DEMO_TRANSCRIPT =
	'We are hosting a Diwali workshop for our patrons this Saturday at 6 PM at the community hall. Please confirm your attendance so we can reserve your seat.';

function compose(base: string, transcript: string): string {
	const opening = base.trim() || 'Hello {name},';
	return [
		opening,
		'',
		transcript,
		'',
		'Press 1 to confirm, press 2 to reschedule, or press 9 to opt out.',
		'This call is processed by AI and may be recorded.'
	].join('\n');
}

export const POST: RequestHandler = async ({ request }) => {
	let text = '';
	let transcript = '';

	if ((request.headers.get('content-type') ?? '').includes('multipart/form-data')) {
		const form = await request.formData();
		text = String(form.get('text') ?? '');
		transcript = String(form.get('transcript') ?? '');
		// The audio blob (form.get('audio')) is where real ASR would run. Ignored by the mock.
	} else {
		const body = (await request.json().catch(() => ({}))) as {
			text?: string;
			transcript?: string;
		};
		text = body.text ?? '';
		transcript = body.transcript ?? '';
	}

	const heard = transcript.trim() || DEMO_TRANSCRIPT;

	// Simulate server-side processing (ASR + template synthesis) latency.
	await new Promise((resolve) => setTimeout(resolve, 450));

	return json({ text: compose(text, heard), transcript: heard });
};
