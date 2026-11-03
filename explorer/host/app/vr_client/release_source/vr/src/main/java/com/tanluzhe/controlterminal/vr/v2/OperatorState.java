package com.tanluzhe.controlterminal.vr.v2;

import java.util.*;

/** TLZ/2.0 observations with raw input key11, ABXY key13 and optional geometry key14. */
public final class OperatorState {
  public static class Sample {
    public long time;
    public float[] poses, axes, eyes, controllerBounds;
    public int flags;
    public StickButtons stickButtons = StickButtons.invalid();
    public FaceButtons faceButtons = FaceButtons.invalid();
    public InputControls controls = InputControls.invalid();
  }
  public static Map<Long, Object> body(
      Sample in, long now, boolean foreground, long lease, long controlSequence, int frame) {
    boolean fresh = now >= in.time && now - in.time < 100_000_000L;
    int flags = foreground && fresh ? in.flags : 0;
    Map<Long, Object> out =
        Cbor.map(0, Cbor.u(lease), 1, flags & 7, 2, flags | (foreground ? 16 : 0), 8,
            Cbor.map(2, 60000), 9, controlSequence, 10, foreground ? 1 : 0, 11,
            foreground && fresh ? in.controls.cbor() : InputControls.invalid().cbor(), 13,
            foreground && fresh ? in.faceButtons.cbor() : FaceButtons.invalid().cbor(), 15,
            foreground && fresh ? in.stickButtons.cbor() : StickButtons.invalid().cbor());
    if ((flags & 1) != 0) {
      out.put(3L, pose(in.poses, 0, frame));
      out.put(6L,
          Cbor.map(0, pose(in.eyes, 0, frame), 1, Arrays.copyOfRange(in.eyes, 7, 11), 2,
              pose(in.eyes, 11, frame), 3, Arrays.copyOfRange(in.eyes, 18, 22)));
    }
    if ((flags & 2) != 0)
      out.put(4L, pose(in.poses, 7, frame));
    if ((flags & 4) != 0)
      out.put(5L, pose(in.poses, 14, frame));
    Map<Long,Object> geometry=ControllerGeometry.body(in.controllerBounds,in.poses,flags);
    if(geometry!=null)out.put(14L,geometry);
    return out;
  }
  private static Map<Long, Object> pose(float[] p, int offset, int frame) {
    return Cbor.map(0, frame, 1, new float[] {-p[offset + 2], -p[offset], p[offset + 1]}, 2,
        new float[] {-p[offset + 5], -p[offset + 3], p[offset + 4], p[offset + 6]});
  }
}
