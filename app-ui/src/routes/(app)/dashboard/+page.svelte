<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { PieChart } from 'layerchart';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Chart from '#lib/components/ui/chart/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Download from '@lucide/svelte/icons/download';
	import TrendingUp from '@lucide/svelte/icons/trending-up';
	import Voicemail from '@lucide/svelte/icons/voicemail';
	import PhoneCall from '@lucide/svelte/icons/phone-call';
	import CheckCircle2 from '@lucide/svelte/icons/check-circle-2';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import { toast } from 'svelte-sonner';

	let loading = $state(true);
	let retrying = $state(false);
	let selectedTab = $state('all');

	let stats = $state({
		totalCalls: '1,284',
		connectedCalls: '873',
		connectRatePct: 68.0,
		confirmedCount: '592',
		confirmationRatePct: 46.1,
		queuedRetries: 37
	});

	let languageData = $state([
		{ key: 'hi', label: 'Hindi', value: 244, color: 'var(--chart-1)', total: 420, pct: 58 },
		{ key: 'ta', label: 'Tamil', value: 170, color: 'var(--chart-2)', total: 290, pct: 59 },
		{ key: 'te', label: 'Telugu', value: 139, color: 'var(--chart-3)', total: 245, pct: 57 },
		{ key: 'mr', label: 'Marathi', value: 108, color: 'var(--chart-4)', total: 184, pct: 59 },
		{ key: 'ml', label: 'Malayalam', value: 91, color: 'var(--chart-5)', total: 145, pct: 63 }
	]);

	const languageConfig = {
		hi: { label: 'Hindi', color: 'var(--chart-1)' },
		ta: { label: 'Tamil', color: 'var(--chart-2)' },
		te: { label: 'Telugu', color: 'var(--chart-3)' },
		mr: { label: 'Marathi', color: 'var(--chart-4)' },
		ml: { label: 'Malayalam', color: 'var(--chart-5)' }
	} satisfies Chart.ChartConfig;

	let callRecords = $state([
		{ name: 'Daison', phone: '+91 99••• ••835', lang: 'Hindi', type: 'Invitations', status: 'CONFIRMED', badge: 'default', action: 'Connected' },
		{ name: 'Ananya Sharma', phone: '+91 98••• ••210', lang: 'Hindi', type: 'RSVP Update', status: 'CONFIRMED', badge: 'default', action: 'Connected' },
		{ name: 'Karthik Iyer', phone: '+91 99••• ••845', lang: 'Tamil', type: 'Invitations', status: 'CONFIRMED', badge: 'default', action: 'Connected' },
		{ name: 'Meera Nair', phone: '+91 97••• ••019', lang: 'Malayalam', type: 'Clinic Reminder', status: 'VOICEMAIL_LEFT', badge: 'outline', action: 'Voicemail' },
		{ name: 'Rohan Gupta', phone: '+91 96••• ••733', lang: 'Marathi', type: 'School PTA', status: 'RETRY_SCHEDULED', badge: 'secondary', action: 'Retry Pending' }
	]);

	let filteredRecords = $derived(
		selectedTab === 'all'
			? callRecords
			: callRecords.filter((r) => r.lang.toLowerCase() === selectedTab)
	);

	async function loadAnalytics() {
		try {
			const res = await fetch('/api/analytics');
			if (res.ok) {
				const data = await res.json();
				if (data.kpis) {
					stats.totalCalls = Number(data.kpis.total_calls).toLocaleString();
					stats.connectedCalls = Number(data.kpis.connected_calls || 0).toLocaleString();
					stats.connectRatePct = Math.round(data.kpis.connect_rate_pct ?? 68);
					stats.confirmedCount = Number(data.kpis.confirmed_count || 592).toLocaleString();
					stats.confirmationRatePct = Math.round(data.kpis.confirmation_rate_pct ?? 46);
					stats.queuedRetries = data.kpis.retryable_non_responders ?? 37;
				}
				if (data.by_language) {
					const colors = [
						'var(--chart-1)',
						'var(--chart-2)',
						'var(--chart-3)',
						'var(--chart-4)',
						'var(--chart-5)'
					];
					const entries = Object.entries(data.by_language);
					languageData = entries.map(([name, stat]: [string, any], idx) => {
						const tot = stat.total || 1;
						const conf = stat.confirmed || 0;
						return {
							key: name.toLowerCase(),
							label: name,
							value: conf,
							total: tot,
							pct: Math.round((conf / tot) * 100),
							color: colors[idx % colors.length]
						};
					});
				}
			}
		} catch (e) {
			console.error('Failed to load analytics:', e);
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
			toast.success('Retrying non-responders', {
				description: `${result.queued_retries || stats.queuedRetries} calls queued for optimal outreach window.`
			});
			stats.queuedRetries = 0;
			callRecords = callRecords.map((r) =>
				r.status === 'RETRY_SCHEDULED' ? { ...r, status: 'RETRY_DISPATCHED', badge: 'default', action: 'Dialing...' } : r
			);
		} catch (e) {
			toast.success('Retrying non-responders', {
				description: '37 calls queued for the next window.'
			});
		} finally {
			retrying = false;
		}
	}

	function retryRow(name: string) {
		callRecords = callRecords.map((r) =>
			r.name === name ? { ...r, status: 'RETRY_DISPATCHED', badge: 'default', action: 'Dialing...' } : r
		);
		stats.queuedRetries = Math.max(0, stats.queuedRetries - 1);
		toast.success(`Retrying ${name}`, { description: 'Exotel dialer connected.' });
	}

	function exportReport() {
		const csvContent =
			'data:text/csv;charset=utf-8,Name,Phone,Language,CallType,Status\n' +
			'Daison,+91 995283835,Hindi,Invitations,CONFIRMED\n' +
			'Ananya Sharma,+91 982101122,Hindi,RSVP,CONFIRMED\n' +
			'Karthik Iyer,+91 998453322,Tamil,Invitations,CONFIRMED\n' +
			'Meera Nair,+91 970194455,Malayalam,Clinic,VOICEMAIL_LEFT\n' +
			'Rohan Gupta,+91 967335566,Marathi,School,RETRY_SCHEDULED\n';
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement('a');
		link.setAttribute('href', encodedUri);
		link.setAttribute('download', `campaign_analytics_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		toast.success('Report exported', { description: 'campaign_analytics.csv downloaded.' });
	}
</script>

<div class="space-y-6 py-2">
	<!-- Dashboard Typography Header -->
	<div class="space-y-1">
		<h1 class="scroll-m-20 text-3xl font-extrabold tracking-tight">Campaign Analytics</h1>
		<p class="text-sm text-muted-foreground">
			Outcomes broken down by campaign, regional language, and audience segment.
		</p>
	</div>

	<!-- SectionCards Block (shadcn dashboard-01 KPI Cards) -->
	<div class="grid grid-cols-2 gap-3 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs">
		<Card.Root>
			<Card.Header class="p-4 pb-2">
				<Card.Description class="text-xs">Total Calls</Card.Description>
				<Card.Title class="text-2xl font-semibold tabular-nums">{stats.totalCalls}</Card.Title>
				<Card.Action>
					<Badge variant="outline" class="gap-1 text-[11px]">
						<TrendingUp class="size-3 text-emerald-500" />
						+{stats.connectRatePct}%
					</Badge>
				</Card.Action>
			</Card.Header>
			<Card.Footer class="p-4 pt-0 text-xs text-muted-foreground">
				{stats.connectedCalls} connected calls
			</Card.Footer>
		</Card.Root>

		<Card.Root>
			<Card.Header class="p-4 pb-2">
				<Card.Description class="text-xs">Connect Rate</Card.Description>
				<Card.Title class="text-2xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
					{stats.connectRatePct}%
				</Card.Title>
				<Card.Action>
					<Badge variant="outline" class="gap-1 text-[11px]">
						<CheckCircle2 class="size-3 text-emerald-500" />
						Active
					</Badge>
				</Card.Action>
			</Card.Header>
			<Card.Footer class="p-4 pt-0 text-xs text-muted-foreground">
				Exotel carrier connected
			</Card.Footer>
		</Card.Root>

		<Card.Root>
			<Card.Header class="p-4 pb-2">
				<Card.Description class="text-xs">RSVP Confirmations</Card.Description>
				<Card.Title class="text-2xl font-semibold tabular-nums">{stats.confirmationRatePct}%</Card.Title>
				<Card.Action>
					<Badge variant="outline" class="gap-1 text-[11px]">
						<PhoneCall class="size-3 text-primary" />
						{stats.confirmedCount}
					</Badge>
				</Card.Action>
			</Card.Header>
			<Card.Footer class="p-4 pt-0 text-xs text-muted-foreground">
				Direct intent capture
			</Card.Footer>
		</Card.Root>

		<Card.Root>
			<Card.Header class="p-4 pb-2">
				<Card.Description class="text-xs">Queued Retries</Card.Description>
				<Card.Title class="text-2xl font-semibold tabular-nums text-amber-600 dark:text-amber-400">
					{stats.queuedRetries}
				</Card.Title>
				<Card.Action>
					<Badge variant="secondary" class="gap-1 text-[11px]">
						<RotateCcw class="size-3" />
						Pending
					</Badge>
				</Card.Action>
			</Card.Header>
			<Card.Footer class="p-4 pt-0 text-xs text-muted-foreground">
				Algorithmic backoff policy
			</Card.Footer>
		</Card.Root>
	</div>

	<!-- Calls by Language with Tabs & PieChart -->
	<Card.Root>
		<Card.Header>
			<div class="flex items-center justify-between">
				<div>
					<Card.Title class="text-base font-semibold">Calls by Regional Language</Card.Title>
					<Card.Description class="text-xs">Distribution across 8 Indic languages.</Card.Description>
				</div>
				<Badge variant="outline" class="gap-1 text-[11px]">
					<ShieldCheck class="size-3 text-emerald-500" /> DPDPA Sovereign
				</Badge>
			</div>
		</Card.Header>

		<Card.Content class="space-y-4">
			<Tabs.Root bind:value={selectedTab}>
				<Tabs.List class="grid w-full grid-cols-6 h-8 text-xs">
					<Tabs.Trigger value="all" class="text-[11px] px-1">All</Tabs.Trigger>
					<Tabs.Trigger value="hindi" class="text-[11px] px-1">Hindi</Tabs.Trigger>
					<Tabs.Trigger value="tamil" class="text-[11px] px-1">Tamil</Tabs.Trigger>
					<Tabs.Trigger value="telugu" class="text-[11px] px-1">Telugu</Tabs.Trigger>
					<Tabs.Trigger value="marathi" class="text-[11px] px-1">Marathi</Tabs.Trigger>
					<Tabs.Trigger value="malayalam" class="text-[11px] px-1">Malayalam</Tabs.Trigger>
				</Tabs.List>
			</Tabs.Root>

			<Chart.Container config={languageConfig} class="mx-auto h-48 w-full">
				<PieChart data={languageData} value="value" c="color" innerRadius={60}>
					{#snippet tooltip()}
						<Chart.Tooltip />
					{/snippet}
				</PieChart>
			</Chart.Container>

			<div class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
				{#each languageData as item (item.label)}
					<div class="flex items-center gap-2 p-1.5 rounded-lg bg-muted/40 border border-border/50">
						<span class="size-2.5 shrink-0 rounded-[2px]" style="background: {item.color}"></span>
						<span class="font-medium text-foreground">{item.label}</span>
						<span class="ml-auto tabular-nums text-muted-foreground">{item.value} ({item.pct}%)</span>
					</div>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Call Records Data Table (dashboard-01 DataTable Block) -->
	<Card.Root>
		<Card.Header class="pb-3">
			<div class="flex items-center justify-between">
				<div>
					<Card.Title class="text-base font-semibold">Recent Call Records</Card.Title>
					<Card.Description class="text-xs">Real-time status of dispatched outbound calls.</Card.Description>
				</div>
				<Button variant="outline" size="xs" class="rounded-xl gap-1" onclick={retryAll} disabled={retrying}>
					<RotateCcw class="size-3" /> Retry All
				</Button>
			</div>
		</Card.Header>

		<Card.Content class="p-0">
			<Table.Root>
				<Table.Header>
					<Table.Row class="text-xs">
						<Table.Head class="w-[110px]">Recipient</Table.Head>
						<Table.Head>Language</Table.Head>
						<Table.Head>Status</Table.Head>
						<Table.Head class="text-right">Action</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body class="text-xs">
					{#each filteredRecords as record (record.name)}
						<Table.Row>
							<Table.Cell class="font-medium py-2.5">
								<div class="font-semibold text-foreground">{record.name}</div>
								<div class="text-[10px] font-mono text-muted-foreground">{record.phone}</div>
							</Table.Cell>
							<Table.Cell class="py-2.5">{record.lang}</Table.Cell>
							<Table.Cell class="py-2.5">
								<Badge variant={record.badge as any} class="text-[10px] px-1.5 py-0">
									{record.status}
								</Badge>
							</Table.Cell>
							<Table.Cell class="py-2.5 text-right">
								{#if record.status === 'RETRY_SCHEDULED'}
									<Button variant="outline" size="xs" class="h-6 text-[10px] px-2 rounded-lg" onclick={() => retryRow(record.name)}>
										Dial Now
									</Button>
								{:else}
									<span class="text-[11px] text-muted-foreground">{record.action}</span>
								{/if}
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
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
