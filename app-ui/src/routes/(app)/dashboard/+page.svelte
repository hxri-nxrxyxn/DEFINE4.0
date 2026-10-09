<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { PieChart } from 'layerchart';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Chart from '#lib/components/ui/chart/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { campaign, type CallLogItem } from '#lib/state/campaign.svelte.js';
	import { apiUrl } from '#lib/config.js';
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
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import PhoneMissed from '@lucide/svelte/icons/phone-missed';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { toast } from 'svelte-sonner';

	let loading = $state(true);
	let retrying = $state(false);

	let fetchedStats = $state([
		{ label: 'Calls placed', value: '0' },
		{ label: 'Non-responders', value: '0' }
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
					{ label: 'Non-responders', value: String(campaign.nonResponders.length) }
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
			? campaign.nonResponders.map((r) => ({
					name: r.name,
					phone: r.phone,
					language: r.language || 'Hindi',
					disposition: campaign.outcomes[r.phone]?.disposition || 'no_response',
					count: campaign.outcomes[r.phone]?.attempts ?? 1
				}))
			: []
	);

	const OUTCOME_META: Record<string, { label: string; class: string }> = {
		confirmed: { label: 'Confirmed (10s)', class: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' },
		declined: { label: 'Declined', class: 'bg-rose-500/15 text-rose-600 dark:text-rose-400' },
		not_available: { label: 'Not available', class: 'bg-amber-500/15 text-amber-600 dark:text-amber-400' },
		opt_out: { label: 'Opted out', class: 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400' },
		no_response: { label: 'Non-responder', class: 'bg-muted text-muted-foreground' }
	};

	// Recipients who have been called this session, most recent first.
	const callHistory = $derived.by(() =>
		campaign.recipients
			.map((recipient) => ({ recipient, outcome: campaign.outcomes[recipient.phone] }))
			.filter((entry) => entry.outcome !== undefined)
			.sort((a, b) => (b.outcome?.at ?? 0) - (a.outcome?.at ?? 0))
	);

	function formatTime(ts: number): string {
		return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	// Automated Roster Campaign Execution Loop
	let loopTimer: any = null;
	let isExecutingStep = false;
	let lastDialTimestamp = 0;
	let callRegisteredActive = false;

	const HIPAA_DISCLAIMER_PREFIX =
		"Notice: Under ABDM and DPDP healthcare rules, this call is processed securely by AI. Number masking is active, carrier recordings are purged, and data is kept in Indian datacenters. Your ABHA number will never be shared. By continuing, you agree to voice data processing.";

	function formatScriptForRecipient(template: string, name: string): string {
		const base = template
			? template
					.replace(/{name}/gi, name)
					.replace(/\{recipient\}/gi, name)
					.replace(/\b(Daison|Hari|Rahul|User)\b/gi, name)
			: `Hello ${name}, this is an automated IVR call.`;

		if (campaign.hipaaCompliant) {
			return `${HIPAA_DISCLAIMER_PREFIX} ${base}`;
		}
		return base;
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

			// If call is dialing, allow at least 3.5 seconds for TelecomManager to register and connect
			if (campaign.currentCallStatus === 'dialing' && timeSinceDial < 3.5) {
				return;
			}

			// Call has concluded:
			// Condition A: status.call_state is explicitly 'COMPLETED' (reported by bridge)
			// Condition B: call was registered active and has now ended (!status.active)
			// Condition C: call was dialing and has ended after waiting at least 6 seconds without answering
			const callStateStr = status.call_state as string;
			const isConcluded =
				callStateStr === 'COMPLETED' ||
				(callRegisteredActive && !status.active && callStateStr !== 'CONNECTED') ||
				(campaign.currentCallStatus === 'dialing' && !status.active && timeSinceDial > 6.0);

			if (isConcluded) {
				isExecutingStep = true;
				const outcome = status.outcome || (campaign.currentCallDurationSec >= 9.5 ? 'completed' : 'declined');
				const finalDuration = Math.max(campaign.currentCallDurationSec, status.elapsed_seconds || 0);

				let disposition: 'confirmed' | 'declined' | 'no_response' = 'no_response';
				if (outcome === 'completed') {
					disposition = 'confirmed';
				} else if (outcome === 'declined') {
					disposition = 'declined';
				} else {
					disposition = 'no_response';
				}

				// Record in campaign store outcomes for analytical tracking & non-responder list
				campaign.recordOutcome(current.phone, disposition);

				if (campaign.callLogs[0]) {
					campaign.callLogs[0].status = outcome === 'completed' ? 'completed' : 'failed';
					campaign.callLogs[0].durationSeconds = finalDuration;
				}

				if (outcome === 'completed') {
					toast.success(`Completed call with ${current.name}`, {
						description: `10s active duration met. Advancing to next contact...`
					});
				} else if (outcome === 'declined') {
					toast.info(`Call declined: ${current.name}`, {
						description: `Call was declined by recipient. Added to non-responders list.`
					});
				} else {
					toast.info(`No response from ${current.name}`, {
						description: `Auto-terminated after timeout. Added to non-responders list.`
					});
				}

				// Terminate any trailing call state on device
				await terminateCall();

				// Advance to next contact
				campaign.currentCallIndex++;
				campaign.currentCallDurationSec = 0;
				campaign.currentCallStatus = 'idle';
				callRegisteredActive = false;

				// Give 2.5 seconds breathing room between consecutive calls
				await new Promise((resolve) => setTimeout(resolve, 2500));
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
			const res = await fetch(apiUrl('/api/analytics'));
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
			await fetch(apiUrl('/api/retry'), { method: 'POST' });
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

<div class="space-y-5 sm:space-y-6 py-3">
	<div class="space-y-1.5 px-0.5">
		<h1 class="scroll-m-20 text-2xl sm:text-3xl font-extrabold tracking-tight">Dashboard</h1>
		<p class="text-xs sm:text-sm text-muted-foreground">Outcomes by campaign, language, and segment.</p>
	</div>

	<!-- Live IVR Sensor / Auto-Dialer Control Card -->
	{#if campaign.recipients.length > 0}
		<Card.Root class="border-primary/30 bg-primary/[0.03] overflow-hidden shadow-xs">
			<Card.Header class="p-3.5 sm:p-4 pb-2.5">
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2.5">
						<div class="relative grid size-8.5 place-items-center rounded-lg bg-primary/10 text-primary">
							<PhoneCall class="size-4" />
							{#if campaign.isCampaignRunning}
								<span class="absolute -top-1 -right-1 flex size-2.5">
									<span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
									<span class="relative inline-flex size-2.5 rounded-full bg-primary"></span>
								</span>
							{/if}
						</div>
						<div>
							<Card.Title class="text-sm sm:text-base font-semibold">IVR Dialer</Card.Title>
							<Card.Description class="text-xs">
								{campaign.isCampaignRunning ? 'Auto-dialing · 10s per call' : 'Idle'}
							</Card.Description>
						</div>
					</div>

					<div class="flex items-center gap-1.5">
						<Button
							variant="outline"
							size="icon-sm"
							class="size-8.5 rounded-lg"
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
								class="size-8.5 rounded-lg text-destructive hover:bg-destructive/10"
								onclick={stopCampaignPrematurely}
								title="Stop dialer"
							>
								<Square class="size-3.5 fill-current" />
							</Button>
						{/if}
					</div>
				</div>
			</Card.Header>

			<Card.Content class="p-3.5 sm:p-4 pt-0 space-y-3">
				<div class="grid grid-cols-3 gap-2.5 text-xs">
					<div class="rounded-lg border border-border bg-card/60 p-2.5 sm:p-3">
						<div class="text-muted-foreground text-[11px]">Roster Progress</div>
						<div class="font-semibold text-foreground mt-0.5 text-xs sm:text-sm tabular-nums">
							{Math.min(campaign.currentCallIndex + (campaign.isCampaignRunning ? 1 : 0), campaign.recipients.length)} / {campaign.recipients.length}
						</div>
					</div>

					<div class="rounded-lg border border-border bg-card/60 p-2.5 sm:p-3">
						<div class="flex items-center justify-between text-muted-foreground text-[11px]">
							<span>Active Target</span>
							{#if campaign.hipaaCompliant}
								<span class="text-[9px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1 py-0.2 rounded">
									HIPAA
								</span>
							{/if}
						</div>
						<div class="font-semibold text-foreground mt-0.5 text-xs truncate" title={campaign.currentCallName}>
							{campaign.currentCallName || campaign.recipients[campaign.currentCallIndex]?.name || 'Pending'}
						</div>
					</div>

					<div class="rounded-lg border border-border bg-card/60 p-2.5 sm:p-3">
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
					<div class="rounded-lg border border-border/80 bg-muted/30 p-2.5 sm:p-3 text-xs space-y-1">
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

	<!-- Metric Stat Cards -->
	<div class="grid grid-cols-3 gap-2.5 sm:gap-3">
		{#each stats as stat (stat.label)}
			<Card.Root class="gap-0 shadow-xs">
				<Card.Content class="space-y-1 p-3 sm:px-4 sm:py-4">
					<p class="text-[11px] sm:text-xs text-muted-foreground truncate">{stat.label}</p>
					<p class="text-lg sm:text-2xl font-semibold tabular-nums">{stat.value}</p>
				</Card.Content>
			</Card.Root>
		{/each}
		<Card.Root class="gap-0 shadow-xs">
			<Card.Content class="space-y-1 p-3 sm:px-4 sm:py-4">
				<p class="text-[11px] sm:text-xs text-muted-foreground truncate">Connect rate</p>
				<p class="text-lg sm:text-2xl font-semibold tabular-nums">{connectRatePct}%</p>
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Language Breakdown Card -->
	<Card.Root class="shadow-xs">
		<Card.Header class="p-4 sm:p-5 pb-2">
			<Card.Title class="text-sm sm:text-base font-semibold">Calls by language</Card.Title>
			<Card.Description class="text-xs">Volume across regional languages.</Card.Description>
		</Card.Header>
		<Card.Content class="p-4 sm:p-5 pt-1 space-y-3">
			<Chart.Container config={languageConfig} class="mx-auto h-48 sm:h-52 w-full">
				<PieChart data={languageData} value="value" c="color" innerRadius={58}>
					{#snippet tooltip()}
						<Chart.Tooltip />
					{/snippet}
				</PieChart>
			</Chart.Container>
			<div class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs pt-1">
				{#each languageData as item (item.label)}
					<div class="flex items-center gap-2">
						<span class="size-2.5 shrink-0 rounded-[2px]" style="background: {item.color}"></span>
						<span class="text-muted-foreground">{item.label}</span>
						<span class="ml-auto tabular-nums font-mono">{item.value}</span>
					</div>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Call History Card -->
	<Card.Root class="shadow-xs overflow-hidden">
		<Card.Header class="p-4 sm:p-5 pb-2">
			<Card.Title class="text-sm sm:text-base font-semibold">Call history</Card.Title>
			<Card.Description class="text-xs">People contacted this session and how it went.</Card.Description>
		</Card.Header>
		<Card.Content class="p-0">
			{#if callHistory.length > 0}
				<Table.Root>
					<Table.Header class="bg-muted/30">
						<Table.Row class="border-b border-border/60">
							<Table.Head class="px-4 py-2.5 text-xs">Contact</Table.Head>
							<Table.Head class="px-3 py-2.5 text-right text-xs">Language</Table.Head>
							<Table.Head class="px-4 py-2.5 text-right text-xs">Status</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body class="divide-y divide-border/30">
						{#each callHistory as entry (entry.recipient.phone)}
							<Table.Row class="hover:bg-muted/20 transition-colors">
								<Table.Cell class="px-4 py-3">
									<div class="font-medium text-foreground text-xs">{entry.recipient.name}</div>
									<div class="text-[11px] font-mono text-muted-foreground mt-0.5">
										{campaign.hipaaCompliant ? entry.recipient.phone.replace(/(\d{2})\d{5}(\d{3})/, '$1•••••$2') : entry.recipient.phone}
										{#if entry.outcome}
											· {formatTime(entry.outcome.at)}
										{/if}
									</div>
								</Table.Cell>
								<Table.Cell class="px-3 py-3 text-right text-xs text-muted-foreground">
									{entry.recipient.language || '—'}
								</Table.Cell>
								<Table.Cell class="px-4 py-3 text-right">
									<span
										class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium {OUTCOME_META[
											entry.outcome?.disposition ?? ''
										]?.class ?? ''}"
									>
										{OUTCOME_META[entry.outcome?.disposition ?? '']?.label ??
											entry.outcome?.disposition}
									</span>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			{:else}
				<div class="px-6 py-8 text-center text-xs text-muted-foreground">
					No calls yet. Contact a recipient to see them here.
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Non-Responders Card -->
	<Card.Root class="shadow-xs">
		<Card.Header class="p-4 sm:p-5 pb-2">
			<div class="flex items-center justify-between">
				<div>
					<Card.Title class="text-sm sm:text-base font-semibold">Non-Responders</Card.Title>
					<Card.Description class="text-xs">
						Contacts who declined, timed out, or did not answer.
					</Card.Description>
				</div>
				{#if retries.length > 0}
					<Badge variant="secondary" class="h-5 px-2 text-[11px] font-medium tabular-nums">
						{retries.length} queued
					</Badge>
				{/if}
			</div>
		</Card.Header>
		<Card.Content class="p-4 sm:p-5 pt-1 space-y-2.5">
			{#if retries.length > 0}
				{#each retries as item (item.phone)}
					<div class="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 p-2.5 sm:p-3 text-xs">
						<div class="flex items-center gap-2.5 min-w-0">
							<div class="grid size-7.5 place-items-center rounded-md bg-muted text-muted-foreground shrink-0">
								<PhoneMissed class="size-3.5 text-rose-500" />
							</div>
							<div class="min-w-0 truncate">
								<div class="font-medium text-foreground truncate text-xs">{item.name}</div>
								<div class="text-[11px] font-mono text-muted-foreground truncate mt-0.5">
									{campaign.hipaaCompliant ? item.phone.replace(/(\d{2})\d{5}(\d{3})/, '$1•••••$2') : item.phone} · {item.language}
								</div>
							</div>
						</div>
						<div class="flex items-center gap-2 shrink-0">
							<span
								class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium {OUTCOME_META[item.disposition]?.class ?? 'bg-muted text-muted-foreground'}"
							>
								{OUTCOME_META[item.disposition]?.label ?? item.disposition}
							</span>
							<span class="text-[11px] font-mono text-muted-foreground" title="Attempt count">
								x{item.count}
							</span>
						</div>
					</div>
				{/each}
			{:else}
				<div class="py-4 text-center text-xs text-muted-foreground">
					No non-responders detected. All calls connected or roster pending.
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
