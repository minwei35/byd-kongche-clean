package com.qinl.car.pub.trial;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 1.0.3: Local time-range log archive exporter + diagnostic bridge (window.KCLog).
 * Reads persisted daily files in files/logs/app-YYYYMMDD.txt + in-memory AppLog,
 * filters by [startMs, endMs], packs a ZIP into Download/BYD-Kongche-Logs/,
 * and offers Android system share. Zero network / upload capability.
 */
public final class LogExportApi {
    private static final String SUBDIR = "BYD-Kongche-Logs";
    private static final String AUTH_SUFFIX = ".diagfile";
    private static final Pattern FILE_PAT = Pattern.compile("^app-(\\d{4})(\\d{2})(\\d{2})\\.txt$");
    // Inner AppLog timestamp: [11-26 13:07:05.123] or [11-26 13:07:05]
    private static final Pattern INNER_TS = Pattern.compile("\\[(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2}):(\\d{2})(?:\\.(\\d{1,3}))?\\]");
    // Outer LogUploader flush timestamp: [2026-11-26 13:07:12]
    private static final Pattern OUTER_TS = Pattern.compile("^\\[(\\d{4})-(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2}):(\\d{2})(?:\\.(\\d{1,3}))?\\]");
    private static final Pattern PHONE_PAT = Pattern.compile("(?<![0-9])1[3-9][0-9]{9}(?![0-9])");
    private static final Pattern VIN_PAT = Pattern.compile("(?i)\\b[A-HJ-NPR-Z0-9]{17}\\b");

    private final Activity act;

    private LogExportApi(Activity act) {
        this.act = act;
    }

    public static void attach(Activity act, WebView web) {
        if (act == null || web == null) return;
        try {
            web.addJavascriptInterface(new LogExportApi(act), "KCLog");
        } catch (Throwable t) {
            Log.w("KC", "attach KCLog failed", t);
        }
    }

    @JavascriptInterface
    public void note(String line, boolean persist) {
        if (line == null) return;
        Log.i("KC", line);
        if (persist) {
            PauseOverride.appLog(line);
        }
    }

