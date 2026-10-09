<script lang="ts">
	import { goto } from '$app/navigation';
	import { PieChart } from 'layerchart';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Chart from '#lib/components/ui/chart/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Download from '@lucide/svelte/icons/download';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Voicemail from '@lucide/svelte/icons/voicemail';
	import { toast } from 'svelte-sonner';

	const stats = [
		{ label: 'Calls placed', value: '1,284' },
		{ label: 'Queued retries', value: '37' }
	];

	const languageData = [
		{ key: 'hi', label: 'Hindi', value: 244, color: 'var(--chart-1)' },
		{ key: 'ta', label: 'Tamil', value: 170, color: 'var(--chart-2)' },
		{ key: 'te', label: 'Telugu', value: 139, color: 'var(--chart-3)' },
		{ key: 'mr', label: 'Marathi', value: 108, color: 'var(--chart-4)' }
	];

	const languageConfig = {
		hi: { label: 'Hindi', color: 'var(--chart-1)' },
		ta: { label: 'Tamil', color: 'var(--chart-2)' },
		te: { label: 'Telugu', color: 'var(--chart-3)' },
		mr: { label: 'Marathi', color: 'var(--chart-4)' }
	} satisfies Chart.ChartConfig;

	const retries = [
		{ campaign: 'Diwali Seminar', count: 18 },
		{ campaign: 'City Clinic Reminders', count: 12 },
		{ campaign: 'School Parents Sync', count: 7 }
	];

	function retryAll() {
		toast.success('Retrying non-responders', { description: '37 calls queued for the next window.' });
	}

	function exportReport() {
		toast.success('Report exported', { description: 'campaign-report.csv (demo).' });
	}
</script>

<div class="space-y-6 py-2">
	<div class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Dashboard</h1>
		<p class="text-sm text-muted-foreground">Outcomes by campaign, language, and segment.</p>
	</div>

	<div class="grid grid-cols-3 gap-3">
		{#each stats as stat (stat.label)}
			<Card.Root class="gap-2">
				<Card.Content class="space-y-1 px-4 py-4">
					<p class="text-xs text-muted-foreground">{stat.label}</p>
					<p class="text-xl font-semibold tabular-nums">{stat.value}</p>
				</Card.Content>
			</Card.Root>
		{/each}
		<Card.Root class="gap-2">
			<Card.Content class="flex flex-col items-center gap-1 px-4 py-3">
				<div
					class="grid size-12 place-items-center rounded-full"
					style="background: conic-gradient(var(--foreground) 68%, var(--muted) 0)"
				>
					<div
						class="grid size-9 place-items-center rounded-full bg-card text-xs font-semibold"
					>
						68%
					</div>
				</div>
				<p class="text-xs text-muted-foreground">Connect rate</p>
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
				{#each languageData as item (item.key)}
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
			{#each retries as item (item.campaign)}
				<div class="flex items-center justify-between gap-3">
					<div class="flex items-center gap-2">
						<Voicemail class="size-4 text-muted-foreground" />
						<span class="text-sm">{item.campaign}</span>
					</div>
					<span class="text-sm tabular-nums text-muted-foreground">{item.count}</span>
				</div>
			{/each}
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
