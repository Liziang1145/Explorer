package com.tanluzhe.controlterminal.vr.v2;

import java.util.Map;

/** Raw OpenXR controls, never buttons, dead-zoned axes, velocities or motor targets. */
public final class InputControls {
  public final int valid;
  public final float leftGrip, rightGrip, leftTrigger, rightTrigger;
  public final float[] leftStick, rightStick;
  public InputControls(int mask, float lg, float rg, float lt, float rt, float[] ls, float[] rs) {
    int bits = mask & 63;
    float[] values = {lg, rg, lt, rt};
    for (int i = 0; i < 4; i++)
      if (!Float.isFinite(values[i]) || values[i] < 0 || values[i] > 1)
        bits &= ~(1 << i);
    if (!stick(ls))
      bits &= ~16;
    if (!stick(rs))
      bits &= ~32;
    valid = bits;
    leftGrip = lg;
    rightGrip = rg;
    leftTrigger = lt;
    rightTrigger = rt;
    leftStick = ls == null ? new float[2] : ls.clone();
    rightStick = rs == null ? new float[2] : rs.clone();
  }
  public static InputControls invalid() {
    return new InputControls(0, 0, 0, 0, 0, new float[2], new float[2]);
  }
  public static InputControls nativeSample(float[] axes, float[] pointer, boolean focused) {
    int mask = focused && pointer.length >= 9 ? (int) pointer[8] : 0;
    return new InputControls(mask, pointer[6], pointer[7], pointer[4], pointer[5],
        new float[] {axes[0], axes[1]}, new float[] {axes[2], axes[3]});
  }
  private static boolean stick(float[] s) {
    return s != null && s.length == 2 && Float.isFinite(s[0]) && Float.isFinite(s[1])
        && Math.abs(s[0]) <= 1 && Math.abs(s[1]) <= 1;
  }
  public Map<Long, Object> cbor() {
    Map<Long, Object> out = Cbor.map(0, 1, 7, valid);
    float[] values = {leftGrip, rightGrip, leftTrigger, rightTrigger};
    for (int i = 0; i < 4; i++)
      if ((valid & (1 << i)) != 0)
        out.put((long) i + 1, values[i]);
    if ((valid & 16) != 0)
      out.put(5L, leftStick.clone());
    if ((valid & 32) != 0)
      out.put(6L, rightStick.clone());
    return out;
  }
}
