package com.tanluzhe.controlterminal.vr.v2;
import android.content.*;
import android.opengl.*;
import android.media.*;
import java.io.*;
import java.nio.*;
import org.json.*;

/** Optional actual-device live encode check. No XR session or robot connection. */
final class CaptureDeviceCheck {
  static void run(Context target)throws Exception{
    if(V2Activity.current()!=null)throw new IllegalStateException("请先退出VR场景，再运行独立编码验收");
    Context isolated=new ContextWrapper(target){
      @Override public SharedPreferences getSharedPreferences(String name,int mode){return super.getSharedPreferences("capture_smoke_"+name,mode);}
      @Override public File getExternalFilesDir(String name){File f=new File(getCacheDir(),"capture-smoke");f.mkdirs();return f;}
    };
    isolated.getSharedPreferences("capture",0).edit().clear().commit();
    EGLDisplay display=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);int[] versions=new int[2];if(!EGL14.eglInitialize(display,versions,0,versions,1))throw new IllegalStateException("EGL init");
    EGLConfig[] configurations=new EGLConfig[1];int[] count=new int[1];int[] attributes={EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RENDERABLE_TYPE,0x40,EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_ALPHA_SIZE,8,EGL14.EGL_NONE};
    if(!EGL14.eglChooseConfig(display,attributes,0,configurations,0,1,count,0)||count[0]<1)throw new IllegalStateException("EGL config");
    EGLContext context=EGL14.eglCreateContext(display,configurations[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,3,EGL14.EGL_NONE},0);
    EGLSurface parking=EGL14.eglCreatePbufferSurface(display,configurations[0],new int[]{EGL14.EGL_WIDTH,1,EGL14.EGL_HEIGHT,1,EGL14.EGL_NONE},0);
    if(!EGL14.eglMakeCurrent(display,parking,parking,context))throw new IllegalStateException("EGL current");
    ViewCapture capture=new ViewCapture(isolated);int[] textures=new int[16];GLES30.glGenTextures(textures.length,textures,0);
    try{
      capture.foreground(true);capture.attach(context);capture.command("/v1/view/config",new JSONObject().put("width",320).put("height",240).put("fps",10).put("bitrate",1000000));
      if(!capture.streaming())throw new IllegalStateException("默认直播未开启");LiveViewBus.Client client=capture.live.subscribe(()->{});
      capture.command("/v1/view/record/config",new JSONObject().put("width",320).put("height",240).put("fps",10).put("bitrate",1000000));
      capture.command("/v1/view/record/start",new JSONObject());
      boolean liveSeen=false;
      for(int frame=0;frame<textures.length;frame++){
        ByteBuffer rgba=ByteBuffer.allocateDirect(320*240*4);for(int pixel=0;pixel<320*240;pixel++){rgba.put((byte)(80+frame*4));rgba.put((byte)128);rgba.put((byte)192);rgba.put((byte)255);}rgba.flip();
        GLES30.glBindTexture(GLES30.GL_TEXTURE_2D,textures[frame]);GLES30.glTexImage2D(GLES30.GL_TEXTURE_2D,0,GLES30.GL_SRGB8_ALPHA8,320,240,0,GLES30.GL_RGBA,GLES30.GL_UNSIGNED_BYTE,rgba);GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D,GLES30.GL_TEXTURE_MIN_FILTER,GLES30.GL_LINEAR);GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D,GLES30.GL_TEXTURE_MAG_FILTER,GLES30.GL_LINEAR);
        long fence=GLES30.glFenceSync(GLES30.GL_SYNC_GPU_COMMANDS_COMPLETE,0);GLES30.glFlush();if(!capture.frame(textures[frame],frame%3,System.nanoTime(),fence,new float[]{0,0,1,1,70,50,320,240},capture.status().getLong("session_id"))){GLES30.glDeleteSync(fence);throw new IllegalStateException("frame rejected");}
        long recordFence=GLES30.glFenceSync(GLES30.GL_SYNC_GPU_COMMANDS_COMPLETE,0);GLES30.glFlush();
        if(!capture.frame(textures[frame],3+frame%3,System.nanoTime(),recordFence,new float[]{0,0,1,1,70,50,320,240},capture.recordStatus().getLong("session_id"))){GLES30.glDeleteSync(recordFence);throw new IllegalStateException("录制帧被拒绝");}
        // Consume network frames so the bounded subscriber is not intentionally disconnected.
        Thread.sleep(120);LiveViewBus.Frame sample;while((sample=client.frames.poll())!=null){if(sample.bytes.length<5||sample.bytes[0]!=0||sample.bytes[1]!=0||sample.bytes[2]!=0||sample.bytes[3]!=1)throw new IllegalStateException("直播不是Annex-B");liveSeen=true;}
      }
      Thread.sleep(250);
      if(!liveSeen)throw new IllegalStateException("并行直播没有输出");
      JSONObject status=capture.status();if(status.getLong("encoded_frames")<8)throw new IllegalStateException("硬编码输出不足8帧: "+status);
      if(!status.getBoolean("recording")||!status.getBoolean("local_recording_supported"))throw new IllegalStateException("双路录制未运行");
      capture.command("/v1/view/record/stop",new JSONObject());
      if(!capture.streaming())throw new IllegalStateException("停止录制不应中断预览");
      String name=capture.recordStatus().getString("last_file");
      try(RecordingStore.Opened file=capture.openRecording(name)){
        MediaExtractor extractor=new MediaExtractor();try{extractor.setDataSource(file.file.getFD());if(extractor.getTrackCount()!=1)throw new IllegalStateException("录像轨道数量");MediaFormat fmt=extractor.getTrackFormat(0);if(fmt.getInteger(MediaFormat.KEY_WIDTH)!=320||fmt.getInteger(MediaFormat.KEY_HEIGHT)!=240)throw new IllegalStateException("录像画幅");extractor.selectTrack(0);long previous=-1;int samples=0;while(extractor.getSampleTime()>=0){long pts=extractor.getSampleTime();if(pts<previous)throw new IllegalStateException("录像PTS倒退");previous=pts;samples++;extractor.advance();}if(samples<8)throw new IllegalStateException("录像帧数不足");}finally{extractor.release();}
      }
      capture.deleteRecording(name);
      capture.cancelStreamFromMenu();capture.command("/v1/view/config",new JSONObject());
      if(capture.streaming())throw new IllegalStateException("菜单取消后不应重新开启");
      capture.foreground(false);capture.foreground(true);capture.command("/v1/view/config",new JSONObject());
      if(capture.streaming())throw new IllegalStateException("恢复前台不应覆盖用户取消");
      capture.command("/v1/view/live/start",new JSONObject());
      if(!capture.streaming())throw new IllegalStateException("后台应可再次开启直播");
      capture.command("/v1/view/live/stop",new JSONObject());
    }finally{
      capture.close();GLES30.glDeleteTextures(textures.length,textures,0);EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);EGL14.eglDestroySurface(display,parking);EGL14.eglDestroyContext(display,context);EGL14.eglTerminate(display);
    }
  }
}
