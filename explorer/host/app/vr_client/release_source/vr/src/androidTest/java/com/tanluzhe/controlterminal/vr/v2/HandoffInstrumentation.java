package com.tanluzhe.controlterminal.vr.v2;
import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.os.*;
import android.text.*;
import android.text.method.DigitsKeyListener;
import android.widget.EditText;
import com.tanluzhe.controlterminal.vr.*;
import java.io.*;
import java.util.*;
/** No-headset, no-network checks intended for the eventual Quest device. */
public final class HandoffInstrumentation extends Instrumentation {
  private boolean captureSmoke;
  @Override
  public void onCreate(Bundle args) {
    super.onCreate(args);
    captureSmoke=args!=null&&"true".equals(args.getString("capture"));
    start();
  }
  @Override
  public void onStart() {
    Bundle result = new Bundle();
    int code = Activity.RESULT_CANCELED;
    try {
      Context c = getTargetContext();
      Context isolated = new ContextWrapper(c) {
        @Override
        public SharedPreferences getSharedPreferences(String n, int mode) {
          return super.getSharedPreferences("handoff_test_" + n, mode);
        }
      };
      isolated.getSharedPreferences("v2", 0).edit().clear().commit();
      require(new ConnectionSettings(isolated).token.equals("1"), "default credential");
      ConnectionSettings direct=new ConnectionSettings(isolated);
      require(!direct.automatic && direct.manualHost.equals("192.168.137.2")&&direct.port==8088,"direct AIPC defaults");
      for(VrUiState.Rect r:VrUiState.DIALOG)require(r.id<8||r.id>11,"no lease/sync/enable menu");
      long now=System.nanoTime();
      Telemetry telemetry=AipcTelemetry.parse(new org.json.JSONObject("{\"mode\":\"base\",\"mode_text\":\"RC\",\"stopped\":true,\"base\":{\"vx\":0.3,\"vy\":0.4},\"arms\":{\"left\":{\"state\":\"moving\",\"ee_quat\":[0,0,0,2],\"grip_open\":0.5,\"link_cm\":[[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]]}}}"),now);
      require(telemetry.left.links.length==7&&telemetry.left.quaternion[3]==1&&telemetry.right.links==null,"telemetry seven joints and normalized xyzw quaternion");
      require(telemetry.stopped&&!telemetry.errors(now).isEmpty()&&Math.abs(telemetry.vx-.3)<1e-6,"telemetry stopped and speed parse");
      Telemetry missing=AipcTelemetry.parse(new org.json.JSONObject("{}"),now);
      require(Double.isNaN(missing.vx)&&missing.left.links==null,"missing telemetry never invented");
      final Throwable[] error = new Throwable[1];
      runOnMainSync(() -> {
        try {
          EditText ip = new EditText(c);
          ip.setKeyListener(DigitsKeyListener.getInstance("0123456789."));
          ip.setRawInputType(android.text.InputType.TYPE_CLASS_TEXT
              | android.text.InputType.TYPE_TEXT_VARIATION_URI);
          ip.setText("");
          ip.getText().append("192.168.137.1");
          require(ip.getText().toString().equals("192.168.137.1"), "three dots accepted");
        } catch (Throwable e) {
          error[0] = e;
        }
      });
      if (error[0] != null)
        throw new AssertionError(error[0]);
      require(ConnectionSettings.validIpv4("192.168.137.1")
              && !ConnectionSettings.validIpv4("192.168..1"),
          "IPv4 validation");
      try {
        c.getPackageManager().getActivityInfo(
            new ComponentName(c, "com.tanluzhe.controlterminal.vr.ConfiguredVrActivity"), 0);
        throw new AssertionError("legacy entry still exists");
      } catch (android.content.pm.PackageManager.NameNotFoundException expected) {
      }
      android.content.pm.ActivityInfo receiver =
          c.getPackageManager().getReceiverInfo(new ComponentName(c, DebugReceiver.class), 0);
      require("android.permission.DUMP".equals(receiver.permission), "ADB receiver permission");
      require(AppLog.safe("Authorization: Bearer handoff-secret").indexOf("handoff-secret") == -1,
          "Bearer redaction");
      AppLog.init(c, "ui");
      AppLog.info("APP", "HANDOFF_SMOKE", "本地测试事件，不连接基站");
      VrUiState ui = new VrUiState();
      Dashboard state = new Dashboard();
      state.simulation = true;
      Bitmap image = Bitmap.createBitmap(1600, 1000, Bitmap.Config.ARGB_8888);
      for (int mode = 0; mode < 4; mode++) {
        ui.menuOpen = mode == 1;
        ui.logsOpen = mode == 2;
        ui.videoPanel = mode == 3;
        ui.logLines = new String[] {"12:00:00 INFO INPUT/SAMPLE valid=63 (synthetic test)"};
        new VrHud().draw(image, state, ui, System.nanoTime(), false);
        try (FileOutputStream out =
                 c.openFileOutput("handoff-ui-" + mode + ".png", Context.MODE_PRIVATE)) {
          require(image.compress(Bitmap.CompressFormat.PNG, 100, out), "HUD PNG");
        }
      }
      new VrHud().drawWorld(image,state,ui,System.nanoTime(),false);
      try(FileOutputStream out=c.openFileOutput("handoff-world.png",Context.MODE_PRIVATE)) {
        require(image.compress(Bitmap.CompressFormat.PNG,100,out),"world HUD PNG");
      }
      image.recycle();
      if(captureSmoke)CaptureDeviceCheck.run(c);
      code = Activity.RESULT_OK;
      result.putString("stream",
          "PASS: default credential, IPv4 editing with3 dots, no legacy activity, debug "
          + "permission, redaction, HUD layouts. Optional capture smoke="+captureSmoke+". No physical IME/XR/network test.");
    } catch (Throwable e) {
      result.putString("stream", "FAIL: " + e);
    }
    finish(code, result);
  }
  private static void require(boolean value, String label) {
    if (!value)
      throw new AssertionError(label);
  }
}
