package com.tanluzhe.controlterminal.vr.v2;

import java.nio.*;
import java.security.*;
import java.util.*;

/** Bounded, independently decodable scene chunks. Partial map replacements never become visible. */
public final class SceneStore {
  public interface Repair {
    void request(Packet descriptor);
  }
  public static final class Cloud {
    public final float[] vertices;
    public final long arrival;
    Cloud(float[] p, long t) {
      vertices = p;
      arrival = t;
    }
  }
  private static final class Assembly {
    Packet p;
    long arrival;
    int count, bytes;
    byte[][] parts;
  }
  private final LinkedHashMap<String, float[]> tiles = new LinkedHashMap<>(16, .75f, true);
  private final Map<String, Long> versions = new HashMap<>();
  private final Map<String, Assembly> pending = new HashMap<>();
  private final Map<Integer, Map<Integer, Cloud>> live = new HashMap<>();
  private final Map<Integer, Long> liveFrame = new HashMap<>();
  private final Map<Integer, float[]> transforms = new HashMap<>();
  private long mapEpoch;
  private boolean epochKnown;
  private int pendingBytes;
  public long rejected, repairs;
  public volatile boolean dirty;
  public Repair repair = p -> {};
  public synchronized void clear() {
    tiles.clear();
    versions.clear();
    pending.clear();
    live.clear();
    liveFrame.clear();
    transforms.clear();
    pendingBytes = 0;
    epochKnown = false;
    dirty = true;
  }
  public synchronized void selectEpoch(long epoch) {
    if (!epochKnown || mapEpoch != epoch) {
      tiles.clear();
      versions.clear();
      pending.clear();
      pendingBytes = 0;
      mapEpoch = epoch;
      epochKnown = true;
      dirty = true;
    }
  }
  public synchronized boolean needs(Packet descriptor) {
    String key = tileKey(descriptor.body);
    return !versions.containsKey(key)
        || Long.compareUnsigned(Cbor.number(descriptor.body, 22, 0), versions.get(key)) > 0;
  }
  /** Matrix column-major, source frame into map FLU. */
  public synchronized void transform(int frame, float[] matrix) {
    if (matrix.length != 16)
      throw new IllegalArgumentException("Transform length");
    for (float f : matrix)
      if (!Float.isFinite(f))
        throw new IllegalArgumentException("Transform finite");
    if (Math.abs(matrix[3]) + Math.abs(matrix[7]) + Math.abs(matrix[11]) + Math.abs(matrix[15] - 1)
        > 1e-4)
      throw new IllegalArgumentException("Transform affine");
    transforms.put(frame, matrix.clone());
  }
  public synchronized void accept(Packet p, long arrivalNs) {
    try {
      Map<Long, Object> b = p.body;
      int format = (int) Cbor.number(b, 7, 0), compression = (int) Cbor.number(b, 10, 0),
          n = (int) Cbor.number(b, 6, -1);
      int stride = format == 1 ? 10 : format == 2 || format == 3 ? 16 : format == 4 ? 22 : 0;
      byte[] data = (byte[]) b.get(12L);
      if (stride == 0 || compression != 0 || n < 0 || n > 65536 || data == null
          || data.length != n * stride || data.length != Cbor.number(b, 11, -1))
        throw new IllegalArgumentException("Point format/size");
      if (p.type == Packet.CLOUD) {
        long frame = Cbor.number(b, 1, -1);
        int chunk = (int) Cbor.number(b, 4, -1), count = (int) Cbor.number(b, 5, 0);
        if (frame < 0 || chunk < 0 || chunk >= count || count > 65535)
          throw new IllegalArgumentException("Cloud index");
        long previous = liveFrame.getOrDefault(p.stream, -1L);
        if (frame < previous)
          return;
        if (frame > previous) {
          live.put(p.stream, new HashMap<>());
          liveFrame.put(p.stream, frame);
        }
        Map<Integer, Cloud> chunks = live.get(p.stream);
        if (chunks.size() >= 512 && !chunks.containsKey(chunk))
          return;
        chunks.put(chunk, new Cloud(decode(b, data), arrivalNs));
        dirty = true;
        return;
      }
      long epoch = Cbor.number(b, 20, 0), version = Cbor.number(b, 22, 0);
      if (!epochKnown || mapEpoch != epoch)
        return;
      String key = tileKey(b);
      if (versions.containsKey(key) && Long.compareUnsigned(version, versions.get(key)) <= 0)
        return;
      if (Cbor.number(b, 26, 0) == 1) {
        tiles.remove(key);
        versions.put(key, version);
        dirty = true;
        return;
      }
      int count = (int) Cbor.number(b, 5, 0), index = (int) Cbor.number(b, 4, -1),
          size = (int) Cbor.number(b, 24, 0);
      if (count < 1 || count > 1024 || index < 0 || index >= count || size < 0 || size > 262144)
        throw new IllegalArgumentException("Tile bounds");
      String object = key + "/" + version;
      Assembly a = pending.get(object);
      if (a == null) {
        if (pending.size() >= 32 || pendingBytes + size > 4 * 1024 * 1024) {
          repairs++;
          repair.request(p);
          return;
        }
        a = new Assembly();
        a.p = p;
        a.arrival = arrivalNs;
        a.parts = new byte[count][];
        pending.put(object, a);
      }
      if (a.parts.length != count || !Arrays.equals(descriptor(a.p.body), descriptor(b)))
        throw new IllegalArgumentException("Tile descriptor changed");
      if (a.parts[index] == null) {
        if (pendingBytes + data.length > 4 * 1024 * 1024)
          throw new IllegalArgumentException("Pending memory limit");
        a.parts[index] = data;
        a.count++;
        a.bytes += data.length;
        pendingBytes += data.length;
      }
      if (a.bytes > size)
        throw new IllegalArgumentException("Tile overflow");
      if (a.count == count) {
        byte[] all = new byte[a.bytes];
        int offset = 0;
        for (byte[] part : a.parts) {
          System.arraycopy(part, 0, all, offset, part.length);
          offset += part.length;
        }
        pending.remove(object);
        pendingBytes -= a.bytes;
        publish(a.p, all);
      }
    } catch (RuntimeException e) {
      rejected++;
    }
  }
  private byte[] descriptor(Map<Long, Object> b) {
    Map<Long, Object> d = new LinkedHashMap<>();
    for (long k : new long[] {2, 3, 7, 8, 9, 10, 20, 21, 22, 23, 24, 25, 26}) d.put(k, b.get(k));
    return Cbor.encode(d);
  }
  public synchronized void publish(Packet p, byte[] object) {
    try {
      Map<Long, Object> b = p.body;
      if (object.length != Cbor.number(b, 24, -1) || object.length > 262144
          || !MessageDigest.isEqual(
              MessageDigest.getInstance("SHA-256").digest(object), (byte[]) b.get(25L)))
        throw new IllegalArgumentException("Tile hash");
      long epoch = Cbor.number(b, 20, 0);
      if (!epochKnown || epoch != mapEpoch)
        return;
      String key = tileKey(b);
      long v = Cbor.number(b, 22, 0);
      if (versions.containsKey(key) && Long.compareUnsigned(v, versions.get(key)) <= 0)
        return;
      tiles.put(key, decode(b, object));
      versions.put(key, v);
      while (tiles.size() > 64) {
        String oldest = tiles.keySet().iterator().next();
        tiles.remove(oldest);
        versions.remove(oldest);
      }
      dirty = true;
    } catch (Exception e) {
      rejected++;
      repairs++;
      repair.request(p);
    }
  }
  public synchronized float[] matrix(int frame) {
    float[] m = transforms.get(frame);
    if (m == null)
      throw new IllegalArgumentException("Unknown reference frame");
    return m.clone();
  }
  private String tileKey(Map<Long, Object> b) {
    List<?> xyz = (List<?>) b.get(21L);
    if (xyz == null || xyz.size() != 3)
      throw new IllegalArgumentException("Tile key");
    return xyz.get(0) + "," + xyz.get(1) + "," + xyz.get(2) + "/" + Cbor.number(b, 23, -1);
  }
  public synchronized void expire(long now) {
    Iterator<Map.Entry<String, Assembly>> it = pending.entrySet().iterator();
    while (it.hasNext()) {
      Assembly a = it.next().getValue();
      if (now - a.arrival > 500_000_000L) {
        it.remove();
        pendingBytes -= a.bytes;
        repairs++;
        repair.request(a.p);
      }
    }
    for (Map<Integer, Cloud> chunks : live.values())
      if (chunks.values().removeIf(c -> now - c.arrival > 150_000_000L))
        dirty = true;
  }
  /** Interleaved map+live xyzRGBA in OpenXR local coordinates. Hard cap protects VR GPU/memory. */
  public synchronized float[] vertices() {
    int count = 0;
    for (float[] p : tiles.values()) count += p.length / 7;
    for (Map<Integer, Cloud> m : live.values())
      for (Cloud c : m.values()) count += c.vertices.length / 7;
    float[] out = new float[Math.min(count, 60000) * 7];
    int at = 0;
    for (Map<Integer, Cloud> m : live.values())
      for (Cloud c : m.values()) {
        int n = Math.min(c.vertices.length, out.length - at);
        System.arraycopy(c.vertices, 0, out, at, n);
        at += n;
      }
    for (float[] p : tiles.values()) {
      int n = Math.min(p.length, out.length - at);
      System.arraycopy(p, 0, out, at, n);
      at += n;
    }
    dirty = false;
    return out;
  }
  private float[] decode(Map<Long, Object> descriptor, byte[] bytes) {
    int f = (int) Cbor.number(descriptor, 7, 0), stride = f == 1 ? 10 : f == 4 ? 22 : 16;
    if (bytes.length % stride != 0)
      throw new IllegalArgumentException("Point alignment");
    int frame = (int) Cbor.number(descriptor, 2, -1);
    float[] t = transforms.get(frame);
    if (t == null)
      throw new IllegalArgumentException("Unknown point reference frame");
    float[] origin = Cbor.floats(descriptor.get(8L), 3);
    Object scaleValue = descriptor.get(9L);
    float scale = scaleValue instanceof Number ? ((Number) scaleValue).floatValue() : 0;
    if (!Float.isFinite(scale) || scale <= 0)
      throw new IllegalArgumentException("Point scale");
    ByteBuffer b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    float[] out = new float[bytes.length / stride * 7];
    int o = 0;
    while (b.hasRemaining()) {
      float x, y, z;
      int r, g, blue, a;
      if (f == 3) {
        int flags = b.getInt(), rgba = b.getInt();
        long morton = b.getLong();
        if ((morton & Long.MIN_VALUE) != 0)
          continue;
        int qx = 0, qy = 0, qz = 0;
        for (int bit = 0; bit < 21; bit++) {
          qx |= ((morton >>> (bit * 3)) & 1L) << bit;
          qy |= ((morton >>> (bit * 3 + 1)) & 1L) << bit;
          qz |= ((morton >>> (bit * 3 + 2)) & 1L) << bit;
        }
        x = (qx - 1048576) * .01f;
        y = (qy - 1048576) * .01f;
        z = (qz - 1048576) * .01f;
        r = (rgba >>> 24) & 255;
        g = (rgba >>> 16) & 255;
        blue = (rgba >>> 8) & 255;
        a = rgba & 255;
      } else {
        if (f == 2) {
          x = b.getFloat();
          y = b.getFloat();
          z = b.getFloat();
        } else {
          x = origin[0] + b.getShort() * scale;
          y = origin[1] + b.getShort() * scale;
          z = origin[2] + b.getShort() * scale;
        }
        r = b.get() & 255;
        g = b.get() & 255;
        blue = b.get() & 255;
        a = b.get() & 255;
        if (f == 4) {
          b.position(b.position() + 6);
          int flags = b.getShort() & 65535;
          b.getInt();
          if ((flags & 2) != 0)
            continue;
        }
      }
      if (!Float.isFinite(x) || !Float.isFinite(y) || !Float.isFinite(z))
        throw new IllegalArgumentException("Invalid point");
      float wx = t[0] * x + t[4] * y + t[8] * z + t[12],
            wy = t[1] * x + t[5] * y + t[9] * z + t[13],
            wz = t[2] * x + t[6] * y + t[10] * z + t[14];
      out[o++] = -wy;
      out[o++] = wz;
      out[o++] = -wx;
      out[o++] = r / 255f;
      out[o++] = g / 255f;
      out[o++] = blue / 255f;
      out[o++] = a / 255f;
    }
    return o == out.length ? out : Arrays.copyOf(out, o);
  }
}
