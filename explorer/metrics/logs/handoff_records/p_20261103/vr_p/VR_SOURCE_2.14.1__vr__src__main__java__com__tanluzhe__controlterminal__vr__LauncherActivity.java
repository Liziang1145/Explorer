package com.tanluzhe.controlterminal.vr;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.text.method.DigitsKeyListener;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import com.tanluzhe.controlterminal.vr.v2.*;
/** Current controller only: connection, input observation, logs and local demo. */
public final class LauncherActivity extends Activity {
  private Switch automatic;
  private EditText mediaUrl,sceneUrl, host, port, telemetryPort, secret, hz, press, release, deadzone;
  private TextView status, address;
  private LinearLayout keypad;
  @Override
  public void onCreate(Bundle saved) {
    super.onCreate(saved);
    AppLog.init(this, "ui");
    AppLog.info("APP", "SETTINGS_OPEN", "连接设置 " + BuildConfig.VERSION_NAME);
    ConnectionSettings s = new ConnectionSettings(this);
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(1);
    root.setPadding(24, 16, 24, 16);
    root.setBackgroundColor(0xff102622);
    root.addView(text("探路者-控制终端", 27));
    root.addView(text("①选择AIPC  ②检测连接  ③进入VR；直接收发输入与视频，默认50Hz", 14));
    LinearLayout columns = new LinearLayout(this);
    root.addView(columns, new LinearLayout.LayoutParams(-1, 0, 1));
    LinearLayout left = new LinearLayout(this);
    left.setOrientation(1);
    ScrollView form = new ScrollView(this);
    form.addView(left);
    columns.addView(form, new LinearLayout.LayoutParams(0, -1, 1.2f));
    LinearLayout right = new LinearLayout(this);
    right.setOrientation(1);
    right.setPadding(24, 0, 0, 0);
    ScrollView actions = new ScrollView(this);
    actions.addView(right);
    columns.addView(actions, new LinearLayout.LayoutParams(0, -1, 1));
    automatic = new Switch(this);
    automatic.setText("使用Wi-Fi网关（通常请关闭）");
    automatic.setTextColor(Color.WHITE);
    automatic.setChecked(s.automatic);
    left.addView(automatic);
    address = text("", 15);
    left.addView(address);
    host = field(left, "AIPCIP", s.manualHost, false);
    host.setHint("192.168.137.2");
    host.setId(0x6001);
    host.setKeyListener(DigitsKeyListener.getInstance("0123456789."));
    host.setRawInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI
        | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
    host.setShowSoftInputOnFocus(false);
    keypad = new LinearLayout(this);
    keypad.setOrientation(1);
    left.addView(keypad);
    for (String[] row :
        new String[][] {{"1", "2", "3", "."}, {"4", "5", "6", "⌫"}, {"7", "8", "9", "0"}}) {
      LinearLayout line = new LinearLayout(this);
      keypad.addView(line);
      for (String value : row) {
        Button b = new Button(this);
        b.setText(value);
        b.setTextSize(22);
        b.setOnClickListener(v -> typeIp(value));
        line.addView(b, new LinearLayout.LayoutParams(0, 56, 1));
      }
    }
    Button keyboard = button(left, "系统键盘 / 支持输入小数点", () -> {
      host.setShowSoftInputOnFocus(true);
      host.requestFocus();
      ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
          .showSoftInput(host, InputMethodManager.SHOW_IMPLICIT);
    });
    automatic.setOnCheckedChangeListener((v, on) -> {
      host.setEnabled(!on);
      keypad.setVisibility(on ? View.GONE : View.VISIBLE);
      keyboard.setEnabled(!on);
      refreshAddress();
    });
    host.setEnabled(!s.automatic);
    keypad.setVisibility(s.automatic ? View.GONE : View.VISIBLE);
    keyboard.setEnabled(!s.automatic);
    port = field(left, "控制 / 输入端口", Integer.toString(s.port), true);
    mediaUrl=field(left,"六路媒体 HTTP 地址",getSharedPreferences("v2",0).getString("native_media_url","http://192.168.137.2:8096"),false);mediaUrl.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
    telemetryPort=field(left,"AIPC 遥测端口",Integer.toString(s.telemetryPort),true);
    sceneUrl=new EditText(this);sceneUrl.setText("");
    secret = field(left, "AIPC连接密钥（默认1）", s.token, false);
    secret.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    button(right, "检测AIPC（只读）", this::probe);
    button(right, "连接AIPC并进入VR", () -> launch(false));
    button(right, "本地输入演示", () -> launch(true));
    button(right,"点云分块服务设置",()->startActivity(new Intent(this,com.tanluzhe.cloud.CloudSettingsActivity.class)));
    button(right, "查看详细日志", () -> startActivity(new Intent(this, LogsActivity.class)));
    button(right, "保存设置", () -> save(true));
    status = text("就绪：连接后持续发送真实输入，执行策略由AIPC负责", 16);
    right.addView(status);
    button(right, "展开 / 收起输入参数", () -> {
      View advanced = right.findViewWithTag("advanced");
      advanced.setVisibility(advanced.getVisibility() == View.GONE ? View.VISIBLE : View.GONE);
    });
    LinearLayout advanced = new LinearLayout(this);
    advanced.setTag("advanced");
    advanced.setOrientation(1);
    advanced.setVisibility(View.GONE);
    right.addView(advanced);
    hz = field(advanced, "观察输入频率Hz（10–90）", Integer.toString(s.observationHz), true);
    press = field(advanced, "侧键全按阈值", Float.toString(s.press), false);
    release = field(advanced, "侧键释放阈值", Float.toString(s.release), false);
    deadzone = field(advanced, "摇杆预览死区", Float.toString(s.deadzone), false);
    advanced.addView(
        text("侧键为侧握；上键为食指扳机。原始值不做死区映射，车辆物理映射与模式由AIPC配置。", 14));
    TerminalStyle.page(root);
    setContentView(root);
    refreshAddress();
  }
  private TextView text(String value, int size) {
    TextView t = new TextView(this);
    t.setText(value);
    t.setTextSize(size);
    t.setTextColor(0xffdef2e8);
    t.setPadding(0, 5, 0, 5);
    return t;
  }
  private EditText field(LinearLayout root, String label, String value, boolean numeric) {
    root.addView(text(label, 15));
    EditText e = new EditText(this);
    e.setSingleLine(true);
    e.setTextSize(20);
    e.setTextColor(Color.WHITE);
    e.setHintTextColor(0xff849f94);
    e.setInputType(numeric ? InputType.TYPE_CLASS_NUMBER
                           : InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
    e.setText(value);
    root.addView(e);
    return e;
  }
  private Button button(LinearLayout parent, String title, Runnable run) {
    Button b = new Button(this);
    b.setText(title);
    if(title.equals("连接AIPC并进入VR"))b.setTag("primary");
    b.setTextSize(18);
    b.setMinHeight(60);
    b.setOnClickListener(v -> run.run());
    parent.addView(b);
    return b;
  }
  private void typeIp(String value) {
    host.requestFocus();
    int a = Math.max(0, host.getSelectionStart()), b = Math.max(a, host.getSelectionEnd());
    if (value.equals("⌫")) {
      if (a == b && a > 0)
        a--;
      host.getText().replace(a, b, "");
    } else
      host.getText().replace(a, b, value);
  }
  private void refreshAddress() {
    address.setText("Wi-Fi网关：" + ConnectionSettings.wifiGateway(this));
  }
  private boolean save(boolean report) {
    try {
      String ip = host.getText().toString().trim(), key = secret.getText().toString().trim();
      int tp=Integer.parseInt(telemetryPort.getText().toString());
      if(tp<1||tp>65535)throw new IllegalArgumentException("遥测端口范围1–65535");
      int p = Integer.parseInt(port.getText().toString()),
          rate = Integer.parseInt(hz.getText().toString());
      if (!automatic.isChecked() && !ConnectionSettings.validIpv4(ip))
        throw new IllegalArgumentException("IP格式错误，例如192.168.137.2，可用下方小数点键输入");
      if (p < 1 || p > 65535)
        throw new IllegalArgumentException("端口范围1–65535");
      CameraLayout.origin(mediaUrl.getText().toString().trim());
      new ObservationRate(rate);
      float up = Float.parseFloat(press.getText().toString()),
            down = Float.parseFloat(release.getText().toString()),
            dz = Float.parseFloat(deadzone.getText().toString());
      new InputMode(up, down, dz);
      if (key.isEmpty()) {
        key = "1";
        secret.setText(key);
      }
      getSharedPreferences("v2", 0)
          .edit()
          .putBoolean("automatic", automatic.isChecked())
          .putString("native_media_url",mediaUrl.getText().toString().trim())
          .putString("host", ip)
          .putInt("port", p).putInt("telemetry_port",tp)
          .putString("colored_scene_url",sceneUrl.getText().toString().trim())
          .putString("token", key)
          .putInt("observation_hz", rate)
          .putFloat("grip_press", up)
          .putFloat("grip_release", down)
          .putFloat("stick_deadzone", dz)
          .commit();
      if (report)
        status.setText("设置已保存");
      AppLog.info("UI", "SETTINGS_SAVED",
          "自动地址=" + automatic.isChecked() + " 端口=" + p + " 观察Hz=" + rate);
      return true;
    } catch (Exception e) {
      status.setText("设置错误：" + e.getMessage());
      AppLog.warn("UI", "SETTINGS_INVALID", e.getMessage());
      return false;
    }
  }
  private void probe() {
    if (!save(false))
      return;
    ConnectionSettings s = new ConnectionSettings(this);
    status.setText("正在检测HTTP服务，不会申请控制权…");
    new Thread(() -> {
      String result = ConnectionProbe.run(s.host(this), s.port, s.token);
      runOnUiThread(() -> status.setText(result));
    }, "tlz-probe").start();
  }
  private void launch(boolean demo) {
    if (!save(false))
      return;
    ConnectionSettings s = new ConnectionSettings(this);
    String ip = s.host(this);
    if (!demo && !ConnectionSettings.validIpv4(ip)) {
      status.setText("没有有效AIPCIP，请连接热点或手动输入");
      return;
    }
    AppLog.info("UI", demo ? "DEMO_START" : "CONNECT_START",
        demo ? "本地演示不联网" : "AIPC=" + ip + ":" + s.port);
    startActivity(new Intent(this, V2Activity.class).putExtra("demo", demo).putExtra("host", ip));
  }
  @Override
  protected void onResume() {
    super.onResume();
    if (address != null)
      refreshAddress();
  }
}
