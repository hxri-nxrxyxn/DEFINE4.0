import { browser } from '$app/env';
import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
	getDatabase,
	ref,
	set,
	remove,
	push,
	query,
	orderByChild,
	limitToLast,
	onValue,
	type Database
} from 'firebase/database';

const firebaseConfig = {
	apiKey: 'AIzaSyDVdS3eIFytji0bZ61IIa9b3IrxuhMs3y8',
	authDomain: 'define-hack.firebaseapp.com',
	databaseURL: 'https://define-hack-default-rtdb.firebaseio.com',
	projectId: 'define-hack',
	storageBucket: 'define-hack.firebasestorage.app',
	messagingSenderId: '707372249632',
	appId: '1:707372249632:web:89c66178a08cf3f1b8c245'
};

let app: FirebaseApp | null = null;
let db: Database | null = null;

export function getDb(): Database | null {
	if (!browser) return null;
	if (!db) {
		app = initializeApp(firebaseConfig);
		db = getDatabase(app);
	}
	return db;
}

export type RecipientRecord = {
	name: string;
	phone: string;
	language: string;
	segment: string;
};

export type CallRecord = {
	name: string;
	phone: string;
	language: string;
	segment: string;
	disposition: string;
	attempts: number;
	durationSec: number;
	ts: number;
	transcript?: string;
	campaign?: string;
};

const ROOT = 'campaigns';
const path = (cid: string) => `${ROOT}/${cid}`;

export async function publishCampaign(
	cid: string,
	meta: { name: string; script: string; domain?: string; createdAt: number },
	recipients: RecipientRecord[]
): Promise<void> {
	const database = getDb();
	if (!database) return;
	await set(ref(database, `${path(cid)}/meta`), meta);
	const recs: Record<string, RecipientRecord> = {};
	recipients.forEach((r, i) => {
		recs[`r${i}`] = r;
	});
	await set(ref(database, `${path(cid)}/recipients`), recs);
}

export async function publishCall(cid: string, call: CallRecord): Promise<void> {
	const database = getDb();
	if (!database) return;
	const node = push(ref(database, `${path(cid)}/calls`));
	await set(node, call);
}

export function subscribeCalls(cid: string, cb: (calls: CallRecord[]) => void): () => void {	const database = getDb();
	if (!database) {
		cb([]);
		return () => {};
	}
	const q = query(ref(database, `${path(cid)}/calls`), orderByChild('ts'), limitToLast(1000));
	const unsub = onValue(
		q,
		(snap) => {
			const val = snap.val() || {};
			const calls = Object.entries(val).map(([id, c]) => ({ id, ...(c as object) }) as CallRecord & { id: string });
			calls.sort((a, b) => (a.ts ?? 0) - (b.ts ?? 0));
			cb(calls);
		},
		(err) => {
			console.error('[firebase] calls subscription error:', err);
			cb([]);
		}
	);
	return unsub;
}

/** Subscribe to every campaign's calls (aggregated), so the dashboard can show
 *  all seeded/live data and break outcomes down by campaign. */
export function subscribeAllCalls(
	cb: (calls: (CallRecord & { id: string })[]) => void
): () => void {
	const database = getDb();
	if (!database) {
		cb([]);
		return () => {};
	}
	const unsub = onValue(
		ref(database, ROOT),
		(snap) => {
			const val = (snap.val() || {}) as Record<string, any>;
			const out: (CallRecord & { id: string })[] = [];
			for (const [cid, camp] of Object.entries(val)) {
				const calls = camp?.calls || {};
				const metaName = camp?.meta?.name;
				for (const [id, c] of Object.entries<any>(calls)) {
					out.push({ id: `${cid}:${id}`, campaign: c?.campaign || metaName, ...c });
				}
			}
			out.sort((a, b) => (a.ts ?? 0) - (b.ts ?? 0));
			cb(out);
		},
		(err) => {
			console.error('[firebase] all-calls subscription error:', err);
			cb([]);
		}
	);
	return unsub;
}

export async function seedDemo(
	cid: string,
	recipients: RecipientRecord[],
	script: string,
	campaignName: string
): Promise<void> {
	const database = getDb();
	if (!database) return;
	await publishCampaign(cid, { name: campaignName, script, domain: 'events', createdAt: Date.now() }, recipients);

	const dispositions = [
		'confirmed',
		'confirmed',
		'confirmed',
		'declined',
		'not_available',
		'no_response',
		'opt_out',
		'confirmed',
		'not_available',
		'confirmed'
	];
	const calls: Record<string, CallRecord> = {};
	const base = Date.now() - recipients.length * 45000;
	recipients.forEach((r, i) => {
		calls[`seed${i}`] = {
			...r,
			disposition: dispositions[i % dispositions.length],
			attempts: 1 + (i % 2),
			durationSec: 18 + ((i * 7) % 72),
			ts: base + i * 45000,
			campaign: campaignName
		};
	});
	await set(ref(database, `${path(cid)}/calls`), calls);
}

export async function clearCalls(cid: string): Promise<void> {
	const database = getDb();
	if (!database) return;
	await remove(ref(database, `${path(cid)}/calls`));
}

export function newCampaignId(): string {
	return `cmp_${Math.random().toString(36).slice(2, 10)}`;
}
