#pragma once
#include <cmath>
#include <algorithm>
struct CameraPanelHit {int index;float distance;};
inline CameraPanelHit cameraPanelHit(float x,float y,float z,float dx,float dy,float dz){
 if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z)||!std::isfinite(dx)||!std::isfinite(dy)||!std::isfinite(dz)||dz<=.0001f)return {-1,0};
 float t=z/dz;if(t<=0||t>=15)return {-1,0};float px=((x-dx*t)/6.6f+.5f)*1600,py=(.5f-(y-dy*t)/4.125f)*1000;
 if(px>=1314&&px<=1580)for(int i=0;i<5;i++)if(py>=158+170*i&&py<=308+170*i)return {i==4?5:i,t};return {-1,0};
}

inline float armCameraWidth(float distance,bool large){return std::clamp(distance*(large?.9f:.45f),large?.05f:.025f,large?1.2f:.6f);}
