package com.tanluzhe.controlterminal.vr.v2;

import java.util.Map;

/** Direct-AIPC key13. These are instantaneous physical states, not UI edges or action events. */
public final class FaceButtons {
  public final int valid, pressed;
  public FaceButtons(int valid, int pressed) {
    if ((valid & ~15) != 0 || (pressed & ~valid) != 0)
      throw new IllegalArgumentException("ABXY bitmap");
    this.valid = valid;
    this.pressed = pressed;
  }
  public static FaceButtons invalid() {
    return new FaceButtons(0, 0);
  }
  public static FaceButtons nativeSample(int localButtons, float[] pointers, boolean focused) {
    if (!focused || pointers.length < 10)
      return invalid();
    // Local OpenXR/UI order is A,X,B,Y. Wire order is A,B,X,Y.
    int pressed = (localButtons & 1) | ((localButtons & 4) >> 1) | ((localButtons & 2) << 1)
        | (localButtons & 8);
    int mask = (int) pointers[9];
    return new FaceButtons(mask & 15, pressed & mask & 15);
  }
  public Map<Long, Object> cbor() {
    return Cbor.map(0, 1, 1, valid, 2, pressed);
  }
}
