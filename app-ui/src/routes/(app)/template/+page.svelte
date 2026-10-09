<script lang="ts">
	import { goto } from '$app/navigation';
	import { onDestroy } from 'svelte';
	import { ActionBar } from '#lib/components/action-bar/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { campaign } from '#lib/state/campaign.svelte.js';
	import { apiUrl } from '#lib/config.js';
	import Mic from '@lucide/svelte/icons/mic';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Volume2 from '@lucide/svelte/icons/volume-2';
	import { toast } from 'svelte-sonner';

	let playing = $state(false);
	let recording = $state(false);
	let transcribing = $state(false);
	let mediaRecorder: MediaRecorder | undefined;
	let chunks: BlobPart[] = [];

	const templateTips = [
		{
			label: 'Tech Seminar',
			text: 'Hello {name},\n\nWe are hosting an All-India Technology Seminar in Mumbai next Saturday at 10:00 AM. Please confirm your seat.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: 'Clinic Appointment',
			text: 'Hello {name},\n\nThis is a reminder for your upcoming medical consultation at City Health Clinic tomorrow at 3:00 PM.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: 'School PTA Sync',
			text: 'Hello {name},\n\nAnnual Parent-Teacher Association sync is scheduled for this Friday at 4:00 PM in the main school auditorium.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: 'Payment Invoice',
			text: 'Hello {name},\n\nYour monthly subscription invoice #INV-2026 is due tomorrow. Please confirm payment dispatch.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		},
		{
			label: 'Event Update',
			text: 'Hello {name},\n\nImportant update regarding venue change for the Annual Conference. The event is now at Grand Convention Hall.\n\nPress 1 to confirm, press 2 to reschedule, or press 9 to opt out.'
		}
	];

	function selectTip(text: string, label: string) {
		campaign.templateText = text;
		toast.success(`Loaded ${label} template`);
	}

	function reset() {
		campaign.reset();
		toast.info('Template reset');
	}

	async function playAudio() {
		if (!campaign.templateText.trim()) return;
		playing = true;
		toast.info('Synthesizing ElevenLabs Voice…');
		try {
			const res = await fetch(apiUrl('/api/process'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ text: campaign.templateText })
			});
			const data = await res.json();
			if (data.audio_base_64) {
				const player = new Audio(`data:audio/mpeg;base64,${data.audio_base_64}`);
				player.onended = () => (playing = false);
				void player.play();
				toast.success('Playing ElevenLabs Voice Audio');
			} else {
				playing = false;
				toast.error('Voice audio unavailable');
			}
		} catch (e) {
			playing = false;
			toast.error('Error generating audio preview');
		}
	}

	async function toggleMic() {
		if (recording) {
			mediaRecorder?.stop();
			return;
		}

		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			const mime = MediaRecorder.isTypeSupported('audio/webm')
				? 'audio/webm'
				: MediaRecorder.isTypeSupported('audio/mp4')
					? 'audio/mp4'
					: '';

			mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
			chunks = [];
			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) chunks.push(e.data);
			};
			mediaRecorder.onstop = async () => {
				stream.getTracks().forEach((t) => t.stop());
				recording = false;
				transcribing = true;
				try {
					const form = new FormData();
					form.append('audio', new Blob(chunks, { type: mime || 'audio/webm' }), 'speech.webm');
					const res = await fetch(apiUrl('/api/compose'), { method: 'POST', body: form });
					const data = await res.json();
					if (data.script) {
						campaign.templateText = data.script;
						toast.success('Script ready', {
							description: data.transcript ? `Heard: "${data.transcript}"` : undefined
						});
					} else {
						toast.error(data.error || 'Could not understand that');
					}
				} catch {
					toast.error('Transcription failed');
				} finally {
					transcribing = false;
				}
			};
			mediaRecorder.start();
			recording = true;
			toast.info('Listening… tap again to stop');
		} catch {
			toast.error('Microphone unavailable', {
				description: 'Allow mic access (needs HTTPS or localhost).'
			});
		}
	}

	onDestroy(() => {
		try {
			mediaRecorder?.stop();
		} catch {}
	});
</script>

<section class="space-y-4 py-2">
	<div class="space-y-1">
		<h1 class="scroll-m-20 text-3xl font-extrabold tracking-tight">Template</h1>
		<p class="text-sm text-muted-foreground">
			Tell it what to do — e.g. "remind Class 8 parents about tomorrow's meeting" — by speaking, typing, or picking a template.
		</p>
	</div>

	<Card.Root class="py-3 border-border shadow-xs">
		<Card.Content>
			<Textarea
				bind:value={campaign.templateText}
				placeholder="Your campaign script will appear here… Type, speak, or select a template below."
				class="min-h-44 resize-none border-none bg-transparent px-0 text-base leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent"
			/>
		</Card.Content>
	</Card.Root>

	<!-- Clean Template Preset Tags (No Emojis) -->
	<div class="space-y-2 pt-1">
		<p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
			Sample Templates
		</p>
		<div class="flex flex-wrap gap-2">
			{#each templateTips as tip (tip.label)}
				<button
					type="button"
					onclick={() => selectTip(tip.text, tip.label)}
					class="px-3 py-1.5 text-xs font-medium rounded-xl border border-border bg-card hover:bg-muted text-foreground transition-all shadow-xs"
				>
					{tip.label}
				</button>
			{/each}
		</div>
	</div>
</section>

<ActionBar
	primaryLabel="Show template"
	primaryDisabled={!campaign.templateText.trim()}
	onPrimaryAction={() => goto('/preview')}
	actions={[
		{ icon: Trash2, label: 'Reset', onclick: reset },
		{ icon: Volume2, label: playing ? 'Playing…' : 'Listen Voice', onclick: playAudio },
		{
			icon: Mic,
			label: transcribing ? 'Writing…' : recording ? 'Stop' : 'Speak',
			onclick: toggleMic,
			disabled: transcribing
		}
	]}
/>
