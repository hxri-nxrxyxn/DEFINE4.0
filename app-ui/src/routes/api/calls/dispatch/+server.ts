import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { CORE_API_URL } from '#lib/server/backend.js';

export const POST: RequestHandler = async ({ request, fetch }) => {
	const body = await request.json().catch(() => ({}));

	try {
		const res = await fetch(`${CORE_API_URL}/api/calls/dispatch`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body),
			signal: AbortSignal.timeout(15000)
		});
		if (res.ok) {
			const data = await res.json();
			return json(data);
		}
		const detail = await res.text().catch(() => '');
		return json(
			{ status: 'error', message: `Core API ${res.status}: ${detail.slice(0, 200)}` },
			{ status: 502 }
		);
	} catch (e: any) {
		// Core platform API not reachable.
		return json(
			{ status: 'error', backend: 'offline', message: e?.message ?? 'Core API unreachable' },
			{ status: 502 }
		);
	}
};
