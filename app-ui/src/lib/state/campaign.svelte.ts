import { browser } from '$app/env';
import type { Recipient } from '#lib/csv.js';

const STORAGE_KEY = 'campaign-draft';

export interface CallLogItem {
	phone: string;
	name: string;
	language: string;
	status: 'pending' | 'dialing' | 'connected' | 'completed' | 'failed';
	durationSeconds: number;
	callScriptText?: string;
	timestamp: number;
}

export type OutcomeDisposition =
	| 'confirmed'
	| 'declined'
	| 'not_available'
	| 'opt_out'
	| 'no_response';

export type CallOutcome = {
	disposition: OutcomeDisposition;
	attempts: number;
	at: number;
	transcript?: string;
};

type PersistedState = {
	userName: string;
	templateText: string;
	tested: boolean;
	csvName: string;
	recipients: Recipient[];
	outcomes: Record<string, CallOutcome>;
	activePhone: string;
};

const DEFAULTS: PersistedState = {
	userName: 'Hari',
	templateText: '',
	tested: false,
	csvName: '',
	recipients: [],
	outcomes: {},
	activePhone: ''
};

function read(): PersistedState {
	if (!browser) return { ...DEFAULTS };
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<PersistedState>) } : { ...DEFAULTS };
	} catch {
		return { ...DEFAULTS };
	}
}

class CampaignStore {
	userName = $state(DEFAULTS.userName);
	templateText = $state(DEFAULTS.templateText);
	tested = $state(DEFAULTS.tested);
	csvName = $state(DEFAULTS.csvName);
	// The roster is only ever replaced wholesale, so `$state.raw` avoids the
	// cost of deeply proxying large CSV imports.
	recipients = $state.raw<Recipient[]>([]);

	// IVR Auto-Dialer Roster Campaign Execution State
	isCampaignRunning = $state(false);
	currentCallIndex = $state(0);
	currentCallPhone = $state('');
	currentCallName = $state('');
	currentCallStatus = $state<'idle' | 'dialing' | 'connected' | 'completed' | 'stopped'>('idle');
	currentCallDurationSec = $state(0);
	targetCallDurationSec = $state(10);
	callLogs = $state<CallLogItem[]>([]);

	/** Per-recipient call outcomes, keyed by phone number. */
	outcomes = $state<Record<string, CallOutcome>>({});
	/** Phone of the recipient currently being called. */
	activePhone = $state('');

	csvUploaded = $derived(this.recipients.length > 0);

	activeRecipient = $derived(
		this.recipients.find((r) => r.phone === this.activePhone) ?? this.recipients[0] ?? null
	);

	/** Recipients that need another attempt (no answer / not available). */
	retryList = $derived(
		this.recipients.filter((r) => {
			const d = this.outcomes[r.phone]?.disposition;
			return d === 'no_response' || d === 'not_available';
		})
	);

	summary = $derived.by(() => {
		const counts: Record<OutcomeDisposition | 'pending', number> = {
			confirmed: 0,
			declined: 0,
			not_available: 0,
			opt_out: 0,
			no_response: 0,
			pending: 0
		};
		for (const r of this.recipients) {
			const o = this.outcomes[r.phone];
			if (o) counts[o.disposition] += 1;
			else counts.pending += 1;
		}
		return counts;
	});

	#saveTimer: ReturnType<typeof setTimeout> | undefined;

	constructor() {
		if (!browser) return;

		const saved = read();
		this.userName = saved.userName;
		this.templateText = saved.templateText;
		this.tested = saved.tested;
		this.csvName = saved.csvName;
		this.recipients = saved.recipients;
		this.outcomes = saved.outcomes ?? {};
		this.activePhone = saved.activePhone ?? '';

		$effect.root(() => {
			$effect(() => {
				// Track the fields we persist (cheap reference reads only — the
				// expensive serialization happens later, outside the effect).
				void this.userName;
				void this.templateText;
				void this.tested;
				void this.csvName;
				void this.recipients;
				void this.outcomes;
				void this.activePhone;
				this.#scheduleSave();
			});
		});
	}

	#scheduleSave() {
		clearTimeout(this.#saveTimer);
		this.#saveTimer = setTimeout(() => {
			const payload: PersistedState = {
				userName: this.userName,
				templateText: this.templateText,
				tested: this.tested,
				csvName: this.csvName,
				recipients: $state.snapshot(this.recipients),
				outcomes: $state.snapshot(this.outcomes),
				activePhone: this.activePhone
			};
			try {
				sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
			} catch {
				// storage unavailable (private mode) - ignore
			}
		}, 250);
	}

	setRecipients(name: string, recipients: Recipient[]) {
		this.csvName = name;
		this.recipients = recipients;
	}

	clearRecipients() {
		this.csvName = '';
		this.recipients = [];
		this.outcomes = {};
		this.activePhone = '';
	}

	setActiveRecipient(phone: string) {
		this.activePhone = phone;
	}

	recordOutcome(phone: string, disposition: OutcomeDisposition, transcript?: string) {
		const prev = this.outcomes[phone];
		this.outcomes = {
			...this.outcomes,
			[phone]: {
				disposition,
				attempts: (prev?.attempts ?? 0) + 1,
				at: Date.now(),
				transcript
			}
		};
	}

	reset() {
		this.templateText = '';
		this.tested = false;
		this.isCampaignRunning = false;
		this.currentCallIndex = 0;
		this.currentCallStatus = 'idle';
	}

	stopCampaign() {
		this.isCampaignRunning = false;
		this.currentCallStatus = 'stopped';
	}
}

export const campaign = new CampaignStore();
