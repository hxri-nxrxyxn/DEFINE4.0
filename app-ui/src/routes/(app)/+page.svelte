<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import { parseRecipients, type Recipient } from '#lib/csv.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Check from '@lucide/svelte/icons/check';
	import Upload from '@lucide/svelte/icons/upload';
	import Users from '@lucide/svelte/icons/users';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';

	let fileInput: HTMLInputElement;
	let showModal = $state(false);

	let contactRows = $state<Array<{ name: string; phone: string; language: string; segment: string }>>([
		{ name: 'Daison', phone: '9995283835', language: 'Hindi', segment: 'VIP' },
		{ name: 'Rahul', phone: '9876543210', language: 'Tamil', segment: 'Patron' }
	]);

	function addRow() {
		contactRows.push({ name: '', phone: '', language: 'English', segment: 'General' });
	}

	function removeRow(index: number) {
		if (contactRows.length > 1) {
			contactRows.splice(index, 1);
		}
	}

	function saveRoster() {
		const valid = contactRows.filter((r) => r.name.trim() || r.phone.trim());
		if (valid.length === 0) {
			toast.error('Please add at least one recipient name or phone number');
			return;
		}

		const recipients: Recipient[] = valid.map((r) => ({
			name: r.name.trim() || 'Recipient',
			phone: r.phone.trim().startsWith('+') ? r.phone.trim() : `+91 ${r.phone.trim()}`,
			language: r.language || 'Hindi',
			segment: r.segment || 'General'
		}));

		campaign.setRecipients('Test Recipient Roster', recipients);
		toast.success(`${recipients.length} recipients loaded & saved`);
		showModal = false;
	}

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
		toast.success(`${recipients.length} recipients loaded from ${file.name}`);
		input.value = '';
		showModal = false;
	}
</script>

<section class="flex min-h-[62vh] flex-col justify-center gap-6 py-6">
	<div class="space-y-3 text-center">
		<div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold">
			<Users class="size-3.5" />
			<span>Multilingual Voice AI Campaign</span>
		</div>
		<h1 class="text-3xl font-semibold tracking-tight text-balance">
			Hi {campaign.userName}, what should we publish today?
		</h1>
		<p class="text-sm text-muted-foreground">
			{#if campaign.csvUploaded}
				Ready · <span class="font-medium text-foreground">{campaign.csvName}</span> · {campaign.recipients.length} recipients
			{:else}
				Add or upload recipient contacts to start your campaign.
			{/if}
		</p>
	</div>

	<!-- Recipient Summary Badge Card -->
	<div class="mx-auto w-full max-w-sm">
		<button
			type="button"
			onclick={() => (showModal = true)}
			class="w-full p-4 rounded-xl border border-border bg-card hover:bg-accent/50 transition-all text-left space-y-2 shadow-xs"
		>
			<div class="flex items-center justify-between">
				<span class="text-xs font-medium text-muted-foreground uppercase tracking-wider">Recipients Roster</span>
				{#if campaign.csvUploaded}
					<span class="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
						<Check class="size-3.5" /> Ready
					</span>
				{:else}
					<span class="text-xs font-medium text-primary underline">Tap to add</span>
				{/if}
			</div>
			<div class="flex items-center justify-between">
				<p class="text-base font-semibold">
					{campaign.csvUploaded ? `${campaign.recipients.length} Recipients Loaded` : 'No Contacts Selected'}
				</p>
				<span class="text-xs text-muted-foreground">Edit &rarr;</span>
			</div>
		</button>
	</div>
</section>

<input bind:this={fileInput} type="file" accept=".csv,text/csv" class="hidden" onchange={onFile} />

<!-- Recipient Editor Modal -->
{#if showModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in">
		<Card.Root class="w-full max-w-md shadow-lg border-border">
			<Card.Header class="flex flex-row items-center justify-between pb-3">
				<div>
					<Card.Title class="text-base font-semibold">Recipients Contact Roster</Card.Title>
					<Card.Description class="text-xs">Add test contact names and phone numbers.</Card.Description>
				</div>
				<Button variant="ghost" size="icon-sm" onclick={() => (showModal = false)}>
					<X class="size-4" />
				</Button>
			</Card.Header>

			<Card.Content class="space-y-3 pt-2">
				{#each contactRows as row, idx}
					<div class="flex items-center gap-2 p-2.5 rounded-xl border border-border bg-muted/30">
						<div class="flex-1 space-y-1.5">
							<input
								type="text"
								bind:value={row.name}
								placeholder="Recipient Name"
								class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
							/>
						</div>
						<div class="flex-1 space-y-1.5">
							<input
								type="text"
								bind:value={row.phone}
								placeholder="Phone (e.g. 9995283835)"
								class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono"
							/>
						</div>
						{#if contactRows.length > 1}
							<button
								type="button"
								onclick={() => removeRow(idx)}
								class="p-1.5 text-muted-foreground hover:text-destructive transition-colors"
								aria-label="Remove contact"
							>
								<Trash2 class="size-4" />
							</button>
						{/if}
					</div>
				{/each}

				<div class="flex items-center justify-between pt-2">
					<Button variant="outline" size="sm" class="rounded-xl text-xs gap-1" onclick={addRow}>
						<Plus class="size-3.5" /> Add Contact
					</Button>
					<Button variant="ghost" size="sm" class="rounded-xl text-xs gap-1" onclick={() => fileInput.click()}>
						<Upload class="size-3.5" /> Upload CSV File
					</Button>
				</div>
			</Card.Content>

			<Card.Footer class="flex justify-end gap-2 border-t border-border pt-3">
				<Button variant="outline" size="sm" class="rounded-xl" onclick={() => (showModal = false)}>
					Cancel
				</Button>
				<Button variant="default" size="sm" class="rounded-xl px-4" onclick={saveRoster}>
					Save Recipients
				</Button>
			</Card.Footer>
		</Card.Root>
	</div>
{/if}

<ActionBar
	primaryLabel="New campaign"
	onPrimaryAction={() => goto('/template')}
	actions={[
		campaign.csvUploaded
			? {
					icon: Check,
					label: 'Recipients uploaded',
					variant: 'secondary',
					onclick: () => (showModal = true)
				}
			: { icon: Upload, label: 'Upload CSV', onclick: () => (showModal = true) }
	]}
/>
