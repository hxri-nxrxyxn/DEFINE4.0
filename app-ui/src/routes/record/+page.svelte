<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { startConvAISession, type ConvAISession } from '#lib/audio/convai.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import { toast } from 'svelte-sonner';

	type Status = 'requesting' | 'listening' | 'speaking' | 'processing' | 'error';

	let status = $state<Status>('requesting');
	let level = $state(0);
	let liveTranscript = $state('');
	let agentResponseText = $state('');
	let convSession: ConvAISession | undefined;
	let disposed = false;

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
			convSession = await startConvAISession({
				onLevel: (val) => (level = val),
				onUserMessage: (msg) => {
					liveTranscript = msg;
				},
				onAgentMessage: (msg) => {
					agentResponseText = msg;
					status = 'speaking';
					campaign.templateText = msg.trim();
				},
				onAudioPlay: () => {
					status = 'speaking';
				},
				onError: (err) => {
					console.error('ElevenLabs ConvAI session error:', err);
					if (!disposed) status = 'error';
				},
				onClose: () => {
					if (!disposed && status !== 'processing') {
						// session finished naturally
					}
				}
			});
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

	async function finish() {
		status = 'processing';
		convSession?.stop();

		const finalPrompt = agentResponseText.trim() || liveTranscript.trim() || campaign.templateText.trim();
		if (finalPrompt) {
			campaign.templateText = finalPrompt;
			toast.success('Live ElevenLabs Conversational AI script saved!');
		}

		leave();
	}

	function stop() {
		void finish();
	}

	function cancel() {
		leave();
	}

	function leave() {
		if (disposed) return;
		disposed = true;
		convSession?.stop();
		void goto('/template');
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
				Speak now to ElevenLabs Voice Agent…
			{:else if status === 'speaking'}
				ElevenLabs Agent is speaking…
			{:else if status === 'processing'}
				Saving conversation script…
			{:else}
				Microphone / Session Error
			{/if}
		</h1>
		<p class="text-xs text-muted-foreground min-h-12 px-2">
			{#if agentResponseText}
				"Agent: {agentResponseText}"
			{:else if liveTranscript}
				"You: {liveTranscript}"
			{:else if status === 'listening'}
				Speak directly to the ElevenLabs Conversational Voice Agent.
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
				Done Recording
			</Button>
		{:else}
			<Button variant="ghost" size="sm" class="rounded-xl px-4" onclick={cancel}>
				Cancel
			</Button>
		{/if}
	</div>
</div>
