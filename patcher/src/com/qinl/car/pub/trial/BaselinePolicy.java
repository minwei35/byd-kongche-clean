package com.qinl.car.pub.trial;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.Collections;
public final class BaselinePolicy {
 private BaselinePolicy(){}
 public static boolean shouldApply(boolean applied){return !applied;}
 public static Map<String,String> advanced(){
  Map<String,String> v=new LinkedHashMap<>();
  String[][] pairs={{"scan.rssiPollMs","500"},{"prox.emaAlpha","0.2"},{"prox.outlierDb","8"},{"prox.stepJumpDb","20"},{"prox.curvFilterDb","12"},{"prox.curvBaseDb","8"},{"prox.curvBaseDbLock","6"},{"prox.curvEnable","0"},{"prox.farConfirmMs","5000"},{"scan.connLostLockMs","60000"},{"scan.lockCooldownMs","60000"},{"scan.autoActionCooldownMs","15000"},{"auto.recheckLockMs","3000"},{"pocket.enable","1"},{"pocket.unlockOnly","0"},{"pocket.offsetDb","0"},{"pocket.maxOffsetDb","12"},{"pocket.guardMs","3000"}};
  for(String[] p:pairs)v.put(p[0],p[1]);return Collections.unmodifiableMap(v);
 }
 public static Map<String,Boolean> runtime(){
  Map<String,Boolean> v=new LinkedHashMap<>();
  for(String s:new String[]{"ble_auto_near","ble_auto_far","ble_door_start","ble_near_trend"})v.put(s,false);
  return Collections.unmodifiableMap(v);
 }
 public static Map<String,String> thresholds(){
  Map<String,String> v=new LinkedHashMap<>();v.put("rssi_enter","-70");v.put("rssi_exit","-83");return Collections.unmodifiableMap(v);
 }
}
