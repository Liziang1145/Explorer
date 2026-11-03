package com.tanluzhe.controlterminal.vr;
import android.content.Context;
import android.os.Process;
import android.util.Log;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;
import org.json.JSONObject;
/** Bounded per-process JSONL logs. XR/network callbacks enqueue, never wait for disk. */
public final class AppLog {
  private static volatile File directory;
  private static String source = "ui";
  private static final ExecutorService writer =
      new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS, new ArrayBlockingQueue<>(256), r -> {
        Thread t = new Thread(r, "tlz-log");
        t.setDaemon(true);
        return t;
      }, new ThreadPoolExecutor.DiscardOldestPolicy());
  public static void init(Context c, String name) {
    directory = new File(c.getFilesDir(), "logs");
    directory.mkdirs();
    source = name;
  }
  public static String safe(String value) {
    if (value == null)
      return "";
    return value.replaceAll("(?i)Bearer\\s+[^\\s,;]+", "Bearer [redacted]")
        .replaceAll("(?i)(token|secret|password|密钥|令牌)[\\s\"':=]+[^\\s,;}]+", "$1=[redacted]");
  }
  public static void event(String level, String component, String code, String message) {
    String clean = safe(message), tag = "TLZ." + component;
    if (level.equals("ERROR"))
      Log.e(tag, code + " " + clean);
    else if (level.equals("WARN"))
      Log.w(tag, code + " " + clean);
    else
      Log.i(tag, code + " " + clean);
    File dir = directory;
    if (dir == null)
      return;
    long time = System.currentTimeMillis(), mono = System.nanoTime();
    String origin = source;
    writer.execute(() -> {
      try {
        File file = new File(dir, origin + ".jsonl");
        if (file.length() > 262144) {
          new File(dir, origin + ".jsonl.2").delete();
          new File(dir, origin + ".jsonl.1").renameTo(new File(dir, origin + ".jsonl.2"));
          file.renameTo(new File(dir, origin + ".jsonl.1"));
        }
        JSONObject row = new JSONObject()
                             .put("time_ms", time)
                             .put("mono_ns", Long.toString(mono))
                             .put("pid", Process.myPid())
                             .put("source", origin)
                             .put("level", level)
                             .put("component", component)
                             .put("code", code)
                             .put("message", clean);
        try (FileOutputStream out = new FileOutputStream(file, true)) {
          out.write((row.toString() + "\n").getBytes(StandardCharsets.UTF_8));
        }
      } catch (Exception ignored) {
      }
    });
  }
  public static void info(String component, String code, String message) {
    event("INFO", component, code, message);
  }
  public static void warn(String component, String code, String message) {
    event("WARN", component, code, message);
  }
  public static void error(String component, String code, String message) {
    event("ERROR", component, code, message);
  }
  public static String reason(Throwable t) {
    return safe(t.getClass().getSimpleName() + ": " + t.getMessage());
  }
  public static String recent(Context c, int count, boolean errorsOnly) {
    ArrayList<JSONObject> rows = new ArrayList<>();
    File dir = new File(c.getFilesDir(), "logs");
    File[] files = dir.listFiles();
    if (files != null)
      for (File file : files)
        if (file.isFile() && file.getName().matches("(ui|vr)\\.jsonl(\\.[12])?")) {
          try (BufferedReader in = new BufferedReader(
                   new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = in.readLine()) != null) try {
                JSONObject row = new JSONObject(line);
                if (!errorsOnly || !row.optString("level").equals("INFO"))
                  rows.add(row);
              } catch (Exception ignored) {
              }
          } catch (IOException ignored) {
          }
        }
    rows.sort(Comparator.comparingLong(o -> o.optLong("time_ms")));
    StringBuilder text = new StringBuilder();
    SimpleDateFormat time = new SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT);
    for (int i = Math.max(0, rows.size() - count); i < rows.size(); i++) {
      JSONObject r = rows.get(i);
      text.append(time.format(new Date(r.optLong("time_ms"))))
          .append(' ')
          .append(r.optString("level"))
          .append(' ')
          .append(r.optString("component"))
          .append('/')
          .append(r.optString("code"))
          .append("  ")
          .append(r.optString("message"))
          .append('\n');
    }
    return text.length() == 0 ? "暂无符合筛选条件的日志" : text.toString();
  }
}
