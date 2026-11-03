package com.tanluzhe.controlterminal.vr.v2;

import java.util.ArrayList;

/** Display-only cm/B -> metre/OpenXR geometry. No IK/FK and no control output. */
public final class ArmGeometry {
  private final float[][][] shown=new float[2][][];
  private long previous;
  public float[] labels=new float[]{0,0,0,-2,0,0,0,-2};
  private final ArrayList<Float> vertices=new ArrayList<>();
  public static float[] position(int side,float[] cm){return new float[]{(side==0?-.155f:.155f)+cm[0]/100,.32f+.020f+cm[2]/100,-(.185f+cm[1]/100)};}
  public float[] sample(Telemetry t,long now){
    vertices.clear();labels=new float[]{0,0,0,-2,0,0,0,-2};
    double dt=previous==0?.02:Math.min(.2,Math.max(0,(now-previous)/1e9));previous=now;float mix=(float)(1-Math.exp(-dt/.09));
    for(int side=0;side<2;side++){
      Telemetry.Arm a=side==0?t.left:t.right;
      if(!t.fresh(now)||a.links==null||a.links.length!=7){shown[side]=null;continue;}
      boolean valid=true;for(float[] p:a.links)if(p==null||p.length!=3)valid=false;
      if(!valid){shown[side]=null;continue;}
      if(shown[side]==null){shown[side]=new float[7][];for(int i=0;i<7;i++)shown[side][i]=position(side,a.links[i]);}
      else for(int i=0;i<7;i++){float[] target=position(side,a.links[i]);for(int k=0;k<3;k++)shown[side][i][k]+=(target[k]-shown[side][i][k])*mix;}
      float[] color=a.source.equals("feedback")?new float[]{.02f,.78f,.61f,1}:new float[]{.72f,.48f,.08f,.6f};
      for(int i=1;i<7;i++)line(shown[side][i-1],shown[side][i],color);
      float[] end=shown[side][6];System.arraycopy(end,0,labels,side*4,3);labels[side*4+1]+=.08f;labels[side*4+3]=Float.isFinite(a.open)?a.open:-1;
      if(a.quaternion!=null&&Float.isFinite(a.open)){
        float gap=.009f+.04f*a.open;
        line(local(end,a.quaternion,0,0,0),local(end,a.quaternion,0,.035f,0),color);
        line(local(end,a.quaternion,-.065f,.035f,0),local(end,a.quaternion,.065f,.035f,0),color);
        for(int sign:new int[]{-1,1}){line(local(end,a.quaternion,sign*gap,.035f,0),local(end,a.quaternion,sign*gap,.105f,0),color);line(local(end,a.quaternion,sign*gap,.105f,0),local(end,a.quaternion,sign*(gap-.006f),.105f,0),color);}
      }
    }
    float[] out=new float[vertices.size()];for(int i=0;i<out.length;i++)out[i]=vertices.get(i);return out;
  }
  public float[] rightCameraAnchor(){if(shown[1]==null)return null;float loX=Float.POSITIVE_INFINITY,hiX=-loX,loZ=loX,hiZ=-loX,top=-loX;for(float[] p:shown[1]){loX=Math.min(loX,p[0]);hiX=Math.max(hiX,p[0]);loZ=Math.min(loZ,p[2]);hiZ=Math.max(hiZ,p[2]);top=Math.max(top,p[1]);}return new float[]{(loX+hiX)*.5f,top+.18f,(loZ+hiZ)*.5f};}
  private float[] local(float[] origin,float[] q,float x,float y,float z){
    float[] r=Math3.mul(Math3.mul(q,new float[]{x,y,z,0}),new float[]{-q[0],-q[1],-q[2],q[3]});
    return new float[]{origin[0]+r[0],origin[1]+r[2],origin[2]-r[1]};
  }
  private void line(float[] a,float[] b,float[] color){
    double norm=0;for(int i=0;i<3;i++){if(!Float.isFinite(a[i])||!Float.isFinite(b[i]))return;norm+=(a[i]-b[i])*(a[i]-b[i]);}if(norm<1e-12)return;
    for(float[] p:new float[][]{a,b}){for(float v:p)vertices.add(v);for(float v:color)vertices.add(v);}
  }
}
