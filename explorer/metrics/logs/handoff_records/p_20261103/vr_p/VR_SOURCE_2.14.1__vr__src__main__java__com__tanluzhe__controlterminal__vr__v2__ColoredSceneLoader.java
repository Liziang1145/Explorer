package com.tanluzhe.controlterminal.vr.v2;

import android.content.Context;
import com.tanluzhe.controlterminal.vr.AppLog;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Static apex-quest-scene/1 adapter. Never opens a robot control session. */
public final class ColoredSceneLoader implements AutoCloseable {
  private final Context context;
  private final ExecutorService worker = Executors.newSingleThreadExecutor();
  private volatile boolean closed, busy;
  public volatile String status = "等待加载", error = "", source = "";
  private interface Files {
    InputStream open(String name) throws Exception;
  }
  public ColoredSceneLoader(Context c) {
    context = c;
  }
  public boolean busy() {
    return busy;
  }
  public synchronized void load(boolean remote) {
    if (closed || busy)
      return;
    busy  = true;
    error = "";
    worker.execute(() -> {
      try {
        Files files;
        String selectedSource;
        if (remote) {
          String value = context.getSharedPreferences("v2", 0).getString("colored_scene_url", "").trim();
          if (value.isEmpty())
            throw new IllegalStateException("请在设置填写 AIPC 场景 manifest.json 地址；当前交付未提供实时场景接口");
          URI uri = new URI(value);
          if (!"http".equals(uri.getScheme()) || uri.getHost() == null || uri.getRawUserInfo() != null || uri.getQuery() != null
              || uri.getFragment() != null || !uri.getPath().endsWith("/manifest.json"))
            throw new IllegalArgumentException("场景地址须为 http://主机:端口/.../assets/manifest.json，不含账号或查询参数");
          final URI base     = uri.resolve(".");
          final String token = new com.tanluzhe.controlterminal.vr.ConnectionSettings(context).token;
          files              = name -> {
            if (closed)
              throw new InterruptedIOException();
            URL url                      = base.resolve(name).toURL();
            HttpURLConnection connection = (HttpURLConnection) url.openConnection(Proxy.NO_PROXY);
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(3000);
            connection.setReadTimeout(10000);
            connection.setRequestProperty("Authorization", "Bearer " + token);
            int code = connection.getResponseCode();
            if (code != 200) {
              connection.disconnect();
              throw new IOException("AIPC 场景 HTTP " + code + "；此通道需要可直接读取的静态资源，工作台登录地址不能直接替代");
            }
            return new FilterInputStream(connection.getInputStream()) {
              @Override
              public void close() throws IOException {
                try {
                  super.close();
                } finally {
                  connection.disconnect();
                }
              }
            };
          };
          selectedSource = "AIPC HTTP 资源";
        } else {
          files          = name -> context.getAssets().open("colored_scene/" + (name.equals("../SHA256SUMS.txt") ? "SHA256SUMS.txt" : name));
          selectedSource = "内置实验室扫描";
        }
        status                     = "读取场景清单与校验信息";
        Map<String, String> hashes = new HashMap<>();
        for (String line : text(files, "../SHA256SUMS.txt", 65536).split("\n")) {
          String[] pair = line.trim().split("\\s+", 2);
          if (pair.length == 2 && pair[0].matches("[0-9a-fA-F]{64}"))
            hashes.put(pair[1], pair[0].toLowerCase(Locale.ROOT));
        }
        String manifestText = text(files, "manifest.json", 65536);
        String manifestHash = hashes.get("assets/manifest.json");
        if (manifestHash == null || !manifestHash.equals(hex(MessageDigest.getInstance("SHA-256").digest(manifestText.getBytes("UTF-8")))))
          throw new IOException("场景清单 SHA-256 不匹配");
        JSONObject manifest = new JSONObject(manifestText);
        if (!manifest.getString("schema").equals("apex-quest-scene/1") || !manifest.getString("units").equals("metre"))
          throw new IllegalArgumentException("不支持的场景 schema / 单位");
        int n = manifest.getInt("vertices"), faces = manifest.getInt("triangles");
        if (n <= 0 || n > 1000000 || faces <= 0 || faces > 2000000)
          throw new IllegalArgumentException("场景数量超过本轮容量限制");
        ByteBuffer positions = buffer(files, "positions.bin", n * 12, hashes);
        ByteBuffer colors    = buffer(files, "colors.bin", n * 3, hashes);
        ByteBuffer indices   = buffer(files, "indices.bin", faces * 12, hashes);
        if (closed)
          return;
        status        = "后台分块 / 线性颜色转换";
        String reason = NativeVr.coloredSceneLoad(positions, colors, indices, n, faces);
        if (reason != null)
          throw new IllegalStateException(reason);
        source = selectedSource;
        status = "GPU 分帧上传中";
        AppLog.info("SCENE", "ASSET_STAGED",
            "source=" + source + " vertices=" + n + " triangles=" + faces + " bins already display Y-up; no second transform");
      } catch (Exception e) {
        error  = AppLog.reason(e);
        status = "场景加载失败，保留已有画面";
        AppLog.warn("SCENE", "LOAD_FAILED", error);
      } finally {
        busy = false;
      }
    });
  }
  private String text(Files f, String name, int max) throws Exception {
    try (InputStream in = f.open(name); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
      byte[] bytes = new byte[8192];
      int n;
      while ((n = in.read(bytes)) != -1) {
        if (closed)
          throw new InterruptedIOException();
        if (out.size() + n > max)
          throw new IOException("Scene metadata too large");
        out.write(bytes, 0, n);
      }
      return new String(out.toByteArray(), "UTF-8");
    }
  }
  private ByteBuffer buffer(Files files, String name, int size, Map<String, String> hashes) throws Exception {
    String expected = hashes.get("assets/" + name);
    if (expected == null)
      throw new IOException("缺少文件校验值：" + name);
    status               = "读取 / 校验 " + name;
    ByteBuffer result    = ByteBuffer.allocateDirect(size).order(ByteOrder.LITTLE_ENDIAN);
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    try (InputStream in = files.open(name)) {
      byte[] scratch = new byte[65536];
      int n;
      while ((n = in.read(scratch)) != -1) {
        if (closed)
          throw new InterruptedIOException();
        if (n > result.remaining())
          throw new IOException("场景文件超长：" + name);
        digest.update(scratch, 0, n);
        result.put(scratch, 0, n);
      }
    }
    if (result.position() != size || !expected.equals(hex(digest.digest())))
      throw new IOException("场景文件长度 / SHA-256 错误：" + name);
    result.flip();
    return result;
  }
  private static String hex(byte[] b) {
    StringBuilder s = new StringBuilder();
    for (byte v : b) s.append(String.format(Locale.ROOT, "%02x", v & 255));
    return s.toString();
  }
  @Override
  public void close() {
    closed = true;
    worker.shutdownNow();
  }
}
