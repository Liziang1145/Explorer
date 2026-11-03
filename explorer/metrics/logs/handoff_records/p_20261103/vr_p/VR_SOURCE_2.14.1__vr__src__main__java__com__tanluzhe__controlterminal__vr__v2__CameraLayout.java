package com.tanluzhe.controlterminal.vr.v2;
/** Shared world-panel pixel layout. Includes the temporary fisheye channel. */
public final class CameraLayout {
 public static final String[] KINDS={"camera","depth","camera3","camera4","camera1","camera2"};
 public static final int THUMB_X=1314,THUMB_Y=158,THUMB_STEP=170,THUMB_W=266,THUMB_H=150;
 public static final int MAP_X=-280,MAP_Y=150,MAP_W=266,MAP_H=230;
 public static String streamPath(String kind,String quality,String id){if(!java.util.Arrays.asList(KINDS).contains(kind)||!java.util.Arrays.asList("auto","native","economy","720p30","720p15","540p15","360p15","240p15").contains(quality)||!id.matches("[0-9a-f]{32}"))throw new IllegalArgumentException("无效媒体通道/档位/客户端ID");return "/stream/"+kind+"?quality="+quality+"&client_id="+id;}
 public static String origin(String text){try{java.net.URI u=new java.net.URI(text);if(!"http".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null||u.getQuery()!=null||u.getFragment()!=null||!java.util.Arrays.asList("","/").contains(u.getPath())||u.getPort()==0||u.getPort()>65535)throw new IllegalArgumentException();return text.endsWith("/")?text.substring(0,text.length()-1):text;}catch(Exception e){throw new IllegalArgumentException("媒体地址应为 http://IP:8096");}}
 public static int hit(float x,float y){if(!Float.isFinite(x)||!Float.isFinite(y)||x<THUMB_X||x>THUMB_X+THUMB_W)return -1;for(int i=0;i<5;i++)if(y>=THUMB_Y+i*THUMB_STEP&&y<=THUMB_Y+i*THUMB_STEP+THUMB_H)return i==4?5:i;return -1;}
 public static boolean interactionLocked(Telemetry t,long now){return t.fresh(now)&&!t.stopped&&(enabled(t.left)||enabled(t.right));}
 private static boolean enabled(Telemetry.Arm a){return a.state.equals("vr_follow")||a.state.equals("following");}
 public static boolean rightEnabled(Telemetry t,long now){return t.fresh(now)&&!t.stopped&&(t.right.state.equals("vr_follow")||t.right.state.equals("following"));}
 public static String label(int i){return i==0?"深度相机 RGB":i==1?"深度相机深度图":i==2?"摄像头 3":i==3?"摄像头 4":i==4?"右臂摄像头 1":"鱼眼摄像头 2";}
}
