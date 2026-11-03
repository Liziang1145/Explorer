package com.tanluzhe.controlterminal.vr.v2;

import android.content.Context;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.view.Surface;
import androidx.media3.common.*;
import androidx.media3.common.util.TimestampAdjuster;
import androidx.media3.datasource.okhttp.OkHttpDataSource;
import androidx.media3.exoplayer.*;
import androidx.media3.exoplayer.analytics.AnalyticsListener;
import androidx.media3.exoplayer.mediacodec.MediaCodecUtil;
import androidx.media3.exoplayer.source.ProgressiveMediaSource;
import androidx.media3.exoplayer.upstream.DefaultLoadErrorHandlingPolicy;
import androidx.media3.exoplayer.upstream.LoadErrorHandlingPolicy;
import androidx.media3.extractor.Extractor;
import androidx.media3.extractor.mp4.FragmentedMp4Extractor;
import androidx.media3.extractor.text.SubtitleParser;
import com.tanluzhe.controlterminal.vr.AppLog;
import java.net.URI;
import java.util.*;
import java.util.concurrent.*;
import okhttp3.*;
import org.json.*;

/** Independent authenticated HEVC/fMP4 subscription. One hardware decoder per subscribed source; no RTP. */
@androidx.media3.common.util.UnstableApi
public final class DirectHevcVideo implements AutoCloseable {
  private final Context context;
  private final Surface surface;
  private final Dashboard ui;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final ExecutorService discovery = Executors.newSingleThreadExecutor();
  private final OkHttpClient http = new OkHttpClient.Builder()
                                        .followRedirects(false)
                                        .followSslRedirects(false)
                                        .retryOnConnectionFailure(false)
                                        .connectTimeout(5, TimeUnit.SECONDS)
                                        .readTimeout(6, TimeUnit.SECONDS)
                                        .callTimeout(8,TimeUnit.SECONDS)
                                        .build();
  private final String root, token;
  private String kind,quality="720p15",clientId="";private boolean nativeMedia;private volatile boolean fatal,feedbackPending;private long feedbackAt,feedbackFrames,dropped;
  private final VideoReconnect reconnectPolicy=new VideoReconnect();
  private void cancelReconnect(){main.removeCallbacks(reconnectTask);retryPending=false;}
  private ExoPlayer player;
  private String cameraUrl, depthUrl;
  private boolean depth, foreground = true, closed, retryPending, discovering;
  private final Runnable reconnectTask=()->{retryPending=false;if(!closed&&foreground&&!fatal)open();};

  private volatile long lastFrame;
  private long consumedAt,consumedFrames;
  public volatile boolean outputReady;
  private volatile int generation;

