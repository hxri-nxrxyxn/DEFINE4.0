import { registerPlugin, Capacitor } from '@capacitor/core';
import { apiUrl } from '#lib/config.js';

export interface CallStateEvent {
	state: 'IDLE' | 'RINGING' | 'OFFHOOK';
	stateCode: number;
	timestamp: number;
}

export interface AutoDialerPlugin {
	makeCall(options: { phone: string; duration?: number; bridgeUrl?: string }): Promise<{ status: string; phone: string; targetDuration: number }>;
	endCall(): Promise<{ ended: boolean; stateCode: number }>;
	getCallState(): Promise<{ state: string; stateCode: number; elapsedSeconds: number }>;
	startHangupWatcher(options: { url: string }): Promise<void>;
	stopHangupWatcher(): Promise<void>;
	isAccessibilityEnabled(): Promise<{ enabled: boolean }>;
	openAccessibilitySettings(): Promise<void>;
	addListener(
		eventName: 'callStateChange',
		listenerFunc: (event: CallStateEvent) => void
	): Promise<{ remove: () => Promise<void> }>;
}

export const AutoDialer = registerPlugin<AutoDialerPlugin>('AutoDialer');

export const isNative = Capacitor.isNativePlatform();

// The bridge daemon runs on the host machine. On the phone we reach it over the
// network (Tailscale hostname first, then the LAN IP); localhost is kept as a
// last resort for the USB + `adb reverse` dev setup.
const BRIDGE_ENDPOINTS = isNative
	? ['http://10.80.0.48:8765', 'http://x1carbon:8765', 'http://localhost:8765']
	: [''];

let activeBridgeUrl = isNative ? 'http://10.80.0.48:8765' : '';

/** Forward the phone's native call state to the bridge (no USB/adb needed). */
async function reportCallStateToBridge(state: 'OFFHOOK' | 'IDLE'): Promise<void> {
	for (const base of (isNative ? [activeBridgeUrl, ...BRIDGE_ENDPOINTS].filter(Boolean) : [])) {
		try {
			const res = await fetch(`${base}/call/state`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ state }),
				signal: AbortSignal.timeout(1500)
			});
			if (res.ok) return;
		} catch {
			// try next
		}
	}
}

let callStateForwardingReady = false;

/** Subscribe to the native dialer so OFFHOOK/IDLE reach the bridge. */
export async function registerCallStateForwarding(): Promise<void> {
	if (!isNative || callStateForwardingReady) return;
	callStateForwardingReady = true;
	try {
		await AutoDialer.addListener('callStateChange', (e) => {
			if (e.state === 'OFFHOOK') {
				void reportCallStateToBridge('OFFHOOK');
			} else if (e.state === 'IDLE') {
				void reportCallStateToBridge('IDLE');
				void stopHangupWatcher();
			}
		});
	} catch (e) {
		console.error('AutoDialer addListener failed:', e);
	}
}

/** End the call using the phone's native dialer. */
export async function endCallNatively(): Promise<boolean> {
	if (!isNative) return false;
	try {
		await AutoDialer.endCall();
		return true;
	} catch (e) {
		console.error('AutoDialer plugin endCall failed:', e);
		return false;
	}
}

/**
 * Start a native background watcher that polls the bridge and ends the call when
 * a hang-up is requested — even if the WebView is backgrounded during the call.
 */
export async function startHangupWatcher(): Promise<void> {
	if (!isNative) return;
	try {
		console.log('[auto-dialer] starting hangup watcher at', activeBridgeUrl);
		await AutoDialer.startHangupWatcher({ url: activeBridgeUrl });
	} catch (e) {
		console.error('AutoDialer startHangupWatcher failed:', e);
	}
}

export async function stopHangupWatcher(): Promise<void> {
	if (!isNative) return;
	try {
		await AutoDialer.stopHangupWatcher();
	} catch {
		// ignore
	}
}

/**
 * The HONOR ROM refuses TelecomManager.endCall() from a non-default-dialer app,
 * so the app taps the in-call "End call" button via an accessibility service.
 * Returns whether that service is currently enabled.
 */
export async function isEndCallAccessibilityEnabled(): Promise<boolean> {
	if (!isNative) return true;
	try {
		const res = await AutoDialer.isAccessibilityEnabled();
		return !!res?.enabled;
	} catch {
		return false;
	}
}

export async function openAccessibilitySettings(): Promise<void> {
	if (!isNative) return;
	try {
		await AutoDialer.openAccessibilitySettings();
	} catch {
		// ignore
	}
}

/**
 * Triggers a call to the specified phone number.
 * Uses native Android AutoDialer plugin if running inside Capacitor,
 * and notifies the dialer bridge daemon to manage the active call.
 * The call stays connected until the recipient hangs up or /end is triggered.
 */
export async function triggerCall(
	phone: string,
	name = 'Recipient',
	script?: string,
	language?: string
): Promise<boolean> {
	// First inform the bridge daemon (both localhost and LAN endpoints)
	// We pass native_dialed=true when on native so the bridge doesn't trigger a duplicate ACTION_CALL.
	// `script`/`language` let the bridge point the ElevenLabs agent at the
	// operator's Template before the call connects.
	for (const base of (isNative ? BRIDGE_ENDPOINTS : [''])) {
		try {
			const endpoint = base ? `${base}/call` : apiUrl('/api/calls/bridge');
			const res = await fetch(endpoint, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ phone, name, script, language, native_dialed: isNative }),
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

	// In native Capacitor environment, trigger the native ACTION_CALL intent
	if (isNative) {
		await registerCallStateForwarding();
		try {
			await AutoDialer.makeCall({ phone, bridgeUrl: activeBridgeUrl });
			await startHangupWatcher();
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
		await stopHangupWatcher();
	}

	const endpoints = isNative ? [activeBridgeUrl, ...BRIDGE_ENDPOINTS].filter(Boolean) : [''];
	for (const base of endpoints) {
		try {
			const endpoint = base ? `${base}/end` : apiUrl('/api/calls/bridge');
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
	outcome?: string | null;
	hangup_requested?: boolean;
	current_phone?: string;
	current_name?: string;
}> {
	// 1. Try querying the active bridge daemon
	const endpoints = isNative ? [activeBridgeUrl, ...BRIDGE_ENDPOINTS].filter(Boolean) : [''];
	for (const base of endpoints) {
		try {
			const endpoint = base ? `${base}/status` : apiUrl('/api/calls/bridge');
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

