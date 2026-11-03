#define XR_USE_PLATFORM_ANDROID
#define XR_USE_GRAPHICS_API_OPENGL_ES
// Khronos extension headers depend on core GL and JNI declarations; preserve
// this order.
// clang-format off
#include <jni.h>
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include "view_capture_math.h"
#include "camera_ui_math.h"
#include "live_cloud_gpu.h"
#include "controller_model.h"
#include "colored_scene_gpu.h"
#include "../../../../shared/src/main/cpp/cloud_points.h"
#include <android/bitmap.h>
#include <android/log.h>
#include <openxr.h>
#include <openxr_platform.h>
#include <time.h>
// clang-format on

#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using Mat = std::array<float, 16>;
Mat identity() { return {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}; }
Mat multiply(const Mat& a, const Mat& b) {
  Mat r{};
  for (int c = 0; c < 4; c++)
    for (int row = 0; row < 4; row++)
      for (int k = 0; k < 4; k++)
        r[c * 4 + row] += a[k * 4 + row] * b[c * 4 + k];
  return r;
}
Mat pose(const XrPosef& p) {
  auto q = p.orientation;
  float x = q.x, y = q.y, z = q.z, w = q.w;
  return {1 - 2 * y * y - 2 * z * z,
          2 * x * y + 2 * w * z,
          2 * x * z - 2 * w * y,
          0,
          2 * x * y - 2 * w * z,
          1 - 2 * x * x - 2 * z * z,
          2 * y * z + 2 * w * x,
          0,
          2 * x * z + 2 * w * y,
          2 * y * z - 2 * w * x,
          1 - 2 * x * x - 2 * y * y,
          0,
          p.position.x,
          p.position.y,
          p.position.z,
          1};
}
Mat inversePose(const XrPosef& p) {
  XrPosef inv{};
  inv.orientation = {-p.orientation.x, -p.orientation.y, -p.orientation.z,
                     p.orientation.w};
  Mat r = pose(inv);
  r[12] = -r[0] * p.position.x - r[4] * p.position.y - r[8] * p.position.z;
  r[13] = -r[1] * p.position.x - r[5] * p.position.y - r[9] * p.position.z;
  r[14] = -r[2] * p.position.x - r[6] * p.position.y - r[10] * p.position.z;
  return r;
}
// Rigid inverse for display-only camera rigs; never changes sampled operator
// poses.
Mat rigidInverse(const Mat& m) {
  Mat r = identity();
  for (int c = 0; c < 3; c++)
    for (int row = 0; row < 3; row++) r[c * 4 + row] = m[row * 4 + c];
  for (int row = 0; row < 3; row++)
    r[12 + row] = -(r[row] * m[12] + r[4 + row] * m[13] + r[8 + row] * m[14]);
  return r;
}
Mat planar(float x, float y, float z, float yaw) {
  Mat m = identity();
  float c = cosf(yaw), s = sinf(yaw);
  m[0] = m[10] = c;
  m[8] = s;
  m[2] = -s;
  m[12] = x;
  m[13] = y;
  m[14] = z;
  return m;
}
Mat followRig(const Mat& stageFromMap, const Mat& carWorld,
              const Mat& rawHead) {
  float originYaw = atan2f(stageFromMap[8], stageFromMap[10]);
  float carYaw = atan2f(carWorld[8], carWorld[10]);
  Mat rig = planar(0, 0, 0, carYaw - originYaw);
  for (int row = 0; row < 3; row++)
    rig[12 + row] = carWorld[12 + row] + (row == 1 ? 1.6f : 0) -
                    (rig[row] * rawHead[12] + rig[4 + row] * rawHead[13] +
                     rig[8 + row] * rawHead[14]);
  return rig;
}
Mat projection(const XrFovf& f) {
  float l = tanf(f.angleLeft), r = tanf(f.angleRight), d = tanf(f.angleDown),
        u = tanf(f.angleUp), near = .05f, far = 500;
  Mat p{};
  p[0] = 2 / (r - l);
  p[5] = 2 / (u - d);
  p[8] = (r + l) / (r - l);
  p[9] = (u + d) / (u - d);
  p[10] = -(far + near) / (far - near);
  p[11] = -1;
  p[14] = -2 * far * near / (far - near);
  return p;
}
std::vector<float> vehicleLines() {
  std::vector<float> car;
  auto cv = [&](float x, float y, float z) {
    car.insert(car.end(), {x, y, z, .06f, .43f, .49f, 1});
  };
  const int edge[] = {0, 1, 1, 3, 3, 2, 2, 0, 4, 5, 5, 7,
                      7, 6, 6, 4, 0, 4, 1, 5, 2, 6, 3, 7};
  for (int c : edge)
    cv((c & 1) ? .38f : -.38f, (c & 2) ? .32f : .14f, (c & 4) ? .46f : -.46f);
  for (int side = 0; side < 2; side++)
    for (int wheel = 0; wheel < 2; wheel++)
      for (int k = 0; k < 24; k++)
        for (int e = 0; e < 2; e++) {
          float a = (k + e) * 6.2831853f / 24;
          cv(side ? .41f : -.41f, .14f + cosf(a) * .14f,
             (wheel ? .29f : -.29f) + sinf(a) * .14f);
        }
  cv(0, .34f, .25f);
  cv(0, .34f, -.65f);
  cv(0, .34f, -.65f);
  cv(-.12f, .34f, -.45f);
  cv(0, .34f, -.65f);
  cv(.12f, .34f, -.45f);
  return car;
}
int64_t mono() {
  timespec t{};
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
void check(XrResult r, const char* what) {
  if (XR_FAILED(r))
    throw std::runtime_error(std::string(what) + " (" + std::to_string(r) +
                             ")");
}
struct Engine;
std::mutex lifecycle;
Engine* engine = nullptr;
JavaVM* vm = nullptr;

GLuint shader(GLenum type, const char* code) {
  GLuint s = glCreateShader(type);
  glShaderSource(s, 1, &code, nullptr);
  glCompileShader(s);
  GLint ok = 0;
  glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
  if (!ok) {
    char log[2048];
    glGetShaderInfoLog(s, 2048, nullptr, log);
    glDeleteShader(s);
    throw std::runtime_error(log);
  }
  return s;
}
GLuint program(const char* vertex, const char* fragment) {
  GLuint v = shader(GL_VERTEX_SHADER, vertex),
         f = shader(GL_FRAGMENT_SHADER, fragment), p = glCreateProgram();
  glAttachShader(p, v);
  glAttachShader(p, f);
  glLinkProgram(p);
  glDeleteShader(v);
  glDeleteShader(f);
  GLint ok = 0;
  glGetProgramiv(p, GL_LINK_STATUS, &ok);
  if (!ok) throw std::runtime_error("GL program link");
  return p;
}
const char* colorVertex =
    "#version 300 es\nlayout(location=0)in vec3 pos;layout(location=1)in vec4 "
    "color;uniform mat4 mvp;out vec4 c;void "
    "main(){gl_Position=mvp*vec4(pos,1);gl_PointSize=3.;c=color;}";
const char* colorFragment =
    "#version 300 es\nprecision mediump float;in vec4 c;out vec4 frag;void "
    "main(){frag=c;}";
const char* texVertex =
    "#version 300 es\nlayout(location=0)in vec3 pos;layout(location=1)in vec2 "
    "tex;uniform mat4 mvp;uniform mat4 uvMatrix;out vec2 uv;void "
    "main(){gl_Position=mvp*vec4(pos,1);uv=(uvMatrix*vec4(tex,0,1)).xy;}";
const char* hudFragment = R"(#version 300 es
precision highp float;uniform sampler2D image;uniform sampler2D backdrop;
uniform vec2 screenSize;uniform vec2 plateSize;in vec2 uv;out vec4 frag;
void main(){vec4 t=texture(image,uv);if(t.a<.004)discard;
 vec3 tint=t.rgb/max(t.a,.001);
 if(t.a<.85&&dot(tint,vec3(.2126,.7152,.0722))>.5){
   vec3 frosted=texture(backdrop,gl_FragCoord.xy/screenSize).rgb;
   frag=vec4((t.rgb+(1.-t.a)*frosted)*.90,.90);
 }else frag=t;
 if(plateSize.x>0.){float radius=min(.07,min(plateSize.x,plateSize.y)*.12);vec2 q=abs((uv-.5)*plateSize)-(plateSize*.5-radius);float d=length(max(q,0.))+min(max(q.x,q.y),0.)-radius;frag*=1.-smoothstep(-fwidth(d),fwidth(d),d);}
})";
const char* blurFragment = R"(#version 300 es
precision highp float;uniform sampler2D image;uniform vec2 direction;in vec2 uv;out vec4 frag;
void main(){vec3 c=texture(image,uv).rgb*.2270270270;
 c+=(texture(image,uv+direction*1.).rgb+texture(image,uv-direction*1.).rgb)*.1945945946;
 c+=(texture(image,uv+direction*2.).rgb+texture(image,uv-direction*2.).rgb)*.1216216216;
 c+=(texture(image,uv+direction*3.).rgb+texture(image,uv-direction*3.).rgb)*.0540540541;
 c+=(texture(image,uv+direction*4.).rgb+texture(image,uv-direction*4.).rgb)*.0162162162;
 frag=vec4(c,1.);
})";
// Controller geometry has its own opaque, texture-independent material pipeline.
const char* sceneVertex = R"(#version 300 es
precision highp float;layout(location=0) in vec3 position;layout(location=1) in vec3 color;
uniform mat4 mvp;out vec3 rgb;
void main(){gl_Position=mvp*vec4(position,1.);gl_PointSize=2.5;rgb=color;}
)";
const char* sceneFragment = R"(#version 300 es
precision highp float;in vec3 rgb;uniform bool encodeSrgb;out vec4 frag;
vec3 srgb(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
void main(){frag=vec4(encodeSrgb?srgb(rgb):rgb,1.);}
)";
const char* controllerVertex = R"(#version 300 es
precision highp float;
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
layout(location=2) in vec3 baseColor;
uniform mat4 mvp;
uniform mat4 modelView;
out vec3 n;out vec3 v;out vec3 color;
void main(){vec4 p=modelView*vec4(position,1.);v=p.xyz;n=mat3(modelView)*normal;color=baseColor;gl_Position=mvp*vec4(position,1.);}
)";
const char* controllerFragment = R"(#version 300 es
precision highp float;
in vec3 n;in vec3 v;in vec3 color;out vec4 frag;
uniform vec3 accent;
void main(){vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
vec3 V=normalize(-v),L=normalize(vec3(-.35,.8,.6));
float diffuse=max(dot(N,L),0.);float rim=pow(1.-max(dot(N,V),0.),3.);
float spec=pow(max(dot(N,normalize(L+V)),0.),36.);
vec3 c=color*(.42+.58*diffuse)+vec3(.10)*spec+accent*rim*.14;
frag=vec4(c,1.);}
)";
const char* resolvedVideoFragment =
    "#version 300 es\nprecision mediump float;uniform sampler2D image;in vec2 "
    "uv;"
    "out vec4 frag;void main(){frag=texture(image,uv);}";
const char* videoFragment =
    "#version 300 es\n#extension GL_OES_EGL_image_external_essl3 : "
    "require\nprecision mediump float;uniform samplerExternalOES image;in vec2 "
    "uv;out vec4 frag;void main(){frag=texture(image,uv);}";

const char* skyVertex = R"(#version 300 es
layout(location=0)in vec3 pos;out vec2 uv;
void main(){gl_Position=vec4(pos,1);uv=pos.xy*.5+.5;})";
const char* skyFragment = R"(#version 300 es
precision highp float;
in vec2 uv;out vec4 frag;uniform mat4 camera;uniform vec4 fov;uniform float floorY;
void main(){
 vec3 ray=normalize((camera*vec4(mix(fov.x,fov.y,uv.x),mix(fov.z,fov.w,uv.y),-1.,0.)).xyz);
 vec3 light=normalize(vec3(-.45,.62,-.65));
 float sun=pow(max(dot(ray,light),0.),48.);
 vec3 haze=vec3(.69,.79,.86);
 vec3 color=mix(haze,vec3(.18,.37,.58),smoothstep(-.06,.85,ray.y));
 color+=sun*vec3(.36,.29,.17);
 float cloud=sin(ray.x*14.+ray.z*8.)*sin(ray.z*21.-ray.y*12.);
 color+=vec3(.025)*cloud*smoothstep(.12,.5,ray.y);
 if(ray.y<-.0001){
  float t=(floorY-camera[3].y)/ray.y;
  if(t>0.){
   vec3 hit=camera[3].xyz+ray*t;
   float fade=exp(-t*.028);
   float shade=.88+.10*sin(hit.x*.16+hit.z*.11)+.06*cos(hit.z*.24-hit.x*.08);
   vec3 ground=vec3(.35,.43,.48)*shade;
   float shadow=exp(-dot(hit.xz,hit.xz)*.32);
   ground*=1.-shadow*.23;
   color=mix(haze,ground,fade);
   vec2 cell=abs(fract(hit.xz+.5)-.5)/max(fwidth(hit.xz),vec2(.001));
   float grid=(1.-min(min(cell.x,cell.y),1.))*exp(-t*.07);
   color=mix(color,vec3(.52,.65,.72),grid*.32);
  }
 }
 frag=vec4(color,1.);
})";

