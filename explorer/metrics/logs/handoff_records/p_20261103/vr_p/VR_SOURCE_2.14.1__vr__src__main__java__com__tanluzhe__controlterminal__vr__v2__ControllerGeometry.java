package com.tanluzhe.controlterminal.vr.v2;

import java.util.Map;

/** Additive OPERATOR_STATE key14. Bounds and corners use grip-aligned FLU axes. */
public final class ControllerGeometry {
  private ControllerGeometry() {}

  public static Map<Long, Object> body(float[] nativeBounds, float[] poses, int flags) {
    if (nativeBounds == null || nativeBounds.length != 14 || poses == null || poses.length != 21)
      return null;
    Map<Long, Object> out = Cbor.map(0, 1);
    for (int side = 0; side < 2; side++) {
      if ((flags & (2 << side)) == 0)
        continue;
      int b = side * 7, p = 7 + side * 7;
      float source = nativeBounds[b + 6];
      if (source != 0 && source != 1)
        continue; // -1 means no rendered, focused controller.
      boolean valid = true;
      for (int k = 0; k < 6; k++) valid &= Float.isFinite(nativeBounds[b + k]);
      for (int k = 0; k < 7; k++) valid &= Float.isFinite(poses[p + k]);
      for (int k = 0; k < 3; k++) valid &= nativeBounds[b + k + 3] > nativeBounds[b + k];
      double norm = 0;
      for (int k = 3; k < 7; k++) norm += (double) poses[p + k] * poses[p + k];
      if (!valid || Math.abs(norm - 1) > .002)
        continue;
      // Native right/up/back -> wire forward/left/up. Ordering min/max survives sign flips.
      float[] bounds
          = {-nativeBounds[b + 5], -nativeBounds[b + 3], nativeBounds[b + 1], -nativeBounds[b + 2], -nativeBounds[b], nativeBounds[b + 4]};
      float x = -poses[p + 5], y = -poses[p + 3], z = poses[p + 4], w = poses[p + 6];
      float[] corners = new float[24];
      for (int i = 0; i < 8; i++) {
        float a = bounds[(i & 1) != 0 ? 3 : 0], bb = bounds[(i & 2) != 0 ? 4 : 1], c = bounds[(i & 4) != 0 ? 5 : 2];
        // q * local * inverse(q); same orientation as existing pose key4/key5.
        float tx = 2 * (y * c - z * bb), ty = 2 * (z * a - x * c), tz = 2 * (x * bb - y * a);
        corners[i * 3]     = -poses[p + 2] + a + w * tx + y * tz - z * ty;
        corners[i * 3 + 1] = -poses[p] + bb + w * ty + z * tx - x * tz;
        corners[i * 3 + 2] = poses[p + 1] + c + w * tz + x * ty - y * tx;
      }
      out.put((long) side + 1, Cbor.map(0, side + 4, 1, (int) source, 2, bounds, 3, corners));
    }
    return out.size() > 1 ? out : null;
  }
}
