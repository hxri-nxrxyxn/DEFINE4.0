<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import { parseRecipients, type Recipient } from '#lib/csv.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Upload from '@lucide/svelte/icons/upload';
	import FileSpreadsheet from '@lucide/svelte/icons/file-spreadsheet';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';

	const LANGUAGES = ['Hindi', 'English', 'Tamil', 'Telugu', 'Malayalam', 'Marathi', 'Kannada', 'Bengali'] as const;

	let fileInput: HTMLInputElement;
	let showModal = $state(false);
	let isEditingRoster = $state(false);

	let contactRows = $state<Array<{ name: string; phone: string; language: string }>>([
		{ name: 'Daison', phone: '9995283835', language: 'Hindi' },
		{ name: 'Rahul', phone: '9876543210', language: 'Tamil' }
	]);

	function openModal() {
		// If call chart already uploaded/prepared, show call chart; otherwise show editor
		isEditingRoster = !campaign.csvUploaded;
		showModal = true;
	}

	function addRow() {
		contactRows.push({ name: '', phone: '', language: 'Hindi' });
	}

	function removeRow(index: number) {
		if (contactRows.length > 1) {
			contactRows.splice(index, 1);
		}
	}

	function editManualRoster() {
		if (campaign.recipients.length > 0) {
			contactRows = campaign.recipients.map((r) => ({
				name: r.name,
				phone: r.phone.replace(/^\+91\s*/, ''),
				language: r.language || 'Hindi'
			}));
		}
		isEditingRoster = true;
	}

	function deleteRoster() {
		campaign.clearRecipients();
		contactRows = [
			{ name: 'Daison', phone: '9995283835', language: 'Hindi' },
			{ name: 'Rahul', phone: '9876543210', language: 'Tamil' }
		];
		isEditingRoster = false;
		showModal = false;
		toast.success('Roster deleted');
	}

	function clearAllRows() {
		contactRows = [{ name: '', phone: '', language: 'Hindi' }];
		toast.info('All rows cleared');
	}

	function saveRoster() {
		const valid = contactRows.filter((r) => r.name.trim() || r.phone.trim());
		if (valid.length === 0) {
			toast.error('Please enter at least one contact name or phone number');
			return;
		}

		const recipients: Recipient[] = valid.map((r) => ({
			name: r.name.trim() || 'Recipient',
			phone: r.phone.trim().startsWith('+') ? r.phone.trim() : `+91 ${r.phone.trim()}`,
			language: r.language || 'Hindi',
			segment: 'General'
		}));

		campaign.setRecipients('Contact Roster', recipients);
		toast.success(`${recipients.length} recipients saved`);
		isEditingRoster = false;
		showModal = false;
	}

	async function onFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		const recipients = parseRecipients(await file.text());
		if (recipients.length === 0) {
			toast.error('No recipients found in that CSV file');
			return;
		}

		campaign.setRecipients(file.name, recipients);
		contactRows = recipients.map((r) => ({
			name: r.name,
			phone: r.phone.replace(/^\+91\s*/, ''),
			language: r.language || 'Hindi'
		}));
		toast.success(`${recipients.length} recipients loaded from ${file.name}`);
		input.value = '';
		isEditingRoster = false;
		showModal = false;
	}
</script>

