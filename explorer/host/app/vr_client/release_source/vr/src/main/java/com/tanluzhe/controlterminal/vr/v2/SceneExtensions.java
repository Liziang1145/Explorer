package com.tanluzhe.controlterminal.vr.v2;
/** Local, scene-qualified extension contract. No navigation or vehicle command is sent. */
public final class SceneExtensions {
  public enum ViewMode { HEADSET, TOP_DOWN, ORBIT }
  public static final class Context {
    public final String sceneId, revision;
    public final float[] stageFromScene;
    public final boolean navigationAligned;
    public Context(String id, String revision, float[] anchor) {
      sceneId           = id;
      this.revision     = revision;
      stageFromScene    = anchor.clone();
      navigationAligned = false;
    }
  }
  public static final class Target {
    public final Context context;
    public final float x, y, z;
    public Target(Context context, float x, float y, float z) {
      if (!Float.isFinite(x) || !Float.isFinite(y) || !Float.isFinite(z))
        throw new IllegalArgumentException("目标坐标须有限");
      this.context = context;
      this.x       = x;
      this.y       = y;
      this.z       = z;
    }
  }
  public interface Handler {
    void onViewModeRequested(Context context, ViewMode mode);
    void onTargetSelected(Target target);
  }
  private volatile Handler handler;
  public void register(Handler value) {
    handler = value;
  }
  public boolean installed() {
    return handler != null;
  }
  public void requestView(Context context, ViewMode mode) {
    if (handler == null)
      throw new UnsupportedOperationException("俯视/环绕扩展尚未安装");
    handler.onViewModeRequested(context, mode);
  }
  public void selectTarget(Target target) {
    if (handler == null)
      throw new UnsupportedOperationException("导航选点扩展尚未安装");
    handler.onTargetSelected(target);
  }
}
