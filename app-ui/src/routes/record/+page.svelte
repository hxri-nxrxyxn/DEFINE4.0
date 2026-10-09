<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
import { Button } from '#lib/components/ui/button/index.js';
import { startRecording, type RecordingHandle } from '#lib/audio/recorder.js';
import { campaign } from '#lib/state/campaign.svelte.js';
import Mic from '@lucide/svelte/icons/mic';
import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
import X from '@lucide/svelte/icons/x';

type Status = 'requesting' | 'listening' | 'processing' | 'error';

let status = $state<Status>('requesting');
let level = $state(0);
let handle: RecordingHandle | undefined;
let disposed = false;

onMount(() => {
	void begin();
	return () => {
		disposed = true;
		handle?.cancel();
	};
});

async function begin() {
	status = 'requesting';
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

	const form = new FormData();
	form.append('text', campaign.templateText);
	form.append('audio', audio, 'recording.webm');

	try {
		const response = await fetch('/api/process', { method: 'POST', body: form });
		const data = (await response.json()) as { text?: string };
		if (data.text) campaign.templateText = data.text;
	} catch {
		// keep existing text on failure
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
	handle?.cancel();
	// Pop back to the previous screen so we don't stack a duplicate /template
	// entry (which made back-navigation bounce back into the recorder).
	if (typeof window !== 'undefined' && window.history.length > 1) {
		window.history.back();
	} else {
		void goto('/template');
	}
}
</script>

<div
	class="relative flex h-dvh flex-col items-center justify-center gap-10 bg-muted px-6 text-foreground dark:bg-background"
>
	<Button
		variant="ghost"
		size="icon-lg"
		aria-label="Cancel"
		class="size-11 absolute top-3 right-3"
		onclick={cancel}
	>
		<X />
	</Button>

	<button
		type="button"
		class="relative flex size-56 items-center justify-center"
		aria-label={status === 'listening' ? 'Stop recording' : 'Recording'}
		onclick={status === 'listening' ? stop : undefined}
	>
		<span
			class="absolute size-40 rounded-full bg-foreground/10 transition-transform duration-75"
			style="transform: scale({1 + level * 0.4}); opacity: {0.1 + level * 0.5};"
		></span>
		<span
			class="breathe flex size-40 items-center justify-center rounded-full border border-border bg-card"
		>
			<Mic class="size-8 text-muted-foreground" />
		</span>
	</button>

	<div class="space-y-2 text-center">
		{#if status === 'error'}
			<p class="text-sm text-muted-foreground">We couldn't access your microphone.</p>
			<Button variant="outline" class="h-11 px-5 text-base" onclick={begin}>
				<RotateCcw />
				Try again
			</Button>
		{:else}
			<p class="text-base font-medium">
				{status === 'listening' ? 'Listening…' : status === 'processing' ? 'Writing your template…' : 'Starting…'}
			</p>
			<p class="text-sm text-muted-foreground">Speak naturally — we'll stop when you're done.</p>
		{/if}
	</div>
</div>

<style>
	.breathe {
		animation: breathe 3.6s ease-in-out infinite;
	}

	@keyframes breathe {
		0%,
		100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.14);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.breathe {
			animation: none;
		}
	}
</style>
