import { PUBLIC_API_BASE_URL } from '$app/env/public';

/**
 * Single source of truth for the API origin the browser talks to.
 *
 * Empty (the default) means "same origin that served this page" — correct when
 * you open the app from the Vite dev server, including from your phone at
 * http://<pc-ip>:5173.
 *
 * Set PUBLIC_API_BASE_URL in .env to point somewhere else, e.g.
 *   PUBLIC_API_BASE_URL=http://x1carbon:5173
 */
export const API_BASE_URL = (PUBLIC_API_BASE_URL ?? '').replace(/\/+$/, '');

/** Build an absolute (or same-origin relative) URL for an `/api/...` path. */
export function apiUrl(path: string): string {
	return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}