struct Eye {
  XrSwapchain swap = XR_NULL_HANDLE;
  uint32_t width = 0, height = 0;
  std::vector<XrSwapchainImageOpenGLESKHR> images;
  GLuint depth = 0;
};
struct Engine {
  jobject owner = nullptr;
  JNIEnv* env = nullptr;
  std::thread worker;
  std::atomic<bool> quit{false}, foreground{true};
  struct VideoSlot {GLuint external=0,texture=0,framebuffer=0;Mat uv=identity();std::atomic<bool> has{false},dirty{false},ready{false};std::atomic<int> width{1280},height{720};std::atomic<float> aspect{16.f/9};int allocatedWidth=0,allocatedHeight=0;} videos[6];
  std::atomic<bool> depthSelected{false};std::atomic<int> selectedCamera{0};int resolvingStream=0;
  Mat cameraListPanel=identity();bool cameraListPanelReady=false;int cameraTile[2]{-1,-1};jmethodID onUiOcclusion=nullptr;
  std::array<float,3> armCameraPosition{};bool armCameraValid=false,armCameraLarge=false;
  GLuint armVbo=0,labelTex=0,labelProg=0,mapTex=0,mapFbo=0;int armCount=0,labelIndex=0;bool labelsReady=false;
  std::vector<float> armData;bool armDirty=false,labelDirty=false;std::vector<uint8_t> labelPixels;float labelAnchors[8]={0,0,0,-2,0,0,0,-2};
  int64_t mapAt=0;float mapCenterX=0,mapCenterZ=0,mapRange=4;
  std::atomic<int> vibrate{0}, videoMode{2};
  std::atomic<bool> followView{false};
  Mat stageFromMap = identity(), carInMap = identity();
  bool originReady = false;
  XrReferenceSpaceType worldType = XR_REFERENCE_SPACE_TYPE_LOCAL;
  XrTime recenterTime = 0;
  Mat recenterTransform = identity();
  bool recenterValid = false;
  std::atomic<bool> showMap{true}, menuOpen{false};
  std::mutex dataMutex;
  std::vector<float> points, lines;
  std::vector<uint8_t> hudPixels, worldHudPixels;
  bool worldHudDirty = false;
  int worldHudWidth = 0, worldHudHeight = 0;
  bool pointsDirty = true, linesDirty = true, hudDirty = false;
  int hudWidth = 0, hudHeight = 0, allocatedHudWidth = 0,
      allocatedWorldWidth = 0;
  bool touchPlus = false, touchPro = false;
  bool refreshProfiles = true;
  std::string lastProfiles[2];
  std::vector<float> controllerLines;
  std::shared_ptr<livecloud::Gpu> livePoints=std::make_shared<livecloud::Gpu>();GLuint livePointProg=0;
  std::shared_ptr<cloud::Gpu> streamed=std::make_shared<cloud::Gpu>();GLuint cloudProg=0;
  std::array<float,3> cloudPosition{0,1.6f,0};std::atomic<float> cloudFloor{0};
  void drawStreamed(const Mat& vp,const Mat& head){
    if(sceneMode!=3)return;
    {std::lock_guard<std::mutex> lock(sceneMoveMutex);
    if(sceneReset.exchange(false)||sceneAnchorMode!=3){
      float yaw=atan2f(head[8],head[10]);float floor=worldType==XR_REFERENCE_SPACE_TYPE_STAGE?0:head[13]-1.6f;
      sceneAnchor=planar(head[12],floor-cloudFloor.load(),head[14],yaw);sceneAnchorMode=3;
    }
      if(sceneMoveYaw)sceneAnchor=multiply(multiply(planar(head[12],0,head[14],sceneMoveYaw),planar(-head[12],0,-head[14],0)),sceneAnchor);
      sceneAnchor[12]+=sceneMoveX;sceneAnchor[14]+=sceneMoveZ;sceneMoveX=sceneMoveZ=sceneMoveYaw=0;
      Mat inv=rigidInverse(sceneAnchor);for(int k=0;k<3;k++)cloudPosition[k]=inv[k]*head[12]+inv[4+k]*head[13]+inv[8+k]*head[14]+inv[12+k];
    }
    streamed->draw(cloudProg,multiply(vp,sceneAnchor),cloudPosition,!swapSrgb);
  }
  tlzscene::Gpu coloredScene;GLuint sceneProg=0;bool swapSrgb=true;
  std::atomic<int> sceneMode{0};std::atomic<bool> scenePoints{false},sceneReset{true};
  Mat sceneAnchor=identity();int sceneAnchorMode=0;
  std::mutex sceneMoveMutex;float sceneMoveX=0,sceneMoveZ=0,sceneMoveYaw=0;
  void drawColoredScene(const Mat& vp,const Mat& head){
    int mode=sceneMode.load();if(!mode||mode==3||!coloredScene.stats[0])return;
    if(sceneReset.exchange(false)||sceneAnchorMode!=mode){
      const auto& b=coloredScene.bounds;float yaw=atan2f(head[8],head[10]);
      float floor=worldType==XR_REFERENCE_SPACE_TYPE_STAGE?0:head[13]-1.6f;
      float scale=mode==1?1.5f/std::max(.01f,std::max(b[3]-b[0],b[5]-b[2])):1;
      sceneAnchor=planar(head[12]-(mode==1?head[8]*1.5f:0),floor+(mode==1?.85f:0),head[14]-(mode==1?head[10]*1.5f:0),yaw);
      for(int k=0;k<12;k++)sceneAnchor[k]*=scale;
      if(mode==1)for(int k=0;k<3;k++)sceneAnchor[12+k]-=sceneAnchor[k]*(b[0]+b[3])*.5f+sceneAnchor[4+k]*b[1]+sceneAnchor[8+k]*(b[2]+b[5])*.5f;
      sceneAnchorMode=mode;
    }
    // Scene-only locomotion, never applied to serialized operator poses.
    {std::lock_guard<std::mutex> lock(sceneMoveMutex);
      if(sceneMoveYaw){Mat turn=multiply(planar(head[12],0,head[14],sceneMoveYaw),planar(-head[12],0,-head[14],0));sceneAnchor=multiply(turn,sceneAnchor);}
      sceneAnchor[12]+=sceneMoveX;sceneAnchor[14]+=sceneMoveZ;sceneMoveX=sceneMoveZ=sceneMoveYaw=0;
    }
    coloredScene.draw(sceneProg,multiply(vp,sceneAnchor),!swapSrgb,scenePoints.load());
  }
  struct Controller {tlzcontroller::Mesh mesh=tlzcontroller::fallback();GLuint vbo=0;Mat grip=identity();bool tracked=false;};
  Controller controllers[2];GLuint controllerProg=0;
  bool renderModelExtension=false;
  PFN_xrEnumerateRenderModelPathsFB enumerateModels=nullptr;
  PFN_xrGetRenderModelPropertiesFB modelProperties=nullptr;
  PFN_xrLoadRenderModelFB loadModel=nullptr;
  std::thread modelWorker;std::atomic<bool> modelWorkerActive{false};
  std::atomic<unsigned> modelGeneration{0};
  std::mutex modelMutex;
  std::unique_ptr<tlzcontroller::Mesh> pendingModels[2];
  unsigned pendingGeneration[2]{};
  std::atomic<bool> captureRequested{false};
  uint64_t renderedFrames = 0;
  struct ExportSlot {GLuint texture=0,framebuffer=0;bool busy=false;int width=0,height=0;};
  ExportSlot exportSlots[6];
  struct ExportChannel {int width=0,height=0,fps=30;int64_t at=0,generation=0;float options[8]={70,.02f,.02f,.02f,.02f,.5f,.5f,0};};
  ExportChannel exportChannels[2];
  jmethodID onExport=nullptr;

