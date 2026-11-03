package com.tanluzhe.controlterminal.vr.v2;
import android.media.*;
import android.opengl.*;
import android.os.*;
import android.view.Surface;
import com.tanluzhe.controlterminal.vr.AppLog;
import java.io.*;
import java.nio.*;
import java.util.concurrent.*;
import org.json.*;
/** Independent high-quality channel 1. No network rate control or VR recording buttons. */
final class ViewRecorder implements AutoCloseable {
  private final ScheduledThreadPoolExecutor worker = new ScheduledThreadPoolExecutor(1);
  private final ExecutorService graphics           = Executors.newSingleThreadExecutor();
  final RecordingStore store;
  private volatile CaptureConfig config = CaptureConfig.recordingDefaults();
  private volatile boolean active, closed, finalizing;
  private volatile long generation, rendered, samples, base = -1, lastPts = -1;
  private volatile String error = "", lastFile = "", encoder = "";
  private volatile float[] effective = new float[0];
  private boolean eos;
  private MediaCodec codec;
  private Surface input;
  private CaptureEgl egl;
  private MediaMuxer muxer;
  private MediaFormat format;
  private File partial;
  private int track = -1;
  private ScheduledFuture<?> timer;
  ViewRecorder(File directory) {
    store = new RecordingStore(directory);
    worker.setRemoveOnCancelPolicy(true);
  }
  private <T> T call(Callable<T> fn) throws Exception {
    if (closed)
      throw new IllegalStateException("录制服务已关闭");
    try {
      return worker.submit(fn).get(12, TimeUnit.SECONDS);
    } catch (ExecutionException e) {
      Throwable t = e.getCause();
      if (t instanceof Exception)
        throw (Exception) t;
      throw new IllegalStateException(t);
    } catch (TimeoutException e) {
      throw new IllegalStateException("录制操作处理中，请查询状态，勿重复提交");
    }
  }
  boolean active() {
    return active;
  }
  CaptureConfig config() {
    return config;
  }
  void configure(CaptureConfig next) throws Exception {
    call(() -> {
      if (active)
        throw new IllegalStateException("录制中不能更改录制配置，请先停止");
      config = next;
      return null;
    });
  }
  static MediaCodecInfo choose(CaptureConfig c) {
    for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
      if (!info.isEncoder())
        continue;
      if (Build.VERSION.SDK_INT >= 29 ? !info.isHardwareAccelerated()
                                      : info.getName().startsWith("OMX.google.") || info.getName().startsWith("c2.android."))
        continue;
      try {
        MediaCodecInfo.VideoCapabilities v = info.getCapabilitiesForType("video/avc").getVideoCapabilities();
        if (v.areSizeAndRateSupported(c.width, c.height, c.fps) && v.getBitrateRange().contains(c.bitrate))
          return info;
      } catch (Exception ignored) {
      }
    }
    throw new IllegalStateException("设备不支持请求的 H.264 分辨率/帧率/码率；未自动降低录制质量");
  }
  void start(EGLContext shared, boolean foreground) throws Exception {
    call(() -> {
      if (active)
        return null;
      if (!foreground || shared == null)
        throw new IllegalStateException("VR 不在可渲染前台");
      CaptureConfig c     = config;
      MediaCodecInfo info = choose(c);
      error               = "";
      eos=false;rendered = samples = 0;
      base = lastPts = -1;
      format         = null;
      effective      = new float[0];
      try {
        partial       = store.begin();
        encoder       = info.getName();
        codec         = MediaCodec.createByCodecName(encoder);
        MediaFormat f = MediaFormat.createVideoFormat("video/avc", c.width, c.height);
        f.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
        f.setInteger(MediaFormat.KEY_BIT_RATE, c.bitrate);
        f.setInteger(MediaFormat.KEY_FRAME_RATE, c.fps);
        f.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
        f.setInteger(MediaFormat.KEY_COLOR_STANDARD, MediaFormat.COLOR_STANDARD_BT709);
        f.setInteger(MediaFormat.KEY_COLOR_RANGE, MediaFormat.COLOR_RANGE_LIMITED);
        f.setInteger(MediaFormat.KEY_COLOR_TRANSFER, MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
        MediaCodecInfo.CodecCapabilities caps = info.getCapabilitiesForType("video/avc");
        for (MediaCodecInfo.CodecProfileLevel level : caps.profileLevels)
          if (level.profile == MediaCodecInfo.CodecProfileLevel.AVCProfileHigh) {
            f.setInteger(MediaFormat.KEY_PROFILE, level.profile);
            break;
          }
        if (Build.VERSION.SDK_INT >= 29)
          f.setInteger(MediaFormat.KEY_MAX_B_FRAMES, 0);
        codec.configure(f, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        input = codec.createInputSurface();
        codec.start();
        Surface surface = input;
        graphics
            .submit(() -> {
              if (egl == null)
                egl = new CaptureEgl(shared);
              egl.attach(surface);
            })
            .get(4, TimeUnit.SECONDS);
        generation++;
        active = true;
        timer  = worker.scheduleWithFixedDelay(() -> {
          try {
            drain();
          } catch (Exception e) {
            error = AppLog.reason(e);
            stopInternal();
          }
         }, 0, 5, TimeUnit.MILLISECONDS);
        NativeVr.captureConfigureTrack(1, c.width, c.height, c.fps, c.nativeValues(), generation);
        AppLog.info("RECORD", "START", c.width + "x" + c.height + " @" + c.fps + " bitrate=" + c.bitrate);
      } catch (Exception e) {
        error = AppLog.reason(e);
        stopInternal();
        throw e;
      }
      return null;
    });
  }
  boolean frame(int texture, int slot, long time, long fence, float[] framing, long version) {
    if (closed || !active || version != generation)
      return false;
    CaptureConfig c = config;
    effective       = framing.clone();
    try {
      graphics.execute(() -> {
        try {
          egl.consume(fence);
          if (active && version == generation) {
            egl.draw(texture, c.width, c.height, time);
            rendered++;
          }
        } catch (Exception e) {
          error = AppLog.reason(e);
          worker.execute(this::stopInternal);
        } finally {
          GLES20.glFinish();
          NativeVr.captureReleased(slot);
        }
      });
      return true;
    } catch (RejectedExecutionException e) {
      return false;
    }
  }
  private void drain() throws Exception {
    if (codec == null)
      return;
    MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
    for (int i = 0; i < 64; i++) {
      int index = codec.dequeueOutputBuffer(info, 0);
      if (index == MediaCodec.INFO_TRY_AGAIN_LATER)
        return;
      if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
        format = codec.getOutputFormat();
        if (format.getInteger(MediaFormat.KEY_WIDTH) != config.width || format.getInteger(MediaFormat.KEY_HEIGHT) != config.height)
          throw new IOException("实际录制画幅与请求不一致");
        continue;
      }
      if (index < 0)
        continue;
      try {
        if((info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0)eos=true;
        ByteBuffer data = codec.getOutputBuffer(index);
        if (data == null || info.size == 0 || (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0)
          continue;
        boolean key = (info.flags & MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0;
        if (muxer == null) {
          if (!key || format == null)
            continue;
          muxer = new MediaMuxer(partial.getAbsolutePath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
          track = muxer.addTrack(format);
          muxer.start();
          base = info.presentationTimeUs;
        }
        if (info.presentationTimeUs < lastPts)
          throw new IOException("录制时间戳倒退");
        lastPts = info.presentationTimeUs;
        data.position(info.offset);
        data.limit(info.offset + info.size);
        MediaCodec.BufferInfo sample = new MediaCodec.BufferInfo();
        sample.set(info.offset, info.size, info.presentationTimeUs - base, info.flags);
        muxer.writeSampleData(track, data, sample);
        samples++;
        if (samples % 60 == 0 && store.freeBytes() < 64L * 1024 * 1024)
          throw new IOException("磁盘空间低于64MiB，自动结束录制");
      } finally {
        codec.releaseOutputBuffer(index, false);
      }
    }
  }
  void stop() throws Exception {
    call(() -> {
      stopInternal();
      return null;
    });
  }
  private void stopInternal() {
    finalizing  = true;
    boolean was = active;
    active      = false;
    generation++;
    if (timer != null) {
      timer.cancel(false);
      timer = null;
    }
    try {
      NativeVr.captureConfigureTrack(1, 0, 0, config.fps, config.nativeValues(), generation);
    } catch (Throwable ignored) {
    }
    if (codec != null) {
      try {
        Future<?> detach = graphics.submit(() -> {
          if (egl != null)
            egl.detach();
        });
        long end         = System.nanoTime() + 3_000_000_000L;
        while (!detach.isDone() && System.nanoTime() < end) {
          drain();
          Thread.sleep(2);
        }
        detach.get(1, TimeUnit.SECONDS);
        codec.signalEndOfInputStream();
        end = System.nanoTime() + 3_000_000_000L;
        while (!eos&&System.nanoTime() < end) {
          drain();
          Thread.sleep(3);
        }
      } catch (Exception e) {
        error = AppLog.reason(e);
      } finally {
        try {
          codec.stop();
        } catch (Exception ignored) {
        }
        try {
          codec.release();
        } catch (Exception ignored) {
        }
        codec = null;
      }
    }
    if (input != null) {
      input.release();
      input = null;
    }
    boolean valid = false;
    if (muxer != null) {
      try {
        muxer.stop();
        valid = samples > 0;
      } catch (Exception e) {
        error = AppLog.reason(e);
      } finally {
        try {
          muxer.release();
        } catch (Exception ignored) {
        }
        muxer = null;
      }
    }
    if (partial != null && valid)
      try {
        JSONObject meta = ViewCapture.json(config)
                              .put("samples", samples)
                              .put("duration_ms", Math.max(0, (lastPts - base) / 1000))
                              .put("actual_encoded_fps", samples > 1 && lastPts > base ? (samples - 1) * 1000000.0 / (lastPts - base) : 0)
                              .put("codec", "avc")
                              .put("encoder", encoder);
        lastFile = store.finish(partial, meta).getName();
      } catch (Exception e) {
        error = AppLog.reason(e);
      }
    store.abandon();
    partial    = null;
    format     = null;
    track      = -1;
    finalizing = false;
    if (was)
      AppLog.info("RECORD", "STOP", "samples=" + samples + " file=" + lastFile + " error=" + error);
  }
  JSONObject status() throws JSONException {
    return new JSONObject()
        .put("recording", active)
        .put("finalizing", finalizing)
        .put("session_id", generation)
        .put("config", ViewCapture.json(config))
        .put("exported_frames", rendered)
        .put("encoded_frames", samples)
        .put("effective", new JSONArray(effective))
        .put("duration_ms", base >= 0 ? Math.max(0, (lastPts - base) / 1000) : 0)
        .put("actual_encoded_fps", samples > 1 && lastPts > base ? (samples - 1) * 1000000.0 / (lastPts - base) : 0)
        .put("last_file", lastFile.isEmpty() ? JSONObject.NULL : lastFile)
        .put("free_bytes", store.freeBytes())
        .put("encoder", encoder)
        .put("error", error);
  }
  public void close() {
    if (closed)
      return;
    try {
      stop();
      graphics
          .submit(() -> {
            if (egl != null) {
              egl.close();
              egl = null;
            }
          })
          .get(4, TimeUnit.SECONDS);
    } catch (Exception e) {
      error = AppLog.reason(e);
    }
    closed = true;
    worker.shutdown();
    graphics.shutdown();
  }
}
