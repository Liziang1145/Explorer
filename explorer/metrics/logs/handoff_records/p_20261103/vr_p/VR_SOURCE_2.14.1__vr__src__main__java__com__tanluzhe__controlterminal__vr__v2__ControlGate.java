package com.tanluzhe.controlterminal.vr.v2;

/** Every reconnect/background/stop clears arm intent. Input alone can never grant a lease. */
public final class ControlGate {
  public volatile long lease, leaseExpiryBase;
  public volatile int referenceRevision, allowedMask;
  public volatile boolean connected, armed, foreground, tracking, clockConfirmed, robotReady,
      stopLatched = true;
  public synchronized void disarm() {
    armed = false;
  }
  public synchronized void reset() {
    lease = 0;
    leaseExpiryBase = 0;
    connected = false;
    armed = false;
    clockConfirmed = false;
    robotReady = false;
    stopLatched = true;
  }
  public synchronized boolean arm(long nowBase) {
    armed = connected && foreground && tracking && clockConfirmed && robotReady && !stopLatched
        && lease != 0 && (allowedMask & 1) != 0 && nowBase < leaseExpiryBase;
    return armed;
  }
  public synchronized boolean allow(long nowBase) {
    if (!connected || !foreground || !tracking || !clockConfirmed || !robotReady || stopLatched
        || lease == 0 || (allowedMask & 1) == 0 || nowBase >= leaseExpiryBase)
      armed = false;
    return armed;
  }
}
