package com.qinl.car.pub.trial;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.os.Handler;
import android.util.Log;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/**
 * 1.0.5: Self-healing watchdog for zombie BluetoothGatt handles stuck in WAIT_RETRY.
 *
 * Root cause observed in 2026-11-26 13:04~13:45 logs:
 * After cold boot, BleDirectSession.openGatt() can obtain a stale BluetoothGatt handle
 * whose autoConnect=true never delivers onConnectionStateChange. Because rearmRegistration()
 * only calls gatt.connect() without closing/recreating the client, it stayed stuck in
 * WAIT_RETRY for 41 minutes even inside the car.
 *
 * This watchdog inspects BleDirectSession phase (without modifying bluetooth/*.smali) and
 * invokes BleDirectSession.rebuildClient(why) on its own handler thread:
 *  - On motion wake (walking to car): if in WAIT_RETRY >= 25s (cooldown 45s) -> immediate rebuild
 *  - On foreground resume: if in WAIT_RETRY >= 20s (cooldown 30s) -> immediate rebuild
 *  - On periodic service tick (throttled 15s): backoff 3m -> 5m -> 10m while in WAIT_RETRY
 *  - Manual button ("立即连接/重新连接/待命"): immediate rebuild if not LIVE
 */
public final class GattWatchdog {
    private static final String CLS = "com.qinl.car.pub.bluetooth.BleDirectSession";
    private static final long TICK_THROTTLE_MS = 15_000L;
    private static final long MOTION_STUCK_MS = 25_000L;
    private static final long MOTION_COOLDOWN_MS = 45_000L;
    private static final long FG_STUCK_MS = 20_000L;
    private static final long FG_COOLDOWN_MS = 30_000L;

    private static final Object LOCK = new Object();
    private static long waitRetrySince = 0L;
    private static long lastRebuildAt = 0L;
    private static long lastTickAt = 0L;
    private static int consecutiveRebuilds = 0;

    private GattWatchdog() {}

    public static void tick(Context ctx) {
        if (ctx == null) return;
        long now = System.currentTimeMillis();
        synchronized (LOCK) {
            if (now - lastTickAt < TICK_THROTTLE_MS) return;
            lastTickAt = now;
        }
        evaluate(ctx.getApplicationContext(), now, false, false, "看门狗");
    }

    public static void onMotion(Context ctx, String why) {
        if (ctx == null) return;
        String tag = (why == null || why.isEmpty()) ? "运动唤醒" : ("运动唤醒:" + why);
        evaluate(ctx.getApplicationContext(), System.currentTimeMillis(), true, false, tag);
    }

    public static void onForeground(Context ctx) {
        if (ctx == null) return;
        evaluate(ctx.getApplicationContext(), System.currentTimeMillis(), false, true, "回到前台");
    }

    public static boolean forceRebuild(Context ctx, String why) {
        if (ctx == null) return false;
        Context app = ctx.getApplicationContext();
        if (!isBluetoothOn(app)) return false;
        String phase = currentPhase();
        if ("LIVE".equals(phase)) return false;
        synchronized (LOCK) {
            lastRebuildAt = System.currentTimeMillis();
            waitRetrySince = 0L;
            consecutiveRebuilds++;
        }
        return triggerRebuild(app, (why == null || why.isEmpty()) ? "手动重建" : why);
    }

    public static int getConsecutiveRebuilds() {
        synchronized (LOCK) {
            return consecutiveRebuilds;
        }
    }

    public static long getWaitRetrySec() {
        synchronized (LOCK) {
            if (waitRetrySince <= 0L) return 0L;
            return Math.max(0L, (System.currentTimeMillis() - waitRetrySince) / 1000L);
        }
    }

