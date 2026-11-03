"""Host checks for real camera layout/policy/URLs and native world-plane picking, no devices."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1];out=root/'vr/build/camera-layout-test';out.mkdir(parents=True,exist_ok=True);src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2';java=Path(r'C:/Program Files/Android/Android Studio/jbr/bin')
code=r"""import com.tanluzhe.controlterminal.vr.v2.*;import java.util.*;
public class CameraLayoutTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}interface Fn{void run();}static void reject(Fn f){boolean rejected=false;try{f.run();}catch(IllegalArgumentException expected){rejected=true;}check(rejected);}
 static Telemetry telemetry(long now,String state,boolean stopped){float[][] links=new float[7][3];for(int i=0;i<7;i++){links[i][0]=i;links[i][1]=i*4;links[i][2]=i*10;}return new Telemetry(now,"arm","arm","",stopped,0,0,0,Telemetry.Arm.unknown(),new Telemetry.Arm(state,"feedback","",links,null,.5f));}
 public static void main(String[] args){
  check(CameraLayout.KINDS.length==6&&Arrays.asList(CameraLayout.KINDS).contains("camera2"));check(new HashSet<>(Arrays.asList(CameraLayout.KINDS)).size()==6);
  String id="0123456789abcdef0123456789abcdef";for(String kind:CameraLayout.KINDS){String path=CameraLayout.streamPath(kind,"720p30",id);check(path.equals("/stream/"+kind+"?quality=720p30&client_id="+id));check(!path.contains("token"));}
  reject(()->CameraLayout.streamPath("camera6","auto",id));reject(()->CameraLayout.streamPath("camera1","bad",id));reject(()->CameraLayout.streamPath("camera1","auto","abc&token=x"));
  check(CameraLayout.origin("http://192.168.137.2:8096/").equals("http://192.168.137.2:8096"));for(String url:new String[]{"https://192.168.137.2:8096","http://user:pw@192.168.137.2:8096","http://192.168.137.2:8096?token=1","http://192.168.137.2:0","http://192.168.137.2:8096/path"})reject(()->CameraLayout.origin(url));
  VrUiState ui=new VrUiState();for(int i=0;i<4;i++){ui.presentation(VrUiState.VIDEO_RGB+i);check(ui.selectedCamera==i&&ui.videoMode==2&&ui.depthVideo==(i==1));check(CameraLayout.hit(1400,200+i*170)==i);check(CameraLayout.hit(1400,320+i*170)==-1||i==3);}check(CameraLayout.hit(Float.NaN,200)==-1);check(CameraLayout.MAP_X+CameraLayout.MAP_W<12&&CameraLayout.MAP_Y==150);
  ui.presentation(VrUiState.VIDEO_FISHEYE);check(ui.selectedCamera==5);check(CameraLayout.hit(1400,880)==5);ui.presentation(VrUiState.RIGHT_CAMERA);check(!ui.rightCameraVisible);ui.interactionLocked=true;int mode=ui.videoMode;ui.presentation(VrUiState.VIDEO_OFF);check(ui.videoMode==mode&&ui.hit(.25f,.95f)==0&&ui.localButtonAction(16)==0);ui.logsOpen=true;ui.navigate(1,1000000000L);check(ui.logScroll==0);ui.interactionLocked=false;
  long now=1000000000L;check(CameraLayout.interactionLocked(telemetry(now,"vr_follow",false),now));check(!CameraLayout.interactionLocked(telemetry(now,"idle",false),now));for(String state:new String[]{"following","vr_follow"})check(CameraLayout.rightEnabled(telemetry(now,state,false),now+100));for(String state:new String[]{"idle","moving","unknown"})check(!CameraLayout.rightEnabled(telemetry(now,state,false),now+100));check(!CameraLayout.rightEnabled(telemetry(now,"vr_follow",true),now+100));check(!CameraLayout.rightEnabled(telemetry(now,"vr_follow",false),now+2000000000L));
  ArmGeometry arm=new ArmGeometry();arm.sample(telemetry(now,"vr_follow",false),now);float[] anchor=arm.rightCameraAnchor();check(anchor!=null&&Math.abs(anchor[0]-.185f)<.0001&&Math.abs(anchor[1]-1.12f)<.0001);arm.sample(telemetry(now,"vr_follow",false),now+3000000000L);check(arm.rightCameraAnchor()==null);
  System.out.println("PASS: "+checks+" camera source/URL/isolation, UI selection, left minimap, authoritative right-arm enable and spatial anchor checks.");
 }
}
"""
(out/'CameraLayoutTest.java').write_text(code,encoding='utf8')
cp=root/'vr/build/v2-contract-tests'
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(cp),'-d',str(out),str(src/'CameraLayout.java'),str(src/'ArmGeometry.java'),str(src/'VrUiState.java'),str(out/'CameraLayoutTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(out)+';'+str(cp),'CameraLayoutTest'],check=True)
cpp=r"""
#include <cassert>
#include <random>
#include <iostream>
#include "camera_ui_math.h"
int main(){std::mt19937 rng(31);std::uniform_real_distribution<float> offset(-.2f,.2f);int checks=0;
 for(int k=0;k<5;k++)for(int i=0;i<5000;i++){
  float px=1320+(i%250),py=165+k*170+(i%130),t=1.5f+std::abs(offset(rng)),dx=offset(rng),dy=offset(rng);
  float x=(px/1600-.5f)*6.6f+dx*t,y=(.5f-py/1000)*4.125f+dy*t;
  auto hit=cameraPanelHit(x,y,t,dx,dy,1);assert(hit.index==(k==4?5:k)&&std::abs(hit.distance-t)<.0001f);checks++;
 }
 assert(cameraPanelHit(0,0,2,0,0,-1).index==-1);assert(cameraPanelHit(0,0,2,0,0,0).index==-1);assert(armCameraWidth(.5f,true)>armCameraWidth(.5f,false));assert(armCameraWidth(20,true)<=1.2f);
 std::cout<<"PASS: "<<checks+4<<" native controller-ray/world-panel hit and distance-scaled right-arm window checks.\n";
}
"""
(out/'pick.cpp').write_text(cpp,encoding='utf8');vs=Path(r'C:/Program Files/Microsoft Visual Studio/18/Insiders/Common7/Tools/VsDevCmd.bat')
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /std:c++17 /EHsc /I"{root/"vr/src/main/cpp"}" pick.cpp /Fe:pick.exe && pick.exe',shell=True,cwd=out,check=True)

