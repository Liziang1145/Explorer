"""Execute the production GPU uploader/drawer in real ANGLE GLES, without a device/emulator."""
from pathlib import Path
import subprocess,re,os
from PIL import Image
root=Path(__file__).resolve().parents[1];out=root/'vr/build/colored-scene-test'
native=(root/'vr/src/main/cpp/terminal_v2.cpp').read_text(encoding='utf8')
shaders='\n'.join('const char* '+name+'=R"('+re.search(r'const char\* '+name+r'\s*=\s*R"\((.*?)\)";',native,re.S)[1]+')";' for name in ['sceneVertex','sceneFragment'])
code=r'''
#define NOMINMAX
#include <windows.h>
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>
#include <array>
using GLuint=unsigned int;using GLenum=unsigned int;using GLint=int;using GLsizei=int;using GLboolean=unsigned char;
constexpr GLenum GL_ARRAY_BUFFER=0x8892,GL_ELEMENT_ARRAY_BUFFER=0x8893,GL_STATIC_DRAW=0x88e4,GL_NO_ERROR=0,GL_CULL_FACE=0xb44,GL_DEPTH_TEST=0xb71,GL_BLEND=0xbe2,GL_FLOAT=0x1406,GL_POINTS=0,GL_TRIANGLES=4,GL_UNSIGNED_INT=0x1405;
constexpr GLboolean GL_TRUE=1,GL_FALSE=0;
#define FN(ret,name,...) using F_##name=ret(*)(__VA_ARGS__);F_##name name;
FN(void,glDeleteBuffers,GLsizei,const GLuint*) FN(void,glGenBuffers,GLsizei,GLuint*)
FN(void,glBindBuffer,GLenum,GLuint) FN(void,glBufferData,GLenum,ptrdiff_t,const void*,GLenum)
FN(void,glBufferSubData,GLenum,ptrdiff_t,ptrdiff_t,const void*) FN(GLenum,glGetError)
FN(GLboolean,glIsEnabled,GLenum) FN(void,glDisable,GLenum) FN(void,glEnable,GLenum) FN(void,glDepthMask,GLboolean)
FN(void,glUseProgram,GLuint) FN(void,glUniformMatrix4fv,GLint,GLsizei,GLboolean,const float*) FN(GLint,glGetUniformLocation,GLuint,const char*) FN(void,glUniform1i,GLint,GLint)
FN(void,glEnableVertexAttribArray,GLuint) FN(void,glVertexAttribPointer,GLuint,GLint,GLenum,GLboolean,GLsizei,const void*) FN(void,glDrawArrays,GLenum,GLint,GLsizei) FN(void,glDrawElements,GLenum,GLsizei,GLenum,const void*)
FN(void*,eglGetDisplay,void*) FN(unsigned,eglInitialize,void*,int*,int*) FN(unsigned,eglChooseConfig,void*,const int*,void**,int,int*)
FN(void*,eglCreateContext,void*,void*,void*,const int*) FN(void*,eglCreatePbufferSurface,void*,void*,const int*) FN(unsigned,eglMakeCurrent,void*,void*,void*,void*)
FN(unsigned,eglDestroyContext,void*,void*) FN(unsigned,eglDestroySurface,void*,void*) FN(unsigned,eglTerminate,void*)
FN(GLuint,glCreateShader,GLenum) FN(void,glShaderSource,GLuint,GLsizei,const char* const*,const GLint*) FN(void,glCompileShader,GLuint) FN(void,glGetShaderiv,GLuint,GLenum,GLint*) FN(void,glGetShaderInfoLog,GLuint,GLsizei,GLsizei*,char*)
FN(GLuint,glCreateProgram) FN(void,glAttachShader,GLuint,GLuint) FN(void,glLinkProgram,GLuint) FN(void,glGetProgramiv,GLuint,GLenum,GLint*) FN(void,glDeleteProgram,GLuint)
FN(void,glGenVertexArrays,GLsizei,GLuint*) FN(void,glBindVertexArray,GLuint) FN(void,glViewport,GLint,GLint,GLsizei,GLsizei) FN(void,glClearColor,float,float,float,float) FN(void,glClear,GLenum) FN(void,glFinish) FN(void,glReadPixels,GLint,GLint,GLsizei,GLsizei,GLenum,GLenum,void*)
std::set<GLuint> liveBuffers;size_t uploadCalls=0;
F_glGenBuffers rawGen;F_glDeleteBuffers rawDelete;F_glBufferSubData rawSub;
void trackGen(GLsizei n,GLuint* names){rawGen(n,names);for(int i=0;i<n;i++)liveBuffers.insert(names[i]);}
void trackDelete(GLsizei n,const GLuint* names){for(int i=0;i<n;i++)liveBuffers.erase(names[i]);rawDelete(n,names);}
void trackSub(GLenum t,ptrdiff_t o,ptrdiff_t n,const void* p){uploadCalls++;rawSub(t,o,n,p);}
#include "colored_scene_gpu.h"
''' + shaders +r'''
using Mat=std::array<float,16>;
Mat mul(Mat a,Mat b){Mat c{};for(int col=0;col<4;col++)for(int r=0;r<4;r++)for(int k=0;k<4;k++)c[col*4+r]+=a[k*4+r]*b[col*4+k];return c;}
Mat view(){
 float eye[]={4,11,12},target[]={-5,0,1},f[3],r[3],u[3];
 float len=0;for(int k=0;k<3;k++){f[k]=target[k]-eye[k];len+=f[k]*f[k];}for(float&v:f)v/=sqrtf(len);
 r[0]=-f[2];r[1]=0;r[2]=f[0];len=sqrtf(r[0]*r[0]+r[2]*r[2]);for(float&v:r)v/=len;
 u[0]=r[1]*f[2]-r[2]*f[1];u[1]=r[2]*f[0]-r[0]*f[2];u[2]=r[0]*f[1]-r[1]*f[0];
 return {r[0],u[0],-f[0],0,r[1],u[1],-f[1],0,r[2],u[2],-f[2],0,
 -(r[0]*eye[0]+r[1]*eye[1]+r[2]*eye[2]),-(u[0]*eye[0]+u[1]*eye[1]+u[2]*eye[2]),f[0]*eye[0]+f[1]*eye[1]+f[2]*eye[2],1};
}
std::vector<uint8_t> read(const char* file){std::ifstream in(file,std::ios::binary);assert(in);return {(std::istreambuf_iterator<char>(in)),{}};}
int main(int argc,char**argv){
 assert(argc==5);SetDllDirectoryA(argv[1]);HMODULE egl=LoadLibraryA("libEGL.dll"),gles=LoadLibraryA("libGLESv2.dll");assert(egl&&gles);
'''
egl_names=re.findall(r'FN\([^,]+,(egl\w+)[,)]',code)
gl_names=re.findall(r'FN\([^,]+,(gl\w+)[,)]',code)
for lib,names in [('egl',egl_names),('gles',gl_names)]:
    for name in names:code+=f' {name}=(F_{name})GetProcAddress({lib},"{name}");assert({name});\n'
