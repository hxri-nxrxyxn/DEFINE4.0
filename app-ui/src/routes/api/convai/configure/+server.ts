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

const SET_SCRIPT_TOOL = {
	type: 'client',
	name: 'set_script',
	description:
		'Save the finalized call script so the app can use it for the campaign. Call this every time you have composed or updated the script.',
	parameters: {
		type: 'object',
		properties: {
			script: {
				type: 'string',
				description:
					'The call script to read to recipients, keeping the {name} placeholder where their name goes.'
			}
		},
		required: ['script']
	}
};

// Never let a stray closing line (e.g. a polluted draft) become the greeting.
function sanitizeScript(script: string): string {
	const t = script.trim();
	if (!t) return '';
	const looksLikeFarewell =
		t.length < 120 &&
		/(goodbye|\bbye\b|thank you for your time|thanks for your time|have a (great|good|nice) day)/i.test(t);
	return looksLikeFarewell ? '' : t;
}

function buildCallFirstMessage(script: string): string {
	const base = script.trim();
	if (base) return base.replace(/\{\s*name\s*\}/gi, '{{name}}');
	return 'Hello {{name}}, this is DEFINE Voice AI calling with an important update. Do you have a moment?';
}

function buildCallPrompt(script: string): string {
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

const BUILDER_FIRST_MESSAGE =
	"Hi! What should the call say? For example, 'remind Class 8 parents about tomorrow's meeting'.";

const BUILDER_PROMPT = [
	'You are the DEFINE campaign assistant. The operator will describe, in natural speech and any language, what an outbound call should say or do.',
	'Your only job is to turn their request into ONE short, friendly, spoken call script (1-3 sentences) that a voice agent reads to a recipient.',
	'Keep the placeholder {name} exactly where the recipient name goes.',
	'Do NOT role-play as a recipient, do NOT discuss the operator, and do NOT chat about unrelated things.',
	'Whenever you have composed or updated the script, immediately call the set_script tool with the final script text, then reply with one short line like "Done — ready to place the call."'
].join('\n');

export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json().catch(() => ({}));
	const mode: 'call' | 'build' = body.mode === 'call' ? 'call' : 'build';
	const script: string = sanitizeScript(typeof body.script === 'string' ? body.script : '');
	const name: string = (typeof body.name === 'string' && body.name.trim()) || 'there';
	const language: string = typeof body.language === 'string' ? body.language.trim().toLowerCase() : '';

	const langCode = LANG_CODES[language] ?? (mode === 'build' ? 'en' : 'en');

	const agent =
		mode === 'build'
			? {
					first_message: BUILDER_FIRST_MESSAGE,
					language: langCode,
					dynamic_variables: { dynamic_variable_placeholders: { name } },
					prompt: {
						prompt: BUILDER_PROMPT,
						tools: [SET_SCRIPT_TOOL]
					}
				}
			: {
					first_message: buildCallFirstMessage(script),
					language: langCode,
					dynamic_variables: { dynamic_variable_placeholders: { name } },
					prompt: {
						prompt: buildCallPrompt(script),
						tools: [OUTCOME_TOOL],
						built_in_tools: {
							end_call: { name: 'end_call', description: 'End the call once the outcome is reported.' }
						}
					}
				};

	const payload = { conversation_config: { agent } };

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
			mode,
			first_message: data?.conversation_config?.agent?.first_message ?? agent.first_message,
			language: langCode
		});
	} catch (e: any) {
		return json({ ok: false, error: e?.message ?? 'Failed to configure agent' }, { status: 502 });
	}
};