    private static void evaluate(Context app, long now, boolean isMotion, boolean isFg, String why) {
        if (app == null || !isBluetoothOn(app)) {
            resetTracking();
            return;
        }
        if (!isSessionRunning()) {
            resetTracking();
            return;
        }
        String phase = currentPhase();
        if (phase == null || "IDLE".equals(phase) || "LIVE".equals(phase)) {
            resetTracking();
            return;
        }
        if (!"WAIT_RETRY".equals(phase)) {
            // CONNECTING / DISCOVERING / AUTHING in flight -> never disturb
            return;
        }

        long stuckMs;
        long sinceRebuild;
        int count;
        synchronized (LOCK) {
            if (waitRetrySince == 0L) waitRetrySince = now;
            stuckMs = now - waitRetrySince;
            sinceRebuild = (lastRebuildAt > 0L) ? (now - lastRebuildAt) : Long.MAX_VALUE;
            count = consecutiveRebuilds;
        }

        boolean shouldRebuild = false;
        if (isMotion) {
            shouldRebuild = (stuckMs >= MOTION_STUCK_MS && sinceRebuild >= MOTION_COOLDOWN_MS);
        } else if (isFg) {
            shouldRebuild = (stuckMs >= FG_STUCK_MS && sinceRebuild >= FG_COOLDOWN_MS);
        } else {
            long minGap = (count <= 0) ? 180_000L : (count == 1 ? 300_000L : 600_000L);
            shouldRebuild = (stuckMs >= 180_000L && sinceRebuild >= minGap);
        }

        if (!shouldRebuild) return;

        int nextCount;
        synchronized (LOCK) {
            lastRebuildAt = now;
            waitRetrySince = 0L;
            consecutiveRebuilds++;
            nextCount = consecutiveRebuilds;
        }
        String reason = why + "·WAIT_RETRY持续" + (stuckMs / 1000L) + "s·第" + nextCount + "次";
        triggerRebuild(app, reason);
    }

    private static void resetTracking() {
        synchronized (LOCK) {
            waitRetrySince = 0L;
            consecutiveRebuilds = 0;
        }
    }

    private static boolean triggerRebuild(final Context app, final String why) {
        String note = "[直连自愈] 销毁僵尸 GATT 并新建连接（" + why + "）";
        Log.i("KC", note);
        PauseOverride.appLog(note);
        try {
            final Class<?> cls = Class.forName(CLS);
            final Object inst = cls.getField("INSTANCE").get(null);
            Field hf = cls.getDeclaredField("handler");
            hf.setAccessible(true);
            Handler h = (Handler) hf.get(null);
            final Method rebuild = cls.getDeclaredMethod("rebuildClient", String.class);
            rebuild.setAccessible(true);
            if (h != null) {
                h.post(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            if (!isSessionRunning()) return;
                            String p = currentPhase();
                            if ("LIVE".equals(p) || "CONNECTING".equals(p)
                                    || "DISCOVERING".equals(p) || "AUTHING".equals(p)) {
                                return;
                            }
                            rebuild.invoke(inst, why);
                        } catch (Throwable t) {
                            Log.w("KC", "rebuildClient failed, fallback stop/start", t);
                            fallbackRestart(app);
                        }
                    }
                });
                return true;
            }
        } catch (Throwable t) {
            Log.w("KC", "reflect rebuildClient failed, fallback stop/start", t);
        }
        fallbackRestart(app);
        return true;
    }

    private static void fallbackRestart(final Context app) {
        try {
            Class<?> cls = Class.forName(CLS);
            Object inst = cls.getField("INSTANCE").get(null);
            cls.getMethod("stop").invoke(inst);
            cls.getMethod("start", Context.class).invoke(inst, app);
        } catch (Throwable ignored) {}
    }

    private static boolean isSessionRunning() {
        try {
            Class<?> cls = Class.forName(CLS);
            Field ef = cls.getDeclaredField("enabled");
            ef.setAccessible(true);
            return ef.getBoolean(null);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static String currentPhase() {
        try {
            Class<?> cls = Class.forName(CLS);
            Object inst = cls.getField("INSTANCE").get(null);
            Object p = cls.getMethod("getPhase").invoke(inst);
            return (p instanceof Enum) ? ((Enum<?>) p).name() : (p == null ? null : String.valueOf(p));
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static boolean isBluetoothOn(Context app) {
        try {
            Object s = app.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothManager bm = (s instanceof BluetoothManager) ? (BluetoothManager) s : null;
            BluetoothAdapter ad = (bm != null) ? bm.getAdapter() : null;
            return ad != null && ad.isEnabled();
        } catch (Throwable ignored) {
            return false;
        }
    }
}