<section class="flex min-h-[62vh] flex-col justify-center gap-6 py-6">
	<div class="space-y-3 text-center">
		<h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight text-balance leading-tight">
			Hi {campaign.userName}, what should we publish today?
		</h1>
		<p class="text-base text-muted-foreground max-w-sm mx-auto">
			Upload recipients or set up your voice campaign script.
		</p>
		{#if campaign.csvUploaded}
			<div class="pt-2 flex justify-center">
				<button
					type="button"
					onclick={openModal}
					class="inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3.5 py-1.5 text-xs font-medium text-foreground shadow-xs transition-colors hover:bg-muted"
				>
					<FileSpreadsheet class="size-3.5 text-primary" />
					<span class="font-semibold">{campaign.csvName}</span>
					<span class="text-muted-foreground">•</span>
					<span class="text-muted-foreground">{campaign.recipients.length} recipients</span>
				</button>
			</div>
		{/if}
	</div>
</section>

<input bind:this={fileInput} type="file" accept=".csv,text/csv" class="hidden" onchange={onFile} />

<!-- Recipient / Call Chart Modal -->
{#if showModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-3 bg-background/80 backdrop-blur-sm animate-in fade-in"
	>
		<Card.Root class="w-full max-w-md shadow-lg border-border py-0 overflow-hidden">
			{#if campaign.csvUploaded && !isEditingRoster}
				<!-- Display Call Chart -->
				<Card.Header class="flex flex-row items-center justify-between pt-4 pb-2 px-4">
					<div class="flex items-center gap-2.5">
						<div class="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
							<FileSpreadsheet class="size-4" />
						</div>
						<div>
							<Card.Title class="text-sm font-semibold leading-none">
								{campaign.csvName || 'Call Chart'}
							</Card.Title>
							<Card.Description class="text-xs mt-1">
								{campaign.recipients.length} recipients in call chart
							</Card.Description>
						</div>
					</div>
					<div class="flex items-center gap-1">
						<Button
							variant="ghost"
							size="icon-sm"
							class="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
							onclick={deleteRoster}
							title="Delete entire roster"
						>
							<Trash2 class="size-4" />
						</Button>
						<Button variant="ghost" size="icon-sm" onclick={() => (showModal = false)}>
							<X class="size-4" />
						</Button>
					</div>
				</Card.Header>

				<Card.Content class="pt-1 px-4 pb-3">
					<div class="rounded-lg border border-border overflow-hidden">
						<div class="max-h-72 overflow-y-auto overflow-x-hidden">
							<table class="w-full table-fixed text-xs">
								<thead class="bg-muted/50 sticky top-0 z-10 border-b border-border">
									<tr class="text-muted-foreground text-left">
										<th class="h-8 px-3 font-medium w-[36%]">Name</th>
										<th class="h-8 px-2 font-medium w-[40%]">Phone</th>
										<th class="h-8 px-3 font-medium text-right w-[24%]">Language</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-border/40">
									{#each campaign.recipients as recipient, i (i)}
										<tr class="hover:bg-muted/30 transition-colors">
											<td class="py-2.5 px-3 font-medium text-foreground truncate" title={recipient.name}>
												{recipient.name}
											</td>
											<td class="py-2.5 px-2 font-mono text-muted-foreground truncate" title={recipient.phone}>
												{recipient.phone}
											</td>
											<td class="py-2.5 px-3 text-right text-muted-foreground truncate" title={recipient.language}>
												{recipient.language || 'Hindi'}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				</Card.Content>

				<Card.Footer class="flex items-center justify-between border-t border-border py-2.5 px-4 bg-muted/10">
					<div class="flex items-center gap-1">
						<Button
							variant="ghost"
							size="sm"
							class="text-xs text-destructive hover:text-destructive hover:bg-destructive/10 h-8 px-2 gap-1.5"
							onclick={deleteRoster}
						>
							<Trash2 class="size-3.5" />
							Delete
						</Button>
						{#if campaign.csvName === 'Contact Roster'}
							<Button
								variant="ghost"
								size="sm"
								class="text-xs text-muted-foreground hover:text-foreground h-8 px-2"
								onclick={editManualRoster}
							>
								Edit
							</Button>
						{/if}
						<Button
							variant="ghost"
							size="sm"
							class="text-xs text-muted-foreground hover:text-foreground h-8 px-2"
							onclick={() => fileInput.click()}
						>
							Replace
						</Button>
					</div>
					<Button variant="default" size="sm" class="rounded-xl px-4 h-8 text-xs" onclick={() => (showModal = false)}>
						Done
					</Button>
				</Card.Footer>
			{:else}
				<!-- Manual Editor / Upload Mode -->
				<Card.Header class="flex flex-row items-center justify-between pt-4 pb-2 px-4">
					<div>
						<Card.Title class="text-sm font-semibold">Contact Recipients</Card.Title>
						<Card.Description class="text-xs">Add target names, phone numbers, and language.</Card.Description>
					</div>
					<Button variant="ghost" size="icon-sm" onclick={() => (showModal = false)}>
						<X class="size-4" />
					</Button>
				</Card.Header>

				<Card.Content class="pt-1 px-4 pb-3 space-y-3">
					<div class="max-h-72 space-y-2.5 overflow-y-auto overflow-x-hidden pr-0.5">
						{#each contactRows as row, idx (idx)}
							<div class="rounded-xl border border-border bg-muted/20 p-2.5 space-y-2">
								<div class="flex items-center gap-2">
									<input
										type="text"
										bind:value={row.name}
										placeholder="Contact name"
										class="h-8 flex-1 px-2.5 text-xs rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
									/>
									{#if contactRows.length > 1}
										<button
											type="button"
											onclick={() => removeRow(idx)}
											class="p-1.5 text-muted-foreground hover:text-destructive transition-colors shrink-0"
											aria-label="Remove contact"
										>
											<Trash2 class="size-3.5" />
										</button>
									{/if}
								</div>

								<div class="flex items-center gap-2">
									<input
										type="text"
										bind:value={row.phone}
										placeholder="Phone (e.g. 9995283835)"
										class="h-8 flex-1 px-2.5 text-xs rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring font-mono"
									/>
									<select
										bind:value={row.language}
										class="h-8 w-28 px-2 text-xs rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring shrink-0"
									>
										{#each LANGUAGES as lang}
											<option value={lang}>{lang}</option>
										{/each}
									</select>
								</div>
							</div>
						{/each}
					</div>

					<div class="flex items-center justify-between pt-1">
						<Button variant="outline" size="sm" class="rounded-xl text-xs gap-1 h-8" onclick={addRow}>
							<Plus class="size-3.5" /> Add Row
						</Button>
						<Button variant="ghost" size="sm" class="rounded-xl text-xs gap-1 h-8" onclick={() => fileInput.click()}>
							<Upload class="size-3.5" /> Upload File
						</Button>
					</div>
				</Card.Content>

				<Card.Footer class="flex items-center justify-between border-t border-border py-2.5 px-4 bg-muted/10">
					<Button
						variant="ghost"
						size="sm"
						class="text-xs text-destructive hover:text-destructive hover:bg-destructive/10 h-8 px-2 gap-1"
						onclick={clearAllRows}
					>
						<Trash2 class="size-3.5" />
						Clear All
					</Button>
					<div class="flex items-center gap-2">
						<Button variant="outline" size="sm" class="rounded-xl h-8 text-xs" onclick={() => (showModal = false)}>
							Cancel
						</Button>
						<Button variant="default" size="sm" class="rounded-xl px-4 h-8 text-xs" onclick={saveRoster}>
							Save Recipients
						</Button>
					</div>
				</Card.Footer>
			{/if}
		</Card.Root>
	</div>
{/if}

<ActionBar
	primaryLabel="New campaign"
	onPrimaryAction={() => goto('/template')}
	actions={[
		campaign.csvUploaded
			? {
					icon: FileSpreadsheet,
					label: campaign.csvName || 'Call Chart',
					variant: 'secondary',
					onclick: openModal
				}
			: {
					icon: Upload,
					label: 'Upload CSV',
					onclick: openModal
				}
	]}
/>

