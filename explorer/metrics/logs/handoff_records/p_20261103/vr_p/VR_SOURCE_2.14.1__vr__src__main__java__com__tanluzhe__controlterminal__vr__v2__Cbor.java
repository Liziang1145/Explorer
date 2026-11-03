package com.tanluzhe.controlterminal.vr.v2;

import java.io.ByteArrayOutputStream;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Strict TLZ CBOR profile. No tags, indefinite lengths, duplicate keys or nonfinite floats. */
public final class Cbor {
  public static final class UInt extends Number {
    final long bits;
    UInt(long b) {
      bits = b;
    }
    public int intValue() {
      return (int) bits;
    }
    public long longValue() {
      return bits;
    }
    public float floatValue() {
      return (float) doubleValue();
    }
    public double doubleValue() {
      return bits >= 0 ? bits : (double) (bits & Long.MAX_VALUE) + 0x1.0p63;
    }
    @Override
    public String toString() {
      return Long.toUnsignedString(bits);
    }
  }
  public static Number u(long bits) {
    return bits < 0 ? new UInt(bits) : Long.valueOf(bits);
  }
  private Cbor() {}
  public static Map<Long, Object> map(Object... pairs) {
    Map<Long, Object> m = new LinkedHashMap<>();
    if (pairs.length % 2 != 0)
      throw new IllegalArgumentException("CBOR key/value pairs");
    for (int i = 0; i < pairs.length; i += 2) {
      long key = ((Number) pairs[i]).longValue();
      if (key < 0 || m.containsKey(key))
        throw new IllegalArgumentException("CBOR duplicate key");
      m.put(key, pairs[i + 1]);
    }
    return m;
  }
  public static byte[] encode(Object value) {
    ByteArrayOutputStream o = new ByteArrayOutputStream();
    write(o, value, 0);
    return o.toByteArray();
  }
  private static void head(ByteArrayOutputStream o, int major, long v) {
    if (v < 0)
      throw new IllegalArgumentException("CBOR unsigned overflow");
    if (v < 24)
      o.write((major << 5) | (int) v);
    else {
      int n = v <= 255 ? 1 : v <= 65535 ? 2 : v <= 0xffffffffL ? 4 : 8;
      o.write((major << 5) | (n == 1 ? 24 : n == 2 ? 25 : n == 4 ? 26 : 27));
      for (int i = n - 1; i >= 0; i--) o.write((int) (v >>> (8 * i)));
    }
  }
  private static void write(ByteArrayOutputStream o, Object v, int depth) {
    if (depth > 8)
      throw new IllegalArgumentException("CBOR nesting");
    if (v == null) {
      o.write(246);
      return;
    }
    if (v instanceof Boolean) {
      o.write((Boolean) v ? 245 : 244);
      return;
    }
    if (v instanceof Float || v instanceof Double) {
      float f = ((Number) v).floatValue();
      if (!Float.isFinite(f))
        throw new IllegalArgumentException("Nonfinite");
      o.write(250);
      int b = Float.floatToRawIntBits(f);
      for (int i = 3; i >= 0; i--) o.write(b >>> (i * 8));
      return;
    }
    if (v instanceof UInt) {
      o.write(27);
      long n = ((UInt) v).bits;
      for (int i = 7; i >= 0; i--) o.write((int) (n >>> (8 * i)));
      return;
    }
    if (v instanceof Number) {
      long n = ((Number) v).longValue();
      head(o, n < 0 ? 1 : 0, n < 0 ? -1 - n : n);
      return;
    }
    if (v instanceof byte[]) {
      byte[] a = (byte[]) v;
      head(o, 2, a.length);
      o.write(a, 0, a.length);
      return;
    }
    if (v instanceof String) {
      byte[] a = ((String) v).getBytes(StandardCharsets.UTF_8);
      head(o, 3, a.length);
      o.write(a, 0, a.length);
      return;
    }
    if (v instanceof float[]) {
      float[] a = (float[]) v;
      head(o, 4, a.length);
      for (float f : a) write(o, f, depth + 1);
      return;
    }
    if (v instanceof List) {
      List<?> a = (List<?>) v;
      head(o, 4, a.size());
      for (Object x : a) write(o, x, depth + 1);
      return;
    }
    if (v instanceof Map) {
      Map<?, ?> m = (Map<?, ?>) v;
      head(o, 5, m.size());
      long last = -1;
      List<Long> keys = new ArrayList<>();
      for (Object k : m.keySet()) {
        if (!(k instanceof Number) || ((Number) k).longValue() < 0)
          throw new IllegalArgumentException("Integer keys only");
        keys.add(((Number) k).longValue());
      }
      Collections.sort(keys);
      for (long k : keys) {
        if (k == last)
          throw new IllegalArgumentException("Duplicate key");
        last = k;
        write(o, k, depth + 1);
        write(o, m.get(k), depth + 1);
      }
      return;
    }
    throw new IllegalArgumentException("Unsupported CBOR type");
  }
  public static Object decode(byte[] data) {
    ByteBuffer b = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
    Object v = read(b, 0);
    if (b.hasRemaining())
      throw new IllegalArgumentException("Trailing CBOR");
    return v;
  }
  private static long arg(ByteBuffer b, int ai) {
    if (ai < 24)
      return ai;
    int n = ai == 24 ? 1 : ai == 25 ? 2 : ai == 26 ? 4 : ai == 27 ? 8 : 0;
    if (n == 0)
      throw new IllegalArgumentException("Indefinite CBOR");
    long x = 0;
    for (int i = 0; i < n; i++) x = (x << 8) | (b.get() & 255L);
    return x;
  }
  private static Object read(ByteBuffer b, int d) {
    if (d > 8 || !b.hasRemaining())
      throw new IllegalArgumentException("CBOR depth/length");
    int h = b.get() & 255, m = h >>> 5, ai = h & 31;
    if (m == 7) {
      if (ai == 20)
        return false;
      if (ai == 21)
        return true;
      if (ai == 22)
        return null;
      if (ai == 26) {
        float f = b.getFloat();
        if (!Float.isFinite(f))
          throw new IllegalArgumentException("Nonfinite");
        return f;
      }
      throw new IllegalArgumentException("CBOR simple/float64");
    }
    long n = arg(b, ai);
    if (m == 0)
      return u(n);
    if (m == 1) {
      if (n < 0)
        throw new IllegalArgumentException("Signed integer overflow");
      return -1 - n;
    }
    if (n < 0 || n > 65536)
      throw new IllegalArgumentException("CBOR allocation limit");
    int len = (int) n;
    if (m == 2 || m == 3) {
      if (len > b.remaining())
        throw new IllegalArgumentException("CBOR truncated");
      byte[] a = new byte[len];
      b.get(a);
      if (m == 2)
        return a;
      try {
        return StandardCharsets.UTF_8.newDecoder()
            .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
            .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
            .decode(ByteBuffer.wrap(a))
            .toString();
      } catch (java.nio.charset.CharacterCodingException e) {
        throw new IllegalArgumentException("CBOR UTF-8", e);
      }
    }
    if (m == 4) {
      if (len > b.remaining())
        throw new IllegalArgumentException("CBOR array length");
      List<Object> a = new ArrayList<>();
      for (int i = 0; i < len; i++) a.add(read(b, d + 1));
      return a;
    }
    if (m == 5) {
      if (len > b.remaining() / 2)
        throw new IllegalArgumentException("CBOR map length");
      Map<Long, Object> a = new LinkedHashMap<>();
      for (int i = 0; i < len; i++) {
        Object k = read(b, d + 1);
        if (!(k instanceof Long) || (Long) k < 0 || a.containsKey(k))
          throw new IllegalArgumentException("CBOR duplicate/key");
        a.put((Long) k, read(b, d + 1));
      }
      return a;
    }
    throw new IllegalArgumentException("CBOR tags prohibited");
  }
  @SuppressWarnings("unchecked")
  public static Map<Long, Object> object(Object v) {
    if (!(v instanceof Map))
      throw new IllegalArgumentException("Expected map");
    return (Map<Long, Object>) v;
  }
  public static long number(Map<Long, Object> m, long k, long fallback) {
    Object x = m.get(k);
    return x instanceof Number ? ((Number) x).longValue() : fallback;
  }
  public static float[] floats(Object v, int n) {
    if (v instanceof float[]) {
      float[] a = ((float[]) v).clone();
      if (a.length != n)
        throw new IllegalArgumentException("Vector size");
      for (float f : a)
        if (!Float.isFinite(f))
          throw new IllegalArgumentException("Vector nonfinite");
      return a;
    }
    if (!(v instanceof List) || ((List<?>) v).size() != n)
      throw new IllegalArgumentException("Vector size");
    float[] a = new float[n];
    for (int i = 0; i < n; i++) {
      Object x = ((List<?>) v).get(i);
      if (!(x instanceof Number))
        throw new IllegalArgumentException("Vector type");
      a[i] = ((Number) x).floatValue();
      if (!Float.isFinite(a[i]))
        throw new IllegalArgumentException("Vector nonfinite");
    }
    return a;
  }
}
