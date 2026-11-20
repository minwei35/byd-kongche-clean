from pathlib import Path
import unittest,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src/com/qinl/car/pub/trial'
class Secure4Fixes(unittest.TestCase):
 def test_source_failure_boundaries(self):
  baseline=(SRC/'Baseline.java').read_text(encoding='utf-8')
  self.assertIn('public static String status()',baseline)
  self.assertNotIn('throw new IllegalStateException("baseline migration incomplete",e)',baseline)
  self.assertIn('stage',baseline)
  # 1.0.0：加密上传组件整体删除（公开版不留任何上报出口）
  self.assertFalse((SRC/'SecureUpload.java').exists())

 def test_watch_source_patch_is_idempotent_and_pre_sink(self):
  import sys
  sys.path.insert(0,str(ROOT))
  from reliability_patch import apply
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'smali_classes2/com/qinl/car/pub/cloud/WatchApiClient.smali'
   p.parent.mkdir(parents=True)
   original=ROOT.parents[1]/'rea/apktool/smali_classes2/com/qinl/car/pub/cloud/WatchApiClient.smali'
   p.write_bytes(original.read_bytes());apply(tmp);first=p.read_bytes();apply(tmp)
   self.assertEqual(first,p.read_bytes())
   text=p.read_text(encoding='utf-8');start=text.index('.method private final log(');body=text[start:text.index('.end method',start)]
   self.assertIn('payload-omitted',body)
   self.assertNotIn('verboseLog',body)
   self.assertLess(body.index('const-string p1'),body.index('Log;->i'))
 def test_real_java_redaction(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);t=p/'LogTest.java'
   t.write_text('''import com.qinl.car.pub.trial.SafeLog;public class LogTest {public static void main(String[]a){String[] bad={"[WatchApi] HTTP 200 {\\\"response\\\":\\\"SYNTHETIC\\\"}","dk=0102030405060708090a0b0c0d0e0f10"};for(String s:bad)if(!SafeLog.clean(s).contains("omitted"))throw new AssertionError(s);if(!SafeLog.clean("[CAL] {\\\"config\\\":{\\\"rssi_enter\\\":-70}}").contains("rssi_enter"))throw new AssertionError();}}''',encoding='utf-8')
   j=Path('C:/Program Files/java/jdk-11.0.18/bin')
   subprocess.run([str(j/'javac.exe'),'-encoding','UTF-8','-d',tmp,str(SRC/'SafeLog.java'),str(t)],check=True,capture_output=True)
   r=subprocess.run([str(j/'java.exe'),'-cp',tmp,'LogTest'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