    @JavascriptInterface
    public String tempResume(int minutes) {
        try {
            long until = PauseOverride.resumeFor(act, minutes);
            JSONObject j = new JSONObject();
            j.put("ok", 1);
            j.put("untilMs", until);
            j.put("remainSec", PauseOverride.remainingSec(act));
            return j.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    @JavascriptInterface
    public String cancelTempResume() {
        try {
            PauseOverride.cancel(act);
            JSONObject j = new JSONObject();
            j.put("ok", 1);
            return j.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    @JavascriptInterface
    public String rebuildBle() {
        try {
            boolean fired = GattWatchdog.forceRebuild(act, "蓝牙页按钮重建");
            JSONObject j = new JSONObject();
            j.put("ok", 1);
            j.put("rebuilt", fired ? 1 : 0);
            return j.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    @JavascriptInterface
    public String pauseStatus() {
        try {
            Context app = act.getApplicationContext();
            JSONObject j = new JSONObject();
            j.put("ok", 1);
            j.put("tempRemainSec", PauseOverride.remainingSec(app));
            j.put("running", PauseOverride.isBleServiceRunning() ? 1 : 0);
            j.put("autoPaused", reflectBool("com.qinl.car.pub.AutoPause", "active", app) ? 1 : 0);
            j.put("userPaused", reflectBool("com.qinl.car.pub.wui.BleRuntime", "userPauseOn", app) ? 1 : 0);
            j.put("verdict", reflectStr("com.qinl.car.pub.wui.BleRuntime", "getWifiVerdict"));
            return j.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    @JavascriptInterface
    public String info() {
        try {
            flushLogs(120);
            Context app = act.getApplicationContext();
            List<File> files = listLogFiles(app);
            JSONArray days = new JSONArray();
            int totalLines = 0;
            String minDate = "";
            String maxDate = "";
            for (File f : files) {
                Matcher m = FILE_PAT.matcher(f.getName());
                if (!m.matches()) continue;
                String d = m.group(1) + "-" + m.group(2) + "-" + m.group(3);
                int lines = countLines(f);
                totalLines += lines;
                if (minDate.isEmpty()) minDate = d;
                maxDate = d;
                JSONObject item = new JSONObject();
                item.put("date", d);
                item.put("kb", Math.max(1L, (f.length() + 1023L) / 1024L));
                item.put("lines", lines);
                days.put(item);
            }
            String mem = appLogAll();
            int memLines = mem.isEmpty() ? 0 : mem.split("\n").length;
            if (totalLines == 0 && memLines > 0) {
                String today = new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date());
                minDate = today;
                maxDate = today;
                totalLines = memLines;
            }
            JSONObject out = new JSONObject();
            out.put("ok", 1);
            out.put("minDate", minDate);
            out.put("maxDate", maxDate);
            out.put("days", days);
            out.put("totalLines", totalLines);
            out.put("memLines", memLines);
            out.put("keepDays", readKeepDays());
            out.put("tempRemainSec", PauseOverride.remainingSec(app));
            return out.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    @JavascriptInterface
    public String exportRange(long startMs, long endMs, String scopePng, String label) {
        try {
            flushLogs(180);
            Context app = act.getApplicationContext();
            boolean filter = (startMs > 0L && endMs > 0L && endMs >= startMs);
            List<File> files = listLogFiles(app);

            // Narrow file list to dates overlapping [startMs - 1 day, endMs + 1 day]
            String minYmd = "";
            String maxYmd = "";
            if (filter) {
                SimpleDateFormat ymdFmt = new SimpleDateFormat("yyyyMMdd", Locale.US);
                minYmd = ymdFmt.format(new Date(startMs - 86400_000L));
                maxYmd = ymdFmt.format(new Date(endMs + 86400_000L));
            }

            List<String> matched = new ArrayList<>();
            Set<String> seenTail = new HashSet<>();
            int scanned = 0;
            int fileCount = 0;

            for (File f : files) {
                Matcher fm = FILE_PAT.matcher(f.getName());
                if (!fm.matches()) continue;
                int fileYear = Integer.parseInt(fm.group(1));
                int fileMonth = Integer.parseInt(fm.group(2));
                String fileYmd = fm.group(1) + fm.group(2) + fm.group(3);
                if (filter && (fileYmd.compareTo(minYmd) < 0 || fileYmd.compareTo(maxYmd) > 0)) {
                    continue;
                }
                fileCount++;
                long lastTs = 0L;
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8), 16384)) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        scanned++;
                        long ts = parseLineTs(line, fileYear, fileMonth);
                        if (ts > 0L) lastTs = ts;
                        else ts = lastTs;
                        if (!filter || (ts >= startMs && ts <= endMs)) {
                            String clean = maskLite(line);
                            matched.add(clean);
                            String core = extractCore(clean);
                            if (seenTail.size() < 4000) seenTail.add(core);
                        }
                    }
                } catch (Throwable ignored) {}
            }

            // Merge in-memory AppLog lines that may not have flushed yet
            String memAll = appLogAll();
            if (!memAll.isEmpty()) {
                Calendar nowCal = Calendar.getInstance();
                int curYear = nowCal.get(Calendar.YEAR);
                int curMonth = nowCal.get(Calendar.MONTH) + 1;
                long lastTs = 0L;
                for (String raw : memAll.split("\n")) {
                    if (raw == null || raw.isEmpty()) continue;
                    String clean = maskLite(raw);
                    if (seenTail.contains(extractCore(clean))) continue;
                    scanned++;
                    long ts = parseLineTs(clean, curYear, curMonth);
                    if (ts > 0L) lastTs = ts;
                    else ts = lastTs;
                    if (!filter || (ts >= startMs && ts <= endMs)) {
                        matched.add(clean);
                    }
                }
            }

            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            String rangeTag = buildRangeTag(filter, startMs, endMs, stamp);
            String zipName = "kongche-log-" + rangeTag + ".zip";
            String rangeHuman = filter
                    ? (fmtFull(startMs) + " ~ " + fmtFull(endMs))
                    : "全部留存日志";
            if (label != null && !label.trim().isEmpty()) {
                rangeHuman = label.trim() + "（" + rangeHuman + "）";
            }

            File workDir = app.getExternalFilesDir("diag");
            if (workDir == null) workDir = new File(app.getFilesDir(), "diag");
            if (!workDir.exists()) workDir.mkdirs();
            File zipFile = new File(workDir, zipName);

            String summary = buildSummary(app, rangeHuman, files, fileCount, scanned, matched.size());
            writeZip(zipFile, rangeTag, summary, matched, new File(app.getFilesDir(), "crash.log"), scopePng);

            Uri pubUri = publishZipToDownloads(app, zipFile, zipName);
            boolean published = (pubUri != null);
            String dirHint = published ? ("Download/" + SUBDIR + "/") : workDir.getAbsolutePath();
            long kb = Math.max(1L, (zipFile.length() + 1023L) / 1024L);

            showExportDialog(zipFile, pubUri, zipName, rangeHuman, matched.size(), kb, dirHint);

            JSONObject res = new JSONObject();
            res.put("ok", 1);
            res.put("file", zipName);
            res.put("dir", dirHint);
            res.put("published", published ? 1 : 0);
            res.put("lines", matched.size());
            res.put("scanned", scanned);
            res.put("kb", kb);
            return res.toString();
        } catch (Throwable t) {
            return errJson(t);
        }
    }

    private void writeZip(File outZip, String tag, String summary, List<String> lines, File crashFile, String scopePng) throws Exception {
        try (ZipOutputStream zos = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(outZip)))) {
            zos.putNextEntry(new ZipEntry("summary.txt"));
            zos.write(summary.getBytes(StandardCharsets.UTF_8));
            zos.closeEntry();

            zos.putNextEntry(new ZipEntry("logs-" + tag + ".txt"));
            if (lines.isEmpty()) {
                zos.write("（该时间段内没有匹配到日志行。请检查 summary.txt 中的本机留存日期列表。）\n".getBytes(StandardCharsets.UTF_8));
            } else {
                byte[] nl = "\n".getBytes(StandardCharsets.UTF_8);
                for (String l : lines) {
                    zos.write(l.getBytes(StandardCharsets.UTF_8));
                    zos.write(nl);
                }
            }
            zos.closeEntry();

            if (crashFile != null && crashFile.isFile() && crashFile.length() > 0L) {
                zos.putNextEntry(new ZipEntry("crash.log"));
                try (FileInputStream fis = new FileInputStream(crashFile)) {
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = fis.read(buf)) > 0) zos.write(buf, 0, n);
                }
                zos.closeEntry();
            }

            if (scopePng != null && scopePng.startsWith("data:image/")) {
                int comma = scopePng.indexOf(',');
                if (comma > 0) {
                    try {
                        byte[] img = Base64.decode(scopePng.substring(comma + 1), Base64.DEFAULT);
                        if (img != null && img.length > 0) {
                            String ext = scopePng.substring(0, comma).toLowerCase(Locale.US).contains("jpeg") ? "jpg" : "png";
                            zos.putNextEntry(new ZipEntry("scope-" + tag + "." + ext));
                            zos.write(img);
                            zos.closeEntry();
                        }
                    } catch (Throwable ignored) {}
                }
            }
        }
    }

