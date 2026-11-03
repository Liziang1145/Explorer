package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;
public final class RttHistory {
  private final ArrayDeque<double[]> samples = new ArrayDeque<>();
  public synchronized void add(double ms, long now) {
    if (!Double.isFinite(ms) || ms < 0)
      return;
    samples.add(new double[] {now, ms});
    while (samples.size() > 200) samples.removeFirst();
  }
  /** p50/p95/max and mean absolute consecutive RTT difference, all milliseconds. */
  public synchronized float[] summary(long now) {
    while (!samples.isEmpty() && now - samples.peekFirst()[0] > 10_000_000_000L)
      samples.removeFirst();
    if (samples.isEmpty())
      return null;
    double[] values = new double[samples.size()];
    int i = 0;
    double jitter = 0, last = -1;
    for (double[] s : samples) {
      values[i++] = s[1];
      if (last >= 0)
        jitter += Math.abs(s[1] - last);
      last = s[1];
    }
    Arrays.sort(values);
    return new float[] {(float) values[(values.length - 1) / 2],
        (float) values[Math.max(0, (int) Math.ceil(values.length * .95) - 1)],
        (float) values[values.length - 1],
        values.length < 2 ? 0 : (float) (jitter / (values.length - 1))};
  }
}
