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
				enum: ['confirmed', 'declined', 'reschedule', 'not_available', 'opt_out']
			}
		},
		required: ['outcome']
	}
};

const SET_SCRIPT_TOOL = {
	type: 'client',
	name: 'set_script',
	description:
		'Save/update the current call-script draft so the operator can see it. Call this every time you compose or change the script.',
	parameters: {
		type: 'object',
		properties: {
			script: {
				type: 'string',
				description: 'The current full script, keeping the {name} placeholder.'
			}
		},
		required: ['script']
	}
};

const CONFIRM_SCRIPT_TOOL = {
	type: 'client',
	name: 'confirm_script',
	description:
		"Call this once the operator confirms they are happy with the script (e.g. they say 'done', 'fine', 'ok', \"that's good\").",
	parameters: {
		type: 'object',
		properties: {
			script: {
				type: 'string',
				description: 'The final, approved script text.'
			}
		}
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
		'- reschedule: the recipient wants to reschedule or be called again later.',
		'- not_available: the recipient is busy or cannot talk now. Report this immediately (do not interrogate); offer to call back later.',
		'- declined: the recipient says no, is not interested, or will not attend.',
		'- opt_out: the recipient asks to stop being called.',
		'After reporting the outcome, say a short goodbye and end the call.'
	].join('\n');
}

const BUILDER_FIRST_MESSAGE =
	"Hi {{name}}! I'm your RSVP script assistant. Tell me what the call is about and I'll draft the call script for you.";

const BUILDER_PROMPT = [
	'You are the DEFINE script assistant, talking with the campaign operator (the user of this app).',
	'Your job is to help them design the voice-call script for an outbound RSVP campaign.',
	'Compose the script in this standard RSVP format:',
	'"Hello {name}, we are <enquiring about | inviting you to | informing you about> <the event>. <optionally: It will be held on <date> at <time> at <venue>.> Will you be available to attend? Press 1 to confirm, press 2 to reschedule, or press 9 to opt out."',
	"Keep the placeholder {name} exactly where the recipient's name goes.",
	'Whenever you compose or change the script, immediately call the set_script tool with the FULL new script. Do not read the whole script aloud every time — a short spoken confirmation is enough.',
	'If the operator asks for a change, analyse the script you already produced, apply the requested change, and call set_script again with the updated full script.',
	'Ask one short clarifying question only if a key detail is missing (the occasion, date/time, venue, or tone).',
	'Do NOT role-play as a recipient and do NOT discuss unrelated things; you are only drafting the script with the operator.',
	'When the operator confirms they are happy, call the confirm_script tool with the final script.'
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
					language: 'en',
					dynamic_variables: { dynamic_variable_placeholders: { name } },
					prompt: {
						prompt: BUILDER_PROMPT,
						tools: [SET_SCRIPT_TOOL, CONFIRM_SCRIPT_TOOL]
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
