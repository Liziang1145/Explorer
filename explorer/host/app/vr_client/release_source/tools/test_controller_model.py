"""Execute the production GLB loader on Windows; no Android device/emulator involved."""
from pathlib import Path
import json, struct, subprocess

root=Path(__file__).resolve().parents[1]
out=root/'vr/build/controller-model-test'
out.mkdir(parents=True,exist_ok=True)

def fixture(edit=None):
    # Cube with a transformed parent, smooth source normals, uint16 indices.
    positions=[(.02 if i&1 else -.02,.03 if i&2 else -.03,.06 if i&4 else -.06) for i in range(8)]
    vertices=b''.join(struct.pack('<6f',*p,0,0,1) for p in positions)
    indices=struct.pack('<36H',0,2,1,1,2,3,4,5,6,5,7,6,0,1,4,1,5,4,2,6,3,3,6,7,0,4,2,2,4,6,1,3,5,3,7,5)
    binary=vertices+indices
    doc={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
         'nodes':[{'translation':[.01,.02,.03],'children':[1]},{'mesh':0,'scale':[1,2,1]}],
         'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(vertices),'byteStride':24},
                        {'buffer':0,'byteOffset':len(vertices),'byteLength':len(indices)}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3'},
                      {'bufferView':0,'byteOffset':12,'componentType':5126,'count':8,'type':'VEC3'},
                      {'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR'}],
         'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[.2,.3,.4,1]}}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1},'indices':2,'material':0}]}]}
    if edit:edit(doc)
    raw=json.dumps(doc,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4)
    binary+=b'\0'*((-len(binary))%4)
    return struct.pack('<III',0x46546c67,2,28+len(raw)+len(binary))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(binary),0x004e4942)+binary

(out/'valid.glb').write_bytes(fixture())
(out/'rotated.glb').write_bytes(fixture(lambda d:d['nodes'][0].update(rotation=[0,0,.7071067811865476,.7071067811865476])))
(out/'no-default-scene.glb').write_bytes(fixture(lambda d:d.pop('scene')))
(out/'external.glb').write_bytes(fixture(lambda d:d['buffers'][0].update(uri='file.bin')))
(out/'unsupported.glb').write_bytes(fixture(lambda d:d['meshes'][0]['primitives'][0].update(mode=1)))
(out/'cycle.glb').write_bytes(fixture(lambda d:d['nodes'][1].update(children=[0])))
(out/'bad-accessor.glb').write_bytes(fixture(lambda d:d['accessors'][0].update(count=800000)))
(out/'truncated.glb').write_bytes(fixture()[:-16])

source=r'''
#include "controller_model.h"
#include <fstream>
#include <iterator>
#include <iostream>
#include <cassert>
using namespace tlzcontroller;
int main(int argc,char**argv){
 auto fallbackMesh=fallback();assert(fallbackMesh.source==0&&fallbackMesh.vertices.size()==36*9);
 auto read=[](const char* file){std::ifstream f(file,std::ios::binary);assert(f);return std::vector<uint8_t>((std::istreambuf_iterator<char>(f)),{});};
 Mesh m=load(read("valid.glb"));assert(m.source==1&&m.vertices.size()==36*9);
 const float expected[]={-.01f,-.04f,-.03f,.03f,.08f,.09f};
 for(int k=0;k<6;k++)assert(std::abs(m.bounds[k]-expected[k])<1e-6f);
 for(size_t i=0;i<m.vertices.size();i+=9){
   assert(std::abs(m.vertices[i+5]-1)<1e-6f);assert(std::abs(m.vertices[i+6]-.2f)<1e-6f);
 }
 assert(load(read("no-default-scene.glb")).vertices.size()==m.vertices.size());
 auto rotated=load(read("rotated.glb"));
 const float rotatedBounds[]={-.05f,0,-.03f,.07f,.04f,.09f};
 for(int k=0;k<6;k++)assert(std::abs(rotated.bounds[k]-rotatedBounds[k])<1e-6f);
 for(const char* file:{"external.glb","unsupported.glb","cycle.glb","bad-accessor.glb","truncated.glb"}){
   bool rejected=false;try{load(read(file));}catch(const std::exception&){rejected=true;}assert(rejected);
 }
 for(int a=1;a<argc;a++){
   auto real=load(read(argv[a]));assert(real.source==1&&real.vertices.size()>1000);
   for(size_t i=0;i<real.vertices.size();i+=9)for(int k=0;k<3;k++)assert(real.vertices[i+k]>=real.bounds[k]-1e-7f&&real.vertices[i+k]<=real.bounds[k+3]+1e-7f);
   std::cout<<argv[a]<<" vertices="<<real.vertices.size()/9<<" bounds=";
   for(float b:real.bounds)std::cout<<b<<",";std::cout<<"\n";
   if(a==1)std::ofstream("controller-real.bin",std::ios::binary).write((char*)real.vertices.data(),real.vertices.size()*sizeof(float));
 }
 std::ofstream("controller-fallback.bin",std::ios::binary).write((char*)fallbackMesh.vertices.data(),fallbackMesh.vertices.size()*sizeof(float));
 std::cout<<"PASS: production GLB scene transforms, normals, indices, source flags, fallback, malformed GLBs and mesh bounds\n";
}
'''
(out/'test.cpp').write_text(source,encoding='utf8')
vs=Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
include=root/'vr/src/main/cpp'
real=[root/f'tools/v2_deps/controller_model_test/{side}.glb' for side in ('left','right')]
real=[p for p in real if p.is_file()]
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /std:c++17 /EHsc /I"{include}" test.cpp /Fe:test.exe',shell=True,cwd=out,check=True)
subprocess.run([str(out/'test.exe'),*map(str,real)],cwd=out,check=True,timeout=20)
