package com.tanluzhe.controlterminal.vr.v2;
import java.io.*;
import java.util.*;
import org.json.*;
/** Finalized files only. Leases prevent deletion during preview/download. */
public final class RecordingStore {
  private final File directory;
  private String active                      = "";
  private final Map<String, Integer> readers = new HashMap<>();
  public RecordingStore(File directory) {
    this.directory = directory;
    if (!directory.isDirectory() && !directory.mkdirs())
      throw new IllegalStateException("无法创建录像目录");
  }
  public synchronized File begin() {
    if (!active.isEmpty())
      throw new IllegalStateException("已有录像未结束");
    if (directory.getUsableSpace() < 256L * 1024 * 1024)
      throw new IllegalStateException("录制需要至少256MiB可用空间");
    active = "view-" + UUID.randomUUID() + ".mp4";
    return new File(directory, active + ".partial");
  }
  public synchronized File finish(File partial, JSONObject metadata) throws Exception {
    if (active.isEmpty() || !partial.getName().equals(active + ".partial"))
      throw new IllegalStateException("录像会话不一致");
    File target = new File(directory, active);
    if (!partial.renameTo(target))
      throw new IOException("录像封装后重命名失败");
    active = "";
    try (FileOutputStream out = new FileOutputStream(new File(directory, target.getName() + ".json"))) {
      out.write(metadata.toString().getBytes("UTF-8"));
    } catch (IOException ignored) {
    }
    return target;
  }
  public synchronized void abandon() {
    active = "";
  }
  public synchronized long freeBytes() {
    return directory.getUsableSpace();
  }
  private File validated(String name) throws IOException {
    if (!name.matches("view-[0-9a-fA-F-]{36}\\.mp4"))
      throw new FileNotFoundException("录像不存在");
    if (name.equals(active))
      throw new IllegalStateException("录像尚未结束");
    File f = new File(directory, name);
    if (!f.getCanonicalFile().getParentFile().equals(directory.getCanonicalFile()) || !f.isFile())
      throw new FileNotFoundException("录像不存在");
    return f;
  }
  public synchronized JSONArray list() throws Exception {
    JSONArray result = new JSONArray();
    File[] files     = directory.listFiles((d, n) -> n.matches("view-[0-9a-fA-F-]{36}\\.mp4"));
    if (files == null)
      return result;
    Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
    for (File f : files) {
      JSONObject j = new JSONObject();
      File meta    = new File(directory, f.getName() + ".json");
      if (meta.length() > 0 && meta.length() < 16384)
        try {
          j = new JSONObject(new String(java.nio.file.Files.readAllBytes(meta.toPath()), "UTF-8"));
        } catch (Exception ignored) {
        }
      j.put("name", f.getName())
          .put("bytes", f.length())
          .put("modified_ms", f.lastModified())
          .put("preview_url", "/v1/view/recordings/" + f.getName())
          .put("download_url", "/v1/view/recordings/" + f.getName() + "/download");
      result.put(j);
    }
    return result;
  }
  public synchronized void delete(String name) throws IOException {
    File f = validated(name);
    if (readers.getOrDefault(name, 0) > 0)
      throw new IllegalStateException("文件正在预览或下载，请关闭后重试");
    if (!f.delete())
      throw new IOException("删除失败");
    new File(directory, name + ".json").delete();
  }
  public synchronized Opened open(String name) throws IOException {
    File f                = validated(name);
    RandomAccessFile file = new RandomAccessFile(f, "r");
    readers.put(name, readers.getOrDefault(name, 0) + 1);
    return new Opened(name, file);
  }
  public final class Opened implements AutoCloseable {
    public final RandomAccessFile file;
    public final long length;
    private final String name;
    private boolean closed;
    private Opened(String name, RandomAccessFile file) throws IOException {
      this.name = name;
      this.file = file;
      length    = file.length();
    }
    public void close() throws IOException {
      synchronized (RecordingStore.this) {
        if (closed)
          return;
        closed = true;
        try {
          file.close();
        } finally {
          int n = readers.getOrDefault(name, 1) - 1;
          if (n == 0)
            readers.remove(name);
          else
            readers.put(name, n);
        }
      }
    }
  }
}
