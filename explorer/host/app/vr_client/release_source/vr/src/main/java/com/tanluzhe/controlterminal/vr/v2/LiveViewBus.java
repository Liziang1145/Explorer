package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;
import java.util.concurrent.*;
import java.io.*;
import java.nio.*;

/** Bounded access-unit fanout. Slow receivers disconnect, never stall encoder/XR. */
public final class LiveViewBus {
  public static final class Frame {
    public final byte[] bytes;public final boolean key;public final long pts,sequence;public final int width,height;
    Frame(byte[] b,boolean k,long p,long seq,int w,int h){bytes=b;key=k;pts=p;sequence=seq;width=w;height=h;}
    public byte[] header(){return ByteBuffer.allocate(32).order(ByteOrder.BIG_ENDIAN).putInt(0x544c5a56).put((byte)1).put((byte)(key?1:0)).putShort((short)32).putInt((int)sequence).putLong(pts).putShort((short)width).putShort((short)height).putInt(bytes.length).putInt(0).array();}
  }
  public static final class Client implements AutoCloseable {
    public final ArrayBlockingQueue<Frame> frames=new ArrayBlockingQueue<>(8);
    public final String id=UUID.randomUUID().toString();
    public volatile boolean closed;private boolean waiting=true;private final Runnable disconnect;
    Client(Runnable disconnect){this.disconnect=disconnect;}
    public void close(){if(closed)return;closed=true;frames.clear();disconnect.run();}
  }
  private final Set<Client> clients=new HashSet<>();private long sequence;
  public synchronized Client subscribe(Runnable disconnect){if(clients.size()>=2)throw new IllegalStateException("直播最多同时2个接收端");Client c=new Client(disconnect);clients.add(c);return c;}
  public synchronized void remove(Client c){clients.remove(c);c.close();}
  public synchronized boolean hasClient(String id){for(Client c:clients)if(c.id.equals(id)&&!c.closed)return true;return false;}
  public synchronized int size(){return clients.size();}
  public synchronized void publish(byte[] bytes,boolean key,long pts,int w,int h,byte[] codec){
    Frame frame=new Frame(key?NalUnits.join(codec,bytes):bytes,key,pts,sequence++,w,h);
    Iterator<Client> it=clients.iterator();while(it.hasNext()){Client c=it.next();if(c.closed){it.remove();continue;}if(c.waiting&&!key)continue;if(key)c.waiting=false;if(!c.frames.offer(frame)){c.close();it.remove();}}
  }
  public synchronized void clear(){for(Client c:clients)c.close();clients.clear();}
  public synchronized void finish(){for(Client c:clients){c.closed=true;c.frames.clear();}clients.clear();}
}
