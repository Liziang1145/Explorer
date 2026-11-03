"""Execute the production native camera functions on the host, without an XR device."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
source = (root / 'vr/src/main/cpp/terminal_v2.cpp').read_text(encoding='utf-8')
functions = source[source.index('using Mat ='):source.index('Mat projection(')]
vehicle = source[source.index('std::vector<float> vehicleLines()'):source.index('int64_t mono()')]
out = root / 'vr/build/view-math-test'
out.mkdir(parents=True, exist_ok=True)
test = r'''
#include <array>
#include <cmath>
#include <cassert>
#include <iostream>
#include <vector>
#include <fstream>
struct XrVector3f {float x,y,z;};
struct XrQuaternionf {float x,y,z,w;};
struct XrPosef {XrQuaternionf orientation;XrVector3f position;};
'''+functions+vehicle+r'''
int checks=0;
void near(float a,float b){assert(std::abs(a-b)<0.00005f);checks++;}
int main(){
 for(int n=0;n<40;n++){
  Mat stage=planar(3,.2f,-2,n*.13f);
  Mat carWorld=multiply(stage,planar(n*.1f,0,-n*.2f,n*.03f));
  Mat head=planar(1+n*.04f,1.7f,-.5f,n*.12f),original=head;
  Mat rig=followRig(stage,carWorld,head);
  Mat centered=multiply(rig,head);
  for(int k=0;k<3;k++)near(centered[12+k],carWorld[12+k]+(k==1?1.6f:0));
  Mat inv=multiply(rigidInverse(rig),rig);
  for(int k=0;k<16;k++)near(inv[k],identity()[k]);
  Mat moved=head;moved[12]+=.8f;moved[13]-=.4f;moved[14]+=.5f;
  Mat centered2=multiply(followRig(stage,carWorld,moved),moved);
  for(int k=0;k<16;k++)near(centered2[k],centered[k]);
  Mat left=head,right=head;
  // Eye displacement follows head orientation, preserving physical stereo baseline.
  for(int k=0;k<3;k++){left[12+k]-=head[k]*.032f;right[12+k]+=head[k]*.032f;}
  left=multiply(rig,left);right=multiply(rig,right);
  float distance=0;
  for(int k=0;k<3;k++){
   distance+=(left[12+k]-right[12+k])*(left[12+k]-right[12+k]);
   near((left[12+k]+right[12+k])*.5f,centered[12+k]);
  }
  near(std::sqrt(distance),.064f);
  for(int k=0;k<16;k++)near(head[k],original[k]);
 }
 auto car=vehicleLines();assert(car.size()%14==0 && car.size()>1000);
 std::ofstream("vehicle-lines.bin",std::ios::binary).write(reinterpret_cast<const char*>(car.data()),car.size()*sizeof(float));
 std::cout<<"PASS: "<<checks<<" native follow, rigid inverse, locked translation, IPD and untouched input checks; production vehicle exported\n";
}
'''
(out / 'view_math.cpp').write_text(test, encoding='utf-8')
vs = Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
assert vs.is_file(), 'Visual Studio C++ host tools required'
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /std:c++17 /EHsc view_math.cpp /Fe:view_math.exe && view_math.exe',
               shell=True, cwd=out, check=True)
