"""Validate the supplied real scan with the production decoder, and export exact GPU buffers."""
from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[1];out=root/'vr/build/colored-scene-test';out.mkdir(parents=True,exist_ok=True)
source=r'''
#include "colored_scene_data.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>
#include <chrono>
using namespace tlzscene;
std::vector<uint8_t> read(const char* p){std::ifstream f(p,std::ios::binary);assert(f);return {(std::istreambuf_iterator<char>(f)),{}};}
uint64_t hash(const float* values){uint64_t h=1469598103934665603ULL;for(int i=0;i<6;i++){uint32_t bits;memcpy(&bits,values+i,4);h=(h^bits)*1099511628211ULL;}return h;}
int main(int argc,char**argv){
 assert(argc==4);auto p=read(argv[1]),c=read(argv[2]),ix=read(argv[3]);
 auto start=std::chrono::steady_clock::now();auto scene=decode(p.data(),p.size(),c.data(),c.size(),ix.data(),ix.size(),p.size()/12,ix.size()/12);
 assert(scene.vertices==410071&&scene.triangles==780279&&scene.bytes<MaxAssetBytes);
 const float bounds[]={-13.950570f,-.120455f,-5.280784f,3.884858f,.849376f,7.245167f};
 for(int k=0;k<6;k++)assert(std::abs(scene.bounds[k]-bounds[k])<.00001f);
 assert(linear(0)==0&&linear(255)==1&&std::abs(linear(128)-.21586)<.00001);
 uint64_t sourceHash=0,outputHash=0;size_t triangles=0,duplicates=0,maxIndex=0;
 for(size_t t=0;t<ix.size()/12;t++){
   uint64_t h=0;for(int j=0;j<3;j++){
     uint32_t i=u32(ix.data()+t*12+j*4);maxIndex=std::max(maxIndex,(size_t)i);
     float v[6];for(int k=0;k<3;k++){v[k]=f32(p.data()+i*12+k*4);v[k+3]=linear(c[i*3+k]);}
     h=h*131+hash(v);
   }sourceHash+=h;
 }
 std::ofstream vertices("scene-vertices.bin",std::ios::binary),indices("scene-indices.bin",std::ios::binary),chunks("scene-chunks.txt");
 for(const auto& chunk:scene.chunks){
   assert(chunk.indices.size()%3==0);triangles+=chunk.indices.size()/3;duplicates+=chunk.vertices.size()/6;
   for(size_t t=0;t<chunk.indices.size();t+=3){
     uint64_t h=0;for(int j=0;j<3;j++){auto i=chunk.indices[t+j];assert(i<chunk.vertices.size()/6);h=h*131+hash(chunk.vertices.data()+i*6);}outputHash+=h;
   }
   vertices.write((char*)chunk.vertices.data(),chunk.vertices.size()*4);indices.write((char*)chunk.indices.data(),chunk.indices.size()*4);
   chunks<<chunk.vertices.size()/6<<" "<<chunk.indices.size();for(float b:chunk.bounds)chunks<<" "<<b;chunks<<"\n";
 }
 assert(triangles==scene.triangles&&sourceHash==outputHash&&maxIndex>65535);
 auto identity=std::array<float,16>{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
 assert(visible({-.5f,-.5f,-.5f,.5f,.5f,.5f},identity));assert(!visible({2,0,0,3,1,1},identity));assert(visible({-20,-20,-20,20,20,20},identity));
 bool invalid=false;auto bad=ix;bad[0]=bad[1]=bad[2]=bad[3]=255;
 try{decode(p.data(),p.size(),c.data(),c.size(),bad.data(),bad.size(),p.size()/12,ix.size()/12);}catch(const std::exception&){invalid=true;}assert(invalid);
 std::cout<<"PASS: full scan preserves every triangle and linear vertex colour, uint32 indices, exact display coordinates, per-chunk bounds/frustum; chunks="<<scene.chunks.size()<<" GPU bytes="<<scene.bytes<<" per-chunk vertices="<<duplicates<<" decode_ms="<<std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count()<<"\n";
 std::ofstream("metrics.json")<<"{\"chunks\":"<<scene.chunks.size()<<",\"gpu_bytes\":"<<scene.bytes<<",\"source_vertices\":"<<scene.vertices<<",\"chunk_vertices\":"<<duplicates<<",\"triangles\":"<<triangles<<"}";
}
'''
(out/'test.cpp').write_text(source,encoding='utf8')
vs=Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /O2 /std:c++17 /EHsc /I"{root/"vr/src/main/cpp"}" test.cpp /Fe:test.exe',shell=True,cwd=out,check=True)
assets=root/'vr/src/main/assets/colored_scene'
subprocess.run([str(out/'test.exe'),*[str(assets/name) for name in ['positions.bin','colors.bin','indices.bin']]],cwd=out,check=True,timeout=30)
