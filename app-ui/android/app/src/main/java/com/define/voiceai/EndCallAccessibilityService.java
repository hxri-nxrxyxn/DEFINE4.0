package com.define.voiceai;

import android.accessibilityservice.AccessibilityService;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.util.List;

/**
 * Ends an in-progress cellular call by tapping the system dialer's "End call"
 * button. This is used because HONOR's ROM refuses TelecomManager.endCall()
 * from a non-default-dialer app (it returns false), so we fall back to an
 * accessibility tap on the real in-call UI.
 *
 * The user enables this service once in Settings > Accessibility.
 */
public class EndCallAccessibilityService extends AccessibilityService {

    private static final String TAG = "AutoDialer";
    private static final long MAX_MS = 30000L;

    private static EndCallAccessibilityService instance;
    private static volatile boolean pendingEnd = false;
    private static volatile long pendingSince = 0L;
    private static volatile String lastProbe = "";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable retry = new Runnable() {
        @Override
        public void run() {
            if (!pendingEnd) {
                return;
            }
            if (System.currentTimeMillis() - pendingSince > MAX_MS) {
                pendingEnd = false;
                Log.i(TAG, "accessibility end-call timed out");
                return;
            }
            attemptClick();
            handler.postDelayed(this, 500);
        }
    };

    /** True when the user has enabled the "Define Voice AI" accessibility service. */
    public static boolean isConnected() {
        return instance != null;
    }

    /** Last sampled description of the in-call UI (for debugging). */
    public static String getLastProbe() {
        return lastProbe;
    }

    /** Ask the service to tap the in-call End button. Returns true if connected. */
    public static boolean requestEndCall() {
        if (!pendingEnd) {
            pendingSince = System.currentTimeMillis();
        }
        pendingEnd = true;
        EndCallAccessibilityService s = instance;
        if (s != null) {
            s.handler.removeCallbacks(s.retry);
            s.handler.post(s.retry);
            return true;
        }
        return false;
    }

    public static void cancel() {
        pendingEnd = false;
        EndCallAccessibilityService s = instance;
        if (s != null) {
            s.handler.removeCallbacks(s.retry);
        }
    }

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        Log.i(TAG, "EndCallAccessibilityService connected");
        if (pendingEnd) {
            handler.removeCallbacks(retry);
            handler.post(retry);
        }
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (pendingEnd) {
            attemptClick();
        }
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        if (instance == this) {
            instance = null;
        }
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        if (instance == this) {
            instance = null;
        }
        super.onDestroy();
    }

    private void attemptClick() {
        try {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root != null && clickEndButton(root)) {
                onClicked("active-window");
                return;
            }
            List<AccessibilityWindowInfo> windows = getWindows();
            if (windows != null) {
                for (AccessibilityWindowInfo w : windows) {
                    AccessibilityNodeInfo r = w.getRoot();
                    if (r != null && clickEndButton(r)) {
                        onClicked("window-scan");
                        return;
                    }
                }
            }
            // Nothing matched yet — capture what the in-call UI looks like.
            if (root != null) {
                StringBuilder sb = new StringBuilder();
                sb.append("pkg=").append(root.getPackageName()).append(" ");
                collectProbe(root, sb, new int[]{0});
                lastProbe = sb.toString();
            }
        } catch (Throwable t) {
            Log.e(TAG, "accessibility attemptClick failed", t);
        }
    }

    private void collectProbe(AccessibilityNodeInfo node, StringBuilder sb, int[] count) {
        if (node == null || count[0] >= 16) {
            return;
        }
        if (node.isClickable()) {
            count[0]++;
            sb.append("[")
              .append(str(node.getContentDescription())).append("|")
              .append(str(node.getText())).append("|")
              .append(str(node.getViewIdResourceName()))
              .append("] ");
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            collectProbe(node.getChild(i), sb, count);
        }
    }

    private void onClicked(String where) {
        pendingEnd = false;
        handler.removeCallbacks(retry);
        Log.i(TAG, "accessibility tapped end-call button (" + where + ")");
    }

    private boolean clickEndButton(AccessibilityNodeInfo node) {
        if (node == null) {
            return false;
        }
        String desc = str(node.getContentDescription());
        String text = str(node.getText());
        String vid = str(node.getViewIdResourceName());
        String cls = str(node.getClassName());

        boolean matches =
                desc.contains("end call")
                || desc.contains("endcall")
                || desc.contains("hang up")
                || desc.contains("hangup")
                || desc.contains("disconnect")
                || text.equals("end call")
                || text.equals("hang up")
                || vid.contains("end_call")
                || vid.contains("endcall")
                || vid.contains("hangup")
                || vid.contains("hang_up")
                || vid.contains("disconnect");

        boolean clickableLike = node.isClickable()
                || cls.contains("button")
                || cls.contains("image");

        if (matches && clickableLike) {
            AccessibilityNodeInfo target = node;
            if (!node.isClickable()) {
                AccessibilityNodeInfo p = node.getParent();
                int guard = 0;
                while (p != null && !p.isClickable() && guard++ < 6) {
                    p = p.getParent();
                }
                if (p != null) {
                    target = p;
                }
            }
            try {
                if (target.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                    return true;
                }
            } catch (Throwable ignored) {
            }
        }

        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                boolean ok = clickEndButton(child);
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                    child.recycle();
                }
                if (ok) {
                    return true;
                }
            }
        }
        return false;
    }

    private static String str(CharSequence cs) {
        return cs == null ? "" : cs.toString().toLowerCase();
    }
}
