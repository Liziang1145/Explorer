"""Render production VrHud geometry with an AWT graphics adapter for off-device layout review.

Fonts/antialiasing differ from Android. This is a layout preview, never a Quest screenshot.
"""
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
out = root / 'vr/build/ui-preview'
src = out / 'adapter/android/graphics'
src.mkdir(parents=True, exist_ok=True)
classes = {
 'Color': 'public static final int TRANSPARENT=0, WHITE=0xffffffff;',
 'PorterDuff': 'public enum Mode {CLEAR}',
 'Typeface': 'public static final int NORMAL=0; public static Typeface create(String s,int n){return new Typeface();}',
 'Bitmap': '''public java.awt.image.BufferedImage image=new java.awt.image.BufferedImage(1600,1000,2);''',
 'Paint': '''public static final int ANTI_ALIAS_FLAG=1; public enum Style {FILL,STROKE}
   public int color;public float size=22; public Paint(int flags){}
   public Style style=Style.FILL;public float stroke=1;public void setColor(int c){color=c;}public void setStyle(Style s){style=s;}public void setStrokeWidth(float w){stroke=w;}
   public void setTypeface(Typeface t){}public void setTextSize(float v){size=v;}
   public java.awt.Font font(){return new java.awt.Font("Microsoft YaHei",0,1).deriveFont(size);}
   public float measureText(String s){return (float)font().getStringBounds(s,new java.awt.font.FontRenderContext(null,true,true)).getWidth();}
   public int breakText(String s,boolean f,float w,float[] a){int n=s.length();while(n>0&&measureText(s.substring(0,n))>w)n--;return n;}
 ''',
 'Canvas': '''java.awt.Graphics2D g; public Canvas(Bitmap b){g=b.image.createGraphics();g.setRenderingHint(java.awt.RenderingHints.KEY_ANTIALIASING,java.awt.RenderingHints.VALUE_ANTIALIAS_ON);g.setRenderingHint(java.awt.RenderingHints.KEY_TEXT_ANTIALIASING,java.awt.RenderingHints.VALUE_TEXT_ANTIALIAS_ON);}
   public java.util.ArrayDeque<java.awt.Shape> clips=new java.util.ArrayDeque<>();public int save(){java.awt.Shape clip=g.getClip();clips.push(clip==null?new java.awt.Rectangle(0,0,1600,1000):clip);return clips.size();}public void clipRect(float l,float t,float r,float b){g.clip(new java.awt.geom.Rectangle2D.Float(l,t,r-l,b-t));}public void restore(){g.setClip(clips.pop());}
   public void drawColor(int color,PorterDuff.Mode mode){g.setComposite(java.awt.AlphaComposite.Clear);g.fillRect(0,0,1600,1000);g.setComposite(java.awt.AlphaComposite.SrcOver);}
   public void drawRoundRect(float x,float y,float r,float b,float rx,float ry,Paint p){g.setColor(new java.awt.Color(p.color,true));java.awt.Shape shape=new java.awt.geom.RoundRectangle2D.Float(x,y,r-x,b-y,rx*2,ry*2);if(p.style==Paint.Style.STROKE){g.setStroke(new java.awt.BasicStroke(p.stroke));g.draw(shape);}else g.fill(shape);}
   public void drawCircle(float x,float y,float radius,Paint p){g.setColor(new java.awt.Color(p.color,true));java.awt.Shape shape=new java.awt.geom.Ellipse2D.Float(x-radius,y-radius,2*radius,2*radius);g.setStroke(new java.awt.BasicStroke(p.stroke));if(p.style==Paint.Style.STROKE)g.draw(shape);else g.fill(shape);}
   public void drawLine(float x,float y,float x2,float y2,Paint p){g.setColor(new java.awt.Color(p.color,true));g.setStroke(new java.awt.BasicStroke(p.stroke));g.draw(new java.awt.geom.Line2D.Float(x,y,x2,y2));}
   public void drawText(String s,float x,float y,Paint p){g.setFont(p.font());g.setColor(new java.awt.Color(p.color,true));g.drawString(s,x,y);}
 '''
}
for name, body in classes.items():
    (src / (name+'.java')).write_text('package android.graphics; public class '+name+'{'+body+'}', encoding='utf-8')
