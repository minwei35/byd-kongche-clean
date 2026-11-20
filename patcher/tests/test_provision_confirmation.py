from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
JDK=Path('C:/Program Files/java/jdk-11.0.18/bin')
class ProvisionConfirmationTest(unittest.TestCase):
 def test_external_intent_needs_local_confirmation(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp)
   sources={
   'android/content/SharedPreferences.java':'package android.content; public interface SharedPreferences {boolean getBoolean(String k,boolean d);Editor edit();interface Editor {Editor putBoolean(String k,boolean v);boolean commit();}}',
   'android/content/Context.java':'package android.content;public class Context {public java.io.File getFilesDir(){return new java.io.File(".");}public SharedPreferences getSharedPreferences(String k,int m){return null;}}',
   'android/content/Intent.java':'package android.content; public class Intent {public String token;public String getStringExtra(String k){return token;}public void removeExtra(String k){token=null;}}',
   'android/content/DialogInterface.java':'package android.content;public interface DialogInterface {interface OnClickListener {void onClick(DialogInterface d,int which);}}',
   'android/app/Activity.java':'package android.app;public class Activity extends android.content.Context {public boolean isFinishing(){return false;}public boolean isDestroyed(){return false;}public void runOnUiThread(Runnable r){r.run();}}',
   'android/app/AlertDialog.java':'package android.app;import android.content.*;public class AlertDialog {public static DialogInterface.OnClickListener positive;public static int shown;public static class Builder {public Builder(Context c){}public Builder setTitle(String s){return this;}public Builder setMessage(String s){return this;}public Builder setPositiveButton(String s,DialogInterface.OnClickListener l){positive=l;return this;}public Builder setNegativeButton(String s,DialogInterface.OnClickListener l){return this;}public Builder setCancelable(boolean b){return this;}public AlertDialog show(){shown++;return new AlertDialog();}}}',
   'org/json/JSONObject.java':'package org.json;public class JSONObject {public JSONObject(String s){}public void remove(String k){}public boolean has(String k){return false;}public String optString(String k){return "";}public String toString(){return "{}";}}',
   'com/qinl/car/pub/CredentialManager.java':'package com.qinl.car.pub;public class CredentialManager {public static final CredentialManager INSTANCE=new CredentialManager();public String value="";public String get(String k,String d){return value;}public void put(String k,String v){value=v;}}',
   'ProvisionTest.java':'''import android.app.*;import android.content.*;import com.qinl.car.pub.CredentialManager;import com.qinl.car.pub.trial.SecureRuntime;
public class ProvisionTest {static void check(boolean b){if(!b)throw new AssertionError();}static Intent intent(String t){Intent i=new Intent();i.token=t;return i;}public static void main(String[]a){String old="A".repeat(32), next="B".repeat(32);CredentialManager.INSTANCE.value=old;Intent i=intent(next);SecureRuntime.configure(new Activity(),i);check(i.token==null);check(CredentialManager.INSTANCE.value.equals(old));check(AlertDialog.shown==1);AlertDialog.positive.onClick(null,1);check(CredentialManager.INSTANCE.value.equals(next));SecureRuntime.configure(new Activity(),intent(next));check(AlertDialog.shown==1);SecureRuntime.configure(new Context(),intent(old));check(CredentialManager.INSTANCE.value.equals(next));SecureRuntime.configure(new Activity(),intent("bad"));check(AlertDialog.shown==1);System.out.println("PASS token changes require native user confirmation");}}'''}
   for name,content in sources.items():
    p=t/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')
   files=list(t.rglob('*.java'))+[ROOT/'src/com/qinl/car/pub/trial/SecureRuntime.java']
   subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-d',str(t/'classes')]+[str(x) for x in files],check=True,capture_output=True)
   r=subprocess.run([str(JDK/'java.exe'),'-cp',str(t/'classes'),'ProvisionTest'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
