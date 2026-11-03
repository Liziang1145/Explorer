package com.tanluzhe.controlterminal.vr.v2;
public final class SceneCacheInfo {
 public final double fraction,bytesPerSecond;public final long bytes;public final boolean complete;
 public SceneCacheInfo(double fraction,double rate,long bytes,boolean complete){this.fraction=Math.max(0,Math.min(1,fraction));this.bytesPerSecond=Math.max(0,rate);this.bytes=bytes;this.complete=complete;}
}
