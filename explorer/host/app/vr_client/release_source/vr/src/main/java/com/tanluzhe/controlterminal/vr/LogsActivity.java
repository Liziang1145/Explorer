package com.tanluzhe.controlterminal.vr;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.os.*;
import android.widget.*;
public final class LogsActivity extends Activity {
  private TextView output;
  private boolean errors;
  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    AppLog.init(this, "ui");
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(1);
    root.setPadding(24, 16, 24, 16);
    root.setBackgroundColor(0xff102622);
    TextView title = new TextView(this);
    title.setText("详细日志 · 时间 / 级别 / 模块 / 事件 / 原因");
    title.setTextColor(Color.WHITE);
    title.setTextSize(22);
    root.addView(title);
    LinearLayout tools = new LinearLayout(this);
    root.addView(tools);
    button(tools, "刷新", () -> refresh());
    button(tools, "全部 / 警告错误", () -> {
      errors = !errors;
      refresh();
    });
    button(tools, "复制日志", () -> {
      ((android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE))
          .setPrimaryClip(ClipData.newPlainText("探路者日志", output.getText()));
      Toast.makeText(this, "日志已复制（不含连接密钥）", Toast.LENGTH_SHORT).show();
    });
    button(tools, "返回", this::finish);
    ScrollView scroll = new ScrollView(this);
    output = new TextView(this);
    output.setTextColor(0xffd5eee6);
    output.setTextSize(15);
    output.setTypeface(android.graphics.Typeface.MONOSPACE);
    output.setTextIsSelectable(true);
    scroll.addView(output);
    root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    TerminalStyle.page(root);
    setContentView(root);
    refresh();
  }
  private void button(LinearLayout row, String title, Runnable action) {
    Button b = new Button(this);
    b.setText(title);
    b.setOnClickListener(v -> action.run());
    row.addView(b, new LinearLayout.LayoutParams(0, -2, 1));
  }
  private void refresh() {
    new Thread(() -> {
      String text = AppLog.recent(this, 250, errors);
      runOnUiThread(() -> output.setText(text));
    }, "tlz-read-logs").start();
  }
}
