package com.tanluzhe.controlterminal.vr.v2;
import android.app.*;
import android.content.*;
import android.os.*;
import java.io.*;
import java.util.*;
import org.json.*;

/** Real headset engine/demo verification; never creates a live link or robot lease. */
public final class V2SmokeInstrumentation extends Instrumentation {
  @Override
  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }
  @Override
  public void onStart() {
    Bundle result = new Bundle();
    int code = Activity.RESULT_CANCELED;
    String run = UUID.randomUUID().toString();
    try {
      Context c = getTargetContext();
      result.putString("webrtc_loopback", WebRtcLoopbackCheck.run(c));
      c.deleteFile("v2-eye.png");
      c.startActivity(new Intent(c, V2Activity.class)
                          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
                          .putExtra("demo", true)
                          .putExtra("run_id", run));
      JSONObject last = null;
      for (int i = 0; i < 50; i++) {
        SystemClock.sleep(400);
        File f = new File(c.getFilesDir(), "v2-diagnostics.json");
        if (!f.exists())
          continue;
        try (FileInputStream in = new FileInputStream(f)) {
          ByteArrayOutputStream bytes = new ByteArrayOutputStream();
          byte[] b = new byte[4096];
          int n;
          while ((n = in.read(b)) > 0) bytes.write(b, 0, n);
          JSONObject d = new JSONObject(
              new String(bytes.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
          if (!run.equals(d.optString("run_id")))
            continue;
          last = d;
          if (!d.optString("native_error").isEmpty())
            throw new AssertionError(d.getString("native_error"));
          if (d.optLong("rendered_frames") >= 60 && d.optLong("video_frames") > 0
              && completePng(new File(c.getFilesDir(), "v2-eye.png"))) {
            code = Activity.RESULT_OK;
            break;
          }
        }
      }
      result.putString("stream",
          (code == Activity.RESULT_OK
                  ? "PASS: real OpenXR stereo rendering + demo video/points, no robot link. "
                  : "INCOMPLETE: waiting for active headset session. ")
              + (last == null ? "No diagnostics" : last.toString()));
    } catch (Throwable e) {
      result.putString("stream", "FAIL: " + e);
    }
    finish(code, result);
  }

  private static boolean completePng(File file) {
    try (RandomAccessFile in = new RandomAccessFile(file, "r")) {
      if (in.length() < 12) return false;
      in.seek(in.length() - 12);
      return in.readInt() == 0 && in.readInt() == 0x49454e44
          && in.readInt() == 0xae426082;
    } catch (IOException e) {
      return false;
    }
  }
}
