package com.tanluzhe.controlterminal.vr.v2;
import android.graphics.*;
import java.util.*;

/** Approved 2026-10-25 layout, in independent world and head-relative layers. */
final class VrHud {
 private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private Canvas c;
 private static final int INK=0xff132f42,MUTED=0xff294759,TEAL=0xff006474;
 private static String latency(double value){return Double.isFinite(value)?String.format(Locale.ROOT,"%.1f ms",value):"—";}
 private static int armColor(Telemetry.Arm a,boolean fresh){return !fresh?MUTED:a.state.equals("moving")?0xff236bc2:a.state.equals("following")||a.state.equals("vr_follow")?TEAL:MUTED;}
 static String[] wrapLogs(String[] entries){
  Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);paint.setTextSize(19);List<String> rows=new ArrayList<>();
  for(String entry:entries){String level=entry.contains("ERROR")?"ERROR":entry.contains("WARN")?"WARN":entry.contains("DEBUG")?"DEBUG":"INFO";int at=0;while(at<entry.length()){String prefix=at==0?"":"  "+level+" · ";int n=Math.max(1,paint.breakText(entry.substring(at),true,1010-paint.measureText(prefix),null));rows.add(prefix+entry.substring(at,at+n));at+=n;}}
  return rows.toArray(new String[0]);
 }
 private final SpeedDisplay speed=new SpeedDisplay();
 private void begin(Bitmap b){c=new Canvas(b);c.drawColor(Color.TRANSPARENT,PorterDuff.Mode.CLEAR);}
 void draw(Bitmap bitmap,Dashboard d,VrUiState s,long now,boolean ignored){
  begin(bitmap);Telemetry t=d.telemetry;boolean fresh=t.fresh(now);
  String mode=t.modeSummary(now);
  String[] pieces={Double.isFinite(s.displayHz)?String.format(Locale.ROOT,"%.0f FPS",s.displayHz):"— FPS","AIPC "+latency(d.baseRtt),"往返 "+latency(d.endRtt),mode,"左臂 · "+(fresh?Telemetry.armText(t.left):"未知"),"右臂 · "+(fresh?Telemetry.armText(t.right):"未知")};
  if(s.sceneBrowser)pieces=new String[]{Double.isFinite(s.displayHz)?String.format(Locale.ROOT,"%.0f FPS",s.displayHz):"— FPS",s.sceneView==1?"沙盘":"1∶1",s.scenePointMode?"顶点点云":"有色表面","可见块 "+s.sceneStats[6]+" / "+s.sceneStats[0],String.format(Locale.ROOT,"GPU %.1f MB",s.sceneStats[3]/1e6)};
  if(s.cloudMode)pieces=new String[]{Double.isFinite(s.displayHz)?String.format(Locale.ROOT,"%.0f FPS",s.displayHz):"— FPS","1∶1",s.cloudStats[0]+" GPU块",String.format(Locale.ROOT,"GPU %.1f MB",s.cloudStats[1]/1e6),"近区 "+s.cloudStats[3]+"/"+s.cloudStats[4]};
  float size=20,textWidth=0;for(String v:pieces){p.setTextSize(size);textWidth+=p.measureText(v);}float padding=36+16*(pieces.length-1);
  if(textWidth+padding>1480)size*=Math.max(0,1480-padding)/Math.max(1,textWidth);
  float w=padding;for(String v:pieces){p.setTextSize(size);w+=p.measureText(v);}
  float x=(1600-w)/2,y=s.modal()?900:812;box(x,y,w,52,0x70edf5fc,26);
  float tx=x+18;for(int i=0;i<pieces.length;i++){text(pieces[i],tx,y+34,size,i==3?TEAL:i==4?armColor(t.left,fresh):i==5?armColor(t.right,fresh):INK,1480);p.setTextSize(size);tx+=p.measureText(pieces[i])+16;}
  float alpha=speed.update(t,now,s.modal());if(alpha>0){int a=(int)(112*alpha);box(640,680,320,112,(a<<24)|0x102e41,24);String value=Double.isFinite(speed.value)?String.format(Locale.ROOT,"%.2f",speed.value):"—";text(value,665,760,76,((int)(255*alpha)<<24)|0xffffff,210);text("m/s",870,760,30,((int)(255*alpha)<<24)|0xffffff,80);text("指令速度",750,785,18,((int)(255*alpha)<<24)|0xffffff,150);}

  if(!s.modal()){box(330,880,940,118,0x70edf5fc,36);for(VrUiState.Rect r:(s.cloudMode?VrUiState.CLOUD_TOOLBAR:s.sceneBrowser?VrUiState.SCENE_TOOLBAR:VrUiState.TOOLBAR))button(r,s);controller(s,0);controller(s,1);}
  if(s.cloudClearConfirm){sheet(s.sceneDeleteAll?"确认清除所有场景缓存？":"确认删除当前场景缓存？",250,280,1100,400);int labelRow=0;for(String line:wrap(s.sceneDeleteLabel,1000,18)){if(labelRow>=2)break;text(line,300,385+labelRow++*24,18,TEAL,1000);}text("将停止当前下载，重新下载所需块；不会删除AIPC原始数据",300,440,22,INK,1000);for(VrUiState.Rect r:VrUiState.CLOUD_CONFIRM)button(r,s);}
  else if(s.scenePanel){
    sheet("场景 / 实时图传",250,65,1100,800);text(s.sceneServiceAddress,300,163,16,MUTED,710);
    for(VrUiState.Rect r:s.integratedChoices())if(r.id<VrUiState.SCENE_ITEM)button(r,s);
    c.save();c.clipRect(300,VrUiState.SCENE_TOP,1300,VrUiState.SCENE_BOTTOM);
    for(int i=0;i<s.sceneCatalogIds.length;i++){float rowY=VrUiState.SCENE_TOP+i*VrUiState.SCENE_ROW-s.sceneScroll;if(rowY+132<VrUiState.SCENE_TOP||rowY>VrUiState.SCENE_BOTTOM)continue;sceneRow(s,i,rowY);}
    c.restore();float viewport=VrUiState.SCENE_BOTTOM-VrUiState.SCENE_TOP;box(1316,VrUiState.SCENE_TOP,5,viewport,0x28537990,2);float thumb=Math.max(28,viewport*viewport/Math.max(viewport,s.sceneCatalogIds.length*VrUiState.SCENE_ROW));box(1316,VrUiState.SCENE_TOP+(viewport-thumb)*(s.sceneScrollMax()==0?0:s.sceneScroll/s.sceneScrollMax()),5,thumb,0x99537990,2);
    if(s.sceneCatalogIds.length==0)text("暂无场景，刷新以读取 AIPC 列表",340,390,26,MUTED,850);
    if(!s.cloudModeError.isEmpty())text(s.cloudModeError,300,846,16,0xffb52638,1000);
  }else if(s.capturePanel){
    sheet("视野直播",180,120,1240,720);CaptureConfig cfg=s.captureConfig;
    text(s.captureSummary,220,226,24,TEAL,1160);
    text(String.format(Locale.ROOT,"垂直视野 %.0f° · 边距 L%.0f%% / R%.0f%% / T%.0f%% / B%.0f%% · 中心 %.2f, %.2f",cfg.verticalFov,cfg.left*100,cfg.right*100,cfg.top*100,cfg.bottom*100,cfg.centerX,cfg.centerY),220,262,20,INK,1160);
    for(VrUiState.Rect r:VrUiState.CAPTURE_CHOICES)button(r,s);
    text("正前方光轴居中 · 边距对称生效",220,540,24,TEAL,1160);
    text(s.captureAddress+" · H.264 实时流",220,722,22,MUTED,1160);
    int row=0;for(String line:wrap(s.captureError,1160,18)){if(row++>=3)break;text(line,220,755+(row-1)*23,18,0xffb52638,1160);}
  }else if(s.logsOpen){
    sheet("运行日志",250,150,1100,690);String[] levels={"DEBUG","INFO","WARN","ERROR"};for(int i=0;i<4;i++)text(levels[i],290+i*120,282,18,logColor(levels[i]),112);
    String[] lines=s.logLines;
    int start=Math.max(0,lines.length-14-(int)s.logScroll);for(int i=0;i<14&&start+i<lines.length;i++){String v=lines[start+i];text(v,290,322+i*28,19,logColor(v),1020);}
    box(1320,300,5,398,0x28537990,2);float thumb=Math.max(24,398f*14/Math.max(14,lines.length));float progress=lines.length<=14?1:1-Math.min(1,s.logScroll/(lines.length-14));box(1320,300+progress*(398-thumb),5,thumb,0x99537990,2);
    for(VrUiState.Rect r:VrUiState.LOG_TOOLS)button(r,s);
  }else if(s.videoPanel){sheet("视频视窗",300,250,1000,560);for(VrUiState.Rect r:VrUiState.VIDEO_CHOICES)button(r,s);}
  else if(s.menuOpen){sheet("终端菜单",350,150,900,590);for(VrUiState.Rect r:(s.cloudMode?VrUiState.CLOUD_DIALOG:s.sceneBrowser?VrUiState.SCENE_DIALOG:VrUiState.DIALOG))button(r,s);}
  // Always visible above scene and every modal. This is a passive notice, never a hit target.
  if(s.captureStreaming){float nx=20,ny=25,nw=400;
    box(nx,ny,nw,58,0xd0102e41,20);circle(nx+27,ny+29,6,0xffff6262);text("直播中 · 菜单可取消",nx+45,ny+38,22,Color.WHITE,nw-65);}
  if(!s.sceneBrowser&&!s.integratedStatic&&s.rightCameraVisible){badge("右臂镜头",1130,590,300);if(d.cameras[4].received==0||now-d.cameras[4].received>2_000_000_000L)text("等待右臂视频",1150,705,22,Color.WHITE,260);}
  if(s.interactionLocked){String notice="侧键已按满 · 界面交互已锁定";int red=0xffb52e3d;float nw=660,nx=(1600-nw)/2,ny=24;box(nx,ny,nw,64,0x70edf5fc,22);outline(nx,ny,nw,64,red,22,2);p.setTextSize(26);text(notice,(1600-p.measureText(notice))/2,ny+42,26,red,nw-36);}
  if(s.captureRecording)text("● REC",s.modal()?1170:1150,s.modal()?63:790,22,0xffb52638,150);
 }
 void drawWorld(Bitmap bitmap,Dashboard d,VrUiState s,long now,boolean ignored){
  begin(bitmap);
  if(s.cloudMode){
    box(320,74,960,60,0x70eaf3fc,18);text("探路者 · 静态彩色点云",344,116,30,INK,880);
    List<String> rows=wrap(s.sceneSource+"\n"+s.cloudInfo+"\n"+s.cloudDetail+"\n"+s.sceneError,260,16);
    box(12,150,290,Math.max(210,70+rows.size()*23),0x90e6f1fa,24);text("点云连接状态",30,188,23,TEAL,260);int i=0;for(String row:rows)text(row,30,222+i++*23,16,INK,260);return;
  }
  if(s.sceneBrowser){
    box(320,74,960,60,0x70eaf3fc,18);text("探路者控制终端 · 有色场景",344,116,30,INK,880);
    box(12,150,282,310,0x70e6f1fa,24);text("场景浏览",30,190,26,TEAL,246);
    text(s.sceneSource,30,228,20,INK,246);text(s.sceneStatus,30,265,20,INK,246);
    text("顶点 "+s.sceneStats[2],30,304,20,INK,246);text("三角形 "+s.sceneStats[1],30,341,20,INK,246);
    String progress=s.sceneStats[5]>0&&s.sceneStats[4]<s.sceneStats[5]?"上传 "+Math.round(s.sceneStats[4]*100.0/s.sceneStats[5])+"%":"不发布机器人输入";
    text(progress,30,381,18,TEAL,246);
    int row=0;for(String line:wrap(s.sceneError,246,16)){if(row++>=2)break;text(line,30,416+(row-1)*20,16,0xffb52638,246);}
    return;
  }
  box(320,74,960,60,0x70eaf3fc,18);text("探路者控制终端",344,116,32,INK,660);icons(d,now);
  Dashboard.VideoInfo video=d.cameras[s.selectedCamera];
  if(s.videoMode!=0){VrUiState.Rect r=s.videoRect();outline(r.x-8,r.y-8,r.w+16,r.h+16,0xbbecf7ff,22,2);
    if(video.received==0||now-video.received>2_000_000_000L){box(r.x,r.y,r.w,r.h,0x75dfebf5,18);text("等待相机视频",r.x+30,r.y+r.h/2,30,MUTED,r.w-60);}
    badge(CameraLayout.label(s.selectedCamera)+" "+(Double.isFinite(video.fps)?String.format(Locale.ROOT,"%.0f FPS",video.fps):"— FPS"),r.x+6,r.y+6,r.w-12);
    badge("视频延时 "+latency(video.latency)+"   "+video.status,r.x+6,r.y+r.h-40,r.w-12);
  }
  for(int row=0;row<5;row++){int i=row==4?5:row;int y=150+170*row;outline(1306,y,282,168,s.selectedCamera==i?TEAL:0xbbecf7ff,20,s.selectedCamera==i?4:2);Dashboard.VideoInfo v=d.cameras[i];if(v.received==0||now-v.received>2_000_000_000L)box(1314,y+8,266,150,0xff1c3846,10);badge(CameraLayout.label(i),1320,y+12,250);}
  // Minimap plate and frame are rendered together at the left native world quad.
  StringBuilder errors=new StringBuilder();if(!d.warning.isEmpty())errors.append(d.warning).append('\n');if(!d.telemetryError.isEmpty())errors.append(d.telemetryError).append('\n');if(!s.cloudModeError.isEmpty())errors.append(s.cloudModeError).append("\n");String remote=d.telemetry.errors(now);if(!remote.isEmpty())errors.append(remote);
  List<String> errorLines=wrap(errors.toString().trim(),246,16);
  float h=485+errorLines.size()*22+wrap(s.cloudModeStatus+"\n"+s.cloudCacheStatus,246,16).size()*22;box(12,150,282,h,0x70e6f1fa,24);
  text("连接状态",30,190,28,TEAL,246);text(d.simulation?"本地虚拟演示":d.inputConnected?"AIPC 已连接":"AIPC 未连接",30,228,23,d.inputConnected||d.simulation?TEAL:0xffa42a3b,246);
  float y=253;for(String line:errorLines){text(line,30,y,16,0xffb52638,246);y+=22;}
  text("连接 IP",30,y+8,18,MUTED,246);text(d.targetAddress,30,y+36,22,INK,246);y+=66;
  text("VR 状态发送",30,y,18,MUTED,246);y+=32;
  text((Double.isFinite(d.observationActualHz)?String.format(Locale.ROOT,"%.1f Hz",d.observationActualHz):"— Hz"),30,y,27,INK,140);text(Double.isFinite(d.observationBytesPerSecond)?String.format(Locale.ROOT,"%.1f kB/s",d.observationBytesPerSecond/1000):"— kB/s",158,y,18,MUTED,118);y+=28;
  text("累计 "+d.observationSent+" 帧    丢失 — 帧",30,y,18,INK,246);y+=27;text("总发送量 "+String.format(Locale.ROOT,"%.2f MB",d.observationTotalBytes/1e6),30,y,18,MUTED,246);y+=35;
  String[] rows={"车端 RTT  "+latency(d.carRtt),"控制帧龄  "+latency(d.controlAge),"点云更新  "+age(now,d.cloudReceived),"状态反馈  "+age(now,d.stateReceived),s.vehiclePoseFresh?"车辆位姿有效":"原点 / 待有效反馈"};for(String row:rows){text(row,30,y,18,MUTED,246);y+=29;}for(String row:wrap(s.cloudModeStatus+"\n"+s.cloudCacheStatus,246,16)){text(row,30,y,16,TEAL,246);y+=22;}
 }
 void drawGrippers(Bitmap b,Telemetry t,long now){begin(b);if(!t.fresh(now))return;for(int i=0;i<2;i++){Telemetry.Arm arm=i==0?t.left:t.right;if(arm.links==null)continue;float x=i*256;box(x,0,256,128,0xb0102e41,18);text((i==0?"左":"右")+"夹爪 "+(Float.isFinite(arm.open)?Math.round(arm.open*100)+"%":"—"),x+10,78,38,Color.WHITE,236);}}
 private void sceneRow(VrUiState s,int i,float y){
  SceneCacheInfo info=s.sceneCaches.get(s.sceneCatalogIds[i]);boolean done=info!=null&&info.complete;int color=done?0xff239b60:TEAL;
  box(300,y,1000,132,0x70edf5fc,20);if(s.hover==VrUiState.SCENE_ITEM+i)outline(300,y,1000,132,TEAL,20,3);
  String label=i<s.sceneCatalogLabels.length?s.sceneCatalogLabels[i]:s.sceneCatalogIds[i];List<String> lines=wrap(label,730,25);for(int j=0;j<Math.min(2,lines.size());j++)text(lines.get(j),324,y+36+j*31,25,INK,730);
  text(s.sceneCatalogIds[i],324,y+112,14,MUTED,730);float cx=1215,cy=y+49;
  if(done){line(cx-22,cy,cx-6,cy+16,color,6);line(cx-6,cy+16,cx+24,cy-20,color,6);text(String.format(Locale.ROOT,"%.1f MiB",info.bytes/1048576.0),cx-63,y+111,18,color,126);}
  else{double value=info==null?0:info.fraction;outline(cx-35,cy-35,70,70,0x30537990,35,4);for(int k=0;k<(int)(value*72);k++){double a=-Math.PI/2+k*Math.PI*2/72,b=a+Math.PI*2/72;line(cx+(float)Math.cos(a)*35,cy+(float)Math.sin(a)*35,cx+(float)Math.cos(b)*35,cy+(float)Math.sin(b)*35,color,4);}String percent=Math.min(99,(int)(value*100))+"%";p.setTextSize(22);text(percent,cx-p.measureText(percent)/2,cy+8,22,color,100);text(String.format(Locale.ROOT,"%.0f KiB/s",info==null?0:info.bytesPerSecond/1024),cx-70,y+111,17,MUTED,140);}
 }
 private void controller(VrUiState s,int side){
  float x=side==0?20:1290,y=864;box(x,y,290,136,0x70e6f1fa,24);
  boolean active=(s.activeHands&(1<<side))!=0,tracked=(s.tracking&(2<<side))!=0;outline(x,y,290,136,!active?0xbbecf7ff:tracked?0xff239b60:0xffd34b52,24,2);
  text(side==0?"左手":"右手",x+12,y+29,18,TEAL,45);
  int[] bits=side==0?new int[]{4,8}:new int[]{1,2};String[] keys=side==0?new String[]{"X","Y"}:new String[]{"A","B"};
  for(int i=0;i<2;i++){boolean down=(s.faceButtons.pressed&bits[i])!=0;float cx=x+75+i*35;circle(cx,y+22,15,down?TEAL:0x65f4fbff);text(keys[i],cx-7,y+29,18,down?Color.WHITE:INK,25);}
  float grip=side==0?s.raw.leftGrip:s.raw.rightGrip,trigger=side==0?s.raw.leftTrigger:s.raw.rightTrigger;
  gauge("侧键",grip,(s.raw.valid&(1<<side))!=0,x+12,y+53);gauge("扳机",trigger,(s.raw.valid&(4<<side))!=0,x+12,y+91);
  float cx=x+230,cy=y+56;outline(cx-48,cy-48,96,96,0x80537f94,48,1.5f);line(cx-46,cy,cx+46,cy,0x334b7e91,1);line(cx,cy-46,cx,cy+46,0x334b7e91,1);
  float a=s.axes[side*2],b=s.axes[side*2+1];double norm=Math.max(1,Math.hypot(a,b));circle(cx+(float)(a/norm*32),cy-(float)(b/norm*32),12,(s.stickButtons.pressed&(1<<side))!=0?0xffe58b31:TEAL);text(String.format(Locale.ROOT,"%.2f, %.2f",a,b),cx-48,y+127,13,MUTED,100);
 }
 private void gauge(String name,float value,boolean valid,float x,float y){text(name,x,y,17,INK,80);text(valid?Math.round(value*100)+"%":"—",x+110,y,16,MUTED,45);box(x,y+5,150,8,0x24193e54,4);if(valid)box(x,y+5,150*Math.max(0,Math.min(1,value)),8,TEAL,4);}
 private void icons(Dashboard d,long now){for(int i=0;i<6;i++)circle(1010+(i%3)*8,100+(i/3)*8,2.5f,TEAL);for(int i=0;i<3;i++)box(1060+i*9,115-i*6,5,7+i*6,d.wifiLevel>i?TEAL:0x44537f94,2);outline(1120,94,44,24,TEAL,4,1.5f);box(1166,101,3,10,TEAL,1);if(d.battery>=0)box(1124,98,36*d.battery/100f,16,d.battery<=20?0xffb33243:TEAL,2);text(d.battery>=0?d.battery+"%":"—",1180,115,21,TEAL,80);}
 private void badge(String value,float x,float y,float maxWidth){p.setTextSize(16);float w=Math.min(maxWidth,p.measureText(value)+16);box(x,y,w,32,0xb0000000,6);text(value,x+8,y+23,16,Color.WHITE,w-16);}
 private void sheet(String title,float x,float y,float w,float h){box(x,y,w,h,0x85e6f1fa,32);text(title,x+40,y+55,36,INK,w-80);}
 private static int logColor(String s){return s.contains("ERROR")?0xffb1273c:s.contains("WARN")?0xff925100:s.contains("DEBUG")?0xff52677c:0xff006575;}
 private List<String> wrap(String text,float width,float size){List<String> out=new ArrayList<>();p.setTextSize(size);for(String paragraph:text.split("\n")){if(paragraph.isEmpty())continue;int start=0;while(start<paragraph.length()){int n=Math.max(1,p.breakText(paragraph.substring(start),true,width,null));out.add(paragraph.substring(start,start+n));start+=n;}}return out;}
 private void box(float x,float y,float w,float h,int color,float radius){p.setStyle(Paint.Style.FILL);p.setColor(color);c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);}
 private void outline(float x,float y,float w,float h,int color,float radius,float stroke){p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(stroke);p.setColor(color);c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);p.setStyle(Paint.Style.FILL);}
 private void circle(float x,float y,float radius,int color){p.setColor(color);p.setStyle(Paint.Style.FILL);c.drawCircle(x,y,radius,p);}
 private void line(float x,float y,float a,float b,int color,float width){p.setColor(color);p.setStrokeWidth(width);c.drawLine(x,y,a,b,p);}
 private void text(String value,float x,float y,float size,int color,float width){if(value==null)value="—";p.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));p.setTextSize(size);p.setColor(color);p.setStyle(Paint.Style.FILL);int n=p.breakText(value,true,width,null);if(n<value.length())value=value.substring(0,Math.max(0,n-1))+"…";c.drawText(value,x,y,p);}
 private static String age(long now,long t){return t==0?"—":String.format(Locale.ROOT,"%.0f ms前",(now-t)/1e6);}
  private void button(VrUiState.Rect r, VrUiState s) {
    boolean focus = s.hover == r.id || (s.modal() && s.selected == r.id);
    boolean selected = (r.id >= 1 && r.id <= 3 && s.videoMode == r.id - 1)
        || (r.id == 4 && s.mapVisible) || (r.id == VrUiState.VIEW && s.followView)
        || r.id == VrUiState.SOURCE_RGB && !s.depthVideo
        || r.id == VrUiState.SOURCE_DEPTH && s.depthVideo
        || r.id==VrUiState.SCENE_TABLE&&s.sceneView==1 || r.id==VrUiState.SCENE_FULL&&s.sceneView==2;
    boolean disabled = s.interactionLocked || r.id == VrUiState.LIVE && !s.captureStreaming;
    if(disabled)focus=false;
    boolean danger = r.id == VrUiState.EXIT || r.id == VrUiState.LIVE && s.captureStreaming;
    int fill = disabled ? 0x35dfedf6 : focus ? TEAL : selected ? 0xa6c9e9ed : danger ? 0xa6f5dbd1 : 0x85dfedf6;
    box(r.x, r.y, r.w, r.h, fill, 22);
    String label;
    switch (r.id) {
      case VrUiState.CLOUD_START:label=s.cloudMode?"重新连接":"分块点云服务";break;
      case VrUiState.CLOUD_NEXT:label="切换场景 / catalog";break;
      case VrUiState.CLOUD_LINK:label="切换 Wi-Fi / 中继";break;
      case VrUiState.CLOUD_CLEAR:label="清缓存…";break;
      case VrUiState.CLOUD_CLEAR_YES:label="确认清除";break;
      case VrUiState.CLOUD_CLEAR_NO:label="取消";break;
      case VrUiState.CLOUD_FLOOR_UP:label="地面Y +0.1m";break;
      case VrUiState.CLOUD_FLOOR_DOWN:label="地面Y −0.1m";break;
      
      case VrUiState.SCENE_TABLE:label="沙盘";break;
      case VrUiState.SCENE_FULL:label="1∶1";break;
      case VrUiState.SCENE_RESET:label="复位";break;
      case VrUiState.SCENE_POINTS:label=s.scenePointMode?"显示有色表面":"显示顶点点云";break;
      case VrUiState.SCENE_LOCAL:label="内置真实扫描";break;
      case VrUiState.SCENE_REMOTE:label="从 AIPC 读取";break;
      case VrUiState.SCENE_PANEL:label="场景 / 实时";break;
      case VrUiState.RIGHT_CAMERA:label=s.rightCameraVisible?"右臂镜头：开":"右臂镜头：关";break;
      case VrUiState.VIDEO_FISHEYE:label="鱼眼镜头";break;
      case VrUiState.MODE_LIVE:label=s.integratedStatic?"实时模式":"实时模式（当前）";break;
      case VrUiState.MODE_SCENE:label=s.integratedStatic?"场景模式（当前）":"场景模式";break;
      case VrUiState.SCENE_CATALOG:label="刷新列表";break;
      case VrUiState.MODE_TOGGLE:label=s.integratedStatic?"实时":"场景";break;
      case VrUiState.SCENE_PREV:label="上一页";break;
      case VrUiState.SCENE_NEXT:label="下一页";break;
      case VrUiState.SCENE_CLEAR:label="删除此场景缓存";break;
      case VrUiState.SCENE_CLEAR_ALL:label="清除全部缓存";break;
      case VrUiState.VIDEO_RGB:label="RGB";break;
      case VrUiState.VIDEO_DEPTH:label="深度图";break;
      case VrUiState.VIDEO_CAM3:label="摄像头3";break;
      case VrUiState.VIDEO_CAM4:label="摄像头4";break;
      case VrUiState.CAPTURE:label="视野直播";break;
      case VrUiState.RECORD:label="";break;
      case VrUiState.LIVE:label=s.captureStreaming?"取消直播":"直播未开启";break;
      case VrUiState.PROFILE:label="画幅 "+s.captureConfig.width+"×"+s.captureConfig.height;break;
      case VrUiState.FOV_MINUS:label="视野 −5°";break;
      case VrUiState.FOV_PLUS:label="视野 +5°";break;
      case VrUiState.MARGIN_MINUS:label="边距 −2%";break;
      case VrUiState.MARGIN_PLUS:label="边距 +2%";break;
      case VrUiState.CENTER_LEFT:label="取景 ←";break;
      case VrUiState.CENTER_RIGHT:label="取景 →";break;
      case VrUiState.CENTER_UP:label="取景 ↑";break;
      case VrUiState.CENTER_DOWN:label="取景 ↓";break;
      case VrUiState.EYE:label=s.captureConfig.eye==0?"左眼视野":"右眼视野";break;
      case VrUiState.CAPTURE_RESET:label="恢复取景默认";break;
      case 1:
        label = "关闭视频";
        break;
      case 2:
        label = "标准视窗";
        break;
      case 3:
        label = "宽幅视窗";
        break;
      case 4:
        label = s.mapVisible?"小地图：开":"小地图：关";
        break;
      case 5:
        label = "菜单";
        break;
      case 6:
        label = "返回";
        break;
      case 7:
        label = s.menuOpen ? "退出到设置" : "退出";
        break;
      case 12:
        label = "日志";
        break;
      case 13:
        label = "视频";
        break;
      case 14:
        label = "刷新";
        break;
      case 15:
        label = "上一页";
        break;
      case 16:
        label = "下一页";
        break;
      case 18:
        label = "RGB 相机";
        break;
      case 19:
        label = "伪彩深度";
        break;
      default:
        label = s.followView ? "跟随" : "旁观";
    }
    float size = r.w < 160 ? 27 : 29;
    p.setTextSize(size);
    if(r.id>=VrUiState.SCENE_ITEM&&r.id<VrUiState.SCENE_ITEM+s.sceneCatalogIds.length){int at=r.id-VrUiState.SCENE_ITEM;label=at<s.sceneCatalogLabels.length?s.sceneCatalogLabels[at]:"";}
    if(p.measureText(label)>r.w-32){size=Math.max(17,size*(r.w-32)/p.measureText(label));p.setTextSize(size);while(label.length()>1&&p.measureText(label)>r.w-32)label=label.substring(0,label.length()-1);}
    text(label, r.x + (r.w - p.measureText(label)) / 2, r.y + r.h / 2 + 10, size,
        focus        ? Color.WHITE
            : danger ? 0xffa54b36
                     : INK,
        r.w - 16);
  }
}
