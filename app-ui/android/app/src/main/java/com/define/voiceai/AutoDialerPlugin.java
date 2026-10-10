package com.define.voiceai;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.telecom.TelecomManager;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyCallback;
import android.telephony.TelephonyManager;
import androidx.annotation.RequiresApi;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

@CapacitorPlugin(name = "AutoDialer")
public class AutoDialerPlugin extends Plugin {

    private static final String TAG = "AutoDialer";
    private static final String DEFAULT_BRIDGE_URL = "http://10.80.0.48:8765";
    private TelephonyManager telephonyManager;
    private TelecomManager telecomManager;
    private int currentCallState = TelephonyManager.CALL_STATE_IDLE;
    private Handler timerHandler = new Handler(Looper.getMainLooper());
    private Runnable autoHangupRunnable = null;
    private long callPickupTimestamp = 0;
    private int targetDurationSeconds = 10;
    private boolean isOffhook = false;

    // Background watcher: polls the bridge and ends the call even when the
    // WebView (and its JS timers) is backgrounded during the call.
    private Thread hangupThread = null;
    private volatile boolean hangupWatching = false;
    private String hangupUrl = null;
    private String bridgeUrl = DEFAULT_BRIDGE_URL;

    @RequiresApi(api = Build.VERSION_CODES.S)
    private static class Api31Callback extends TelephonyCallback implements TelephonyCallback.CallStateListener {
        private final AutoDialerPlugin plugin;

        Api31Callback(AutoDialerPlugin plugin) {
            this.plugin = plugin;
        }

        @Override
        public void onCallStateChanged(int state) {
            plugin.handleCallStateChanged(state);
        }
    }

    @Override
    public void load() {
        super.load();
        Context ctx = getContext();
        telephonyManager = (TelephonyManager) ctx.getSystemService(Context.TELEPHONY_SERVICE);
        telecomManager = (TelecomManager) ctx.getSystemService(Context.TELECOM_SERVICE);
        registerCallStateListener();
    }

