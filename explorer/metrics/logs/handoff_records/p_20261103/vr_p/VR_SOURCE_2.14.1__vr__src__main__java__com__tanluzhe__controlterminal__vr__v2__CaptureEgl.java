package com.tanluzhe.controlterminal.vr.v2;

import android.opengl.*;
import android.view.Surface;
import java.nio.*;

/** Encoder-thread-only context sharing the XR textures. Never changes XR GL state. */
final class CaptureEgl implements AutoCloseable {
  private final EGLDisplay display;
  private final EGLContext context;
  private final EGLConfig config;
  private final EGLSurface parking;
  private EGLSurface window=EGL14.EGL_NO_SURFACE;
  private int program,vbo;
  CaptureEgl(EGLContext shared){
    display=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
    EGLConfig[] configs=new EGLConfig[1];int[] count=new int[1];int[] attributes={EGL14.EGL_SURFACE_TYPE,EGL14.EGL_WINDOW_BIT|EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RENDERABLE_TYPE,0x40,EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_ALPHA_SIZE,8,0x3142,1,EGL14.EGL_NONE};
    check(EGL14.eglChooseConfig(display,attributes,0,configs,0,1,count,0)&&count[0]>0,"recordable config");config=configs[0];
    context=EGL14.eglCreateContext(display,config,shared,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,3,EGL14.EGL_NONE},0);check(context!=EGL14.EGL_NO_CONTEXT,"shared context");
    parking=EGL14.eglCreatePbufferSurface(display,config,new int[]{EGL14.EGL_WIDTH,1,EGL14.EGL_HEIGHT,1,EGL14.EGL_NONE},0);check(parking!=EGL14.EGL_NO_SURFACE,"parking surface");park();
    int vs=shader(GLES20.GL_VERTEX_SHADER,"attribute vec2 position;attribute vec2 texCoord;varying vec2 uv;void main(){gl_Position=vec4(position,0.,1.);uv=texCoord;}");
    int fs=shader(GLES20.GL_FRAGMENT_SHADER,"precision mediump float;uniform sampler2D image;varying vec2 uv;void main(){vec3 c=texture2D(image,uv).rgb;vec3 rgb=mix(12.92*c,1.055*pow(c,vec3(1./2.4))-.055,step(vec3(.0031308),c));gl_FragColor=vec4(rgb,1.);}");
    program=GLES20.glCreateProgram();GLES20.glAttachShader(program,vs);GLES20.glAttachShader(program,fs);GLES20.glBindAttribLocation(program,0,"position");GLES20.glBindAttribLocation(program,1,"texCoord");GLES20.glLinkProgram(program);int[] ok=new int[1];GLES20.glGetProgramiv(program,GLES20.GL_LINK_STATUS,ok,0);check(ok[0]!=0,"encoder program");GLES20.glDeleteShader(vs);GLES20.glDeleteShader(fs);
    float[] quad={-1,-1,0,0,1,-1,1,0,1,1,1,1,-1,-1,0,0,1,1,1,1,-1,1,0,1};FloatBuffer data=ByteBuffer.allocateDirect(quad.length*4).order(ByteOrder.nativeOrder()).asFloatBuffer();data.put(quad).position(0);int[] buffer=new int[1];GLES20.glGenBuffers(1,buffer,0);vbo=buffer[0];GLES20.glBindBuffer(GLES20.GL_ARRAY_BUFFER,vbo);GLES20.glBufferData(GLES20.GL_ARRAY_BUFFER,quad.length*4,data,GLES20.GL_STATIC_DRAW);
  }
  void attach(Surface surface){detach();window=EGL14.eglCreateWindowSurface(display,config,surface,new int[]{EGL14.EGL_NONE},0);check(window!=EGL14.EGL_NO_SURFACE,"codec EGL surface");}
  void consume(long fence){park();GLES30.glWaitSync(fence,0,GLES30.GL_TIMEOUT_IGNORED);GLES30.glDeleteSync(fence);}
  void draw(int texture,int width,int height,long time){
    check(EGL14.eglMakeCurrent(display,window,window,context),"codec current");GLES20.glViewport(0,0,width,height);GLES20.glDisable(GLES20.GL_BLEND);GLES20.glDisable(GLES20.GL_DEPTH_TEST);GLES20.glDisable(GLES20.GL_SCISSOR_TEST);GLES20.glUseProgram(program);GLES20.glActiveTexture(GLES20.GL_TEXTURE0);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,texture);GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"image"),0);GLES20.glBindBuffer(GLES20.GL_ARRAY_BUFFER,vbo);GLES20.glEnableVertexAttribArray(0);GLES20.glEnableVertexAttribArray(1);GLES20.glVertexAttribPointer(0,2,GLES20.GL_FLOAT,false,16,0);GLES20.glVertexAttribPointer(1,2,GLES20.GL_FLOAT,false,16,8);GLES20.glDrawArrays(GLES20.GL_TRIANGLES,0,6);check(GLES20.glGetError()==GLES20.GL_NO_ERROR,"encoder draw");check(EGLExt.eglPresentationTimeANDROID(display,window,time),"presentation time");check(EGL14.eglSwapBuffers(display,window),"codec swap");
  }
  private void park(){check(EGL14.eglMakeCurrent(display,parking,parking,context),"encoder parking");}
  void detach(){park();if(window!=EGL14.EGL_NO_SURFACE){EGL14.eglDestroySurface(display,window);window=EGL14.EGL_NO_SURFACE;}}
  public void close(){detach();GLES20.glDeleteProgram(program);GLES20.glDeleteBuffers(1,new int[]{vbo},0);EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);EGL14.eglDestroySurface(display,parking);EGL14.eglDestroyContext(display,context);EGL14.eglReleaseThread();/* Display is owned by XR: never eglTerminate here. */}
  private static int shader(int type,String text){int id=GLES20.glCreateShader(type);GLES20.glShaderSource(id,text);GLES20.glCompileShader(id);int[] ok=new int[1];GLES20.glGetShaderiv(id,GLES20.GL_COMPILE_STATUS,ok,0);check(ok[0]!=0,"encoder shader");return id;}
  private static void check(boolean ok,String what){if(!ok)throw new IllegalStateException(what+" EGL=0x"+Integer.toHexString(EGL14.eglGetError()));}
}
