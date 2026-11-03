package com.tanluzhe.controlterminal.vr;

import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.view.View;

/**
 * Cached sky/ground backdrop for the 2D settings/log windows, with actual Gaussian glass surfaces.
 */
final class GlassBackdrop extends Drawable {
  private final View root;
  private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
  private Bitmap sharp, blurred;
  private int width, height;
  GlassBackdrop(View root) {
    this.root = root;
  }
  private void prepare() {
    int w = Math.max(1, getBounds().width() / 4), h = Math.max(1, getBounds().height() / 4);
    if (sharp != null && width == w && height == h)
      return;
    if (sharp != null) {
      sharp.recycle();
      blurred.recycle();
    }
    width = w;
    height = h;
    sharp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
    Canvas c = new Canvas(sharp);
    paint.setShader(
        new LinearGradient(0, 0, 0, h, new int[] {0xff6696bd, 0xffc6ddeb, 0xff8babbc, 0xff496575},
            new float[] {0, .52f, .65f, 1}, Shader.TileMode.CLAMP));
    c.drawRect(0, 0, w, h, paint);
    paint.setShader(new RadialGradient(w * .23f, h * .18f, w * .65f,
        new int[] {0x60fff1d4, 0x00fff1d4}, null, Shader.TileMode.CLAMP));
    c.drawRect(0, 0, w, h, paint);
    paint.setShader(null);
    paint.setColor(0x449cbace);
    paint.setStrokeWidth(.6f);
    for (int k = -12; k <= 12; k++) c.drawLine(w * .5f, h * .56f, w * .5f + k * w * .2f, h, paint);
    for (int k = 1; k < 14; k++) {
      float y = h * .56f + (float) Math.pow(k / 14f, 2) * h * .44f;
      c.drawLine(0, y, w, y, paint);
    }
    int[] pixels = new int[w * h], temp = new int[w * h], result = new int[w * h];
    sharp.getPixels(pixels, 0, w, 0, 0, w, h);
    float[] weights = {.227027027f, .194594595f, .121621622f, .054054054f, .016216216f};
    for (int pass = 0; pass < 2; pass++) {
      int[] in = pass == 0 ? pixels : temp, out = pass == 0 ? temp : result;
      for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
          float r = 0, g = 0, b = 0;
          for (int offset = -4; offset <= 4; offset++) {
            int xx = Math.max(0, Math.min(w - 1, x + (pass == 0 ? offset * 2 : 0)));
            int yy = Math.max(0, Math.min(h - 1, y + (pass == 1 ? offset * 2 : 0)));
            int color = in[yy * w + xx];
            float weight = weights[Math.abs(offset)];
            r += ((color >> 16) & 255) * weight;
            g += ((color >> 8) & 255) * weight;
            b += (color & 255) * weight;
          }
          out[y * w + x] = 0xff000000 | Math.round(r) << 16 | Math.round(g) << 8 | Math.round(b);
        }
    }
    blurred = Bitmap.createBitmap(result, w, h, Bitmap.Config.ARGB_8888);
  }
  @Override
  public void draw(Canvas canvas) {
    prepare();
    paint.setColor(Color.WHITE);
    canvas.drawBitmap(sharp, null, getBounds(), paint);
  }
  Drawable glass(View owner, int tint) {
    return new Drawable() {
      private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
      private final Path clip = new Path();
      @Override
      public void draw(Canvas c) {
        Rect bounds = getBounds();
        RectF box = new RectF(bounds);
        int saved = c.save();
        clip.reset();
        clip.addRoundRect(box, 18, 18, Path.Direction.CW);
        c.clipPath(clip);
        if (blurred != null) {
          int[] a = new int[2], b = new int[2];
          owner.getLocationInWindow(a);
          root.getLocationInWindow(b);
          float sx = (float) width / Math.max(1, root.getWidth()),
                sy = (float) height / Math.max(1, root.getHeight());
          Rect source = new Rect(Math.round((a[0] - b[0]) * sx), Math.round((a[1] - b[1]) * sy),
              Math.round((a[0] - b[0] + bounds.width()) * sx),
              Math.round((a[1] - b[1] + bounds.height()) * sy));
          p.setColor(Color.WHITE);
          c.drawBitmap(blurred, source, box, p);
        }
        p.setColor(tint);
        c.drawRect(box, p);
        c.restoreToCount(saved);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(1.5f);
        p.setColor(0xbbeef8ff);
        c.drawRoundRect(box, 18, 18, p);
        p.setStyle(Paint.Style.FILL);
      }
      @Override
      public void setAlpha(int a) {}
      @Override
      public void setColorFilter(ColorFilter f) {}
      @Override
      public int getOpacity() {
        return PixelFormat.TRANSLUCENT;
      }
    };
  }
  @Override
  public void setAlpha(int a) {}
  @Override
  public void setColorFilter(ColorFilter f) {}
  @Override
  public int getOpacity() {
    return PixelFormat.OPAQUE;
  }
}
