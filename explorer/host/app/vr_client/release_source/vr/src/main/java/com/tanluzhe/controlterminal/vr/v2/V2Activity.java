package com.tanluzhe.controlterminal.vr.v2;

import android.app.*;
import android.graphics.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import com.tanluzhe.controlterminal.vr.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.webrtc.*;
import com.tanluzhe.cloud.*;

/** Real binocular OpenXR scene. Demo and live sessions are intentionally different lifetimes. */
public final class V2Activity extends Activity {
  private static final java.util.concurrent.ExecutorService xrLifecycle =
      java.util.concurrent.Executors.newSingleThreadExecutor();
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Dashboard ui = new Dashboard();
  private final SceneStore scene = new SceneStore();
  private final VrUiState controls = new VrUiState();
  private final VrHud hud = new VrHud();
  private InputMode inputMode;
  private static volatile java.lang.ref.WeakReference<V2Activity> current =
      new java.lang.ref.WeakReference<>(null);
  public static V2Activity current() {
    return current.get();
  }
  private volatile String[] pendingLogs;
  private long lastInputLog;
  private InputMode.Mode previousMode = InputMode.Mode.IDLE;
  private final AtomicBoolean exiting = new AtomicBoolean();
  private final AtomicBoolean videoPending = new AtomicBoolean();
  private final AtomicBoolean captureWriting = new AtomicBoolean();
  private volatile SurfaceTexture videoTexture;
  private volatile Surface videoSurface;
  private volatile DirectHevcVideo hevc,hevcDepth;
  private ViewCapture viewCapture;
  private volatile AipcTelemetry telemetryClient;
  private volatile SurfaceTexture depthTexture;
  private volatile Surface depthSurface;
  private final AtomicBoolean depthPending=new AtomicBoolean(),logLoading=new AtomicBoolean();
  private final Dashboard rgbState=new Dashboard(),depthState=new Dashboard();
  private final ArmGeometry armGeometry=new ArmGeometry();
  private final Bitmap gripBitmap=Bitmap.createBitmap(512,128,Bitmap.Config.ARGB_8888);
  private final long[] videoAt=new long[CameraLayout.KINDS.length],videoCounts=new long[CameraLayout.KINDS.length];
  private final SurfaceTexture[] cameraTextures=new SurfaceTexture[6];
  private final Surface[] cameraSurfaces=new Surface[6];
  private final DirectHevcVideo[] cameras=new DirectHevcVideo[6];
  private final Dashboard[] cameraStates={rgbState,depthState,new Dashboard(),new Dashboard(),new Dashboard(),new Dashboard()};
  private final AtomicBoolean[] cameraPending={videoPending,depthPending,new AtomicBoolean(),new AtomicBoolean(),new AtomicBoolean(),new AtomicBoolean()};
  private volatile boolean rightCameraPose;
  private boolean camera1Demand;
  private long deviceAt;

