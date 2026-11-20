package com.qinl.car.pub.trial;
import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Map;
public final class Baseline {
 private static volatile String result="not_checked";
 private Baseline(){}
 public static String status(){return result;}
 public static synchronized void apply(Context ctx){
  try {
   SharedPreferences migration=ctx.getSharedPreferences("kc_baseline",0);
   if(migration.getBoolean("secure3",false)){result="ready";return;}
   SharedPreferences runtime=ctx.getSharedPreferences("qinl_runtime",0);
   // Per-key progress lives with its value: retries never replay completed defaults.
   for(Map.Entry<String,Boolean> e:BaselinePolicy.runtime().entrySet()){
    String stage="baseline_secure3_"+e.getKey();
    if(!runtime.getBoolean(stage,false) && !runtime.edit().putBoolean(e.getKey(),e.getValue()).putBoolean(stage,true).commit())throw new Exception("runtime");
   }
   if(!runtime.getBoolean("baseline_secure3_scenes",false)){
    String wifi=disabledScenes(runtime.getString("bg_wifi_scenes","[]"));
    String schedule=disabledScenes(runtime.getString("bg_sched_scenes","[]"));
    if(!runtime.edit().putString("bg_wifi_scenes",wifi).putString("bg_sched_scenes",schedule)
      .putString("bg_wifi_ssids","").putString("bg_sched_off","")
      .putString("ble_bg_wifi_pause","").putString("ble_bg_sched_off","")
      .putBoolean("ble_bg_auto_active",false).putBoolean("ble_bg_pause",false)
      .putLong("ble_near_trend_win",10000L).putBoolean("baseline_secure3_scenes",true).commit())throw new Exception("scenes");
   }
   SharedPreferences advanced=ctx.getSharedPreferences("qinl_advanced",0);
   for(Map.Entry<String,String> e:BaselinePolicy.advanced().entrySet()){
    String stage="baseline_secure3_"+e.getKey();
    if(!advanced.getBoolean(stage,false) && !advanced.edit().putString(e.getKey(),e.getValue()).putBoolean(stage,true).commit())throw new Exception("advanced");
   }
   Class<?> c=Class.forName("com.qinl.car.pub.CredentialManager");Object cm=c.getField("INSTANCE").get(null);
   c.getMethod("init",Context.class).invoke(cm,ctx);
   for(Map.Entry<String,String> e:BaselinePolicy.thresholds().entrySet()){
    String stage="threshold_"+e.getKey();
    if(migration.getBoolean(stage,false))continue;
    String actual=(String)c.getMethod("get",String.class,String.class).invoke(cm,e.getKey(),"");
    // Existing thresholds survive interrupted migrations; only seed absent keys.
    if(actual.isEmpty()){
     c.getMethod("put",String.class,String.class).invoke(cm,e.getKey(),e.getValue());
     actual=(String)c.getMethod("get",String.class,String.class).invoke(cm,e.getKey(),"");
     if(!e.getValue().equals(actual))throw new Exception("threshold");
    }
    if(!migration.edit().putBoolean(stage,true).commit())throw new Exception("stage");
   }
   if(!migration.edit().putBoolean("secure3",true).commit())throw new Exception("completion");
   result="ready";
  }catch(Throwable failure){result="migration_incomplete";}
 }
 static String disabledScenes(String raw)throws Exception{
  JSONArray a;
  try{a=new JSONArray(raw);}catch(Exception malformed){return "[]";}
  JSONArray disabled=new JSONArray();
  for(int i=0;i<a.length();i++){
   JSONObject scene=a.optJSONObject(i);if(scene==null)continue;
   scene.put("on",false);disabled.put(scene);
  }
  return disabled.toString();
 }
}
