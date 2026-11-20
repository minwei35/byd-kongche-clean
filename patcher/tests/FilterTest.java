import com.qinl.car.pub.trial.SafeLog;
public class FilterTest {
 public static void main(String[] a) {
  check(!SafeLog.clean("口令帧 len=20 hex=5BB5E2010203").contains("010203"));
  check(!SafeLog.clean("[WatchApi] response=encryptedblob").contains("encryptedblob"));
  check(!SafeLog.clean("password=foo").contains("foo"));
  check(!SafeLog.clean("pwd14:secret").contains("secret"));
  check(!SafeLog.clean("hex=5BB5E10102030405060708090A0B0C0D0E00F5FA").contains("010203"));
  check(SafeLog.clean("RX A5 5A 21 status=19").equals("RX A5 5A 21 status=19"));
  check(!SafeLog.clean("uid=13631315741").contains("13631315741"));
  check(!SafeLog.clean("vin=LC0CE6CD6M1115465").contains("LC0CE6"));
  System.out.println("PASS 8 safe log cases");
 }
 static void check(boolean v) { if (!v) throw new AssertionError(); }
}
