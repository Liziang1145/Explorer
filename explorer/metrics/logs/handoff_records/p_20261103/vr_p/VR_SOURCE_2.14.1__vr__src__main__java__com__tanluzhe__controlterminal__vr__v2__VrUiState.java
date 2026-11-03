package com.tanluzhe.controlterminal.vr.v2;

/**
 * Head-relative interaction geometry; vehicle-anchored information is a separate layer and input
 * arbitration, independent of Android/XR.
 */
public final class VrUiState {
  public static final int SCENE_PANEL=34,SCENE_TABLE=35,SCENE_FULL=36,SCENE_RESET=37,SCENE_POINTS=38,SCENE_LOCAL=39,SCENE_REMOTE=40;
  public static final int CLOUD_START=41,CLOUD_NEXT=42,CLOUD_LINK=43,CLOUD_CLEAR=44,CLOUD_CLEAR_YES=45,CLOUD_CLEAR_NO=46,CLOUD_FLOOR_UP=47,CLOUD_FLOOR_DOWN=48;
  public static final int MODE_TOGGLE=60;
  public static final int VIDEO_RGB=56,VIDEO_DEPTH=57,VIDEO_CAM3=58,VIDEO_CAM4=59;
  public volatile int selectedCamera;
  public static final int RIGHT_CAMERA=61,VIDEO_FISHEYE=62;
  public volatile boolean rightCameraVisible=true, interactionLocked;
  public static final int MODE_LIVE=49,MODE_SCENE=50,SCENE_CATALOG=51,SCENE_PREV=52,SCENE_NEXT=53,SCENE_CLEAR=54,SCENE_CLEAR_ALL=55,SCENE_ITEM=100;
  public volatile boolean integratedStatic,sceneDeleteAll;
  public volatile String sceneServiceAddress="",sceneDeleteLabel="";
  public volatile float sceneCacheFraction;
  public volatile String cloudModeStatus="实时模式",cloudCacheStatus="",cloudModeError="";
  public volatile String[] sceneCatalogIds=new String[0],sceneCatalogLabels=new String[0];
  public volatile float sceneScroll;
  public volatile java.util.Map<String,SceneCacheInfo> sceneCaches=java.util.Collections.emptyMap();
  public static final int WIDTH = 1600, HEIGHT = 1000;
  public static final int VIDEO_OFF = 1, VIDEO_SMALL = 2, VIDEO_LARGE = 3, MAP = 4, MENU = 5,
                          RESUME = 6, EXIT = 7, LOGS = 12, VIDEO_PANEL = 13, LOG_REFRESH = 14,
                          PREV = 15, NEXT = 16, VIEW = 17, SOURCE_RGB = 18, SOURCE_DEPTH = 19,
                          CAPTURE=20,RECORD=21,LIVE=22,FOV_MINUS=23,FOV_PLUS=24,MARGIN_MINUS=25,MARGIN_PLUS=26,PROFILE=27,EYE=28,CAPTURE_RESET=29,CENTER_LEFT=30,CENTER_RIGHT=31,CENTER_UP=32,CENTER_DOWN=33;
  public static final class Rect {
    public final int id;
    public final float x, y, w, h;
    public Rect(int id, float x, float y, float w, float h) {
      this.id = id;
      this.x = x;
      this.y = y;
      this.w = w;
      this.h = h;
    }
    public boolean contains(float px, float py) {
      return Float.isFinite(px) && Float.isFinite(py) && px >= x && px <= x + w && py >= y
          && py <= y + h;
    }
  }
  public static final Rect[] TOOLBAR = {new Rect(VIDEO_PANEL, 350, 894, 140, 90),
      new Rect(MODE_TOGGLE, 502, 894, 140, 90), new Rect(MENU, 654, 894, 140, 90),
      new Rect(VIEW, 806, 894, 140, 90), new Rect(LOGS, 958, 894, 140, 90),
      new Rect(EXIT, 1110, 894, 140, 90)};
  public static final Rect[] DIALOG={new Rect(RESUME,400,310,350,90),new Rect(VIDEO_PANEL,850,310,350,90),new Rect(VIEW,400,420,350,90),new Rect(LOGS,850,420,350,90),new Rect(CAPTURE,400,535,350,90),new Rect(EXIT,850,535,350,90),new Rect(MAP,400,650,350,80),new Rect(SCENE_PANEL,850,650,350,80)};
  public static final int SCENE_TOP=285,SCENE_BOTTOM=645,SCENE_ROW=144;
  public float sceneScrollMax(){return Math.max(0,sceneCatalogIds.length*SCENE_ROW-(SCENE_BOTTOM-SCENE_TOP));}
  public Rect[] integratedChoices(){java.util.ArrayList<Rect> result=new java.util.ArrayList<>();result.add(new Rect(MODE_LIVE,300,180,480,70));result.add(new Rect(MODE_SCENE,820,180,480,70));result.add(new Rect(SCENE_CATALOG,1040,105,260,55));float scroll=Math.max(0,Math.min(sceneScrollMax(),sceneScroll));for(int i=0;i<sceneCatalogIds.length;i++){float y=SCENE_TOP+i*SCENE_ROW-scroll;float top=Math.max(SCENE_TOP,y),bottom=Math.min(SCENE_BOTTOM,y+132);if(bottom>top)result.add(new Rect(SCENE_ITEM+i,300,top,1000,bottom-top));}result.add(new Rect(SCENE_CLEAR,300,670,300,65));result.add(new Rect(SCENE_CLEAR_ALL,630,670,300,65));result.add(new Rect(SCENE_RESET,960,670,300,65));result.add(new Rect(CLOUD_FLOOR_UP,300,755,300,65));result.add(new Rect(CLOUD_FLOOR_DOWN,630,755,300,65));result.add(new Rect(RESUME,960,755,300,65));return result.toArray(new Rect[0]);}
  public static final Rect[] VIDEO_CHOICES = {new Rect(VIDEO_OFF, 370, 390, 260, 100),
      new Rect(VIDEO_SMALL, 670, 390, 260, 100), new Rect(VIDEO_LARGE, 970, 390, 260, 100),
      new Rect(VIDEO_RGB,370,520,200,95),new Rect(VIDEO_DEPTH,590,520,200,95),new Rect(VIDEO_CAM3,810,520,200,95),new Rect(VIDEO_CAM4,1030,520,200,95),
      new Rect(VIDEO_FISHEYE,370,630,260,65),new Rect(RIGHT_CAMERA,670,630,560,65),
      new Rect(RESUME,550,720,500,65)};
  public static final Rect[] LOG_TOOLS = {new Rect(LOG_REFRESH, 300, 730, 485, 90),new Rect(RESUME,815,730,485,90)};
  public static final Rect[] CAPTURE_CHOICES={new Rect(LIVE,230,280,530,80),new Rect(PROFILE,800,280,520,80),
    new Rect(FOV_MINUS,230,390,240,80),new Rect(FOV_PLUS,500,390,240,80),new Rect(MARGIN_MINUS,770,390,240,80),new Rect(MARGIN_PLUS,1040,390,240,80),
    new Rect(EYE,230,600,350,70),new Rect(CAPTURE_RESET,600,600,350,70),new Rect(RESUME,970,600,350,70)};
  public static final Rect[] SCENE_TOOLBAR={new Rect(SCENE_PANEL,350,894,140,90),new Rect(SCENE_TABLE,502,894,140,90),new Rect(SCENE_FULL,654,894,140,90),new Rect(SCENE_RESET,806,894,140,90),new Rect(LOGS,958,894,140,90),new Rect(EXIT,1110,894,140,90)};
  public static final Rect[] SCENE_DIALOG={new Rect(RESUME,400,310,350,90),new Rect(SCENE_PANEL,850,310,350,90),new Rect(SCENE_TABLE,400,420,350,90),new Rect(SCENE_FULL,850,420,350,90),new Rect(CAPTURE,400,535,350,90),new Rect(EXIT,850,535,350,90)};
  public static final Rect[] SCENE_CHOICES={new Rect(SCENE_LOCAL,310,330,470,90),new Rect(SCENE_REMOTE,820,330,470,90),new Rect(SCENE_POINTS,310,455,470,90),new Rect(SCENE_RESET,820,455,470,90),new Rect(CLOUD_START,550,555,500,70),new Rect(RESUME,550,650,500,80)};
  public static final Rect[] CLOUD_TOOLBAR={new Rect(SCENE_PANEL,350,894,140,90),new Rect(SCENE_RESET,502,894,140,90),new Rect(CLOUD_FLOOR_UP,654,894,140,90),new Rect(CLOUD_FLOOR_DOWN,806,894,140,90),new Rect(LOGS,958,894,140,90),new Rect(EXIT,1110,894,140,90)};
  public static final Rect[] CLOUD_DIALOG={new Rect(RESUME,400,310,350,90),new Rect(SCENE_PANEL,850,310,350,90),new Rect(SCENE_RESET,400,420,350,90),new Rect(CLOUD_CLEAR,850,420,350,90),new Rect(CAPTURE,400,535,350,90),new Rect(EXIT,850,535,350,90)};
  public static final Rect[] CLOUD_CHOICES={new Rect(CLOUD_NEXT,300,330,480,80),new Rect(CLOUD_LINK,820,330,480,80),new Rect(SCENE_RESET,300,440,300,80),new Rect(CLOUD_FLOOR_UP,630,440,300,80),new Rect(CLOUD_FLOOR_DOWN,960,440,300,80),new Rect(CLOUD_START,300,550,300,80),new Rect(CLOUD_CLEAR,630,550,300,80),new Rect(SCENE_LOCAL,960,550,300,80),new Rect(RESUME,550,700,500,75)};
  public static final Rect[] CLOUD_CONFIRM={new Rect(CLOUD_CLEAR_YES,350,500,400,90),new Rect(CLOUD_CLEAR_NO,850,500,400,90)};
  public volatile boolean cloudMode,cloudClearConfirm;public volatile String cloudInfo="",cloudDetail="";public volatile long[] cloudStats=new long[8];
  public volatile boolean sceneBrowser,scenePanel,scenePointMode;
  public volatile int sceneView=1;
  public volatile String sceneStatus="等待场景",sceneError="",sceneSource="";
  public volatile long[] sceneStats=new long[8];
  public volatile boolean capturePanel,captureRecording,captureStreaming;
  public volatile CaptureConfig captureConfig=CaptureConfig.defaults();
  public volatile String captureSummary="取景服务初始化中",captureError="",captureAddress="http://<VR-IP>:8095";
  public volatile boolean followView, depthVideo;
  public volatile double displayHz = Double.NaN;
  public volatile boolean vehiclePoseFresh;
  public volatile int videoMode = 2, hover, buttons, activeHands, tracking, sessionState;
  public volatile boolean mapVisible = true, menuOpen, logsOpen, videoPanel;
  public volatile int selected = RESUME, logPage;
  public volatile int logWanted=100,logLoaded;
  public volatile boolean logEnd;
  public volatile float logScroll;
  private long scrollAt;
  public volatile String[] logLines = {"暂无日志"};
  public volatile String modeLabel = "待命 · 原始输入", modeReason = "请释放侧键、摇杆回中";
  public volatile StickButtons stickButtons=StickButtons.invalid();
  public volatile FaceButtons faceButtons = FaceButtons.invalid();
  public volatile InputControls raw = InputControls.invalid();
  public volatile float[] pointers = {-1, -1, -1, -1, 0, 0, 0, 0}, axes = new float[6];
  public volatile long inputEvents;
  public volatile String feedback = "将手柄射线指向按钮，扣扳机选择", leftProfile = "未激活",
                         rightProfile = "未激活";
  public volatile boolean demoLease, demoSynced, demoArmed;
  private int previousButtons, previousTriggers = 3;
  private boolean wasFocused, buttonsFocused;
  private long navigateAt;
  public Rect videoRect() {
    return videoMode == 2 ? new Rect(0, 320, 160, 960, 540) : new Rect(0, 450, 220, 700, 393.75f);
  }
  public int hit(float u, float v) {
    if (interactionLocked) return 0;
    if (!Float.isFinite(u) || !Float.isFinite(v) || u < 0 || v < 0 || u > 1 || v > 1)
      return 0;
    for (Rect rect : buttons())
      if (rect.contains(u * WIDTH, v * HEIGHT))
        return rect.id;
    return 0;
  }
  /** Front UI owns its surface even while disabled, so empty BAR spacing cannot click through. */
  public boolean occludes(float u,float v){
    if(!Float.isFinite(u)||!Float.isFinite(v)||u<0||u>1||v<0||v>1)return false;
    if(modal())return true;
    float x=u*WIDTH,y=v*HEIGHT;
    return x>=330&&x<=1270&&y>=880&&y<=998;
  }
  /** Use this frame's real side-grip samples; remote arm telemetry never locks VR controls. */
  public static boolean gripLocksUi(float[] data,boolean focused){
    if(!focused||data==null||data.length<9)return false;
    int valid=(int)data[8];
    return (valid&1)!=0&&data[6]==1f||(valid&2)!=0&&data[7]==1f;
  }
  private int pointerTarget(float[] data,int hand){
    float u=data[hand*2],v=data[hand*2+1];
    int front=hit(u,v);if(front!=0)return front;
    if(interactionLocked||modal()||occludes(u,v)||data.length<13)return 0;
    float tile=data[11+hand];if(!Float.isFinite(tile)||tile!=(int)tile)return 0;
    int i=(int)tile;return i==5?VIDEO_FISHEYE:i>=0&&i<4?VIDEO_RGB+i:0;
  }
  /** One action per frame: sample both grips first, then arbitrate front UI and rear camera hits. */
  public int pointerAction(float[] data,boolean focused){
    pointers=data.clone();interactionLocked=gripLocksUi(data,focused);
    int left=pointerTarget(data,0),right=pointerTarget(data,1);
    int lh=hit(data[0],data[1]),rh=hit(data[2],data[3]);hover=rh!=0?rh:lh;
    if(hover!=0)selected=hover;
    int triggers=(data[4]>.65f?1:0)|(data[5]>.65f?2:0);
    if(!focused||!wasFocused){previousTriggers=triggers;wasFocused=focused;if(!focused)demoArmed=false;return 0;}
    int edges=triggers&~previousTriggers;previousTriggers=triggers;
    int action=(edges&2)!=0&&rh!=0?rh:(edges&1)!=0&&lh!=0?lh:(edges&2)!=0&&right!=0?right:(edges&1)!=0?left:0;
    if(action!=0)inputEvents++;return action;
  }
  public int buttonEdges(int value, boolean focused) {
    buttons = focused ? value : 0;
    int edges = focused && buttonsFocused ? buttons & ~previousButtons : 0;
    buttonsFocused = focused;
    previousButtons = buttons;
    if (edges != 0)
      inputEvents++;
    return edges;
  }
  /** ABXY (native bits 0..3) are exclusively remote inputs, including combinations. */
  public int localButtonAction(int edges) {
    if (interactionLocked) return 0;
    if ((edges & 16) != 0)
      return MENU;

    return 0;
  }
  public boolean blocksControl() {
    return !interactionLocked && (modal() || hover != 0);
  }
  public boolean modal() {
    return menuOpen || logsOpen || videoPanel || capturePanel || scenePanel || cloudClearConfirm;
  }
  public Rect[] buttons() {
    return cloudClearConfirm?CLOUD_CONFIRM : scenePanel ? integratedChoices() : capturePanel ? CAPTURE_CHOICES : logsOpen ? LOG_TOOLS : videoPanel ? VIDEO_CHOICES : menuOpen ? DIALOG : TOOLBAR;
  }
  public int select() {
    return hover != 0 ? hover : modal() ? selected : MENU;
  }
  public void navigate(float y, long now) {
    if(interactionLocked){scrollAt=0;navigateAt=0;return;}
    if(scenePanel){if(scrollAt==0)scrollAt=now;double dt=Math.min(.1,Math.max(0,(now-scrollAt)/1e9));scrollAt=now;if(Math.abs(y)>.18f)sceneScroll=(float)Math.max(0,Math.min(sceneScrollMax(),sceneScroll-y*dt*600));return;}
    if(logsOpen){
      if(scrollAt==0)scrollAt=now;double dt=Math.min(.1,Math.max(0,(now-scrollAt)/1e9));scrollAt=now;
      if(Math.abs(y)>.18f)logScroll=(float)Math.max(0,Math.min(Math.max(0,logLines.length-14),logScroll+y*dt*24));
      if(logScroll>logLines.length-30&&logWanted<=logLoaded&&logLoaded>=logWanted)logWanted=Math.min(10000,logWanted+100);
      return;
    } scrollAt=0;

    if (!modal() || Math.abs(y) < .6f) {
      navigateAt = 0;
      return;
    }
    if (now < navigateAt)
      return;
    navigateAt = now + 350_000_000L;
    Rect[] choices = buttons();
    int index = 0;
    for (int i = 0; i < choices.length; i++)
      if (choices[i].id == selected)
        index = i;
    selected = choices[(index + (y < 0 ? 1 : choices.length - 1)) % choices.length].id;
  }
  public void presentation(int action) {
    if(interactionLocked)return;
    switch (action) {
      case RIGHT_CAMERA:rightCameraVisible=!rightCameraVisible;break;
      case VIDEO_FISHEYE:selectedCamera=5;depthVideo=false;videoMode=2;break;
      case VIDEO_OFF:
        videoMode = 0;
        feedback = "视频已关闭显示";
        break;
      case VIDEO_SMALL:
        videoMode = 1;
        feedback = "视频已缩小（仍固定在车辆前方）";
        break;
      case VIDEO_LARGE:
        videoMode = 2;
        feedback = "视频已放大（固定在车辆前方）";
        break;
      case VIEW:
        followView = !followView;
        feedback = followView ? "跟随视角 · 位置绑定车辆，自由转头" : "旁观视角 · 可在空间自由观察";
        break;
      case VIDEO_RGB:case VIDEO_DEPTH:case VIDEO_CAM3:case VIDEO_CAM4:
        selectedCamera=action-VIDEO_RGB;depthVideo=selectedCamera==1;videoMode=2;break;
      case SOURCE_RGB:
        selectedCamera=0;depthVideo = false;
        feedback = "RGB 相机";
        break;
      case SOURCE_DEPTH:
        selectedCamera=1;depthVideo = true;
        feedback = "伪彩深度，仅用于显示";
        break;
      case MAP:
        mapVisible = !mapVisible;
        feedback = mapVisible ? "小地图已显示" : "小地图已隐藏";
        break;
      case MENU:
        cloudClearConfirm=false;scenePanel=false;capturePanel=false;logsOpen = videoPanel = false;
        selected = RESUME;
        menuOpen = !menuOpen;
        demoArmed = false;
        demoSynced = false;
        feedback = menuOpen ? "菜单已打开，输入快照持续上报" : "已返回场景，输入持续上报";
        break;
      case RESUME:
        if(scenePanel){scenePanel=false;selected=SCENE_PANEL;break;}
        if(capturePanel){capturePanel=false;selected=CAPTURE;break;}
        if (logsOpen) {
          logsOpen = false;
          selected = RESUME;
          break;
        }
        if (videoPanel) {
          videoPanel = false;
          selected = RESUME;
          break;
        }
        menuOpen = false;
        feedback = "已返回场景，输入持续上报";
        break;
      case SCENE_PANEL:
        scenePanel=true;capturePanel=logsOpen=videoPanel=false;menuOpen=true;selected=MODE_LIVE;break;
      case CAPTURE:
        scenePanel=false;
        capturePanel=true;logsOpen=videoPanel=false;menuOpen=true;selected=LIVE;break;
      case LOGS:
        scenePanel=false;
        capturePanel=false;
        logsOpen = true;
        videoPanel = false;
        menuOpen = true;
        selected = RESUME;
        logPage = 0;logWanted=100;logLoaded=0;logScroll=0;logEnd=false;
        demoArmed = demoSynced = false;
        feedback = "日志详情：射线扳机选择，左菜单键返回";
        break;
      case VIDEO_PANEL:
        scenePanel=false;
        capturePanel=false;
        videoPanel = true;
        logsOpen = false;
        selected = VIDEO_SMALL;
        feedback = "选择视频显示方式";
        break;
      case PREV:
        logPage = Math.max(0, logPage - 1);
        break;
      case NEXT:
        logPage = Math.min(Math.max(0, (logLines.length - 1) / 8), logPage + 1);
        break;
      default:
        break;
    }
  }
}
