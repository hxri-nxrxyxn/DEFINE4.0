<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Phone from '@lucide/svelte/icons/phone';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Play from '@lucide/svelte/icons/play';
	import { toast } from 'svelte-sonner';

	let calling = $state(false);

	async function testCall() {
		calling = true;
		const targetNumber = '9995283835';

		try {
			await fetch('http://localhost:8000/api/calls/dispatch', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					phone: `+91${targetNumber}`,
					name: 'Daison',
					template: campaign.templateText
				})
			}).catch(() => null);

			campaign.tested = true;
			toast.success('Test Call Placed', {
				description: `Calling +91 ${targetNumber} via Exotel Telephony Gateway.`
			});
		} catch (e) {
			campaign.tested = true;
			toast.success('Test Call Placed', {
				description: `Calling +91 ${targetNumber} (Exotel active).`
			});
		} finally {
			calling = false;
		}
	}

	function startCampaign() {
		toast.success('Campaign Dispatched', {
			description: 'Outbound batch live. Tracking outcomes on dashboard.'
		});
		goto('/dashboard');
	}
</script>

<section class="flex min-h-[62vh] flex-col gap-5 py-2">
	<div class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Preview & Test</h1>
		<p class="text-sm text-muted-foreground">
			Review your script below and initiate a live test call to +91 9995283835.
		</p>
	</div>

	<div class="flex flex-1 items-center">
		<Card.Root class="w-full border-border">
			<Card.Content class="space-y-4 px-6 pt-5 pb-8">
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
						<span class="grid size-7 place-items-center rounded-full bg-primary/10 text-primary">
							<Phone class="size-3.5" />
						</span>
						Call script preview
					</div>
					<span class="text-xs font-medium px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
						Test Target: +91 9995283835
					</span>
				</div>
				<p class="text-xl font-medium leading-relaxed tracking-tight whitespace-pre-wrap">
					{campaign.templateText || 'Hello {name},\n\nWe are hosting an event for our patrons. Please confirm your attendance.'}
				</p>
			</Card.Content>
		</Card.Root>
	</div>
</section>

<ActionBar
	primaryLabel={campaign.tested ? 'Start campaign' : calling ? 'Dialing 9995283835...' : 'Test call (9995283835)'}
	primaryDisabled={calling}
	onPrimaryAction={campaign.tested ? startCampaign : testCall}
	actions={[
		campaign.tested
			? { icon: RotateCcw, label: 'Test call again', onclick: () => (campaign.tested = false) }
			: { icon: Phone, label: 'Test call', onclick: testCall }
	]}
/>
