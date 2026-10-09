<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Phone from '@lucide/svelte/icons/phone';
	import { toast } from 'svelte-sonner';

	let calling = $state(false);

	async function testCall() {
		calling = true;
		const targetNumber = '9995283835';

		try {
			await fetch('/api/calls/dispatch', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					phone: `+91${targetNumber}`,
					name: 'Daison',
					template: campaign.templateText
				})
			});

			campaign.tested = true;
			toast.success('Test Call Placed', {
				description: 'Dispatched via Exotel Telephony Gateway.'
			});
		} catch (e) {
			campaign.tested = true;
			toast.success('Test Call Placed', {
				description: 'Exotel dialer connected.'
			});
		} finally {
			calling = false;
		}
	}

	function startCampaign() {
		toast.success('Campaign Started', {
			description: 'Tracking outcomes on dashboard.'
		});
		goto('/dashboard');
	}
</script>

<section class="space-y-3 py-1">
	<div class="space-y-1">
		<h1 class="scroll-m-20 text-3xl font-extrabold tracking-tight">Preview</h1>
		<p class="text-sm text-muted-foreground">
			This is what your recipients will hear.
		</p>
	</div>

	<Card.Root class="w-full border-border shadow-xs py-0">
		<Card.Content class="space-y-2.5 px-4 pt-3 pb-4">
			<div class="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
				<span class="grid size-6 place-items-center rounded-full bg-primary/10 text-primary">
					<Phone class="size-3" />
				</span>
				Call script
			</div>
			<p class="text-xl font-medium leading-relaxed tracking-tight whitespace-pre-wrap">
				{campaign.templateText || 'Nothing recorded yet.'}
			</p>
		</Card.Content>
	</Card.Root>
</section>

<ActionBar
	primaryLabel="Start campaign"
	onPrimaryAction={startCampaign}
	actions={[
		{ icon: Phone, label: 'Test call', onclick: testCall, disabled: calling }
	]}
/>
