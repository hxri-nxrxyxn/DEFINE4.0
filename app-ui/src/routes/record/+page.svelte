<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { startRecording, type RecordingHandle } from '#lib/audio/recorder.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';

	type Status = 'requesting' | 'listening' | 'processing' | 'error';

	let status = $state<Status>('requesting');
	let level = $state(0);
	let liveTranscript = $state('');
	let handle: RecordingHandle | undefined;
	let recognition: any = null;
	let disposed = false;

	onMount(() => {
		void begin();
		return () => {
			disposed = true;
			if (recognition) {
				try { recognition.stop(); } catch {}
			}
			handle?.cancel();
		};
	});

	async function begin() {
		status = 'requesting';
		liveTranscript = '';

		// Start Web Speech Recognition if supported in browser
		if (typeof window !== 'undefined') {
			const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
			if (SpeechRecognition) {
				try {
					recognition = new SpeechRecognition();
					recognition.continuous = true;
					recognition.interimResults = true;
					recognition.lang = 'en-US';
					recognition.onerror = (err: any) => {
						console.warn('SpeechRecognition error:', err);
					};
					recognition.onresult = (event: any) => {
						let text = '';
						for (let i = 0; i < event.results.length; i++) {
							text += event.results[i][0].transcript + ' ';
						}
						liveTranscript = text.trim();
					};
					recognition.start();
				} catch (e) {
					console.warn('SpeechRecognition initialization error:', e);
				}
			}
		}

		try {
			const recording = await startRecording({
				onLevel: (value) => (level = value),
				onStop: (audio) => void finish(audio),
				onError: () => (status = 'error')
			});
			if (disposed) {
				recording.cancel();
				return;
			}
			handle = recording;
			status = 'listening';
		} catch {
			if (!disposed) status = 'error';
		}
	}

	async function finish(audio: Blob) {
		status = 'processing';
		level = 0;

		if (recognition) {
			try { recognition.stop(); } catch {}
		}

		const form = new FormData();
		form.append('text', campaign.templateText);
		form.append('transcript', liveTranscript);
		form.append('audio', audio, 'recording.webm');

		try {
			const response = await fetch('/api/process', { method: 'POST', body: form });
			const data = (await response.json()) as { text?: string };
			if (data.text) {
				campaign.templateText = data.text;
			}
		} catch (e) {
			if (liveTranscript) {
				campaign.templateText = `Hello {name},\n\n${liveTranscript}\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.`;
			}
		}

		leave();
	}

	function stop() {
		handle?.stop();
	}

	function cancel() {
		leave();
	}

	function leave() {
		if (disposed) return;
		disposed = true;
		if (recognition) {
			try { recognition.stop(); } catch {}
		}
		handle?.cancel();
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
				Accessing microphone…
			{:else if status === 'listening'}
				Speak now…
			{:else if status === 'processing'}
				Processing with ElevenLabs AI…
			{:else}
				Microphone error
			{/if}
		</h1>
		<p class="text-xs text-muted-foreground min-h-12 px-2">
			{#if liveTranscript}
				"{liveTranscript}"
			{:else if status === 'listening'}
				Describe your event details or message. We will generate the voice script.
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
