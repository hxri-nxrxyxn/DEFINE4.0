package com.define.voiceai;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
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

@CapacitorPlugin(name = "AutoDialer")
public class AutoDialerPlugin extends Plugin {

    private TelephonyManager telephonyManager;
    private TelecomManager telecomManager;
    private int currentCallState = TelephonyManager.CALL_STATE_IDLE;

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
        } else if (state == TelephonyManager.CALL_STATE_RINGING) {
            stateStr = "RINGING";
        }

        JSObject ret = new JSObject();
        ret.put("state", stateStr);
        ret.put("stateCode", state);
        ret.put("timestamp", System.currentTimeMillis());
        notifyListeners("callStateChange", ret);
    }

    @PluginMethod
    public void makeCall(PluginCall call) {
        String phone = call.getString("phone");
        if (phone == null || phone.trim().isEmpty()) {
            call.reject("Phone number is required");
            return;
        }

        String cleanPhone = phone.trim().replaceAll("\\s+", "");
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
            call.resolve(res);
        } catch (Exception e) {
            call.reject("Failed to trigger call: " + e.getMessage(), e);
        }
    }

    @PluginMethod
    public void endCall(PluginCall call) {
        boolean ended = false;
        try {
            if (telecomManager != null && ContextCompat.checkSelfPermission(getContext(), Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    ended = telecomManager.endCall();
                }
            }
        } catch (Throwable t) {
            t.printStackTrace();
        }

        JSObject res = new JSObject();
        res.put("ended", ended);
        res.put("stateCode", currentCallState);
        call.resolve(res);
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
        call.resolve(res);
    }
}
