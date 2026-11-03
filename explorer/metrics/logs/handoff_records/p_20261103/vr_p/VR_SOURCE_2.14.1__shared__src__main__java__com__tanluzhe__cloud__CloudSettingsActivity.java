package com.tanluzhe.cloud;
import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.net.*;
import java.io.*;
import java.util.*;
import org.json.*;
/** Independent point-cloud credentials; does not connect robot services. */
public final class CloudSettingsActivity extends Activity {
  private EditText wifi, relay, token, scene, floor, liveUrl;
  private Spinner profile;
  private TextView status;
  private final Handler main = new Handler(Looper.getMainLooper());
  @Override
  public void onCreate(Bundle b) {
    super.onCreate(b);
    ScrollView scroll = new ScrollView(this);
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(1);
    root.setPadding(28, 24, 28, 24);
    root.setBackgroundColor(0xffedf4f6);
    scroll.addView(root);
    setContentView(scroll);
    android.content.SharedPreferences p = CloudSettings.prefs(this);
    label(root, "VR 实时 / 场景图传设置", 25);
    label(root, "只读场景服务，不发送机器人控制。切换档位不会改变实际路由。", 15);
    wifi  = field(root, "实验室 Wi-Fi URL", p.getString("wifi_url", "http://192.168.137.2:18184"), false);
    relay = field(root, "中继 URL（尚需实际路由验收）", p.getString("relay_url", "http://192.168.137.2:18184"), false);
    liveUrl=field(root,"实时VCL1 URL",p.getString("live_url","http://192.168.137.2:8088"),false);
    token = new EditText(this);
    token.setText(p.getString("token", ""));
    label(root, p.getString("token", "").isEmpty() ? "服务凭据尚未自动配置" : "只读点云服务凭据已自动配置（不显示）", 15);
    profile = new Spinner(this);
    profile.setAdapter(
        new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[] {"wifi · 实验室直连", "relay · 无线中继"}));
    profile.setSelection(p.getString("profile", "wifi").equals("relay") ? 1 : 0);
    root.addView(profile);
    scene = field(root, "场景 ID", p.getString("scene", CloudStream.DENSE), false);
    button(root, "全量精细按需", () -> scene.setText(CloudStream.DENSE));
    button(root, "完整轻量场景", () -> scene.setText(CloudStream.LIGHT));
    floor = field(
        root, "场景地面 Y / 米（空白=未校准；采集原点不是地面）", p.contains("scene_floor:"+scene.getText().toString()) ? Float.toString(CloudSettings.floor(this,scene.getText().toString())) : "", false);
    scene.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){}public void afterTextChanged(android.text.Editable s){String key="scene_floor:"+s.toString();floor.setText(CloudSettings.prefs(CloudSettingsActivity.this).contains(key)?Float.toString(CloudSettings.floor(CloudSettingsActivity.this,s.toString())):"");}});
    status = label(root, "点云令牌与控制密钥按双方约定统一为 1；自动配置，无需输入", 15);
    button(root, "查询 catalog / 选择已有场景", this::catalog);
    button(root, "保存并返回", () -> {
      if (save())
        finish();
    });
  }
  private TextView label(LinearLayout root, String text, int size) {
    TextView v = new TextView(this);
    v.setText(text);
    v.setTextColor(0xff173743);
    v.setTextSize(size);
    v.setPadding(0, 10, 0, 10);
    root.addView(v);
    return v;
  }
  private EditText field(LinearLayout root, String title, String value, boolean secret) {
    label(root, title, 15);
    EditText e = new EditText(this);
    e.setSingleLine();
    e.setText(value);
    e.setTextColor(0xff173743);
    e.setInputType(InputType.TYPE_CLASS_TEXT | (secret ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_VARIATION_URI));
    root.addView(e, new LinearLayout.LayoutParams(-1, 58));
    return e;
  }
  private void button(LinearLayout root, String text, Runnable action) {
    Button b = new Button(this);
    b.setText(text);
    b.setTextColor(Color.WHITE);
    b.setAllCaps(false);
    GradientDrawable d = new GradientDrawable();
    d.setColor(0xff126979);
    d.setCornerRadius(22);
    b.setBackground(d);
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, 56);
    lp.topMargin                 = 12;
    root.addView(b, lp);
    b.setOnClickListener(v -> action.run());
  }
  private boolean save() {
    try {
      String mode = profile.getSelectedItemPosition() == 1 ? "relay" : "wifi";
      new CloudStream.Config((mode.equals("wifi") ? wifi : relay).getText().toString().trim(), token.getText().toString(),
          scene.getText().toString().trim(), mode);
      android.content.SharedPreferences.Editor e = CloudSettings.prefs(this)
                                                       .edit()
                                                       .putString("wifi_url", wifi.getText().toString().trim())
                                                       .putString("relay_url", relay.getText().toString().trim())
                                                       .putString("live_url",liveUrl.getText().toString().trim())
                                                       .putString("token", token.getText().toString())
                                                       .putString("scene", scene.getText().toString().trim())
                                                       .putString("profile", mode);
      String f = floor.getText().toString().trim();
      if (f.isEmpty())
        e.remove("floor_y").remove("scene_floor:"+scene.getText().toString().trim());
      else {
        float y = Float.parseFloat(f);
        if (!Float.isFinite(y) || Math.abs(y) > 10000)
          throw new IllegalArgumentException();
        e.putFloat("floor_y", y).putFloat("scene_floor:"+scene.getText().toString().trim(),y);
      }
      e.apply();
      return true;
    } catch (Exception e) {
      status.setText("配置无效：请检查 URL、独立令牌、场景ID和地面高度");
      return false;
    }
  }
  private void catalog() {
    if (!save())
      return;
    status.setText("读取 catalog…");
    CloudStream.Config c = CloudSettings.config(this);
    new Thread(() -> {
      HttpURLConnection h = null;
      try {
        h = (HttpURLConnection) new URL(c.base + "api/v2/catalog").openConnection(Proxy.NO_PROXY);
        h.setConnectTimeout(4000);
        h.setReadTimeout(8000);
        h.setInstanceFollowRedirects(false);
        h.setRequestProperty("Authorization", "Bearer " + c.token);
        h.setRequestProperty("X-Cloud-Profile", c.profile);
        if (h.getResponseCode() != 200)
          throw new IOException("HTTP " + h.getResponseCode());
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (InputStream in = h.getInputStream()) {
          byte[] b = new byte[8192];
          int n;
          while ((n = in.read(b)) != -1) {
            if (out.size() + n > 1024 * 1024)
              throw new IOException();
            out.write(b, 0, n);
          }
        }
        JSONObject response = new JSONObject(out.toString("UTF-8"));
        JSONArray items     = response.getJSONArray("scenes");
        String[] names = new String[items.length()], ids = new String[items.length()];
        for (int i = 0; i < items.length(); i++) {
          JSONObject j = items.getJSONObject(i);
          ids[i]       = j.optString("id", j.optString("scene_id", ""));
          names[i]     = j.optString("label",j.optString("name", ids[i])) + "\n" + ids[i];
        }
        main.post(() -> {
          if (isFinishing())
            return;
          status.setText("目录已读取 · relay_configured=" + response.optBoolean("relay_configured", false));
          new AlertDialog.Builder(this)
              .setTitle("选择场景")
              .setItems(names, (d, i) -> scene.setText(ids[i]))
              .setNegativeButton("返回", null)
              .show();
        });
      } catch (Exception e) {
        main.post(() -> status.setText("catalog 读取失败，请检查独立令牌与实际 URL"));
      } finally {
        if (h != null)
          h.disconnect();
      }
    }, "cloud-catalog").start();
  }
}
