package com.tanluzhe.controlterminal.vr.v2;
/** Pure display state: zero hold 5s + 650ms fade, repeated samples never restart hold. */
public final class SpeedDisplay {
  private long zeroSince=-1;
  public double value=Double.NaN;
  public float update(Telemetry t,long now,boolean modal){
    if(!t.fresh(now)||!t.mode.equals("base")){zeroSince=-1;value=Double.NaN;return 0;}
    value=Double.isFinite(t.vx)&&Double.isFinite(t.vy)?Math.hypot(t.vx,t.vy):Double.NaN;
    float alpha=1;
    if(Double.isFinite(value)&&value<.0001){if(zeroSince<0)zeroSince=now;alpha=(float)Math.max(0,Math.min(1,1-(now-zeroSince-5_000_000_000L)/650_000_000.0));}else zeroSince=-1;
    return modal?0:alpha;
  }
}
