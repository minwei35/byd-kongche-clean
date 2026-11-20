package com.qinl.car.pub.trial;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 4.9：比亚迪官方 App 的充电通知监听（只认这一个包，只留时刻与类型）。
 *
 * 隐私边界（用户要求确认过）：
 *   · Android 的通知使用权是**整机级**授权 —— 系统会把所有应用的通知都递进来，
 *     没有"只给某个包"的开关。所以隔离只能靠代码，下面是硬约束：
 *   · 第一行就比包名：不是 com.byd.aeri.caranywhere 的通知**立即 return**，
 *     不解析、不落盘、不留痕；
 *   · 即使是官方 App 的通知，也要过"充电关键词"才记，其它车辆消息（开锁/OTA/消毒…）一律丢；
 *   · 落盘内容：marks 只存 {ts, kind}；samples 只留最近 6 条**匹配到**的通知原文（各截断 40 字），
 *     仅用于文案对不齐时排错，可在界面上清空；
 *   · 不联网、不上传、不写外部存储、不进日志。
 */
public final class ChargeNotify extends NotificationListenerService {

    public static final String PKG = "com.byd.aeri.caranywhere";
    private static final String PREF = "kc_charge";
    private static final String KEY_MARKS = "marks";
    private static final String KEY_SAMPLES = "samples";
    private static final int MAX_MARKS = 120;
    private static final int MAX_SAMPLES = 6;

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null || !PKG.equals(sbn.getPackageName())) return;  // ← 只认官方 App
            Bundle ex = sbn.getNotification() == null ? null : sbn.getNotification().extras;
            if (ex == null) return;
            String title = str(ex.getCharSequence("android.title"));
            String text = str(ex.getCharSequence("android.text"));
            String big = str(ex.getCharSequence("android.bigText"));
            String kind = classify(title + " " + text + " " + big);
            if (kind == null) return;                                       // ← 只认充电事件
            long ts = sbn.getPostTime() > 0 ? sbn.getPostTime() / 1000 : System.currentTimeMillis() / 1000;
            addMark(ts, kind);
            addSample(ts, kind, title, text);
        } catch (Throwable t) {
            // 监听器绝不能因为解析失败把系统通知服务带崩
        }
    }

    private static String str(CharSequence cs) { return cs == null ? "" : cs.toString(); }

    /** 只认充电相关；返回 start / stop / done，认不出返回 null（不记）。 */
    private static String classify(String s) {
        if (s == null || s.length() == 0) return null;
        boolean chg = s.contains("充电") || s.contains("补能") || s.contains("插枪") || s.contains("拔枪");
        if (!chg) return null;
        if (s.contains("完成") || s.contains("充满") || s.contains("结束") || s.contains("已拔枪")) return "done";
        if (s.contains("停止") || s.contains("中断") || s.contains("异常")) return "stop";
        if (s.contains("开始") || s.contains("已插枪") || s.contains("启动")) return "start";
        return null;
    }

    /** marks：只存时刻与类型，不带任何原文。 */
    private synchronized void addMark(long ts, String kind) {
        try {
            SharedPreferences sp = prefs();
            JSONArray arr = new JSONArray(sp.getString(KEY_MARKS, "[]"));
            JSONArray out = new JSONArray();
            int from = Math.max(0, arr.length() - (MAX_MARKS - 1));
            for (int i = from; i < arr.length(); i++) out.put(arr.get(i));
            out.put(new JSONObject().put("ts", ts).put("kind", kind));
            sp.edit().putString(KEY_MARKS, out.toString()).apply();
        } catch (Throwable t) { }
    }

    /** samples：只留最近几条匹配到的原文，供文案对不上时排查，界面可一键清空。 */
    private synchronized void addSample(long ts, String kind, String title, String text) {
        try {
            SharedPreferences sp = prefs();
            JSONArray arr = new JSONArray(sp.getString(KEY_SAMPLES, "[]"));
            JSONArray out = new JSONArray();
            int from = Math.max(0, arr.length() - (MAX_SAMPLES - 1));
            for (int i = from; i < arr.length(); i++) out.put(arr.get(i));
            out.put(new JSONObject().put("ts", ts).put("kind", kind)
                    .put("title", cut(title)).put("text", cut(text)));
            sp.edit().putString(KEY_SAMPLES, out.toString()).apply();
        } catch (Throwable t) { }
    }

    private static String cut(String s) {
        if (s == null) return "";
        s = s.trim();
        return s.length() > 40 ? s.substring(0, 40) : s;
    }

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    private SharedPreferences prefs() { return prefs(getApplicationContext()); }
}
