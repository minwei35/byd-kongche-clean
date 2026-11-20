from pathlib import Path
import tempfile,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
J=Path('C:/Program Files/java/jdk-11.0.18/bin')
class DurabilityTest(unittest.TestCase):
 def test_real_baseline_commit_failure_and_retry(self):
  with tempfile.TemporaryDirectory() as d:
   t=Path(d)
   sources={
   'android/content/SharedPreferences.java':'''package android.content;public interface SharedPreferences{boolean getBoolean(String k,boolean d);String getString(String k,String d);Editor edit();interface Editor{Editor putBoolean(String k,boolean v);Editor putString(String k,String v);Editor putLong(String k,long v);boolean commit();}}''',
   'android/content/Context.java':'''package android.content;import java.util.*;public class Context {public Map<String,P> maps=new HashMap<>();public SharedPreferences getSharedPreferences(String n,int m){return maps.computeIfAbsent(n,k->new P());}public static class P implements SharedPreferences {public Map<String,Object> data=new HashMap<>();public boolean fail;public boolean getBoolean(String k,boolean d){return (Boolean)data.getOrDefault(k,d);}public String getString(String k,String d){return (String)data.getOrDefault(k,d);}public Editor edit(){return new E();}class E implements Editor{Map<String,Object> next=new HashMap<>();public Editor putBoolean(String k,boolean v){next.put(k,v);return this;}public Editor putString(String k,String v){next.put(k,v);return this;}public Editor putLong(String k,long v){next.put(k,v);return this;}public boolean commit(){if(fail)return false;data.putAll(next);return true;}}}}''',
   'org/json/JSONArray.java':'''package org.json;public class JSONArray{public JSONArray(){}public JSONArray(String s){}public int length(){return 0;}public JSONObject optJSONObject(int i){return null;}public void put(Object o){}public String toString(){return "[]";}}''',
   'org/json/JSONObject.java':'''package org.json;public class JSONObject{public void put(String k,Object v){}}''',
   'com/qinl/car/pub/CredentialManager.java':'''package com.qinl.car.pub;import java.util.*;public class CredentialManager{public static final CredentialManager INSTANCE=new CredentialManager();public boolean fail;Map<String,String> data=new HashMap<>();public void init(android.content.Context c){if(fail)throw new RuntimeException();}public void put(String k,String v){data.put(k,v);}public String get(String k,String d){return data.getOrDefault(k,d);}}''',
   'BaselineFailure.java':'''import android.content.*;import com.qinl.car.pub.trial.*;import com.qinl.car.pub.CredentialManager;public class BaselineFailure{static void c(boolean v){if(!v)throw new AssertionError();}public static void main(String[]a){Context x=new Context();Context.P rt=(Context.P)x.getSharedPreferences("qinl_runtime",0);rt.fail=true;Baseline.apply(x);c(Baseline.status().equals("migration_incomplete"));rt.fail=false;CredentialManager.INSTANCE.fail=true;Baseline.apply(x);c(Baseline.status().equals("migration_incomplete"));rt.edit().putBoolean("ble_auto_near",true).commit();CredentialManager.INSTANCE.fail=false;Baseline.apply(x);c(Baseline.status().equals("ready"));c(rt.getBoolean("ble_auto_near",false));rt.edit().putBoolean("ble_auto_far",true).commit();Baseline.apply(x);c(rt.getBoolean("ble_auto_far",false));System.out.println("PASS no startup exception, staged retry and completed migration preservation");}}'''}
   for n,v in sources.items():
    p=t/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v,encoding='utf-8')
   files=list(t.rglob('*.java'))+[ROOT/'src/com/qinl/car/pub/trial'/n for n in ['Baseline.java','BaselinePolicy.java']]
   subprocess.run([str(J/'javac.exe'),'-encoding','UTF-8','-d',str(t/'c')]+list(map(str,files)),check=True,capture_output=True)
   r=subprocess.run([str(J/'java.exe'),'-cp',str(t/'c'),'BaselineFailure'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
