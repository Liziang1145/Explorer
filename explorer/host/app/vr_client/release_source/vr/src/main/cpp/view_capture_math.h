#pragma once
#include <algorithm>
#include <cmath>

struct ViewCrop { float x0,y0,x1,y1,horizontalDegrees,verticalDegrees; };
// The principal ray is tangent (0,0), not the midpoint of an asymmetric eye texture.
// Always crop symmetrically about that ray. Opposing margins use the larger value.
inline ViewCrop viewCrop(float l,float r,float d,float u,float aspect,const float* p){
  constexpr float pi=3.14159265358979323846f;
  float baseY=std::min(std::tan(p[0]*pi/360.f),std::min(std::min(-d,u),std::min(-l,r)/aspect));
  float baseX=baseY*aspect;
  float halfY=std::min(baseY*(1-2*std::max(p[3],p[4])),baseX*(1-2*std::max(p[1],p[2]))/aspect);
  float halfX=halfY*aspect;
  return {(-halfX-l)/(r-l),(-halfY-d)/(u-d),(halfX-l)/(r-l),(halfY-d)/(u-d),
    2*std::atan(halfX)*180.f/pi,2*std::atan(halfY)*180.f/pi};
}