harness = out / 'adapter/Preview.java'
harness.write_text('''package com.tanluzhe.controlterminal.vr.v2;
import android.graphics.*;import java.nio.file.*;import javax.imageio.ImageIO;
public class Preview {
 public static void main(String[] args)throws Exception {
  VrUiState s=new VrUiState();Dashboard d=new Dashboard();long now=System.nanoTime();
  d.connection="AIPC已连接";d.lease="直连输入";d.robot="车辆反馈未就绪";d.simulation=true;
  d.baseRtt=8.2;d.endRtt=19.6;d.carRtt=10.1;d.controlAge=22.4;
  d.stateReceived=d.cloudReceived=now-18000000;d.observationActualHz=50;d.observationBytes=308;d.observationEncoding="opbin1";
  s.displayHz=72;s.activeHands=3;s.tracking=7;
  d.telemetry=new Telemetry(now,"arms","双臂模式","",false,0,0,0,Telemetry.Arm.unknown(),Telemetry.Arm.unknown(),"",1,"普通");
  s.raw=new InputControls(63,0,0,.12f,0,new float[2],new float[2]);
  VrHud hud=new VrHud();
  Bitmap b=new Bitmap();hud.drawWorld(b,d,s,now,false);ImageIO.write(b.image,"png",Path.of(args[0],"world.png").toFile());
  d.videoReceived=now;d.rgb.received=now;d.rgb.fps=30;d.rgb.status="已连接";d.depth.received=now;
  Bitmap live=new Bitmap();hud.drawWorld(live,d,s,now,false);
  for(int y=220;y<640;y++)for(int x=360;x<1240;x++)
    if((live.image.getRGB(x,y)>>>24)!=0)throw new AssertionError("Live video aperture must be transparent: "+x+","+y);
  ImageIO.write(live.image,"png",Path.of(args[0],"world-live.png").toFile());
  s.videoMode=0;
  for(int state=0;state<2;state++){
   d.videoReceived=state==0?0:now;
   Bitmap closed=new Bitmap();hud.drawWorld(closed,d,s,now,false);
   for(int y=140;y<710;y++)for(int x=310;x<1290;x++)
    if((closed.image.getRGB(x,y)>>>24)!=0)throw new AssertionError("Closed video must not leave a window");
   ImageIO.write(closed.image,"png",Path.of(args[0],"world-closed.png").toFile());
  }
  s.videoMode=2;d.videoReceived=now;d.rgb.received=now;d.rgb.fps=30;d.rgb.status="已连接";d.depth.received=now;
  s.captureStreaming=true;
  for(int mode=0;mode<5;mode++){
   s.menuOpen=mode==1||mode==4;s.logsOpen=mode==2;s.videoPanel=mode==3;s.capturePanel=mode==4;
   s.logLines=new String[]{"12:00:00 INFO UI/VIEW_MODE observer","12:00:00 INFO INPUT/SAMPLE valid=63","12:00:00 INFO RTC/CHANNEL_OPEN tlz.ctrl.v2"};
   Bitmap h=new Bitmap();hud.draw(h,d,s,now,false);ImageIO.write(h.image,"png",Path.of(args[0],"hud-"+mode+".png").toFile());
   // A live notice must remain visible over every modal and be passive.
   int noticeX=25,noticeY=54;
   if((h.image.getRGB(noticeX,noticeY)>>>24)==0)throw new AssertionError("Live notice missing in mode "+mode);
   if(s.hit(noticeX/1600f,noticeY/1000f)!=0)throw new AssertionError("Live notice must not be a clickable permission/cancel control");
  }
  s.menuOpen=s.logsOpen=s.videoPanel=s.capturePanel=false;s.interactionLocked=true;
  Bitmap locked=new Bitmap();hud.draw(locked,d,s,now,false);ImageIO.write(locked.image,"png",Path.of(args[0],"hud-locked.png").toFile());
  int redPixels=0;for(int y=24;y<89;y++)for(int x=469;x<1132;x++){int rgba=locked.image.getRGB(x,y);if(((rgba>>>16)&255)>130&&((rgba>>>8)&255)<100&&(rgba&255)<120)redPixels++;}
  if(redPixels<1000)throw new AssertionError("Top-centred red lock border/text missing");
  int alpha=locked.image.getRGB(800,40)>>>24;if(alpha==0||alpha>=217)throw new AssertionError("Lock glass must be translucent");
  s.interactionLocked=false;
  s.integratedStatic=true;s.sceneBrowser=false;s.cloudModeStatus="场景模式 · 实验室全量彩色 · 未配准 · 粗图已显示";s.cloudCacheStatus="近区缓存 88/88 · 显示 75/88 · 磁盘 85.1 MiB · 当前近区缓存完成";s.sceneCacheFraction=1;s.sceneCatalogIds=new String[]{"scene-a","scene-b","scene-c"};s.sceneCatalogLabels=new String[]{"实验室 · 静态净化 · 全量彩色","实验室 · 完整轻量场景","历史实验室 · 分块场景"};s.sceneSource="内置实验室扫描";s.sceneStatus="场景就绪";s.sceneStats=new long[]{113,780279,410071,19772364,19772364,19772364,113,0};
  s.menuOpen=s.capturePanel=s.logsOpen=s.videoPanel=false;
  Bitmap sw=new Bitmap();hud.drawWorld(sw,d,s,now,false);ImageIO.write(sw.image,"png",Path.of(args[0],"scene-world.png").toFile());
  s.sceneCaches=java.util.Map.of("scene-a",new SceneCacheInfo(1,0,89128960,true),"scene-b",new SceneCacheInfo(.47,430080,41943040,false));
  s.presentation(VrUiState.SCENE_PANEL);
  Bitmap sh=new Bitmap();hud.draw(sh,d,s,now,false);ImageIO.write(sh.image,"png",Path.of(args[0],"scene-panel.png").toFile());

 }
}''', encoding='utf-8')
java = Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
production = root / 'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2/VrHud.java'
cp = root / 'vr/build/v2-contract-tests'
compiled = out / 'classes'
compiled.mkdir(exist_ok=True)
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(cp),'-d',str(compiled),
                *map(str,src.glob('*.java')),str(production),str(harness)],check=True)
subprocess.run([str(java/'java.exe'),'-Djava.awt.headless=true','-cp',str(compiled)+';'+str(cp),
                'com.tanluzhe.controlterminal.vr.v2.Preview',str(out)],check=True)
background = Image.open(out/'environment.png').convert('RGBA')
for mode in range(5):
    image = background.copy()
    # Same physical panel dimensions/distances as the native renderer, symmetric preview FOV.
    world=Image.open(out/'world.png').resize((1158,724),Image.Resampling.LANCZOS)
    image.alpha_composite(world,(221,129))
    hud=Image.open(out/f'hud-{mode}.png').resize((879,549),Image.Resampling.LANCZOS)
    image.alpha_composite(hud,(360,225))
    draw=ImageDraw.Draw(image)
    draw.text((24,24),'OFF-DEVICE LAYOUT PREVIEW / synthetic data / not a Quest capture',fill='#617780')
    image.save(out/f'layout-{mode}.png')
print('PASS: production VrHud drawing geometry rendered in five modes with AWT adapter; previews are not device captures.')
