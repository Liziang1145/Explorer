package com.tanluzhe.controlterminal.vr;

import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.View;
import android.widget.*;

/** Shared app surfaces, including settings, logs and initialization errors. */
public final class TerminalStyle {
  public static final int INK = 0xff233b45, MUTED = 0xff637b84, ACCENT = 0xff087e8b;
  private static GradientDrawable surface(int color, float radius) {
    GradientDrawable d = new GradientDrawable();
    d.setColor(color);
    d.setCornerRadius(radius);
    d.setStroke(1, 0xffd7e4e8);
    return d;
  }
  public static void button(Button b) {
    button(b, null);
  }
  private static void button(Button b, GlassBackdrop scene) {
    b.setAllCaps(false);
    boolean primary = "primary".equals(b.getTag());
    b.setTextColor(primary ? Color.WHITE : INK);
    b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x33087e8b),
        scene == null ? surface(primary ? ACCENT : Color.WHITE, 18)
                      : scene.glass(b, primary ? 0xe0087e8b : 0x85eaf4ff),
        null));
    b.setBackgroundTintList(null);
    b.setElevation(0);
    b.setStateListAnimator(null);
    if (b.getLayoutParams() instanceof android.view.ViewGroup.MarginLayoutParams) {
      android.view.ViewGroup.MarginLayoutParams lp =
          (android.view.ViewGroup.MarginLayoutParams) b.getLayoutParams();
      lp.setMargins(4, 5, 4, 5);
      b.setLayoutParams(lp);
    }
    b.setPadding(16, 8, 16, 8);
  }
  public static void apply(View v) {
    apply(v, null);
  }
  private static void apply(View v, GlassBackdrop scene) {
    if (v instanceof Button)
      button((Button) v, scene);
    else if (v instanceof EditText) {
      EditText e = (EditText) v;
      e.setTextColor(INK);
      e.setHintTextColor(MUTED);
      e.setBackground(scene == null ? surface(0xfff8fbfc, 14) : scene.glass(e, 0x8aebf5ff));
      e.setPadding(14, 10, 14, 10);
    } else if (v instanceof TextView)
      ((TextView) v).setTextColor(INK);
    if (scene != null && v instanceof ScrollView) {
      v.setBackground(scene.glass(v, 0x80e6f0f9));
      v.setPadding(12, 12, 12, 12);
    }
    if (v instanceof android.view.ViewGroup) {
      android.view.ViewGroup g = (android.view.ViewGroup) v;
      for (int i = 0; i < g.getChildCount(); i++) apply(g.getChildAt(i), scene);
    }
  }
  public static void page(LinearLayout root) {
    GlassBackdrop scene = new GlassBackdrop(root);
    root.setBackground(scene);
    apply(root, scene);
  }
}