    private void registerCallStateListener() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (ContextCompat.checkSelfPermission(getContext(), Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED) {
                    telephonyManager.registerTelephonyCallback(
                        getContext().getMainExecutor(),
                        new Api31Callback(this)
                    );
                }
            } else {
                PhoneStateListener legacyListener = new PhoneStateListener() {
                    @Override
                    public void onCallStateChanged(int state, String phoneNumber) {
                        handleCallStateChanged(state);
                    }
                };
                telephonyManager.listen(legacyListener, PhoneStateListener.LISTEN_CALL_STATE);
            }
        } catch (Throwable t) {
            t.printStackTrace();
        }
    }

    public void handleCallStateChanged(int state) {
        currentCallState = state;
        String stateStr = "IDLE";
        
        if (state == TelephonyManager.CALL_STATE_OFFHOOK) {
            stateStr = "OFFHOOK";
            if (!isOffhook) {
                isOffhook = true;
                callPickupTimestamp = System.currentTimeMillis();
                // Self-start the background hangup watcher the moment the call
                // connects. The WebView's JS timers are frozen while the in-call
                // UI is foreground, so we cannot rely on JS to start it.
                startWatcher(bridgeUrl);
            }
        } else if (state == TelephonyManager.CALL_STATE_RINGING) {
            stateStr = "RINGING";
        } else if (state == TelephonyManager.CALL_STATE_IDLE) {
            stateStr = "IDLE";
            cancelAutoDisconnect();
            isOffhook = false;
            // NOTE: do NOT stop the hangup watcher here. OEM radios can emit a
            // transient IDLE when a call is answered / the SCO link opens, which
            // would otherwise kill the watcher before the bridge asks to hang up.
        }

        // Report the state to the bridge directly from native code (the WebView
        // may be frozen in the background during the call).
        postState(stateStr);
        postDiag("state_change", stateStr);

        JSObject ret = new JSObject();
        ret.put("state", stateStr);
        ret.put("stateCode", state);
        ret.put("timestamp", System.currentTimeMillis());
        notifyListeners("callStateChange", ret);
    }

    private void cancelAutoDisconnect() {
        if (autoHangupRunnable != null) {
            timerHandler.removeCallbacks(autoHangupRunnable);
            autoHangupRunnable = null;
        }
    }

    private boolean performHangup() {
        return performHangup(true);
    }

    private boolean performHangup(boolean bringFront) {
        boolean ended = false;
        boolean perm = ContextCompat.checkSelfPermission(getContext(), Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED;
        Log.i(TAG, "performHangup: answeredPerm=" + perm + " sdk=" + Build.VERSION.SDK_INT + " telecom=" + (telecomManager != null));
        try {
            if (telecomManager != null && perm) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    ended = telecomManager.endCall();
                }
            }
        } catch (Throwable t) {
            Log.e(TAG, "telecomManager.endCall threw", t);
        }

        // Legacy fallback: ITelephony.endCall() via reflection. Blocked by the
        // hidden-API blacklist on most modern builds, but harmless to attempt.
        if (!ended) {
            try {
                TelephonyManager tm = (TelephonyManager) getContext().getSystemService(Context.TELEPHONY_SERVICE);
                java.lang.reflect.Method getITelephony = tm.getClass().getDeclaredMethod("getITelephony");
                getITelephony.setAccessible(true);
                Object iTelephony = getITelephony.invoke(tm);
                java.lang.reflect.Method endCall = iTelephony.getClass().getDeclaredMethod("endCall");
                endCall.setAccessible(true);
                Object r = endCall.invoke(iTelephony);
                if (r instanceof Boolean) {
                    ended = (Boolean) r;
                }
            } catch (Throwable t) {
                Log.e(TAG, "ITelephony fallback failed", t);
            }
        }

        boolean accRequested = false;
        if (!ended) {
            // HONOR (and some other ROMs) refuse TelecomManager.endCall() from a
            // non-default-dialer app. Fall back to tapping the real in-call
            // "End call" button through the accessibility service.
            accRequested = EndCallAccessibilityService.requestEndCall();
        }

        postDiag("hangup_result", "ended=" + ended + " accReq=" + accRequested
                + " accOn=" + EndCallAccessibilityService.isConnected()
                + " perm=" + perm + " state=" + currentCallState
                + " probe=" + EndCallAccessibilityService.getLastProbe());
        Log.i(TAG, "performHangup result ended=" + ended + " accReq=" + accRequested);

        // Immediately re-assert screen wakefulness and return focus to MainActivity
        try {
            if (bringFront && getActivity() != null) {
                getActivity().runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            getActivity().getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                            Intent bringToFront = new Intent(getContext(), MainActivity.class);
                            bringToFront.setFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                            getContext().startActivity(bringToFront);
                        } catch (Throwable ignored) {}
                    }
                });
            }
        } catch (Throwable ignored) {}

        return ended;
    }

    @PluginMethod
    public void makeCall(PluginCall call) {
        String phone = call.getString("phone");
        Integer duration = call.getInt("duration", 10);
        if (duration != null) {
            targetDurationSeconds = duration;
        } else {
            targetDurationSeconds = 10;
        }

        // Remember the bridge URL so the native watcher can self-start when the
        // call goes OFFHOOK (the WebView is frozen while the in-call UI is up).
        String bUrl = call.getString("bridgeUrl");
        if (bUrl != null && !bUrl.trim().isEmpty()) {
            bridgeUrl = bUrl.trim().replaceAll("/+$", "");
            hangupUrl = bridgeUrl;
        }
        // Start the background watcher now, before the call is even placed, so
        // it is guaranteed to be listening when the bridge requests a hang-up.
        startWatcher(bridgeUrl);

        if (phone == null || phone.trim().isEmpty()) {
            call.reject("Phone number is required");
            return;
        }

        String cleanPhone = phone.trim().replaceAll("\\s+", "");
        isOffhook = false;
        callPickupTimestamp = 0;
        cancelAutoDisconnect();

        Intent intent;
        if (ContextCompat.checkSelfPermission(getContext(), Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
            intent = new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + cleanPhone));
        } else {
            intent = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + cleanPhone));
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

        try {
            getContext().startActivity(intent);
            JSObject res = new JSObject();
            res.put("status", "dialing");
            res.put("phone", cleanPhone);
            res.put("targetDuration", targetDurationSeconds);
            call.resolve(res);
        } catch (Exception e) {
            call.reject("Failed to trigger call: " + e.getMessage(), e);
        }
    }

    @PluginMethod
    public void endCall(PluginCall call) {
        cancelAutoDisconnect();
        boolean ended = performHangup();

        JSObject res = new JSObject();
        res.put("ended", ended);
        res.put("stateCode", currentCallState);
        call.resolve(res);
    }

    @PluginMethod
    public void startHangupWatcher(PluginCall call) {
        String url = call.getString("url");
        if (url == null || url.trim().isEmpty()) {
            call.reject("url is required");
            return;
        }
        startWatcher(url.trim().replaceAll("/+$", ""));
        call.resolve();
    }

    /** Start (idempotently) the background thread that polls the bridge and
     *  ends the call when the bridge requests it. Safe to call from any thread. */
    private void startWatcher(final String url) {
        if (url == null || url.isEmpty()) {
            return;
        }
        hangupUrl = url;
        if (hangupWatching && hangupThread != null && hangupThread.isAlive()) {
            return;
        }
        hangupWatching = true;
        Log.i(TAG, "startWatcher url=" + hangupUrl);
        postDiag("watcher_start", hangupUrl);
        hangupThread = new Thread(new Runnable() {
            @Override
            public void run() {
                int attempts = 0;
                boolean loggedError = false;
                boolean sawActive = false;
                while (hangupWatching && attempts < 1200) {
                    attempts++;
                    boolean done = false;
                    try {
                        HttpURLConnection conn = (HttpURLConnection) new URL(hangupUrl + "/status").openConnection();
                        conn.setConnectTimeout(2000);
                        conn.setReadTimeout(2000);
                        if (conn.getResponseCode() == 200) {
                            BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                            StringBuilder sb = new StringBuilder();
                            String line;
                            while ((line = reader.readLine()) != null) sb.append(line);
                            reader.close();
                            JSONObject o = new JSONObject(sb.toString());
                            boolean active = o.optBoolean("active", false);
                            boolean hangup = o.optBoolean("hangup_requested", false);
                            String state = o.optString("call_state", "");

                            if (active || "CONNECTED".equals(state) || "DIALING".equals(state)) {
                                sawActive = true;
                            }

                            if (hangup) {
                                Log.i(TAG, "watcher: hangup_requested active=" + active + " state=" + state + " -> performHangup");
                                postDiag("hangup_detected", "active=" + active + " state=" + state);
                                timerHandler.post(new Runnable() {
                                    @Override
                                    public void run() {
                                        // Do NOT raise our app here: the in-call
                                        // UI must stay foreground so the
                                        // accessibility service can tap End.
                                        performHangup(false);
                                    }
                                });
                            }

                            // Only conclude once we have actually seen the call live
                            // AND the bridge now reports it finished. This prevents a
                            // transient "IDLE" at answer time from stopping us early.
                            if (sawActive && !active && ("COMPLETED".equals(state) || "IDLE".equals(state))) {
                                done = true;
                            }
                        }
                    } catch (Throwable t) {
                        if (!loggedError) {
                            loggedError = true;
                            Log.e(TAG, "hangup watcher poll error", t);
                            postDiag("watcher_poll_error", String.valueOf(t.getMessage()));
                        }
                    }
                    if (!sawActive && attempts > 130) {
                        // The call never came up (declined/unanswered) — stop.
                        break;
                    }
                    if (done) break;
                    try {
                        Thread.sleep(700);
                    } catch (InterruptedException e) {
                        break;
                    }
                }
                postDiag("watcher_stopped", "attempts=" + attempts);
                Log.i(TAG, "hangup watcher stopped after " + attempts + " attempts");
                hangupWatching = false;
            }
        });
        hangupThread.setDaemon(true);
        hangupThread.start();
    }

    /** Fire-and-forget diagnostic POST to the bridge (never blocks a caller). */
    private void postDiag(final String event, final String detail) {
        final String url = (hangupUrl != null && !hangupUrl.isEmpty()) ? hangupUrl : bridgeUrl;
        if (url == null || url.isEmpty()) {
            return;
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    HttpURLConnection conn = (HttpURLConnection) new URL(url + "/diag").openConnection();
                    conn.setRequestMethod("POST");
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(2500);
                    conn.setReadTimeout(2500);
                    conn.setRequestProperty("Content-Type", "application/json");
                    String safe = detail == null ? "" : detail.replace("\\", "").replace("\"", "'");
                    String payload = "{\"event\":\"" + event + "\",\"detail\":\"" + safe + "\"}";
                    conn.getOutputStream().write(payload.getBytes("UTF-8"));
                    conn.getResponseCode();
                    conn.disconnect();
                } catch (Throwable t) {
                    Log.e(TAG, "diag post failed: " + event, t);
                }
            }
        }).start();
    }

    /** Fire-and-forget POST of a call-state update to the bridge. */
    private void postState(final String state) {
        final String url = (hangupUrl != null && !hangupUrl.isEmpty()) ? hangupUrl : bridgeUrl;
        if (url == null || url.isEmpty()) {
            return;
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    HttpURLConnection conn = (HttpURLConnection) new URL(url + "/call/state").openConnection();
                    conn.setRequestMethod("POST");
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(2500);
                    conn.setReadTimeout(2500);
                    conn.setRequestProperty("Content-Type", "application/json");
                    String payload = "{\"state\":\"" + state + "\"}";
                    conn.getOutputStream().write(payload.getBytes("UTF-8"));
                    conn.getResponseCode();
                    conn.disconnect();
                } catch (Throwable t) {
                    Log.e(TAG, "state post failed: " + state, t);
                }
            }
        }).start();
    }

    @PluginMethod
    public void stopHangupWatcher(PluginCall call) {
        hangupWatching = false;
        call.resolve();
    }

    @PluginMethod
    public void isAccessibilityEnabled(PluginCall call) {
        JSObject res = new JSObject();
        res.put("enabled", EndCallAccessibilityService.isConnected());
        call.resolve(res);
    }

    @PluginMethod
    public void openAccessibilitySettings(PluginCall call) {
        try {
            Intent i = new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
        } catch (Throwable t) {
            Log.e(TAG, "openAccessibilitySettings failed", t);
        }
        call.resolve();
    }

    @PluginMethod
    public void getCallState(PluginCall call) {
        JSObject res = new JSObject();
        String stateStr = "IDLE";
        if (currentCallState == TelephonyManager.CALL_STATE_OFFHOOK) {
            stateStr = "OFFHOOK";
        } else if (currentCallState == TelephonyManager.CALL_STATE_RINGING) {
            stateStr = "RINGING";
        }
        res.put("state", stateStr);
        res.put("stateCode", currentCallState);
        
        long elapsed = 0;
        if (isOffhook && callPickupTimestamp > 0) {
            elapsed = (System.currentTimeMillis() - callPickupTimestamp) / 1000;
        }
        res.put("elapsedSeconds", elapsed);
        call.resolve(res);
    }
}

