package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;

/** Clock conversion is explicit and bounded. Never treats RTT/2 as measured one-way delay. */
public final class ClockSync {
  public static final class Mapping {
    public int node, epoch;
    public long refLocal, refBase, updatedBase, uncertainty;
    public double drift;
    public long base(long t) {
      return refBase + Math.round((t - refLocal) * (1 + drift));
    }
  }
  private final Map<Integer, Mapping> maps = new HashMap<>();
  private final List<long[]> samples = new ArrayList<>();
  public synchronized void reset() {
    maps.clear();
    samples.clear();
  }
  public synchronized void install(Mapping m) {
    if (Math.abs(m.drift) > 0.001 || m.uncertainty < 0)
      throw new IllegalArgumentException("Clock mapping");
    maps.put(m.node, m);
  }
  public synchronized Mapping get(int node) {
    return maps.get(node);
  }
  public synchronized double ageMs(int origin, int epoch, long originNs, int local, long nowNs) {
    Mapping a = maps.get(origin), b = maps.get(local);
    if (a == null || b == null || a.epoch != epoch)
      return Double.NaN;
    long nowB = b.base(nowNs);
    if (nowB - a.updatedBase > 2_000_000_000L || nowB - b.updatedBase > 2_000_000_000L)
      return Double.NaN;
    return (nowB - a.base(originNs)) / 1e6;
  }
  public synchronized double uncertaintyMs(int a, int b) {
    Mapping x = maps.get(a), y = maps.get(b);
    return x == null || y == null ? Double.POSITIVE_INFINITY
                                  : (x.uncertainty + y.uncertainty) / 1e6;
  }
  public synchronized boolean controlReady(int base, int local, long now) {
    Mapping m = maps.get(local), b = maps.get(base);
    return m != null && b != null && uncertaintyMs(base, local) <= 20
        && m.base(now) - m.updatedBase < 2_000_000_000L;
  }
  public synchronized boolean fresh(int source, int local, long now) {
    Mapping a = maps.get(source), b = maps.get(local);
    return a != null && b != null && b.base(now) - a.updatedBase <= 2_000_000_000L
        && b.base(now) - b.updatedBase <= 2_000_000_000L;
  }
  public synchronized Mapping sample(int node, int epoch, long t1, long t2, long t3, long t4) {
    long rtt = (t4 - t1) - (t3 - t2);
    if (rtt < 0 || rtt > 2_000_000_000L || t3 < t2)
      return null;
    samples.add(new long[] {t1 + (t4 - t1) / 2, t2 + (t3 - t2) / 2, rtt});
    if (samples.size() > 120)
      samples.remove(0);
    long[] best = samples.stream().min(Comparator.comparingLong(x -> x[2])).get();
    Mapping m = new Mapping();
    m.node = node;
    m.epoch = epoch;
    m.refLocal = best[0];
    m.refBase = best[1];
    m.uncertainty = best[2] / 2 + 500_000;
    m.updatedBase = t3;
    return m;
  }
}
