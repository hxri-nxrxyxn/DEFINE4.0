import { browser } from '$app/env';
import type { Recipient } from '#lib/csv.js';

const STORAGE_KEY = 'campaign-draft';

type PersistedState = {
	userName: string;
	templateText: string;
	tested: boolean;
	csvName: string;
	recipients: Recipient[];
};

const DEFAULTS: PersistedState = {
	userName: 'Hari',
	templateText: '',
	tested: false,
	csvName: '',
	recipients: []
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

	csvUploaded = $derived(this.recipients.length > 0);

	#saveTimer: ReturnType<typeof setTimeout> | undefined;

	constructor() {
		if (!browser) return;

		const saved = read();
		this.userName = saved.userName;
		this.templateText = saved.templateText;
		this.tested = saved.tested;
		this.csvName = saved.csvName;
		this.recipients = saved.recipients;

		$effect.root(() => {
			$effect(() => {
				// Track the fields we persist (cheap reference reads only — the
				// expensive serialization happens later, outside the effect).
				void this.userName;
				void this.templateText;
				void this.tested;
				void this.csvName;
				void this.recipients;
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
				recipients: $state.snapshot(this.recipients)
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
	}

	reset() {
		this.templateText = '';
		this.tested = false;
	}
}

export const campaign = new CampaignStore();
