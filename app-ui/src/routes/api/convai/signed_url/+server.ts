import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID } from '#lib/server/elevenlabs.js';

export const GET: RequestHandler = async () => {
	try {
		const res = await fetch(
			`https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id=${ELEVENLABS_AGENT_ID}`,
			{
				headers: {
					'xi-api-key': ELEVENLABS_API_KEY
				}
			}
		);
		if (!res.ok) {
			throw new Error(`ElevenLabs API error: ${res.statusText}`);
		}
		const data = await res.json();
		return json(data);
	} catch (e: any) {
		return json({ error: e.message, fallback_agent_id: ELEVENLABS_AGENT_ID }, { status: 500 });
	}
};
