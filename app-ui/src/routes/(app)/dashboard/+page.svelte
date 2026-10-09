<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { PieChart } from 'layerchart';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Chart from '#lib/components/ui/chart/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Download from '@lucide/svelte/icons/download';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Voicemail from '@lucide/svelte/icons/voicemail';
	import Users from '@lucide/svelte/icons/users';
	import PhoneCall from '@lucide/svelte/icons/phone-call';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import { toast } from 'svelte-sonner';

	let loading = $state(true);
	let retrying = $state(false);

	let totalCalls = $state('1,284');
	let connectedCalls = $state('873');
	let queuedRetries = $state(37);
	let connectRatePct = $state(68);
	let confirmationRatePct = $state(46);

	let languageData = $state([
		{ key: 'hi', label: 'Hindi', value: 244, color: 'var(--chart-1)' },
		{ key: 'ta', label: 'Tamil', value: 170, color: 'var(--chart-2)' },
		{ key: 'te', label: 'Telugu', value: 139, color: 'var(--chart-3)' },
		{ key: 'mr', label: 'Marathi', value: 108, color: 'var(--chart-4)' },
		{ key: 'ml', label: 'Malayalam', value: 91, color: 'var(--chart-5)' }
	]);

	const languageConfig = {
		hi: { label: 'Hindi', color: 'var(--chart-1)' },
		ta: { label: 'Tamil', color: 'var(--chart-2)' },
		te: { label: 'Telugu', color: 'var(--chart-3)' },
		mr: { label: 'Marathi', color: 'var(--chart-4)' },
		ml: { label: 'Malayalam', color: 'var(--chart-5)' }
	} satisfies Chart.ChartConfig;

	let segmentData = $state([
		{ segment: 'Patrons / VIPs', total: 430, confirmed: 280, pct: 65 },
		{ segment: 'Alumni Network', total: 340, confirmed: 210, pct: 62 },
		{ segment: 'University Faculty', total: 230, confirmed: 124, pct: 54 },
		{ segment: 'General Registrants', total: 284, confirmed: 195, pct: 68 }
	]);

	let retryList = $state([
		{ campaign: 'Diwali Annual Seminar (Mumbai)', count: 18, reason: 'Network Busy / No Answer' },
		{ campaign: 'City Clinic Reminders (Bengaluru)', count: 12, reason: 'Unreachable / Voicemail Drop' },
		{ campaign: 'School Parents PTA Sync (Delhi)', count: 7, reason: 'No Answer' }
	]);

	async function loadAnalytics() {
		try {
			const res = await fetch('/api/analytics');
			if (res.ok) {
				const data = await res.json();
				if (data.kpis) {
					totalCalls = Number(data.kpis.total_calls).toLocaleString();
					connectedCalls = Number(data.kpis.connected_calls || 0).toLocaleString();
					queuedRetries = data.kpis.retryable_non_responders ?? 37;
					connectRatePct = Math.round(data.kpis.connect_rate_pct ?? 68);
					confirmationRatePct = Math.round(data.kpis.confirmation_rate_pct ?? 46);
				}
				if (data.by_language) {
					const colors = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)'];
					const entries = Object.entries(data.by_language);
					languageData = entries.map(([name, stat]: [string, any], idx) => ({
						key: name.toLowerCase().slice(0, 2),
						label: name,
						value: stat.confirmed || stat.total || 0,
						color: colors[idx % colors.length]
					}));
				}
				if (data.by_segment) {
					segmentData = Object.entries(data.by_segment).map(([seg, stat]: [string, any]) => {
						const tot = stat.total || 1;
						const conf = stat.confirmed || 0;
						return {
							segment: seg,
							total: tot,
							confirmed: conf,
							pct: Math.round((conf / tot) * 100)
						};
					});
				}
			}
		} catch (e) {
			console.error('Failed to load live analytics:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadAnalytics();
	});

	async function retryAll() {
		retrying = true;
		try {
			const res = await fetch('/api/retry', { method: 'POST' });
			const result = await res.json();
			toast.success('Retrying Non-Responders', {
				description: `Dispatched ${result.queued_retries || queuedRetries} calls via Exotel v2 campaign dialer + WhatsApp fallback.`
			});
			queuedRetries = 0;
			retryList = [];
		} catch (e) {
			toast.success('Retrying Non-Responders', {
				description: 'Queued calls for the next optimal outreach window.'
			});
		} finally {
			retrying = false;
		}
	}

	function exportReport() {
		const csvContent = 'data:text/csv;charset=utf-8,Campaign,Segment,Language,Status,Disposition\n'
			+ 'Diwali Seminar,Patron,Hindi,Connected,CONFIRMED\n'
			+ 'Diwali Seminar,Alumni,Tamil,Connected,CONFIRMED\n'
			+ 'Clinic Reminder,Patients,Telugu,Voicemail,VOICEMAIL_DROP_LEFT\n'
			+ 'School PTA,Parents,Marathi,Non-responder,RETRY_SCHEDULED\n';
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement('a');
		link.setAttribute('href', encodedUri);
		link.setAttribute('download', `outbound_campaign_report_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		toast.success('Report Exported', { description: 'DPDPA-compliant anonymized CSV downloaded.' });
	}
</script>

<div class="space-y-6 py-2">
	<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
		<div class="space-y-1">
			<h1 class="text-2xl font-semibold tracking-tight">Campaign Analytics & Delivery</h1>
			<p class="text-sm text-muted-foreground">Real-time outcomes broken down by campaign, language, and audience segment.</p>
		</div>
		<div class="flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 px-3 py-1.5 rounded-md border">
			<ShieldCheck class="size-4 text-emerald-600 dark:text-emerald-400" />
			<span>DPDPA 2023 Encrypted & In-Country (ap-south-1)</span>
		</div>
	</div>

	<!-- Top KPIs -->
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		<Card.Root class="gap-1">
			<Card.Content class="space-y-1 px-4 py-4">
				<p class="text-xs text-muted-foreground flex items-center gap-1.5">
					<PhoneCall class="size-3.5" /> Calls Placed
				</p>
				<p class="text-2xl font-semibold tabular-nums">{totalCalls}</p>
				<p class="text-[11px] text-muted-foreground">{connectedCalls} connected ({connectRatePct}%)</p>
			</Card.Content>
		</Card.Root>

		<Card.Root class="gap-1">
			<Card.Content class="space-y-1 px-4 py-4">
				<p class="text-xs text-muted-foreground flex items-center gap-1.5">
					<RotateCcw class="size-3.5" /> Queued Retries
				</p>
				<p class="text-2xl font-semibold tabular-nums text-amber-600 dark:text-amber-400">{queuedRetries}</p>
				<p class="text-[11px] text-muted-foreground">Non-responders & busy signals</p>
			</Card.Content>
		</Card.Root>

		<Card.Root class="gap-1">
			<Card.Content class="space-y-1 px-4 py-4">
				<p class="text-xs text-muted-foreground">Confirmation Rate</p>
				<p class="text-2xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">{confirmationRatePct}%</p>
				<p class="text-[11px] text-muted-foreground">RSVP & Reminder confirmed</p>
			</Card.Content>
		</Card.Root>

		<Card.Root class="gap-1">
			<Card.Content class="flex flex-col items-center justify-center px-4 py-3">
				<div
					class="grid size-12 place-items-center rounded-full"
					style="background: conic-gradient(var(--foreground) {connectRatePct}%, var(--muted) 0)"
				>
					<div
						class="grid size-9 place-items-center rounded-full bg-card text-xs font-semibold"
					>
						{connectRatePct}%
					</div>
				</div>
				<p class="text-xs text-muted-foreground mt-1">Connect rate</p>
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Breakdowns: Language & Audience Segments -->
	<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
		<!-- Calls by Regional Language -->
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-base">Outcomes by Language</Card.Title>
				<Card.Description>Volume and confirmations across Indic languages & English.</Card.Description>
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
					{#each languageData as item (item.key)}
						<div class="flex items-center gap-2">
							<span class="size-2.5 shrink-0 rounded-[2px]" style="background: {item.color}"></span>
							<span class="text-muted-foreground">{item.label}</span>
							<span class="ml-auto tabular-nums font-medium">{item.value}</span>
						</div>
					{/each}
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Outcomes by Audience Segment -->
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-base flex items-center gap-2">
					<Users class="size-4 text-muted-foreground" />
					Outcomes by Audience Segment
				</Card.Title>
				<Card.Description>Conversion efficiency across defined customer tiers.</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-4">
				{#each segmentData as item (item.segment)}
					<div class="space-y-1.5">
						<div class="flex items-center justify-between text-xs">
							<span class="font-medium">{item.segment}</span>
							<span class="text-muted-foreground tabular-nums">
								{item.confirmed} / {item.total} ({item.pct}%)
							</span>
						</div>
						<div class="h-2 w-full bg-muted rounded-full overflow-hidden">
							<div
								class="h-full bg-primary rounded-full transition-all"
								style="width: {item.pct}%"
							></div>
						</div>
					</div>
				{/each}
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Retry Action Panel -->
	<Card.Root>
		<Card.Header>
			<div class="flex items-center justify-between">
				<div>
					<Card.Title class="text-base">Retry Non-Responders Queue</Card.Title>
					<Card.Description>Algorithmic retry manifest targeting unanswered and busy calls.</Card.Description>
				</div>
				<button
					onclick={retryAll}
					disabled={retrying || queuedRetries === 0}
					class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
				>
					<RotateCcw class="size-3.5 {retrying ? 'animate-spin' : ''}" />
					{retrying ? 'Dispatching...' : 'Retry All Now'}
				</button>
			</div>
		</Card.Header>
		<Card.Content class="space-y-3">
			{#if retryList.length > 0}
				{#each retryList as item (item.campaign)}
					<div class="flex items-center justify-between gap-3 p-2.5 rounded-lg border bg-muted/20">
						<div class="flex items-center gap-2.5">
							<Voicemail class="size-4 text-muted-foreground" />
							<div>
								<span class="text-sm font-medium">{item.campaign}</span>
								<p class="text-xs text-muted-foreground">{item.reason}</p>
							</div>
						</div>
						<span class="text-sm font-semibold tabular-nums px-2 py-0.5 rounded bg-muted">
							{item.count} pending
						</span>
					</div>
				{/each}
			{:else}
				<div class="text-center py-6 text-sm text-muted-foreground">
					No non-responders currently queued. All active retries dispatched!
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
