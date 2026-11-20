import com.qinl.car.pub.trial.BaselinePolicy;
public final class BaselineTest {
 public static void main(String[] args){
  check(BaselinePolicy.advanced().get("scan.rssiPollMs").equals("500"));
  check(BaselinePolicy.advanced().get("prox.emaAlpha").equals("0.2"));
  check(BaselinePolicy.advanced().get("prox.curvEnable").equals("0"));
  check(BaselinePolicy.advanced().get("prox.farConfirmMs").equals("5000"));
  check(BaselinePolicy.advanced().get("pocket.maxOffsetDb").equals("12"));
  check(!BaselinePolicy.runtime().get("ble_auto_near"));
  check(!BaselinePolicy.runtime().get("ble_auto_far"));
  check(!BaselinePolicy.runtime().get("ble_door_start"));
  check(!BaselinePolicy.runtime().get("ble_near_trend"));
  check(BaselinePolicy.thresholds().get("rssi_enter").equals("-70"));
  check(BaselinePolicy.thresholds().get("rssi_exit").equals("-83"));
  for(String k:BaselinePolicy.advanced().keySet())check(!k.matches(".*(password|token|key|pin).*"));
  check(BaselinePolicy.shouldApply(false));check(!BaselinePolicy.shouldApply(true));
  try{BaselinePolicy.advanced().put("extra","1");throw new AssertionError();}catch(UnsupportedOperationException expected){}
  System.out.println("PASS baseline defaults, disabled automatic actions, immutable maps, one-time rule");
 }
 private static void check(boolean value){if(!value)throw new AssertionError();}
}