  public DirectHevcVideo(Context c, String host, int port, String key, Surface s, Dashboard d) {
    context = c;
    root = BaseLink.endpoint("http", host, port);
    token = key;
    surface = s;
    ui = d;
  }
  public DirectHevcVideo(Context c,String host,int port,String key,Surface surface,Dashboard state,String kind,String quality){this(c,host,port,key,surface,state);if(!Arrays.asList(CameraLayout.KINDS).contains(kind))throw new IllegalArgumentException("未支持的摄像头");this.kind=kind;this.quality=quality;nativeMedia=true;}
  public void quality(String value){if(!Arrays.asList("auto","720p30","720p15","540p15","240p15").contains(value))throw new IllegalArgumentException("视频档位");main.post(()->{if(closed||quality.equals(value))return;quality=value;restart("视频档位更新");});}
  public void start() {
    main.post(() -> {
      discover();
      main.post(watchdog);
    });
  }
  public void select(boolean useDepth) {
    main.post(() -> {
      if (depth == useDepth)
        return;
      depth = useDepth;
      ui.videoSource = nativeMedia ? kind : depth ? "伪彩深度（非度量值）" : "RGB 相机";
      restart("切换媒体源");
    });
  }
  public void foreground(boolean active) {
    main.post(() -> {
      foreground = active;
      if (!active){cancelReconnect();releasePlayer();}
      else if (!closed&&!retryPending&&!fatal)open();
    });
  }
  private void discover() {
    if (closed || fatal || discovering)
      return;
    discovering = true;
    discovery.execute(() -> {
      try {
        Request request = new Request.Builder()
                              .url(root + (nativeMedia?"/status":"/v2/media"))
                              .header("Authorization", "Bearer " + token)
                              .build();
        JSONObject descriptor;
        try (Response response = http.newCall(request).execute()) {
          if(VideoReconnect.authorizationFailure(response.code()))fatal=true;
          if (!response.isSuccessful() || response.body() == null)
            throw new IllegalStateException((nativeMedia?"/status":"/v2/media")+" HTTP " + response.code());
          java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
          java.io.InputStream in = response.body().byteStream();
          byte[] buffer = new byte[4096];
          int n;
          while ((n = in.read(buffer)) != -1) {
            if (bytes.size() + n > 1048576)
              throw new IllegalArgumentException("media descriptor too large");
            bytes.write(buffer, 0, n);
          }
          descriptor = new JSONObject(bytes.toString("UTF-8"));
        }
        if(nativeMedia){if(!"HEVC".equalsIgnoreCase(descriptor.optString("codec"))||!descriptor.getJSONObject("streams").has(kind))throw new IllegalArgumentException("六路服务未提供"+kind);main.post(()->{discovering=false;if(!closed){cameraUrl=root+"/stream/"+kind;open();}});return;}
        if (!"HEVC".equalsIgnoreCase(descriptor.optString("codec"))
            || !"hevc-fmp4".equals(descriptor.optString("transport")))
          throw new IllegalArgumentException("AIPC未声明HEVC/hevc-fmp4");
        String camera = streamUrl(descriptor, "camera", "rgb", "/v2/media/hevc/camera");
        String dep = streamUrl(descriptor, "depth", "depth", "/v2/media/hevc/depth");
        main.post(() -> {
          discovering = false;
          if (closed)
            return;
          cameraUrl = camera;
          depthUrl = dep;
          open();
        });
      } catch (Exception error) {
        main.post(() -> {
          discovering = false;
          if (!closed)
            retry("媒体发现失败：" + AppLog.reason(error));
        });
      }
    });
  }
  private String streamUrl(JSONObject descriptor, String name, String alias, String fallback)
      throws Exception {
    Object streams = descriptor.opt("streams"), stream = null;
    if (streams instanceof JSONObject) {
      JSONObject map = (JSONObject) streams;
      stream = map.opt(name);
      if (stream == null)
        stream = map.opt(alias);
    }
    if (streams instanceof JSONArray) {
      JSONArray a = (JSONArray) streams;
      for (int i = 0; i < a.length(); i++) {
        JSONObject item = a.optJSONObject(i);
        if (item != null
            && (name.equals(item.optString("name")) || alias.equals(item.optString("name"))))
          stream = item;
      }
    }
    String path = stream instanceof String ? (String) stream
        : stream instanceof JSONObject
        ? ((JSONObject) stream).optString("url", ((JSONObject) stream).optString("path", fallback))
        : fallback;
    URI base = new URI(root), url = base.resolve(path);
    if (!Objects.equals(base.getScheme(), url.getScheme())
        || !Objects.equals(base.getHost(), url.getHost()) || base.getPort() != url.getPort()
        || url.getUserInfo() != null)
      throw new IllegalArgumentException("媒体地址必须来自当前AIPC");
    return url.toString();
  }
  private void open() {
    try {
      openInternal();
    } catch (Exception error) {
      retry("HEVC初始化失败：" + AppLog.reason(error));
    }
  }
  private void openInternal() {
    if (closed || fatal || !foreground || player != null)
      return;
    if (cameraUrl == null) {
      discover();
      return;
    }
    outputReady = false;
    ui.videoWidth = ui.videoHeight = 0;
    ui.videoReceived = 0;
    ui.videoAge = Double.NaN;
    ui.videoLoss = Double.NaN;
    ui.videoSource = nativeMedia ? kind : depth ? "伪彩深度（非度量值）" : "RGB 相机";
    ui.videoStatus = "等待硬件解码";
    final int attempt = ++generation;
    DefaultRenderersFactory renderers =
        new DefaultRenderersFactory(context).setEnableDecoderFallback(false).setMediaCodecSelector(
            (mime, secure, tunnel) -> {
              java.util.List<androidx.media3.exoplayer.mediacodec.MediaCodecInfo> choices =
                  new ArrayList<>();
              for (androidx.media3.exoplayer.mediacodec.MediaCodecInfo info :
                  MediaCodecUtil.getDecoderInfos(mime, secure, tunnel))
                if (MimeTypes.VIDEO_H265.equals(mime) && info.hardwareAccelerated
                    && !info.softwareOnly)
                  choices.add(info);
              return choices;
            });
    player = new ExoPlayer.Builder(context, renderers)
                 .setLoadControl(new DefaultLoadControl.Builder()
                                     .setBufferDurationsMs(50, 300, 0, 50)
                                     .setTargetBufferBytes(4 * 1024 * 1024)
                                     .setPrioritizeTimeOverSizeThresholds(true)
                                     .build())
                 .build();
    player.setTrackSelectionParameters(player.getTrackSelectionParameters()
                                           .buildUpon()
                                           .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, true)
                                           .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                                           .build());
    player.setVideoSurface(surface);
    player.setVideoFrameMetadataListener((pts, release, format, mediaFormat) -> {
      if (attempt != generation)
        return;
      lastFrame = System.nanoTime();
      ui.videoPtsUs = pts;ui.videoFrames++;
    });
    player.addAnalyticsListener(new AnalyticsListener() {
      @Override public void onDroppedVideoFrames(EventTime time,int count,long elapsed){if(attempt==generation)dropped+=count;}
      @Override
      public void onVideoDecoderInitialized(
          EventTime time, String name, long initialized, long duration) {
        if (attempt != generation)
          return;
        ui.videoDecoder = name;
        AppLog.info("VIDEO", "HEVC_DECODER", name + " source=" + (nativeMedia?kind:depth ? "depth" : "camera"));
      }
    });
    player.addListener(new Player.Listener() {
      @Override
      public void onVideoSizeChanged(VideoSize size) {
        if (attempt != generation)
          return;
        ui.videoWidth = size.width;
        ui.videoHeight = size.height;
        ui.videoPixelRatio = size.pixelWidthHeightRatio;
      }
      @Override
      public void onRenderedFirstFrame() {
        if (attempt != generation)
          return;
        outputReady = true;reconnectPolicy.recovered();
        ui.videoStatus = "硬件播放中";
        AppLog.info("VIDEO", "HEVC_FIRST_FRAME", ui.videoSource);
      }
      @Override
      public void onPlayerError(PlaybackException error) {
        if (attempt == generation){Throwable cause=error;while(cause!=null){if(cause instanceof androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException){int code=((androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException)cause).responseCode;if(VideoReconnect.authorizationFailure(code))fatal=true;}cause=cause.getCause();}
          retry("HEVC播放失败 " + error.getErrorCodeName() + "：" + AppLog.reason(error));}
      }
      @Override
      public void onPlaybackStateChanged(int state) {
        if (attempt == generation && state == Player.STATE_ENDED)
          retry("视频EOF，重新获取初始化段");
      }
    });
    OkHttpDataSource.Factory data = new OkHttpDataSource.Factory(http).setDefaultRequestProperties(
        Collections.singletonMap("Authorization", "Bearer " + token));
    ProgressiveMediaSource.Factory media =
        new ProgressiveMediaSource
            .Factory(data,
                ()
                    -> new Extractor[] {
                        new FragmentedMp4Extractor(SubtitleParser.Factory.UNSUPPORTED, 0,
                            new TimestampAdjuster(0), null, Collections.emptyList(), null)})
            .setLoadErrorHandlingPolicy(new DefaultLoadErrorHandlingPolicy(0) {
              @Override
              public long getRetryDelayMsFor(LoadErrorHandlingPolicy.LoadErrorInfo info) {
                return C.TIME_UNSET;
              }
            });
    lastFrame = System.nanoTime();consumedAt=lastFrame;consumedFrames=ui.videoSubmitted;clientId=UUID.randomUUID().toString().replace("-","");feedbackAt=lastFrame;feedbackFrames=ui.videoSubmitted;dropped=0;
    player.setMediaSource(
        media.createMediaSource(new MediaItem.Builder()
                                    .setUri(Uri.parse(nativeMedia?root+CameraLayout.streamPath(kind,quality,clientId):depth ? depthUrl : cameraUrl))
                                    .setMimeType(MimeTypes.VIDEO_MP4)
                                    .build()));
    player.prepare();
    player.play();
    AppLog.info(
        "VIDEO", "HEVC_OPEN", (nativeMedia?kind:depth ? "depth" : "camera") + " fresh timeline; buffer=50..300ms");
  }
  private final Runnable watchdog = new Runnable() {
    public void run() {
      if (closed)
        return;
      if (player != null && foreground) {
        long now = System.nanoTime();
        if(consumedFrames!=ui.videoSubmitted){consumedFrames=ui.videoSubmitted;consumedAt=now;}
        if(nativeMedia&&now-feedbackAt>=3_000_000_000L)feedback(now);
        if(now-consumedAt>6_000_000_000L)retry("6秒没有画面消费，重建独立订阅");
        else if (now - lastFrame > 6_000_000_000L)
          retry("6秒没有解码输出，丢弃旧订阅");
        else if (outputReady && player.getTotalBufferedDuration() > 1500)
          retry("视频积压，重新订阅最新GOP");
      }
      if(player==null&&foreground&&!fatal&&!retryPending&&!discovering)open();
      main.postDelayed(this, 500);
    }
  };
  private void feedback(long now){
    if(feedbackPending||player==null)return;double seconds=(now-feedbackAt)/1e9;long count=ui.videoSubmitted-feedbackFrames;double buffer=player.getTotalBufferedDuration()/1000.0;boolean stalled=now-lastFrame>2_000_000_000L;double loss=dropped/(double)Math.max(1,count+dropped);String id=clientId;int attempt=generation;feedbackAt=now;feedbackFrames=ui.videoSubmitted;dropped=0;feedbackPending=true;
    discovery.execute(()->{try{if(closed||attempt!=generation)return;JSONObject json=new JSONObject().put("client_id",id).put("stalled",stalled).put("buffer",buffer).put("drop_ratio",Math.min(1,loss)).put("fps",Math.max(0,count/seconds));Request request=new Request.Builder().url(root+"/feedback/"+kind).header("Authorization","Bearer "+token).post(RequestBody.create(MediaType.parse("application/json"),json.toString())).build();try(Response response=http.newCall(request).execute()){int code=response.code();if(VideoReconnect.authorizationFailure(code))main.post(()->{if(!closed&&attempt==generation){fatal=true;retry("媒体反馈 HTTP "+code);}});}}catch(Exception ignored){}finally{feedbackPending=false;}});
  }
  private void restart(String reason) {
    if (closed)
      return;
    cancelReconnect();releasePlayer();open();
  }
  private void retry(String reason) {
    if (closed || retryPending)
      return;
    if(fatal){releasePlayer();ui.videoStatus=reason+"；请检查媒体权限/通道后重新连接";return;}
    retryPending = true;
    releasePlayer();cameraUrl=null;depthUrl=null;
    int delay=reconnectPolicy.nextDelayMillis();
    ui.videoStatus=reason+"；"+(delay/1000)+"秒后重连";
    AppLog.warn("VIDEO","HEVC_RETRY",(nativeMedia?kind+": ":"")+reason+" delay_ms="+delay);
    main.removeCallbacks(reconnectTask);main.postDelayed(reconnectTask,delay);
  }

  private void releasePlayer() {
    generation++;
    outputReady = false;
    ui.videoWidth = ui.videoHeight = 0;
    ui.videoReceived = 0;
    if (player != null) {
      ExoPlayer old = player;
      player = null;
      try{old.release();}catch(RuntimeException e){AppLog.warn("VIDEO","HEVC_RELEASE",AppLog.reason(e));}
    }
  }
  @Override
  public void close() {
    closed = true;
    main.removeCallbacksAndMessages(null);
    releasePlayer();
    http.dispatcher().cancelAll();
    http.connectionPool().evictAll();
    discovery.shutdownNow();
  }
}
