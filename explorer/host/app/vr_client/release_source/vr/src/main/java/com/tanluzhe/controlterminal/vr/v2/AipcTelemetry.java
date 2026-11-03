package com.tanluzhe.controlterminal.vr.v2;

import com.tanluzhe.controlterminal.vr.AppLog;
import java.util.concurrent.*;
import okhttp3.*;
import org.json.*;

/** Read-only 3 Hz telemetry, bounded HTTP, no commands and no overlapping requests. */
public final class AipcTelemetry implements AutoCloseable {
  private final Dashboard ui;
  private final String endpoint,token;
  private final ScheduledExecutorService worker=Executors.newSingleThreadScheduledExecutor();
  private final OkHttpClient http=new OkHttpClient.Builder().followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false).connectTimeout(1200,TimeUnit.MILLISECONDS).readTimeout(1200,TimeUnit.MILLISECONDS).callTimeout(1600,TimeUnit.MILLISECONDS).build();
  private volatile boolean closed,active=true;
  private volatile Call pending;
  private long logged;
  public AipcTelemetry(String host,int port,String token,Dashboard ui){this.ui=ui;this.token=token;endpoint=BaseLink.endpoint("http",host,port)+"/api/vr_telemetry";}
  public void start(){worker.scheduleWithFixedDelay(this::poll,0,333,TimeUnit.MILLISECONDS);}
  public void foreground(boolean value){active=value;if(!value&&pending!=null)pending.cancel();}
  private void poll(){if(closed||!active)return;
    try{
      Call call=http.newCall(new Request.Builder().url(endpoint).header("Authorization","Bearer "+token).build());pending=call;
      try(Response response=call.execute()){
        if(!response.isSuccessful()||response.body()==null)throw new java.io.IOException("HTTP "+response.code());
        java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;
        java.io.InputStream in=response.body().byteStream();while((n=in.read(buffer))!=-1){if(bytes.size()+n>262144)throw new java.io.IOException("遥测超过256KiB");bytes.write(buffer,0,n);}
        Telemetry sample=parse(new JSONObject(bytes.toString("UTF-8")),System.nanoTime());
        if(!closed&&active){ui.telemetry=sample;ui.telemetryError="";}
      }
    }catch(Exception e){if(!closed&&active){ui.telemetryError="AIPC 遥测："+AppLog.reason(e);long now=System.nanoTime();if(now-logged>5_000_000_000L){logged=now;AppLog.warn("TELEMETRY","POLL",ui.telemetryError);}}}
    finally{pending=null;}
  }
  public static Telemetry parse(JSONObject j,long now)throws JSONException{
    JSONObject base=j.optJSONObject("base"),arms=j.optJSONObject("arms");
    return new Telemetry(now,j.optString("mode",""),j.optString("mode_text","模式未知"),j.isNull("error")?"":j.optString("error",""),j.optBoolean("stopped",false),number(base,"vx"),number(base,"vy"),number(base,"wz"),arm(arms==null?null:arms.optJSONObject("left")),arm(arms==null?null:arms.optJSONObject("right")),base==null?"":base.optString("reason",""),number(j,"vr_motion_scale"),j.optString("vr_motion_scale_text",""));
  }
  private static double number(JSONObject j,String key){Object v=j==null?null:j.opt(key);return v instanceof Number&&Double.isFinite(((Number)v).doubleValue())?((Number)v).doubleValue():Double.NaN;}
  private static Telemetry.Arm arm(JSONObject j)throws JSONException{
    if(j==null)return Telemetry.Arm.unknown();float[][] points=null;float[] q=null;
    JSONArray links=j.optJSONArray("link_cm");if(links!=null&&links.length()==7){points=new float[7][3];try{for(int i=0;i<7;i++){JSONArray p=links.getJSONArray(i);if(p.length()!=3)throw new JSONException("point");for(int k=0;k<3;k++){Object v=p.get(k);if(!(v instanceof Number)||!Double.isFinite(((Number)v).doubleValue())||Math.abs(((Number)v).doubleValue())>1000)throw new JSONException("coordinate");points[i][k]=((Number)v).floatValue();}}}catch(JSONException invalid){points=null;}}
    JSONArray quat=j.optJSONArray("ee_quat");if(quat!=null&&quat.length()==4){q=new float[4];double norm=0;for(int i=0;i<4;i++){Object v=quat.opt(i);q[i]=v instanceof Number?((Number)v).floatValue():Float.NaN;norm+=q[i]*q[i];}if(!Double.isFinite(norm)||norm<.01||norm>4)q=null;else for(int i=0;i<4;i++)q[i]/=Math.sqrt(norm);}
    double open=number(j,"grip_open");return new Telemetry.Arm(j.optString("state","unknown"),j.optString("ee_src",""),j.optString("reason",""),points,q,Double.isFinite(open)&&open>=0&&open<=1?(float)open:Float.NaN);
  }
  public void close(){closed=true;Call call=pending;if(call!=null)call.cancel();worker.shutdownNow();http.dispatcher().cancelAll();http.connectionPool().evictAll();}
}
