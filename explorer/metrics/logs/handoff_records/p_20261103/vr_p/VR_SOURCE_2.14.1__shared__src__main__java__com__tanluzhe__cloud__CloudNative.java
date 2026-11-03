package com.tanluzhe.cloud;
import java.nio.*;
import java.util.*;
public final class CloudNative {
  public static native void policy(long generation, float nearRadius);
  public static native void grid(long generation, float meters, int[] cells);
  public static native void configure(long generation, String[] ids, float[] bounds);
  public static native boolean offer(long generation, String id, ByteBuffer raw, boolean coarse);
  public static native String[] resident(long generation);
  public static native String[] pending(long generation);
  public static native void retain(long generation, String[] ids);
  public static native long[] stats();
  public static native float[] head();
  public static native float[] anchor();
  public static native void recenter(float floorY);
  public static CloudStream.Sink sink() {
    return new CloudStream.Sink() {
      public void reset(long gen, List<CloudStream.Block> blocks) {
        String[] ids = new String[blocks.size()];
        float[] b    = new float[blocks.size() * 6];
        for (int i = 0; i < ids.length; i++) {
          ids[i] = blocks.get(i).id;
          System.arraycopy(blocks.get(i).bounds, 0, b, i * 6, 6);
        }
        configure(gen, ids, b);
        int[] cells   = new int[blocks.size() * 3];
        boolean valid = !blocks.isEmpty();
        for (int i = 0; i < blocks.size(); i++) {
          if (blocks.get(i).cell == null) {
            valid = false;
            break;
          }
          System.arraycopy(blocks.get(i).cell, 0, cells, i * 3, 3);
        }
        grid(gen, blocks.isEmpty() ? 1 : blocks.get(0).tileMeters, valid ? cells : new int[0]);
      }
      public boolean offer(long gen, CloudStream.Block b, ByteBuffer raw, boolean coarse) {
        return CloudNative.offer(gen, b.id, raw, coarse);
      }
      public Set<String> resident(long gen) {
        return new HashSet<>(Arrays.asList(CloudNative.resident(gen)));
      }
      public Set<String> pending(long gen) {
        return new HashSet<>(Arrays.asList(CloudNative.pending(gen)));
      }
      public void policy(long gen, float radius) {
        CloudNative.policy(gen, radius);
      }
      public void retain(long gen, Set<String> ids) {
        CloudNative.retain(gen, ids.toArray(new String[0]));
      }
    };
  }
}