  private String targetHost;
  private final AtomicBoolean reconnecting = new AtomicBoolean();
  private volatile BaseLink link;
  private boolean demo,sceneBrowser;
  private ColoredSceneLoader coloredLoader;
  private SceneModeController sceneModes;
  private CloudStream cloudStream;private boolean startCloud;
  private long sceneMoveAt;private boolean sceneSnapHeld;
  private volatile boolean closed, resumed;
  private long lastCloud, lastWorldHud, lastDemoVideo, fpsAt, fpsFrames;
  private volatile int lastHapticResult = Integer.MIN_VALUE;
  private volatile long hapticPulses;
  private volatile int seenButtons, seenVideoModes = 2, seenAnalog;
  private volatile long uiClicks;
  private volatile boolean menuOpened;
  private volatile boolean awaitGripRelease = true;
  private long demoTime;
  private float demoX, demoZ;
  private volatile float[] displayedCar = new float[4];
  private volatile boolean glReady;
  private volatile long frameCount, renderedFrames;
  private volatile int trackingFlags;
  private volatile float[] latestControllerBounds;
  private int lastLeftModel=-2,lastRightModel=-2;
  private volatile String nativeError = "";
  private String runId = "";
  private long lastDiagnostics;
  private final Bitmap hudBitmap =
      Bitmap.createBitmap(VrUiState.WIDTH, VrUiState.HEIGHT, Bitmap.Config.ARGB_8888);
  private final Bitmap worldBitmap =
      Bitmap.createBitmap(VrUiState.WIDTH, VrUiState.HEIGHT, Bitmap.Config.ARGB_8888);
  private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    AppLog.init(this, "vr");
    current = new java.lang.ref.WeakReference<>(this);
    viewCapture=new ViewCapture(this);
    ConnectionSettings settings = new ConnectionSettings(this);
    inputMode = new InputMode(settings.press, settings.release, settings.deadzone);
    AppLog.info("XR", "ACTIVITY_CREATE",
        "version=" + BuildConfig.VERSION_NAME + " input revision=1 Hz=" + settings.observationHz);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    sceneBrowser=false; // legacy standalone scene intents no longer create a separate page.
    controls.sceneBrowser=false;startCloud=false;
    if(sceneBrowser)coloredLoader=new ColoredSceneLoader(this);
    demo = sceneBrowser||getIntent().getBooleanExtra("demo", true);
    runId = getIntent().getStringExtra("run_id");
    if (runId == null)
      runId = java.util.UUID.randomUUID().toString();
    sceneModes=new SceneModeController(this,controls,demo);
    ui.simulation = demo;
    TextView loading = new TextView(this);
    loading.setText("探路者-控制终端\n正在初始化 OpenXR…\n"
        + (sceneBrowser ? "真实实验室扫描 / GPU 场景浏览" : demo ? "虚拟演示，不连接机器人" : "AIPC 直连 / HEVC 视频"));
    loading.setTextSize(26);
    loading.setTextColor(Color.WHITE);
    loading.setBackgroundColor(0xffedf4f6);
    TerminalStyle.apply(loading);
    setContentView(loading);
    if(!sceneBrowser)PeerConnectionFactory.initialize(
        PeerConnectionFactory.InitializationOptions.builder(this).createInitializationOptions());
    if (!demo)
      targetHost = getIntent().getStringExtra("host");
    xrLifecycle.execute(() -> {
      if (closed)
        return;
      try {
        NativeVr.start(this);
      } catch (Throwable e) {
        onNativeError(e.getMessage());
      }
    });
    main.post(hudTask);
  }
  /** Called on native GL thread with a current GLES context. */
  public void onGlReady(int texture,int secondTexture) {
    if (closed)
      return;
    glReady = true;main.post(()->{if(!closed)sceneModes.ready();});
    android.opengl.EGLContext share=android.opengl.EGL14.eglGetCurrentContext();main.post(()->{if(!closed)viewCapture.attach(share);});
    NativeVr.active(resumed);
    AppLog.info("XR", "GL_READY", sceneBrowser ? "真实扫描场景，不创建机器人控制会话" : demo ? "本地演示，不创建网络连接" : "图形就绪，开始AIPC协商");
    if(sceneBrowser){
      ui.simulation=false;ui.connection="有色场景浏览";ui.targetAddress="独立浏览 / 不发布机器人输入";
      controls.videoMode=0;controls.mapVisible=false;
      NativeVr.coloredSceneView(1,false,true);NativeVr.presentation(0,false,controls.modal());
      if(startCloud)startCloudStream();else coloredLoader.load(false);return;
    }
    videoTexture = new SurfaceTexture(texture);
    videoTexture.setDefaultBufferSize(1280, 720);
    videoTexture.setOnFrameAvailableListener(s -> videoPending.set(true), main);
    videoSurface = new Surface(videoTexture);
    depthTexture=new SurfaceTexture(secondTexture);depthTexture.setDefaultBufferSize(1280,720);depthTexture.setOnFrameAvailableListener(t->depthPending.set(true),main);depthSurface=new Surface(depthTexture);
    controls.rightCameraVisible=getSharedPreferences("v2",0).getBoolean("right_camera_visible",true);
    cameraTextures[0]=videoTexture;cameraTextures[1]=depthTexture;cameraSurfaces[0]=videoSurface;cameraSurfaces[1]=depthSurface;
    for(int i=2;i<6;i++){final int index=i;SurfaceTexture tex=new SurfaceTexture(NativeVr.videoTexture(i));tex.setDefaultBufferSize(1280,720);tex.setOnFrameAvailableListener(t->cameraPending[index].set(true),main);cameraTextures[i]=tex;cameraSurfaces[i]=new Surface(tex);}
    if (demo) {
      NativeVr.captureDemo();
      ui.connection = "本地输入演示";ui.targetAddress="离线演示";
      ui.lease = "离线 / 不连接AIPC";
      ui.robot = "虚拟机器人";
      NativeVr.presentation(controls.videoMode, controls.mapVisible, controls.modal());
      scene.transform(1, new float[] {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1});
    } else {
      main.post(() -> {
        if (closed)
          return;
        ConnectionSettings settings = new ConnectionSettings(this);
        try{java.net.URI media=new java.net.URI(CameraLayout.origin(getSharedPreferences("v2",0).getString("native_media_url","http://192.168.137.2:8096")));for(int i=0;i<6;i++){cameras[i]=new DirectHevcVideo(this,media.getHost(),media.getPort()<0?80:media.getPort(),"1",cameraSurfaces[i],cameraStates[i],CameraLayout.KINDS[i],i==4?"240p15":"720p30");cameras[i].foreground(resumed&&i!=4);cameras[i].start();}hevc=cameras[0];hevcDepth=cameras[1];}catch(Exception e){AppLog.warn("VIDEO","MEDIA_CONFIG",AppLog.reason(e));}
        ui.targetAddress=targetHost+":"+settings.port;
        telemetryClient=new AipcTelemetry(targetHost,settings.telemetryPort,settings.token,ui);telemetryClient.foreground(resumed);telemetryClient.start();
        connectInput();
      });
    }
  }
  public boolean onViewCaptureFrame(int texture,int slot,long time,long fence,float[] crop,long generation){return !closed&&viewCapture!=null&&viewCapture.frame(texture,slot,time,fence,crop,generation);}
  private void startCloudStream(){
    if(closed||exiting.get())return;
    if(cloudStream!=null)cloudStream.close();
    controls.cloudMode=true;controls.sceneView=2;NativeVr.coloredSceneView(3,true,true);
    CloudNative.recenter(CloudSettings.prefs(this).getFloat("floor_y",0));
    try{cloudStream=new CloudStream(CloudSettings.config(this),CloudSettings.cache(this),CloudNative.sink());CloudStream selected=cloudStream;new Thread(()->{CloudSettings.seedCoarse(this,selected);if(!closed)selected.start();},"cloud-bootstrap").start();controls.cloudInfo="鉴权 / 读取场景";}
    catch(Exception e){controls.cloudInfo="请先在设置配置独立点云令牌";controls.sceneError=e.getMessage();}
  }
  private void stopCloud(){if(cloudStream!=null){cloudStream.close();cloudStream=null;}controls.cloudMode=false;CloudNative.configure(0,new String[0],new float[0]);}
  private void captureAction(int action){
    if(viewCapture==null)return;CaptureConfig c=viewCapture.config();
    if(action==VrUiState.RECORD)return;if(action==VrUiState.LIVE){if(controls.capturePanel)viewCapture.cancelStreamFromMenu();return;}
    int w=c.width,h=c.height,eye=c.eye;float f=c.verticalFov,l=c.left,r=c.right,t=c.top,b=c.bottom,cx=c.centerX,cy=c.centerY;
    if(action==VrUiState.FOV_MINUS)f=Math.max(20,f-5);if(action==VrUiState.FOV_PLUS)f=Math.min(120,f+5);
    if(action==VrUiState.MARGIN_MINUS){l=Math.max(0,l-.02f);r=Math.max(0,r-.02f);t=Math.max(0,t-.02f);b=Math.max(0,b-.02f);}
    if(action==VrUiState.MARGIN_PLUS){l=Math.min(.45f,l+.02f);r=Math.min(.45f,r+.02f);t=Math.min(.45f,t+.02f);b=Math.min(.45f,b+.02f);}
    if(action==VrUiState.EYE)eye=1-eye;
    if(action==VrUiState.PROFILE){int[][] sizes={{1280,720},{960,720},{720,1280},{1024,1024},{1920,1080}};int at=0;for(int i=0;i<sizes.length;i++)if(sizes[i][0]==w&&sizes[i][1]==h)at=i+1;w=sizes[at%sizes.length][0];h=sizes[at%sizes.length][1];}
    if(action==VrUiState.CAPTURE_RESET)viewCapture.change(CaptureConfig.defaults());else viewCapture.change(new CaptureConfig(w,h,c.fps,c.bitrate,eye,f,l,r,t,b,cx,cy));
  }
  private void connectInput() {
    if (closed || exiting.get())
      return;
    ConnectionSettings settings = new ConnectionSettings(this);
    BaseLink next =
        new BaseLink(this, targetHost, settings.port, settings.token, null, null, ui, scene);
    next.bootId = runId;
    next.gate.foreground = resumed;
    next.disconnected = () -> {
      if (closed || exiting.get() || !reconnecting.compareAndSet(false, true))
        return;
      main.postDelayed(()
                           -> xrLifecycle.execute(() -> {
        next.close();
        main.post(() -> {
          reconnecting.set(false);
          if (closed || exiting.get())
            return;
          scene.clear();
          ui.stateReceived = 0;
          displayedCar = new float[4];
          NativeVr.cloud(new float[0]);
          NativeVr.lines(new float[0]);
          connectInput();
        });
      }),
          1000);
    };
    link = next;
    next.connect();
  }
  /**
   * Native render thread calls once per XR frame. No networking or disk work blocks this callback.
   */
  public void onVrFrame(float[] poses, float[] axes, float[] eyes, float[] pointers, float[] controllerBounds, int tracking,
      int buttons, int activeHands, int sessionState, long sampleTime) {
    if (closed || exiting.get())
      return;
    frameCount++;
    latestControllerBounds=controllerBounds;
    if(lastLeftModel!=(int)controllerBounds[6]||lastRightModel!=(int)controllerBounds[13]){
      lastLeftModel=(int)controllerBounds[6];lastRightModel=(int)controllerBounds[13];
      AppLog.info("XR","CONTROLLER_MODEL","left="+lastLeftModel+" right="+lastRightModel+"; -1=not rendered, 0=matte fallback, 1=official runtime GLB; key14 revision=1");
    }
    trackingFlags=tracking;for(int i=0;i<6;i++)latchVideo(i,sampleTime);
    controls.tracking = tracking;
    controls.activeHands = activeHands;
    controls.sessionState = sessionState;
    controls.axes = axes.clone();
    boolean focused = sessionState == 5; // XR_SESSION_STATE_FOCUSED
    int action = controls.pointerAction(pointers, focused);
    int edges = controls.buttonEdges(buttons, focused);
    if (!focused)
      awaitGripRelease = true;
    else if (pointers[6] < .25f && pointers[7] < .25f)
      awaitGripRelease = false;
    if(focused)controls.navigate(Math.abs(axes[1])>=Math.abs(axes[3])?axes[1]:axes[3],sampleTime);
    if (edges != 0) {
      seenButtons |= edges;
      AppLog.info("UI", "BUTTON",
          "buttons=" + edges + "; ABXY and stick clicks report-only; dedicated menu shortcut");
      int localAction = controls.localButtonAction(edges);
      if (localAction != 0) {
        NativeVr.hapticHand(((edges & 16) != 0 ? 1 : 0) | ((edges & 96) != 0 ? 2 : 0));
        perform(localAction);action=0;
      }
    }
    if (action != 0) {
      uiClicks++;
      NativeVr.hapticHand(pointers[5] > .65f ? 2 : 1);
      perform(action);
    }
    if (Math.abs(axes[0]) + Math.abs(axes[1]) > .3f)
      seenAnalog |= 1;
    if (Math.abs(axes[2]) + Math.abs(axes[3]) > .3f)
      seenAnalog |= 2;
    if (pointers[4] > .5f)
      seenAnalog |= 4;
    if (pointers[5] > .5f)
      seenAnalog |= 8;
    if (pointers[6] > .5f)
      seenAnalog |= 16;
    if (pointers[7] > .5f)
      seenAnalog |= 32;
    if (exiting.get())
      return;
    InputControls raw = InputControls.nativeSample(axes, pointers, focused);
    controls.raw = raw;
    controls.faceButtons = FaceButtons.nativeSample(buttons, pointers, focused);
    controls.stickButtons=StickButtons.nativeSample(buttons,pointers,focused);
    InputMode.Mode mode =
        inputMode.update(raw, focused, tracking, controls.blocksControl() || awaitGripRelease);
    controls.modeLabel = (mode == InputMode.Mode.ARMS                   ? "双臂输入"
                                 : mode == InputMode.Mode.VEHICLE_LEFT  ? "左摇杆车辆"
                                 : mode == InputMode.Mode.VEHICLE_RIGHT ? "右摇杆车辆"
                                                                        : "待命")
        + " · 预览";
    controls.modeReason = inputMode.reason;
    if (mode != previousMode) {
      AppLog.info(
          "INPUT", "MODE_PREVIEW", previousMode + " -> " + mode + "; AIPC owns motion mapping");
      previousMode = mode;
    }
    if (!sceneBrowser && link != null) {
      BaseLink.Input input = new BaseLink.Input();
      input.poses = poses;
      input.axes = axes;
      input.eyes = eyes;
      input.controllerBounds = controllerBounds;
      input.controls = raw;
      input.faceButtons = controls.faceButtons;input.stickButtons=controls.stickButtons;
      input.flags = (tracking & 7) | (mode != InputMode.Mode.IDLE ? 8 : 0);
      input.time = sampleTime;
      link.input(input);
    }
    if (sampleTime - lastInputLog > 1_000_000_000L) {
      lastInputLog = sampleTime;
      AppLog.info("INPUT", "SAMPLE",
          "valid=" + raw.valid + " face_valid=" + controls.faceButtons.valid
              + " face_pressed=" + controls.faceButtons.pressed + " tracking=" + tracking
              + " mode=" + mode + " grips=" + raw.leftGrip + "," + raw.rightGrip
              + " triggers=" + raw.leftTrigger + "," + raw.rightTrigger);
    }
    if(sceneBrowser){
      double dt=sceneMoveAt==0?0:Math.min(.05,Math.max(0,(sampleTime-sceneMoveAt)/1e9));sceneMoveAt=sampleTime;
      if(focused&&!controls.modal()){
        float speed=controls.sceneView==1?.25f:1f;
        float x=Math.abs(axes[0])>.18f?axes[0]*speed*(float)dt:0,z=Math.abs(axes[1])>.18f?-axes[1]*speed*(float)dt:0;
        boolean snap=Math.abs(axes[2])>.7f;float yaw=snap&&!sceneSnapHeld?(axes[2]>0?-.5235988f:.5235988f):0;sceneSnapHeld=snap;
        float hx=poses[3],hy=poses[4],hz=poses[5],hw=poses[6];
        float heading=(float)Math.atan2(2*hx*hz+2*hw*hy,1-2*hx*hx-2*hy*hy),cy=(float)Math.cos(heading),sy=(float)Math.sin(heading);
        NativeVr.coloredSceneMove(-(cy*x+sy*z),-(-sy*x+cy*z),yaw);
      }else sceneSnapHeld=true;
      return;
    }
    float[] car = !demo && link != null ? link.robotScene.displayBase(sampleTime) : null;
    controls.vehiclePoseFresh = car != null;
    if (car != null)
      displayedCar = car;
    float[] shownCar = displayedCar;
    NativeVr.scenePose(shownCar[0], shownCar[1], shownCar[2], shownCar[3], controls.followView);
    NativeVr.armLines(armGeometry.sample(ui.telemetry,sampleTime),armGeometry.labels);
    float[] cameraAnchor=armGeometry.rightCameraAnchor();rightCameraPose=controls.rightCameraVisible&&!controls.integratedStatic&&!sceneBrowser;
    NativeVr.armCamera(cameraAnchor==null?new float[3]:cameraAnchor,rightCameraPose,CameraLayout.rightEnabled(ui.telemetry,sampleTime));
    if (sampleTime - lastCloud > 66_000_000L) {
      lastCloud = sampleTime;
      if (demo)
        demoGeometry(sampleTime);
      else {
        scene.expire(sampleTime);
        if (scene.dirty)
          NativeVr.cloud(scene.vertices());
        if (link != null)
          NativeVr.lines(link.robotScene.lines(sampleTime));
      }
    }
  }
  public void onReferenceSpaceChanged(boolean valid) {
    if (closed)
      return;
    awaitGripRelease = true;
    if(sceneBrowser)NativeVr.coloredSceneView(controls.sceneView,controls.scenePointMode,true);
    inputMode.reset("显示参考空间变化");
    controls.feedback = "显示空间已重置，原始采样仍由AIPC解释";
    AppLog.warn("XR", "REFERENCE_SPACE_CHANGED", "display transform valid=" + valid);
  }
  public void onInputProfiles(String left, String right) {
    controls.leftProfile = left;
    controls.rightProfile = right;
  }
  public boolean onUiOcclusion(float u,float v){return controls.occludes(u,v);}
  public void onHapticResult(int hands, int result) {
    lastHapticResult = result;
    if (result >= 0)
      hapticPulses++;
  }
  public SceneExtensions sceneExtensions(){if(sceneModes==null)throw new IllegalStateException("场景尚未初始化");return sceneModes.extensions;}
  public SceneExtensions.Context sceneExtensionContext(){if(android.os.Looper.myLooper()!=android.os.Looper.getMainLooper())throw new IllegalStateException("场景上下文请在主线程读取");return sceneModes.extensionContext();}
  private void perform(int action) {
    if(controls.interactionLocked)return;
    awaitGripRelease = true;
    if (action == VrUiState.EXIT) {
      if (controls.menuOpen)
        exitToSettings();
      else
        perform(VrUiState.MENU);
      return;
    }
    AppLog.info("UI", "ACTION", "action=" + action);
    if(sceneModes!=null&&sceneModes.action(action))return;
    if(sceneBrowser&&action>=VrUiState.CLOUD_START){
      if(action==VrUiState.CLOUD_START){startCloudStream();return;}
      if(action==VrUiState.CLOUD_NEXT){
        try{org.json.JSONArray a=new org.json.JSONArray(cloudStream==null?"[]":cloudStream.catalog);String current=CloudSettings.prefs(this).getString("scene",CloudStream.DENSE);int at=-1;for(int i=0;i<a.length();i++){org.json.JSONObject j=a.getJSONObject(i);if(current.equals(j.optString("id",j.optString("scene_id",""))))at=i;}if(a.length()>0){org.json.JSONObject j=a.getJSONObject((at+1)%a.length());CloudSettings.prefs(this).edit().putString("scene",j.optString("id",j.optString("scene_id",""))).apply();startCloudStream();}else controls.sceneError="请先读取 catalog 或返回设置选择场景";}catch(Exception e){controls.sceneError="场景列表尚未就绪";}return;
      }
      if(action==VrUiState.CLOUD_LINK){String old=CloudSettings.prefs(this).getString("profile","wifi");CloudSettings.prefs(this).edit().putString("profile",old.equals("wifi")?"relay":"wifi").apply();startCloudStream();return;}
      if(action==VrUiState.CLOUD_CLEAR){controls.cloudClearConfirm=true;return;}
      if(action==VrUiState.CLOUD_CLEAR_NO){controls.cloudClearConfirm=false;return;}
      if(action==VrUiState.CLOUD_CLEAR_YES){controls.cloudClearConfirm=false;CloudStream previous=cloudStream;if(previous!=null){previous.close();cloudStream=null;}new Thread(()->{if(previous!=null)previous.awaitStopped();CloudStream.clearCache(CloudSettings.cache(this));main.post(this::startCloudStream);},"cloud-clear").start();return;}
      if(action==VrUiState.CLOUD_FLOOR_UP||action==VrUiState.CLOUD_FLOOR_DOWN){float y=CloudSettings.prefs(this).getFloat("floor_y",0)+(action==VrUiState.CLOUD_FLOOR_UP?.1f:-.1f);CloudSettings.prefs(this).edit().putFloat("floor_y",y).apply();CloudNative.recenter(y);return;}
    }
    if(sceneBrowser && action>=VrUiState.SCENE_TABLE&&action<=VrUiState.SCENE_REMOTE){
      if(action==VrUiState.SCENE_LOCAL||action==VrUiState.SCENE_REMOTE){stopCloud();controls.sceneView=1;NativeVr.coloredSceneView(1,false,true);coloredLoader.load(action==VrUiState.SCENE_REMOTE);}
      else{
        if(controls.cloudMode){CloudNative.recenter(CloudSettings.prefs(this).getFloat("floor_y",0));return;}
        if(action==VrUiState.SCENE_TABLE)controls.sceneView=1;
        if(action==VrUiState.SCENE_FULL)controls.sceneView=2;
        if(action==VrUiState.SCENE_POINTS)controls.scenePointMode=!controls.scenePointMode;
        NativeVr.coloredSceneView(controls.sceneView,controls.scenePointMode,action!=VrUiState.SCENE_POINTS);
      }
      return;
    }
    if(action>=VrUiState.RECORD&&action<=VrUiState.CENTER_DOWN){captureAction(action);return;}
    if (action == VrUiState.LOG_REFRESH) {
      refreshLogs();
      return;
    }
    controls.presentation(action);
    if(action==VrUiState.RIGHT_CAMERA)getSharedPreferences("v2",0).edit().putBoolean("right_camera_visible",controls.rightCameraVisible).apply();
    if(action==VrUiState.SOURCE_RGB||action==VrUiState.SOURCE_DEPTH||action>=VrUiState.VIDEO_RGB&&action<=VrUiState.VIDEO_CAM4||action==VrUiState.VIDEO_FISHEYE){NativeVr.videoSelection(controls.selectedCamera);}
    seenVideoModes |= 1 << controls.videoMode;
    if (controls.modal())
      menuOpened = true;
    if (action == VrUiState.LOGS)
      refreshLogs();
    NativeVr.presentation(controls.videoMode, controls.mapVisible, controls.modal());
    if (demo&&!sceneBrowser)
      NativeVr.captureDemo();
  }
  private void refreshLogs(){
    if(!logLoading.compareAndSet(false,true))return;
    final int wanted=controls.logWanted;
    new Thread(()->{try{
      String[] old=controls.logLines;String previous=old.length>0?old[old.length-1]:"";
      String[] entries=AppLog.recent(this,wanted,false).split("\n");String[] lines=VrHud.wrapLogs(entries);int added=0;
      if(controls.logScroll>0&&!previous.isEmpty()){int found=-1;for(int i=lines.length-1;i>=0;i--)if(lines[i].equals(previous)){found=i;break;}if(found>=0)added=lines.length-1-found;}
      controls.logLines=lines;controls.logLoaded=entries.length;controls.logScroll=Math.max(0,controls.logScroll+added);
      controls.logEnd=entries.length<wanted;
    }finally{logLoading.set(false);}},"tlz-vr-logs").start();
  }
  private void latchVideo(int index,long now){
    SurfaceTexture texture=cameraTextures[index];DirectHevcVideo decoder=cameras[index];AtomicBoolean pending=cameraPending[index];Dashboard state=cameraStates[index];Dashboard.VideoInfo info=ui.cameras[index];
    if(!demo&&(decoder==null||!decoder.outputReady)){NativeVr.videoStreamReset(index);info.received=0;info.fps=Double.NaN;info.status=state.videoStatus;}
    if(texture==null||!pending.getAndSet(false))return;
    try{texture.updateTexImage();float[] matrix=new float[16];texture.getTransformMatrix(matrix);
      if(demo||decoder!=null&&decoder.outputReady){int w=demo?1280:state.videoWidth,h=demo?720:state.videoHeight;float ratio=w>0&&h>0?w*state.videoPixelRatio/h:16f/9;
        NativeVr.videoFrame(index,matrix,w,h,ratio);state.videoSubmitted++;info.received=now;info.width=w;info.height=h;info.frames++;info.status=demo?"虚拟视频":state.videoStatus;
        if(videoAt[index]==0){videoAt[index]=now;videoCounts[index]=info.frames;}else if(now-videoAt[index]>=1_000_000_000L){info.fps=(info.frames-videoCounts[index])*1e9/(now-videoAt[index]);videoAt[index]=now;videoCounts[index]=info.frames;}
      }
    }catch(RuntimeException e){NativeVr.videoStreamReset(index);info.received=0;AppLog.warn("VIDEO","LATCH_"+index,e.toString());}
  }
  private void deviceStatus(){
    try{android.content.Intent battery=registerReceiver(null,new android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED));int level=battery==null?-1:battery.getIntExtra("level",-1),scale=battery==null?0:battery.getIntExtra("scale",0);ui.battery=level>=0&&scale>0?Math.min(100,level*100/scale):-1;}catch(Exception e){ui.battery=-1;}
    try{android.net.wifi.WifiManager wifi=(android.net.wifi.WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);android.net.wifi.WifiInfo info=wifi==null?null:wifi.getConnectionInfo();int rssi=info==null?-127:info.getRssi();if(info!=null&&info.getIpAddress()!=0)controls.captureAddress="http://"+android.text.format.Formatter.formatIpAddress(info.getIpAddress())+":8095";else controls.captureAddress="http://<VR-IP>:8095";ui.wifiLevel=info!=null&&info.getNetworkId()!=-1&&rssi>-127?1+android.net.wifi.WifiManager.calculateSignalLevel(rssi,3):0;}catch(Exception e){ui.wifiLevel=-1;}
  }
  public String debugAction(String action, int value) {
    if (action.equals("status") || action.equals("snapshot")) {
      diagnostics();
      return "snapshot written";
    }
    main.post(() -> {
      if (action.equals("stop")) {
        if (link != null)
          link.stop("ADB停止输入意图");
      } else if (action.equals("exit"))
        exitToSettings();
      else if (action.equals("video"))
        perform(value == 0   ? VrUiState.VIDEO_OFF
                : value == 2 ? VrUiState.VIDEO_LARGE
                             : VrUiState.VIDEO_SMALL);
      else if (action.equals("logs"))
        perform(VrUiState.LOGS);
    });
    return "queued " + action;
  }
  private void exitToSettings() {
    if (!exiting.compareAndSet(false, true))
      return;
    if (link != null)
      link.stop("退出到设置，发送停止信号");
    controls.demoArmed = false;
    AppLog.info("UI", "EXIT_SETTINGS", "退出到AIPC设置");
    diagnostics();
    main.post(() -> {
      startActivity(
          new android.content.Intent(this, com.tanluzhe.controlterminal.vr.LauncherActivity.class)
              .addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP
                  | android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP));
      finish();
    });
  }
  @Override
  public void onBackPressed() {
    perform(VrUiState.MENU);
  }
  public void onNativeError(String reason) {
    nativeError = reason == null ? "Unknown native error" : reason;
    AppLog.error("XR", "NATIVE_ERROR", nativeError);
    ui.connection = "OpenXR启动失败";
    ui.warning = reason == null ? "未知错误" : reason;
    main.post(() -> {
      if (!isFinishing()) {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(1);
        TextView text = new TextView(this);
        text.setText("VR初始化失败\n" + ui.warning + "\n请返回设置。此界面不是VR场景。");
        text.setTextColor(Color.WHITE);
        text.setTextSize(22);
        text.setPadding(30, 30, 30, 30);
        text.setBackgroundColor(0xff382222);
        panel.addView(text);
        Button back = new Button(this);
        back.setText("退出并返回设置");
        back.setOnClickListener(v -> exitToSettings());
        panel.addView(back);
        TerminalStyle.page(panel);
        setContentView(panel);
      }
    });
  }
  private final Runnable hudTask = new Runnable() {
    public void run() {
      if (closed)
        return;
      long now = System.nanoTime();
      if(now-deviceAt>1_000_000_000L){deviceAt=now;deviceStatus();}
      
      if(sceneModes!=null){sceneModes.update();ui.cloudReceived=sceneModes.receivedNs();}
      if(demo&&!sceneBrowser)ui.telemetry=demoTelemetry(now);
      if(controls.cloudMode){
        if(cloudStream!=null){
          try{cloudStream.position(CloudNative.head());}catch(Exception ignored){}
          controls.cloudInfo=cloudStream.summary();controls.sceneSource=cloudStream.sceneName+" · "+cloudStream.config().profile;
          controls.sceneError=cloudStream.error;controls.cloudDetail=cloudStream.config().scene+"\n"+cloudStream.config().base+"\n"+(CloudSettings.prefs(V2Activity.this).contains("floor_y")?"地面Y="+CloudSettings.prefs(V2Activity.this).getFloat("floor_y",0):"地面未校准；Y=0不是地板")+"\n缓存 "+cloudStream.diskBytes/1024/1024+" MiB · 中继部署="+cloudStream.relayConfigured;
          long[] st=CloudNative.stats();controls.cloudStats=st;if(st[6]!=0)controls.sceneError=st[6]==3?"预取受显存预算限制":"GPU预算/上传受限，近区尚未完整；保留粗图";
        }
      }
      if(sceneBrowser&&!controls.cloudMode&&coloredLoader!=null){
        controls.sceneStats=NativeVr.coloredSceneStats();controls.sceneSource=coloredLoader.source;
        controls.sceneStatus=coloredLoader.status;controls.sceneError=coloredLoader.error;
        long[] stats=controls.sceneStats;
        if(stats[7]!=0)controls.sceneError=stats[7]==1?"GPU 内存预算不足，保留原场景":"GPU 上传失败，保留原场景";
        else if(!coloredLoader.busy()&&coloredLoader.error.isEmpty()&&stats[0]>0&&stats[4]==stats[5])controls.sceneStatus="场景就绪";
      }
      Dashboard.VideoInfo selected=ui.cameras[controls.selectedCamera];ui.videoReceived=selected.received;ui.videoFrames=selected.frames;ui.videoStatus=selected.status;ui.videoWidth=selected.width;ui.videoHeight=selected.height;ui.videoFps=selected.fps;Dashboard source=cameraStates[controls.selectedCamera];ui.videoSource=CameraLayout.label(controls.selectedCamera);ui.videoDecoder=source.videoDecoder;ui.videoPtsUs=source.videoPtsUs;
      if(controls.logsOpen&&!controls.logEnd&&controls.logWanted>controls.logLoaded)refreshLogs();
      if(viewCapture!=null){controls.captureConfig=viewCapture.config();controls.captureSummary=viewCapture.summary();controls.captureError=viewCapture.error();controls.captureRecording=viewCapture.recording();controls.captureStreaming=viewCapture.streaming();}
      hud.draw(hudBitmap, ui, controls, now, false);
      NativeVr.hud(hudBitmap);
      if(!demo){boolean want=resumed&&rightCameraPose;if(want!=camera1Demand){camera1Demand=want;if(cameras[4]!=null)cameras[4].foreground(want);}if(cameras[4]!=null)cameras[4].quality(CameraLayout.rightEnabled(ui.telemetry,now)?"720p30":"240p15");}
      if (now - lastWorldHud >= 200_000_000L) {
        lastWorldHud = now;
        hud.drawWorld(worldBitmap, ui, controls, now, false);
        NativeVr.worldHud(worldBitmap);
        hud.drawGrippers(gripBitmap,ui.telemetry,now);NativeVr.gripLabels(gripBitmap);
      }
      if (demo && !sceneBrowser && videoSurface != null && now - lastDemoVideo >= 66_000_000L)
        drawDemoVideo(now);
      if (now - lastDiagnostics > 1_000_000_000L) {
        lastDiagnostics = now;
        diagnostics();
      }
      main.postDelayed(this, 50);
    }
  };
  public void onNativeRendered() {
    renderedFrames++;
    long now = System.nanoTime();
    if (fpsAt == 0) {
      fpsAt = now;
      fpsFrames = renderedFrames;
    } else if (now - fpsAt >= 1_000_000_000L) {
      controls.displayHz = (renderedFrames - fpsFrames) * 1e9 / (now - fpsAt);
      fpsAt = now;
      fpsFrames = renderedFrames;
    }
  }
  public void onMirrorPixels(int width, int height, int[] pixels) {
    if (!captureWriting.compareAndSet(false, true))
      return;
    new Thread(() -> {
      try {
        Bitmap bitmap = Bitmap.createBitmap(pixels, width, height, Bitmap.Config.ARGB_8888);
        android.util.AtomicFile file =
            new android.util.AtomicFile(new java.io.File(getFilesDir(), "v2-eye.png"));
        java.io.FileOutputStream out = file.startWrite();
        try {
          if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, out))
            throw new java.io.IOException("PNG encode failed");
          file.finishWrite(out);
        } catch (Exception e) {
          file.failWrite(out);
          throw e;
        }
        bitmap.recycle();
      } catch (Exception ignored) {
      } finally {
        captureWriting.set(false);
      }
    }, "tlz-capture").start();
  }
  public void diagnostics() {
    try {
      org.json.JSONObject d =
          new org.json.JSONObject()
              .put("run_id", runId)
              .put("demo", demo)
              .put("gl_ready", glReady)
              .put("vr_frames", frameCount)
              .put("rendered_frames", renderedFrames)
              .put("display_hz",
                  Double.isFinite(controls.displayHz) ? controls.displayHz
                                                      : org.json.JSONObject.NULL)
              .put("view_mode", controls.followView ? "follow" : "observer")
              .put("vehicle_pose_fresh", controls.vehiclePoseFresh)
              .put("hud_text_hz", 20)
              .put("face_buttons",
                  new org.json.JSONObject()
                      .put("revision", 1)
                      .put("valid_mask", controls.faceButtons.valid)
                      .put("pressed_mask", controls.faceButtons.pressed))
              .put("stick_buttons",new org.json.JSONObject().put("revision",1).put("valid_mask",controls.stickButtons.valid).put("pressed_mask",controls.stickButtons.pressed))
              .put("video_transport", "hevc-fmp4")
              .put("video_source", ui.videoSource)
              .put("video_decoder", ui.videoDecoder)
              .put("video_status", ui.videoStatus)
              .put("video_pts_us", ui.videoPtsUs)
              .put("video_width", ui.videoWidth)
              .put("video_height", ui.videoHeight)
              .put("video_frames", ui.videoFrames)
              .put("controller_geometry_revision",1)
              .put("controller_left_model_source",latestControllerBounds==null?-1:(int)latestControllerBounds[6])
              .put("controller_right_model_source",latestControllerBounds==null?-1:(int)latestControllerBounds[13])
              .put("scene_mode",controls.integratedStatic?"scene":"live").put("scene_cache_status",controls.cloudCacheStatus).put("scene_cloud_status",controls.cloudModeStatus).put("scene_cloud_error",controls.cloudModeError).put("scene_browser",sceneBrowser).put("colored_scene_stats",new org.json.JSONArray(controls.sceneStats)).put("colored_scene_status",controls.sceneStatus).put("colored_scene_error",controls.sceneError)
              .put("tracking_flags", trackingFlags)
              .put("native_error", nativeError);
      Telemetry telemetry=ui.telemetry;long sampled=System.nanoTime();
      d.put("telemetry_fresh",telemetry.fresh(sampled)).put("telemetry_error",ui.telemetryError)
       .put("telemetry_port",new ConnectionSettings(this).telemetryPort).put("aipc_mode",telemetry.mode)
       .put("left_arm_state",telemetry.left.state).put("right_arm_state",telemetry.right.state)
       .put("minimap_visible",controls.mapVisible).put("logs_scroll",controls.logScroll).put("logs_entries_loaded",controls.logLoaded)
       .put("rgb_frames",ui.rgb.frames).put("depth_frames",ui.depth.frames)
       .put("rgb_status",ui.rgb.status).put("depth_status",ui.depth.status)
       .put("rgb_fps",Double.isFinite(ui.rgb.fps)?ui.rgb.fps:org.json.JSONObject.NULL)
       .put("depth_fps",Double.isFinite(ui.depth.fps)?ui.depth.fps:org.json.JSONObject.NULL)
       .put("observation_total_bytes",ui.observationTotalBytes).put("wifi_level",ui.wifiLevel).put("vr_battery",ui.battery);
      if(viewCapture!=null)d.put("view_capture",viewCapture.status());
      d.put("active_hands", controls.activeHands)
          .put("session_state", controls.sessionState)
          .put("left_profile", controls.leftProfile)
          .put("right_profile", controls.rightProfile)
          .put("buttons", controls.buttons)
          .put("input_events", controls.inputEvents)
          .put("video_mode", controls.videoMode)
          .put("menu_open", controls.menuOpen)
          .put("hover", controls.hover)
          .put("haptic_pulses", hapticPulses)
          .put("last_haptic_result", lastHapticResult)
          .put("ui_feedback", controls.feedback);
      d.put("seen_buttons", seenButtons)
          .put("seen_video_modes", seenVideoModes)
          .put("seen_analog", seenAnalog)
          .put("ui_clicks", uiClicks)
          .put("menu_opened", menuOpened)
          .put("exit_requested", exiting.get());
      d.put("input_valid_mask", controls.raw.valid)
          .put("input_mode_preview", controls.modeLabel)
          .put("mode_reason", controls.modeReason)
          .put("input_controls_revision", 1)
          .put("observation_hz_requested", new ConnectionSettings(this).observationHz)
          .put("setpoint_owner", "aipc");
      if (link != null)
        d.put("observation_sent", ui.observationSent)
            .put("observation_encoding", ui.observationEncoding)
            .put("observation_dropped", ui.observationDropped)
            .put("observation_bytes", ui.observationBytes)
            .put("observation_actual_hz",
                Double.isFinite(ui.observationActualHz) ? ui.observationActualHz
                                                        : org.json.JSONObject.NULL)
            .put("observation_channel", ui.observationChannel);
      d.put("pointer_inputs", new org.json.JSONArray(controls.pointers))
          .put("axes", new org.json.JSONArray(controls.axes));
      android.util.AtomicFile file =
          new android.util.AtomicFile(new java.io.File(getFilesDir(), "v2-diagnostics.json"));
      java.io.FileOutputStream out = file.startWrite();
      try {
        out.write(d.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        file.finishWrite(out);
      } catch (Exception e) {
        file.failWrite(out);
      }
    } catch (Exception ignored) {
    }
  }
  private void drawDemoVideo(long now) {
    lastDemoVideo = now;for(int i=0;i<6;i++)drawDemoSurface(cameraSurfaces[i],now,i==1);
  }
  private void drawDemoSurface(Surface output,long now,boolean depth){
    if(output==null)return;try {
      Canvas c = output.lockCanvas(null);
      int w = c.getWidth(), h = c.getHeight();
      int[] colors = {
          0xffcccccc, 0xffffff00, 0xff00ffff, 0xff00cc00, 0xffff00ff, 0xffcc0000, 0xff0000cc};
      for (int i = 0; i < 7; i++) {
        paint.setColor(colors[depth?6-i:i]);
        c.drawRect(i * w / 7f, 0, (i + 1) * w / 7f, h, paint);
      }
      paint.setColor(0xd0000000);
      c.drawRect(0, h * .62f, w, h, paint);
      paint.setColor(Color.WHITE);
      paint.setTextSize(44);
      c.drawText("SIMULATED VIDEO / NOT A CAMERA", 35, h * .73f, paint);
      paint.setTextSize(32);
      c.drawText(String.format(Locale.ROOT, "Monotonic %.3f s", now / 1e9), 35, h * .84f, paint);
      output.unlockCanvasAndPost(c);
      ui.videoReceived = now;
      ui.videoFrames++;
      ui.videoAgeQuality = "虚拟测试图";
    } catch (RuntimeException ignored) {
    }
  }
  private Telemetry demoTelemetry(long now){float[][] left={{0,0,0},{0,0,12},{0,0,12},{-8,13,28},{-11,27,20},{-11,27,20},{-9,36,20}};float[][] right={{0,0,0},{0,0,12},{0,0,12},{8,13,28},{11,27,20},{11,27,20},{9,36,20}};return new Telemetry(now,"arms","双臂模式（演示）","",false,0,0,0,new Telemetry.Arm("following","target","",left,new float[]{0,0,0,1},.6f),new Telemetry.Arm("idle","target","",right,new float[]{0,0,0,1},.25f));}
  private void demoGeometry(long now) {
    float[] points = new float[9000 * 7];
    Random r = new Random(42);
    float phase = (float) (now / 1e9);
    for (int i = 0; i < 9000; i++) {
      int o = i * 7;
      float x = (r.nextFloat() - .5f) * 10, z = -r.nextFloat() * 10;
      float y = i % 3 == 0 ? 0
          : i % 3 == 1     ? 1.8f * r.nextFloat()
                           : 1.2f + .4f * (float) Math.sin(x + phase * .15f);
      points[o] = x;
      points[o + 1] = y;
      points[o + 2] = z;
      points[o + 3] = i % 3 == 2 ? .95f : .25f;
      points[o + 4] = .7f;
      points[o + 5] = .5f;
      points[o + 6] = 1;
    }
    float[] lines = {-.35f, 0, -2, .1f, 1, .5f, 1, .35f, 0, -2, .1f, 1, .5f, 1, .35f, 0, -2, .1f, 1,
        .5f, 1, .35f, .5f, -2, .1f, 1, .5f, 1, .35f, .5f, -2, .1f, 1, .5f, 1, -.35f, .5f, -2, .1f,
        1, .5f, 1, -.35f, .5f, -2, .1f, 1, .5f, 1, -.35f, 0, -2, .1f, 1, .5f, 1};
    // All geometry is map-local. The native display origin is calibrated once, not on head motion.
    for (int i = 0; i < lines.length; i += 7) {
      lines[i] += demoX;
      lines[i + 2] += demoZ + 2;
    }
    NativeVr.cloud(points);
    NativeVr.lines(lines);
    ui.stateReceived = now;
    ui.cloudReceived = now;
  }
  @Override
  protected void onResume() {
    super.onResume();
    if(sceneModes!=null)sceneModes.foreground(true);
    if(cloudStream!=null)cloudStream.pause(false);
    resumed = true;
    if(viewCapture!=null)viewCapture.foreground(true);
    try {
      NativeVr.active(true);
    } catch (Throwable ignored) {
    }
    if (link != null)
      link.gate.foreground = true;
    for(int i=0;i<6;i++)if(cameras[i]!=null)cameras[i].foreground(i!=4||rightCameraPose);if(telemetryClient!=null)telemetryClient.foreground(true);
  }
  @Override
  protected void onPause() {
    resumed = false;
    if(viewCapture!=null)viewCapture.foreground(false);
    controls.faceButtons = FaceButtons.invalid();controls.stickButtons=StickButtons.invalid();
    controls.raw = InputControls.invalid();
    awaitGripRelease = true;
    inputMode.reset("应用暂停，输入失效");
    AppLog.warn("XR", "PAUSE", "应用失焦，输入有效位清零");
    for(DirectHevcVideo camera:cameras)if(camera!=null)camera.foreground(false);camera1Demand=false;if(telemetryClient!=null)telemetryClient.foreground(false);
    if (link != null) {
      link.gate.foreground = false;
      link.stop("应用暂停");
    }
    try {
      NativeVr.active(false);
    } catch (Throwable ignored) {
    }
    if(sceneModes!=null)sceneModes.foreground(false);
    if(cloudStream!=null)cloudStream.pause(true);
    super.onPause();
  }
  @Override
  protected void onDestroy() {
    closed = true;
    if(viewCapture!=null)viewCapture.shutdownService();
    if(coloredLoader!=null)coloredLoader.close();
    if(sceneModes!=null)sceneModes.close();
    if(cloudStream!=null)cloudStream.close();
    current.clear();
    AppLog.info("XR", "ACTIVITY_DESTROY", "XR资源清理");
    main.removeCallbacksAndMessages(null);
    for(DirectHevcVideo camera:cameras)if(camera!=null)camera.close();if(telemetryClient!=null)telemetryClient.close();
    if (link != null)
      link.close();
    xrLifecycle.execute(() -> {
      if(viewCapture!=null)viewCapture.close();
      try {
        NativeVr.stop();
      } catch (Throwable ignored) {
      }

      if (videoSurface != null)
        videoSurface.release();
      if (videoTexture != null)
        videoTexture.release();

      if(depthSurface!=null)depthSurface.release();if(depthTexture!=null)depthTexture.release();for(int i=2;i<6;i++){if(cameraSurfaces[i]!=null)cameraSurfaces[i].release();if(cameraTextures[i]!=null)cameraTextures[i].release();}gripBitmap.recycle();
      hudBitmap.recycle();
      worldBitmap.recycle();
    });

    super.onDestroy();
  }
}
