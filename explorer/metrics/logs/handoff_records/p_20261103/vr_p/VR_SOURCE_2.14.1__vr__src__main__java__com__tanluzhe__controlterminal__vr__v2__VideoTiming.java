package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;

/** Matches the pinned Android decoder's RTP/90 millisecond timestamp to source capture metadata. */
public final class VideoTiming {
  private final LinkedHashMap<Long, Packet> metadata = new LinkedHashMap<>();
  private final ClockSync clocks;
  private final Dashboard ui;
  private int localNode;
  private long videoEpoch = -1, ssrc = -1;
  public VideoTiming(ClockSync c, Dashboard d) {
    clocks = c;
    ui = d;
  }
  public synchronized void localNode(int n) {
    localNode = n;
  }
  public synchronized void metadata(Packet p) {
    long e = Cbor.number(p.body, 1, -1), s = Cbor.number(p.body, 9, -1),
         rtp = Cbor.number(p.body, 10, -1);
    if (e < 0 || s < 0 || rtp < 0 || rtp > 0xffffffffL)
      return;
    if (e != videoEpoch || s != ssrc) {
      metadata.clear();
      videoEpoch = e;
      ssrc = s;
    }
    metadata.put(rtp / 90, p);
    while (metadata.size() > 120) metadata.remove(metadata.keySet().iterator().next());
  }
  /** Drop output of obsolete frames without disturbing the H.264 decoder's reference chain. */
  public synchronized boolean acceptDecoded(long timestampNs, long now) {
    Packet m = metadata.get(timestampNs / 1_000_000L);
    if (m == null)
      return true;
    int src = (int) Cbor.number(m.body, 3, 0), epoch = (int) Cbor.number(m.body, 5, 0);
    double age = clocks.ageMs(src, epoch, Cbor.number(m.body, 4, 0), localNode, now);
    if (Double.isFinite(age) && age - clocks.uncertaintyMs(src, localNode) > 200) {
      ui.warning = "视频帧超过200ms，等待新画面";
      return false;
    }
    return true;
  }
  public synchronized void submitted(long textureTimestampNs, long now) {
    Packet m = metadata.get(textureTimestampNs / 1_000_000L);
    if (m == null) {
      ui.videoAge = Double.NaN;
      ui.videoAgeQuality = "采集时间未关联";
      return;
    }
    int src = (int) Cbor.number(m.body, 3, 0), epoch = (int) Cbor.number(m.body, 5, 0);
    long capture = Cbor.number(m.body, 4, 0);
    double age = clocks.ageMs(src, epoch, capture, localNode, now),
           error = clocks.uncertaintyMs(src, localNode);
    if (!Double.isFinite(age) || error > 20 || age < -error) {
      ui.videoAge = Double.NaN;
      ui.videoAgeQuality = "视频对时不可用";
      return;
    }
    ui.videoAge = age;
    ui.videoSubmitted = now;
    ui.videoAgeQuality = String.format(Locale.ROOT, "提交年龄 ±%.1fms%s", error,
        Cbor.number(m.body, 6, 1) == 0 ? "" : "（采集估计）");
  }
}
