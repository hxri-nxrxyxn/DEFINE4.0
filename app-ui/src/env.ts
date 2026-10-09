import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
	ELEVENLABS_API_KEY: {
		description: 'ElevenLabs API key used by server routes to call the ConvAI/TTS APIs.',
		schema: (value) => value ?? ''
	},
	ELEVENLABS_AGENT_ID: {
		description: 'ElevenLabs Conversational AI agent id.',
		schema: (value) => value ?? 'agent_8901m4gnv2a6f7xb5n0sbgbznz9f'
	}
});
