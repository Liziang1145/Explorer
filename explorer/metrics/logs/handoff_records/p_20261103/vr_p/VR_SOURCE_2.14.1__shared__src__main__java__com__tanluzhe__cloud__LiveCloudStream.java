package com.tanluzhe.cloud;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.zip.*;
import org.json.*;
/** 5 Hz replace-all VCL1 snapshots. No disk cache, robot commands or static fallback. */
public final class LiveCloudStream implements AutoCloseable {
  public interface Sink {
    void reset(long generation);
    boolean offer(long generation, ByteBuffer rgba, float[] mapToDisplay);
    void visible(boolean visible);
  }
  public static final class Frame {
    public final JSONObject meta;
    public final ByteBuffer points;
    Frame(JSONObject m, ByteBuffer p) {
      meta   = m;
      points = p;
    }
  }
  private static final AtomicLong GENERATIONS = new AtomicLong();
  private final String base, token;
  private final Sink sink;
  private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
  private volatile HttpURLConnection connection;
  private volatile boolean closed, paused, fatal;
  private String etag = "", epoch = "";
  private long version = -1, generation = GENERATIONS.incrementAndGet(), retryAt;
  public volatile String state = "实时点云待连接", error = "", sourceEpoch = "";
  public volatile long points, frames, bytes, lastFrameNs;
  public volatile double sourceAge;
  public volatile boolean available;
  public LiveCloudStream(String base, String token, Sink sink) {
    new CloudStream.Config(base, token, CloudStream.DENSE, "wifi");
    this.base  = base.endsWith("/") ? base : base + "/";
    this.token = token;
    this.sink  = sink;
  }
  public void start() {
    if (!closed)
      worker.scheduleWithFixedDelay(this::tick, 0, 200, TimeUnit.MILLISECONDS);
  }
  public void pause(boolean p) {
    paused = p;
    if (p)
      sink.visible(false);
  }
  private void unavailable(String message) {
    available = false;
    state     = "实时点云不可用";
    error     = message;
    sink.visible(false);
  }
  private void tick() {
    if (closed || paused || fatal)
      return;
    long now = System.nanoTime();
    if (now < retryAt)
      return;
    HttpURLConnection c = null;
    try {
      c          = (HttpURLConnection) new URL(base + "v2/cloud/live/frame").openConnection(Proxy.NO_PROXY);
      connection = c;
      c.setConnectTimeout(4000);
      c.setReadTimeout(5000);
      c.setInstanceFollowRedirects(false);
      c.setRequestProperty("Authorization", "Bearer " + token);
      c.setRequestProperty("Accept-Encoding", "identity");
      if (!etag.isEmpty())
        c.setRequestProperty("If-None-Match", etag);
      int code = c.getResponseCode();
      if (code == 304) {
        if (lastFrameNs == 0 || now - lastFrameNs > 2_000_000_000L)
          unavailable("实时快照已陈旧，等待新版本");
        else {
          available = true;
          sink.visible(true);
        }
        return;
      }
      if (code != 200) {
        if (code == 401 || code == 400 || code == 403)
          fatal = true;
        long delay = 1000;
        try {
          delay = Math.max(1000, Math.min(30000, Long.parseLong(c.getHeaderField("Retry-After")) * 1000));
        } catch (Exception ignored) {
        }
        retryAt = now + delay * 1_000_000;
        throw new IOException("实时服务 HTTP " + code);
      }
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      try (InputStream in = c.getInputStream()) {
        byte[] b = new byte[32768];
        int n;
        while ((n = in.read(b)) != -1) {
          if (out.size() + n > 2065552)
            throw new IOException("VCL1响应过大");
          out.write(b, 0, n);
        }
      }
      byte[] packet = out.toByteArray();
      Frame frame   = decode(packet);
      JSONObject m  = frame.meta;
      if (!Arrays.asList("metre", "meter", "m").contains(m.getString("units")))
        throw new IOException("实时单位不是米");
      double age = m.getDouble("source_age_s");
      if (!Double.isFinite(age) || age < 0 || age >= 2)
        throw new IOException("实时源陈旧");
      if (!"replace_all_not_append".equals(m.getString("snapshot_semantics")) || m.optBoolean("persistent_cache", true)
          || !m.getBoolean("same_source_as_web_home"))
        throw new IOException("实时快照语义不符");
      String nextEpoch = m.getString("source_epoch");
      if (nextEpoch.isEmpty() || nextEpoch.length() > 160)
        throw new IOException("epoch无效");
      long nextVersion = m.getLong("cloud_version");
      if (nextVersion < 0)
        throw new IOException("version无效");
      if (!nextEpoch.equals(epoch)) {
        epoch      = nextEpoch;
        version    = -1;
        generation = GENERATIONS.incrementAndGet();
        sink.reset(generation);
      }
      etag = c.getHeaderField("ETag") == null ? "" : c.getHeaderField("ETag");
      if (nextVersion <= version){if(lastFrameNs==0||now-lastFrameNs>2_000_000_000L)unavailable("实时快照已陈旧，等待新版本");return;}
      float[] matrix = displayMatrix(m.getJSONArray("map_to_vehicle"));
      if (closed || paused)
        return;
      if (sink.offer(generation, frame.points, matrix)) {
        version     = nextVersion;
        sourceEpoch = nextEpoch;
        sourceAge   = age;
        points      = m.getInt("points");
        frames++;
        bytes += packet.length;
        lastFrameNs = System.nanoTime();
        available   = true;
        state       = "实时融合点云";
        error       = "";
        sink.visible(true);
      }
    } catch (Exception e) {
      if(retryAt<now)retryAt=now+1_000_000_000L;
      if (!closed)
        unavailable(e instanceof IOException ? e.getMessage() : "实时点云协议校验失败");
    } finally {
      connection = null;
      if (c != null)
        c.disconnect();
    }
  }
  public static Frame decode(byte[] packet) throws Exception {
    if (packet.length < 16)
      throw new IOException("VCL1头截断");
    ByteBuffer header = ByteBuffer.wrap(packet).order(ByteOrder.LITTLE_ENDIAN);
    if (header.getInt() != 0x314c4356)
      throw new IOException("VCL1 magic无效");
    long j = Integer.toUnsignedLong(header.getInt()), p = Integer.toUnsignedLong(header.getInt()), r = Integer.toUnsignedLong(header.getInt());
    if (j == 0 || j > 65536 || p > 2000000 || r > 1920000 || 16 + j + p != packet.length)
      throw new IOException("VCL1长度无效");
    JSONObject meta   = new JSONObject(new String(packet, 16, (int) j, "UTF-8"));
    JSONObject format = meta.getJSONObject("point_format");
    int count         = meta.getInt("points");
    if (!"apex-vr-live-cloud/1".equals(meta.getString("schema")) || !"camera_init".equals(meta.getString("coordinate_frame"))
        || format.getInt("stride") != 16 || !"little".equals(format.optString("endianness", "little")) || count < 0 || (long) count * 16 != r
        || meta.getLong("raw_bytes") != r || meta.getLong("packed_bytes") != p)
      throw new IOException("实时16字节点布局不符");
    ByteBuffer raw                     = ByteBuffer.allocateDirect((int) r).order(ByteOrder.LITTLE_ENDIAN);
    java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
    try (InputStream in = new GZIPInputStream(new ByteArrayInputStream(packet, 16 + (int) j, (int) p))) {
      byte[] b = new byte[32768];
      int n;
      while ((n = in.read(b)) != -1) {
        if (n > raw.remaining())
          throw new IOException("实时解压超限");
        digest.update(b, 0, n);
        raw.put(b, 0, n);
      }
    }
    StringBuilder hash = new StringBuilder();
    for (byte b : digest.digest()) hash.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
    if (raw.position() != r || !hash.toString().equals(meta.getString("raw_sha256")))
      throw new IOException("实时原始SHA/长度无效");
    raw.flip();
    for (int i = 0; i < count; i++)
      for (int k = 0; k < 3; k++)
        if (!Float.isFinite(raw.getFloat(i * 16 + k * 4)) || Math.abs(raw.getFloat(i * 16 + k * 4)) > 1000000)
          throw new IOException("实时坐标无效");
    return new Frame(meta, raw);
  }
  public static float[] displayMatrix(JSONArray rows) throws Exception {
    if (rows.length() != 4)
      throw new IOException("车体矩阵形状");
    float[][] m = new float[4][4];
    for (int i = 0; i < 4; i++) {
      if (rows.getJSONArray(i).length() != 4)
        throw new IOException("车体矩阵形状");
      for (int j = 0; j < 4; j++) {
        m[i][j] = (float) rows.getJSONArray(i).getDouble(j);
        if (!Float.isFinite(m[i][j]) || Math.abs(m[i][j]) > 1000000)
          throw new IOException("矩阵非有限");
      }
    }
    for (int k = 0; k < 4; k++)
      if (Math.abs(m[3][k] - (k == 3 ? 1 : 0)) > 1e-5)
        throw new IOException("车体矩阵非仿射");
    for (int a = 0; a < 3; a++)
      for (int b = 0; b < 3; b++) {
        float dot = 0;
        for (int k = 0; k < 3; k++) dot += m[a][k] * m[b][k];
        if (Math.abs(dot - (a == b ? 1 : 0)) > .005)
          throw new IOException("车体矩阵非刚体");
      }
    double determinant = m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
    if (Math.abs(determinant - 1) > .01)
      throw new IOException("车体矩阵包含反射");
    float[] out = new float[16];
    for (int c = 0; c < 4; c++) {
      out[c * 4]     = m[0][c];
      out[c * 4 + 1] = m[2][c];
      out[c * 4 + 2] = -m[1][c];
      out[c * 4 + 3] = m[3][c];
    }
    return out;
  }
  public String summary() {
    return state + " · " + points + "点 · " + frames + "帧 · " + (available ? "可用" : "未就绪") + (error.isEmpty() ? "" : " · " + error);
  }
  public void close() {
    closed              = true;
    HttpURLConnection c = connection;
    if (c != null)
      c.disconnect();
    worker.shutdownNow();
    sink.visible(false);
    sink.reset(GENERATIONS.incrementAndGet());
  }
}
