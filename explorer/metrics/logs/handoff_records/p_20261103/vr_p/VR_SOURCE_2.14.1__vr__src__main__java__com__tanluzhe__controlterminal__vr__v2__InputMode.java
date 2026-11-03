package com.tanluzhe.controlterminal.vr.v2;

/** Display/demo preview only. AIPC owns the final motion mode and physical mapping. */
public final class InputMode {
  public enum Mode { IDLE, VEHICLE_LEFT, VEHICLE_RIGHT, ARMS }
  public final float press, release, deadzone;
  public volatile Mode mode = Mode.IDLE;
  public volatile boolean releaseRequired = true;
  public volatile String reason = "请松开双侧键、摇杆回中";
  private boolean left, right;
  public InputMode(float up, float down, float dz) {
    if (!Float.isFinite(up) || !Float.isFinite(down) || !Float.isFinite(dz) || down < .5f || up > 1
        || up <= down || dz < 0 || dz > .3f)
      throw new IllegalArgumentException("输入阈值：0.5≤释放<按下≤1，死区0–0.3");
    press = up;
    release = down;
    deadzone = dz;
  }
  public void reset(String why) {
    mode = Mode.IDLE;
    left = right = false;
    releaseRequired = true;
    reason = why;
  }
  public Mode update(InputControls c, boolean focused, int tracking, boolean uiBlocked) {
    if (!focused || (tracking & 7) != 7 || (c.valid & 51) != 51 || uiBlocked) {
      reset(uiBlocked ? "页面操作中，运动输入未授权" : "焦点/追踪/输入无效，请释放后重新确认");
      return mode;
    }
    if (releaseRequired) {
      if (c.leftGrip < release && c.rightGrip < release && center(c.leftStick)
          && center(c.rightStick)) {
        releaseRequired = false;
        reason = "就绪：单侧全按车辆，双侧全按双臂";
      } else {
        reason = "请松开双侧键并将摇杆回中";
        return mode;
      }
    }
    left = left ? c.leftGrip >= release : c.leftGrip >= press;
    right = right ? c.rightGrip >= release : c.rightGrip >= press;
    Mode next = left && right ? Mode.ARMS
        : left                ? Mode.VEHICLE_LEFT
        : right               ? Mode.VEHICLE_RIGHT
                              : Mode.IDLE;
    if (mode == Mode.ARMS && next != Mode.ARMS) {
      reset("离开双臂模式，请双侧释放、摇杆回中");
      return mode;
    }
    mode = next;
    reason = mode == Mode.ARMS      ? "双臂输入；车辆意图无效"
        : mode == Mode.IDLE         ? "无运动意图"
        : mode == Mode.VEHICLE_LEFT ? "车辆输入：仅左摇杆"
                                    : "车辆输入：仅右摇杆";
    return mode;
  }
  private boolean center(float[] a) {
    return Math.abs(a[0]) <= deadzone && Math.abs(a[1]) <= deadzone;
  }
  public float axis(float value) {
    return Math.abs(value) <= deadzone
        ? 0
        : Math.copySign((Math.abs(value) - deadzone) / (1 - deadzone), value);
  }
}
