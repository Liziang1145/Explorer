package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;
/** A 200ms reorder grace period, with bounded gaps and ten-second reporting windows. */
public final class LossWindow {
  private static final class Stream {
    long high;
    final Map<Long, Long> missing = new HashMap<>();
  }
  private final Map<String, Stream> streams = new HashMap<>();
  private long received, lost, late, duplicates;
  public synchronized void receive(Packet p, long now) {
    String key = p.node + "/" + p.stream;
    Stream s = streams.computeIfAbsent(key, k -> new Stream());
    if (s.high == 0) {
      s.high = p.seq;
      received++;
      return;
    }
    if (Long.compareUnsigned(p.seq, s.high) > 0) {
      received++;
      long gap = p.seq - s.high - 1;
      if (gap > 512) {
        lost += gap;
      } else
        for (long x = s.high + 1; x != p.seq; x++) s.missing.put(x, now);
      s.high = p.seq;
    } else {
      Long expected = s.missing.remove(p.seq);
      if (expected != null) {
        late++;
        received++;
      } else
        duplicates++;
    }
    expire(now);
  }
  public synchronized void expire(long now) {
    for (Stream s : streams.values()) {
      Iterator<Long> i = s.missing.values().iterator();
      while (i.hasNext())
        if (now - i.next() > 200_000_000L) {
          lost++;
          i.remove();
        }
    }
  }
  public synchronized long[] snapshot() {
    long[] out = {received, lost, late, duplicates};
    received = lost = late = duplicates = 0;
    return out;
  }
  public synchronized long[] peek() {
    return new long[] {received, lost, late, duplicates};
  }
}
