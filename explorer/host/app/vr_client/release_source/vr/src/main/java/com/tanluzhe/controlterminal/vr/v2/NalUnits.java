package com.tanluzhe.controlterminal.vr.v2;
import java.io.ByteArrayOutputStream;
/** AVC access units: Annex B or four-byte AVCC lengths, never arbitrary byte slicing. */
public final class NalUnits {
  public static byte[] annexB(byte[] sample){
    if(sample.length>4194304)throw new IllegalArgumentException("AVC access unit exceeds 4MiB");
    if(sample.length>=5&&sample[0]==0&&sample[1]==0&&sample[2]==0&&sample[3]==1)return sample.clone();
    // Check an entire AVCC access unit before considering a three-byte start
    // code: a 256..511-byte AVCC length also begins 00 00 01.
    boolean lengths=sample.length>0;int scan=0;
    while(lengths&&scan<sample.length){if(sample.length-scan<4){lengths=false;break;}long n=0;for(int k=0;k<4;k++)n=(n<<8)|(sample[scan++]&255);if(n<1||n>sample.length-scan){lengths=false;break;}scan+=(int)n;}
    if(!lengths&&sample.length>=4&&sample[0]==0&&sample[1]==0&&sample[2]==1)return sample.clone();
    if(!lengths)throw new IllegalArgumentException("Invalid AVC access unit");
    ByteArrayOutputStream out=new ByteArrayOutputStream();int at=0;
    while(at<sample.length){if(sample.length-at<4)throw new IllegalArgumentException("Truncated AVCC length");long n=0;for(int k=0;k<4;k++)n=(n<<8)|(sample[at++]&255);if(n<1||n>sample.length-at)throw new IllegalArgumentException("Invalid AVCC NAL length");out.write(0);out.write(0);out.write(0);out.write(1);out.write(sample,at,(int)n);at+=(int)n;}
    return out.toByteArray();
  }
  public static byte[] join(byte[] a,byte[] b){byte[] r=new byte[a.length+b.length];System.arraycopy(a,0,r,0,a.length);System.arraycopy(b,0,r,a.length,b.length);return r;}
}
