"""Regression: physical full-grip UI lock, single-owner ray selection and reconnect policy."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1];src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2';out=root/'vr/build/ui-recovery-tests';out.mkdir(parents=True,exist_ok=True)
java=Path(r'C:/Program Files/Android/Android Studio/jbr/bin');cp=root/'vr/build/v2-contract-tests'
code=r'''package com.tanluzhe.controlterminal.vr.v2;
public class UiRecoveryTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 static float[] ray(float u,float v,int rear){return new float[]{-1,-1,u,v,0,0,0,0,63,0,0,-1,rear};}
 static VrUiState ready(float[] p){VrUiState ui=new VrUiState();ui.pointerAction(p,true);return ui;}
 public static void main(String[] args){
  float[] p=ray(1.1f,.5f,2);check(!VrUiState.gripLocksUi(p,true));
  for(int side=0;side<2;side++)for(float value:new float[]{0,.5f,.95f,.999f,1f,Float.NaN,Float.POSITIVE_INFINITY,1.1f}){
   p[6]=p[7]=0;p[6+side]=value;check(VrUiState.gripLocksUi(p,true)==(value==1));check(!VrUiState.gripLocksUi(p,false));float mask=p[8];p[8]=0;check(!VrUiState.gripLocksUi(p,true));p[8]=mask;
  }
  p=ray(1.1f,.5f,3);VrUiState ui=ready(p);p[7]=1;p[5]=1;check(ui.pointerAction(p,true)==0&&ui.interactionLocked);check(ui.localButtonAction(16)==0);ui.presentation(VrUiState.VIDEO_OFF);check(ui.videoMode==2);
  p[7]=0;check(ui.pointerAction(p,true)==0&&!ui.interactionLocked);p[5]=0;ui.pointerAction(p,true);p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_CAM4);
  p=ray(400/1600f,940/1000f,2);ui=ready(p);p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_PANEL);check(ui.selectedCamera==0);check(ui.occludes(p[2],p[3]));
  // BAR gaps still consume the front surface and never select a rear thumbnail.
  p=ray(495/1600f,940/1000f,3);ui=ready(p);p[5]=1;check(ui.pointerAction(p,true)==0);check(ui.occludes(p[2],p[3]));
  p=ray(1.05f,.3f,5);ui=ready(p);p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_FISHEYE);check(ui.pointerAction(p,true)==0);
  p=ray(.9f,.2f,3);ui=ready(p);ui.menuOpen=true;p[5]=1;check(ui.pointerAction(p,true)==0);ui.menuOpen=false;check(ui.pointerAction(p,true)==0);p[5]=0;ui.pointerAction(p,true);p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_CAM4);
  // Either grip locks both hands, even on the same frame as a rear trigger edge.
  for(int side=0;side<2;side++){p=ray(1.1f,.3f,2);ui=ready(p);p[6+side]=1;p[5]=1;check(ui.pointerAction(p,true)==0);}
  p=ray(1.1f,.3f,1);ui=ready(p);p[0]=1.1f;p[1]=.4f;p[11]=2;p[4]=p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_DEPTH);
  p=ray(1.1f,.3f,1);ui=ready(p);p[0]=400/1600f;p[1]=940/1000f;p[11]=2;p[4]=p[5]=1;check(ui.pointerAction(p,true)==VrUiState.VIDEO_PANEL);
  VideoReconnect reconnect=new VideoReconnect();int[] delays={1000,2000,4000,8000,8000,8000};for(int delay:delays)check(reconnect.nextDelayMillis()==delay);reconnect.recovered();check(reconnect.nextDelayMillis()==1000);
  for(int status:new int[]{200,400,401,403,404,408,409,429,500,502,503,504})check(VideoReconnect.authorizationFailure(status)==(status==401||status==403));
  System.out.println("PASS: "+checks+" full-grip lock, release edges, front BAR/modal occlusion, single action and bounded reconnect checks");
 }
}'''
(out/'UiRecoveryTest.java').write_text(code,encoding='utf8')
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(cp),'-d',str(out),str(src/'VrUiState.java'),str(src/'VideoReconnect.java'),str(out/'UiRecoveryTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(out)+';'+str(cp),'com.tanluzhe.controlterminal.vr.v2.UiRecoveryTest'],check=True)
