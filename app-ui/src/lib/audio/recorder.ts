export type StartRecordingOptions = {
	/** Called ~60x per second with a normalized 0-1 loudness level (for visualization). */
	onLevel?: (level: number) => void;
	/** Called once when recording finishes, with the captured audio. */
	onStop: (audio: Blob) => void;
	/** Called if the microphone cannot be accessed. */
	onError?: (error: unknown) => void;
	/** Milliseconds of continuous silence after speech before auto-stopping. */
	silenceDurationMs?: number;
	/** RMS amplitude considered "speech". */
	silenceThreshold?: number;
	/** Hard cap on recording length. */
	maxDurationMs?: number;
};

export type RecordingHandle = {
	/** Stop recording and trigger `onStop`. */
	stop: () => void;
	/** Stop recording without triggering `onStop`. */
	cancel: () => void;
};

/**
 * Records from the microphone, reporting loudness levels, and automatically
 * stops once the speaker has gone quiet for `silenceDurationMs` (after having
 * spoken at least once).
 */
export async function startRecording(options: StartRecordingOptions): Promise<RecordingHandle> {
	const {
		onLevel,
		onStop,
		onError,
		silenceDurationMs = 1100,
		silenceThreshold = 0.02,
		maxDurationMs = 15000
	} = options;

	let stream: MediaStream;
	try {
		stream = await navigator.mediaDevices.getUserMedia({ audio: true });
	} catch (error) {
		onError?.(error);
		throw error;
	}

	const audioContext = new AudioContext();
	const source = audioContext.createMediaStreamSource(stream);
	const analyser = audioContext.createAnalyser();
	analyser.fftSize = 1024;
	source.connect(analyser);

	const mimeType = MediaRecorder.isTypeSupported('audio/webm')
		? 'audio/webm'
		: MediaRecorder.isTypeSupported('audio/mp4')
			? 'audio/mp4'
			: '';

	const chunks: BlobPart[] = [];
	const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
	recorder.ondataavailable = (event) => {
		if (event.data.size > 0) chunks.push(event.data);
	};
	recorder.start();

	const data = new Uint8Array(analyser.fftSize);
	const startedAt = performance.now();
	let frame = 0;
	let finished = false;
	let speechStarted = false;
	let silenceSince = 0;

	const teardown = () => {
		cancelAnimationFrame(frame);
		source.disconnect();
		for (const track of stream.getTracks()) track.stop();
		void audioContext.close();
	};

	const stop = () => {
		if (finished) return;
		finished = true;
		cancelAnimationFrame(frame);
		recorder.onstop = () => {
			teardown();
			onStop(new Blob(chunks, { type: mimeType || 'audio/webm' }));
		};
		recorder.stop();
	};

	const cancel = () => {
		if (finished) return;
		finished = true;
		cancelAnimationFrame(frame);
		try {
			recorder.stop();
		} catch {
			// already stopped
		}
		teardown();
	};

	const tick = () => {
		if (finished) return;

		analyser.getByteTimeDomainData(data);
		let sum = 0;
		for (let i = 0; i < data.length; i++) {
			const value = (data[i] - 128) / 128;
			sum += value * value;
		}
		const rms = Math.sqrt(sum / data.length);
		onLevel?.(Math.min(1, rms * 6));

		const now = performance.now();
		if (rms > silenceThreshold) {
			speechStarted = true;
			silenceSince = 0;
		} else if (speechStarted) {
			if (silenceSince === 0) silenceSince = now;
			else if (now - silenceSince >= silenceDurationMs) {
				stop();
				return;
			}
		}

		if (now - startedAt >= maxDurationMs) {
			stop();
			return;
		}

		frame = requestAnimationFrame(tick);
	};

	frame = requestAnimationFrame(tick);

	return { stop, cancel };
}
