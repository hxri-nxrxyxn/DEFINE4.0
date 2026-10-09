import { SERVER_API_URL, DIALER_BRIDGE_URL } from '$app/env/private';

function trim(url: string): string {
	return (url || '').replace(/\/+$/, '');
}

/** Python core platform API (Exotel dispatch, analytics, retry, governance). */
export const CORE_API_URL = trim(SERVER_API_URL);

/** Local IVR dialer bridge daemon. */
export const BRIDGE_URL = trim(DIALER_BRIDGE_URL);
