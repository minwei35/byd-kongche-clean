package com.qinl.car.pub.trial;
import android.content.Context;
import android.content.Intent;
import java.io.File;
import org.json.JSONObject;
public final class SecureRuntime {
 private SecureRuntime() {}
 public static String getToken() {
  try {Class<?> c=Class.forName("com.qinl.car.pub.CredentialManager");return (String)c.getMethod("get",String.class,String.class).invoke(c.getField("INSTANCE").get(null),"trial_log_upload_token","");}catch(Throwable t){return "";}
 }
 public static void configure(Context ctx, Intent intent) {
  if(intent==null)return;
  String token=intent.getStringExtra("loguploadtoken");
  intent.removeExtra("loguploadtoken");
  if(token==null||!token.matches("[A-Za-z0-9_-]{32,128}"))return;
  if(token.equals(getToken()) || !(ctx instanceof android.app.Activity))return;
  final android.app.Activity activity=(android.app.Activity)ctx;
  final String candidate=token;
  activity.runOnUiThread(new Runnable(){public void run(){
   if(activity.isFinishing() || activity.isDestroyed())return;
   new android.app.AlertDialog.Builder(activity).setTitle("确认日志上传配置")
    .setMessage("有请求希望配置或更换 NAS 日志上传凭据。仅在你正在使用 USB 配置本应用时确认；取消会保留现有配置。")
    .setNegativeButton("取消",null).setPositiveButton("确认配置",new android.content.DialogInterface.OnClickListener(){
     public void onClick(android.content.DialogInterface dialog,int which){
      try {Class<?> c=Class.forName("com.qinl.car.pub.CredentialManager");c.getMethod("put",String.class,String.class).invoke(c.getField("INSTANCE").get(null),"trial_log_upload_token",candidate);}catch(Throwable t){}
     }
    }).setCancelable(true).show();
  }});
 }
 public static String publicConfig(String input) {
  try {JSONObject j=new JSONObject(input);String[] keys={"byd_pass","byd_pin","bemfa_uid","bemfa","log_host","signToken","encryToken","watch_pwd","ble_watch_pwd","watchBlueToothKey"};for(String k:keys)j.remove(k);return j.toString();}catch(Throwable t){return "{}";}
 }
 public static String preserveSecrets(String input) {
  try {JSONObject j=new JSONObject(input);for(String k:new String[]{"byd_pass","byd_pin"})if(j.has(k)&&j.optString(k).isEmpty())j.remove(k);return j.toString();}catch(Throwable t){return "{}";}
 }
 public static void cleanOldLogs(Context ctx) {
  android.content.SharedPreferences p=ctx.getSharedPreferences("kc_harden_migration",0);
  if(p.getBoolean("logs-v2",false))return;
  File dir=new File(ctx.getFilesDir(),"logs");File[] files=dir.listFiles();
  boolean deleted=true;
  if(dir.exists()&&files==null)deleted=false;
  if(files!=null)for(File f:files)if(f.isFile()&&f.getName().matches("app-[0-9]{8}\\.txt")&&!f.delete())deleted=false;
  File crash=new File(ctx.getFilesDir(),"crash.log");if(crash.isFile()&&!crash.delete())deleted=false;
  if(deleted)p.edit().putBoolean("logs-v2",true).commit();
 }
}
