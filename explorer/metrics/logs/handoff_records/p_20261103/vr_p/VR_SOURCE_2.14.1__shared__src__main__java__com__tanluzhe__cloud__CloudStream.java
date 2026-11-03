package com.tanluzhe.cloud;

import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.zip.*;
import org.json.*;

/** Read-only v2 explicit-scene cloud service (v1 retained for fixtures). Shared by Quest and phone; no robot transport. */
public final class CloudStream implements AutoCloseable {
  public static final String DENSE = "20261030t153351z-60940b9a-static-dense-v2", LIGHT = "20261030t153351z-60940b9a-static-light-v2";
  public static final long CACHE_LIMIT = 256L * 1024 * 1024;
  public static final class Config {
    public final String base, token, scene, profile;
    public final boolean v2;
    public Config(String base, String token, String scene, String profile) {
      this(base, token, scene, profile, true);
    }
    public Config(String base, String token, String scene, String profile, boolean v2) {
      this.v2 = v2;
      try {
        URI u = new URI(base);
        if (!Arrays.asList("http", "https").contains(u.getScheme()) || u.getHost() == null || u.getRawUserInfo() != null || u.getQuery() != null
            || u.getFragment() != null)
          throw new Exception();
      } catch (Exception e) {
        throw new IllegalArgumentException("点云服务地址无效，请填写不带令牌的 HTTP URL");
      }
      if (token.trim().isEmpty())
        throw new IllegalArgumentException("请配置独立点云令牌，不能沿用默认机器人密钥");
      if (!scene.matches("[A-Za-z0-9_-]{1,160}") || !Arrays.asList("wifi", "relay").contains(profile))
        throw new IllegalArgumentException("场景或链路配置无效");
      this.base    = base.endsWith("/") ? base : base + "/";
      this.token   = token;
      this.scene   = scene;
      this.profile = profile;
    }
  }
  public static final class Block {
    public final String id, hash, gzipHash;
    public final int points, bytes, gzipBytes;
    public final float[] bounds;
    public final int priority;
    public int[] cell;
    public float tileMeters = 1;
    public Block(JSONObject j, String fallback) throws JSONException {
      id        = j.optString("id", fallback);
      hash      = j.getString("sha256").toLowerCase(Locale.ROOT);
      gzipHash  = j.getString("gzip_sha256").toLowerCase(Locale.ROOT);
      points    = j.getInt("points");
      bytes     = j.getInt("bytes");
      gzipBytes = j.getInt("gzip_bytes");
      priority  = j.optInt("priority", 0);
      if (j.has("cell")) {
        JSONArray c = j.getJSONArray("cell");
        if (c.length() != 3)
          throw new IllegalArgumentException("cell形状");
        cell = new int[] {c.getInt(0), c.getInt(1), c.getInt(2)};
      }
      bounds = bounds(j.getJSONArray("bounds"));
      if (!id.matches("[A-Za-z0-9_-]{1,128}") || !hash.matches("[0-9a-f]{64}") || !gzipHash.matches("[0-9a-f]{64}") || points <= 0
          || points > 1000000 || bytes != points * 15 || gzipBytes <= 0 || gzipBytes > 24 * 1024 * 1024)
        throw new IllegalArgumentException("点块描述/15字节记录长度无效");
    }
  }
  public interface Sink {
    void reset(long generation, List<Block> blocks);
    boolean offer(long generation, Block block, ByteBuffer raw, boolean coarse);
    Set<String> resident(long generation);
    default Set<String> pending(long generation) {
      return Collections.emptySet();
    }
    default void policy(long generation, float nearRadius) {}
    void retain(long generation, Set<String> ids);
  }
  public static final class CacheProgress {
    public final double fraction,rate;public final long bytes;public final boolean complete;
    public CacheProgress(double f,double r,long b,boolean c){fraction=f;rate=r;bytes=b;complete=c;}
  }
  public volatile CacheProgress cacheProgress=new CacheProgress(0,0,0,false);
  private long progressAt,progressSaveAt;
  /** The saved target is coarse + tiles intersecting the last selected near sphere, never the full map. */
  public static CacheProgress readCacheProgress(File root,String scene){
    try{File folder=new File(root,scene),file=new File(folder,"progress.json");if(file.length()>4*1024*1024)return new CacheProgress(0,0,0,false);JSONObject j=new JSONObject(new String(java.nio.file.Files.readAllBytes(file.toPath()),"UTF-8"));String revision=j.getString("revision");if(!revision.matches("[0-9a-f]{64}"))throw new IOException();File dir=new File(folder,revision);JSONArray a=j.getJSONArray("files");long total=0;double have=0;boolean complete=a.length()>0;
      for(int i=0;i<a.length();i++){JSONObject item=a.getJSONObject(i);String name=item.getString("name"),part=item.getString("part");long bytes=item.getLong("bytes"),gzip=item.getLong("gzip");if(!name.matches("(coarse-)?[0-9a-f]{64}\\.bin")||!part.matches("[0-9a-f]{16}-[0-9a-f]{64}\\.part")||bytes<=0||gzip<=0)throw new IOException();boolean ready=new File(dir,name).length()==bytes;total+=bytes;have+=ready?bytes:bytes*Math.min(.999,new File(dir,part).length()/(double)gzip);complete&=ready;}
      List<File> files=new ArrayList<>();files(folder,files);long bytes=0;for(File f:files)bytes+=f.length();return new CacheProgress(total>0?Math.min(1,have/total):0,0,bytes,complete);
    }catch(Exception ignored){return new CacheProgress(0,0,0,false);}
  }
  private void updateCacheProgress(long now){
    Block basis=coarse==null?progressCoarse:coarse;if(now-progressAt<300_000_000L||basis==null)return;progressAt=now;
    try{JSONArray target=new JSONArray();String prefix=sha(config.scene.getBytes("UTF-8")).substring(0,16);List<Block> all=new ArrayList<>();all.add(basis);for(Block b:blocks.values())if(intersects(b.bounds,position,nearRadius))all.add(b);long total=0;double have=0;boolean complete=true;
      for(Block b:all){String name=(b.id.equals("coarse")?"coarse-":"")+b.hash+".bin",part=prefix+"-"+b.gzipHash+".part";boolean ready=new File(directory,name).length()==b.bytes;total+=b.bytes;have+=ready?b.bytes:b.bytes*Math.min(.999,new File(directory,part).length()/(double)b.gzipBytes);complete&=ready;target.put(new JSONObject().put("name",name).put("part",part).put("bytes",b.bytes).put("gzip",b.gzipBytes));}
      if(now-rateAt>=1_000_000_000L){long n=networkBytes.get();bytesPerSecond=(n-rateBytes)*1e9/(now-rateAt);rateAt=now;rateBytes=n;}
      long bytes=cacheProgress.bytes;if(now-progressSaveAt>2_000_000_000L){progressSaveAt=now;List<File> list=new ArrayList<>();files(new File(root,config.scene),list);bytes=0;for(File f:list)bytes+=f.length();if(config.v2)atomicWrite(new File(new File(root,config.scene),"progress.json"),new JSONObject().put("revision",manifestRevision).put("radius_m",nearRadius).put("center",new JSONArray(position)).put("files",target).toString().getBytes("UTF-8"));}
      cacheProgress=new CacheProgress(total>0?Math.min(1,have/total):0,bytesPerSecond,bytes,complete);
    }catch(Exception ignored){}
  }
  public volatile String state = "未连接", error = "", sceneName = "", catalog = "[]";
  public volatile boolean connected, coarseReady, relayConfigured;
  public volatile int nearDone, nearDiskDone, nearTotal, residentBlocks;
  public volatile String manifestRevision = "";
  private volatile float nearRadius = 3, prefetchRadius = 4, retainRadius = 5;
  private volatile int concurrency = 4, requestBytes = 524288, targetRate = 4194304;
  private final Set<String> diskReady = ConcurrentHashMap.newKeySet();
  private long nextRangeNs, lastCacheScan;
  public volatile long downloadedBytes, cacheHits, diskBytes, coarseTotalBytes, coarseDownloadedBytes,lastDataNs;
  public volatile double bytesPerSecond;
  private final Config config;
  private final Sink sink;
  private final File root;
  private volatile File directory;
  private final ScheduledExecutorService control   = Executors.newSingleThreadScheduledExecutor();
  private final ExecutorService downloads          = Executors.newFixedThreadPool(4);
  private final Set<HttpURLConnection> connections = ConcurrentHashMap.newKeySet();
  private final Set<String> inFlight = ConcurrentHashMap.newKeySet(), offered = ConcurrentHashMap.newKeySet();
  private final Map<String, Block> blocks = new LinkedHashMap<>();
  private final Map<String, Long> retry   = new ConcurrentHashMap<>();
  private final Set<String> activeCache   = ConcurrentHashMap.newKeySet();
  private final AtomicLong networkBytes = new AtomicLong(), hits = new AtomicLong();
  private final AtomicLong sequence           = new AtomicLong();
  private static final AtomicLong GENERATIONS = new AtomicLong();
  public volatile long generation             = GENERATIONS.incrementAndGet();
  private volatile boolean closed, fatal, paused, refreshRequired;
  private volatile float[] position = {0, 1.6f, 0};
  private Block coarse,progressCoarse;
  private List<Block> wanted                   = new ArrayList<>();
  private String seedCoarseHash                = "";
  private final Map<String, String> seedHashes = new HashMap<>();
  private volatile Set<String> retain          = new HashSet<>();
  private long selectAt, rateAt = System.nanoTime(), rateBytes;
  private long reconnectAt;
  public CloudStream(Config config, File cache, Sink sink) {
    this.config    = config;
    this.root      = cache;
    this.directory = cache;
    this.sink      = sink;
    if (!cache.exists() && !cache.mkdirs())
      throw new IllegalStateException("无法创建点云缓存");
  }
  public Config config() {
    return config;
  }
  private String scenePath() {
    return "api/v2/scenes/" + config.scene + "/";
  }
  private void cacheDirectory(JSONObject manifest) throws Exception {
    if (!config.v2)
      return;
    String revision = manifest.getString("manifest_revision");
    if (!revision.matches("[0-9a-f]{64}") || !manifest.getString("cache_namespace").equals(config.scene + ":" + revision))
      throw new ProtocolException("缓存命名空间无效");
    File next = new File(new File(root, config.scene), revision);
    if (!next.isDirectory() && !next.mkdirs())
      throw new IOException("持久缓存目录创建失败");
    directory        = next;
    manifestRevision = revision;
  }
  private static void atomicWrite(File target, byte[] bytes) throws IOException {
    File temp = new File(target.getParentFile(), target.getName() + ".tmp");
    try (FileOutputStream out = new FileOutputStream(temp)) {
      out.write(bytes);
      out.getFD().sync();
    }
    java.nio.file.Files.move(temp.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
  }
  public boolean hasCoarseSeed() {
    return !seedCoarseHash.isEmpty();
  }
  public void restorePersistent() {
    if (!config.v2)
      return;
    try {
      File manifestFile = new File(new File(root, config.scene), "manifest.json");
      if (!manifestFile.isFile() || manifestFile.length() > 8 * 1024 * 1024)
        return;
      JSONObject m = new JSONObject(new String(java.nio.file.Files.readAllBytes(manifestFile.toPath()), "UTF-8"));
      cacheDirectory(m);
      String hash  = m.getJSONObject("coarse").getString("sha256");
      File rawFile = new File(directory, "coarse-" + hash + ".bin");
      if (!rawFile.isFile() || rawFile.length() != m.getJSONObject("coarse").getInt("bytes") || rawFile.length() > 15000000)
        return;
      byte[] bytes   = java.nio.file.Files.readAllBytes(rawFile.toPath());
      ByteBuffer raw = ByteBuffer.allocateDirect(bytes.length).order(ByteOrder.LITTLE_ENDIAN);
      raw.put(bytes).flip();
      preloadCoarse(m, raw);
    } catch (Exception ignored) {
    }
  }
  public void preloadCoarse(JSONObject manifest, ByteBuffer raw) throws Exception {
    if (closed)
      return;
    if (!config.scene.equals(manifest.getString("scene_id")))
      throw new ProtocolException("本地粗图 scene_id 不匹配");
    JSONObject descriptor = new JSONObject(manifest.getJSONObject("coarse").toString());
    descriptor.put("bounds", manifest.getJSONArray("bounds"));
    Block b = new Block(descriptor, "coarse");
    if (raw.remaining() != b.bytes)
      throw new ProtocolException("本地粗图长度错误");
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    digest.update(raw.duplicate());
    if (!hex(digest.digest()).equals(b.hash))
      throw new ProtocolException("本地粗图校验失败");
    cacheDirectory(manifest);progressCoarse=b;
    List<Block> list = new ArrayList<>();
    JSONArray tiles  = manifest.getJSONArray("tiles");
    for (int i = 0; i < tiles.length(); i++) {
      Block block      = new Block(tiles.getJSONObject(i), "");
      block.tileMeters = (float) manifest.optDouble("tile_m", 1);
      list.add(block);
      seedHashes.put(block.id, block.hash);
    }
    if (closed)
      return;
    sink.reset(generation, list);
    sink.policy(generation, nearRadius);
    if (!closed && sink.offer(generation, b, raw, true)) {
      coarseTotalBytes      = b.gzipBytes;
      coarseDownloadedBytes = b.gzipBytes;
      lastDataNs=System.nanoTime();
      seedCoarseHash        = b.hash;
      state                 = "本地真实粗图缓存；等待服务";
      sceneName             = config.scene;
      if (config.v2) {
        ByteBuffer copy = raw.duplicate();
        byte[] bytes    = new byte[copy.remaining()];
        copy.get(bytes);
        atomicWrite(new File(directory, "coarse-" + b.hash + ".bin"), bytes);
        atomicWrite(new File(new File(root, config.scene), "manifest.json"), manifest.toString().getBytes("UTF-8"));
      }
    }
  }
  public void start() {
    if (closed || control.isShutdown())
      return;
    control.scheduleWithFixedDelay(this::tick, 0, 100, TimeUnit.MILLISECONDS);
  }
  public void position(float[] p) {
    if (p.length != 3)
      throw new IllegalArgumentException();
    for (float f : p)
      if (!Float.isFinite(f) || Math.abs(f) > 1000000)
        throw new IllegalArgumentException("场景坐标无效");
    position = p.clone();
  }
  public void pause(boolean p) {
    paused = p;
  }
  private void tick() {
    if (closed || paused)
      return;
    if(fatal){offlineCached();return;}
    downloadedBytes = networkBytes.get();
    try {
      long now = System.nanoTime();
      if (now < reconnectAt) {
        offlineCached();
        return;
      }
      coarseReady = sink.resident(generation).contains("coarse");
      if (coarse == null || refreshRequired)
        initialize();
      updateCacheProgress(now);
      Set<String> ready  = sink.resident(generation);
      Set<String> queued = sink.pending(generation);
      offered.removeIf(id -> {
        if (ready.contains(id) || queued.contains(id) || inFlight.contains(id))
          return false;
        retry.put(id, now + 2_000_000_000L);
        return true;
      });
      residentBlocks = ready.size();
      coarseReady    = ready.contains("coarse");
      if (!coarseReady) {
        if (!inFlight.contains("coarse") && !offered.contains("coarse"))
          schedule(coarse, true);
        state = "下载/校验/上传粗图";
        return;
      }
      if (now >= selectAt) {
        selectAt = now + 500_000_000L;
        select(ready);
      }
      nearDone = nearDiskDone = nearTotal = 0;
      for (Block b : blocks.values())
        if (intersects(b.bounds, position, nearRadius)) {
          nearTotal++;
          if (diskReady.contains(b.id) && (!config.v2 || new File(directory, b.hash + ".bin").isFile()))
            nearDiskDone++;
          if (ready.contains(b.id))
            nearDone++;
        }
      state     = nearDone == nearTotal ? "近区全量已到齐" : "近区尚未全量加载";
      int limit = Math.min(4, concurrency);
      for (Block b : wanted) {
        if (inFlight.size() >= limit)
          break;
        if (!ready.contains(b.id) && !offered.contains(b.id) && !inFlight.contains(b.id) && System.nanoTime() >= retry.getOrDefault(b.id, 0L))
          schedule(b, false);
      }

    } catch (Exception e) {
      fault(e);
      offlineCached();
    }
  }
  private void initialize() throws Exception {
    state        = "鉴权 / 读取目录";
    JSONObject c = json(config.v2 ? "api/v2/catalog" : "api/v1/catalog", null);
    applyLimits(c.optJSONObject("profiles") == null ? null : c.getJSONObject("profiles").optJSONObject(config.profile));
    JSONArray scenes = c.getJSONArray("scenes");
    catalog          = scenes.toString();
    boolean found    = false;
    for (int i = 0; i < scenes.length(); i++) {
      JSONObject scene = scenes.getJSONObject(i);
      if (config.scene.equals(scene.optString("id", scene.optString("scene_id", "")))) {
        found     = true;
        sceneName = scene.optString("label", scene.optString("name", config.scene));
      }
    }
    if (!found)
      throw new ProtocolException("所选 scene_id 不在 catalog 中");
    relayConfigured     = c.optBoolean("relay_configured", false);
    state               = "读取 manifest";
    JSONObject manifest = json(config.v2 ? scenePath() + "manifest" : "api/v1/manifest", null);
    String id           = manifest.optString("scene_id", manifest.optString("id", ""));
    if (!config.scene.equals(id))
      throw new ProtocolException("manifest scene_id 不一致");
    if (manifest.has("scale") && Math.abs(manifest.getDouble("scale") - 1) > 1e-6)
      throw new ProtocolException("只接受 scale=1 的米制点云");
    String units = manifest.optString("units", "m");
    if (!Arrays.asList("m", "metre", "meter", "meters").contains(units))
      throw new ProtocolException("场景单位不是米");
    if (config.v2) {
      JSONObject format = manifest.getJSONObject("point_format");
      if (format.getInt("stride") != 15 || !"little".equals(format.getString("endianness")))
        throw new ProtocolException("静态点布局须15字节小端");
    }
    JSONArray a = manifest.has("tiles") ? manifest.getJSONArray("tiles") : manifest.getJSONArray("blocks");
    if (a.length() > 30000)
      throw new ProtocolException("manifest 块数超出上限");
    if (config.v2 && !manifestRevision.isEmpty() && !manifestRevision.equals(manifest.getString("manifest_revision"))) {
      generation     = GENERATIONS.incrementAndGet();
      seedCoarseHash = "";
      seedHashes.clear();
      offered.clear();
      wanted.clear();
      diskReady.clear();
      coarse = null;progressCoarse=null;
    }
    cacheDirectory(manifest);
    if (config.v2)
      atomicWrite(new File(new File(root, config.scene), "manifest.json"), manifest.toString().getBytes("UTF-8"));
    Map<String, String> previous = new HashMap<>();
    for (Block b : blocks.values()) previous.put(b.id, b.hash);
    String oldCoarse = coarse == null ? "" : coarse.hash;
    blocks.clear();
    for (int i = 0; i < a.length(); i++) {
      Block b      = new Block(a.getJSONObject(i), "");
      b.tileMeters = (float) manifest.optDouble("tile_m", 1);
      if (blocks.put(b.id, b) != null)
        throw new ProtocolException("重复块ID");
    }
    JSONObject coarseMeta = new JSONObject(manifest.getJSONObject("coarse").toString());
    if (!coarseMeta.has("bounds"))
      coarseMeta.put("bounds", manifest.getJSONArray("bounds"));
    coarse           = new Block(coarseMeta, "coarse");
    coarseTotalBytes = coarse.gzipBytes;
    if (!coarse.id.equals("coarse"))
      throw new ProtocolException("粗图 ID 必须为 coarse");
    if (!oldCoarse.isEmpty()) {
      boolean unchanged = oldCoarse.equals(coarse.hash) && previous.size() == blocks.size();
      for (Block b : blocks.values()) unchanged &= b.hash.equals(previous.get(b.id));
      if (!unchanged)
        throw new ProtocolException("SCENE_CHANGED");
      refreshRequired = false;
      connected       = true;
      error           = "";
      return;
    }
    boolean same = seedCoarseHash.equals(coarse.hash) && seedHashes.size() == blocks.size();
    for (Block b : blocks.values()) same &= b.hash.equals(seedHashes.get(b.id));
    if (!same)
      sink.reset(generation, new ArrayList<>(blocks.values()));
    else
      offered.add("coarse");
    sink.policy(generation, nearRadius);
    refreshRequired = false;
    connected       = true;
    error           = "";
  }
  private void select(Set<String> ready) throws Exception {
    JSONArray cached = new JSONArray();
    for (String id : ready)
      if (blocks.containsKey(id))
        cached.put(config.v2 ? new JSONObject().put("id", id).put("sha256", blocks.get(id).hash) : id);
    float[] p          = position;
    long seq           = sequence.incrementAndGet();
    JSONObject request = new JSONObject()
                             .put("scene_id", config.scene)
                             .put("request_seq", seq)
                             .put("profile", config.profile)
                             .put("position_scene_m", new JSONArray(p))
                             .put("cached", cached);
    if (config.v2) {
      request.remove("scene_id");
      request.remove("position_scene_m");
      request.put("manifest_revision", manifestRevision).put("center_scene_m", new JSONArray(p));
    }
    JSONObject response = json(config.v2 ? scenePath() + "select" : "api/v1/select", request);
    if (config.v2 && !manifestRevision.equals(response.getString("manifest_revision")))
      throw new ProtocolException("选块revision不一致");
    applyLimits(response.optJSONObject("limits"));
    sink.policy(generation, nearRadius);
    if (response.getLong("request_seq") != seq || !config.scene.equals(response.optString("scene_id", config.scene)))
      throw new ProtocolException("过期选块响应");
    Set<String> keep = ids(response.getJSONArray("retain"));
    keep.add("coarse");
    retain = keep;
    sink.retain(generation, keep);
    offered.removeIf(id -> !keep.contains(id));
    List<Block> next   = new ArrayList<>();
    JSONArray requests = response.getJSONArray("requests");
    for (int i = 0; i < requests.length(); i++) {
      Block b        = new Block(requests.getJSONObject(i), "");
      Block original = blocks.get(b.id);
      if (original == null || !original.hash.equals(b.hash) || !original.gzipHash.equals(b.gzipHash) || original.bytes != b.bytes
          || original.gzipBytes != b.gzipBytes)
        throw new ProtocolException("选块版本与 manifest 不一致");
      next.add(b);
    }
    next.sort(Comparator.comparingInt(b -> b.priority));
    wanted    = next;
    connected = true;
    error     = "";
  }
  private void schedule(Block block, boolean coarseBlock){schedule(block,coarseBlock,false);}
  private void schedule(Block block, boolean coarseBlock,boolean localOnly) {
    inFlight.add(block.id);
    long submittedGeneration = generation;
    File cacheDirectory      = directory;
    downloads.execute(() -> {
      try {
        ByteBuffer raw = fetch(block, cacheDirectory,localOnly);
        if (closed || submittedGeneration != generation)
          return;
        diskReady.add(block.id);
        while (!closed && submittedGeneration == generation && (coarseBlock || retain.contains(block.id))) {
          if (sink.offer(submittedGeneration, block, raw, coarseBlock)) {
            lastDataNs=System.nanoTime();offered.add(block.id);
            return;
          }
          Thread.sleep(50);
        }
      } catch (Exception e) {
        if (!closed) {
          retry.put(block.id, System.nanoTime() + 2_000_000_000L);
          fault(e);
        }
      } finally {
        inFlight.remove(block.id);
      }
    });
  }
  private ByteBuffer fetch(Block b, File cacheDirectory,boolean localOnly) throws Exception {
    String key = sha(config.scene.getBytes("UTF-8")).substring(0, 16) + "-" + b.gzipHash;
    activeCache.add(key);
    activeCache.add(b.hash);
    try {
      return fetchBlock(b, cacheDirectory,localOnly);
    } finally {
      activeCache.remove(key);
      activeCache.remove(b.hash);
      trimCacheMaybe();
    }
  }
  private ByteBuffer fetchBlock(Block b, File directory,boolean localOnly) throws Exception {
    File rawFile = new File(directory, (b.id.equals("coarse") ? "coarse-" : "") + b.hash + ".bin");
    if (config.v2 && rawFile.isFile() && rawFile.length() == b.bytes && sha(rawFile).equals(b.hash)) {
      byte[] bytes   = java.nio.file.Files.readAllBytes(rawFile.toPath());
      ByteBuffer raw = ByteBuffer.allocateDirect(bytes.length).order(ByteOrder.LITTLE_ENDIAN);
      raw.put(bytes).flip();
      cacheHits = hits.incrementAndGet();
      rawFile.setLastModified(System.currentTimeMillis());
      return raw;
    }

    if(localOnly)throw new IOException("Offline cache missing or invalid");
    String sceneKey = sha(config.scene.getBytes("UTF-8")).substring(0, 16);
    File full = new File(directory, sceneKey + "-" + b.gzipHash + ".gz"), part = new File(directory, sceneKey + "-" + b.gzipHash + ".part");
    boolean valid = full.isFile() && full.length() == b.gzipBytes && sha(full).equals(b.gzipHash);
    if (valid) {
      cacheHits = hits.incrementAndGet();
      full.setLastModified(System.currentTimeMillis());
    } else {
      if (full.exists() && !full.delete())
        throw new IOException("无法删除错误缓存");
      if (part.length() > b.gzipBytes && !part.delete())
        throw new IOException("无法重置半包");
      while (part.length() < b.gzipBytes) {
        if (closed || Thread.currentThread().isInterrupted())
          throw new InterruptedIOException();
        long at = part.length(), end = Math.min(b.gzipBytes - 1, at + requestBytes - 1);
        pace(end - at + 1);
        HttpURLConnection connection = open(config.v2 ? scenePath() + "blocks/" + b.id + ".gz" : "api/v1/blocks/" + b.id + ".gz");
        connection.setRequestProperty("Range", "bytes=" + at + "-" + end);
        connection.setRequestProperty("If-Match", "\"" + b.gzipHash + "\"");
        try {
          int code = connection.getResponseCode();
          if (code == 412 || code == 416) {
            part.delete();
            throw new Status(code, 0);
          }
          check(connection, 206);
          String expected = "bytes " + at + "-" + end + "/" + b.gzipBytes;
          if (!expected.equals(connection.getHeaderField("Content-Range")) || connection.getContentLengthLong() != end - at + 1
              || !("\"" + b.gzipHash + "\"").equals(connection.getHeaderField("ETag")) || connection.getHeaderField("Content-Encoding") != null)
            throw new ProtocolException("Range / ETag / gzip传输头无效");
          try (InputStream in = connection.getInputStream(); OutputStream out = new FileOutputStream(part, true)) {
            long left      = end - at + 1;
            byte[] scratch = new byte[32768];
            while (left > 0) {
              int n = in.read(scratch, 0, (int) Math.min(left, scratch.length));
              if (n < 0)
                throw new EOFException();
              out.write(scratch, 0, n);
              left -= n;
              networkBytes.addAndGet(n);
              if (b.id.equals("coarse"))
                coarseDownloadedBytes = part.length();
            }
            if (in.read() != -1)
              throw new ProtocolException("Range响应超长");
          }
        } finally {
          disconnect(connection);
        }
      }
      if (!sha(part).equals(b.gzipHash)) {
        part.delete();
        throw new ProtocolException("gzip SHA256 不匹配");
      }
      if (!part.renameTo(full))
        throw new IOException("缓存提交失败");
    }
    ByteBuffer raw       = ByteBuffer.allocateDirect(b.bytes).order(ByteOrder.LITTLE_ENDIAN);
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    try (InputStream in = new GZIPInputStream(new FileInputStream(full))) {
      byte[] scratch = new byte[32768];
      int n;
      while ((n = in.read(scratch)) != -1) {
        if (closed)
          throw new InterruptedIOException();
        if (n > raw.remaining())
          throw new ProtocolException("解压大小超过清单");
        digest.update(scratch, 0, n);
        raw.put(scratch, 0, n);
      }
    }
    if (raw.position() != b.bytes || !hex(digest.digest()).equals(b.hash)) {
      full.delete();
      throw new ProtocolException("原始点块大小 / SHA256 不匹配");
    }
    raw.flip();
    for (int i = 0; i < b.points; i++)
      for (int k = 0; k < 3; k++) {
        float x = raw.getFloat(i * 15 + k * 4);
        if (!Float.isFinite(x) || x < b.bounds[k] - .02f || x > b.bounds[k + 3] + .02f)
          throw new ProtocolException("点坐标与块范围无效");
      }
    if (config.v2) {
      byte[] bytes = new byte[b.bytes];
      raw.duplicate().get(bytes);
      atomicWrite(rawFile, bytes);
      full.delete();
    }
    trimCache();
    return raw;
  }
  private HttpURLConnection open(String path) throws Exception {
    if (closed)
      throw new InterruptedIOException();
    HttpURLConnection c = (HttpURLConnection) new URL(config.base + path).openConnection(Proxy.NO_PROXY);
    c.setInstanceFollowRedirects(false);
    c.setConnectTimeout(4000);
    c.setReadTimeout(10000);
    c.setRequestProperty("Accept-Encoding", "identity");
    c.setRequestProperty("Authorization", "Bearer " + config.token);
    if (!path.endsWith("catalog") && !path.endsWith("settings"))
      c.setRequestProperty("X-Cloud-Scene", config.scene);
    c.setRequestProperty("X-Cloud-Profile", config.profile);
    connections.add(c);
    return c;
  }
  private JSONObject json(String path, JSONObject body) throws Exception {
    HttpURLConnection c = open(path);
    try {
      if (body != null) {
        byte[] bytes = body.toString().getBytes("UTF-8");
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setFixedLengthStreamingMode(bytes.length);
        c.setRequestProperty("Content-Type", "application/json");
        try (OutputStream out = c.getOutputStream()) {
          out.write(bytes);
        }
      }
      check(c, 200);
      try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
        byte[] buf = new byte[32768];
        int n;
        while ((n = in.read(buf)) != -1) {
          if (out.size() + n > 8 * 1024 * 1024)
            throw new ProtocolException("JSON响应超限");
          out.write(buf, 0, n);
        }
        return new JSONObject(out.toString("UTF-8"));
      }
    } finally {
      disconnect(c);
    }
  }
  private void disconnect(HttpURLConnection c) {
    connections.remove(c);
    c.disconnect();
  }
  private static final class Status extends IOException {
    final int code;
    final long wait;
    Status(int c, long w) {
      super("点云服务 HTTP " + c);
      code = c;
      wait = w;
    }
  }
  private static void check(HttpURLConnection c, int expected) throws IOException {
    int status = c.getResponseCode();
    if (status == expected)
      return;
    long wait = 2000;
    try {
      wait = Math.max(1000, Math.min(30000, Long.parseLong(c.getHeaderField("Retry-After")) * 1000));
    } catch (Exception ignored) {
    }
    throw new Status(status, wait);
  }
  private synchronized void fault(Exception e) {
    if (closed)
      return;
    connected = false;
    error     = e instanceof Status ? e.getMessage() : "点云连接或数据校验失败（缓存场景保留）";
    if (e instanceof Status) {
      int code = ((Status) e).code;
      if (code == 409 || code == 404 || code == 412 || code == 416)
        refreshRequired = true;
      if (code == 400 || code == 401 || code == 403) {
        fatal = true;
        error += "，请检查独立令牌/配置后重新连接";
      }
      reconnectAt = System.nanoTime() + ((Status) e).wait * 1000000L;
    } else {
      reconnectAt = System.nanoTime() + 2_000_000_000L;
      if (e instanceof ProtocolException && ("SCENE_CHANGED".equals(e.getMessage()) || e.getMessage().contains("不在 catalog"))) {
        fatal = true;
        error = "场景版本/目录变化，请重新选择场景并连接";
      }
    }
    state = "可恢复断连 / 保留缓存";
  }
  private void applyLimits(JSONObject p) throws Exception {
    if (p == null)
      return;
    int c = p.getInt("concurrency"), r = p.getInt("request_bytes"), rate = p.getInt("target_bytes_per_sec");
    float n = (float) p.getDouble("near_m"), pre = (float) p.getDouble("prefetch_m"), ret = (float) p.getDouble("retain_m");
    if (c < 1 || c > 6 || r < 65536 || r > 1048576 || rate < 65536 || rate > 16777216 || !Float.isFinite(n) || !Float.isFinite(pre)
        || !Float.isFinite(ret) || n < .5 || n > pre || pre > ret || ret > 10)
      throw new ProtocolException("下载profile预算无效");
    concurrency    = c;
    requestBytes   = r;
    targetRate     = rate;
    nearRadius     = n;
    prefetchRadius = pre;
    retainRadius   = ret;
  }
  private void pace(long bytes) throws InterruptedException {
    long wait;
    synchronized (this) {
      long now = System.nanoTime(), at = Math.max(now, nextRangeNs);
      nextRangeNs = at + bytes * 1_000_000_000L / targetRate;
      wait        = at - now;
    }
    if (wait > 0)
      TimeUnit.NANOSECONDS.sleep(wait);
  }
  private void offlineCached() {
    if (!config.v2 || closed)
      return;
    try {
      updateCacheProgress(System.nanoTime());
      Set<String> ready = sink.resident(generation), queued = sink.pending(generation);
      long now = System.nanoTime();
      offered.removeIf(id -> {
        if (ready.contains(id) || queued.contains(id) || inFlight.contains(id))
          return false;
        retry.put(id, now + 2_000_000_000L);
        return true;
      });
      coarseReady    = ready.contains("coarse");
      residentBlocks = ready.size();
      if (blocks.isEmpty() && !seedHashes.isEmpty()) {
        File f         = new File(new File(root, config.scene), "manifest.json");
        JSONObject m   = new JSONObject(new String(java.nio.file.Files.readAllBytes(f.toPath()), "UTF-8"));
        JSONArray list = m.getJSONArray("tiles");
        for (int i = 0; i < list.length(); i++) {
          Block b      = new Block(list.getJSONObject(i), "");
          b.tileMeters = (float) m.optDouble("tile_m", 1);
          blocks.put(b.id, b);
        }
      }
      Set<String> keep = new HashSet<>();
      keep.add("coarse");
      nearDone = nearDiskDone = nearTotal = 0;
      for (Block b : blocks.values()) {
        if (intersects(b.bounds, position, retainRadius))
          keep.add(b.id);
        if (intersects(b.bounds, position, nearRadius)) {
          nearTotal++;
          if (ready.contains(b.id))
            nearDone++;
          if (diskReady.contains(b.id) && (!config.v2 || new File(directory, b.hash + ".bin").isFile()))
            nearDiskDone++;
        }
      }
      retain = keep;
      sink.retain(generation, keep);
      for (Block b : blocks.values())
        if (intersects(b.bounds, position, prefetchRadius) && inFlight.size() < Math.min(4, concurrency) && !ready.contains(b.id)
            && !offered.contains(b.id) && !inFlight.contains(b.id) && System.nanoTime() >= retry.getOrDefault(b.id, 0L)
            && new File(directory, b.hash + ".bin").isFile())
          schedule(b, false,true);
      diskBytes = cacheSize();
      state     = "离线缓存场景（AIPC不可达）";
    } catch (Exception ignored) {
    }
  }
  private static void files(File dir, List<File> list) {
    File[] children = dir.listFiles();
    if (children != null)
      for (File f : children) {
        if (f.isDirectory())
          files(f, list);
        else
          list.add(f);
      }
  }
  private long cacheSize() {
    long n          = 0;
    List<File> list = new ArrayList<>();
    files(root, list);
    for (File f : list) n += f.length();
    return n;
  }
  private synchronized void trimCacheMaybe() {
    if (System.nanoTime() - lastCacheScan > 500_000_000L)
      trimCache();
  }
  private synchronized void trimCache() {
    lastCacheScan   = System.nanoTime();
    List<File> list = new ArrayList<>();
    files(root, list);
    list.removeIf(f -> !f.getName().matches("([0-9a-f]{16}-)?[0-9a-f]{64}\\.(gz|part|bin)(\\.tmp)?"));
    list.sort(Comparator.comparingLong(File::lastModified));
    long fineBytes = 0;
    for (File f : list) fineBytes += f.length();
    for (File f : list) {
      if (fineBytes <= CACHE_LIMIT)
        break;
      String name  = f.getName();
      boolean busy = false;
      for (String key : activeCache)
        if (name.contains(key) || name.contains(key.substring(key.length() - 64)))
          busy = true;
      if (busy)
        continue;
      long bytes = f.length();
      if (f.delete())
        fineBytes -= bytes;
    }
    diskBytes = cacheSize();
  }
  /** Call only after stopping this session and explicit user confirmation. */
  public static void clearCache(File directory) {
    List<File> list = new ArrayList<>();
    files(directory, list);
    for (File f : list)
      if (f.getName().matches("(coarse-)?([0-9a-f]{16}-)?[0-9a-f]{64}\\.(gz|part|bin)(\\.tmp)?")
          || (f.getName().equals("manifest.json") || f.getName().equals("manifest.json.tmp") || f.getName().equals("progress.json") || f.getName().equals("progress.json.tmp")))
        f.delete();
  }
  public String summary() {
    return state + " · 磁盘 " + String.format(Locale.ROOT, "%.1f MiB", diskBytes / 1048576.0) + " · 近区缓存 " + nearDiskDone + "/" + nearTotal
        + " · 粗图" + (coarseReady ? "已就绪" : "未就绪") + " · 近区 " + nearDone + "/" + nearTotal + " · "
        + String.format(Locale.ROOT, "%.1f KiB/s", bytesPerSecond / 1024) + " · 命中 " + cacheHits;
  }
  public static float[] bounds(JSONArray a) throws JSONException {
    float[] b = new float[6];
    if (a.length() == 2) {
      for (int i = 0; i < 6; i++) b[i] = (float) a.getJSONArray(i / 3).getDouble(i % 3);
    } else if (a.length() == 6) {
      for (int i = 0; i < 6; i++) b[i] = (float) a.getDouble(i);
    } else
      throw new IllegalArgumentException("bounds形状");
    for (int i = 0; i < 6; i++)
      if (!Float.isFinite(b[i]) || Math.abs(b[i]) > 1000000 || i < 3 && b[i] > b[i + 3])
        throw new IllegalArgumentException("bounds无效");
    return b;
  }
  public static boolean intersects(float[] b, float[] p, float radius) {
    double d = 0;
    for (int k = 0; k < 3; k++) {
      double v = Math.max(b[k] - p[k], Math.max(0, p[k] - b[k + 3]));
      d += v * v;
    }
    return d <= radius * radius;
  }
  private static Set<String> ids(JSONArray a) throws JSONException {
    Set<String> s = new HashSet<>();
    for (int i = 0; i < a.length(); i++) s.add(a.getString(i));
    return s;
  }
  public static String sha(byte[] b) throws Exception {
    return hex(MessageDigest.getInstance("SHA-256").digest(b));
  }
  private static String sha(File file) throws Exception {
    MessageDigest d = MessageDigest.getInstance("SHA-256");
    try (InputStream in = new FileInputStream(file)) {
      byte[] b = new byte[65536];
      int n;
      while ((n = in.read(b)) != -1) d.update(b, 0, n);
    }
    return hex(d.digest());
  }
  private static String hex(byte[] b) {
    StringBuilder s = new StringBuilder();
    for (byte x : b) s.append(String.format(Locale.ROOT, "%02x", x & 255));
    return s.toString();
  }
  public void awaitStopped() {
    try {
      downloads.awaitTermination(12, TimeUnit.SECONDS);
      control.awaitTermination(12, TimeUnit.SECONDS);
      downloadedBytes = networkBytes.get();
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    }
  }
  @Override
  public void close() {
    closed = true;
    for (HttpURLConnection c : connections) c.disconnect();
    control.shutdownNow();
    downloads.shutdownNow();
  }
}
