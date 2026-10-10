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
                // No native auto-disconnect: the call now stays connected until
                // the recipient hangs up or an external trigger calls endCall().
            }
        } else if (state == TelephonyManager.CALL_STATE_RINGING) {
            stateStr = "RINGING";
        } else if (state == TelephonyManager.CALL_STATE_IDLE) {
            stateStr = "IDLE";
            cancelAutoDisconnect();
            isOffhook = false;
        }

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

        if (!ended) {
            // Best-effort fallback (usually not permitted for a normal app).
            try {
                Runtime.getRuntime().exec(new String[]{"input", "keyevent", "6"});
            } catch (Throwable ignore) {
                Log.e(TAG, "keyevent fallback failed", ignore);
            }
        }
        Log.i(TAG, "performHangup result ended=" + ended);

        // Immediately re-assert screen wakefulness and return focus to MainActivity
        try {
            if (getActivity() != null) {
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
        hangupUrl = url.trim().replaceAll("/+$", "");
        hangupWatching = true;
        Log.i(TAG, "startHangupWatcher url=" + hangupUrl);
        if (hangupThread == null || !hangupThread.isAlive()) {
            hangupThread = new Thread(new Runnable() {
                @Override
                public void run() {
                    int attempts = 0;
                    boolean loggedError = false;
                    while (hangupWatching && attempts < 150) {
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
                                if (!active && ("COMPLETED".equals(state) || "IDLE".equals(state))) {
                                    done = true;
                                } else if (hangup) {
                                    Log.i(TAG, "watcher: hangup_requested active=" + active + " state=" + state + " -> performHangup");
                                    timerHandler.post(new Runnable() {
                                        @Override
                                        public void run() {
                                            performHangup();
                                        }
                                    });
                                }
                            }
                        } catch (Throwable t) {
                            if (!loggedError) {
                                loggedError = true;
                                Log.e(TAG, "hangup watcher poll error", t);
                            }
                        }
                        if (done) break;
                        try {
                            Thread.sleep(800);
                        } catch (InterruptedException e) {
                            break;
                        }
                    }
                    Log.i(TAG, "hangup watcher stopped after " + attempts + " attempts");
                    hangupWatching = false;
                }
            });
            hangupThread.setDaemon(true);
            hangupThread.start();
        }
        call.resolve();
    }

    @PluginMethod
    public void stopHangupWatcher(PluginCall call) {
        hangupWatching = false;
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

