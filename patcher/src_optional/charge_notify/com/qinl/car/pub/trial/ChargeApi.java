package com.qinl.car.pub.trial;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

/**
 * 4.9：把「官方 App 充电通知」里抓到的时刻交给页面（window.KCCharge）。
 *
 * marks()    → [{ts,kind}]  只含时刻与类型，用于算"上次充电从X到Y、之后开了多远"
 * samples()  → 最近 6 条匹配到的通知原文（截断），仅用于文案排错
 * status()   → 授权状态 / 已抓条数 / 监听器原文，用于界面提示
 * clear()    → 清空 marks 与 samples
 * openAccess() → 跳到系统「通知使用权」页
 */
public final class ChargeApi {

    private final Context ctx;

    public ChargeApi(Context c) { this.ctx = c; }

    /** 由 MainActivity.onCreate 一行 invoke-static 调起，失败不影响主流程。 */
    public static void attach(Activity a, WebView wv) {
        try {
            if (a == null || wv == null) return;
            wv.addJavascriptInterface(new ChargeApi(a.getApplicationContext()), "KCCharge");
        } catch (Throwable t) { }
    }

    @JavascriptInterface
    public String marks() {
        try { return ChargeNotify.prefs(ctx).getString("marks", "[]"); } catch (Throwable t) { return "[]"; }
    }

    @JavascriptInterface
    public String samples() {
        try { return ChargeNotify.prefs(ctx).getString("samples", "[]"); } catch (Throwable t) { return "[]"; }
    }

    @JavascriptInterface
    public String status() {
        try {
            String enabled = Settings.Secure.getString(ctx.getContentResolver(), "enabled_notification_listeners");
            String me = new ComponentName(ctx, ChargeNotify.class).flattenToString();
            boolean granted = enabled != null && enabled.contains(ctx.getPackageName());
            int n = new org.json.JSONArray(marks()).length();
            return new org.json.JSONObject()
                    .put("granted", granted)
                    .put("self", me)
                    .put("count", n)
                    .put("source", ChargeNotify.PKG)
                    .toString();
        } catch (Throwable t) {
            return "{\"granted\":false,\"count\":0}";
        }
    }

    @JavascriptInterface
    public void openAccess() {
        try {
            Intent i = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Throwable t) { }
    }

    @JavascriptInterface
    public void clear() {
        try {
            ChargeNotify.prefs(ctx).edit().remove("marks").remove("samples").apply();
        } catch (Throwable t) { }
    }
}
