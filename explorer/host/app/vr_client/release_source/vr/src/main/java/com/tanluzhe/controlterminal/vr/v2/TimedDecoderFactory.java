package com.tanluzhe.controlterminal.vr.v2;
import org.webrtc.*;

/** Hardware only, with a decoded-frame tap before WebRTC rewrites render timestamps. */
public final class TimedDecoderFactory implements VideoDecoderFactory {
  private final HardwareVideoDecoderFactory hardware;
  private final VideoSink sink;
  private final Dashboard ui;
  private final VideoTiming timing;
  public TimedDecoderFactory(EglBase.Context context, VideoSink s, Dashboard d, VideoTiming t) {
    hardware = new HardwareVideoDecoderFactory(context);
    sink = s;
    ui = d;
    timing = t;
  }
  @Override
  public VideoCodecInfo[] getSupportedCodecs() {
    return hardware.getSupportedCodecs();
  }
  @Override
  public VideoDecoder createDecoder(VideoCodecInfo info) {
    if (!info.name.equalsIgnoreCase("H264"))
      return null;
    VideoDecoder real = hardware.createDecoder(info);
    if (real == null)
      return null;
    return new VideoDecoder() {
      public VideoCodecStatus initDecode(Settings s, Callback cb) {
        return real.initDecode(s, (frame, ms, qp) -> {
          long now = System.nanoTime();
          ui.videoFrames++;
          if (timing.acceptDecoded(frame.getTimestampNs(), now)) {
            ui.videoReceived = now;
            sink.onFrame(frame);
          }
          cb.onDecodedFrame(frame, ms, qp);
        });
      }
      public VideoCodecStatus release() {
        return real.release();
      }
      public VideoCodecStatus decode(EncodedImage image, DecodeInfo info) {
        if (image.encodedWidth > 1920 || image.encodedHeight > 1080)
          return VideoCodecStatus.ERR_SIZE;
        return real.decode(image, info);
      }
      public String getImplementationName() {
        return "TLZ2/" + real.getImplementationName();
      }
    };
  }
}
