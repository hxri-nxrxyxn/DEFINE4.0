import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const res = await fetch('http://127.0.0.1:8765/status', { signal: AbortSignal.timeout(1500) });
		if (res.ok) {
			const data = await res.json();
			return json(data);
		}
	} catch {
		// Bridge not running or offline
	}
	return json({ active: false, call_state: 'IDLE', elapsed_seconds: 0 });
};

export const POST: RequestHandler = async ({ request, fetch }) => {
	const body = await request.json().catch(() => ({}));
	const action = body.action || 'call';

	if (action === 'end') {
		try {
			const res = await fetch('http://127.0.0.1:8765/end', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				signal: AbortSignal.timeout(2000)
			});
			if (res.ok) return json(await res.json());
		} catch {
			// fallback
		}
		return json({ status: 'ended' });
	}

	// Trigger call via dialer bridge
	try {
		const res = await fetch('http://127.0.0.1:8765/call', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				phone: body.phone,
				name: body.name,
				duration: body.duration ?? 10
			}),
			signal: AbortSignal.timeout(3000)
		});
		if (res.ok) {
			const data = await res.json();
			return json(data);
		}
	} catch (e) {
		// Bridge server offline fallback
	}

	return json({
		status: 'started',
		phone: body.phone,
		name: body.name,
		target_duration: body.duration ?? 10
	});
};
