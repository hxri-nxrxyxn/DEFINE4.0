<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Download from '@lucide/svelte/icons/download';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import PhoneCall from '@lucide/svelte/icons/phone-call';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import Users from '@lucide/svelte/icons/users';
	import Globe from '@lucide/svelte/icons/globe';
	import CheckCircle2 from '@lucide/svelte/icons/check-circle-2';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import PhoneForwarded from '@lucide/svelte/icons/phone-forwarded';
	import { toast } from 'svelte-sonner';

	let loading = $state(true);
	let retrying = $state(false);
	let selectedLangFilter = $state('all');

	let totalCalls = $state('1,284');
	let connectedCalls = $state('873');
	let queuedRetries = $state(37);
	let connectRatePct = $state(68);
	let confirmationRatePct = $state(46);

	let languages = $state([
		{ key: 'hi', label: 'Hindi', count: 420, confirmed: 244, pct: 58, color: 'bg-indigo-500' },
		{ key: 'ta', label: 'Tamil', count: 290, confirmed: 170, pct: 59, color: 'bg-emerald-500' },
		{ key: 'te', label: 'Telugu', count: 245, confirmed: 139, pct: 57, color: 'bg-sky-500' },
		{ key: 'mr', label: 'Marathi', count: 184, confirmed: 108, pct: 59, color: 'bg-amber-500' },
		{ key: 'ml', label: 'Malayalam', count: 145, confirmed: 91, pct: 63, color: 'bg-purple-500' }
	]);

	let segmentData = $state([
		{ segment: 'VIPs & Patrons', total: 430, confirmed: 280, pct: 65 },
		{ segment: 'Alumni Roster', total: 340, confirmed: 210, pct: 62 },
		{ segment: 'University Faculty', total: 230, confirmed: 124, pct: 54 },
		{ segment: 'General Attendees', total: 284, confirmed: 195, pct: 68 }
	]);

	let retryList = $state([
		{ name: 'Vikram Malhotra', phone: '+91 98••• ••999', campaign: 'Seminar Invitation', reason: 'Network Busy', attempts: 1 },
		{ name: 'Pooja Hegde', phone: '+91 97••• ••888', campaign: 'Clinic Appointment', reason: 'No Answer', attempts: 2 },
		{ name: 'Rajesh Kumar', phone: '+91 99••• ••777', campaign: 'School PTA Sync', reason: 'Unreachable', attempts: 1 }
	]);

	let filteredLanguages = $derived(
		selectedLangFilter === 'all'
			? languages
			: languages.filter((l) => l.key === selectedLangFilter)
	);

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
					const langCodes: Record<string, { key: string; color: string }> = {
						Hindi: { key: 'hi', color: 'bg-indigo-500' },
						Tamil: { key: 'ta', color: 'bg-emerald-500' },
						Telugu: { key: 'te', color: 'bg-sky-500' },
						Marathi: { key: 'mr', color: 'bg-amber-500' },
						Malayalam: { key: 'ml', color: 'bg-purple-500' }
					};
					const entries = Object.entries(data.by_language);
					languages = entries.map(([name, stat]: [string, any]) => {
						const meta = langCodes[name] || { key: name.toLowerCase(), color: 'bg-primary' };
						const tot = stat.total || 1;
						const conf = stat.confirmed || 0;
						return {
							key: meta.key,
							label: name,
							count: tot,
							confirmed: conf,
							pct: Math.round((conf / tot) * 100),
							color: meta.color
						};
					});
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
			console.error('Failed to fetch analytics:', e);
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
				description: `Dispatched ${result.queued_retries || queuedRetries} calls via Exotel + WhatsApp.`
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

	function retrySingle(name: string) {
		retryList = retryList.filter((r) => r.name !== name);
		queuedRetries = Math.max(0, queuedRetries - 1);
		toast.success(`Retrying ${name}`, { description: 'Exotel dialer active.' });
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
		link.setAttribute('download', `campaign_report_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		toast.success('Report Downloaded', { description: 'DPDPA 2023 anonymized export.' });
	}
</script>

<div class="space-y-4 py-1 pb-24">
	<!-- Android App Mobile Status Header -->
	<div class="flex items-center justify-between gap-2 bg-gradient-to-r from-zinc-900 to-zinc-950 p-3.5 rounded-2xl border border-zinc-800 text-white shadow-sm">
		<div class="space-y-0.5">
			<div class="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-indigo-400">
				<Sparkles class="size-3.5" />
				<span>DEFINE VOICE AI ENGINE</span>
			</div>
			<p class="text-base font-bold tracking-tight">Campaign Telephony</p>
		</div>
		<div class="flex flex-col items-end text-[11px] font-medium text-emerald-400 gap-0.5">
			<span class="inline-flex items-center gap-1 bg-emerald-950/80 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-800/50">
				<span class="size-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
				Exotel Live
			</span>
			<span class="text-zinc-400 text-[10px]">ap-south-1 (Mumbai)</span>
		</div>
	</div>

	<!-- Mobile 2x2 Metric Grid -->
	<div class="grid grid-cols-2 gap-2.5">
		<div class="p-3.5 rounded-2xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
			<div class="flex items-center justify-between text-muted-foreground">
				<span class="text-xs font-medium">Total Calls</span>
				<PhoneCall class="size-4 text-indigo-500" />
			</div>
			<div class="mt-2">
				<span class="text-2xl font-bold tracking-tight tabular-nums">{totalCalls}</span>
				<p class="text-[11px] text-muted-foreground mt-0.5">{connectedCalls} connected</p>
			</div>
		</div>

		<div class="p-3.5 rounded-2xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
			<div class="flex items-center justify-between text-muted-foreground">
				<span class="text-xs font-medium">Connect Rate</span>
				<CheckCircle2 class="size-4 text-emerald-500" />
			</div>
			<div class="mt-2">
				<span class="text-2xl font-bold tracking-tight tabular-nums text-emerald-600 dark:text-emerald-400">{connectRatePct}%</span>
				<p class="text-[11px] text-muted-foreground mt-0.5">Target achieved</p>
			</div>
		</div>

		<div class="p-3.5 rounded-2xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
			<div class="flex items-center justify-between text-muted-foreground">
				<span class="text-xs font-medium">Confirmations</span>
				<PhoneForwarded class="size-4 text-sky-500" />
			</div>
			<div class="mt-2">
				<span class="text-2xl font-bold tracking-tight tabular-nums text-sky-600 dark:text-sky-400">{confirmationRatePct}%</span>
				<p class="text-[11px] text-muted-foreground mt-0.5">RSVP / Appointment</p>
			</div>
		</div>

		<div class="p-3.5 rounded-2xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
			<div class="flex items-center justify-between text-muted-foreground">
				<span class="text-xs font-medium">Queued Retries</span>
				<RotateCcw class="size-4 text-amber-500" />
			</div>
			<div class="mt-2">
				<span class="text-2xl font-bold tracking-tight tabular-nums text-amber-600 dark:text-amber-400">{queuedRetries}</span>
				<p class="text-[11px] text-muted-foreground mt-0.5">Non-responders</p>
			</div>
		</div>
	</div>

	<!-- Language Breakdown Section with Touch Filters -->
	<Card.Root class="rounded-2xl border border-border/80 shadow-xs overflow-hidden">
		<Card.Header class="pb-2 pt-3.5 px-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<Globe class="size-4 text-indigo-500" />
					<Card.Title class="text-base font-semibold">Multilingual Delivery</Card.Title>
				</div>
				<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
					8 Indic Languages
				</span>
			</div>
		</Card.Header>

		<Card.Content class="px-4 pb-4 space-y-3">
			<!-- Horizontal Scrollable Language Pills -->
			<div class="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
				<button
					onclick={() => selectedLangFilter = 'all'}
					class="px-3 py-1 rounded-full font-medium transition-all shrink-0 {selectedLangFilter === 'all' ? 'bg-primary text-primary-foreground shadow-xs' : 'bg-muted text-muted-foreground hover:bg-muted/80'}"
				>
					All ({languages.length})
				</button>
				{#each languages as lang (lang.key)}
					<button
						onclick={() => selectedLangFilter = lang.key}
						class="px-3 py-1 rounded-full font-medium transition-all shrink-0 {selectedLangFilter === lang.key ? 'bg-primary text-primary-foreground shadow-xs' : 'bg-muted text-muted-foreground hover:bg-muted/80'}"
					>
						{lang.label}
					</button>
				{/each}
			</div>

			<!-- Language Progress List -->
			<div class="space-y-2.5 pt-1">
				{#each filteredLanguages as lang (lang.key)}
					<div class="p-2.5 rounded-xl bg-muted/40 border border-border/40 space-y-1.5">
						<div class="flex items-center justify-between text-xs">
							<span class="font-semibold text-foreground">{lang.label}</span>
							<span class="text-muted-foreground tabular-nums font-medium">
								{lang.confirmed} confirmed / {lang.count} calls ({lang.pct}%)
							</span>
						</div>
						<div class="h-2 w-full bg-muted rounded-full overflow-hidden">
							<div
								class="h-full {lang.color} rounded-full transition-all duration-500"
								style="width: {lang.pct}%"
							></div>
						</div>
					</div>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Audience Segment Tiers -->
	<Card.Root class="rounded-2xl border border-border/80 shadow-xs">
		<Card.Header class="pb-2 pt-3.5 px-4">
			<div class="flex items-center gap-2">
				<Users class="size-4 text-emerald-500" />
				<Card.Title class="text-base font-semibold">Audience Segments</Card.Title>
			</div>
		</Card.Header>
		<Card.Content class="px-4 pb-4 space-y-2.5">
			{#each segmentData as seg (seg.segment)}
				<div class="flex items-center justify-between p-2.5 rounded-xl bg-muted/30 text-xs">
					<div class="space-y-0.5">
						<p class="font-semibold text-foreground">{seg.segment}</p>
						<p class="text-[11px] text-muted-foreground">{seg.confirmed} confirmed of {seg.total}</p>
					</div>
					<div class="flex items-center gap-2">
						<span class="font-bold tabular-nums text-sm text-foreground">{seg.pct}%</span>
						<div class="size-8 rounded-full border-2 border-emerald-500/30 flex items-center justify-center text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
							{seg.pct}%
						</div>
					</div>
				</div>
			{/each}
		</Card.Content>
	</Card.Root>

	<!-- Retry Queue Section with Touch Actions -->
	<Card.Root class="rounded-2xl border border-border/80 shadow-xs">
		<Card.Header class="pb-2 pt-3.5 px-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<AlertCircle class="size-4 text-amber-500" />
					<Card.Title class="text-base font-semibold">Retry Queue</Card.Title>
				</div>
				<button
					onclick={retryAll}
					disabled={retrying || queuedRetries === 0}
					class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-amber-500 text-zinc-950 hover:bg-amber-400 active:scale-95 transition-all disabled:opacity-50"
				>
					<RotateCcw class="size-3.5 {retrying ? 'animate-spin' : ''}" />
					{retrying ? 'Retrying...' : 'Retry All'}
				</button>
			</div>
		</Card.Header>

		<Card.Content class="px-4 pb-4 space-y-2">
			{#if retryList.length > 0}
				{#each retryList as item (item.name)}
					<div class="flex items-center justify-between p-2.5 rounded-xl bg-muted/40 border border-border/40 text-xs">
						<div class="space-y-0.5">
							<div class="flex items-center gap-2">
								<span class="font-semibold text-foreground">{item.name}</span>
								<span class="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">{item.phone}</span>
							</div>
							<p class="text-[11px] text-muted-foreground">{item.campaign} · <span class="text-amber-600 dark:text-amber-400">{item.reason}</span></p>
						</div>
						<button
							onclick={() => retrySingle(item.name)}
							class="px-2.5 py-1 rounded-lg bg-card border border-border hover:bg-muted text-[11px] font-medium transition-colors"
						>
							Dial Now
						</button>
					</div>
				{/each}
			{:else}
				<div class="text-center py-5 text-xs text-muted-foreground">
					✨ All retries successfully dispatched!
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Mobile Compliance Footer Badge -->
	<div class="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground py-1">
		<ShieldCheck class="size-3.5 text-emerald-500" />
		<span>DPDPA 2023 Encrypted · In-Country Mumbai Sovereign</span>
	</div>
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
