package com.tanluzhe.controlterminal.vr.v2;
import java.util.Map;
/** OPERATOR_STATE key15; physical instantaneous L/R thumbstick clicks, never local shortcuts. */
public final class StickButtons {
 public final int valid,pressed;
 public StickButtons(int valid,int pressed){if((valid&~3)!=0||(pressed&~valid)!=0)throw new IllegalArgumentException("stick click bitmap");this.valid=valid;this.pressed=pressed;}
 public static StickButtons invalid(){return new StickButtons(0,0);}
 public static StickButtons nativeSample(int buttons,float[] pointer,boolean focused){if(!focused||pointer.length<11)return invalid();int valid=(int)pointer[10]&3;int pressed=((buttons&64)!=0?1:0)|((buttons&32)!=0?2:0);return new StickButtons(valid,pressed&valid);}
 public Map<Long,Object> cbor(){return Cbor.map(0,1,1,valid,2,pressed);}
}
