import { registerPlugin, Capacitor } from '@capacitor/core';

export interface CallStateEvent {
	state: 'IDLE' | 'RINGING' | 'OFFHOOK';
	stateCode: number;
	timestamp: number;
}

export interface AutoDialerPlugin {
	makeCall(options: { phone: string }): Promise<{ status: string; phone: string }>;
	endCall(): Promise<{ ended: boolean; stateCode: number }>;
	getCallState(): Promise<{ state: string; stateCode: number }>;
	addListener(
		eventName: 'callStateChange',
		listenerFunc: (event: CallStateEvent) => void
	): Promise<{ remove: () => Promise<void> }>;
}

export const AutoDialer = registerPlugin<AutoDialerPlugin>('AutoDialer');

export const isNative = Capacitor.isNativePlatform();

// When running on Android via Capacitor, localhost points to the phone itself.
// The bridge daemon runs on the host computer at 10.80.0.48:8765.
const BRIDGE_BASE_URL = isNative ? 'http://10.80.0.48:8765' : '';

/**
 * Triggers a call to the specified phone number.
 * Uses native Android AutoDialer plugin if running inside Capacitor,
 * and notifies the dialer bridge daemon to manage the active call timer & hangup.
 */
export async function triggerCall(phone: string, name = 'Recipient', duration = 10): Promise<boolean> {
	// First inform the bridge daemon to track the call countdown and auto-hangup
	try {
		const bridgeEndpoint = isNative ? `${BRIDGE_BASE_URL}/call` : '/api/calls/bridge';
		await fetch(bridgeEndpoint, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ phone, name, duration }),
			signal: AbortSignal.timeout(3000)
		});
	} catch (e) {
		console.warn('Bridge daemon notify error:', e);
	}

	// In native Capacitor environment, also trigger the native ACTION_CALL intent
	if (isNative) {
		try {
			await AutoDialer.makeCall({ phone });
			return true;
		} catch (e) {
			console.error('AutoDialer plugin makeCall failed:', e);
		}
	}

	return true;
}

/**
 * Terminates the ongoing call.
 */
export async function terminateCall(): Promise<boolean> {
	if (isNative) {
		try {
			await AutoDialer.endCall();
		} catch (e) {
			console.error('AutoDialer plugin endCall failed:', e);
		}
	}

	try {
		const bridgeEndpoint = isNative ? `${BRIDGE_BASE_URL}/end` : '/api/calls/bridge';
		const res = await fetch(bridgeEndpoint, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ action: 'end' }),
			signal: AbortSignal.timeout(2000)
		});
		return res.ok;
	} catch (e) {
		console.error('Bridge end call failed:', e);
		return false;
	}
}

/**
 * Retrieves the current call status from the bridge daemon or native plugin.
 */
export async function pollCallStatus(): Promise<{
	active: boolean;
	call_state: 'IDLE' | 'DIALING' | 'CONNECTED' | 'DISCONNECTING' | 'COMPLETED';
	elapsed_seconds: number;
	outcome?: 'completed' | 'declined' | 'unanswered' | 'error' | null;
	current_phone?: string;
	current_name?: string;
}> {
	try {
		const bridgeEndpoint = isNative ? `${BRIDGE_BASE_URL}/status` : '/api/calls/bridge';
		const res = await fetch(bridgeEndpoint, { signal: AbortSignal.timeout(1500) });
		if (res.ok) {
			return await res.json();
		}
	} catch (err) {
		// bridge polling error
	}

	// Fallback to native plugin state if running natively
	if (isNative) {
		try {
			const nativeState = await AutoDialer.getCallState();
			const isOffhook = nativeState.state === 'OFFHOOK';
			return {
				active: isOffhook,
				call_state: isOffhook ? 'CONNECTED' : 'IDLE',
				elapsed_seconds: 0
			};
		} catch {
			// ignore
		}
	}

	return { active: false, call_state: 'IDLE', elapsed_seconds: 0 };
}
