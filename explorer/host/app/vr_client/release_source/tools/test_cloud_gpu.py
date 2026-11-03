"""Execute shared production point shaders/uploader in real off-screen GLES."""
from pathlib import Path
import ast,re,subprocess,os
root=Path(__file__).resolve().parents[1];out=root/'vr/build/cloud-gpu-test';out.mkdir(parents=True,exist_ok=True)
# Reuse the existing dynamic EGL/GLES host binding declarations (not its renderer).
tree=ast.parse((root/'tools/test_colored_scene_gpu.py').read_text(encoding='utf8'))
assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
parts=[]
def constants(n):
 if isinstance(n,ast.Constant) and isinstance(n.value,str):parts.append(n.value)
 elif isinstance(n,ast.BinOp):constants(n.left);constants(n.right)
constants(assignment.value)
prefix=parts[0].split('#include "colored_scene_gpu.h"')[0]
prefix+='\nconstexpr GLenum GL_UNSIGNED_BYTE=0x1401;\nFN(void,glUniform3fv,GLint,GLsizei,const float*) FN(void,glUniform1f,GLint,float)\n#include "cloud_points.h"\n'
extra={"GL_DYNAMIC_DRAW":0x88e8,"GL_SRC_ALPHA":0x0302,"GL_ONE_MINUS_SRC_ALPHA":0x0303,"GL_FALSE":0,"GL_TEXTURE6":0x84c6,"GL_TEXTURE_3D":0x806f,"GL_NEAREST":0x2600,"GL_CLAMP_TO_EDGE":0x812f,"GL_TEXTURE_WRAP_R":0x8072,"GL_R8UI":0x8232,"GL_RED_INTEGER":0x8d94,"GL_UNPACK_ALIGNMENT":0xcf5,"GL_TEXTURE_MIN_FILTER":0x2801,"GL_TEXTURE_MAG_FILTER":0x2800,"GL_TEXTURE_WRAP_S":0x2802,"GL_TEXTURE_WRAP_T":0x2803}
# Bind optional production texture-grid functions before including the renderer.
insert=""
for name,value in extra.items():
 if not re.search(r"\b"+name+r"\s*=",prefix):insert+=f"constexpr GLenum {name}={value};\n"
for result,name,args in [("void","glBlendFunc","GLenum,GLenum"),("void","glGenTextures","GLsizei,GLuint*"),("void","glDeleteTextures","GLsizei,const GLuint*"),("void","glActiveTexture","GLenum"),("void","glBindTexture","GLenum,GLuint"),("void","glTexParameteri","GLenum,GLenum,GLint"),("void","glUniform3i","GLint,GLint,GLint,GLint"),("void","glTexImage3D","GLenum,GLint,GLint,GLsizei,GLsizei,GLsizei,GLint,GLenum,GLenum,const void*"),("void","glPixelStorei","GLenum,GLint")]:
 if not re.search(r"FN\([^,]+,"+name+r"[,)]",prefix):insert+=f"FN({result},{name},{args})\n"
prefix=prefix.replace('#include "cloud_points.h"',insert+'#include "cloud_points.h"\n#include "live_cloud_gpu.h"')
code=prefix+r'''
std::vector<uint8_t> point(float x,float y,float z,uint8_t r,uint8_t g,uint8_t b){float p[]={x,y,z};auto bytes=(uint8_t*)p;std::vector<uint8_t> data(bytes,bytes+12);data.insert(data.end(),{r,g,b});return data;}
void add(std::vector<uint8_t>& a,std::vector<uint8_t> b){a.insert(a.end(),b.begin(),b.end());}
int main(int argc,char**argv){
 assert(argc==3);SetDllDirectoryA(argv[1]);HMODULE egl=LoadLibraryA("libEGL.dll"),gles=LoadLibraryA("libGLESv2.dll");assert(egl&&gles);
'''
for lib,pattern in [('egl','egl'),('gles','gl')]:
 for name in re.findall(r'FN\([^,]+,('+pattern+r'\w+)[,)]',prefix):code+=f'{name}=(F_{name})GetProcAddress({lib},"{name}");assert({name});\n'
