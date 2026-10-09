<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Trash2 from '@lucide/svelte/icons/trash-2';

	function reset() {
		campaign.reset();
	}
</script>

<section class="space-y-4 py-2">
	<div class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Template</h1>
		<p class="text-sm text-muted-foreground">
			Tap record and describe your event. We'll write the script for you.
		</p>
	</div>

	<Card.Root class="py-3">
		<Card.Content>
			<Textarea
				bind:value={campaign.templateText}
				placeholder="Your script will appear here…"
				class="min-h-40 resize-none border-none bg-transparent px-0 text-base leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent"
			/>
		</Card.Content>
	</Card.Root>
</section>

<ActionBar
	primaryLabel="Show template"
	primaryDisabled={!campaign.templateText.trim()}
	onPrimaryAction={() => goto('/preview')}
	actions={[
		{ icon: Trash2, label: 'Reset', onclick: reset },
		{ icon: Mic, label: 'Record more', onclick: () => goto('/record') }
	]}
/>
