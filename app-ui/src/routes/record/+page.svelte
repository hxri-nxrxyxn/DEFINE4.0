<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { startConvAISession, type ConvAISession } from '#lib/audio/convai.js';
	import { campaign, type OutcomeDisposition } from '#lib/state/campaign.svelte.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';

	type Status = 'requesting' | 'listening' | 'speaking' | 'processing' | 'done' | 'error';

	const OUTCOME_LABEL: Record<string, string> = {
		confirmed: 'Confirmed',
		not_available: 'Not available — moved to retry list',
		declined: 'Declined',
		opt_out: 'Opted out',
		no_response: 'No response — moved to retry list'
	};

	const contact = campaign.activeRecipient;
	const contactName = contact?.name?.trim() || campaign.userName || 'there';
	const contactLanguage = contact?.language || 'English';
	const contactPhone = contact?.phone || '';

	// Guard against a stale draft that captured the agent's own closing line
	// (older builds wrote agent replies into templateText, which then became
	// the next call's first message).
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
			// Configure the shared agent from the /template script before dialing.
			await fetch('/api/convai/configure', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					script: cleanScript(campaign.templateText),
					name: contactName,
					language: contactLanguage
				})
			}).catch(() => {});

			convSession = await startConvAISession(
				{
					onLevel: (val) => (level = val),
					onUserMessage: (msg) => {
						userSpoke = true;
						liveTranscript = msg;
					},
					onAgentMessage: (msg) => {
						agentResponseText = msg;
					},
					onAudioPlay: () => {
						status = 'speaking';
					},
					onAudioEnd: () => {
						if (!disposed && status !== 'processing' && status !== 'done') status = 'listening';
					},
					onOutcome: (o) => handleOutcome(o),
					onError: (err) => {
						console.error('ElevenLabs ConvAI session error:', err);
						if (!disposed) status = 'error';
					},
					onClose: () => {
						if (disposed || outcome) return;
						if (!userSpoke) finalize('no_response');
					}
				},
				{ name: contactName, language: contactLanguage }
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

	function handleOutcome(o: string) {
		if (disposed || outcome) return;
		outcome = o;
		status = 'processing';
		// Let the agent finish its goodbye before hanging up.
		setTimeout(() => {
			if (!disposed) finalize(o);
		}, 2500);
	}

	function finalize(o: string) {
		if (disposed) return;
		disposed = true;
		status = 'done';
		outcome = o;
		try {
			convSession?.stop();
		} catch {}
		if (contactPhone) {
			try {
				campaign.recordOutcome(contactPhone, o as OutcomeDisposition, agentResponseText || liveTranscript);
			} catch {}
		}
		toast.success(`Call ended — ${OUTCOME_LABEL[o] ?? o}`);
		setTimeout(() => void goto('/dashboard'), 1600);
	}

	function exit(target: string) {
		disposed = true;
		try {
			convSession?.stop();
		} catch {}
		void goto(target);
	}

	function stop() {
		status = 'processing';
		finalize(outcome ?? (userSpoke ? 'confirmed' : 'no_response'));
	}

	function cancel() {
		exit('/template');
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
				Speak now, {contactName}…
			{:else if status === 'speaking'}
				ElevenLabs Agent is speaking…
			{:else if status === 'processing'}
				Ending the call…
			{:else if status === 'done'}
				{OUTCOME_LABEL[outcome ?? ''] ?? 'Call complete'}
			{:else}
				Microphone / Session Error
			{/if}
		</h1>
		<p class="text-xs text-muted-foreground min-h-12 px-2">
			{#if status === 'done'}
				{OUTCOME_LABEL[outcome ?? ''] ?? 'Call complete'}
			{:else if agentResponseText}
				"Agent: {agentResponseText}"
			{:else if liveTranscript}
				"You: {liveTranscript}"
			{:else if status === 'listening'}
				Speak naturally — the agent will wrap up the call automatically.
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

	<div class="mb-4 text-center">
		{#if status === 'listening'}
			<Button variant="outline" size="sm" class="rounded-xl px-4" onclick={stop}>
				End call
			</Button>
		{:else if status === 'done'}
			<Button variant="outline" size="sm" class="rounded-xl px-4" onclick={() => goto('/dashboard')}>
				View dashboard
			</Button>
		{:else}
			<Button variant="ghost" size="sm" class="rounded-xl px-4" onclick={cancel}>
				Cancel
			</Button>
		{/if}
	</div>
</div>
