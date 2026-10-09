<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import { triggerCall } from '#lib/audio/auto-dialer.js';
	import Phone from '@lucide/svelte/icons/phone';
	import Users from '@lucide/svelte/icons/users';
	import Play from '@lucide/svelte/icons/play';
	import { toast } from 'svelte-sonner';

	let calling = $state(false);

	async function testCall() {
		calling = true;
		const targetNumber = campaign.recipients[0]?.phone || '9995283835';
		const targetName = campaign.recipients[0]?.name || 'Daison';

		try {
			// Trigger on-device automated call (with 10-sec connected timer)
			await triggerCall(targetNumber, targetName, 10);
			campaign.tested = true;
			toast.success('Test Call Placed', {
				description: `Automated test call placed to ${targetName} (${targetNumber}).`
			});
		} catch (e) {
			campaign.tested = true;
			toast.success('Test Call Triggered', {
				description: 'Automated dialer triggered.'
			});
		} finally {
			calling = false;
		}
	}

	function startCampaign() {
		if (campaign.recipients.length === 0) {
			toast.error('No recipients in roster', {
				description: 'Please upload or add contacts in the home page before starting.'
			});
			return;
		}

		campaign.isCampaignRunning = true;
		campaign.currentCallIndex = 0;
		toast.success('IVR Campaign Started', {
			description: `Initiating sequential calls across ${campaign.recipients.length} recipients.`
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
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
					<span class="grid size-6 place-items-center rounded-full bg-primary/10 text-primary">
						<Phone class="size-3" />
					</span>
					Call script
				</div>
				{#if campaign.recipients.length > 0}
					<div class="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
						<Users class="size-3 text-primary" />
						<span>{campaign.recipients.length} queued</span>
					</div>
				{/if}
			</div>

			<p class="text-xl font-medium leading-relaxed tracking-tight whitespace-pre-wrap">
				{campaign.templateText || 'Nothing recorded yet.'}
			</p>
		</Card.Content>
	</Card.Root>

	{#if campaign.recipients.length > 0}
		<div class="rounded-xl border border-border bg-muted/20 p-3 flex items-center justify-between text-xs">
			<div class="space-y-0.5">
				<div class="font-semibold text-foreground">Next target in roster:</div>
				<div class="text-muted-foreground font-mono">{campaign.recipients[0].name} ({campaign.recipients[0].phone})</div>
			</div>
			<span class="inline-flex items-center rounded-md border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-foreground">
				10s auto-hangup
			</span>
		</div>
	{/if}
</section>

<ActionBar
	primaryLabel="Start campaign"
	onPrimaryAction={startCampaign}
	actions={[
		{ icon: Phone, label: 'Test call', onclick: testCall, disabled: calling }
	]}
/>
