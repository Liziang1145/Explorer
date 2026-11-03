package com.tanluzhe.controlterminal.vr.v2;

/** Validated independent observation scheduler period. */
public final class ObservationRate {
  public final int hz;
  public final long periodNs;
  public ObservationRate(int value) {
    if (value < 10 || value > 90)
      throw new IllegalArgumentException("观察频率范围10–90Hz");
    hz = value;
    periodNs = 1_000_000_000L / hz;
  }
}
