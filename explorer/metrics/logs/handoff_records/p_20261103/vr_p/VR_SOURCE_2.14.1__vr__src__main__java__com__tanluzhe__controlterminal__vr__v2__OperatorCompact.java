package com.tanluzhe.controlterminal.vr.v2;

import java.io.*;
import java.nio.*;
import java.util.*;

/** Negotiated OPC1: full snapshots, unchanged TLZ header, no inter-packet dependencies. */
public final class OperatorCompact {
  public static final String CBOR = "cbor", LOSSLESS = "opbin1", QUANTIZED = "opq1";
  public static boolean supported(String name) {
    return name.equals(CBOR) || name.equals(LOSSLESS) || name.equals(QUANTIZED);
  }
  public static Map<Long, Object> choose(Map<Long, Object> source, String profile) {
    if (profile.equals(CBOR))
      return source;
    if (!supported(profile))
      throw new IllegalArgumentException("Unsupported operator encoding");
    try {
      Map<Long, Object> compact = pack(source, profile);
      return Cbor.encode(compact).length < Cbor.encode(source).length ? compact : source;
    } catch (IllegalArgumentException e) {
      return source;
    } // Unsupported optional field/range: preserve every original value.
  }
  public static Map<Long, Object> pack(Map<Long, Object> source, String profile) {
    boolean quant = profile.equals(QUANTIZED);
    if (!quant && !profile.equals(LOSSLESS))
      throw new IllegalArgumentException("OPC1 profile");
    if (source.containsKey(12L))
      throw new IllegalArgumentException("key12 already occupied");
    int presence = 0, valid = 0;
    long frame = 0;
    List<Map<Long, Object>> poses = new ArrayList<>();
    for (int k = 3; k <= 5; k++)
      if (source.containsKey((long) k)) {
        presence |= 1 << (k - 3);
        poses.add(Cbor.object(source.get((long) k)));
      }
    if ((Cbor.number(source, 1, 0) & 7) != (presence & 7))
      throw new IllegalArgumentException("Pose tracking mask mismatch");
    Map<Long, Object> view = null, controls = null;
    if (source.containsKey(6L)) {
      presence |= 8;
      view = Cbor.object(source.get(6L));
      exact(view, 0, 1, 2, 3);
      if ((presence & 1) == 0)
        throw new IllegalArgumentException("Views without head");
      poses.add(Cbor.object(view.get(0L)));
      poses.add(Cbor.object(view.get(2L)));
    }
    if (source.containsKey(11L)) {
      presence |= 16;
      controls = Cbor.object(source.get(11L));
      if (Cbor.number(controls, 0, 0) != 1)
        throw new IllegalArgumentException("Input revision");
      valid = (int) Cbor.number(controls, 7, -1);
      if (valid < 0 || (valid & ~63) != 0)
        throw new IllegalArgumentException("Control validity");
      Set<Long> keys = new HashSet<>(Arrays.asList(0L, 7L));
      for (int i = 0; i < 6; i++)
        if ((valid & (1 << i)) != 0)
          keys.add((long) i + 1);
      if (!controls.keySet().equals(keys))
        throw new IllegalArgumentException("Unexpected control fields");
    }
    for (Map<Long, Object> pose : poses) {
      exact(pose, 0, 1, 2);
      long id = Cbor.number(pose, 0, -1);
      if (id <= 0 || id > 0xffffffffL)
        throw new IllegalArgumentException("Frame");
      if (frame == 0)
        frame = id;
      else if (frame != id)
        throw new IllegalArgumentException("Different pose frames");
    }
    try {
      ByteArrayOutputStream bytes = new ByteArrayOutputStream();
      DataOutputStream out = new DataOutputStream(bytes);
      out.writeShort(0x4f50);
      out.writeByte(1);
      out.writeByte(quant ? 1 : 0);
      out.writeByte(presence);
      out.writeByte(valid);
      out.writeShort(0);
      out.writeInt((int) frame);
      for (Map<Long, Object> pose : poses) {
        float[] xyz = Cbor.floats(pose.get(1L), 3), q = Cbor.floats(pose.get(2L), 4);
        double sourceNorm = 0;
        for (float x : q) sourceNorm += x * x;
        if (Math.abs(Math.sqrt(sourceNorm) - 1) > .001)
          throw new IllegalArgumentException("Quaternion normalization");
        if (quant) {
          for (float x : xyz)
            out.writeInt((int) rounded(x, 10000, Integer.MIN_VALUE, Integer.MAX_VALUE));
          double norm = 0;
          for (float x : q) norm += x * x;
          if (Math.abs(Math.sqrt(norm) - 1) > .001)
            throw new IllegalArgumentException("Quaternion normalization");
          for (float x : q) out.writeShort((short) rounded(x, 32767, -32767, 32767));
        } else {
          for (float x : xyz) out.writeFloat(finite(x));
          for (float x : q) out.writeFloat(finite(x));
        }
      }
      if (view != null) {
        for (float f : Cbor.floats(view.get(1L), 4)) out.writeFloat(finite(f));
        for (float f : Cbor.floats(view.get(3L), 4)) out.writeFloat(finite(f));
      }
      if (controls != null)
        for (int bit = 0; bit < 6; bit++)
          if ((valid & (1 << bit)) != 0) {
            if (bit < 4) {
              Object value = controls.get((long) bit + 1);
              if (!(value instanceof Float))
                throw new IllegalArgumentException("Raw pressure must f32");
              float v = (Float) value;
              if (v < 0 || v > 1)
                throw new IllegalArgumentException("Pressure range");
              out.writeFloat(finite(v));
            } else
              for (float v : Cbor.floats(controls.get((long) bit + 1), 2)) {
                if (Math.abs(v) > 1)
                  throw new IllegalArgumentException("Stick range");
                out.writeFloat(finite(v));
              }
          }
      Map<Long, Object> envelope = new LinkedHashMap<>(source);
      for (long key : new long[] {3, 4, 5, 6, 11}) envelope.remove(key);
      envelope.put(12L, bytes.toByteArray());
      return envelope;
    } catch (IOException e) {
      throw new IllegalStateException(e);
    }
  }
  public static Map<Long, Object> expand(Map<Long, Object> envelope) {
    if (!(envelope.get(12L) instanceof byte[]))
      throw new IllegalArgumentException("OPC1 blob");
    for (long key : new long[] {3, 4, 5, 6, 11})
      if (envelope.containsKey(key))
        throw new IllegalArgumentException("Mixed compact/original fields");
    ByteBuffer in = ByteBuffer.wrap((byte[]) envelope.get(12L)).order(ByteOrder.BIG_ENDIAN);
    if (in.remaining() < 12 || in.getShort() != 0x4f50 || in.get() != 1)
      throw new IllegalArgumentException("OPC1 version");
    int codec = in.get() & 255, mask = in.get() & 255, valid = in.get() & 255;
    if (codec > 1 || (mask & ~31) != 0 || (valid & ~63) != 0 || in.getShort() != 0
        || (mask & 16) == 0 && valid != 0 || (mask & 8) != 0 && (mask & 1) == 0)
      throw new IllegalArgumentException("OPC1 header");
    long frame = Integer.toUnsignedLong(in.getInt());
    int poseCount = Integer.bitCount(mask & 7) + ((mask & 8) != 0 ? 2 : 0);
    int controlFloats = Integer.bitCount(valid & 15) + 2 * Integer.bitCount(valid & 48);
    int length =
        12 + poseCount * (codec == 0 ? 28 : 20) + ((mask & 8) != 0 ? 32 : 0) + controlFloats * 4;
    if (in.capacity() != length || poseCount > 0 && frame == 0 || poseCount == 0 && frame != 0
        || (Cbor.number(envelope, 1, 0) & 7) != (mask & 7))
      throw new IllegalArgumentException("OPC1 exact length/frame/tracking");
    Map<Long, Object> result = new LinkedHashMap<>(envelope);
    result.remove(12L);
    for (int bit = 0; bit < 3; bit++)
      if ((mask & (1 << bit)) != 0)
        result.put((long) bit + 3, readPose(in, codec, frame));
    if ((mask & 8) != 0) {
      Map<Long, Object> left = readPose(in, codec, frame), right = readPose(in, codec, frame);
      float[] lf = new float[4], rf = new float[4];
      for (int i = 0; i < 4; i++) lf[i] = finite(in.getFloat());
      for (int i = 0; i < 4; i++) rf[i] = finite(in.getFloat());
      result.put(6L, Cbor.map(0, left, 1, lf, 2, right, 3, rf));
    }
    if ((mask & 16) != 0) {
      Map<Long, Object> controls = Cbor.map(0, 1, 7, valid);
      for (int bit = 0; bit < 6; bit++)
        if ((valid & (1 << bit)) != 0) {
          if (bit < 4) {
            float value = finite(in.getFloat());
            if (value < 0 || value > 1)
              throw new IllegalArgumentException("Pressure range");
            controls.put((long) bit + 1, value);
          } else {
            float[] v = {finite(in.getFloat()), finite(in.getFloat())};
            if (Math.abs(v[0]) > 1 || Math.abs(v[1]) > 1)
              throw new IllegalArgumentException("Stick range");
            controls.put((long) bit + 1, v);
          }
        }
      result.put(11L, controls);
    }
    return result;
  }
  private static Map<Long, Object> readPose(ByteBuffer in, int codec, long frame) {
    float[] xyz = new float[3], q = new float[4];
    if (codec == 0) {
      for (int i = 0; i < 3; i++) xyz[i] = finite(in.getFloat());
      for (int i = 0; i < 4; i++) q[i] = finite(in.getFloat());
    } else {
      for (int i = 0; i < 3; i++) xyz[i] = in.getInt() / 10000f;
      double norm = 0;
      for (int i = 0; i < 4; i++) {
        int value = in.getShort();
        if (value == -32768)
          throw new IllegalArgumentException("Quaternion sentinel");
        q[i] = value / 32767f;
        norm += q[i] * q[i];
      }
      norm = Math.sqrt(norm);
      if (Math.abs(norm - 1) > .001)
        throw new IllegalArgumentException("Quaternion norm");
      for (int i = 0; i < 4; i++) q[i] /= (float) norm;
    }
    double finalNorm = 0;
    for (float x : q) finalNorm += x * x;
    if (Math.abs(Math.sqrt(finalNorm) - 1) > .001)
      throw new IllegalArgumentException("Quaternion norm");
    return Cbor.map(0, frame, 1, xyz, 2, q);
  }
  private static float finite(float x) {
    if (!Float.isFinite(x))
      throw new IllegalArgumentException("Nonfinite OPC1");
    return x;
  }
  private static long rounded(float value, double scale, long low, long high) {
    finite(value);
    double x = value * scale;
    double n = Math.copySign(Math.floor(Math.abs(x) + .5), x);
    if (n < low || n > high)
      throw new IllegalArgumentException("Quantized range");
    return (long) n;
  }
  private static void exact(Map<Long, Object> map, long... keys) {
    Set<Long> wanted = new HashSet<>();
    for (long k : keys) wanted.add(k);
    if (!map.keySet().equals(wanted))
      throw new IllegalArgumentException("Unsupported optional pose/view field");
  }
}
