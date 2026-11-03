package com.tanluzhe.controlterminal.vr;
import android.content.*;
import com.tanluzhe.controlterminal.vr.v2.*;
import java.io.*;
import org.json.JSONObject;
/** Shell-only debug entry. Never arms a controller or generates a motion target. */
public final class DebugReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context c, Intent i) {
    if (!BuildConfig.DEBUG) {
      setResultData("disabled in release");
      return;
    }
    AppLog.init(c, "vr");
    String command = i.getStringExtra("command");
    if (command == null)
      command = "status";
    final String action = command;
    V2Activity vr = V2Activity.current();
    try {
      if (action.equals("probe")) {
        PendingResult pending = goAsync();
        new Thread(() -> {
          try {
            ConnectionSettings s = new ConnectionSettings(c);
            pending.setResultData(ConnectionProbe.run(s.host(c), s.port, s.token));
          } finally {
            pending.finish();
          }
        }, "tlz-adb-probe").start();
        return;
      }
      if (action.equals("demo")) {
        if (vr == null)
          c.startActivity(new Intent(c, V2Activity.class)
                              .putExtra("demo", true)
                              .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        setResultData(vr == null ? "local demo started; no robot connection"
                                 : "VR already running; no new session started");
        return;
      }
      if (action.equals("status") || action.equals("snapshot")) {
        if (vr != null)
          vr.diagnostics();
        JSONObject result =
            new JSONObject().put("version", BuildConfig.VERSION_NAME).put("vr_running", vr != null);
        ConnectionSettings s = new ConnectionSettings(c);
        result.put("host", s.host(c))
            .put("port", s.port)
            .put("observation_hz", s.observationHz)
            .put("credential_configured", !s.token.isEmpty());
        File file = new File(c.getFilesDir(), "v2-diagnostics.json");
        if (file.exists() && file.length() < 65536)
          try (FileInputStream in = new FileInputStream(file)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] data = new byte[4096];
            int n;
            while ((n = in.read(data)) > 0) out.write(data, 0, n);
            result.put("last_snapshot", new JSONObject(out.toString("UTF-8")));
          }
        setResultData(result.toString());
        return;
      }
      if (!action.equals("stop") && !action.equals("exit") && !action.equals("video")
          && !action.equals("logs")) {
        setResultData("unsupported; status,snapshot,probe,demo,stop,exit,video,logs only");
        return;
      }
      setResultData(
          vr == null ? "VR not running" : vr.debugAction(action, i.getIntExtra("mode", 1)));
      AppLog.info("ADB", "COMMAND", action);
    } catch (Exception e) {
      setResultData("debug failed: " + AppLog.reason(e));
    }
  }
}
