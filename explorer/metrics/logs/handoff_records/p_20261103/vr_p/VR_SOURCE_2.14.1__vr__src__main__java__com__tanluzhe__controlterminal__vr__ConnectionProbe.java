package com.tanluzhe.controlterminal.vr;
import java.util.concurrent.TimeUnit;
import okhttp3.*;
/** Read-only health check. Never creates a session or robot lease. */
public final class ConnectionProbe {
  public static String run(String host, int port, String token) {
    if (!ConnectionSettings.validIpv4(host))
      return "地址无效：请填写四段IPv4，或连接AIPC热点";
    OkHttpClient client = new OkHttpClient.Builder()
                              .connectTimeout(3, TimeUnit.SECONDS)
                              .readTimeout(3, TimeUnit.SECONDS)
                              .callTimeout(5, TimeUnit.SECONDS)
                              .followRedirects(false)
                              .build();
    String target = "http://" + host + ":" + port + "/v2/health";
    AppLog.info("NET", "PROBE_BEGIN", target);
    try (Response r = client
                          .newCall(new Request.Builder()
                                       .url(target)
                                       .header("Authorization", "Bearer " + token)
                                       .build())
                          .execute()) {
      String result = r.isSuccessful()
          ? "HTTP " + r.code() + "：AIPCHTTP可达，媒体/输入通道需进入VR后协商"
          : r.code() == 401 || r.code() == 403
          ? "HTTP " + r.code() + "：AIPC拒绝密钥，请核对两端配置"
          : r.code() == 404 ? "HTTP 404：主机可达，但未提供 /v2/health"
                            : "HTTP " + r.code() + "：请查看AIPC服务日志";
      AppLog.event(r.isSuccessful() ? "INFO" : "WARN", "NET", "PROBE_RESULT", result);
      return result;
    } catch (Exception e) {
      String result = "检测失败：" + AppLog.reason(e) + "；检查IP、端口、Wi-Fi和服务";
      AppLog.error("NET", "PROBE_FAILED", result);
      return result;
    } finally {
      client.dispatcher().executorService().shutdown();
      client.connectionPool().evictAll();
    }
  }
}
