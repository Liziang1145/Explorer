package com.tanluzhe.controlterminal.vr.v2;

import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.os.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.JSONObject;

/** Interactive Quest check; all controls use virtual data and never open BaseLink. */
public final class VrInteractionInstrumentation extends Instrumentation {
  private boolean layoutOnly;
  @Override
  public void onCreate(Bundle args) {
    super.onCreate(args);
    layoutOnly = args != null && "true".equals(args.getString("layoutOnly"));
    start();
  }
  @Override
  public void onStart() {
    Bundle result = new Bundle();
    int code = Activity.RESULT_CANCELED;
    Context context = getTargetContext();
    String run = UUID.randomUUID().toString();
    try {
      // These files are flat layout previews from the production HUD renderer, not XR screenshots.
      Dashboard d = new Dashboard();
      d.simulation = true;
      d.connection = "虚拟基站";
      VrUiState s = new VrUiState();
      Bitmap b = Bitmap.createBitmap(1600, 1000, Bitmap.Config.ARGB_8888);
      for (int mode = 0; mode < 4; mode++) {
        s.videoMode = mode % 3;
        s.menuOpen = mode == 3;
        new VrHud().draw(b, d, s, System.nanoTime(), false);
        try (FileOutputStream out =
                 context.openFileOutput("v2-layout-" + mode + ".png", Context.MODE_PRIVATE)) {
          b.compress(Bitmap.CompressFormat.PNG, 100, out);
        }
      }
      b.recycle();
      if (layoutOnly) {
        result.putString("stream",
            "PASS: production HUD layout rendered in four modes; flat previews, not XR "
            + "screenshots.");
        finish(Activity.RESULT_OK, result);
        return;
      }
      context.deleteFile("v2-eye.png");
      context.startActivity(
          new Intent(context, V2Activity.class)
              .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
              .putExtra("demo", true)
              .putExtra("run_id", run));
      JSONObject last = null;
      for (int i = 0; i < 300; i++) {
        SystemClock.sleep(400);
        try (FileInputStream in = context.openFileInput("v2-diagnostics.json")) {
          ByteArrayOutputStream out = new ByteArrayOutputStream();
          byte[] bytes = new byte[4096];
          int n;
          while ((n = in.read(bytes)) > 0) out.write(bytes, 0, n);
          JSONObject value = new JSONObject(out.toString("UTF-8"));
          if (!run.equals(value.optString("run_id")))
            continue;
          last = value;
          if (!value.optString("native_error").isEmpty())
            throw new AssertionError(value.optString("native_error"));
          if (value.optBoolean("exit_requested")) {
            boolean passed = value.optLong("rendered_frames") >= 60
                && value.optLong("input_events") > 0 && value.optInt("seen_video_modes") == 7
                && value.optLong("ui_clicks") > 0 && value.optBoolean("menu_opened")
                && value.optLong("haptic_pulses") > 0;
            if (passed)
              code = Activity.RESULT_OK;
            break;
          }
        } catch (FileNotFoundException ignored) {
        }
      }
      result.putString("stream",
          (code == Activity.RESULT_OK ? "PASS" : "INCOMPLETE") + ": interactive virtual VR; "
              + (last == null ? "No diagnostics" : last.toString()));
    } catch (Throwable e) {
      result.putString("stream", "FAIL: " + e);
    }
    finish(code, result);
  }
}
