package com.define.voiceai;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;
import java.util.Arrays;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AutoDialerPlugin.class);
        super.onCreate(savedInstanceState);

        String[] neededPermissions = new String[]{
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.MODIFY_AUDIO_SETTINGS,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.ANSWER_PHONE_CALLS
        };
        boolean anyMissing = false;
        for (String perm : neededPermissions) {
            if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
                anyMissing = true;
                break;
            }
        }
        if (anyMissing) {
            ActivityCompat.requestPermissions(this, neededPermissions, 1001);
        }

        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().setWebChromeClient(new BridgeWebChromeClient(getBridge()) {
                @Override
                public void onPermissionRequest(final PermissionRequest request) {
                    try {
                        if (Arrays.asList(request.getResources()).contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                            if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                                try {
                                    request.grant(request.getResources());
                                } catch (Exception ignored) {}
                            } else {
                                ActivityCompat.requestPermissions(MainActivity.this, new String[]{Manifest.permission.RECORD_AUDIO, Manifest.permission.MODIFY_AUDIO_SETTINGS}, 1001);
                                try {
                                    request.grant(request.getResources());
                                } catch (Exception ignored) {}
                            }
                        } else {
                            super.onPermissionRequest(request);
                        }
                    } catch (Throwable t) {
                        t.printStackTrace();
                    }
                }
            });
        }
    }
}

