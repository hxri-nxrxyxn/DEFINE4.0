<script lang="ts">
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import { apiUrl } from '#lib/config.js';
	import Phone from '@lucide/svelte/icons/phone';
	import Users from '@lucide/svelte/icons/users';
	import Play from '@lucide/svelte/icons/play';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import Lock from '@lucide/svelte/icons/lock';
	import Server from '@lucide/svelte/icons/server';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { toast } from 'svelte-sonner';

	let calling = $state(false);

	const HIPAA_DISCLAIMER_TEXT =
		"Notice: Under ABDM & DPDP healthcare regulations, this call is processed securely using AI. Number masking is active, no telecom recordings are retained on external gateways, and data is hosted exclusively within Indian datacenters. Your ABHA number will never be shared. By continuing, you consent to your voice and responses being processed by our healthcare AI.";

	async function playVoiceLocally(text: string) {
		try {
			const res = await fetch(apiUrl('/api/process'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ text })
			});
			const data = await res.json();
			if (data.audio_base_64) {
				void new Audio(`data:audio/mpeg;base64,${data.audio_base_64}`).play();
			}
		} catch {
			// ignore
		}
	}

	async function testCall() {
		const script = campaign.templateText.trim();
		const targetNumber = campaign.recipients[0]?.phone || '9995283835';
		const targetName = campaign.recipients[0]?.name || 'Daison';

		if (!script) {
			toast.error('Add a script first', { description: 'Speak or type what the call should say.' });
			return;
		}

		calling = true;
		try {
			const res = await fetch(apiUrl('/api/calls/dispatch'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ phone: targetNumber, name: targetName, template: script })
			});
			const data = await res.json();
			campaign.tested = true;

			if (data?.backend === 'offline') {
				toast.error('Call backend offline', {
					description: 'Start the core server + tunnel. Playing the voice here instead.'
				});
				await playVoiceLocally(script);
			} else if (data?.status === 'error' || data?.call_details?.status === 'error') {
				toast.error('Call failed', {
					description: data?.call_details?.message || data?.message || 'The telephony gateway rejected the call.'
				});
			} else {
				toast.success('Demo call placed', {
					description: `Dialing ${targetNumber} with the ElevenLabs voice message.`
				});
			}
		} catch {
			toast.error('Could not place the call');
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
			This is what your recipients will hear upon pickup.
		</p>
	</div>

	<!-- HIPAA & DPDP Compliancy Toggle Card -->
	<Card.Root class="w-full border-border shadow-xs overflow-hidden {campaign.hipaaCompliant ? 'border-primary/50 bg-primary/[0.02]' : 'bg-card'}">
		<Card.Content class="p-3.5 space-y-3">
			<div class="flex items-center justify-between gap-3">
				<div class="flex items-start gap-2.5">
					<div class="mt-0.5 grid size-7 place-items-center rounded-lg {campaign.hipaaCompliant ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'}">
						<ShieldCheck class="size-4" />
					</div>
					<div class="space-y-0.5">
						<div class="flex items-center gap-2">
							<span class="text-sm font-semibold tracking-tight text-foreground">HIPAA / DPDP Compliancy</span>
							{#if campaign.hipaaCompliant}
								<Badge variant="default" class="h-4 px-1.5 text-[10px] font-medium bg-emerald-600 text-white">
									Active
								</Badge>
							{/if}
						</div>
						<p class="text-xs text-muted-foreground leading-normal">
							Enforce ABDM consent, number masking, and Indian DC residency.
						</p>
					</div>
				</div>
				<Switch
					checked={campaign.hipaaCompliant}
					onCheckedChange={(checked) => {
						campaign.hipaaCompliant = checked;
						if (checked) {
							toast.success('HIPAA / DPDP Compliance Enabled', {
								description: 'Mandatory IVR consent and number masking are now enforced.'
							});
						} else {
							toast.info('HIPAA Compliance Disabled');
						}
					}}
					aria-label="Toggle HIPAA compliancy"
				/>
			</div>

			{#if campaign.hipaaCompliant}
				<div class="rounded-lg border border-primary/20 bg-primary/5 p-2.5 space-y-2 text-xs animate-in fade-in">
					<div class="flex items-center gap-1.5 font-medium text-primary text-[11px] uppercase tracking-wider">
						<Lock class="size-3" /> Mandatory ABDM / DPDP IVR Consent Intro
					</div>
					<p class="text-xs italic text-foreground/90 leading-relaxed bg-background/60 p-2 rounded-md border border-border/50">
						"{HIPAA_DISCLAIMER_TEXT}"
					</p>
					<div class="grid grid-cols-2 gap-2 pt-1 text-[11px] text-muted-foreground">
						<div class="flex items-center gap-1.5">
							<span class="size-1.5 rounded-full bg-emerald-500"></span>
							<span>Number Masking (99••• ••835)</span>
						</div>
						<div class="flex items-center gap-1.5">
							<span class="size-1.5 rounded-full bg-emerald-500"></span>
							<span>No Exotel Carrier Recordings</span>
						</div>
						<div class="flex items-center gap-1.5">
							<span class="size-1.5 rounded-full bg-emerald-500"></span>
							<span>Indian Datacenter (ap-south-1)</span>
						</div>
						<div class="flex items-center gap-1.5">
							<span class="size-1.5 rounded-full bg-emerald-500"></span>
							<span>ABHA Number Guarded</span>
						</div>
					</div>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

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
				<div class="text-muted-foreground font-mono">
					{campaign.recipients[0].name} ({campaign.hipaaCompliant ? campaign.recipients[0].phone.replace(/(\d{2})\d{5}(\d{3})/, '$1•••••$2') : campaign.recipients[0].phone})
				</div>
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
