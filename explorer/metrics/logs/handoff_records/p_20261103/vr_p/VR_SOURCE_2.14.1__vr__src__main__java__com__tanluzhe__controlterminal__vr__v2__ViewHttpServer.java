package com.tanluzhe.controlterminal.vr.v2;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import com.tanluzhe.controlterminal.vr.AppLog;

/** HTTP/1.1, close per request, authenticated JSON controls and chunked AVC. No robot API. */
final class ViewHttpServer implements AutoCloseable {
  private final ViewCapture capture;private final byte[] credential;private final int port;
  private volatile ServerSocket listener;private volatile boolean closed;
  private final ThreadPoolExecutor workers=new ThreadPoolExecutor(6,6,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(12));
  private final ScheduledExecutorService watchdog=Executors.newSingleThreadScheduledExecutor();
  private final Set<Socket> sockets=ConcurrentHashMap.newKeySet();
  private final Semaphore fileSlots=new Semaphore(2);
  private final Map<Socket,Long> writing=new ConcurrentHashMap<>();
  ViewHttpServer(ViewCapture capture,String secret,int port){this.capture=capture;credential=("Bearer "+secret).getBytes(StandardCharsets.UTF_8);this.port=port;}
  void start()throws IOException{
    ServerSocket bound=new ServerSocket();bound.setReuseAddress(true);try{bound.bind(new InetSocketAddress(port),8);}catch(IOException e){bound.close();workers.shutdownNow();watchdog.shutdownNow();throw e;}listener=bound;
    watchdog.scheduleWithFixedDelay(()->{long now=System.nanoTime();for(Map.Entry<Socket,Long> entry:writing.entrySet())if(now-entry.getValue()>3_000_000_000L)quietClose(entry.getKey());},1,1,TimeUnit.SECONDS);
    new Thread(()->{while(!closed)try{Socket socket=bound.accept();socket.setSoTimeout(5000);socket.setTcpNoDelay(true);socket.setSendBufferSize(64*1024);sockets.add(socket);try{workers.execute(()->serve(socket));}catch(RejectedExecutionException e){sockets.remove(socket);quietClose(socket);}}catch(IOException e){if(!closed)AppLog.warn("CAPTURE","HTTP_ACCEPT",AppLog.reason(e));}},"tlz-view-http").start();
    AppLog.info("CAPTURE","HTTP_START","port="+port+" token required; independent 1080P adaptive preview / backend-only recording");
  }
  boolean running(){return listener!=null&&!listener.isClosed()&&!closed;}
  private void serve(Socket socket){
    boolean responseStarted=false;
    try{
      InputStream in=new BufferedInputStream(socket.getInputStream());String first=line(in,2048);String[] request=first.split(" ");if(request.length!=3||!request[2].equals("HTTP/1.1"))throw new IllegalArgumentException("仅支持HTTP/1.1");String method=request[0],path=request[1];
      Map<String,String> headers=new HashMap<>();int total=first.length();for(int n=0;;n++){String header=line(in,2048);if(header.isEmpty())break;total+=header.length();if(n>=32||total>8192)throw new IllegalArgumentException("请求头过长");int colon=header.indexOf(':');if(colon<1)throw new IllegalArgumentException("请求头无效");String key=header.substring(0,colon).trim().toLowerCase(Locale.ROOT);if(headers.put(key,header.substring(colon+1).trim())!=null)throw new IllegalArgumentException("重复请求头");}
      if(!MessageDigest.isEqual(credential,headers.getOrDefault("authorization","").getBytes(StandardCharsets.UTF_8))){json(socket,401,new JSONObject().put("error","需要Authorization: Bearer <连接密钥>"));return;}
      if(headers.containsKey("transfer-encoding"))throw new IllegalArgumentException("控制请求不接受chunked body");
      int length=Integer.parseInt(headers.getOrDefault("content-length","0"));if(length<0||length>8192)throw new IllegalArgumentException("请求体最大8192字节");
      byte[] body=new byte[length];for(int at=0;at<length;){int n=in.read(body,at,length-at);if(n<0)throw new EOFException();at+=n;}
      if(path.startsWith("/v1/view/recordings/")&&(method.equals("GET")||method.equals("HEAD")||method.equals("DELETE"))){
        if(length!=0)throw new IllegalArgumentException("文件接口不接受请求体");String name=path.substring("/v1/view/recordings/".length());boolean download=name.endsWith("/download");if(download)name=name.substring(0,name.length()-9);
        if(method.equals("DELETE")){if(download)throw new IllegalArgumentException("删除路径不带download");capture.deleteRecording(name);json(socket,200,new JSONObject().put("deleted",name));return;}
        if(!fileSlots.tryAcquire()){head(socket,429,"video/mp4",0,"Retry-After: 1\r\n");return;}
        try(RecordingStore.Opened file=capture.openRecording(name)){
          String etag="\""+name+"-"+file.length+"\"";
          String rangeHeader=headers.get("range");if(headers.containsKey("if-range")&&!etag.equals(headers.get("if-range")))rangeHeader=null;
          FileByteRange range;try{range=FileByteRange.parse(rangeHeader,file.length);}catch(IllegalArgumentException invalid){head(socket,416,"video/mp4",0,"Content-Range: bytes */"+file.length+"\r\n");return;}
          responseStarted=true;String extra="Accept-Ranges: bytes\r\nETag: "+etag+"\r\nContent-Disposition: "+(download?"attachment":"inline")+"; filename=\""+name+"\"\r\n";
          if(range.partial)extra+="Content-Range: bytes "+range.start+"-"+range.end+"/"+file.length+"\r\n";
          head(socket,range.partial?206:200,"video/mp4",range.length(),extra);
          if(!method.equals("HEAD")){file.file.seek(range.start);long remaining=range.length();byte[] buffer=new byte[32768];while(remaining>0){int n=file.file.read(buffer,0,(int)Math.min(remaining,buffer.length));if(n<0)throw new EOFException();write(socket,buffer,0,n);remaining-=n;}}
        }finally{fileSlots.release();}return;
      }
      if(method.equals("GET")){
        if(length!=0)throw new IllegalArgumentException("GET不能带请求体");
        if(path.equals("/v1/view/status")||path.equals("/v1/view/config")){json(socket,200,capture.status());return;}
        if(path.equals("/v1/view/capabilities")){json(socket,200,capture.capabilities());return;}
        if(path.equals("/v1/view/record/status")||path.equals("/v1/view/record/config")){json(socket,200,capture.recordStatus());return;}
        if(path.equals("/v1/view/recordings")){json(socket,200,new JSONObject().put("files",capture.recordings()));return;}
        if(path.equals("/v1/view/live.h264")||path.equals("/v1/view/live.tlzv")){
          if(!capture.streaming())throw new IllegalStateException("先POST /v1/view/live/start");
          LiveViewBus.Client client=capture.live.subscribe(()->quietClose(socket));capture.requestKeyAsync();responseStarted=true;
          try{
            head(socket,200,path.endsWith(".h264")?"video/h264":"application/x-tlz-view",-1,"X-Preview-Client-Id: "+client.id+"\r\n");
            while(!closed&&!client.closed&&capture.streaming()){
              LiveViewBus.Frame frame=client.frames.poll(1,TimeUnit.SECONDS);if(frame==null)continue;
              long sendAt=System.nanoTime();if(client.frames.size()>=4)capture.networkCongested();
              int size=frame.bytes.length+(path.endsWith(".tlzv")?32:0);write(socket,(Integer.toHexString(size)+"\r\n").getBytes(StandardCharsets.US_ASCII));if(path.endsWith(".tlzv"))write(socket,frame.header());write(socket,frame.bytes);write(socket,new byte[]{13,10});if(System.nanoTime()-sendAt>100_000_000L)capture.networkCongested();
            }
            if(!socket.isClosed())write(socket,new byte[]{48,13,10,13,10});
          }finally{capture.live.remove(client);}return;
        }
        json(socket,404,new JSONObject().put("error","接口不存在"));return;
      }
      if(method.equals("PUT")&&Arrays.asList("/v1/view/config","/v1/view/record/config").contains(path)||method.equals("POST")&&Arrays.asList("/v1/view/live/start","/v1/view/live/stop","/v1/view/keyframe","/v1/view/record/start","/v1/view/record/stop","/v1/view/preview/feedback").contains(path)){
        JSONObject options=length==0?new JSONObject():new JSONObject(new String(body,StandardCharsets.UTF_8));json(socket,200,capture.command(path,options));return;
      }
      json(socket,405,new JSONObject().put("error","不支持的方法或路径"));
    }catch(Exception e){if(!responseStarted)try{int status=e instanceof FileNotFoundException?404:e instanceof IllegalStateException?409:e instanceof IllegalArgumentException||e instanceof JSONException?400:500;json(socket,status,new JSONObject().put("error",AppLog.reason(e)));}catch(Exception ignored){}}
    finally{writing.remove(socket);sockets.remove(socket);quietClose(socket);}
  }
  private static String line(InputStream in,int limit)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();int previous=-1;for(int n=0;n<limit;n++){int b=in.read();if(b<0)throw new EOFException();if(previous==13&&b==10){byte[] bytes=out.toByteArray();return new String(bytes,0,bytes.length-1,StandardCharsets.US_ASCII);}if(b==10)throw new IOException("CRLF required");out.write(b);previous=b;}throw new IOException("HTTP line too large");}
  private void json(Socket socket,int code,JSONObject object)throws IOException{byte[] bytes=object.toString().getBytes(StandardCharsets.UTF_8);head(socket,code,"application/json; charset=utf-8",bytes.length);write(socket,bytes);}
  private void head(Socket socket,int code,String type,long size)throws IOException{
    head(socket,code,type,size,"");
  }
  private void head(Socket socket,int code,String type,long size,String extra)throws IOException{
    String status=code==200?"OK":code==206?"Partial Content":code==416?"Range Not Satisfiable":code==429?"Too Many Requests":code==400?"Bad Request":code==401?"Unauthorized":code==404?"Not Found":code==405?"Method Not Allowed":code==409?"Conflict":code==410?"Gone":"Internal Server Error";
    String head="HTTP/1.1 "+code+" "+status+"\r\nContent-Type: "+type+"\r\nCache-Control: no-store\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n"+(size>=0?"Content-Length: "+size:"Transfer-Encoding: chunked")+"\r\n"+extra+"\r\n";write(socket,head.getBytes(StandardCharsets.US_ASCII));
  }
  private void write(Socket socket,byte[] bytes)throws IOException{write(socket,bytes,0,bytes.length);}
  private void write(Socket socket,byte[] bytes,int offset,int count)throws IOException{writing.put(socket,System.nanoTime());try{socket.getOutputStream().write(bytes,offset,count);}finally{writing.remove(socket);}}
  public void close(){closed=true;if(listener!=null)try{listener.close();}catch(IOException ignored){}for(Socket socket:sockets)quietClose(socket);workers.shutdownNow();watchdog.shutdownNow();}
  private static void quietClose(Socket socket){try{socket.close();}catch(IOException ignored){}}
}
