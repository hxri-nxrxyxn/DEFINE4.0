<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';
	import { startConvAISession, type ConvAISession } from '#lib/audio/convai.js';
	import { campaign, type OutcomeDisposition } from '#lib/state/campaign.svelte.js';
	import { apiUrl } from '#lib/config.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';

	type Status = 'requesting' | 'listening' | 'speaking' | 'processing' | 'done' | 'error';

	// Assistant mode (default): turn what you say into a call script.
	// Call mode (?call=1): play the script to a recipient and capture the outcome.
	const callMode = page.url.searchParams.has('call');

	const OUTCOME_LABEL: Record<string, string> = {
		confirmed: 'Confirmed',
		not_available: 'Not available — moved to retry list',
		reschedule: 'Rescheduled — moved to retry list',
		declined: 'Declined',
		opt_out: 'Opted out',
		no_response: 'No response — moved to retry list'
	};

	const contact = campaign.activeRecipient;
	const contactName = contact?.name?.trim() || 'there';
	const operatorName = campaign.userName || 'Hari';
	// Build mode talks to the app's operator; call mode talks to the roster contact.
	const agentName = callMode ? contactName : operatorName;
	const contactLanguage = contact?.language || 'English';
	const contactPhone = contact?.phone || '';

	function stripTags(text: string): string {
		return text.replace(/\[[^\]]*\]/g, '').replace(/\s+/g, ' ').trim();
	}

	// Guard against a stale draft that captured the agent's own closing line.
	function cleanScript(text: string): string {
		const t = text.trim();
		if (!t) return '';
		const looksLikeFarewell =
			t.length < 80 &&
			/(goodbye|\bbye\b|thank you for your time|thanks for your time|have a (great|good|nice) day)/i.test(
				t
			);
		if (looksLikeFarewell) {
			campaign.templateText = '';
			return '';
		}
		return t;
	}

	let status = $state<Status>('requesting');
	let level = $state(0);
	let liveTranscript = $state('');
	let agentResponseText = $state('');
	let draftScript = $state('');
	let outcome = $state<string | null>(null);
	let convSession: ConvAISession | undefined;
	let disposed = false;
	let userSpoke = false;

	onMount(() => {
		void begin();
		return () => {
			disposed = true;
			convSession?.stop();
		};
	});

	async function begin() {
		status = 'requesting';
		liveTranscript = '';
		agentResponseText = '';

		try {
			// Configure the shared agent (assistant or caller) before connecting.
			for (const base of ['http://x1carbon:8765', 'http://10.80.0.48:8765', 'http://localhost:8765', '']) {
				try {
					const ep = base ? `${base}/api/convai/configure` : apiUrl('/api/convai/configure');
					await fetch(ep, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							mode: callMode ? 'call' : 'build',
							script: cleanScript(campaign.templateText),
							name: agentName,
							language: callMode ? contactLanguage : 'English'
						}),
						signal: AbortSignal.timeout(2000)
					});
					break;
				} catch {
					// continue
				}
			}

			convSession = await startConvAISession(
				{
					onLevel: (val) => (level = val),
					onUserMessage: (msg) => {
						userSpoke = true;
						liveTranscript = msg;
					},
					onAgentMessage: (msg) => {
						agentResponseText = stripTags(msg);
					},
					onAudioPlay: () => {
						status = 'speaking';
					},
					onAudioEnd: () => {
						if (!disposed && status !== 'processing' && status !== 'done') status = 'listening';
					},
					onScript: (script) => handleScript(script),
					onConfirmScript: (script) => handleConfirmScript(script),
					onOutcome: (o) => handleOutcome(o),
					onError: (err) => {
						console.error('ElevenLabs ConvAI session error:', err);
						if (!disposed) status = 'error';
					},
					onClose: () => {
						if (disposed) return;
						if (callMode && !outcome && !userSpoke) finalize('no_response');
					}
				},
				{ name: agentName, language: callMode ? contactLanguage : 'English' }
			);
			if (disposed) {
				convSession.stop();
				return;
			}
			status = 'listening';
		} catch (e) {
			console.error('Failed to start ElevenLabs ConvAI session:', e);
			if (!disposed) status = 'error';
		}
	}

	function go(path: string) {
		try {
			void goto(path);
		} catch {
			if (typeof window !== 'undefined') window.location.href = path;
		}
	}

	// Assistant mode: the agent handed us a draft — show it, keep iterating.
	function handleScript(script: string) {
		if (disposed || callMode) return;
		const s = stripTags(script);
		if (!s) return;
		draftScript = s;
	}

	// Assistant mode: the operator approved the script — commit it.
	function handleConfirmScript(script: string) {
		if (disposed || callMode) return;
		commitTemplate(stripTags(script) || draftScript);
	}

	function commitTemplate(script: string) {
		if (disposed) return;
		const s = (script || '').trim();
		if (!s) {
			toast.error('No script yet', { description: 'Ask the assistant to draft one first.' });
			return;
		}
		campaign.templateText = s;
		status = 'done';
		disposed = true;
		try {
			convSession?.stop();
		} catch {}
		toast.success('Template ready', { description: 'You can still edit it here.' });
		setTimeout(() => go('/template'), 700);
	}

	function handleOutcome(o: string) {
		if (!callMode || disposed || outcome) return;
		outcome = o;
		status = 'processing';
		// Let the agent finish its goodbye before hanging up.
		setTimeout(() => {
			if (!disposed) finalize(o);
		}, 2000);
	}

	function finalize(o: string) {
		if (disposed) return;
		disposed = true;
		status = 'done';
		outcome = o;
		try {
			convSession?.stop();
		} catch {}
		if (callMode && contactPhone) {
			try {
				campaign.recordOutcome(contactPhone, o as OutcomeDisposition, agentResponseText || liveTranscript);
			} catch {}
		}
		toast.success(`Call ended — ${OUTCOME_LABEL[o] ?? o}`);
		setTimeout(() => go('/dashboard'), 900);
	}

	function exit(target: string) {
		disposed = true;
		try {
			convSession?.stop();
		} catch {}
		void goto(target);
	}

	function stop() {
		if (callMode) {
			status = 'processing';
			finalize(outcome ?? (userSpoke ? 'confirmed' : 'no_response'));
		} else if (draftScript.trim()) {
			commitTemplate(draftScript);
		} else {
			exit('/template');
		}
	}

	function cancel() {
		exit(callMode ? '/dashboard' : '/template');
	}
