package com.tanluzhe.controlterminal.vr.v2;
/** Receiver feedback / sender congestion controller. Changes bitrate only, never recording. */
public final class AdaptivePreview {
  public static final int MIN = 500000, MAX = 16000000;
  private int ceiling = 6000000, current = 6000000;
  private long lastChange = -1, stableSince = -1;
  public synchronized int current() {
    return current;
  }
  public synchronized void reset(int target) {
    ceiling     = Math.max(MIN, Math.min(MAX, target));
    current     = ceiling;
    lastChange  = -1;
    stableSince = -1;
  }
  public synchronized int feedback(long now, long throughput, double bufferedMs, double rttMs, int dropped) {
    if (throughput <= 0 || throughput > 1000000000L || !Double.isFinite(bufferedMs) || bufferedMs < 0 || bufferedMs > 60000
        || !Double.isFinite(rttMs) || rttMs < 0 || rttMs > 60000 || dropped < 0 || dropped > 100000)
      throw new IllegalArgumentException("非法网络反馈");
    boolean slow = bufferedMs > 300 || rttMs > 250 || dropped > 0 || throughput < current * .9;
    if (slow) {
      stableSince = -1;
      if (lastChange < 0 || now - lastChange >= 1000) {
        current    = Math.max(MIN, (int) Math.min(current * .7, throughput * .75));
        lastChange = now;
      }
    } else if (throughput > current * 1.25 && bufferedMs < 120 && rttMs < 180) {
      if (stableSince < 0)
        stableSince = now;
      if (now - stableSince >= 4000 && (lastChange < 0 || now - lastChange >= 1000)) {
        current    = Math.min(ceiling, Math.max(current + 50000, (int) (current * 1.1)));
        lastChange = now;
      }
    } else
      stableSince = -1;
    return current;
  }
  public synchronized int congested(long now) {
    return feedback(now, Math.max(1, current), 500, 0, 1);
  }
}
