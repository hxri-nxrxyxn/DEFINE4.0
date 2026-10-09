<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { PieChart } from 'layerchart';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Chart from '#lib/components/ui/chart/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { campaign, type CallLogItem } from '#lib/state/campaign.svelte.js';
	import { triggerCall, terminateCall, pollCallStatus } from '#lib/audio/auto-dialer.js';
	import Download from '@lucide/svelte/icons/download';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Voicemail from '@lucide/svelte/icons/voicemail';
	import PhoneCall from '@lucide/svelte/icons/phone-call';
	import PhoneOff from '@lucide/svelte/icons/phone-off';
	import PhoneForwarded from '@lucide/svelte/icons/phone-forwarded';
	import CheckCircle2 from '@lucide/svelte/icons/check-circle-2';
	import Pause from '@lucide/svelte/icons/pause';
	import Play from '@lucide/svelte/icons/play';
	import Square from '@lucide/svelte/icons/square';
	import { toast } from 'svelte-sonner';

	let loading = $state(true);
	let retrying = $state(false);

	let fetchedStats = $state([
		{ label: 'Calls placed', value: '0' },
		{ label: 'Queued retries', value: '0' }
	]);

	let fetchedConnectRate = $state(0);

	let fetchedLanguageData = $state<{ key: string; label: string; value: number; color: string }[]>(
		[]
	);

	const languageConfig = {
		hi: { label: 'Hindi', color: 'var(--chart-1)' },
		ta: { label: 'Tamil', color: 'var(--chart-2)' },
		te: { label: 'Telugu', color: 'var(--chart-3)' },
		mr: { label: 'Marathi', color: 'var(--chart-4)' },
		ml: { label: 'Malayalam', color: 'var(--chart-5)' }
	} satisfies Chart.ChartConfig;

	const COLORS = [
		'var(--chart-1)',
		'var(--chart-2)',
		'var(--chart-3)',
		'var(--chart-4)',
		'var(--chart-5)'
	];

	// Prefer live campaign outcomes over the backend/mock analytics.
	const hasLocal = $derived(campaign.recipients.length > 0);
	const attempted = $derived(
		Math.max(campaign.recipients.length - campaign.summary.pending, campaign.currentCallIndex)
	);

	const stats = $derived(
		hasLocal
			? [
					{ label: 'Calls placed', value: String(attempted) },
					{ label: 'Queued retries', value: String(campaign.retryList.length) }
				]
			: fetchedStats
	);

	const connectRatePct = $derived(
		hasLocal
			? Math.round((campaign.summary.confirmed / Math.max(attempted, 1)) * 100)
			: fetchedConnectRate
	);

	const localLanguageData = $derived.by(() => {
		const map = new Map<string, number>();
		for (const r of campaign.recipients) {
			const label = r.language || 'Hindi';
			map.set(label, (map.get(label) ?? 0) + 1);
		}
		return [...map.entries()].map(([label, value], idx) => ({
			key: label.toLowerCase(),
			label,
			value,
			color: COLORS[idx % COLORS.length]
		}));
	});

	const languageData = $derived(hasLocal ? localLanguageData : fetchedLanguageData);

	const retries = $derived(
		hasLocal
			? campaign.retryList.map((r) => ({
					phone: r.phone,
					campaign: r.name,
					count: campaign.outcomes[r.phone]?.attempts ?? 1
				}))
			: []
	);

	// Automated Roster Campaign Execution Loop
	let loopTimer: any = null;
	let isExecutingStep = false;
	let lastDialTimestamp = 0;
	let callRegisteredActive = false;

	function formatScriptForRecipient(template: string, name: string): string {
		if (!template) return `Hello ${name}, this is an automated IVR call.`;
		return template
			.replace(/{name}/gi, name)
			.replace(/\{recipient\}/gi, name)
			.replace(/\b(Daison|Hari|Rahul|User)\b/gi, name);
	}

	async function runAutoDialerLoop() {
		if (!campaign.isCampaignRunning || isExecutingStep) return;

		const roster = campaign.recipients;
		if (!roster || roster.length === 0) {
			campaign.isCampaignRunning = false;
			return;
		}

		if (campaign.currentCallIndex >= roster.length) {
			campaign.isCampaignRunning = false;
			campaign.currentCallStatus = 'completed';
			toast.success('Campaign Completed!', {
				description: `All ${roster.length} numbers in the call roster processed.`
			});
			return;
		}

		const current = roster[campaign.currentCallIndex];
		campaign.currentCallPhone = current.phone;
		campaign.currentCallName = current.name;

		// 1. If currently idle, place call
		if (campaign.currentCallStatus === 'idle') {
			isExecutingStep = true;
			campaign.currentCallStatus = 'dialing';
			campaign.currentCallDurationSec = 0;
			lastDialTimestamp = Date.now();
			callRegisteredActive = false;

			const formattedScript = formatScriptForRecipient(campaign.templateText, current.name);

			const logItem: CallLogItem = {
				phone: current.phone,
				name: current.name,
				language: current.language || 'Hindi',
				status: 'dialing',
				durationSeconds: 0,
				callScriptText: formattedScript,
				timestamp: Date.now()
			};
			campaign.callLogs = [logItem, ...campaign.callLogs];

			toast.info(`Calling ${current.name}`, {
				description: `Dialing ${current.phone}...`
			});

			try {
				await triggerCall(current.phone, current.name, 10);
			} catch (err) {
				console.error('Trigger call failed:', err);
			} finally {
				isExecutingStep = false;
			}
			return;
		}

		// 2. Poll ongoing call status from bridge or native plugin
		try {
			const status = await pollCallStatus();
			const now = Date.now();
			const timeSinceDial = (now - lastDialTimestamp) / 1000;

			// If connected
			if (status.call_state === 'CONNECTED' || status.active) {
				callRegisteredActive = true;
				campaign.currentCallStatus = 'connected';
				campaign.currentCallDurationSec = status.elapsed_seconds || 0;

				// Update top log item
				if (campaign.callLogs[0]) {
					campaign.callLogs[0].status = 'connected';
					campaign.callLogs[0].durationSeconds = status.elapsed_seconds || 0;
				}
				return;
			}

			// If call is dialing, allow at least 3 seconds before concluding it ended or was declined
			if (campaign.currentCallStatus === 'dialing' && timeSinceDial < 3.0) {
				return;
			}

			// Call has concluded (either answered + 10s passed, hung up, or declined during ringing)
			if (status.call_state === 'COMPLETED' || (!status.active && campaign.currentCallStatus !== 'idle')) {
				isExecutingStep = true;
				const outcome = status.outcome || (campaign.currentCallDurationSec >= 9.5 ? 'completed' : 'declined');
				const finalDuration = Math.max(campaign.currentCallDurationSec, status.elapsed_seconds || 0);

				if (campaign.callLogs[0]) {
					campaign.callLogs[0].status = outcome === 'completed' ? 'completed' : 'failed';
					campaign.callLogs[0].durationSeconds = finalDuration;
				}

				if (outcome === 'completed') {
					toast.success(`Completed call with ${current.name}`, {
						description: `10s active duration met. Advancing to next contact...`
					});
				} else {
					toast.info(`Call ended with ${current.name}`, {
						description: `Call declined or disconnected (${finalDuration}s). Advancing to next contact...`
					});
				}

				// Terminate any trailing call state on device
				await terminateCall();

				// Advance to next contact
				campaign.currentCallIndex++;
				campaign.currentCallDurationSec = 0;
				campaign.currentCallStatus = 'idle';
				callRegisteredActive = false;

				// Give a 1.5 second breathing room between consecutive calls
				await new Promise((resolve) => setTimeout(resolve, 1500));
				isExecutingStep = false;
			}
		} catch (e) {
			console.error('Status polling error:', e);
		}
	}

	function pauseResumeCampaign() {
		if (campaign.isCampaignRunning) {
			campaign.isCampaignRunning = false;
			toast.info('Campaign Paused');
		} else {
			campaign.isCampaignRunning = true;
			toast.info('Campaign Resumed');
		}
	}

	async function stopCampaignPrematurely() {
		campaign.isCampaignRunning = false;
		campaign.currentCallStatus = 'stopped';
		await terminateCall();
		toast.info('Campaign Stopped');
	}

	async function loadAnalytics() {
		try {
			const res = await fetch('/api/analytics');
			if (res.ok) {
				const data = await res.json();
				if (data.kpis) {
					fetchedStats = [
						{ label: 'Calls placed', value: Number(data.kpis.total_calls).toLocaleString() },
						{ label: 'Queued retries', value: String(data.kpis.retryable_non_responders ?? 0) }
					];
					fetchedConnectRate = Math.round(data.kpis.connect_rate_pct ?? 0);
				}
				if (data.by_language) {
					const entries = Object.entries(data.by_language);
					fetchedLanguageData = entries.map(([name, stat]: [string, any], idx) => ({
						key: name.toLowerCase(),
						label: name,
						value: stat.confirmed || stat.total || 0,
						color: COLORS[idx % COLORS.length]
					}));
				}
			}
		} catch (e) {
			console.error('Analytics load error:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadAnalytics();
		// Poll loop every 800ms
		loopTimer = setInterval(runAutoDialerLoop, 800);
	});

	onDestroy(() => {
		if (loopTimer) clearInterval(loopTimer);
	});

	async function retryAll() {
		retrying = true;
		try {
			await fetch('/api/retry', { method: 'POST' });
		} catch (e) {
			// offline fallback - retry list is derived locally anyway
		} finally {
			toast.success('Retrying non-responders', {
				description: `${campaign.retryList.length} calls queued for the next window.`
			});
			retrying = false;
		}
	}

	function exportReport() {
		const csvContent =
			'data:text/csv;charset=utf-8,Campaign,Language,Status\n' +
			'Diwali Seminar,Hindi,Confirmed\n' +
			'City Clinic Reminders,Tamil,Confirmed\n' +
			'School Parents Sync,Telugu,Retry Scheduled\n';
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement('a');
		link.setAttribute('href', encodedUri);
		link.setAttribute('download', `campaign_report_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		toast.success('Report exported', { description: 'campaign-report.csv downloaded.' });
	}
</script>

<div class="space-y-6 py-2">
	<div class="space-y-1">
		<h1 class="scroll-m-20 text-3xl font-extrabold tracking-tight">Dashboard</h1>
		<p class="text-sm text-muted-foreground">Outcomes by campaign, language, and segment.</p>
	</div>

	<!-- Live IVR Sensor / Auto-Dialer Control Card -->
	{#if campaign.recipients.length > 0}
		<Card.Root class="border-primary/30 bg-primary/[0.03] overflow-hidden shadow-xs">
			<Card.Header class="pb-2.5">
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2">
						<div class="relative grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
							<PhoneCall class="size-4" />
							{#if campaign.isCampaignRunning}
								<span class="absolute -top-1 -right-1 flex size-2.5">
									<span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
									<span class="relative inline-flex size-2.5 rounded-full bg-primary"></span>
								</span>
							{/if}
						</div>
						<div>
							<Card.Title class="text-base font-semibold">IVR Dialer</Card.Title>
							<Card.Description class="text-xs">
								{campaign.isCampaignRunning ? 'Auto-dialing · 10s per call' : 'Idle'}
							</Card.Description>
						</div>
					</div>

					<div class="flex items-center gap-1.5">
						<Button
							variant="outline"
							size="icon-sm"
							class="size-8 rounded-lg"
							onclick={pauseResumeCampaign}
							title={campaign.isCampaignRunning ? 'Pause campaign' : 'Resume campaign'}
						>
							{#if campaign.isCampaignRunning}
								<Pause class="size-3.5" />
							{:else}
								<Play class="size-3.5" />
							{/if}
						</Button>
						{#if campaign.isCampaignRunning}
							<Button
								variant="ghost"
								size="icon-sm"
								class="size-8 rounded-lg text-destructive hover:bg-destructive/10"
								onclick={stopCampaignPrematurely}
								title="Stop dialer"
							>
								<Square class="size-3.5 fill-current" />
							</Button>
						{/if}
					</div>
				</div>
			</Card.Header>

			<Card.Content class="space-y-3 pt-1">
				<div class="grid grid-cols-3 gap-2 text-xs">
					<div class="rounded-lg border border-border bg-card/60 p-2.5">
						<div class="text-muted-foreground text-[11px]">Roster Progress</div>
						<div class="font-semibold text-foreground mt-0.5 text-sm tabular-nums">
							{Math.min(campaign.currentCallIndex + (campaign.isCampaignRunning ? 1 : 0), campaign.recipients.length)} / {campaign.recipients.length}
						</div>
					</div>

					<div class="rounded-lg border border-border bg-card/60 p-2.5">
						<div class="text-muted-foreground text-[11px]">Active Target</div>
						<div class="font-semibold text-foreground mt-0.5 text-xs truncate" title={campaign.currentCallName}>
							{campaign.currentCallName || campaign.recipients[campaign.currentCallIndex]?.name || 'Pending'}
						</div>
					</div>

					<div class="rounded-lg border border-border bg-card/60 p-2.5">
						<div class="text-muted-foreground text-[11px]">Pickup Timer</div>
						<div class="font-semibold text-primary mt-0.5 text-xs tabular-nums">
							{#if campaign.currentCallStatus === 'connected'}
								{campaign.currentCallDurationSec.toFixed(1)}s / 10s
							{:else if campaign.currentCallStatus === 'dialing'}
								Dialing...
							{:else}
								Idle
							{/if}
						</div>
					</div>
				</div>

				<!-- Personalized Preview snippet -->
				{#if campaign.isCampaignRunning && campaign.currentCallName}
					<div class="rounded-lg border border-border/80 bg-muted/30 p-2.5 text-xs space-y-1">
						<div class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
							Active personalized script:
						</div>
						<div class="italic text-foreground line-clamp-2 leading-relaxed">
							"{formatScriptForRecipient(campaign.templateText, campaign.currentCallName)}"
						</div>
					</div>
				{/if}
			</Card.Content>
		</Card.Root>
	{/if}

	<div class="grid grid-cols-3 gap-3">
		{#each stats as stat (stat.label)}
			<Card.Root class="gap-0">
				<Card.Content class="space-y-1 px-4 py-5">
					<p class="text-xs text-muted-foreground">{stat.label}</p>
					<p class="text-2xl font-semibold tabular-nums">{stat.value}</p>
				</Card.Content>
			</Card.Root>
		{/each}
		<Card.Root class="gap-0">
			<Card.Content class="space-y-1 px-4 py-5">
				<p class="text-xs text-muted-foreground">Connect rate</p>
				<p class="text-2xl font-semibold tabular-nums">{connectRatePct}%</p>
			</Card.Content>
		</Card.Root>
	</div>

	<Card.Root>
		<Card.Header>
			<Card.Title class="text-base">Calls by language</Card.Title>
			<Card.Description>Volume across regional languages.</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-3">
			<Chart.Container config={languageConfig} class="mx-auto h-52 w-full">
				<PieChart data={languageData} value="value" c="color" innerRadius={62}>
					{#snippet tooltip()}
						<Chart.Tooltip />
					{/snippet}
				</PieChart>
			</Chart.Container>
			<div class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
				{#each languageData as item (item.label)}
					<div class="flex items-center gap-2">
						<span class="size-2.5 shrink-0 rounded-[2px]" style="background: {item.color}"></span>
						<span class="text-muted-foreground">{item.label}</span>
						<span class="ml-auto tabular-nums">{item.value}</span>
					</div>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title class="text-base">Retry non-responders</Card.Title>
			<Card.Description>Calls pending a second attempt.</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-3">
			{#if retries.length > 0}
				{#each retries as item (item.phone)}
					<div class="flex items-center justify-between gap-3">
						<div class="flex items-center gap-2">
							<Voicemail class="size-4 text-muted-foreground" />
							<span class="text-sm">{item.campaign}</span>
						</div>
						<span class="text-sm tabular-nums text-muted-foreground">{item.count}</span>
					</div>
				{/each}
			{:else}
				<div class="py-2 text-center text-xs text-muted-foreground">
					No pending retries.
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
</div>

<ActionBar
	primaryLabel="New campaign"
	onPrimaryAction={() => {
		campaign.reset();
		goto('/');
	}}
	actions={[
		{ icon: RotateCcw, label: 'Retry non-responders', onclick: retryAll },
		{ icon: Download, label: 'Export report', onclick: exportReport }
	]}
/>
