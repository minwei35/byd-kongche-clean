package com.qinl.car.pub.trial;
import java.util.Locale;
import java.util.regex.Pattern;
public final class SafeLog {
 private static final Pattern SENSITIVE=Pattern.compile("(?i)(password|pwd|token|secret|dkhex|keyhex|bluetoothkey|bluetoothpassword|watchblue|g2\\s*[=:]|口令|密码|密钥|凭据|response[\"\']?\\s*[=:]|\\bdk[\"\']?\\s*[=:]|原始响应|5b\\s*b5)");
 private SafeLog() {}
 public static String clean(String text) {
  if(text==null)return "";
  String s=text.replace('\r',' ').replace('\n',' ');
  if(SENSITIVE.matcher(s).find()) {
   String event="sensitive-diagnostic";
   if(s.contains("口令帧"))event="pwd-frame";
   else if(s.contains("用户帧")||s.contains("uid帧"))event="uid-frame";
   else if(s.contains("[WatchApi]"))event="watch-http-response";
   else if(s.contains("5BB5")||s.toUpperCase(Locale.US).contains("5B B5"))event="ble-frame";
   return "[诊断] "+event+" [payload-omitted]";
  }
  s=s.replaceAll("(?<![0-9])1[3-9][0-9]{9}(?![0-9])","[phone]");
  s=s.replaceAll("(?i)\\b[A-HJ-NPR-Z0-9]{17}\\b","[vin]");
  return s.length()>2048?s.substring(0,2048):s;
 }
}