code+=r'''
 rawGen=glGenBuffers;glGenBuffers=trackGen;rawDelete=glDeleteBuffers;glDeleteBuffers=trackDelete;rawSub=glBufferSubData;glBufferSubData=trackSub;
 void* display=eglGetDisplay(nullptr);int a,b;assert(eglInitialize(display,&a,&b));
 int attrs[]={0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3038};void* config;int count;
 assert(eglChooseConfig(display,attrs,&config,1,&count)&&count);
 int ca[]={0x3098,3,0x3038},sa[]={0x3057,1200,0x3056,800,0x3038};
 void* context=eglCreateContext(display,config,nullptr,ca),*surface=eglCreatePbufferSurface(display,config,sa);
 assert(context&&surface&&eglMakeCurrent(display,surface,surface,context));
 GLuint program=glCreateProgram();
 for(auto pair:{std::make_pair(sceneVertex,0x8b31u),std::make_pair(sceneFragment,0x8b30u)}){
  GLuint shader=glCreateShader(pair.second);glShaderSource(shader,1,&pair.first,nullptr);glCompileShader(shader);GLint ok;glGetShaderiv(shader,0x8b81,&ok);
  if(!ok){char error[4096];glGetShaderInfoLog(shader,4096,nullptr,error);std::cerr<<error;return 1;}glAttachShader(program,shader);
 }
 glLinkProgram(program);GLint ok;glGetProgramiv(program,0x8b82,&ok);assert(ok);
 auto p=read(argv[2]),c=read(argv[3]),ix=read(argv[4]);
 auto data=tlzscene::decode(p.data(),p.size(),c.data(),c.size(),ix.data(),ix.size(),p.size()/12,ix.size()/12);
 tlzscene::Gpu gpu;GLuint vao;glGenVertexArrays(1,&vao);glBindVertexArray(vao);
 const size_t chunks=data.chunks.size(),bytes=data.bytes;int frames=0;
 gpu.submit(tlzscene::Geometry(data));
 while(gpu.stats[0]==0&&frames<100){auto done=gpu.stats[4].load();gpu.tick();glFinish();assert(gpu.stats[4]-done<=2*1024*1024);frames++;assert(gpu.stats[7]==0);}
 assert(gpu.stats[0]==chunks&&gpu.stats[3]==bytes&&frames>=10&&gpu.revision==1);
 float f=1/tanf(.567232f);Mat projection={f/1.5f,0,0,0,0,f,0,0,0,0,-1.001001f,-1,0,0,-.10005f,0};Mat mvp=mul(projection,view());
 glViewport(0,0,1200,800);glClearColor(.76f,.81f,.84f,1);glClear(0x4100);
 size_t uploads=uploadCalls;gpu.draw(program,mvp,true,false);glFinish();assert(glGetError()==0&&gpu.stats[6]>0&&gpu.stats[6]<=chunks&&uploadCalls==uploads);
 std::vector<uint8_t> pixels(1200*800*4);glReadPixels(0,0,1200,800,0x1908,0x1401,pixels.data());
 std::ofstream ppm("scene-gpu.ppm",std::ios::binary);ppm<<"P6\n1200 800\n255\n";size_t drawn=0;
 for(int y=799;y>=0;y--)for(int x=0;x<1200;x++){size_t i=(y*1200+x)*4;ppm.write((char*)pixels.data()+i,3);if(abs((int)pixels[i]-194)>3||abs((int)pixels[i+1]-207)>3||abs((int)pixels[i+2]-214)>3)drawn++;}ppm.close();assert(drawn>10000);
 gpu.draw(program,mvp,true,true);assert(glGetError()==0&&uploadCalls==uploads);
 // Replacement stays atomic, keeps old view until complete, and frees old VBOs/EBOs.
 gpu.submit(std::move(data));gpu.tick();assert(gpu.revision==1&&gpu.stats[0]==chunks);
 while(gpu.revision==1){gpu.tick();assert(gpu.stats[7]==0);}
 assert(gpu.revision==2&&liveBuffers.size()==chunks*2);gpu.clear();assert(liveBuffers.empty());
 std::cout<<"PASS: production ANGLE GLES chunk VBO/EBO upload in "<<frames<<" bounded frames, uint32 triangle/point draws, colour shader, frustum, atomic replacement and GPU resource cleanup; rendered pixels="<<drawn<<"\n";
 glDeleteProgram(program);eglMakeCurrent(display,nullptr,nullptr,nullptr);eglDestroyContext(display,context);eglDestroySurface(display,surface);eglTerminate(display);
}
'''
(out/'gpu.cpp').write_text(code,encoding='utf8')
vs=Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /O2 /std:c++17 /EHsc /I"{root/"vr/src/main/cpp"}" gpu.cpp /Fe:gpu.exe',shell=True,cwd=out,check=True)
sdk=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/emulator/lib64/gles_angle'
assets=root/'vr/src/main/assets/colored_scene'
subprocess.run([str(out/'gpu.exe'),str(sdk),*[str(assets/n) for n in ['positions.bin','colors.bin','indices.bin']]],cwd=out,check=True,timeout=60)
Image.open(out/'scene-gpu.ppm').save(out/'scene-gpu.png')
