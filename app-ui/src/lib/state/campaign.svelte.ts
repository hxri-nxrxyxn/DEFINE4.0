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
	recipients = $state<Recipient[]>([]);
	/** True while the mock server is processing audio/text. */
	processing = $state(false);

	csvUploaded = $derived(this.recipients.length > 0);

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
				const payload: PersistedState = {
					userName: this.userName,
					templateText: this.templateText,
					tested: this.tested,
					csvName: this.csvName,
					recipients: this.recipients
				};
				try {
					sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
				} catch {
					// storage unavailable (private mode) - ignore
				}
			});
		});
	}

	setRecipients(name: string, recipients: Recipient[]) {
		this.csvName = name;
		this.recipients = recipients;
	}

	reset() {
		this.templateText = '';
		this.tested = false;
	}
}

export const campaign = new CampaignStore();
