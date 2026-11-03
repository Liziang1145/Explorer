package com.tanluzhe.controlterminal.vr.v2;

import android.app.*;
import android.os.Bundle;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import okhttp3.*;

/** Device-local HTTP/WS compatibility test; no robot, TLS or headset tracking. */
public final class HttpConnectionInstrumentation extends Instrumentation {
  @Override
  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }
  @Override
  public void onStart() {
    Bundle result = new Bundle();
    int code = Activity.RESULT_CANCELED;
    OkHttpClient client = BaseLink.directClient();
    AtomicReference<Throwable> serverError = new AtomicReference<>();
    AtomicReference<Throwable> wsError = new AtomicReference<>();
    CountDownLatch echo = new CountDownLatch(1);
    try (ServerSocket server = new ServerSocket(0, 4, InetAddress.getByName("127.0.0.1"))) {
      server.setSoTimeout(10000);
      Thread worker = new Thread(() -> {
        try {
          for (int i = 0; i < 4; i++) {
            try (Socket socket = server.accept()) {
              socket.setSoTimeout(5000);
              serve(socket);
            }
          }
        } catch (Throwable e) {
          serverError.set(e);
        }
      }, "tlz-http-test");
      worker.start();
      String root = BaseLink.endpoint("http", "127.0.0.1", server.getLocalPort());
      check(client, root + "/v2/config", 200,
          "{\"transport\":\"http\"}".getBytes(StandardCharsets.UTF_8));
      check(client, root + "/v2/maps/1/tiles/0,0,0/1/0", 200, new byte[] {0, 1, 2, (byte) 255});
      check(client, root + "/redirect", 302, new byte[0]);
      WebSocket ws = client.newWebSocket(
          new Request.Builder()
              .url(BaseLink.endpoint("ws", "127.0.0.1", server.getLocalPort()) + "/v2/events")
              .build(),
          new WebSocketListener() {
            @Override
            public void onOpen(WebSocket socket, Response response) {
              socket.send("tlz-http-probe");
            }
            @Override
            public void onMessage(WebSocket socket, String text) {
              if (!text.equals("tlz-http-probe"))
                wsError.set(new AssertionError("WS echo mismatch"));
              echo.countDown();
            }
            @Override
            public void onFailure(WebSocket socket, Throwable t, Response response) {
              if (echo.getCount() != 0) {
                wsError.set(t);
                echo.countDown();
              }
            }
          });
      try {
        if (!echo.await(8, TimeUnit.SECONDS))
          throw new AssertionError("WS echo timeout");
        if (wsError.get() != null)
          throw new AssertionError(wsError.get());
        ws.cancel();
        worker.join(1500);
        if (worker.isAlive())
          throw new AssertionError("HTTP server did not finish");
        if (serverError.get() != null)
          throw new AssertionError(serverError.get());
      } finally {
        ws.cancel();
      }
      result.putString("stream",
          "PASS: cleartext HTTP JSON and binary map; WS handshake and echo; redirects disabled; no "
          + "certificate.");
      code = Activity.RESULT_OK;
    } catch (Throwable e) {
      result.putString("stream", "FAIL: " + e);
    } finally {
      client.dispatcher().executorService().shutdown();
      client.connectionPool().evictAll();
    }
    finish(code, result);
  }
  private static void check(OkHttpClient client, String url, int code, byte[] expected)
      throws Exception {
    try (Response response = client.newCall(new Request.Builder().url(url).build()).execute()) {
      if (response.code() != code || response.body() == null
          || !Arrays.equals(response.body().bytes(), expected))
        throw new AssertionError("HTTP response " + url);
    }
  }
  private static void serve(Socket socket) throws Exception {
    InputStream in = socket.getInputStream();
    OutputStream out = socket.getOutputStream();
    ByteArrayOutputStream headers = new ByteArrayOutputStream();
    int tail = 0;
    while (tail != 0x0d0a0d0a) {
      int b = in.read();
      if (b < 0 || headers.size() > 16384)
        throw new IOException("HTTP header");
      headers.write(b);
      tail = (tail << 8) | b;
    }
    String[] lines = headers.toString("US-ASCII").split("\r\n");
    String path = lines[0].split(" ")[1];
    if (path.equals("/v2/events")) {
      String key = null;
      for (String line : lines)
        if (line.toLowerCase(Locale.ROOT).startsWith("sec-websocket-key:"))
          key = line.substring(line.indexOf(':') + 1).trim();
      if (key == null)
        throw new AssertionError("Missing WS key");
      String accept = Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-1").digest(
          (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").getBytes(StandardCharsets.US_ASCII)));
      out.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: "
                 + "Upgrade\r\nSec-WebSocket-Accept: "
          + accept + "\r\n\r\n")
                    .getBytes(StandardCharsets.US_ASCII));
      out.flush();
      DataInputStream data = new DataInputStream(in);
      if (data.readUnsignedByte() != 0x81)
        throw new AssertionError("WS frame opcode");
      int size = data.readUnsignedByte();
      if ((size & 128) == 0 || (size & 127) > 125)
        throw new AssertionError("WS frame length/mask");
      byte[] mask = new byte[4], body = new byte[size & 127];
      data.readFully(mask);
      data.readFully(body);
      for (int i = 0; i < body.length; i++) body[i] ^= mask[i % 4];
      out.write(0x81);
      out.write(body.length);
      out.write(body);
      out.flush();
      // Keep the connection alive until the client cancels after receiving the echo.
      in.read();
      return;
    }
    byte[] body;
    String status = "200 OK", extra = "";
    if (path.equals("/v2/config"))
      body = "{\"transport\":\"http\"}".getBytes(StandardCharsets.UTF_8);
    else if (path.equals("/v2/maps/1/tiles/0,0,0/1/0"))
      body = new byte[] {0, 1, 2, (byte) 255};
    else if (path.equals("/redirect")) {
      status = "302 Found";
      extra = "Location: https://127.0.0.1:1/forbidden\r\n";
      body = new byte[0];
    } else
      throw new AssertionError("Unexpected path " + path);
    out.write(("HTTP/1.1 " + status + "\r\nConnection: close\r\n" + extra
        + "Content-Length: " + body.length + "\r\n\r\n")
                  .getBytes(StandardCharsets.US_ASCII));
    out.write(body);
    out.flush();
  }
}
