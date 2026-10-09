<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Phone from '@lucide/svelte/icons/phone';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import { toast } from 'svelte-sonner';

	function testCall() {
		campaign.tested = true;
		toast.success('Test call placed', { description: 'Playing the script to your number (demo).' });
	}

	function startCampaign() {
		toast.success('Campaign started', { description: 'Track outcomes on the dashboard.' });
		goto('/dashboard');
	}
</script>

<section class="flex min-h-[62vh] flex-col gap-5 py-2">
	<div class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Preview</h1>
		<p class="text-sm text-muted-foreground">This is what your recipients will hear.</p>
	</div>

	<div class="flex flex-1 items-center">
		<Card.Root class="w-full">
			<Card.Content class="space-y-4 px-6 pt-4 pb-8">
				<div class="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
					<span class="grid size-7 place-items-center rounded-full bg-primary/10 text-primary">
						<Phone class="size-3.5" />
					</span>
					Call script
				</div>
				<p class="text-2xl font-medium leading-snug tracking-tight text-pretty whitespace-pre-wrap">
					{campaign.templateText || 'Nothing recorded yet.'}
				</p>
			</Card.Content>
		</Card.Root>
	</div>
</section>

<ActionBar
	primaryLabel={campaign.tested ? 'Start campaign' : 'Test call'}
	onPrimaryAction={campaign.tested ? startCampaign : testCall}
	actions={[
		campaign.tested
			? { icon: RotateCcw, label: 'Test again', onclick: () => (campaign.tested = false) }
			: { icon: Phone, label: 'Call', onclick: testCall }
	]}
/>
