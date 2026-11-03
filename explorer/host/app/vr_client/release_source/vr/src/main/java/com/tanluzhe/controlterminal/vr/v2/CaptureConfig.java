package com.tanluzhe.controlterminal.vr.v2;

/** Immutable export framing. Framing is locked to the principal ray; opposing margins are paired symmetrically. */
public final class CaptureConfig {
  public final int width,height,fps,bitrate,eye;
  public final float verticalFov,left,right,top,bottom,centerX,centerY;
  public CaptureConfig(int width,int height,int fps,int bitrate,int eye,float fov,float left,float right,float top,float bottom,float cx,float cy){
    if(width<320||height<240||width>2560||height>2560||(long)width*height>3686400||width%2!=0||height%2!=0)throw new IllegalArgumentException("宽高须为偶数；320×240起，单边≤2560，总像素≤2560×1440");
    if(fps<5||fps>60||bitrate<250000||bitrate>80000000||eye<0||eye>1)throw new IllegalArgumentException("FPS范围5–60，码率250000–80000000，eye为0或1");
    if(!Float.isFinite(fov)||fov<20||fov>120)throw new IllegalArgumentException("垂直视野角20–120度");
    for(float v:new float[]{left,right,top,bottom})if(!Float.isFinite(v)||v<0||v>.45f)throw new IllegalArgumentException("单侧边距范围0–0.45");
    if(!Float.isFinite(cx)||!Float.isFinite(cy)||cx<0||cx>1||cy<0||cy>1)throw new IllegalArgumentException("取景中心范围0–1");
    this.width=width;this.height=height;this.fps=fps;this.bitrate=bitrate;this.eye=eye;verticalFov=fov;this.left=this.right=Math.max(left,right);this.top=this.bottom=Math.max(top,bottom);centerX=centerY=.5f;
  }
  public static CaptureConfig defaults(){return new CaptureConfig(1920,1080,30,6000000,0,70,.02f,.02f,.02f,.02f,.5f,.5f);}
  public static CaptureConfig recordingDefaults(){return new CaptureConfig(2560,1440,60,40000000,0,70,.02f,.02f,.02f,.02f,.5f,.5f);}
  public float[] nativeValues(){return new float[]{verticalFov,left,right,top,bottom,centerX,centerY,eye};}
  public boolean sameEncoder(CaptureConfig c){return width==c.width&&height==c.height&&fps==c.fps&&bitrate==c.bitrate;}
  public CaptureConfig framing(float fov,float margin){return new CaptureConfig(width,height,fps,bitrate,eye,fov,margin,margin,margin,margin,centerX,centerY);}
}