code+=r'''
 rawGen=glGenBuffers;glGenBuffers=trackGen;rawDelete=glDeleteBuffers;glDeleteBuffers=trackDelete;rawSub=glBufferSubData;glBufferSubData=trackSub;
 void* display=eglGetDisplay(nullptr);int a,b;assert(eglInitialize(display,&a,&b));int attrs[]={0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3038};void* config;int count;assert(eglChooseConfig(display,attrs,&config,1,&count)&&count);
 int ca[]={0x3098,3,0x3038},sa[]={0x3057,1200,0x3056,800,0x3038};void* ctx=eglCreateContext(display,config,nullptr,ca),*surface=eglCreatePbufferSurface(display,config,sa);assert(eglMakeCurrent(display,surface,surface,ctx));
 GLuint program=glCreateProgram();for(auto pair:{std::make_pair(cloud::vertex,0x8b31u),std::make_pair(cloud::fragment,0x8b30u)}){GLuint s=glCreateShader(pair.second);glShaderSource(s,1,&pair.first,nullptr);glCompileShader(s);GLint ok;glGetShaderiv(s,0x8b81,&ok);if(!ok){char log[4096];glGetShaderInfoLog(s,4096,nullptr,log);std::cerr<<log;return 1;}glAttachShader(program,s);}glLinkProgram(program);GLint ok;glGetProgramiv(program,0x8b82,&ok);assert(ok);
 GLuint vao;glGenVertexArrays(1,&vao);glBindVertexArray(vao);glViewport(0,0,1200,800);
 cloud::Gpu gpu;gpu.configure(1,{{"a",{-.05f,-.05f,-3.55f,.65f,.05f,-1.95f}},{"b",{.25f,.25f,-2.25f,.35f,.35f,-2.15f}},{"c",{4,0,-2,4.1f,.1f,-1.9f}}});
 std::vector<uint8_t> coarse=point(0,0,-2,255,0,0);add(coarse,point(.6f,0,-3.5f,128,128,128));add(coarse,point(4,0,-2,255,128,0));assert(gpu.offer(1,"coarse",coarse.data(),coarse.size(),true));gpu.tick();
 cloud::Mat mvp={.2f,0,0,0,0,.2f,0,0,0,0,.1f,0,0,0,0,1};
 auto draw=[&](std::array<float,3> head){glClearColor(.1f,.1f,.1f,1);glClear(0x4100);gpu.draw(program,mvp,head,true);glFinish();assert(glGetError()==0);};
 auto pixel=[&](int x,int y){std::array<uint8_t,4> p{};glReadPixels(x,y,1,1,0x1908,GL_UNSIGNED_BYTE,p.data());return p;};
 draw({0,0,0});assert(pixel(600,400)[0]>250&&gpu.stats[5]==0); // coarse remains before any fine upload
 std::vector<uint8_t> fine=point(0,0,-2,0,255,0);add(fine,point(.6f,0,-3.5f,255,0,0));assert(gpu.offer(1,"a",fine.data(),fine.size(),false));gpu.tick();draw({0,0,0});assert(pixel(600,400)[0]>250&&gpu.stats[3]==1&&gpu.stats[4]==2); // not all near blocks ready
 auto fineB=point(.3f,.3f,-2.2f,0,255,0);assert(gpu.offer(1,"b",fineB.data(),fineB.size(),false));gpu.tick();draw({0,0,0});
 assert(gpu.stats[5]==1&&pixel(600,400)[1]>250&&pixel(600,400)[0]<3); // fine replaces coarse, not double drawn
 auto grey=pixel(672,400);assert(abs((int)grey[0]-128)<=2&&abs((int)grey[1]-128)<=2); // fine point outside 3m clipped; coarse sRGB preserved
 draw({4,0,0});assert(gpu.stats[5]==0&&pixel(1080,400)[0]>250); // moved toward unloaded block: immediate coarse fallback
 size_t before=uploadCalls;draw({0,0,0});assert(uploadCalls==before); // head motion never reuploads cached points
 gpu.configure(2,{});assert(!gpu.offer(1,"stale",fine.data(),fine.size(),false));gpu.tick();assert(gpu.resident(2).empty()&&liveBuffers.empty());gpu.clearGl();
 {
 cloud::Gpu budgetGpu(64);budgetGpu.configure(1,{{"far",{4,0,0,4.1f,.1f,.1f}},{"near",{0,0,0,.1f,.1f,.1f}}});
 auto p=point(0,0,0,255,255,255);budgetGpu.offer(1,"coarse",p.data(),p.size(),true);budgetGpu.tick();budgetGpu.offer(1,"far",p.data(),p.size(),false);budgetGpu.tick();
 std::vector<uint8_t> three=p;add(three,p);add(three,p);assert(budgetGpu.offer(1,"near",three.data(),three.size(),false));assert(budgetGpu.queuedIds(1).count("near"));budgetGpu.tick();
 assert(budgetGpu.resident(1).count("near")&&!budgetGpu.resident(1).count("far")&&budgetGpu.stats[1]==64);
 assert(budgetGpu.offer(1,"reject",p.data(),p.size(),false));budgetGpu.tick();assert(!budgetGpu.queuedIds(1).count("reject"));
 budgetGpu.configure(2,{});assert(budgetGpu.resident(2).empty());budgetGpu.configure(1,{});assert(!budgetGpu.offer(1,"stale",p.data(),p.size(),false));budgetGpu.tick();budgetGpu.clearGl();assert(liveBuffers.empty());
 }
 {
 cloud::Gpu progressiveGpu;progressiveGpu.configure(4,{{"a",{.1f,0,-2,.3f,.1f,-1.9f}},{"b",{.4f,.2f,-2.3f,.6f,.4f,-2.1f}}});progressiveGpu.grid(4,1,{0,0,-2,0,0,-3});
 auto coarseA=point(.2f,0,-2,255,0,0);auto both=coarseA;add(both,point(.5f,.3f,-2.2f,255,0,0));progressiveGpu.offer(4,"coarse",both.data(),both.size(),true);progressiveGpu.tick();
 auto partial=point(.2f,0,-2,0,255,0);progressiveGpu.offer(4,"a",partial.data(),partial.size(),false);progressiveGpu.tick();
 glClearColor(.1f,.1f,.1f,1);glClear(0x4100);progressiveGpu.draw(program,mvp,{0,0,0},true);glFinish();assert(glGetError()==0);assert(pixel(624,400)[1]>250&&pixel(624,400)[0]<3);assert(pixel(660,424)[0]>250);assert(progressiveGpu.stats[3]==1&&progressiveGpu.stats[4]==2&&progressiveGpu.stats[5]==0);
 progressiveGpu.clearGl();assert(liveBuffers.empty());
 }
 {
 GLuint liveProgram=glCreateProgram();for(auto pair:{std::make_pair(livecloud::vertex,0x8b31u),std::make_pair(livecloud::fragment,0x8b30u)}){GLuint shader=glCreateShader(pair.second);glShaderSource(shader,1,&pair.first,nullptr);glCompileShader(shader);GLint ok;glGetShaderiv(shader,0x8b81,&ok);assert(ok);glAttachShader(liveProgram,shader);}glLinkProgram(liveProgram);GLint ok;glGetProgramiv(liveProgram,0x8b82,&ok);assert(ok);
 livecloud::Gpu liveGpu;liveGpu.reset(1);auto one=point(0,0,-2,255,0,0);auto rgba=cloud::packedPoints(one.data(),one.size());rgba[15]=128;cloud::Mat transform={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};assert(liveGpu.offer(1,rgba,transform));liveGpu.visible=true;liveGpu.tick();glClearColor(0,0,0,1);glClear(0x4100);liveGpu.draw(liveProgram,mvp,true);glFinish();assert(abs((int)pixel(600,400)[0]-128)<3);
 one=point(.5f,0,-2,0,255,0);rgba=cloud::packedPoints(one.data(),one.size());assert(liveGpu.offer(1,rgba,transform));liveGpu.tick();glClear(0x4100);liveGpu.draw(liveProgram,mvp,true);glFinish();assert(pixel(600,400)[0]==0&&pixel(660,400)[1]>250&&liveGpu.stats[0]==1&&liveGpu.stats[2]==2);
 liveGpu.reset(2);assert(!liveGpu.offer(1,rgba,transform));liveGpu.tick();assert(liveGpu.stats[0]==0);liveGpu.clear();glDeleteProgram(liveProgram);assert(liveBuffers.empty());assert(glGetError()==0);
 }
 std::ifstream file(argv[2],std::ios::binary);std::vector<uint8_t> real((std::istreambuf_iterator<char>(file)),{});assert(real.size()==117299*15);
 gpu.configure(3,{});assert(gpu.offer(3,"coarse",real.data(),real.size(),true));gpu.tick();
 cloud::Mat top={.05555556f,0,0,0,0,0,-.05f,0,0,-.08333333f,0,0,.31f,-.154f,0,1};
 glClearColor(.74f,.81f,.86f,1);glClear(0x4100);gpu.draw(program,top,{0,4,0},true);glFinish();
 std::vector<uint8_t> pixels(1200*800*4);glReadPixels(0,0,1200,800,0x1908,GL_UNSIGNED_BYTE,pixels.data());
 std::ofstream ppm("real-cloud.ppm",std::ios::binary);ppm<<"P6\n1200 800\n255\n";for(int y=799;y>=0;y--)for(int x=0;x<1200;x++)ppm.write((char*)pixels.data()+(y*1200+x)*4,3);ppm.close();gpu.clearGl();assert(liveBuffers.empty());
 std::cout<<"PASS: production static point renderer with progressive cell coverage, 15->16 byte packing, GPU sRGB, per-point 3m clipping, full-near gating, moving-head fallback, generations and resource release. Real desktop GLES, not Quest.\n";
 glDeleteProgram(program);eglMakeCurrent(display,nullptr,nullptr,nullptr);eglDestroyContext(display,ctx);eglDestroySurface(display,surface);eglTerminate(display);
}
'''
(out/'test.cpp').write_text(code,encoding='utf8')
vs=Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /O2 /std:c++17 /EHsc /I"{root/"shared/src/main/cpp"}" /I"{root/"vr/src/main/cpp"}" test.cpp /Fe:test.exe',shell=True,cwd=out,check=True)
sdk=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/emulator/lib64/gles_angle'
import gzip
bundle=root.parent/'Quest3_static_cloud_offline_v2_20261031/Quest3_static_cloud_offline_v2'
(out/'coarse.bin').write_bytes(gzip.decompress((bundle/'scene/coarse.bin.gz').read_bytes()))
subprocess.run([str(out/'test.exe'),str(sdk),str(out/'coarse.bin')],cwd=out,check=True,timeout=30)
from PIL import Image
Image.open(out/'real-cloud.ppm').save(out/'real-cloud.png')
