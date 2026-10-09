import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const ELEVENLABS_API_KEY = 'sk_d9191a981f7ddca619f2dd4b1787e0cf6fd2e65a3c485e8a';
const ELEVENLABS_AGENT_ID = 'agent_8901m4gnv2a6f7xb5n0sbgbznz9f';

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
		return json({ error: e.message, fallback_agent_id: ELEVENLABS_AGENT_ID }, 500);
	}
};
