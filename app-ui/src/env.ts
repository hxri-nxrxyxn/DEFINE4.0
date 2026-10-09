import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
	ELEVENLABS_API_KEY: {
		description: 'ElevenLabs API key used by server routes to call the ConvAI/TTS APIs.',
		schema: (value) => value ?? ''
	},
	ELEVENLABS_AGENT_ID: {
		description: 'ElevenLabs Conversational AI agent id.',
		schema: (value) => value ?? 'agent_8901m4gnv2a6f7xb5n0sbgbznz9f'
	},
	PUBLIC_API_BASE_URL: {
		public: true,
		description:
			'Origin the browser prefixes onto /api calls. Leave empty to use the same origin that serves the app. Set it (e.g. http://x1carbon:5173) when the UI is hosted separately from the dev server.',
		schema: (value) => value ?? ''
	},
	SERVER_API_URL: {
		description: 'Python core API origin used by the dev proxy routes.',
		schema: (value) => value ?? 'http://127.0.0.1:8000'
	},
	DIALER_BRIDGE_URL: {
		description: 'Local IVR dialer bridge origin used by the calls/bridge proxy route.',
		schema: (value) => value ?? 'http://127.0.0.1:8765'
	}
});
