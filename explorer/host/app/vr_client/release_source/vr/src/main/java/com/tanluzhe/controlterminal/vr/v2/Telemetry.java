package com.tanluzhe.controlterminal.vr.v2;

/** Immutable, display-only AIPC sample. Never feeds the control encoder. */
public final class Telemetry {
  public static final class Arm {
    public final String state, source, reason;
    public final float[][] links;
    public final float[] quaternion;
    public final float open;
    public Arm(String state, String source, String reason, float[][] points, float[] q, float open) {
      this.state=state;this.source=source;this.reason=reason;this.open=open;
      links=points==null?null:new float[points.length][];
      if(points!=null)for(int i=0;i<points.length;i++)links[i]=points[i].clone();
      quaternion=q==null?null:q.clone();
    }
    public static Arm unknown(){return new Arm("unknown","","",null,null,Float.NaN);}
  }
  public final long received;
  public final String mode, modeText, error, baseReason, motionScaleText;
  public final double motionScale;
  public final boolean stopped;
  public final double vx,vy,wz;
  public final Arm left,right;
  public Telemetry(long time,String mode,String text,String error,boolean stopped,double vx,double vy,double wz,Arm left,Arm right){
    this(time,mode,text,error,stopped,vx,vy,wz,left,right,"");
  }
  public Telemetry(long time,String mode,String text,String error,boolean stopped,double vx,double vy,double wz,Arm left,Arm right,String baseReason){
    this(time,mode,text,error,stopped,vx,vy,wz,left,right,baseReason,Double.NaN,"");
  }
  public Telemetry(long time,String mode,String text,String error,boolean stopped,double vx,double vy,double wz,Arm left,Arm right,String baseReason,double scale,String scaleText){
    motionScale=scale==1||scale==.5||scale==.25?scale:Double.NaN;motionScaleText=scaleText==null?"":scaleText.trim();
    this.baseReason=baseReason;received=time;this.mode=mode;modeText=text;this.error=error;this.stopped=stopped;
    this.vx=vx;this.vy=vy;this.wz=wz;this.left=left;this.right=right;
  }
  public String modeSummary(long now){
    if(!fresh(now))return "模式未知 · 倍率：—";
    String label=motionScaleText;if(label.isEmpty()&&Double.isFinite(motionScale))label=motionScale==1?"普通":motionScale==.5?"精细":"微调";
    String value=Double.isFinite(motionScale)?java.math.BigDecimal.valueOf(motionScale).stripTrailingZeros().toPlainString()+"×":"—";
    return modeText+(label.isEmpty()?"":" · "+label)+" · 倍率："+value;
  }
  public boolean fresh(long now){return received>0&&now>=received&&now-received<2_000_000_000L;}
  public static Telemetry unknown(){return new Telemetry(0,"","模式未知","",false,Double.NaN,Double.NaN,Double.NaN,Arm.unknown(),Arm.unknown());}
  public String errors(long now){
    if(!fresh(now))return "";
    StringBuilder s=new StringBuilder();
    if(stopped)s.append("软件停止已锁存，需在网页解除。\n");
    if(!error.isEmpty())s.append(error).append('\n');
    for(int i=0;i<2;i++){Arm a=i==0?left:right;
      if(exceptional(a.reason))s.append(i==0?"左臂：":"右臂：").append(a.reason).append('\n');}
    if(exceptional(baseReason))s.append("底盘：").append(baseReason);
    return s.toString().trim();
  }
  private static boolean exceptional(String reason){return reason.matches("(?is).*(丢失|过期|超时|错误|故障|异常|拒绝|lost|stale|timeout|invalid|fault|error|reject).*");}
  public static String armText(Arm a){return a.state.equals("idle")?"待命":a.state.equals("following")||a.state.equals("vr_follow")?"跟随":a.state.equals("moving")?"动作中":"未知";}
}