  XrInstance instance = XR_NULL_HANDLE;
  XrSession session = XR_NULL_HANDLE;
  XrSystemId system = XR_NULL_SYSTEM_ID;
  XrSpace world = XR_NULL_HANDLE, viewSpace = XR_NULL_HANDLE;
  XrActionSet actions = XR_NULL_HANDLE;
  XrAction handPose = XR_NULL_HANDLE, aimPose = XR_NULL_HANDLE,
           stick = XR_NULL_HANDLE, grip = XR_NULL_HANDLE,
           trigger = XR_NULL_HANDLE, button[7]{}, haptic = XR_NULL_HANDLE;
  XrPath hands[2]{};
  XrSpace handSpace[2]{}, aimSpace[2]{};
  Eye eyes[2];
  XrSessionState state = XR_SESSION_STATE_UNKNOWN;
  bool running = false;
  EGLDisplay display = EGL_NO_DISPLAY;
  EGLContext context = EGL_NO_CONTEXT;
  EGLSurface surface = EGL_NO_SURFACE;
  GLuint skyProg = 0, worldHudTex = 0, carVbo = 0, blurProg = 0;
  GLuint blurTex[2]{}, blurFbo[2]{};
  int blurWidth = 0, blurHeight = 0, eyeWidth = 1, eyeHeight = 1;
  int carVertices = 0;
  GLuint resolvedVideoProg = 0;
  GLuint plateTex=0;
  GLuint colorProg = 0, videoProg = 0, hudProg = 0, fbo = 0, vao = 0,
         cloudVbo = 0, lineVbo = 0, controllerVbo = 0, quadVbo = 0,
         hudTex = 0;
  GLsizei pointCount = 0, lineCount = 0;
  jmethodID onReady = nullptr, onFrame = nullptr, onError = nullptr;
  jmethodID onRendered = nullptr, onMirror = nullptr;
  jmethodID onProfiles = nullptr, onHaptic = nullptr,
            onReferenceChange = nullptr;
  void launch(JNIEnv* e, jobject activity) {
    owner = e->NewGlobalRef(activity);
    worker = std::thread([this]() {
      vm->AttachCurrentThread(&env, nullptr);
      try {
        init();
        loop();
      } catch (const std::exception& e) {
        __android_log_print(ANDROID_LOG_ERROR, "TLZ2", "%s", e.what());
        if (onError) {
          jstring text = env->NewStringUTF(e.what());
          env->CallVoidMethod(owner, onError, text);
          env->DeleteLocalRef(text);
          if (env->ExceptionCheck()) env->ExceptionClear();
        }
      }
      cleanup();
      env->DeleteGlobalRef(owner);
      owner = nullptr;
      vm->DetachCurrentThread();
    });
  }
  void init() {
    jclass cls = env->GetObjectClass(owner);
    onReady = env->GetMethodID(cls, "onGlReady", "(II)V");
    onExport=env->GetMethodID(cls,"onViewCaptureFrame","(IIJJ[FJ)Z");
    onUiOcclusion=env->GetMethodID(cls,"onUiOcclusion","(FF)Z");
    onFrame = env->GetMethodID(cls, "onVrFrame", "([F[F[F[F[FIIIIJ)V");
    onError = env->GetMethodID(cls, "onNativeError", "(Ljava/lang/String;)V");
    onRendered = env->GetMethodID(cls, "onNativeRendered", "()V");
    onMirror = env->GetMethodID(cls, "onMirrorPixels", "(II[I)V");
    onProfiles = env->GetMethodID(cls, "onInputProfiles",
                                  "(Ljava/lang/String;Ljava/lang/String;)V");
    onHaptic = env->GetMethodID(cls, "onHapticResult", "(II)V");
    onReferenceChange =
        env->GetMethodID(cls, "onReferenceSpaceChanged", "(Z)V");
    env->DeleteLocalRef(cls);
    PFN_xrInitializeLoaderKHR loader = nullptr;
    check(xrGetInstanceProcAddr(XR_NULL_HANDLE, "xrInitializeLoaderKHR",
                                (PFN_xrVoidFunction*)&loader),
          "loader function");
    XrLoaderInitInfoAndroidKHR loaderInfo{XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR};
    loaderInfo.applicationVM = vm;
    loaderInfo.applicationContext = owner;
    check(loader((XrLoaderInitInfoBaseHeaderKHR*)&loaderInfo),
          "initialize Android loader");
    std::vector<const char*> extensions = {
        XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME,
        XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME};
    uint32_t extensionCount = 0;
    check(xrEnumerateInstanceExtensionProperties(nullptr, 0, &extensionCount,
                                                 nullptr),
          "extension count");
    std::vector<XrExtensionProperties> available(
        extensionCount, {XR_TYPE_EXTENSION_PROPERTIES});
    check(xrEnumerateInstanceExtensionProperties(
              nullptr, extensionCount, &extensionCount, available.data()),
          "extensions");
    for (const auto& e : available) {
      if(!strcmp(e.extensionName,XR_FB_RENDER_MODEL_EXTENSION_NAME)){
        extensions.push_back(XR_FB_RENDER_MODEL_EXTENSION_NAME);renderModelExtension=true;
      }
      if (!strcmp(e.extensionName,
                  XR_META_TOUCH_CONTROLLER_PLUS_EXTENSION_NAME)) {
        extensions.push_back(XR_META_TOUCH_CONTROLLER_PLUS_EXTENSION_NAME);
        touchPlus = true;
      }
      if (!strcmp(e.extensionName, XR_FB_TOUCH_CONTROLLER_PRO_EXTENSION_NAME)) {
        extensions.push_back(XR_FB_TOUCH_CONTROLLER_PRO_EXTENSION_NAME);
        touchPro = true;
      }
    }
    XrInstanceCreateInfoAndroidKHR androidInfo{
        XR_TYPE_INSTANCE_CREATE_INFO_ANDROID_KHR};
    androidInfo.applicationVM = vm;
    androidInfo.applicationActivity = owner;
    XrInstanceCreateInfo ci{XR_TYPE_INSTANCE_CREATE_INFO};
    ci.next = &androidInfo;
    strcpy(ci.applicationInfo.applicationName, "TanLuZhe Control Terminal");
    ci.applicationInfo.applicationVersion = 2;
    strcpy(ci.applicationInfo.engineName, "TLZ2 OpenXR GLES");
    ci.applicationInfo.apiVersion = XR_API_VERSION_1_0;
    ci.enabledExtensionCount = extensions.size();
    ci.enabledExtensionNames = extensions.data();
    check(xrCreateInstance(&ci, &instance), "xrCreateInstance");
    if(renderModelExtension){
      if(XR_FAILED(xrGetInstanceProcAddr(instance,"xrEnumerateRenderModelPathsFB",(PFN_xrVoidFunction*)&enumerateModels))||
         XR_FAILED(xrGetInstanceProcAddr(instance,"xrGetRenderModelPropertiesFB",(PFN_xrVoidFunction*)&modelProperties))||
         XR_FAILED(xrGetInstanceProcAddr(instance,"xrLoadRenderModelFB",(PFN_xrVoidFunction*)&loadModel)))renderModelExtension=false;
    }
    __android_log_print(ANDROID_LOG_INFO,"TLZ2","CONTROLLER_MODEL runtime_extension=%d",renderModelExtension);
    XrSystemGetInfo si{XR_TYPE_SYSTEM_GET_INFO};
    si.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
    check(xrGetSystem(instance, &si, &system), "xrGetSystem");
    PFN_xrGetOpenGLESGraphicsRequirementsKHR requirements = nullptr;
    check(
        xrGetInstanceProcAddr(instance, "xrGetOpenGLESGraphicsRequirementsKHR",
                              (PFN_xrVoidFunction*)&requirements),
        "GLES requirements function");
    XrGraphicsRequirementsOpenGLESKHR req{
        XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_ES_KHR};
    check(requirements(instance, system, &req), "GLES requirements");
    display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (!eglInitialize(display, nullptr, nullptr))
      throw std::runtime_error("eglInitialize");
    eglBindAPI(EGL_OPENGL_ES_API);
    EGLint attrs[] = {EGL_SURFACE_TYPE,
                      EGL_PBUFFER_BIT,
                      EGL_RENDERABLE_TYPE,
                      EGL_OPENGL_ES3_BIT,
                      EGL_RED_SIZE,
                      8,
                      EGL_GREEN_SIZE,
                      8,
                      EGL_BLUE_SIZE,
                      8,
                      EGL_ALPHA_SIZE,
                      8,
                      EGL_NONE};
    EGLConfig config;
    EGLint count = 0;
    if (!eglChooseConfig(display, attrs, &config, 1, &count) || count == 0)
      throw std::runtime_error("EGL config");
    EGLint contextAttrs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE},
           surfaceAttrs[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};
    context = eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttrs);
    surface = eglCreatePbufferSurface(display, config, surfaceAttrs);
    if (!eglMakeCurrent(display, surface, surface, context))
      throw std::runtime_error("EGL context");
    XrGraphicsBindingOpenGLESAndroidKHR binding{
        XR_TYPE_GRAPHICS_BINDING_OPENGL_ES_ANDROID_KHR};
    binding.display = display;
    binding.config = config;
    binding.context = context;
    XrSessionCreateInfo sessionInfo{XR_TYPE_SESSION_CREATE_INFO};
    sessionInfo.next = &binding;
    sessionInfo.systemId = system;
    check(xrCreateSession(instance, &sessionInfo, &session), "xrCreateSession");
    uint32_t refCount = 0;
    check(xrEnumerateReferenceSpaces(session, 0, &refCount, nullptr),
          "reference count");
    std::vector<XrReferenceSpaceType> refs(refCount);
    check(xrEnumerateReferenceSpaces(session, refCount, &refCount, refs.data()),
          "reference spaces");
    XrReferenceSpaceCreateInfo ref{XR_TYPE_REFERENCE_SPACE_CREATE_INFO};
    ref.poseInReferenceSpace.orientation.w = 1;
    ref.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_LOCAL;
    for (auto r : refs)
      if (r == XR_REFERENCE_SPACE_TYPE_STAGE) ref.referenceSpaceType = r;
    worldType = ref.referenceSpaceType;
    check(xrCreateReferenceSpace(session, &ref, &world), "world space");
    ref.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_VIEW;
    check(xrCreateReferenceSpace(session, &ref, &viewSpace), "view space");
    initActions();
    initSwapchains();
    initGl();
    glActiveTexture(GL_TEXTURE2);
    env->CallVoidMethod(owner, onReady, (jint)videos[0].external, (jint)videos[1].external);
    glBindTexture(GL_TEXTURE_EXTERNAL_OES, 0);
    glActiveTexture(GL_TEXTURE0);
    if (env->ExceptionCheck()) {
      env->ExceptionDescribe();
      env->ExceptionClear();
      throw std::runtime_error("Java video surface initialization");
    }
  }
  XrPath path(const char* s) {
    XrPath p;
    check(xrStringToPath(instance, s, &p), s);
    return p;
  }
  XrAction action(const char* name, XrActionType type, bool subactions) {
    XrActionCreateInfo info{XR_TYPE_ACTION_CREATE_INFO};
    strncpy(info.actionName, name, XR_MAX_ACTION_NAME_SIZE - 1);
    strncpy(info.localizedActionName, name,
            XR_MAX_LOCALIZED_ACTION_NAME_SIZE - 1);
    info.actionType = type;
    if (subactions) {
      info.countSubactionPaths = 2;
      info.subactionPaths = hands;
    }
    XrAction a;
    check(xrCreateAction(actions, &info, &a), name);
    return a;
  }
  void initActions() {
    hands[0] = path("/user/hand/left");
    hands[1] = path("/user/hand/right");
    XrActionSetCreateInfo ai{XR_TYPE_ACTION_SET_CREATE_INFO};
    strcpy(ai.actionSetName, "terminal");
    strcpy(ai.localizedActionSetName, "Terminal controls");
    check(xrCreateActionSet(instance, &ai, &actions), "action set");
    handPose = action("hand_pose", XR_ACTION_TYPE_POSE_INPUT, true);
    aimPose = action("aim_pose", XR_ACTION_TYPE_POSE_INPUT, true);
    stick = action("move_stick", XR_ACTION_TYPE_VECTOR2F_INPUT, true);
    grip = action("hold_control", XR_ACTION_TYPE_FLOAT_INPUT, true);
    trigger = action("gripper", XR_ACTION_TYPE_FLOAT_INPUT, true);
    haptic = action("confirmation", XR_ACTION_TYPE_VIBRATION_OUTPUT, true);
    const char* names[] = {"request_lease", "arm_control",   "stop_control",
                           "synchronize",   "exit_terminal", "toggle_video",
                           "toggle_map"};
    const char* bindings[] = {"/user/hand/right/input/a/click",
                              "/user/hand/left/input/x/click",
                              "/user/hand/right/input/b/click",
                              "/user/hand/left/input/y/click",
                              "/user/hand/left/input/menu/click",
                              "/user/hand/right/input/thumbstick/click",
                              "/user/hand/left/input/thumbstick/click"};
    std::vector<XrActionSuggestedBinding> suggested;
    for (int i = 0; i < 7; i++) {
      button[i] = action(names[i], XR_ACTION_TYPE_BOOLEAN_INPUT, false);
      suggested.push_back({button[i], path(bindings[i])});
    }
    for (int i = 0; i < 2; i++) {
      std::string root = i == 0 ? "/user/hand/left" : "/user/hand/right";
      suggested.push_back(
          {handPose, path((root + "/input/grip/pose").c_str())});
      suggested.push_back({aimPose, path((root + "/input/aim/pose").c_str())});
      suggested.push_back({stick, path((root + "/input/thumbstick").c_str())});
      suggested.push_back(
          {grip, path((root + "/input/squeeze/value").c_str())});
      suggested.push_back(
          {trigger, path((root + "/input/trigger/value").c_str())});
      suggested.push_back({haptic, path((root + "/output/haptic").c_str())});
    }
    XrInteractionProfileSuggestedBinding profile{
        XR_TYPE_INTERACTION_PROFILE_SUGGESTED_BINDING};
    profile.interactionProfile =
        path("/interaction_profiles/oculus/touch_controller");
    profile.countSuggestedBindings = suggested.size();
    profile.suggestedBindings = suggested.data();
    check(xrSuggestInteractionProfileBindings(instance, &profile),
          "Touch bindings");
    if (touchPlus) {
      profile.interactionProfile =
          path("/interaction_profiles/meta/touch_controller_plus");
      check(xrSuggestInteractionProfileBindings(instance, &profile),
            "Touch Plus bindings");
    }
    if (touchPro) {
      profile.interactionProfile =
          path("/interaction_profiles/facebook/touch_controller_pro");
      check(xrSuggestInteractionProfileBindings(instance, &profile),
            "Touch Pro bindings");
    }
    // Minimal controllers retain pointer selection and the menu even without
    // A/B/X/Y.
    std::vector<XrActionSuggestedBinding> simple;
    for (int i = 0; i < 2; i++) {
      std::string root = i == 0 ? "/user/hand/left" : "/user/hand/right";
      simple.push_back({handPose, path((root + "/input/grip/pose").c_str())});
      simple.push_back({aimPose, path((root + "/input/aim/pose").c_str())});
      simple.push_back({trigger, path((root + "/input/select/click").c_str())});
      simple.push_back({button[4], path((root + "/input/menu/click").c_str())});
      simple.push_back({haptic, path((root + "/output/haptic").c_str())});
    }
    profile.interactionProfile =
        path("/interaction_profiles/khr/simple_controller");
    profile.countSuggestedBindings = simple.size();
    profile.suggestedBindings = simple.data();
    check(xrSuggestInteractionProfileBindings(instance, &profile),
          "Simple controller bindings");
    XrSessionActionSetsAttachInfo attach{
        XR_TYPE_SESSION_ACTION_SETS_ATTACH_INFO};
    attach.countActionSets = 1;
    attach.actionSets = &actions;
    check(xrAttachSessionActionSets(session, &attach), "attach actions");
    for (int i = 0; i < 2; i++) {
      XrActionSpaceCreateInfo space{XR_TYPE_ACTION_SPACE_CREATE_INFO};
      space.action = handPose;
      space.subactionPath = hands[i];
      space.poseInActionSpace.orientation.w = 1;
      check(xrCreateActionSpace(session, &space, &handSpace[i]), "hand space");
      space.action = aimPose;
      check(xrCreateActionSpace(session, &space, &aimSpace[i]), "aim space");
    }
  }
  void initSwapchains() {
    uint32_t count = 0;
    check(xrEnumerateViewConfigurationViews(
              instance, system, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0,
              &count, nullptr),
          "view count");
    if (count != 2) throw std::runtime_error("Stereo views required");
    std::vector<XrViewConfigurationView> views(
        count, {XR_TYPE_VIEW_CONFIGURATION_VIEW});
    check(xrEnumerateViewConfigurationViews(
              instance, system, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO,
              count, &count, views.data()),
          "view sizes");
    uint32_t n = 0;
    check(xrEnumerateSwapchainFormats(session, 0, &n, nullptr), "format count");
    std::vector<int64_t> formats(n);
    check(xrEnumerateSwapchainFormats(session, n, &n, formats.data()),
          "formats");
    int64_t format = 0;
    for (auto f : formats)
      if (f == GL_SRGB8_ALPHA8) {
        format = f;
        break;
      }
    if (!format)
      for (auto f : formats)
        if (f == GL_RGBA8) {
          format = f;
          break;
        }
    if (!format) throw std::runtime_error("RGBA swapchain unsupported");
    swapSrgb=format==GL_SRGB8_ALPHA8;
    for (int i = 0; i < 2; i++) {
      Eye& e = eyes[i];
      e.width = views[i].recommendedImageRectWidth;
      e.height = views[i].recommendedImageRectHeight;
      XrSwapchainCreateInfo s{XR_TYPE_SWAPCHAIN_CREATE_INFO};
      s.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT |
                     XR_SWAPCHAIN_USAGE_SAMPLED_BIT;
      s.format = format;
      s.sampleCount = 1;
      s.width = e.width;
      s.height = e.height;
      s.faceCount = 1;
      s.arraySize = 1;
      s.mipCount = 1;
      check(xrCreateSwapchain(session, &s, &e.swap), "swapchain");
      check(xrEnumerateSwapchainImages(e.swap, 0, &n, nullptr), "images count");
      e.images.resize(n, {XR_TYPE_SWAPCHAIN_IMAGE_OPENGL_ES_KHR});
      check(xrEnumerateSwapchainImages(
                e.swap, n, &n, (XrSwapchainImageBaseHeader*)e.images.data()),
            "images");
      glGenRenderbuffers(1, &e.depth);
      glBindRenderbuffer(GL_RENDERBUFFER, e.depth);
      glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, e.width,
                            e.height);
    }
  }
  void initGl() {
    colorProg = program(colorVertex, colorFragment);
    sceneProg=program(sceneVertex,sceneFragment);cloudProg=program(cloud::vertex,cloud::fragment);livePointProg=program(livecloud::vertex,livecloud::fragment);
    controllerProg=program(controllerVertex,controllerFragment);
    for(auto& c:controllers){glGenBuffers(1,&c.vbo);glBindBuffer(GL_ARRAY_BUFFER,c.vbo);
      glBufferData(GL_ARRAY_BUFFER,c.mesh.vertices.size()*sizeof(float),c.mesh.vertices.data(),GL_STATIC_DRAW);}
    hudProg = program(texVertex, hudFragment);
    glGenTextures(1,&plateTex);glBindTexture(GL_TEXTURE_2D,plateTex);const uint8_t glass[]={102,110,118,128};glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,1,1,0,GL_RGBA,GL_UNSIGNED_BYTE,glass);textureParams();
    skyProg = program(skyVertex, skyFragment);
    blurProg = program(texVertex, blurFragment);
    glGenTextures(2, blurTex);
    glGenFramebuffers(2, blurFbo);
    videoProg = program(texVertex, videoFragment);
    resolvedVideoProg = program(texVertex, resolvedVideoFragment);
    labelProg=program(texVertex,resolvedVideoFragment);
    glGenBuffers(1,&armVbo);glGenTextures(1,&labelTex);glGenTextures(1,&mapTex);glGenFramebuffers(1,&mapFbo);
    glGenFramebuffers(1, &fbo);glGenVertexArrays(1, &vao);glBindVertexArray(vao);
    glGenBuffers(1, &cloudVbo);glGenBuffers(1, &lineVbo);glGenBuffers(1, &quadVbo);glGenBuffers(1, &controllerVbo);
    for(auto& v:videos){
      glGenTextures(1,&v.texture);glGenFramebuffers(1,&v.framebuffer);glGenTextures(1,&v.external);
      glActiveTexture(GL_TEXTURE2);glBindTexture(GL_TEXTURE_EXTERNAL_OES,v.external);
      glTexParameteri(GL_TEXTURE_EXTERNAL_OES,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_EXTERNAL_OES,GL_TEXTURE_MAG_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_EXTERNAL_OES,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_EXTERNAL_OES,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);glBindTexture(GL_TEXTURE_EXTERNAL_OES,0);
    } glActiveTexture(GL_TEXTURE0);
    std::vector<float> car = vehicleLines();
    glGenBuffers(1, &carVbo);
    glBindBuffer(GL_ARRAY_BUFFER, carVbo);
    glBufferData(GL_ARRAY_BUFFER, car.size() * sizeof(float), car.data(),
                 GL_STATIC_DRAW);
    carVertices = car.size() / 7;
    for (GLuint* t : {&hudTex, &worldHudTex}) {
      glGenTextures(1, t);
      glBindTexture(GL_TEXTURE_2D, *t);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    }
  }

  void events() {
    XrEventDataBuffer e{XR_TYPE_EVENT_DATA_BUFFER};
    while (xrPollEvent(instance, &e) == XR_SUCCESS) {
      if (e.type == XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED) {
        auto* change = (XrEventDataSessionStateChanged*)&e;
        state = change->state;
        if (state == XR_SESSION_STATE_READY && !running) {
          XrSessionBeginInfo b{XR_TYPE_SESSION_BEGIN_INFO};
          b.primaryViewConfigurationType =
              XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
          check(xrBeginSession(session, &b), "begin session");
          running = true;
          startModelLoader();
        } else if (state == XR_SESSION_STATE_STOPPING && running) {
          stopModelLoader();
          check(xrEndSession(session), "end session");
          running = false;
        } else if (state == XR_SESSION_STATE_EXITING ||
                   state == XR_SESSION_STATE_LOSS_PENDING)
          quit = true;
      } else if (e.type == XR_TYPE_EVENT_DATA_REFERENCE_SPACE_CHANGE_PENDING) {
        auto* change =
            reinterpret_cast<XrEventDataReferenceSpaceChangePending*>(&e);
        if (change->referenceSpaceType == worldType) {
          recenterTime = change->changeTime;
          recenterValid = change->poseValid;
          recenterTransform = inversePose(change->poseInPreviousSpace);
        }
      } else if (e.type == XR_TYPE_EVENT_DATA_INTERACTION_PROFILE_CHANGED)
        refreshProfiles = true;
      else if (e.type == XR_TYPE_EVENT_DATA_INSTANCE_LOSS_PENDING)
        quit = true;
      e = {XR_TYPE_EVENT_DATA_BUFFER};
    }
  }
  void inputProfiles() {
    std::string names[2];
    for (int i = 0; i < 2; i++) {
      XrInteractionProfileState current{XR_TYPE_INTERACTION_PROFILE_STATE};
      if (XR_SUCCEEDED(
              xrGetCurrentInteractionProfile(session, hands[i], &current)) &&
          current.interactionProfile) {
        char name[XR_MAX_PATH_LENGTH]{};
        uint32_t size = 0;
        if (XR_SUCCEEDED(xrPathToString(instance, current.interactionProfile,
                                        sizeof(name), &size, name)))
          names[i] = name;
      }
    }
    if (names[0] != lastProfiles[0] || names[1] != lastProfiles[1] ||
        refreshProfiles) {
      jstring a = env->NewStringUTF(names[0].c_str()),
              b = env->NewStringUTF(names[1].c_str());
      env->CallVoidMethod(owner, onProfiles, a, b);
      env->DeleteLocalRef(a);
      env->DeleteLocalRef(b);
      if(names[0]!=lastProfiles[0]||names[1]!=lastProfiles[1]){
        modelGeneration.fetch_add(1);
        for(auto& c:controllers){c.mesh=tlzcontroller::fallback();glBindBuffer(GL_ARRAY_BUFFER,c.vbo);
          glBufferData(GL_ARRAY_BUFFER,c.mesh.vertices.size()*sizeof(float),c.mesh.vertices.data(),GL_STATIC_DRAW);}
      }
      lastProfiles[0] = names[0];
      lastProfiles[1] = names[1];
      __android_log_print(ANDROID_LOG_INFO, "TLZ2", "Input profiles L=%s R=%s",
                          names[0].c_str(), names[1].c_str());
    }
    refreshProfiles = false;
  }
  void stopModelLoader(){
    modelWorkerActive=false;if(modelWorker.joinable())modelWorker.join();
  }
  void startModelLoader(){
    if(!renderModelExtension||modelWorker.joinable())return;
    modelWorkerActive=true;
    modelWorker=std::thread([this](){
      unsigned generation=~0u;XrRenderModelKeyFB loaded[2]{};
      XrResult lastEnumeration=XR_SUCCESS,lastProperty[2]={XR_SUCCESS,XR_SUCCESS};
      while(modelWorkerActive){
        unsigned current=modelGeneration.load();
        if(current!=generation){generation=current;loaded[0]=loaded[1]=0;}
        try{
          uint32_t count=0;
          XrResult result=enumerateModels(session,0,&count,nullptr);
          if(result!=XR_SUCCESS&&result!=lastEnumeration)
            __android_log_print(ANDROID_LOG_WARN,"TLZ2","CONTROLLER_MODEL enumerate fallback result=%d",(int)result);
          lastEnumeration=result;
          if(result==XR_SUCCESS&&count&&count<=64){
            std::vector<XrRenderModelPathInfoFB> paths(count,{XR_TYPE_RENDER_MODEL_PATH_INFO_FB});
            result=enumerateModels(session,count,&count,paths.data());
            if(result==XR_SUCCESS)for(const auto& entry:paths){
              if(!modelWorkerActive)break;
              char path[XR_MAX_PATH_LENGTH]{};uint32_t length=0;
              if(XR_FAILED(xrPathToString(instance,entry.path,sizeof(path),&length,path)))continue;
              int side=!strcmp(path,"/model_fb/controller/left")?0:!strcmp(path,"/model_fb/controller/right")?1:-1;
              if(side<0)continue;
              XrRenderModelCapabilitiesRequestFB caps{XR_TYPE_RENDER_MODEL_CAPABILITIES_REQUEST_FB};
              caps.flags=XR_RENDER_MODEL_SUPPORTS_GLTF_2_0_SUBSET_1_BIT_FB|XR_RENDER_MODEL_SUPPORTS_GLTF_2_0_SUBSET_2_BIT_FB;
              XrRenderModelPropertiesFB properties{XR_TYPE_RENDER_MODEL_PROPERTIES_FB};properties.next=&caps;
              result=modelProperties(session,entry.path,&properties);
              if(result!=XR_SUCCESS&&result!=lastProperty[side])
                __android_log_print(ANDROID_LOG_WARN,"TLZ2","CONTROLLER_MODEL properties fallback side=%d result=%d",side,(int)result);
              lastProperty[side]=result;
              if(result!=XR_SUCCESS||!properties.modelKey||properties.modelKey==loaded[side])continue;
              XrRenderModelLoadInfoFB info{XR_TYPE_RENDER_MODEL_LOAD_INFO_FB};info.modelKey=properties.modelKey;
              XrRenderModelBufferFB buffer{XR_TYPE_RENDER_MODEL_BUFFER_FB};
              if(loadModel(session,&info,&buffer)!=XR_SUCCESS||!buffer.bufferCountOutput||buffer.bufferCountOutput>16*1024*1024)continue;
              std::vector<uint8_t> bytes(buffer.bufferCountOutput);buffer.bufferCapacityInput=bytes.size();buffer.buffer=bytes.data();
              if(loadModel(session,&info,&buffer)!=XR_SUCCESS||buffer.bufferCountOutput>bytes.size())continue;
              bytes.resize(buffer.bufferCountOutput);
              try {
              auto mesh=std::make_unique<tlzcontroller::Mesh>(tlzcontroller::load(bytes));
              if(modelGeneration.load()!=generation)break;
              __android_log_print(ANDROID_LOG_INFO,"TLZ2","CONTROLLER_MODEL loaded side=%d name=%s version=%u vertices=%zu bounds=%g,%g,%g;%g,%g,%g",side,properties.modelName,properties.modelVersion,mesh->vertices.size()/9,mesh->bounds[0],mesh->bounds[1],mesh->bounds[2],mesh->bounds[3],mesh->bounds[4],mesh->bounds[5]);
              {std::lock_guard<std::mutex> guard(modelMutex);pendingModels[side]=std::move(mesh);pendingGeneration[side]=generation;}
              loaded[side]=properties.modelKey;
              }catch(const std::exception& e){
                loaded[side]=properties.modelKey;
                __android_log_print(ANDROID_LOG_WARN,"TLZ2","CONTROLLER_MODEL fallback side=%d reason=%s",side,e.what());
              }
            }
          }
        }catch(const std::exception& e){
          __android_log_print(ANDROID_LOG_WARN,"TLZ2","CONTROLLER_MODEL fallback reason=%s",e.what());
        }
        for(int n=0;n<20&&modelWorkerActive;n++)std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    });
  }
  void applyControllerModels(){
    std::lock_guard<std::mutex> guard(modelMutex);
    for(int i=0;i<2;i++)if(pendingModels[i]){
      if(pendingGeneration[i]==modelGeneration.load()){
        controllers[i].mesh=std::move(*pendingModels[i]);
        glBindBuffer(GL_ARRAY_BUFFER,controllers[i].vbo);
        glBufferData(GL_ARRAY_BUFFER,controllers[i].mesh.vertices.size()*sizeof(float),controllers[i].mesh.vertices.data(),GL_STATIC_DRAW);
      }
      pendingModels[i].reset();
    }
  }
  void drawControllers(const Mat& vp,const Mat& view){
    // HUD already disabled depth. Clear its stale scene depth before opaque hand geometry.
    glDepthMask(GL_TRUE);glClear(GL_DEPTH_BUFFER_BIT);glEnable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);glDisable(GL_CULL_FACE);
    glUseProgram(controllerProg);
    for(int i=0;i<2;i++){
      const auto& c=controllers[i];if(!c.tracked)continue;
      Mat mvp=multiply(vp,c.grip),mv=multiply(view,c.grip);
      glUniformMatrix4fv(glGetUniformLocation(controllerProg,"mvp"),1,GL_FALSE,mvp.data());
      glUniformMatrix4fv(glGetUniformLocation(controllerProg,"modelView"),1,GL_FALSE,mv.data());
      glUniform3f(glGetUniformLocation(controllerProg,"accent"),i?.72f:.08f,i?.32f:.65f,i?.18f:.83f);
      glBindBuffer(GL_ARRAY_BUFFER,c.vbo);
      for(int k=0;k<3;k++){glEnableVertexAttribArray(k);glVertexAttribPointer(k,3,GL_FLOAT,GL_FALSE,9*sizeof(float),(void*)(k*3*sizeof(float)));}
      glDrawArrays(GL_TRIANGLES,0,c.mesh.vertices.size()/9);
    }
    glDisableVertexAttribArray(2);glDisable(GL_DEPTH_TEST);
  }
  void sample(XrTime time, const XrView* views) {
    XrActiveActionSet active{actions, XR_NULL_PATH};
    XrActionsSyncInfo sync{XR_TYPE_ACTIONS_SYNC_INFO};
    sync.countActiveActionSets = 1;
    sync.activeActionSets = &active;
    XrResult sr = xrSyncActions(session, &sync);
    if (XR_FAILED(sr) && sr != XR_SESSION_NOT_FOCUSED)
      check(sr, "sync actions");
    bool focused =
        sr == XR_SUCCESS && state == XR_SESSION_STATE_FOCUSED && foreground;
    if (focused && refreshProfiles) inputProfiles();
    applyControllerModels();
    for(auto& c:controllers)c.tracked=false;
    float poses[21]{};
    poses[6] = poses[13] = poses[20] = 1;
    float axes[6]{0, 0, 0, 0, 1, 1};
    cameraTile[0]=cameraTile[1]=-1;
    float pointer[13]{-1, -1, -1, -1, 0, 0, 0, 0, 0, 0};
    int controlsValid = 0;
    int flags = 0, buttons = 0, activeHands = 0;
    XrSpaceLocation head{XR_TYPE_SPACE_LOCATION};
    xrLocateSpace(viewSpace, world, time, &head);
    Mat headInverse = inversePose(head.pose);
    controllerLines.clear();
    auto vertex = [&](XrVector3f v, int side) {
      controllerLines.insert(
          controllerLines.end(),
          {v.x, v.y, v.z, side == 0 ? .02f : .65f, side == 0 ? .48f : .27f,
           side == 0 ? .58f : .2f, 1});
    };
    auto locate = [&](XrSpace s, int offset, int bit) {
      XrSpaceLocation l{XR_TYPE_SPACE_LOCATION};
      if (XR_SUCCEEDED(xrLocateSpace(s, world, time, &l)) &&
          (l.locationFlags & (XR_SPACE_LOCATION_POSITION_VALID_BIT |
                              XR_SPACE_LOCATION_ORIENTATION_VALID_BIT)) ==
              (XR_SPACE_LOCATION_POSITION_VALID_BIT |
               XR_SPACE_LOCATION_ORIENTATION_VALID_BIT)) {
        poses[offset] = l.pose.position.x;
        poses[offset + 1] = l.pose.position.y;
        poses[offset + 2] = l.pose.position.z;
        poses[offset + 3] = l.pose.orientation.x;
        poses[offset + 4] = l.pose.orientation.y;
        poses[offset + 5] = l.pose.orientation.z;
        poses[offset + 6] = l.pose.orientation.w;
        if ((l.locationFlags & (XR_SPACE_LOCATION_POSITION_TRACKED_BIT |
                                XR_SPACE_LOCATION_ORIENTATION_TRACKED_BIT)) ==
            (XR_SPACE_LOCATION_POSITION_TRACKED_BIT |
             XR_SPACE_LOCATION_ORIENTATION_TRACKED_BIT))
          flags |= bit;
      }
    };
    locate(viewSpace, 0, 1);
    for (int i = 0; i < 2; i++) {
      XrActionStateGetInfo gi{XR_TYPE_ACTION_STATE_GET_INFO};
      gi.subactionPath = hands[i];
      gi.action = handPose;
      XrActionStatePose ps{XR_TYPE_ACTION_STATE_POSE};
      check(xrGetActionStatePose(session, &gi, &ps), "pose state");
      if (ps.isActive) {
        activeHands |= 1 << i;
        locate(handSpace[i], 7 + i * 7, 2 << i);
        if(focused && (flags & (2<<i))){
          XrPosef gripPose{};
          gripPose.position={poses[7+i*7],poses[8+i*7],poses[9+i*7]};
          gripPose.orientation={poses[10+i*7],poses[11+i*7],poses[12+i*7],poses[13+i*7]};
          controllers[i].grip=pose(gripPose);controllers[i].tracked=true;
        }
      }
      gi.action = aimPose;
      XrActionStatePose aim{XR_TYPE_ACTION_STATE_POSE};
      check(xrGetActionStatePose(session, &gi, &aim), "aim state");
      XrSpaceLocation ray{XR_TYPE_SPACE_LOCATION};
      const XrSpaceLocationFlags valid =
          XR_SPACE_LOCATION_POSITION_VALID_BIT |
          XR_SPACE_LOCATION_ORIENTATION_VALID_BIT;
      if (focused && aim.isActive &&
          XR_SUCCEEDED(xrLocateSpace(aimSpace[i], world, time, &ray)) &&
          (ray.locationFlags & valid) == valid &&
          (head.locationFlags & valid) == valid) {
        Mat worldRay = pose(ray.pose), local = multiply(headInverse, worldRay);
        // Shared head-relative HUD plane: width 2.9m, aspect 1600/1000,
        // distance 2.2m.
        float distance =
            local[10] > .0001f ? (local[14] + 2.2f) / local[10] : -1;
        XrVector3f end{worldRay[12] - worldRay[8] * 2,
                       worldRay[13] - worldRay[9] * 2,
                       worldRay[14] - worldRay[10] * 2};
        if (distance > 0 && distance < 10) {
          float x = local[12] - local[8] * distance,
                y = local[13] - local[9] * distance;
          pointer[i * 2] = x / 2.9f + .5f;
          pointer[i * 2 + 1] = .5f - y / 1.8125f;
          end = {worldRay[12] - worldRay[8] * distance,
                 worldRay[13] - worldRay[9] * distance,
                 worldRay[14] - worldRay[10] * distance};
          // A small cross on the UI plane follows the aim pose at display rate.
          for (int axis = 0; axis < 2; axis++) {
            XrVector3f a = end, b = end;
            a.x -= pose(head.pose)[axis * 4] * .012f;
            b.x += pose(head.pose)[axis * 4] * .012f;
            a.y -= pose(head.pose)[axis * 4 + 1] * .012f;
            b.y += pose(head.pose)[axis * 4 + 1] * .012f;
            a.z -= pose(head.pose)[axis * 4 + 2] * .012f;
            b.z += pose(head.pose)[axis * 4 + 2] * .012f;
            vertex(a, i);
            vertex(b, i);
          }
        }
        bool frontUi=false;
        if(distance>0&&distance<10){frontUi=env->CallBooleanMethod(owner,onUiOcclusion,pointer[i*2],pointer[i*2+1]);if(env->ExceptionCheck()){env->ExceptionClear();frontUi=true;}}
        if(!frontUi&&!menuOpen&&cameraListPanelReady){Mat localVideo=multiply(rigidInverse(cameraListPanel),worldRay);auto hit=cameraPanelHit(localVideo[12],localVideo[13],localVideo[14],localVideo[8],localVideo[9],localVideo[10]);
          if(hit.index>=0){cameraTile[i]=hit.index;end={worldRay[12]-worldRay[8]*hit.distance,worldRay[13]-worldRay[9]*hit.distance,worldRay[14]-worldRay[10]*hit.distance};}}
        vertex(ray.pose.position, i);
        vertex(end, i);
        // Controller orientation glyph, distinct from a system-provided
        // controller model.
        for (int axis = 0; axis < 3; axis++) {
          vertex(ray.pose.position, i);
          vertex({worldRay[12] + worldRay[axis * 4] * .07f,
                  worldRay[13] + worldRay[axis * 4 + 1] * .07f,
                  worldRay[14] + worldRay[axis * 4 + 2] * .07f},
                 i);
        }
      }
      gi.action = stick;
      XrActionStateVector2f v{XR_TYPE_ACTION_STATE_VECTOR2F};
      check(xrGetActionStateVector2f(session, &gi, &v), "stick state");
      if (v.isActive) {
        controlsValid |= 16 << i;
        activeHands |= 1 << i;
        axes[i * 2] = v.currentState.x;
        axes[i * 2 + 1] = v.currentState.y;
      }
      gi.action = trigger;
      XrActionStateFloat f{XR_TYPE_ACTION_STATE_FLOAT};
      check(xrGetActionStateFloat(session, &gi, &f), "trigger state");
      if (f.isActive) {
        controlsValid |= 4 << i;
        axes[4 + i] = 1 - f.currentState;
        pointer[4 + i] = f.currentState;
        activeHands |= 1 << i;
      }
      gi.action = grip;
      f = {XR_TYPE_ACTION_STATE_FLOAT};
      check(xrGetActionStateFloat(session, &gi, &f), "grip state");
      if (f.isActive) {
        controlsValid |= 1 << i;
        pointer[6 + i] = f.currentState;
      }
    }
    if (!focused) {
      flags = 0;
      controlsValid = 0;
    }
    pointer[8] = (float)controlsValid;pointer[11]=(float)cameraTile[0];pointer[12]=(float)cameraTile[1];
    for (int i = 0; i < 7; i++) {
      XrActionStateGetInfo gi{XR_TYPE_ACTION_STATE_GET_INFO};
      gi.action = button[i];
      XrActionStateBoolean b{XR_TYPE_ACTION_STATE_BOOLEAN};
      check(xrGetActionStateBoolean(session, &gi, &b), "button state");
      if (focused && b.isActive && i < 4) {
        const int wireBits[] = {1, 4, 2, 8};
        pointer[9] = (float)((int)pointer[9] | wireBits[i]);
      }
      if(focused&&b.isActive&&i>=5)pointer[10]=(float)((int)pointer[10]|(i==6?1:2));
      if (focused && b.isActive && b.currentState) buttons |= 1 << i;
    }
    int pulseHands = vibrate.exchange(0);
    if (pulseHands && focused) {
      XrHapticActionInfo info{XR_TYPE_HAPTIC_ACTION_INFO};
      info.action = haptic;
      XrHapticVibration pulse{XR_TYPE_HAPTIC_VIBRATION};
      pulse.duration = 50 * 1000 * 1000;
      pulse.frequency = XR_FREQUENCY_UNSPECIFIED;
      pulse.amplitude = .35f;
      for (int i = 0; i < 2; i++)
        if ((pulseHands & activeHands & (1 << i)) != 0) {
          info.subactionPath = hands[i];
          XrResult result = xrApplyHapticFeedback(session, &info,
                                                  (XrHapticBaseHeader*)&pulse);
          env->CallVoidMethod(owner, onHaptic, 1 << i, (jint)result);
        }
    }
    float eye[22]{};
    for (int i = 0; i < 2; i++) {
      int o = i * 11;
      eye[o] = views[i].pose.position.x;
      eye[o + 1] = views[i].pose.position.y;
      eye[o + 2] = views[i].pose.position.z;
      eye[o + 3] = views[i].pose.orientation.x;
      eye[o + 4] = views[i].pose.orientation.y;
      eye[o + 5] = views[i].pose.orientation.z;
      eye[o + 6] = views[i].pose.orientation.w;
      eye[o + 7] = views[i].fov.angleLeft;
      eye[o + 8] = views[i].fov.angleRight;
      eye[o + 9] = views[i].fov.angleUp;
      eye[o + 10] = views[i].fov.angleDown;
    }
    float boxes[14]{};
    for(int i=0;i<2;i++){
      memcpy(boxes+i*7,controllers[i].mesh.bounds,6*sizeof(float));
      boxes[i*7+6]=controllers[i].tracked?(float)controllers[i].mesh.source:-1;
    }
    jfloatArray jb=env->NewFloatArray(14);
    env->SetFloatArrayRegion(jb,0,14,boxes);
    jfloatArray jp = env->NewFloatArray(21), ja = env->NewFloatArray(6),
                je = env->NewFloatArray(22), ju = env->NewFloatArray(13);
    env->SetFloatArrayRegion(jp, 0, 21, poses);
    env->SetFloatArrayRegion(ja, 0, 6, axes);
    env->SetFloatArrayRegion(je, 0, 22, eye);
    env->SetFloatArrayRegion(ju, 0, 13, pointer);
    env->CallVoidMethod(owner, onFrame, jp, ja, je, ju, jb, flags, buttons,
                        activeHands, (jint)state, (jlong)mono());
    env->DeleteLocalRef(jb);
    env->DeleteLocalRef(jp);
    env->DeleteLocalRef(ja);
    env->DeleteLocalRef(je);
    env->DeleteLocalRef(ju);
    if (env->ExceptionCheck()) {
      env->ExceptionDescribe();
      env->ExceptionClear();
      throw std::runtime_error("Java VR frame callback failed");
    }
  }
  void upload() {
    std::lock_guard<std::mutex> guard(dataMutex);
    glActiveTexture(GL_TEXTURE0);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    if (pointsDirty) {
      glBindBuffer(GL_ARRAY_BUFFER, cloudVbo);
      glBufferData(GL_ARRAY_BUFFER, points.size() * sizeof(float),
                   points.data(), GL_DYNAMIC_DRAW);
      pointCount = points.size() / 7;
      pointsDirty = false;
    }
    if (linesDirty) {
      glBindBuffer(GL_ARRAY_BUFFER, lineVbo);
      glBufferData(GL_ARRAY_BUFFER, lines.size() * sizeof(float), lines.data(),
                   GL_DYNAMIC_DRAW);
      lineCount = lines.size() / 7;
      linesDirty = false;
    }
    if(armDirty){glBindBuffer(GL_ARRAY_BUFFER,armVbo);glBufferData(GL_ARRAY_BUFFER,armData.size()*sizeof(float),armData.data(),GL_DYNAMIC_DRAW);armCount=armData.size()/7;armDirty=false;}
    if(labelDirty){glBindTexture(GL_TEXTURE_2D,labelTex);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,512,128,0,GL_RGBA,GL_UNSIGNED_BYTE,labelPixels.data());textureParams();labelDirty=false;labelsReady=true;}
    if (hudDirty) {
      glBindTexture(GL_TEXTURE_2D, hudTex);

      if (allocatedHudWidth != hudWidth) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, hudWidth, hudHeight, 0, GL_RGBA,
                     GL_UNSIGNED_BYTE, nullptr);
        allocatedHudWidth = hudWidth;
      }
      glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, hudWidth, hudHeight, GL_RGBA,
                      GL_UNSIGNED_BYTE, hudPixels.data());
      hudDirty = false;
    }
    if (worldHudDirty) {
      glBindTexture(GL_TEXTURE_2D, worldHudTex);
      if (allocatedWorldWidth != worldHudWidth) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, worldHudWidth, worldHudHeight,
                     0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        allocatedWorldWidth = worldHudWidth;
      }
      glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, worldHudWidth, worldHudHeight,
                      GL_RGBA, GL_UNSIGNED_BYTE, worldHudPixels.data());
      worldHudDirty = false;
    }
  }
  void colored(GLuint buffer, int count, GLenum mode, const Mat& mvp) {
    if (!count) return;
    glUseProgram(colorProg);
    glUniformMatrix4fv(glGetUniformLocation(colorProg, "mvp"), 1, GL_FALSE,
                       mvp.data());
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 7 * sizeof(float), 0);
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 7 * sizeof(float),
                          (void*)(3 * sizeof(float)));
    glDrawArrays(mode, 0, count);
  }
  void textured(GLuint prog, GLuint tex, GLenum target, const Mat& mvp,
                float left, float bottom, float width, float height,
                bool flip) {
    float right = left + width, top = bottom + height;
    float vertices[] = {left,  bottom, 0, 0, 0, right, bottom, 0, 1, 0,
                        right, top,    0, 1, 1, left,  bottom, 0, 0, 0,
                        right, top,    0, 1, 1, left,  top,    0, 0, 1};
    glUseProgram(prog);
    glUniformMatrix4fv(glGetUniformLocation(prog, "mvp"), 1, GL_FALSE,
                       mvp.data());
    if (prog == hudProg) {
      glUniform2f(glGetUniformLocation(prog,"plateSize"),tex==plateTex?width:0,tex==plateTex?height:0);
      glActiveTexture(GL_TEXTURE1);
      glBindTexture(GL_TEXTURE_2D, blurTex[0]);
      glUniform1i(glGetUniformLocation(prog, "backdrop"), 1);
      glUniform2f(glGetUniformLocation(prog, "screenSize"), eyeWidth,
                  eyeHeight);
    }
    Mat uv = prog == videoProg ? videos[resolvingStream].uv : identity();
    if(prog==labelProg){uv[0]=.5f;uv[12]=labelIndex*.5f;}
    if (flip) {
      uv[5] = -1;
      uv[13] = 1;
    }
    glUniformMatrix4fv(glGetUniformLocation(prog, "uvMatrix"), 1, GL_FALSE,
                       uv.data());
    const bool external = target == GL_TEXTURE_EXTERNAL_OES;
    const int unit = external ? 2 : 0;
    glActiveTexture(GL_TEXTURE0 + unit);
    glBindTexture(target, tex);
    glUniform1i(glGetUniformLocation(prog, "image"), unit);
    glBindBuffer(GL_ARRAY_BUFFER, quadVbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * sizeof(float), 0);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * sizeof(float),
                          (void*)(3 * sizeof(float)));
    glDrawArrays(GL_TRIANGLES, 0, 6);
    if (external) glBindTexture(GL_TEXTURE_EXTERNAL_OES, 0);
    glActiveTexture(GL_TEXTURE0);
  }
  // Resolve decoder-owned OES storage exactly once per new frame. Both eyes and
  // UI use independent 2D storage thereafter; no decoder texture is sampled by
  // a HUD pass.
  int glErrorReports = 0;
  bool checkGl(const char* stage) {
    bool ok = true;
    for (int n = 0; n < 16; n++) {
      GLenum error = glGetError();
      if (error == GL_NO_ERROR) break;
      ok = false;
      if (glErrorReports++ < 12)
        __android_log_print(ANDROID_LOG_ERROR, "TLZ.XR",
                            "GL_ERROR stage=%s error=0x%x", stage, error);
    }
    return ok;
  }
  void resolveVideo(int index) {
    auto& v=videos[index];resolvingStream=index;
    if (!v.has) {
      v.ready = false;
      return;
    }
    if (!v.dirty) return;
    checkGl("before_video_resolve");
    int w = v.width.load(), h = v.height.load();
    GLint limit = 0;
    glGetIntegerv(GL_MAX_TEXTURE_SIZE, &limit);
    float scale = std::min(1.f, (float)limit / std::max(w, h));
    w = std::max(1, (int)(w * scale));
    h = std::max(1, (int)(h * scale));
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, v.texture);
    if (w != v.allocatedWidth || h != v.allocatedHeight) {
      glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA,
                   GL_UNSIGNED_BYTE, nullptr);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
      v.allocatedWidth = w;
      v.allocatedHeight = h;
      __android_log_print(ANDROID_LOG_INFO, "TLZ.XR",
                          "VIDEO_RESOLVE_SIZE %dx%d OES=unit2 HUD=unit0/1", w,
                          h);
    }
    glBindTexture(GL_TEXTURE_2D, 0);
    glBindFramebuffer(GL_FRAMEBUFFER, v.framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                           v.texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
      throw std::runtime_error("Video resolve framebuffer");
    glViewport(0, 0, w, h);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_SCISSOR_TEST);
    textured(videoProg, v.external, GL_TEXTURE_EXTERNAL_OES, identity(), -1, -1,
             2, 2, false);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    v.ready = checkGl("video_resolve");
    v.dirty = !v.ready;
  }
  void textureParams(){glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);}
  void glassRect(const Mat& vp,float x,float y,float w,float h){glEnable(GL_BLEND);glBlendFunc(GL_ONE,GL_ONE_MINUS_SRC_ALPHA);textured(hudProg,plateTex,GL_TEXTURE_2D,vp,(x/1600-.5f)*6.6f,(.5f-(y+h)/1000)*4.125f,w/1600*6.6f,h/1000*4.125f,false);}
  void drawVideoRect(int index,const Mat& vp,float x,float y,float w,float h){auto& v=videos[index];if(!v.has||!v.ready)return;float ratio=v.aspect.load();if(ratio<w/h){float fit=h*ratio;x+=(w-fit)*.5f;w=fit;}else{float fit=w/ratio;y+=(h-fit)*.5f;h=fit;}glDisable(GL_BLEND);textured(resolvedVideoProg,v.texture,GL_TEXTURE_2D,vp,(x/1600-.5f)*6.6f,(.5f-(y+h)/1000)*4.125f,w/1600*6.6f,h/1000*4.125f,false);}
  void renderOverview(const Mat& car){
    int64_t now=mono();if(mapAt&&now-mapAt<100000000)return;
    if(!mapAt){glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,mapTex);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,512,448,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);textureParams();}
    mapAt=now;float minX=car[12]-2,maxX=car[12]+2,minZ=car[14]-2,maxZ=car[14]+2;
    {std::lock_guard<std::mutex> g(dataMutex);
      auto include=[&](float x,float z){if(!std::isfinite(x)||!std::isfinite(z))return;minX=std::min(minX,x);maxX=std::max(maxX,x);minZ=std::min(minZ,z);maxZ=std::max(maxZ,z);};
      for(const auto* geometry:{&points,&lines})for(size_t i=0;i+6<geometry->size();i+=7)include((*geometry)[i],(*geometry)[i+2]);
      for(size_t i=0;i+6<armData.size();i+=7)include(car[0]*armData[i]+car[4]*armData[i+1]+car[8]*armData[i+2]+car[12],car[2]*armData[i]+car[6]*armData[i+1]+car[10]*armData[i+2]+car[14]);
    }
    float cx=(minX+maxX)*.5f,cz=(minZ+maxZ)*.5f,halfZ=(maxZ-minZ)*.55f,halfX=std::max((maxX-minX)*.55f,halfZ*512/448);halfZ=std::max(halfZ,halfX*448/512);minX=cx-halfX;maxX=cx+halfX;minZ=cz-halfZ;maxZ=cz+halfZ;
    Mat top{};top[0]=2/std::max(1.f,maxX-minX);top[9]=-2/std::max(1.f,maxZ-minZ);top[6]=-.002f;top[12]=-(maxX+minX)/(maxX-minX);top[13]=(maxZ+minZ)/(maxZ-minZ);top[15]=1;
    glBindFramebuffer(GL_FRAMEBUFFER,mapFbo);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,mapTex,0);
    if(glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)throw std::runtime_error("Overview framebuffer");
    glViewport(0,0,512,448);glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glClearColor(.1f,.2f,.26f,1);glClear(GL_COLOR_BUFFER_BIT);
    colored(cloudVbo,pointCount,GL_POINTS,top);colored(lineVbo,lineCount,GL_LINES,top);colored(carVbo,carVertices,GL_LINES,multiply(top,car));colored(armVbo,armCount,GL_LINES,multiply(top,car));glBindFramebuffer(GL_FRAMEBUFFER,fbo);
  }
  void frostBackdrop(int width, int height) {
    int w = std::max(1, width / 4), h = std::max(1, height / 4);
    if (w != blurWidth || h != blurHeight) {
      blurWidth = w;
      blurHeight = h;
      for (int i = 0; i < 2; i++) {
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, blurTex[i]);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA,
                     GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glBindFramebuffer(GL_FRAMEBUFFER, blurFbo[i]);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, blurTex[i], 0);
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
          throw std::runtime_error("Blur framebuffer");
      }
    }
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, blurFbo[0]);
    glBlitFramebuffer(0, 0, width, height, 0, 0, w, h, GL_COLOR_BUFFER_BIT,
                      GL_LINEAR);
    glViewport(0, 0, w, h);
    for (int pass = 0; pass < 2; pass++) {
      glBindFramebuffer(GL_FRAMEBUFFER, blurFbo[pass == 0 ? 1 : 0]);
      glUseProgram(blurProg);
      glUniform2f(glGetUniformLocation(blurProg, "direction"),
                  pass == 0 ? 1.5f / w : 0, pass == 1 ? 1.5f / h : 0);
      textured(blurProg, blurTex[pass == 0 ? 0 : 1], GL_TEXTURE_2D, identity(),
               -1, -1, 2, 2, false);
    }
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glViewport(0, 0, width, height);
    eyeWidth = width;
    eyeHeight = height;
  }
  void environment(const Mat& camera, const XrFovf& f) {
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glUseProgram(skyProg);
    glUniformMatrix4fv(glGetUniformLocation(skyProg, "camera"), 1, GL_FALSE,
                       camera.data());
    glUniform4f(glGetUniformLocation(skyProg, "fov"), tanf(f.angleLeft),
                tanf(f.angleRight), tanf(f.angleDown), tanf(f.angleUp));
    glUniform1f(glGetUniformLocation(skyProg, "floorY"), stageFromMap[13]);
    float v[] = {-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1, 1, 0};
    glBindBuffer(GL_ARRAY_BUFFER, quadVbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(v), v, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0);
    glDisableVertexAttribArray(1);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float), 0);
    glDrawArrays(GL_TRIANGLES, 0, 6);
  }
  void exportView(int eye,const Eye& e,int channel){
    int width,height,fps,slot=-1;float options[8];int64_t now=mono(),generation;
    {std::lock_guard<std::mutex> lock(dataMutex);auto& output=exportChannels[channel];generation=output.generation;width=output.width;height=output.height;fps=output.fps;memcpy(options,output.options,sizeof(options));
      if(!width||eye!=(int)options[7]||now<output.at)return;
      for(int i=channel*3;i<channel*3+3;i++)if(!exportSlots[i].busy){slot=i;exportSlots[i].busy=true;int64_t period=1000000000LL/fps;output.at=output.at==0||now-output.at>2*period?now+period:output.at+period;break;}
    }
    if(slot<0)return;auto& target=exportSlots[slot];
    if(!target.texture){glGenTextures(1,&target.texture);glGenFramebuffers(1,&target.framebuffer);}
    if(target.width!=width||target.height!=height){glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,target.texture);glTexImage2D(GL_TEXTURE_2D,0,GL_SRGB8_ALPHA8,width,height,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);textureParams();target.width=width;target.height=height;}
    // FOV is updated immediately before this call from the current predicted XR view.
    ViewCrop crop=viewCrop(exportEyeTangents[0],exportEyeTangents[1],exportEyeTangents[2],exportEyeTangents[3],float(width)/height,options);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER,target.framebuffer);glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,target.texture,0);
    glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo);glDisable(GL_SCISSOR_TEST);
    bool complete=glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE;
    if(complete)glBlitFramebuffer((int)std::lround(crop.x0*e.width),(int)std::lround(crop.y0*e.height),(int)std::lround(crop.x1*e.width),(int)std::lround(crop.y1*e.height),0,0,width,height,GL_COLOR_BUFFER_BIT,GL_LINEAR);
    GLsync fence=complete?glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE,0):nullptr;glFlush();glBindFramebuffer(GL_FRAMEBUFFER,fbo);
    bool accepted=false;
    if(fence){float effective[]={crop.x0,crop.y0,crop.x1,crop.y1,crop.horizontalDegrees,crop.verticalDegrees,float(e.width),float(e.height)};
      jfloatArray values=env->NewFloatArray(8);if(values){env->SetFloatArrayRegion(values,0,8,effective);accepted=env->CallBooleanMethod(owner,onExport,(jint)target.texture,(jint)slot,(jlong)now,(jlong)(uintptr_t)fence,values,(jlong)generation);env->DeleteLocalRef(values);}
      if(env->ExceptionCheck()){env->ExceptionClear();accepted=false;}
    }
    if(!accepted){if(fence)glDeleteSync(fence);std::lock_guard<std::mutex> lock(dataMutex);target.busy=false;}
  }
  float exportEyeTangents[4]={-1,1,-1,1};
  void frame() {
    XrFrameWaitInfo wi{XR_TYPE_FRAME_WAIT_INFO};
    XrFrameState fs{XR_TYPE_FRAME_STATE};
    check(xrWaitFrame(session, &wi, &fs), "wait frame");
    XrFrameBeginInfo bi{XR_TYPE_FRAME_BEGIN_INFO};
    check(xrBeginFrame(session, &bi), "begin frame");
    XrViewLocateInfo li{XR_TYPE_VIEW_LOCATE_INFO};
    li.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
    li.displayTime = fs.predictedDisplayTime;
    li.space = world;
    XrViewState vs{XR_TYPE_VIEW_STATE};
    uint32_t count = 2;
    XrView views[2] = {{XR_TYPE_VIEW}, {XR_TYPE_VIEW}};
    check(xrLocateViews(session, &li, &vs, 2, &count, views), "locate views");
    XrCompositionLayerProjectionView pv[2] = {
        {XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW},
        {XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW}};
    if (recenterTime && fs.predictedDisplayTime >= recenterTime) {
      if (originReady && recenterValid)
        stageFromMap = multiply(recenterTransform, stageFromMap);
      else
        originReady = false;
      if(sceneMode==3){std::lock_guard<std::mutex> lock(sceneMoveMutex);if(recenterValid&&sceneAnchorMode==3)sceneAnchor=multiply(recenterTransform,sceneAnchor);else sceneReset=true;}
      recenterTime = 0;
      env->CallVoidMethod(owner, onReferenceChange, (jboolean)recenterValid);
      if (env->ExceptionCheck()) env->ExceptionClear();
    }
    // SurfaceTexture is allowed to change external texture bindings: reserve
    // unit 2.
    glActiveTexture(GL_TEXTURE2);
    sample(fs.predictedDisplayTime, views);
    streamed->tick();livePoints->tick();
    {auto old=coloredScene.revision.load();coloredScene.tick();if(old!=coloredScene.revision.load())sceneReset=true;}
    glBindTexture(GL_TEXTURE_EXTERNAL_OES, 0);
    glActiveTexture(GL_TEXTURE0);
    upload();
    for(int stream=0;stream<6;stream++)resolveVideo(stream);
    glBindBuffer(GL_ARRAY_BUFFER, controllerVbo);
    glBufferData(GL_ARRAY_BUFFER, controllerLines.size() * sizeof(float),
                 controllerLines.data(), GL_STREAM_DRAW);
    bool draw = fs.shouldRender && foreground &&
                (vs.viewStateFlags & XR_VIEW_STATE_POSITION_VALID_BIT) &&
                (vs.viewStateFlags & XR_VIEW_STATE_ORIENTATION_VALID_BIT);
    XrSpaceLocation head{XR_TYPE_SPACE_LOCATION};
    xrLocateSpace(viewSpace, world, fs.predictedDisplayTime, &head);
    Mat rawHead = pose(head.pose);
    if (draw && (head.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT) &&
        (head.locationFlags & XR_SPACE_LOCATION_ORIENTATION_VALID_BIT) &&
        !originReady) {
      float yaw = atan2f(rawHead[8], rawHead[10]);
      stageFromMap = planar(
          rawHead[12],
          worldType == XR_REFERENCE_SPACE_TYPE_STAGE ? 0 : rawHead[13] - 1.6f,
          rawHead[14], yaw);
      originReady = true;
    }
    Mat car;
    {
      std::lock_guard<std::mutex> g(dataMutex);
      car = carInMap;
    }
    Mat carWorld = multiply(stageFromMap, car);
    if(showMap)renderOverview(car);
    // Display-only transform: actual operator pose serialization remains in
    // tracking space.
    Mat rig = followView && originReady
                  ? followRig(stageFromMap, carWorld, rawHead)
                  : identity();
    if (draw)
      for (int i = 0; i < 2; i++) {
        Eye& e = eyes[i];
        uint32_t image = 0;
        XrSwapchainImageAcquireInfo ai{XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO};
        check(xrAcquireSwapchainImage(e.swap, &ai, &image), "acquire image");
        XrSwapchainImageWaitInfo wait{XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO};
        wait.timeout = XR_INFINITE_DURATION;
        check(xrWaitSwapchainImage(e.swap, &wait), "wait image");
        glBindFramebuffer(GL_FRAMEBUFFER, fbo);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, e.images[image].image, 0);
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                  GL_RENDERBUFFER, e.depth);
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
          throw std::runtime_error("Framebuffer incomplete");
        glViewport(0, 0, e.width, e.height);
        glClearColor(.94f, .96f, .97f, 1);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        glBindVertexArray(vao);
        Mat camera = multiply(rig, pose(views[i].pose));
        Mat rawVp =
            multiply(projection(views[i].fov), inversePose(views[i].pose));
        Mat viewProjection = multiply(rawVp, rigidInverse(rig));
        environment(camera, views[i].fov);
        glEnable(GL_DEPTH_TEST);
        Mat mapVp = multiply(viewProjection, stageFromMap);
        drawColoredScene(rawVp,rawHead);drawStreamed(rawVp,rawHead);
        if(!sceneMode.load()){
        livePoints->draw(livePointProg,multiply(rawVp,stageFromMap),!swapSrgb);
        colored(lineVbo, lineCount, GL_LINES, mapVp);
        colored(carVbo, carVertices, GL_LINES,
                multiply(viewProjection, carWorld));
        glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);
        colored(armVbo,armCount,GL_LINES,multiply(viewProjection,carWorld));
        }
        glDisable(GL_DEPTH_TEST);glEnable(GL_BLEND);glBlendFunc(GL_ONE,GL_ONE_MINUS_SRC_ALPHA);
        if(!sceneMode.load())for(int side=0;side<2;side++)if(labelsReady&&labelAnchors[side*4+3]>=-1){
          Mat label=camera;for(int row=0;row<3;row++)label[12+row]=carWorld[12+row]+carWorld[row]*labelAnchors[side*4]+carWorld[4+row]*labelAnchors[side*4+1]+carWorld[8+row]*labelAnchors[side*4+2];
          labelIndex=side;textured(labelProg,labelTex,GL_TEXTURE_2D,multiply(viewProjection,label),-.14f,0,.28f,.14f,true);
        }
        Mat panel = carWorld;
        for (int row = 0; row < 3; row++)
          panel[12 + row] +=
              carWorld[4 + row] * 1.65f - carWorld[8 + row] * 3.8f;
        Mat worldPanelVp = multiply(viewProjection, panel);
        cameraListPanel=multiply(rigidInverse(rig),panel);cameraListPanelReady=sceneMode.load()==0||sceneMode.load()==3;
        frostBackdrop(e.width,e.height);
        if(cameraListPanelReady){int mode=videoMode.load();if(mode!=0)glassRect(worldPanelVp,mode==2?312:442,mode==2?152:212,mode==2?976:716,mode==2?556:409.75f);for(int stream=0;stream<5;stream++)glassRect(worldPanelVp,1306,150+170*stream,282,166);}
        if(showMap&&!sceneMode.load())glassRect(worldPanelVp,-288,142,282,246);
        glDisable(GL_DEPTH_TEST);
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
        int selected=selectedCamera.load();int mode=videoMode.load();
        if((sceneMode.load()==0||sceneMode.load()==3)&&mode!=0)drawVideoRect(selected,worldPanelVp,mode==2?320:450,mode==2?160:220,mode==2?960:700,mode==2?540:393.75f);
        if(sceneMode.load()==0||sceneMode.load()==3)for(int stream=0;stream<5;stream++)drawVideoRect(stream==4?5:stream,worldPanelVp,1314,158+170*stream,266,150);
        if(showMap&&!sceneMode.load()){glDisable(GL_BLEND);textured(resolvedVideoProg,mapTex,GL_TEXTURE_2D,worldPanelVp,(-280.f/1600-.5f)*6.6f,(.5f-(150.f+230)/1000)*4.125f,266.f/1600*6.6f,230.f/1000*4.125f,false);}
        frostBackdrop(e.width,e.height);glEnable(GL_BLEND);glBlendFunc(GL_ONE,GL_ONE_MINUS_SRC_ALPHA);
        if(worldHudWidth>0)textured(hudProg,worldHudTex,GL_TEXTURE_2D,worldPanelVp,-3.3f,-2.0625f,6.6f,4.125f,true);
        if (menuOpen) frostBackdrop(e.width, e.height);
        Mat hudPanel = rawHead;
        for (int row = 0; row < 3; row++)
          hudPanel[12 + row] -= rawHead[8 + row] * 2.2f;
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
        bool showArm;{std::lock_guard<std::mutex> lock(dataMutex);showArm=armCameraValid;}
        if(showArm&&!sceneMode.load()){
          Mat armVp=multiply(rawVp,hudPanel);
          float x=(1130.f/1600-.5f)*2.9f,y=(.5f-790.f/1000)*1.8125f,w=300.f/1600*2.9f,h=169.f/1000*1.8125f;
          textured(hudProg,plateTex,GL_TEXTURE_2D,armVp,x-.012f,y-.012f,w+.024f,h+.024f,false);
          if(videos[4].ready){float ratio=videos[4].aspect.load(),fw=w,fh=w/ratio;if(fh>h){fh=h;fw=h*ratio;}glDisable(GL_BLEND);textured(resolvedVideoProg,videos[4].texture,GL_TEXTURE_2D,armVp,x+(w-fw)*.5f,y+(h-fh)*.5f,fw,fh,false);glEnable(GL_BLEND);}
        }
        if (hudWidth > 0)
          textured(hudProg, hudTex, GL_TEXTURE_2D, multiply(rawVp, hudPanel),
                   -1.45f, -.90625f, 2.9f, 1.8125f, true);
        checkGl("eye_hud");
        glDisable(GL_BLEND);
        // Same raw tracking-space view as the HUD: rendered every predicted XR
        // frame.
        drawControllers(rawVp,inversePose(views[i].pose));
        colored(controllerVbo, controllerLines.size() / 7, GL_LINES, rawVp);
        if (i == 0 && videos[0].has && renderedFrames >= 60 &&
            captureRequested.exchange(false)) {
          std::vector<uint8_t> rgba(e.width * e.height * 4);
          glReadPixels(0, 0, e.width, e.height, GL_RGBA, GL_UNSIGNED_BYTE,
                       rgba.data());
          std::vector<jint> argb(e.width * e.height);
          for (uint32_t y = 0; y < e.height; y++)
            for (uint32_t x = 0; x < e.width; x++) {
              size_t source = ((e.height - 1 - y) * e.width + x) * 4;
              argb[y * e.width + x] =
                  (jint)((uint32_t)rgba[source + 3] << 24 |
                         (uint32_t)rgba[source] << 16 |
                         (uint32_t)rgba[source + 1] << 8 | rgba[source + 2]);
            }
          jintArray pixels = env->NewIntArray(argb.size());
          env->SetIntArrayRegion(pixels, 0, argb.size(), argb.data());
          env->CallVoidMethod(owner, onMirror, (jint)e.width, (jint)e.height,
                              pixels);
          env->DeleteLocalRef(pixels);
          if (env->ExceptionCheck()) env->ExceptionClear();
        }
        exportEyeTangents[0]=tanf(views[i].fov.angleLeft);exportEyeTangents[1]=tanf(views[i].fov.angleRight);exportEyeTangents[2]=tanf(views[i].fov.angleDown);exportEyeTangents[3]=tanf(views[i].fov.angleUp);
        exportView(i,e,0);exportView(i,e,1);
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glFlush();
        XrSwapchainImageReleaseInfo release{
            XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO};
        check(xrReleaseSwapchainImage(e.swap, &release), "release image");
        pv[i].pose = views[i].pose;
        pv[i].fov = views[i].fov;
        pv[i].subImage.swapchain = e.swap;
        pv[i].subImage.imageRect.extent = {(int32_t)e.width, (int32_t)e.height};
      }
    XrCompositionLayerProjection layer{XR_TYPE_COMPOSITION_LAYER_PROJECTION};
    layer.space = world;
    layer.viewCount = 2;
    layer.views = pv;
    const XrCompositionLayerBaseHeader* layers[] = {
        (XrCompositionLayerBaseHeader*)&layer};
    XrFrameEndInfo end{XR_TYPE_FRAME_END_INFO};
    end.displayTime = fs.predictedDisplayTime;
    end.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
    end.layerCount = draw ? 1 : 0;
    end.layers = draw ? layers : nullptr;
    check(xrEndFrame(session, &end), "end frame");
    if (draw) {
      renderedFrames++;
      env->CallVoidMethod(owner, onRendered);
      if (env->ExceptionCheck()) env->ExceptionClear();
    }
  }
  void loop() {
    while (!quit) {
      events();
      if (running) {
        frame();
      } else {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
      }
    }
  }
  void cleanup() {
    stopModelLoader();
    if (display != EGL_NO_DISPLAY && context != EGL_NO_CONTEXT)
      eglMakeCurrent(display, surface, surface, context);
    for (auto& e : eyes) {
      if (e.swap) xrDestroySwapchain(e.swap);
      if (e.depth) glDeleteRenderbuffers(1, &e.depth);
    }
    for (auto s : handSpace)
      if (s) xrDestroySpace(s);
    for (auto s : aimSpace)
      if (s) xrDestroySpace(s);
    if (viewSpace) xrDestroySpace(viewSpace);
    if (world) xrDestroySpace(world);
    if (session) xrDestroySession(session);
    if (actions) xrDestroyActionSet(actions);
    if (instance) xrDestroyInstance(instance);
    if (context != EGL_NO_CONTEXT) {
      GLuint buffers[] = {cloudVbo, lineVbo, quadVbo, controllerVbo, carVbo};
      glDeleteBuffers(5, buffers);
      GLuint textures[]={hudTex,worldHudTex,labelTex,mapTex};glDeleteTextures(4,textures);glDeleteFramebuffers(1,&mapFbo);glDeleteBuffers(1,&armVbo);glDeleteProgram(labelProg);
      for(auto& v:videos){GLuint names[]={v.external,v.texture};glDeleteTextures(2,names);glDeleteFramebuffers(1,&v.framebuffer);}
      glDeleteProgram(resolvedVideoProg);
      glDeleteProgram(skyProg);
      glDeleteProgram(blurProg);
      glDeleteTextures(2, blurTex);
      for(auto& slot:exportSlots){glDeleteTextures(1,&slot.texture);glDeleteFramebuffers(1,&slot.framebuffer);}
      glDeleteFramebuffers(2, blurFbo);
      for(auto& c:controllers)glDeleteBuffers(1,&c.vbo);
      glDeleteProgram(controllerProg);
      coloredScene.clear();streamed->clearGl();livePoints->clear();glDeleteProgram(livePointProg);glDeleteProgram(cloudProg);glDeleteProgram(sceneProg);
      glDeleteProgram(colorProg);
      glDeleteProgram(videoProg);
      glDeleteProgram(hudProg);glDeleteTextures(1,&plateTex);
      glDeleteFramebuffers(1, &fbo);
      glDeleteVertexArrays(1, &vao);
    }
    if (display != EGL_NO_DISPLAY) {
      eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
      if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
      if (context != EGL_NO_CONTEXT) eglDestroyContext(display, context);
      eglTerminate(display);
    }
  }
};
}  // namespace