    private Uri publishZipToDownloads(Context app, File zipFile, String zipName) {
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                ContentResolver cr = app.getContentResolver();
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.MediaColumns.DISPLAY_NAME, zipName);
                cv.put(MediaStore.MediaColumns.MIME_TYPE, "application/zip");
                cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + SUBDIR);
                cv.put(MediaStore.MediaColumns.IS_PENDING, 1);
                Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) return null;
                try (OutputStream os = cr.openOutputStream(uri);
                     FileInputStream fis = new FileInputStream(zipFile)) {
                    if (os == null) return null;
                    byte[] buf = new byte[16384];
                    int n;
                    while ((n = fis.read(buf)) > 0) os.write(buf, 0, n);
                }
                ContentValues done = new ContentValues();
                done.put(MediaStore.MediaColumns.IS_PENDING, 0);
                cr.update(uri, done, null, null);
                return uri;
            } else {
                File pubDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), SUBDIR);
                if (!pubDir.exists()) pubDir.mkdirs();
                File dst = new File(pubDir, zipName);
                try (FileInputStream fis = new FileInputStream(zipFile);
                     FileOutputStream fos = new FileOutputStream(dst)) {
                    byte[] buf = new byte[16384];
                    int n;
                    while ((n = fis.read(buf)) > 0) fos.write(buf, 0, n);
                }
                return fileProviderUri(app, dst);
            }
        } catch (Throwable t) {
            Log.w("KC", "publishZipToDownloads failed", t);
            return null;
        }
    }

    private void showExportDialog(final File zipFile, final Uri pubUri, final String zipName,
                                  final String rangeHuman, final int lines, final long kb, final String dirHint) {
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (act.isFinishing() || act.isDestroyed()) return;
                try {
                    String msg = "时间段：" + rangeHuman
                            + "\n匹配行数：" + lines + " 行（" + kb + " KB）"
                            + "\n文件名：" + zipName
                            + "\n已保存到：" + dirHint;
                    new AlertDialog.Builder(act)
                            .setTitle("日志压缩包已生成")
                            .setMessage(msg)
                            .setPositiveButton("分享 / 发送", new DialogInterface.OnClickListener() {
                                @Override
                                public void onClick(DialogInterface d, int w) {
                                    shareZip(zipFile, pubUri, zipName);
                                }
                            })
                            .setNegativeButton("关闭", null)
                            .setCancelable(true)
                            .show();
                } catch (Throwable ignored) {}
            }
        });
    }

    private void shareZip(File zipFile, Uri pubUri, String zipName) {
        try {
            Uri uri = pubUri != null ? pubUri : fileProviderUri(act, zipFile);
            if (uri == null) return;
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("application/zip");
            intent.putExtra(Intent.EXTRA_STREAM, uri);
            intent.putExtra(Intent.EXTRA_SUBJECT, zipName);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            act.startActivity(Intent.createChooser(intent, "发送 " + zipName));
        } catch (Throwable t) {
            Log.w("KC", "shareZip failed", t);
        }
    }

    private static Uri fileProviderUri(Context ctx, File f) {
        try {
            Class<?> fp = Class.forName("androidx.core.content.FileProvider");
            return (Uri) fp.getMethod("getUriForFile", Context.class, String.class, File.class)
                    .invoke(null, ctx, ctx.getPackageName() + AUTH_SUFFIX, f);
        } catch (Throwable t) {
            return null;
        }
    }

    private String buildSummary(Context app, String rangeHuman, List<File> allFiles,
                                int scannedFiles, int scannedLines, int matchedLines) {
        StringBuilder sb = new StringBuilder();
        sb.append("============================================================\n");
        sb.append(" BYD 控车 · 本地日志压缩包\n");
        sb.append("============================================================\n");
        sb.append("导出时间 ：").append(fmtFull(System.currentTimeMillis())).append('\n');
        sb.append("筛选范围 ：").append(rangeHuman).append('\n');
        sb.append("App 版本 ：").append(reflectStr("com.qinl.car.pub.AppLog", "getAppVersion")).append('\n');
        sb.append("Android  ：").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        sb.append("机型     ：").append(Build.MANUFACTURER).append(' ').append(Build.MODEL).append('\n');
        sb.append("扫描统计 ：").append(scannedFiles).append(" 个文件 / ").append(scannedLines)
          .append(" 行 → 命中 ").append(matchedLines).append(" 行\n\n");

        sb.append("── 导出时刻的保活/停扫状态 ─────────────────────────────────\n");
        sb.append("BleScanService 运行中 ：").append(PauseOverride.isBleServiceRunning()).append('\n');
        sb.append("AutoPause.active      ：").append(reflectBool("com.qinl.car.pub.AutoPause", "active", app)).append('\n');
        sb.append("BleRuntime.bgPaused   ：").append(reflectBool("com.qinl.car.pub.wui.BleRuntime", "bgPaused", app)).append('\n');
        sb.append("BleRuntime.userPause  ：").append(reflectBool("com.qinl.car.pub.wui.BleRuntime", "userPauseOn", app)).append('\n');
        sb.append("BleRuntime.wifiPause  ：").append(reflectBool("com.qinl.car.pub.wui.BleRuntime", "wifiPauseActive", app)).append('\n');
        sb.append("BleRuntime.schedPause ：").append(reflectBool("com.qinl.car.pub.wui.BleRuntime", "schedPauseActive", app)).append('\n');
        sb.append("WiFi 停扫判定         ：").append(reflectStr("com.qinl.car.pub.wui.BleRuntime", "getWifiVerdict")).append('\n');
        sb.append("临时恢复剩余秒数      ：").append(PauseOverride.remainingSec(app)).append(" s\n");
        sb.append("GATT 自愈连续重建     ：").append(GattWatchdog.getConsecutiveRebuilds()).append(" 次（当前 WAIT_RETRY ").append(GattWatchdog.getWaitRetrySec()).append(" s）\n\n");

        sb.append("── 本机留存日志文件（files/logs/）──────────────────────────\n");
        if (allFiles.isEmpty()) {
            sb.append("（暂无落盘文件）\n");
        } else {
            for (File f : allFiles) {
                sb.append("  ").append(f.getName()).append("  (").append(Math.max(1L, (f.length() + 1023L) / 1024L)).append(" KB)\n");
            }
        }
        String dirty = reflectStr("com.qinl.car.pub.AdvancedConfig", "exportDirtyText");
        if (!dirty.isEmpty()) {
            sb.append("\n── 非默认高级参数 ──────────────────────────────────────────\n");
            sb.append(dirty).append('\n');
        }
        return sb.toString();
    }

    static long parseLineTs(String line, int fileYear, int fileMonth) {
        if (line == null || line.isEmpty()) return 0L;
        // 1. Prefer inner [MM-dd HH:mm:ss(.SSS)] (exact AppLog event timestamp)
        Matcher m = INNER_TS.matcher(line);
        if (m.find()) {
            try {
                int mo = Integer.parseInt(m.group(1));
                int da = Integer.parseInt(m.group(2));
                int hh = Integer.parseInt(m.group(3));
                int mi = Integer.parseInt(m.group(4));
                int ss = Integer.parseInt(m.group(5));
                int ms = parseMs(m.group(6));
                int yr = fileYear;
                if (fileMonth == 1 && mo == 12) yr = fileYear - 1;
                else if (fileMonth == 12 && mo == 1) yr = fileYear + 1;
                Calendar cal = Calendar.getInstance();
                cal.set(yr, mo - 1, da, hh, mi, ss);
                cal.set(Calendar.MILLISECOND, ms);
                return cal.getTimeInMillis();
            } catch (Throwable ignored) {}
        }
        // 2. Fallback to outer [yyyy-MM-dd HH:mm:ss(.SSS)]
        Matcher o = OUTER_TS.matcher(line);
        if (o.find()) {
            try {
                int yr = Integer.parseInt(o.group(1));
                int mo = Integer.parseInt(o.group(2));
                int da = Integer.parseInt(o.group(3));
                int hh = Integer.parseInt(o.group(4));
                int mi = Integer.parseInt(o.group(5));
                int ss = Integer.parseInt(o.group(6));
                int ms = parseMs(o.group(7));
                Calendar cal = Calendar.getInstance();
                cal.set(yr, mo - 1, da, hh, mi, ss);
                cal.set(Calendar.MILLISECOND, ms);
                return cal.getTimeInMillis();
            } catch (Throwable ignored) {}
        }
        return 0L;
    }

    private static int parseMs(String g) {
        if (g == null || g.isEmpty()) return 0;
        if (g.length() == 1) return Integer.parseInt(g) * 100;
        if (g.length() == 2) return Integer.parseInt(g) * 10;
        return Integer.parseInt(g);
    }

    private static String extractCore(String line) {
        Matcher m = INNER_TS.matcher(line);
        if (m.find()) return line.substring(m.start());
        return line;
    }

    private static String maskLite(String s) {
        String r = PHONE_PAT.matcher(s).replaceAll("[phone]");
        r = VIN_PAT.matcher(r).replaceAll("[vin]");
        return r;
    }

    private static String buildRangeTag(boolean filter, long s, long e, String fallbackStamp) {
        if (!filter) return "all-" + fallbackStamp;
        SimpleDateFormat d = new SimpleDateFormat("MMdd", Locale.US);
        SimpleDateFormat t = new SimpleDateFormat("HHmm", Locale.US);
        String ds = d.format(new Date(s));
        String de = d.format(new Date(e));
        if (ds.equals(de)) {
            return ds + "_" + t.format(new Date(s)) + "-" + t.format(new Date(e));
        }
        return ds + "_" + t.format(new Date(s)) + "-" + de + "_" + t.format(new Date(e));
    }

    private static String fmtFull(long ms) {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date(ms));
    }

    private static List<File> listLogFiles(Context app) {
        File dir = new File(app.getFilesDir(), "logs");
        File[] arr = dir.listFiles();
        if (arr == null || arr.length == 0) return Collections.emptyList();
        List<File> out = new ArrayList<>();
        for (File f : arr) {
            if (f.isFile() && FILE_PAT.matcher(f.getName()).matches()) out.add(f);
        }
        Collections.sort(out, new Comparator<File>() {
            @Override
            public int compare(File a, File b) {
                return a.getName().compareTo(b.getName());
            }
        });
        return out;
    }

    private static int countLines(File f) {
        int c = 0;
        try (BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8), 8192)) {
            while (br.readLine() != null) c++;
        } catch (Throwable ignored) {}
        return c;
    }

    private static void flushLogs(long waitMs) {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.LogUploader");
            Object inst = c.getField("INSTANCE").get(null);
            c.getMethod("flushAsync").invoke(inst);
            if (waitMs > 0L) Thread.sleep(waitMs);
        } catch (Throwable ignored) {}
    }

    private static String appLogAll() {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.AppLog");
            Object inst = c.getField("INSTANCE").get(null);
            Object r = c.getMethod("all").invoke(inst);
            return r == null ? "" : String.valueOf(r);
        } catch (Throwable ignored) {
            return "";
        }
    }

    private static int readKeepDays() {
        try {
            Class<?> c = Class.forName("com.qinl.car.pub.AdvancedConfig");
            Object inst = c.getField("INSTANCE").get(null);
            for (java.lang.reflect.Method m : c.getMethods()) {
                if (m.getParameterTypes().length == 1 && m.getParameterTypes()[0] == String.class
                        && m.getReturnType() == int.class && m.getName().equals("int")) {
                    return (Integer) m.invoke(inst, "log.keepDays");
                }
            }
        } catch (Throwable ignored) {}
        return 7;
    }

    private static boolean reflectBool(String cls, String method, Context app) {
        try {
            Class<?> c = Class.forName(cls);
            Object inst = c.getField("INSTANCE").get(null);
            Object r = c.getMethod(method, Context.class).invoke(inst, app);
            return Boolean.TRUE.equals(r);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static String reflectStr(String cls, String method) {
        try {
            Class<?> c = Class.forName(cls);
            Object inst = c.getField("INSTANCE").get(null);
            Object r = c.getMethod(method).invoke(inst);
            return r == null ? "" : String.valueOf(r);
        } catch (Throwable ignored) {
            return "";
        }
    }

    private static String errJson(Throwable t) {
        try {
            JSONObject j = new JSONObject();
            j.put("ok", 0);
            String m = t.getMessage();
            j.put("err", (m == null || m.isEmpty()) ? t.getClass().getSimpleName() : m);
            return j.toString();
        } catch (Throwable ignored) {
            return "{\"ok\":0,\"err\":\"export error\"}";
        }
    }
}
