package com.tanluzhe.controlterminal.vr.v2;
import android.graphics.Bitmap;
public final class NativeVr {
  static {
    System.loadLibrary("openxr_loader");
    System.loadLibrary("tlz_v2");
  }
  public static native void start(V2Activity owner);
  public static native String coloredSceneLoad(java.nio.ByteBuffer positions,java.nio.ByteBuffer colors,java.nio.ByteBuffer indices,int vertices,int triangles);
  public static native void coloredSceneView(int mode,boolean points,boolean reset);
  public static native long[] coloredSceneStats();
  public static native void coloredSceneMove(float x,float z,float yaw);
  public static native void active(boolean value);
  public static native void stop();
  public static native void cloud(float[] xyzrgba);
  public static native void lines(float[] xyzrgba);
  public static native void hud(Bitmap bitmap);
  public static native void worldHud(Bitmap bitmap);
  public static native void scenePose(float x, float y, float z, float yaw, boolean follow);
  public static native void haptic();
  public static native void hapticHand(int hands);
  public static native void presentation(int videoMode, boolean mapVisible, boolean menuOpen);
  public static native void liveCloudReset(long generation);
  public static native boolean liveCloud(long generation,java.nio.ByteBuffer points,float[] matrix);
  public static native void liveCloudVisible(boolean visible);
  public static native long[] liveCloudStats();
  public static native void captureDemo();
  public static native void captureConfigure(int width,int height,int fps,float[] options,long generation);
  public static native void captureConfigureTrack(int channel,int width,int height,int fps,float[] options,long generation);
  public static native void captureReleased(int slot);
  public static native void videoMatrix(float[] matrix);
  public static native void videoReset();
  public static native void videoFrame(int stream,float[] matrix,int width,int height,float ratio);
  public static native void videoStreamReset(int stream);
  public static native int videoTexture(int stream);
  public static native void videoSelection(int stream);
  public static native void armCamera(float[] position,boolean valid,boolean enlarged);
  public static native void videoSource(boolean depth);
  public static native void armLines(float[] lines,float[] anchors);
  public static native void gripLabels(Bitmap bitmap);
  public static native void videoSize(int width, int height);
  public static native void videoAspect(float ratio);
}