std::shared_ptr<cloud::Gpu> cloudHandle(){std::lock_guard<std::mutex> g(lifecycle);return engine?engine->streamed:nullptr;}
cloud::Mat cloudAnchor(){std::lock_guard<std::mutex> g(lifecycle);if(!engine)return identity();std::lock_guard<std::mutex> lock(engine->sceneMoveMutex);return engine->sceneAnchor;}
std::array<float,3> cloudHead(){std::lock_guard<std::mutex> g(lifecycle);if(!engine)return {0,1.6f,0};std::lock_guard<std::mutex> lock(engine->sceneMoveMutex);return engine->cloudPosition;}
void cloudRecenter(float floor){std::lock_guard<std::mutex> g(lifecycle);if(engine){engine->cloudFloor=floor;engine->sceneReset=true;}}
#include "../../../../shared/src/main/cpp/cloud_jni_bridge.h"
extern "C" JNIEXPORT jstring JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_coloredSceneLoad(JNIEnv* e,jclass,jobject p,jobject c,jobject ix,jint n,jint faces){
  try{
    auto result=tlzscene::decode((const uint8_t*)e->GetDirectBufferAddress(p),(size_t)e->GetDirectBufferCapacity(p),
      (const uint8_t*)e->GetDirectBufferAddress(c),(size_t)e->GetDirectBufferCapacity(c),
      (const uint8_t*)e->GetDirectBufferAddress(ix),(size_t)e->GetDirectBufferCapacity(ix),n,faces);
    std::lock_guard<std::mutex> guard(lifecycle);if(!engine)return e->NewStringUTF("XR scene closed");
    __android_log_print(ANDROID_LOG_INFO,"TLZ2","COLORED_SCENE staged vertices=%zu triangles=%zu chunks=%zu bytes=%zu",result.vertices,result.triangles,result.chunks.size(),result.bytes);
    engine->coloredScene.submit(std::move(result));return nullptr;
  }catch(const std::exception& x){return e->NewStringUTF(x.what());}
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_coloredSceneView(JNIEnv*,jclass,jint mode,jboolean points,jboolean reset){
  std::lock_guard<std::mutex> guard(lifecycle);if(engine){engine->sceneMode=mode;engine->scenePoints=points;if(reset)engine->sceneReset=true;}
}
extern "C" JNIEXPORT jlongArray JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_coloredSceneStats(JNIEnv* e,jclass){
  jlong values[8]{};{std::lock_guard<std::mutex> guard(lifecycle);if(engine)for(int i=0;i<8;i++)values[i]=engine->coloredScene.stats[i].load();}
  jlongArray result=e->NewLongArray(8);e->SetLongArrayRegion(result,0,8,values);return result;
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_coloredSceneMove(JNIEnv*,jclass,jfloat x,jfloat z,jfloat yaw){
  std::lock_guard<std::mutex> guard(lifecycle);if(engine){std::lock_guard<std::mutex> move(engine->sceneMoveMutex);engine->sceneMoveX+=x;engine->sceneMoveZ+=z;engine->sceneMoveYaw+=yaw;}
}
extern "C" JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* v, void*) {
  vm = v;
  return JNI_VERSION_1_6;
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_start(JNIEnv* e, jclass,
                                                       jobject owner) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) return;
  engine = new Engine();
  engine->launch(e, owner);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_active(JNIEnv*, jclass,
                                                        jboolean b) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) engine->foreground = b;
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_stop(JNIEnv*, jclass) {
  Engine* old;
  {
    std::lock_guard<std::mutex> g(lifecycle);
    old = engine;
    engine = nullptr;
    if (old) old->quit = true;
  }
  if (old) {
    if (old->worker.joinable()) old->worker.join();
    delete old;
  }
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_haptic(JNIEnv*, jclass) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) engine->vibrate.fetch_or(3);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_hapticHand(JNIEnv*, jclass,
                                                            jint mask) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) engine->vibrate.fetch_or(mask & 3);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_presentation(JNIEnv*, jclass,
                                                              jint video,
                                                              jboolean map,
                                                              jboolean menu) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) {
    engine->videoMode = video;
    engine->showMap = map;
    engine->menuOpen = menu;
  }
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_captureDemo(JNIEnv*, jclass) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) engine->captureRequested = true;
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoMatrix(JNIEnv* env,
                                                             jclass,
                                                             jfloatArray a) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine && env->GetArrayLength(a) == 16) {
    env->GetFloatArrayRegion(a, 0, 16, engine->videos[0].uv.data());
    engine->videos[0].has = true;
    engine->videos[0].dirty = true;
  }
}
void geometry(JNIEnv* env, jfloatArray array, bool isLine) {
  std::lock_guard<std::mutex> guard(lifecycle);
  if (!engine) return;
  jsize n = env->GetArrayLength(array);
  if (n < 0 || n % 7 || n > 60000 * 7) return;
  std::vector<float> data(n);
  env->GetFloatArrayRegion(array, 0, n, data.data());
  std::lock_guard<std::mutex> lock(engine->dataMutex);
  if (isLine) {
    engine->lines = std::move(data);
    engine->linesDirty = true;
  } else {
    engine->points = std::move(data);
    engine->pointsDirty = true;
  }
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_cloud(JNIEnv* e, jclass,
                                                       jfloatArray a) {
  geometry(e, a, false);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_lines(JNIEnv* e, jclass,
                                                       jfloatArray a) {
  geometry(e, a, true);
}
void uploadHudBitmap(JNIEnv* env, jobject bitmap, bool worldLayer) {
  std::lock_guard<std::mutex> guard(lifecycle);
  if (!engine) return;
  AndroidBitmapInfo info{};
  if (AndroidBitmap_getInfo(env, bitmap, &info) !=
          ANDROID_BITMAP_RESULT_SUCCESS ||
      info.format != ANDROID_BITMAP_FORMAT_RGBA_8888 || info.width > 2048 ||
      info.height > 1024)
    return;
  void* pixels = nullptr;
  if (AndroidBitmap_lockPixels(env, bitmap, &pixels) !=
      ANDROID_BITMAP_RESULT_SUCCESS)
    return;
  {
    std::lock_guard<std::mutex> lock(engine->dataMutex);
    auto& bytes = worldLayer ? engine->worldHudPixels : engine->hudPixels;
    bytes.resize(info.width * info.height * 4);
    for (uint32_t y = 0; y < info.height; y++)
      memcpy(bytes.data() + y * info.width * 4,
             (uint8_t*)pixels + y * info.stride, info.width * 4);
    if (worldLayer) {
      engine->worldHudWidth = info.width;
      engine->worldHudHeight = info.height;
      engine->worldHudDirty = true;
    } else {
      engine->hudWidth = info.width;
      engine->hudHeight = info.height;
      engine->hudDirty = true;
    }
  }
  AndroidBitmap_unlockPixels(env, bitmap);
}

extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_hud(JNIEnv* e, jclass,
                                                     jobject b) {
  uploadHudBitmap(e, b, false);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_worldHud(JNIEnv* e, jclass,
                                                          jobject b) {
  uploadHudBitmap(e, b, true);
}
extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_scenePose(JNIEnv*, jclass,
                                                           jfloat x, jfloat y,
                                                           jfloat z, jfloat yaw,
                                                           jboolean follow) {
  if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z) ||
      !std::isfinite(yaw))
    return;
  std::lock_guard<std::mutex> g(lifecycle);
  if (!engine) return;
  std::lock_guard<std::mutex> lock(engine->dataMutex);
  engine->carInMap = planar(x, y, z, yaw);
  engine->followView = follow;
}

extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoReset(JNIEnv*, jclass) {
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) {
    engine->videos[0].has = false;
    engine->videos[0].ready = false;
  }
}

extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoAspect(JNIEnv*, jclass,
                                                             jfloat ratio) {
  if (!std::isfinite(ratio) || ratio < .1f || ratio > 10) return;
  std::lock_guard<std::mutex> g(lifecycle);
  if (engine) engine->videos[0].aspect = ratio;
}

extern "C" JNIEXPORT void JNICALL
Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoSize(JNIEnv*, jclass,
                                                           jint w, jint h) {
  std::lock_guard<std::mutex> guard(lifecycle);
  if (engine && w > 0 && h > 0 && w <= 16384 && h <= 16384) {
    engine->videos[0].width = w;
    engine->videos[0].height = h;
  }
}

extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoFrame(JNIEnv* e,jclass,jint index,jfloatArray matrix,jint w,jint h,jfloat ratio){
 std::lock_guard<std::mutex> g(lifecycle);if(!engine||index<0||index>5||e->GetArrayLength(matrix)!=16)return;auto& v=engine->videos[index];e->GetFloatArrayRegion(matrix,0,16,v.uv.data());if(w>0&&h>0&&w<=16384&&h<=16384){v.width=w;v.height=h;}if(std::isfinite(ratio)&&ratio>.1f&&ratio<10)v.aspect=ratio;v.has=true;v.dirty=true;
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoStreamReset(JNIEnv*,jclass,jint index){std::lock_guard<std::mutex> g(lifecycle);if(engine&&index>=0&&index<6){engine->videos[index].has=false;engine->videos[index].ready=false;}}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoSource(JNIEnv*,jclass,jboolean depth){std::lock_guard<std::mutex> g(lifecycle);if(engine){engine->depthSelected=depth;engine->selectedCamera=depth?1:0;}}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_armLines(JNIEnv* e,jclass,jfloatArray data,jfloatArray anchors){
 std::lock_guard<std::mutex> g(lifecycle);if(!engine||e->GetArrayLength(data)>14000||e->GetArrayLength(data)%7||e->GetArrayLength(anchors)!=8)return;std::lock_guard<std::mutex> lock(engine->dataMutex);engine->armData.resize(e->GetArrayLength(data));e->GetFloatArrayRegion(data,0,engine->armData.size(),engine->armData.data());e->GetFloatArrayRegion(anchors,0,8,engine->labelAnchors);engine->armDirty=true;
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_gripLabels(JNIEnv* e,jclass,jobject bitmap){
 std::lock_guard<std::mutex> g(lifecycle);if(!engine)return;AndroidBitmapInfo info{};if(AndroidBitmap_getInfo(e,bitmap,&info)!=0||info.width!=512||info.height!=128||info.format!=ANDROID_BITMAP_FORMAT_RGBA_8888)return;void* pixels=nullptr;if(AndroidBitmap_lockPixels(e,bitmap,&pixels)!=0)return;{std::lock_guard<std::mutex> lock(engine->dataMutex);engine->labelPixels.resize(512*128*4);for(int y=0;y<128;y++)memcpy(engine->labelPixels.data()+y*512*4,(uint8_t*)pixels+y*info.stride,512*4);engine->labelDirty=true;}AndroidBitmap_unlockPixels(e,bitmap);
}

static void configureExport(JNIEnv* e,int channel,int w,int h,int fps,jfloatArray options,jlong generation){
 std::lock_guard<std::mutex> guard(lifecycle);if(!engine||channel<0||channel>1)return;
 if(w<0||h<0||w>2560||h>2560||(int64_t)w*h>3686400||fps<5||fps>60||e->GetArrayLength(options)!=8)return;
 std::lock_guard<std::mutex> lock(engine->dataMutex);auto& output=engine->exportChannels[channel];
 if(!w||output.width!=w||output.height!=h||output.fps!=fps)output.at=0;
 output.generation=generation;output.width=w;output.height=h;output.fps=fps;e->GetFloatArrayRegion(options,0,8,output.options);
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_captureConfigure(JNIEnv* e,jclass,jint w,jint h,jint fps,jfloatArray options,jlong generation){configureExport(e,0,w,h,fps,options,generation);}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_captureConfigureTrack(JNIEnv* e,jclass,jint channel,jint w,jint h,jint fps,jfloatArray options,jlong generation){configureExport(e,channel,w,h,fps,options,generation);}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_captureReleased(JNIEnv*,jclass,jint index){
 std::lock_guard<std::mutex> guard(lifecycle);if(!engine||index<0||index>=6)return;std::lock_guard<std::mutex> lock(engine->dataMutex);engine->exportSlots[index].busy=false;
}

extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_liveCloudReset(JNIEnv*,jclass,jlong generation){std::lock_guard<std::mutex> lock(lifecycle);if(engine)engine->livePoints->reset(generation);}
extern "C" JNIEXPORT jboolean JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_liveCloud(JNIEnv* e,jclass,jlong generation,jobject points,jfloatArray transform){
 auto raw=(const uint8_t*)e->GetDirectBufferAddress(points);auto bytes=e->GetDirectBufferCapacity(points);if(bytes<0||bytes>1920000||bytes%16||e->GetArrayLength(transform)!=16)return false;
 std::vector<uint8_t> copy(bytes);if(bytes)memcpy(copy.data(),raw,bytes);livecloud::Mat matrix{};e->GetFloatArrayRegion(transform,0,16,matrix.data());
 std::lock_guard<std::mutex> lock(lifecycle);return engine&&engine->livePoints->offer(generation,std::move(copy),matrix);
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_liveCloudVisible(JNIEnv*,jclass,jboolean visible){std::lock_guard<std::mutex> lock(lifecycle);if(engine)engine->livePoints->visible=visible;}
extern "C" JNIEXPORT jlongArray JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_liveCloudStats(JNIEnv* e,jclass){jlong values[4]{};{std::lock_guard<std::mutex> lock(lifecycle);if(engine)for(int i=0;i<4;i++)values[i]=engine->livePoints->stats[i].load();}auto a=e->NewLongArray(4);e->SetLongArrayRegion(a,0,4,values);return a;}

extern "C" JNIEXPORT jint JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoTexture(JNIEnv*,jclass,jint stream){std::lock_guard<std::mutex> guard(lifecycle);return engine&&stream>=0&&stream<6?engine->videos[stream].external:0;}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_videoSelection(JNIEnv*,jclass,jint stream){std::lock_guard<std::mutex> guard(lifecycle);if(engine&&stream>=0&&(stream<4||stream==5))engine->selectedCamera=stream;}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_controlterminal_vr_v2_NativeVr_armCamera(JNIEnv* e,jclass,jfloatArray position,jboolean valid,jboolean large){if(e->GetArrayLength(position)!=3)return;std::array<float,3> p;e->GetFloatArrayRegion(position,0,3,p.data());for(float x:p)if(!std::isfinite(x))return;std::lock_guard<std::mutex> guard(lifecycle);if(engine){std::lock_guard<std::mutex> data(engine->dataMutex);engine->armCameraPosition=p;engine->armCameraValid=valid;engine->armCameraLarge=large;}}
