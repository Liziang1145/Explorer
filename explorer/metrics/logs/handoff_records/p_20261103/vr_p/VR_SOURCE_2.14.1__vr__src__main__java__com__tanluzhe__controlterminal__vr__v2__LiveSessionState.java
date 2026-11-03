package com.tanluzhe.controlterminal.vr.v2;

/** Foreground auto-live policy; explicit cancellation survives pause/resume in this session. */
public final class LiveSessionState {
  public static final class Snapshot {
    public final boolean active;
    public final long revision;
    public final String startedBy, stopReason;
    private Snapshot(boolean active,long revision,String startedBy,String stopReason) {
      this.active=active;this.revision=revision;this.startedBy=startedBy;this.stopReason=stopReason;
    }
  }
  private volatile Snapshot current=new Snapshot(false,0,"","not_started");
  private volatile boolean wanted=true;
  public Snapshot snapshot(){return current;}
  public boolean wanted(){return wanted;}
  public void requestStart(){wanted=true;}
  public void requestStop(){wanted=false;}
  public boolean shouldAutoStart(boolean foreground,boolean renderReady){return wanted&&foreground&&renderReady&&!current.active;}
  public synchronized void startRemote(){
    requestStart();start("backend");
  }
  public synchronized void start(String source){
    if(!current.active)current=new Snapshot(true,current.revision+1,source,"");
  }
  public synchronized void stop(String reason){
    if(current.active)current=new Snapshot(false,current.revision+1,current.startedBy,reason);
  }
}
