package com.tanluzhe.controlterminal.vr.v2;
public final class Math3 {
  private Math3() {}
  public static float[] quaternion(Object value) {
    float[] q = Cbor.floats(value, 4);
    double norm = 0;
    for (float v : q) norm += v * v;
    if (Math.abs(Math.sqrt(norm) - 1) > .001)
      throw new IllegalArgumentException("Quaternion normalization");
    float scale = (float) (1 / Math.sqrt(norm));
    for (int i = 0; i < 4; i++) q[i] *= scale;
    return q;
  }
  /** Pose arrays contain position then quaternion, head at 0, hands at 7/14. */
  public static float[] relative(float[] poses, int offset) {
    float[] q = {-poses[3], -poses[4], -poses[5], poses[6]};
    float[] d = {
        poses[offset] - poses[0], poses[offset + 1] - poses[1], poses[offset + 2] - poses[2], 0};
    float[] r = mul(mul(q, d), new float[] {-q[0], -q[1], -q[2], q[3]});
    float[] h = mul(q,
        new float[] {poses[offset + 3], poses[offset + 4], poses[offset + 5], poses[offset + 6]});
    return new float[] {r[0], r[1], r[2], h[0], h[1], h[2], h[3]};
  }
  public static float[] mul(float[] a, float[] b) {
    return new float[] {a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
        a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
        a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
        a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2]};
  }
}
