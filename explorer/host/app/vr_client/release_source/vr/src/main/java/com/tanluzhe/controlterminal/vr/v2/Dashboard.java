package com.tanluzhe.controlterminal.vr.v2;

import java.util.*;

/** Thread-safe display snapshot; unavailable measurements never become zero milliseconds. */
public final class Dashboard {
  public volatile Telemetry telemetry=Telemetry.unknown();
  public volatile String telemetryError="",targetAddress="",connectionError="";
  public volatile int wifiLevel=-1,battery=-1;
  public volatile double videoFps=Double.NaN,observationBytesPerSecond=Double.NaN;
  public volatile long observationTotalBytes;
  public final VideoInfo rgb=new VideoInfo(),depth=new VideoInfo();
  public final VideoInfo[] cameras={rgb,depth,new VideoInfo(),new VideoInfo(),new VideoInfo(),new VideoInfo()};
  public static final class VideoInfo {public volatile long received,frames;public volatile double fps=Double.NaN,latency=Double.NaN;public volatile String status="等待视频";public volatile int width,height;public volatile float pixelRatio=1;}
  public volatile String connection = "尚未连接", lease = "直连输入采集", robot = "状态未就绪",
                         warning = "";
  public volatile boolean simulation,inputConnected;
  public volatile double baseRtt = Double.NaN, carRtt = Double.NaN, endRtt = Double.NaN,
                         controlAge = Double.NaN, controlError = Double.NaN,
                         baseResidence = Double.NaN;
  public volatile long stateReceived, videoReceived, cloudReceived, videoFrames, packets, rejected;
  public volatile double videoAge = Double.NaN;
  public volatile long videoSubmitted;
  public volatile String videoSource="RGB 相机",videoStatus="等待媒体发现",videoDecoder="尚未创建";
  public volatile long videoPtsUs;
  public volatile int videoWidth,videoHeight;
  public volatile float videoPixelRatio=1;
  public volatile String videoAgeQuality = "未关联采集时间";
  public volatile double feedbackLoss = Double.NaN, videoLoss = Double.NaN;
  public volatile long observationSent, observationDropped;
  public volatile int observationBytes;
  public volatile double observationActualHz = Double.NaN;
  public volatile String observationChannel = "等待输入通道";
  public volatile String observationEncoding = "cbor";
  public String lines(long now,boolean ignored){
    return "探路者 / AIPC直连\n"+connection+"\n"+robot+"\n输入 "+observationActualHz+" Hz / "+observationEncoding+" / "+observationBytes+"B\n"
        +"VR↔AIPC RTT "+ms(baseRtt)+"\n"+videoSource+" / "+videoStatus+"\n解码器 "+videoDecoder+"\n"
        +"H.265 PTS仅用于播放，不作为采集到显示延时\n"+(warning.isEmpty()?"无需申请租约、同步或本地使能":warning);
  }
  private static double age(long n, long t) {
    return (n - t) / 1e6;
  }
  public static String ms(double x) {
    return Double.isFinite(x) ? String.format(Locale.ROOT, "%.1f ms", x) : "N/A";
  }
  private static String percent(double x) {
    return Double.isFinite(x) ? String.format(Locale.ROOT, "%.1f%%", x) : "N/A";
  }
}
