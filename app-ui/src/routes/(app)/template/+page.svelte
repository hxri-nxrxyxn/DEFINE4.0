<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import { toast } from 'svelte-sonner';

	const templateTips = [
		{
			label: '🎯 Tech Seminar',
			text: 'Hello {name},\n\nWe are hosting an All-India Technology Seminar in Mumbai next Saturday at 10:00 AM. Please confirm your seat.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: '🏥 Clinic Appointment',
			text: 'Hello {name},\n\nThis is a reminder for your upcoming medical consultation at City Health Clinic tomorrow at 3:00 PM.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: '🏫 School PTA Sync',
			text: 'Hello {name},\n\nAnnual Parent-Teacher Association sync is scheduled for this Friday at 4:00 PM in the main school auditorium.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: '💳 Payment Invoice',
			text: 'Hello {name},\n\nYour monthly subscription invoice #INV-2026 is due tomorrow. Please confirm payment dispatch.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: '🎉 Event Update',
			text: 'Hello {name},\n\nImportant update regarding venue change for the Annual Conference. The event is now at Grand Convention Hall.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		}
	];

	function selectTip(text: string, label: string) {
		campaign.templateText = text;
		toast.success(`Loaded ${label} template`);
	}

	function reset() {
		campaign.reset();
		toast.info('Template reset');
	}
</script>

<section class="space-y-4 py-2">
	<div class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Template</h1>
		<p class="text-sm text-muted-foreground">
			Tap record to speak, type your script below, or tap a quick template tag.
		</p>
	</div>

	<Card.Root class="py-3 border-border">
		<Card.Content>
			<Textarea
				bind:value={campaign.templateText}
				placeholder="Your campaign script will appear here… Type, speak, or select a tag below."
				class="min-h-44 resize-none border-none bg-transparent px-0 text-base leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent"
			/>
		</Card.Content>
	</Card.Root>

	<!-- Template Tips & Prompt Tags Section -->
	<div class="space-y-2 pt-1">
		<div class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
			<Sparkles class="size-3.5 text-primary" />
			<span>Quick Template Tips & Tags:</span>
		</div>
		<div class="flex flex-wrap gap-2">
			{#each templateTips as tip (tip.label)}
				<button
					type="button"
					onclick={() => selectTip(tip.text, tip.label)}
					class="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-xl border border-border bg-card hover:bg-accent hover:text-accent-foreground active:scale-95 transition-all shadow-xs"
				>
					{tip.label}
				</button>
			{/each}
		</div>
	</div>
</section>

<ActionBar
	primaryLabel="Show template"
	primaryDisabled={!campaign.templateText.trim()}
	onPrimaryAction={() => goto('/preview')}
	actions={[
		{ icon: Trash2, label: 'Reset', onclick: reset },
		{ icon: Mic, label: 'Record audio', onclick: () => goto('/record') }
	]}
/>
