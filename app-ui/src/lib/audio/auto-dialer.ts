import { registerPlugin, Capacitor } from '@capacitor/core';

export interface CallStateEvent {
	state: 'IDLE' | 'RINGING' | 'OFFHOOK';
	stateCode: number;
	timestamp: number;
}

export interface AutoDialerPlugin {
	makeCall(options: { phone: string; duration?: number }): Promise<{ status: string; phone: string; targetDuration: number }>;
	endCall(): Promise<{ ended: boolean; stateCode: number }>;
	getCallState(): Promise<{ state: string; stateCode: number; elapsedSeconds: number }>;
	addListener(
		eventName: 'callStateChange',
		listenerFunc: (event: CallStateEvent) => void
	): Promise<{ remove: () => Promise<void> }>;
}

export const AutoDialer = registerPlugin<AutoDialerPlugin>('AutoDialer');

export const isNative = Capacitor.isNativePlatform();

// When running on Android via Capacitor, adb reverse forwards tcp:8765 to localhost:8765.
// We try localhost:8765, with fallback to host LAN IP 10.80.0.48:8765.
const BRIDGE_ENDPOINTS = isNative
	? ['http://localhost:8765', 'http://10.80.0.48:8765']
	: [''];

let activeBridgeUrl = isNative ? 'http://localhost:8765' : '';

/**
 * Triggers a call to the specified phone number.
 * Uses native Android AutoDialer plugin if running inside Capacitor,
 * and notifies the dialer bridge daemon to manage the active call timer & hangup.
 */
export async function triggerCall(phone: string, name = 'Recipient', duration = 10): Promise<boolean> {
	// First inform the bridge daemon (both localhost and LAN endpoints)
	for (const base of (isNative ? BRIDGE_ENDPOINTS : [''])) {
		try {
			const endpoint = base ? `${base}/call` : '/api/calls/bridge';
			const res = await fetch(endpoint, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ phone, name, duration }),
				signal: AbortSignal.timeout(2000)
			});
			if (res.ok) {
				activeBridgeUrl = base;
				break;
			}
		} catch {
			// next
		}
	}

	// In native Capacitor environment, also trigger the native ACTION_CALL intent with duration
	if (isNative) {
		try {
			await AutoDialer.makeCall({ phone, duration });
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

	const endpoints = isNative ? [activeBridgeUrl, ...BRIDGE_ENDPOINTS].filter(Boolean) : [''];
	for (const base of endpoints) {
		try {
			const endpoint = base ? `${base}/end` : '/api/calls/bridge';
			const res = await fetch(endpoint, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ action: 'end' }),
				signal: AbortSignal.timeout(1500)
			});
			if (res.ok) return true;
		} catch {
			// continue
		}
	}
	return false;
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
	// 1. Try querying the active bridge daemon
	const endpoints = isNative ? [activeBridgeUrl, ...BRIDGE_ENDPOINTS].filter(Boolean) : [''];
	for (const base of endpoints) {
		try {
			const endpoint = base ? `${base}/status` : '/api/calls/bridge';
			const res = await fetch(endpoint, { signal: AbortSignal.timeout(1200) });
			if (res.ok) {
				activeBridgeUrl = base;
				return await res.json();
			}
		} catch {
			// continue to fallback
		}
	}

	// 2. Fallback to native plugin state if running natively
	if (isNative) {
		try {
			const nativeState = await AutoDialer.getCallState();
			const isOffhook = nativeState.state === 'OFFHOOK';
			return {
				active: isOffhook,
				call_state: isOffhook ? 'CONNECTED' : 'IDLE',
				elapsed_seconds: nativeState.elapsedSeconds || 0
			};
		} catch {
			// ignore
		}
	}

	return { active: false, call_state: 'IDLE', elapsed_seconds: 0 };
}

