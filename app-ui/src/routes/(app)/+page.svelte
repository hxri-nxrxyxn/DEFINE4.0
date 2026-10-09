<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import { parseRecipients } from '#lib/csv.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Check from '@lucide/svelte/icons/check';
	import Upload from '@lucide/svelte/icons/upload';
	import { toast } from 'svelte-sonner';

	let fileInput: HTMLInputElement;

	async function onFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		const recipients = parseRecipients(await file.text());
		if (recipients.length === 0) {
			toast.error('No recipients found in that CSV');
			return;
		}

		campaign.setRecipients(file.name, recipients);
		toast.success(`${recipients.length} recipients loaded`);
		input.value = '';
	}
</script>

<section class="flex min-h-[62vh] flex-col justify-center gap-6 py-6">
	<div class="space-y-2 text-center">
		<h1 class="text-3xl font-semibold tracking-tight text-balance">
			Hi {campaign.userName}, what should we publish today?
		</h1>
		<p class="text-sm text-muted-foreground">
			{#if campaign.csvUploaded}
				Ready · {campaign.csvName} · {campaign.recipients.length} recipients
			{:else}
				Upload a CSV of recipients to get started.
			{/if}
		</p>
	</div>
</section>

<input bind:this={fileInput} type="file" accept=".csv,text/csv" class="hidden" onchange={onFile} />

<ActionBar
	primaryLabel="New campaign"
	onPrimaryAction={() => goto('/template')}
	actions={[
		campaign.csvUploaded
			? {
					icon: Check,
					label: 'Recipients uploaded',
					variant: 'secondary',
					onclick: () => fileInput.click()
				}
			: { icon: Upload, label: 'Upload CSV', onclick: () => fileInput.click() }
	]}
/>
