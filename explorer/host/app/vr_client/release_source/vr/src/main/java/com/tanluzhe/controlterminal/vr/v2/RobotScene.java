package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;

/**
 * Uses measured/explicitly-estimated poses. Never draws target commands as actual robot feedback.
 */
public final class RobotScene {
  private final Map<Long, Object> stateFields = new HashMap<>();
  public synchronized Map<Long, Object> stateSnapshot() {
    return new HashMap<>(stateFields);
  }
  private final SceneStore frames;
  private final Map<Integer, Map<Long, Object>> parts = new HashMap<>();
  private final Map<Integer, Long> arrivals = new HashMap<>();
  public volatile float[] actualBasePosition;
  public volatile float actualBaseYaw;
  public volatile long actualBaseArrival;
  public volatile int actualBaseFrame, baseFrameId;
  public java.util.function.Predicate<Map<Long, Object>> sampleUsable = s -> true;
  public volatile float[] leftJoints, rightJoints;
  public RobotScene(SceneStore f) {
    frames = f;
  }
  private Map<Long, Object> validSample(Object object) {
    Map<Long, Object> sample = Cbor.object(object);
    return Boolean.TRUE.equals(sample.get(2L)) && sampleUsable.test(sample)
        ? Cbor.object(sample.get(3L))
        : null;
  }
  public synchronized void state(Packet p, long now) {
    Map<Long, Object> b = p.body;
    stateFields.putAll(b);
    if (b.containsKey(3L)) {
      Map<Long, Object> base = validSample(b.get(3L));
      if (base != null) {
        float[] xyz = Cbor.floats(base.get(1L), 3), q = Math3.quaternion(base.get(2L));
        actualBasePosition = xyz;
        actualBaseFrame = (int) Cbor.number(base, 0, -1);
        actualBaseArrival = now;
        actualBaseYaw = (float) Math.atan2(
            2 * (q[3] * q[2] + q[0] * q[1]), 1 - 2 * (q[1] * q[1] + q[2] * q[2]));
        parts.put(0, base);
        arrivals.put(0, now);
        if (baseFrameId > 0 && baseFrameId != actualBaseFrame) {
          float[] parent = frames.matrix(actualBaseFrame), local = matrix(xyz, q),
                  world = new float[16];
          for (int col = 0; col < 4; col++)
            for (int row = 0; row < 4; row++)
              for (int k = 0; k < 4; k++)
                world[col * 4 + row] += parent[k * 4 + row] * local[col * 4 + k];
          frames.transform(baseFrameId, world);
        }
      }
    }
    for (int side = 0; side < 2; side++) {
      Object value = b.get(5L + side);
      if (value != null) {
        Map<Long, Object> s = Cbor.object(value);
        if (Boolean.TRUE.equals(s.get(2L))) {
          float[] joint = Cbor.floats(s.get(3L), 6);
          if (side == 0)
            leftJoints = joint;
          else
            rightJoints = joint;
        }
      }
      Object tcp = b.get(9L + side);
      if (tcp != null) {
        Map<Long, Object> pose = validSample(tcp);
        if (pose != null) {
          parts.put(10 + side, pose);
          arrivals.put(10 + side, now);
        }
      }
    }
    Object grips = b.get(11L);
    if (grips instanceof List)
      for (Object item : (List<?>) grips) {
        Map<Long, Object> part = validSample(item);
        if (part != null) {
          int id = (int) Cbor.number(part, 0, -1);
          if (id >= 0 && id < 4) {
            parts.put(20 + id, Cbor.object(part.get(1L)));
            arrivals.put(20 + id, now);
          }
        }
      }
  }
  /** Display-only base in map/OpenXR coordinates, never an authorization or control target. */
  public synchronized float[] displayBase(long now) {
    if (actualBasePosition == null || now - actualBaseArrival > 200_000_000L
        || now < actualBaseArrival)
      return null;
    try {
      float[] parent = frames.matrix(actualBaseFrame);
      float[] p = actualBasePosition;
      float x = parent[0] * p[0] + parent[4] * p[1] + parent[8] * p[2] + parent[12];
      float y = parent[1] * p[0] + parent[5] * p[1] + parent[9] * p[2] + parent[13];
      float z = parent[2] * p[0] + parent[6] * p[1] + parent[10] * p[2] + parent[14];
      float fx = (float) Math.cos(actualBaseYaw), fy = (float) Math.sin(actualBaseYaw);
      float yaw =
          (float) Math.atan2(parent[1] * fx + parent[5] * fy, parent[0] * fx + parent[4] * fy);
      float[] out = {-y, z, -x, yaw};
      for (float value : out)
        if (!Float.isFinite(value))
          return null;
      return out;
    } catch (RuntimeException unavailable) {
      return null;
    }
  }
  private static float[] matrix(float[] p, float[] q) {
    float x = q[0], y = q[1], z = q[2], w = q[3];
    return new float[] {1 - 2 * y * y - 2 * z * z, 2 * x * y + 2 * w * z, 2 * x * z - 2 * w * y, 0,
        2 * x * y - 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z + 2 * w * x, 0,
        2 * x * z + 2 * w * y, 2 * y * z - 2 * w * x, 1 - 2 * x * x - 2 * y * y, 0, p[0], p[1],
        p[2], 1};
  }
  public synchronized void display(Packet p, long now) {
    Object poses = p.body.get(2L);
    if (!(poses instanceof List))
      return;
    for (Object item : (List<?>) poses) {
      Map<Long, Object> object = Cbor.object(item);
      int id = (int) Cbor.number(object, 0, -1);
      if (id < 0 || id > 1000)
        continue;
      Map<Long, Object> pose = validSample(object.get(1L));
      if (pose != null) {
        parts.put(100 + id, pose);
        arrivals.put(100 + id, now);
      }
    }
  }
  public synchronized float[] lines(long now) {
    List<Float> vertices = new ArrayList<>();
    for (Map.Entry<Integer, Map<Long, Object>> e : parts.entrySet()) {
      if (now - arrivals.get(e.getKey()) > 200_000_000L)
        continue;
      try {
        Map<Long, Object> p = e.getValue();
        float[] xyz = Cbor.floats(p.get(1L), 3), q = Math3.quaternion(p.get(2L)),
                t = frames.matrix((int) Cbor.number(p, 0, -1));
        float size = e.getKey() == 0 ? .25f : .055f;
        int[] edges = {0, 1, 1, 3, 3, 2, 2, 0, 4, 5, 5, 7, 7, 6, 6, 4, 0, 4, 1, 5, 2, 6, 3, 7};
        for (int corner : edges) {
          float x = (corner & 1) == 0 ? -size : size, y = (corner & 2) == 0 ? -size : size,
                z = (corner & 4) == 0 ? -size : size;
          float[] v = Math3.mul(
              Math3.mul(q, new float[] {x, y, z, 0}), new float[] {-q[0], -q[1], -q[2], q[3]});
          x = v[0] + xyz[0];
          y = v[1] + xyz[1];
          z = v[2] + xyz[2];
          float wx = t[0] * x + t[4] * y + t[8] * z + t[12],
                wy = t[1] * x + t[5] * y + t[9] * z + t[13],
                wz = t[2] * x + t[6] * y + t[10] * z + t[14];
          Collections.addAll(vertices, -wy, wz, -wx, .15f, 1f, .55f, 1f);
        }
      } catch (RuntimeException ignored) {
      }
    }
    float[] out = new float[vertices.size()];
    for (int i = 0; i < out.length; i++) out[i] = vertices.get(i);
    return out;
  }
}
