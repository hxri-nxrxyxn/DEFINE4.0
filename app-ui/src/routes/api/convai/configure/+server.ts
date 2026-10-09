import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID } from '#lib/server/elevenlabs.js';

const LANG_CODES: Record<string, string> = {
	english: 'en',
	hindi: 'hi',
	tamil: 'ta',
	telugu: 'te',
	malayalam: 'ml',
	marathi: 'mr',
	kannada: 'kn',
	bengali: 'bn'
};

const OUTCOME_TOOL = {
	type: 'client',
	name: 'report_outcome',
	description:
		'Report the final outcome of the outbound call exactly once, as soon as the outcome is clear.',
	parameters: {
		type: 'object',
		properties: {
			outcome: {
				type: 'string',
				description: 'The final outcome of the call.',
				enum: ['confirmed', 'declined', 'not_available', 'opt_out']
			}
		},
		required: ['outcome']
	}
};

function buildFirstMessage(script: string): string {
	const base = script.trim();
	if (base) return base.replace(/\{\s*name\s*\}/gi, '{{name}}');
	return 'Hello {{name}}, this is DEFINE Voice AI calling with an important update. Do you have a moment?';
}

function buildPrompt(script: string): string {
	const context = script.trim()
		? `Deliver this campaign message naturally in the recipient's own language: "${script.trim()}"`
		: 'Deliver your campaign message naturally in the recipient\'s own language.';

	return [
		'You are a polite, natural outbound voice agent for DEFINE.',
		`The recipient's name is {{name}}. Greet them warmly by name.`,
		context,
		'Answer their questions and keep the conversation natural and brief.',
		'As soon as the outcome is clear, call the report_outcome tool exactly once:',
		'- confirmed: the recipient agreed, confirmed, or will attend.',
		'- not_available: the recipient is busy or cannot talk now. Report this immediately (do not interrogate); offer to call back later.',
		'- declined: the recipient says no, is not interested, or will not attend.',
		'- opt_out: the recipient asks to stop being called.',
		'After reporting the outcome, say a short goodbye and end the call.'
	].join('\n');
}

export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json().catch(() => ({}));
	const script: string = typeof body.script === 'string' ? body.script : '';
	const name: string = (typeof body.name === 'string' && body.name.trim()) || 'there';
	const language: string = typeof body.language === 'string' ? body.language.trim().toLowerCase() : '';

	const langCode = LANG_CODES[language] ?? 'en';

	const payload = {
		conversation_config: {
			agent: {
				first_message: buildFirstMessage(script),
				language: langCode,
				dynamic_variables: {
					dynamic_variable_placeholders: { name }
				},
				prompt: {
					prompt: buildPrompt(script),
					tools: [OUTCOME_TOOL],
					built_in_tools: {
						end_call: { name: 'end_call', description: 'End the call once the outcome is reported.' }
					}
				}
			}
		}
	};

	try {
		const res = await fetch(`https://api.elevenlabs.io/v1/convai/agents/${ELEVENLABS_AGENT_ID}`, {
			method: 'PATCH',
			headers: {
				'xi-api-key': ELEVENLABS_API_KEY,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(payload)
		});

		if (!res.ok) {
			const detail = await res.text().catch(() => '');
			return json(
				{ ok: false, error: `ElevenLabs ${res.status}: ${detail.slice(0, 300)}` },
				{ status: 502 }
			);
		}

		const data = await res.json().catch(() => ({}));
		return json({
			ok: true,
			first_message: data?.conversation_config?.agent?.first_message ?? payload.conversation_config.agent.first_message,
			language: langCode
		});
	} catch (e: any) {
		return json({ ok: false, error: e?.message ?? 'Failed to configure agent' }, { status: 502 });
	}
};
