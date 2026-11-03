package com.tanluzhe.controlterminal.vr.v2;
/** Per-source bounded reconnect policy. A temporarily unavailable stream is not an auth failure. */
public final class VideoReconnect {
 private int failures;
 public static boolean authorizationFailure(int status){return status==401||status==403;}
 public int nextDelayMillis(){int delay=1000<<Math.min(failures,3);failures=Math.min(3,failures+1);return delay;}
 public void recovered(){failures=0;}
}