</script>

<div
	class="relative flex h-dvh flex-col items-center justify-between py-12 px-6 bg-background text-foreground"
>
	<Button
		variant="ghost"
		size="icon-lg"
		aria-label="Cancel"
		class="size-11 absolute top-4 right-4"
		onclick={cancel}
	>
		<X />
	</Button>

	<div class="mt-8 text-center space-y-2 max-w-sm">
		<h1 class="text-xl font-semibold tracking-tight">
			{#if status === 'requesting'}
				Connecting to ElevenLabs Voice Agent…
			{:else if status === 'listening'}
				{callMode ? `Speak now, ${contactName}…` : 'Tell the agent what the call should say…'}
			{:else if status === 'speaking'}
				ElevenLabs Agent is speaking…
			{:else if status === 'processing'}
				{callMode ? 'Ending the call…' : 'Writing the script…'}
			{:else if status === 'done'}
				{callMode ? (OUTCOME_LABEL[outcome ?? ''] ?? 'Call complete') : 'Script ready'}
			{:else}
				Microphone / Session Error
			{/if}
		</h1>
		<p class="text-xs text-muted-foreground min-h-12 px-2">
			{#if status === 'done'}
				{callMode ? (OUTCOME_LABEL[outcome ?? ''] ?? 'Call complete') : campaign.templateText}
			{:else if agentResponseText}
				"Agent: {agentResponseText}"
			{:else if liveTranscript}
				"You: {liveTranscript}"
			{:else if status === 'listening'}
				{callMode
					? 'Speak naturally — the agent will wrap up the call automatically.'
					: draftScript
						? 'Say "change the venue to …" to edit, or "done" (or tap Use this template) to keep it.'
						: 'Tell the assistant the occasion, e.g. "design an RSVP script for our school PTA meeting".'}
			{:else}
				Please allow microphone access.
			{/if}
		</p>
	</div>

	<!-- Pulsing Mic Visualizer Button -->
	<div class="relative flex items-center justify-center">
		{#if status === 'listening'}
			<div
				class="absolute rounded-full bg-primary/20 transition-all duration-75"
				style="width: {120 + level * 140}px; height: {120 + level * 140}px"
			></div>
			<div
				class="absolute rounded-full bg-primary/10 transition-all duration-75 animate-ping"
				style="width: 140px; height: 140px"
			></div>
		{/if}

		<button
			type="button"
			onclick={stop}
			disabled={status !== 'listening'}
			class="relative size-24 grid place-items-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform active:scale-95 disabled:opacity-50"
		>
			{#if status === 'processing'}
				<div class="size-8 rounded-full border-4 border-primary-foreground border-t-transparent animate-spin"></div>
			{:else if status === 'done'}
				<Check class="size-10" />
			{:else if status === 'listening'}
				<Check class="size-10" />
			{:else}
				<Mic class="size-10" />
			{/if}
		</button>
	</div>

	{#if !callMode && draftScript}
		<div class="mt-6 w-full max-w-md rounded-xl border border-border bg-muted/30 p-3 text-left">
			<p class="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
				Draft script
			</p>
			<p class="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{draftScript}</p>
		</div>
	{/if}

	<div class="mt-6 mb-4 flex flex-wrap items-center justify-center gap-2">
		{#if status === 'listening'}
			{#if callMode}
				<Button variant="outline" size="sm" class="rounded-xl px-4" onclick={stop}>
					End call
				</Button>
			{:else}
				{#if draftScript}
					<Button size="sm" class="rounded-xl px-4" onclick={() => commitTemplate(draftScript)}>
						Use this template
					</Button>
				{/if}
				<Button variant="ghost" size="sm" class="rounded-xl px-4" onclick={cancel}>
					Cancel
				</Button>
			{/if}
		{:else if status === 'done'}
			<Button
				variant="outline"
				size="sm"
				class="rounded-xl px-4"
				onclick={() => go(callMode ? '/dashboard' : '/template')}
			>
				{callMode ? 'View dashboard' : 'Back to template'}
			</Button>
		{:else}
			<Button variant="ghost" size="sm" class="rounded-xl px-4" onclick={cancel}>
				Cancel
			</Button>
		{/if}
	</div>
</div>
