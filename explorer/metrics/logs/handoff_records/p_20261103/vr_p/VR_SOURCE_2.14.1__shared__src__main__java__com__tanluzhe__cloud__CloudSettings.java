package com.tanluzhe.cloud;
import android.content.*;
public final class CloudSettings {
  public static synchronized android.content.SharedPreferences prefs(Context c) {
    android.content.SharedPreferences p = c.getSharedPreferences("cloud_stream_v1", 0);
    if (p.getInt("credential_revision", 0) < 1)
      p.edit().putString("token", "1").putInt("credential_revision", 1).commit();
    if (p.getInt("scene_transport_revision", 0) < 2) {
      android.content.SharedPreferences.Editor e
          = p.edit().putInt("scene_transport_revision", 2).putString("live_url", "http://192.168.137.2:8088");
      for (String key : new String[] {"wifi_url", "relay_url"}) {
        String url = p.getString(key, "");
        if (url.isEmpty() || url.contains("192.168.31.135") || url.contains("192.168.6.206"))
          e.putString(key, "http://192.168.137.2:18184");
      }
      if (p.contains("floor_y"))
        e.putFloat("scene_floor:" + p.getString("scene", CloudStream.DENSE), p.getFloat("floor_y", 0));
      e.commit();
    }
    if (p.contains("provision_id"))
      return p;
    try (java.io.InputStream in = c.getAssets().open("cloud_provision.json")) {
      if (!p.contains("provision_id")) {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] b                          = new byte[4096];
        int n;
        while ((n = in.read(b)) != -1) {
          if (out.size() + n > 16384)
            throw new java.io.IOException();
          out.write(b, 0, n);
        }
        org.json.JSONObject j = new org.json.JSONObject(out.toString("UTF-8"));
        p.edit()
            .putString("token", j.getString("token"))
            .putString("wifi_url", j.getString("wifi_url"))
            .putString("relay_url", j.getString("relay_url"))
            .putString("scene", j.getString("scene"))
            .putString("profile", "wifi")
            .putString("provision_id", j.getString("id"))
            .commit();
      }
    } catch (Exception ignored) {
    }
    return p;
  }
  public static CloudStream.Config config(Context c) {
    android.content.SharedPreferences p = prefs(c);
    String mode                         = p.getString("profile", "wifi");
    return new CloudStream.Config(
        p.getString(mode + "_url", "http://192.168.137.2:18184"), p.getString("token", "1"), p.getString("scene", CloudStream.DENSE), mode);
  }
  public static float floor(Context c, String scene) {
    return prefs(c).getFloat("scene_floor:" + scene, 0);
  }
  public static java.io.File cache(Context c) {
    return new java.io.File(c.getFilesDir(), "scene-cloud");
  }
  public static void seedCoarse(Context c, CloudStream stream) {
    stream.restorePersistent();
    if (stream.hasCoarseSeed())
      return;
    try {
      java.io.ByteArrayOutputStream meta = new java.io.ByteArrayOutputStream();
      try (java.io.InputStream in = c.getAssets().open("cloud_manifest.json")) {
        byte[] b = new byte[8192];
        int n;
        while ((n = in.read(b)) != -1) meta.write(b, 0, n);
      }
      org.json.JSONObject manifest = new org.json.JSONObject(meta.toString("UTF-8"));
      if (!stream.config().scene.equals(manifest.getString("scene_id")))
        return;
      int bytes               = manifest.getJSONObject("coarse").getInt("bytes");
      java.nio.ByteBuffer raw = java.nio.ByteBuffer.allocateDirect(bytes).order(java.nio.ByteOrder.LITTLE_ENDIAN);
      try (java.io.InputStream in = c.getAssets().open("cloud_coarse.bin")) {
        byte[] b = new byte[32768];
        int n;
        while ((n = in.read(b)) != -1) {
          if (n > raw.remaining())
            throw new java.io.IOException();
          raw.put(b, 0, n);
        }
      }
      if (raw.position() != bytes)
        return;
      raw.flip();
      stream.preloadCoarse(manifest, raw);
    } catch (Exception ignored) {
    } // Offline bootstrap is optional; network errors remain visible separately.
  }
}
