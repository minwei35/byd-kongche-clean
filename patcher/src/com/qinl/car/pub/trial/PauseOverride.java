package com.qinl.car.pub.trial;

import android.content.Context;
import android.content.SharedPreferences;
import java.lang.reflect.Method;

/**
 * 1.0.3: Temporary override for WiFi / schedule auto-pause, plus foreground sync.
 * Stored in the same "qinl_runtime" SharedPreferences used by AutoPause/BleRuntime.
 */
public final class PauseOverride {
    private static final String PREFS = "qinl_runtime";
    private static final String KEY_UNTIL = "kc_temp_resume_until";

    private PauseOverride() {}

    public static long untilMs(Context ctx) {
        if (ctx == null) return 0L;
        try {
            SharedPreferences sp = ctx.getApplicationContext().getSharedPreferences(PREFS, 0);
            return sp.getLong(KEY_UNTIL, 0L);
        } catch (Throwable t) {
            return 0L;
        }
    }

    public static boolean isActive(Context ctx) {
        long u = untilMs(ctx);
        if (u <= 0L) return false;
        long now = System.currentTimeMillis();
        if (now < u) return true;
        try {
            ctx.getApplicationContext().getSharedPreferences(PREFS, 0).edit().remove(KEY_UNTIL).apply();
        } catch (Throwable ignored) {}
        return false;
    }

    public static long remainingSec(Context ctx) {
        long diff = untilMs(ctx) - System.currentTimeMillis();
        return diff > 0L ? (diff + 999L) / 1000L : 0L;
    }

    public static long resumeFor(Context ctx, int minutes) {
        if (ctx == null) return 0L;
        Context app = ctx.getApplicationContext();
        int m = Math.max(1, Math.min(240, minutes));
        long until = System.currentTimeMillis() + m * 60_000L;
        try {
            app.getSharedPreferences(PREFS, 0).edit().putLong(KEY_UNTIL, until).apply();
        } catch (Throwable ignored) {}
        appLog("[停扫临时恢复] 已临时恢复蓝牙扫描 " + m + " 分钟（并重置旧直连句柄，避免卡在 WAIT_RETRY）");
        stopBleDirectSession();
        autoPauseResetStreak(app);
        autoPauseSync(app, "临时恢复");
        startBleService(app);
        return until;
    }

    static void stopBleDirectSession() {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.bluetooth.BleDirectSession");
            Object inst = c.getField("INSTANCE").get(null);
            c.getMethod("stop").invoke(inst);
        } catch (Throwable ignored) {}
    }

    public static void cancel(Context ctx) {
        if (ctx == null) return;
        Context app = ctx.getApplicationContext();
        try {
            app.getSharedPreferences(PREFS, 0).edit().remove(KEY_UNTIL).apply();
        } catch (Throwable ignored) {}
        appLog("[停扫临时恢复] 已手动取消临时恢复，交回停扫策略判定");
        autoPauseSync(app, "取消临时恢复");
    }

    public static void onForeground(Context ctx) {
        if (ctx == null) return;
        Context app = ctx.getApplicationContext();
        // Clean up expired override silently, then immediately re-evaluate WiFi/schedule pause
        isActive(app);
        autoPauseSync(app, "回到前台");
        GattWatchdog.onForeground(app);
    }

    static void appLog(String msg) {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.AppLog");
            Object inst = c.getField("INSTANCE").get(null);
            c.getMethod("add", String.class).invoke(inst, msg);
        } catch (Throwable ignored) {}
    }

    static void autoPauseSync(Context app, String why) {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.AutoPause");
            Object inst = c.getField("INSTANCE").get(null);
            c.getMethod("sync", Context.class, String.class).invoke(inst, app, why);
        } catch (Throwable ignored) {}
    }

    static void autoPauseResetStreak(Context app) {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.AutoPause");
            Object inst = c.getField("INSTANCE").get(null);
            c.getMethod("resetRecheckStreak", Context.class).invoke(inst, app);
        } catch (Throwable ignored) {}
    }

    static void startBleService(Context app) {
        try {
            Class<?> svc = Class.forName("com.qinl.car.pub.BleScanService");
            Object comp = svc.getField("Companion").get(null);
            Method m = comp.getClass().getMethod("start", Context.class);
            m.invoke(comp, app);
        } catch (Throwable ignored) {}
    }

    static boolean isBleServiceRunning() {
        try {
            Class<?> svc = Class.forName("com.qinl.car.pub.BleScanService");
            Object comp = svc.getField("Companion").get(null);
            Object r = comp.getClass().getMethod("isRunning").invoke(comp);
            return Boolean.TRUE.equals(r);
        } catch (Throwable ignored) {
            return false;
        }
    }
}
