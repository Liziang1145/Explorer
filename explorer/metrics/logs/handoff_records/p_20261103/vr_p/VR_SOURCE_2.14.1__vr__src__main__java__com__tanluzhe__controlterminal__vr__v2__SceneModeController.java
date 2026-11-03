package com.tanluzhe.controlterminal.vr.v2;
import android.content.*;
import android.os.*;
import com.tanluzhe.cloud.*;
import com.tanluzhe.controlterminal.vr.AppLog;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.json.*;
/** Owns only the point-cloud layer in the normal VR activity. Control/video remain connected. */
final class SceneModeController implements AutoCloseable {
  private final Context context;
  private final VrUiState ui;
  private final Handler main       = new Handler(Looper.getMainLooper());
  private final ExecutorService io = Executors.newSingleThreadExecutor();
  private final AtomicLong epoch   = new AtomicLong();
  private volatile boolean closed, paused;
  private CloudStream scene;
  private LiveCloudStream live;
  private final boolean demo;
  private volatile HttpURLConnection catalogConnection;
  private volatile String catalogError = "";
  private long lastLog,cacheRefreshAt;
  private boolean cacheRefreshing;
  final SceneExtensions extensions = new SceneExtensions();
  SceneModeController(Context context, VrUiState ui, boolean demo) {
    this.context = context;
    this.ui      = ui;
    this.demo    = demo;
  }
  void ready() {
    if (demo) {
      ui.cloudModeStatus = "实时模式 · 本地演示未联网";
      NativeVr.coloredSceneView(0, true, false);
    } else
      toLive();
    loadLocalCatalog();
  }
  private void stopSources() {
    if (scene != null) {
      CloudStream.CacheProgress p=scene.cacheProgress;Map<String,SceneCacheInfo> caches=new HashMap<>(ui.sceneCaches);caches.put(scene.config().scene,new SceneCacheInfo(p.fraction,0,p.bytes,p.complete));ui.sceneCaches=Collections.unmodifiableMap(caches);
      scene.close();
      scene = null;
    }
    if (live != null) {
      live.close();
      live = null;
    }
  }
  void toLive() {
    if (closed)
      return;
    stopSources();
    long serial         = epoch.incrementAndGet();
    ui.integratedStatic = false;
    ui.cloudModeError   = "";
    ui.cloudModeStatus  = "实时模式 · 连接 VCL1";
    NativeVr.coloredSceneView(0, true, false);
    CloudNative.configure(0, new String[0], new float[0]);
    NativeVr.liveCloudVisible(false);
    try {
      String base = CloudSettings.prefs(context).getString("live_url", "http://192.168.137.2:8088");
      ui.sceneServiceAddress=base;
      live        = new LiveCloudStream(base, "1", new LiveCloudStream.Sink() {
        public void reset(long g) {
          if (!closed && serial == epoch.get())
            NativeVr.liveCloudReset(g);
        }
        public boolean offer(long g, ByteBuffer raw, float[] matrix) {
          return !closed && serial == epoch.get() && NativeVr.liveCloud(g, raw, matrix);
        }
        public void visible(boolean visible) {
          if (!closed && serial == epoch.get())
            NativeVr.liveCloudVisible(visible);
        }
      });
      live.pause(paused);
      live.start();
      AppLog.info("SCENE", "MODE_LIVE", base + "; legacy scene channel disabled");
    } catch (Exception e) {
      ui.cloudModeError = "实时连接配置无效";
    }
  }
  void toScene(String id) {
    if (closed)
      return;
    stopSources();
    long serial = epoch.incrementAndGet();
    NativeVr.liveCloudVisible(false);
    CloudNative.configure(0, new String[0], new float[0]);
    ui.sceneCacheFraction = 0;
    ui.integratedStatic   = true;
    ui.cloudModeError     = "";
    ui.cloudModeStatus    = "场景模式 · 准备缓存";
    CloudSettings.prefs(context).edit().putString("scene", id).apply();
    NativeVr.coloredSceneView(3, true, true);
    CloudNative.recenter(CloudSettings.floor(context, CloudSettings.prefs(context).getString("scene", CloudStream.DENSE)));
    CloudStream.Sink nativeSink = CloudNative.sink();
    CloudStream.Sink guarded    = new CloudStream.Sink() {
      private boolean valid() {
        return !closed && serial == epoch.get();
      }
      public void reset(long g, List<CloudStream.Block> blocks) {
        if (valid())
          nativeSink.reset(g, blocks);
      }
      public boolean offer(long g, CloudStream.Block b, ByteBuffer raw, boolean coarse) {
        return valid() && nativeSink.offer(g, b, raw, coarse);
      }
      public Set<String> resident(long g) {
        return valid() ? nativeSink.resident(g) : Collections.emptySet();
      }
      public Set<String> pending(long g) {
        return valid() ? nativeSink.pending(g) : Collections.emptySet();
      }
      public void policy(long g, float radius) {
        if (valid())
          nativeSink.policy(g, radius);
      }
      public void retain(long g, Set<String> ids) {
        if (valid())
          nativeSink.retain(g, ids);
      }
    };
    try {
      CloudStream next = new CloudStream(CloudSettings.config(context), CloudSettings.cache(context), guarded);
      scene            = next;ui.sceneServiceAddress=next.config().base+" · "+next.config().profile;
      next.pause(paused);
      io.execute(() -> {
        CloudSettings.seedCoarse(context, next);
        if (!closed && serial == epoch.get())
          next.start();
      });
      AppLog.info("SCENE", "MODE_STATIC", id + "; control/video preserved; no navigation command");
    } catch (Exception e) {
      ui.cloudModeError = "场景配置无效";
    }
  }
  boolean action(int action) {
    if(Looper.myLooper()!=Looper.getMainLooper()){
      boolean handled=action==VrUiState.MODE_TOGGLE||(action>=VrUiState.MODE_LIVE&&action<=VrUiState.SCENE_CLEAR_ALL)||(action>=VrUiState.SCENE_ITEM&&action<VrUiState.SCENE_ITEM+ui.sceneCatalogIds.length)||action==VrUiState.SCENE_RESET||action==VrUiState.CLOUD_FLOOR_UP||action==VrUiState.CLOUD_FLOOR_DOWN||action==VrUiState.CLOUD_CLEAR_YES||action==VrUiState.CLOUD_CLEAR_NO;
      if(handled||action==VrUiState.SCENE_PANEL)main.post(()->{if(!closed)action(action);});
      return handled;
    }
    if (action == VrUiState.SCENE_PANEL) {
      refreshCatalog();
      return false;
    }
    if(action==VrUiState.MODE_TOGGLE){if(ui.integratedStatic)toLive();else toScene(CloudSettings.prefs(context).getString("scene",CloudStream.DENSE));return true;}
    if (action == VrUiState.MODE_LIVE) {
      toLive();
      return true;
    }
    if (action == VrUiState.MODE_SCENE) {
      toScene(CloudSettings.prefs(context).getString("scene", CloudStream.DENSE));
      return true;
    }
    if (action == VrUiState.SCENE_CATALOG) {
      refreshCatalog();
      return true;
    }
    if (action >= VrUiState.SCENE_ITEM && action < VrUiState.SCENE_ITEM + ui.sceneCatalogIds.length) {
      int at = action - VrUiState.SCENE_ITEM;
      if (at < ui.sceneCatalogIds.length)
        toScene(ui.sceneCatalogIds[at]);
      return true;
    }
    if (action == VrUiState.SCENE_CLEAR || action == VrUiState.SCENE_CLEAR_ALL) {
      ui.sceneDeleteAll    = action == VrUiState.SCENE_CLEAR_ALL;
      ui.sceneDeleteLabel=ui.sceneDeleteAll?"全部场景（含固定保留的粗图）":CloudSettings.prefs(context).getString("scene",CloudStream.DENSE);
      ui.cloudClearConfirm = true;
      return true;
    }
    if (action == VrUiState.CLOUD_CLEAR_NO) {
      ui.cloudClearConfirm = false;
      return true;
    }
    if (action == VrUiState.CLOUD_CLEAR_YES) {
      ui.cloudClearConfirm = false;
      boolean all          = ui.sceneDeleteAll;
      String id            = CloudSettings.prefs(context).getString("scene", CloudStream.DENSE);
      CloudStream previous = scene;
      if (ui.integratedStatic)
        toLive();
      ui.cloudCacheStatus = "停止下载并清理缓存…";
      io.execute(() -> {
        if (previous != null)
          previous.awaitStopped();
        File root = CloudSettings.cache(context);
        CloudStream.clearCache(all ? root : new File(root, id));
        main.post(() -> {
          if (!closed)
            {ui.cloudCacheStatus = "缓存已清除；再次选场景后按需下载";Map<String,SceneCacheInfo> caches=new HashMap<>(ui.sceneCaches);if(all)caches.clear();else caches.remove(id);ui.sceneCaches=Collections.unmodifiableMap(caches);}
        });
      });
      return true;
    }
    if (action == VrUiState.SCENE_RESET) {
      if (ui.integratedStatic)
        CloudNative.recenter(CloudSettings.floor(context, CloudSettings.prefs(context).getString("scene", CloudStream.DENSE)));
      return true;
    }
    if (action == VrUiState.CLOUD_FLOOR_UP || action == VrUiState.CLOUD_FLOOR_DOWN) {
      String selected = CloudSettings.prefs(context).getString("scene", CloudStream.DENSE);
      float floor     = CloudSettings.floor(context, selected) + (action == VrUiState.CLOUD_FLOOR_UP ? .1f : -.1f);
      CloudSettings.prefs(context).edit().putFloat("scene_floor:" + selected, floor).apply();
      if (ui.integratedStatic)
        CloudNative.recenter(floor);
      return true;
    }
    return false;
  }
  void update() {
    if (closed)
      return;
    if (scene != null) {
      try {
        scene.position(CloudNative.head());
      } catch (Exception ignored) {
      }
      ui.cloudModeStatus = "场景模式 · " + scene.sceneName + " · 未配准 · " + (scene.coarseReady ? "粗图已显示" : "粗图准备中");
      ui.cloudCacheStatus = "近区缓存 " + scene.nearDiskDone + "/" + scene.nearTotal + " · 显示 " + scene.nearDone + "/" + scene.nearTotal
          + " · " + String.format(Locale.ROOT, "磁盘 %.1f MiB", scene.diskBytes / 1048576.0)
          + (scene.nearTotal > 0 && scene.nearDiskDone == scene.nearTotal ? " · 当前近区缓存完成" : "");
      CloudStream.CacheProgress progress=scene.cacheProgress;ui.sceneCacheFraction=(float)progress.fraction;
      Map<String,SceneCacheInfo> caches=new HashMap<>(ui.sceneCaches);caches.put(scene.config().scene,new SceneCacheInfo(progress.fraction,progress.rate,progress.bytes,progress.complete));ui.sceneCaches=Collections.unmodifiableMap(caches);
      ui.cloudModeError     = scene.error;
      long[] gpu            = CloudNative.stats();
      ui.cloudCacheStatus += String.format(Locale.ROOT," · GPU %.1f MiB",gpu[1]/1048576.0);
      if (gpu[6] == 1 || gpu[6] == 2)
        ui.cloudModeError += " GPU预算/上传受限，保留粗图";
      ui.sceneStats = gpu;
    }
    if (live != null) {
      ui.cloudModeStatus = "实时模式 · " + live.summary();
      ui.cloudModeError  = live.error;
    }
    if (android.os.SystemClock.elapsedRealtime() - lastLog > 5000) {
      lastLog = android.os.SystemClock.elapsedRealtime();
      AppLog.info("SCENE", "STATUS", ui.cloudModeStatus + "; " + ui.cloudCacheStatus + "; " + ui.cloudModeError);
    }
    if(ui.scenePanel&&!cacheRefreshing&&android.os.SystemClock.elapsedRealtime()-cacheRefreshAt>4000){cacheRefreshAt=android.os.SystemClock.elapsedRealtime();cacheRefreshing=true;String active=scene==null?"":scene.config().scene;String[] ids=ui.sceneCatalogIds.clone();io.execute(()->{Map<String,SceneCacheInfo> caches=new HashMap<>();for(String id:ids){CloudStream.CacheProgress p=CloudStream.readCacheProgress(CloudSettings.cache(context),id);caches.put(id,new SceneCacheInfo(p.fraction,0,p.bytes,p.complete));}main.post(()->{cacheRefreshing=false;if(!closed){SceneCacheInfo current=ui.sceneCaches.get(active);if(current!=null)caches.put(active,current);ui.sceneCaches=Collections.unmodifiableMap(caches);}});});}
    if (!catalogError.isEmpty())
      ui.cloudModeError += (ui.cloudModeError.isEmpty() ? "" : " · ") + catalogError;
  }
  long receivedNs(){return live!=null?live.lastFrameNs:scene!=null?scene.lastDataNs:0;}
  private File catalogFile() {
    File root = CloudSettings.cache(context);
    root.mkdirs();
    return new File(root, "catalog.json");
  }
  private void loadLocalCatalog() {
    io.execute(() -> {
      try {
        File file = catalogFile();
        if (file.length() > 1048576)
          return;
        String text = new String(java.nio.file.Files.readAllBytes(file.toPath()), "UTF-8");
        publishCatalog(new JSONObject(text));
      } catch (Exception ignored) {
      }
    });
  }
  private void publishCatalog(JSONObject response) throws Exception {
    JSONArray rows = response.getJSONArray("scenes");
    if (rows.length() > 500)
      throw new IOException("目录过长");
    String[] ids = new String[rows.length()], labels = new String[rows.length()];
    for (int i = 0; i < rows.length(); i++) {
      JSONObject row = rows.getJSONObject(i);
      ids[i]         = row.getString("scene_id");
      if (!ids[i].matches("[A-Za-z0-9_-]{1,120}"))
        throw new IOException("场景ID无效");
      labels[i] = row.optString("label", ids[i]);
      if (labels[i].length() > 240)
        labels[i] = labels[i].substring(0, 240);
    }
    Map<String,SceneCacheInfo> caches=new HashMap<>();for(String id:ids){CloudStream.CacheProgress p=CloudStream.readCacheProgress(CloudSettings.cache(context),id);caches.put(id,new SceneCacheInfo(p.fraction,0,p.bytes,p.complete));}
    main.post(() -> {
      if (!closed) {
        ui.sceneCaches=Collections.unmodifiableMap(caches);
        ui.sceneScroll=0;
        ui.sceneCatalogIds    = ids;
        ui.sceneCatalogLabels = labels;
      }
    });
  }
  void refreshCatalog() {
    if (closed)
      return;
    io.execute(() -> {
      HttpURLConnection c = null;
      try {
        CloudStream.Config cfg = CloudSettings.config(context);
        c                      = (HttpURLConnection) new URL(cfg.base + "api/v2/catalog").openConnection(Proxy.NO_PROXY);
        catalogConnection      = c;
        c.setConnectTimeout(4000);
        c.setReadTimeout(6000);
        c.setInstanceFollowRedirects(false);
        c.setRequestProperty("Authorization", "Bearer 1");
        if (c.getResponseCode() != 200)
          throw new IOException("HTTP " + c.getResponseCode());
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (InputStream in = c.getInputStream()) {
          byte[] b = new byte[8192];
          int n;
          while ((n = in.read(b)) != -1) {
            if (out.size() + n > 1048576)
              throw new IOException("目录过长");
            out.write(b, 0, n);
          }
        }
        byte[] bytes        = out.toByteArray();
        JSONObject response = new JSONObject(new String(bytes, "UTF-8"));
        publishCatalog(response);
        catalogError = "";
        File target  = catalogFile();
        try (FileOutputStream file = new FileOutputStream(target)) {
          file.write(bytes);
        }
        AppLog.info("SCENE", "CATALOG", "entries=" + response.getJSONArray("scenes").length());
      } catch (Exception e) {
        main.post(() -> {
          if (!closed)
            catalogError = "AIPC场景列表不可达；保留本地缓存目录";
        });
      } finally {
        catalogConnection = null;
        if (c != null)
          c.disconnect();
      }
    });
  }
  void foreground(boolean active) {
    paused = !active;
    if (live != null)
      live.pause(!active);
    if (scene != null)
      scene.pause(!active);
  }
  SceneExtensions.Context extensionContext() {
    if (!ui.integratedStatic || scene == null || scene.manifestRevision.isEmpty())
      throw new IllegalStateException("仅静态场景支持场景坐标扩展");
    return new SceneExtensions.Context(scene.config().scene, scene.manifestRevision, CloudNative.anchor());
  }
  public void close() {
    closed = true;
    epoch.incrementAndGet();
    HttpURLConnection c = catalogConnection;
    if (c != null)
      c.disconnect();
    stopSources();
    io.shutdownNow();
  }
}
