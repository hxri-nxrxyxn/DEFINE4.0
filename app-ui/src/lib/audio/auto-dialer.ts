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

/**
 * Triggers a call to the specified phone number.
 * Uses native Android AutoDialer plugin if running inside Capacitor,
 * or routes through the local ADB dialer bridge daemon if running in dev/web.
 */
export async function triggerCall(phone: string, name = 'Recipient', duration = 10): Promise<boolean> {
	if (isNative) {
		try {
			await AutoDialer.makeCall({ phone });
			return true;
		} catch (e) {
			console.error('AutoDialer plugin makeCall failed:', e);
		}
	}

	// Web / Dev mode fallback via dialer bridge daemon
	try {
		const res = await fetch('/api/calls/bridge', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ phone, name, duration })
		});
		return res.ok;
	} catch (e) {
		console.error('Dialer bridge failed:', e);
		return false;
	}
}

/**
 * Terminates the ongoing call.
 */
export async function terminateCall(): Promise<boolean> {
	if (isNative) {
		try {
			const res = await AutoDialer.endCall();
			if (res.ended) return true;
		} catch (e) {
			console.error('AutoDialer plugin endCall failed:', e);
		}
	}

	try {
		const res = await fetch('/api/calls/bridge', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ action: 'end' })
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
	current_phone?: string;
	current_name?: string;
}> {
	try {
		const res = await fetch('/api/calls/bridge');
		if (res.ok) {
			return await res.json();
		}
	} catch {
		// ignore
	}
	return { active: false, call_state: 'IDLE', elapsed_seconds: 0 };
}
