import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const FALLBACK_ANALYTICS = {
	kpis: {
		total_calls: 1284,
		connected_calls: 873,
		connect_rate_pct: 68.0,
		confirmed_count: 592,
		confirmation_rate_pct: 46.1,
		voicemail_count: 147,
		retryable_non_responders: 37
	},
	by_language: {
		Hindi: { total: 420, confirmed: 244, connect_rate: 58.1 },
		Tamil: { total: 290, confirmed: 170, connect_rate: 58.6 },
		Telugu: { total: 245, confirmed: 139, connect_rate: 56.7 },
		Marathi: { total: 184, confirmed: 108, connect_rate: 58.7 },
		Malayalam: { total: 145, confirmed: 91, connect_rate: 62.8 }
	},
	by_segment: {
		Patron: { total: 430, confirmed: 280, rescheduled: 45 },
		Alumni: { total: 340, confirmed: 210, rescheduled: 30 },
		VIP: { total: 284, confirmed: 195, rescheduled: 22 },
		Faculty: { total: 230, confirmed: 124, rescheduled: 18 }
	},
	retry_manifest: [
		{ recipient_name: 'Vikram Malhotra', phone: '+91 98••• ••999', disposition: 'NETWORK_BUSY', attempts: 1, action: 'VOICE_RETRY_SCHEDULED', retry_window_mins: 20, channel: 'Voice' },
		{ recipient_name: 'Pooja Hegde', phone: '+91 97••• ••888', disposition: 'NO_ANSWER_TIMEOUT', attempts: 2, action: 'FALLBACK_WHATSAPP_SMS_LINK', retry_window_mins: 0, channel: 'WhatsApp/SMS Link' }
	]
};

export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const res = await fetch('http://127.0.0.1:8000/api/analytics');
		if (res.ok) {
			const data = await res.json();
			if (data.kpis && data.kpis.total_calls > 0) {
				return json(data);
			}
		}
	} catch (e) {
		// API server not reachable or offline; use structured demo stats
	}
	return json(FALLBACK_ANALYTICS);
};
