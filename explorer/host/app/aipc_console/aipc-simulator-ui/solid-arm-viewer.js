import * as THREE from '/robot-assets/three.module.js';
import {OrbitControls} from '/robot-assets/OrbitControls.js';
import {origins,originMatrix} from '/robot-assets/control-kinematics.js?v=absolute2';
import {createVehicleMaterial} from '/vehicle-appearance.js?v=1';

THREE.Object3D.DEFAULT_UP.set(0,0,1);
const views=new Map();
let assetPromise;
const M=a=>new THREE.Matrix4().set(...a.flat());

async function assets(){
  if(assetPromise)return assetPromise;
  assetPromise=(async()=>{
    const response=await fetch('/robot-assets/model.json?rig=chassis7',{cache:'no-store'});
    if(!response.ok)throw Error('实体模型描述读取失败');
    const model=await response.json();
    const binary=await fetch('/robot-assets/robot-meshes.bin.gz?v=chassis7');
    if(!binary.ok)throw Error('实体模型网格读取失败');
    const buffer=await new Response(binary.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
    const geometries=new Map();
    for(const item of model.meshes){
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(buffer,item.position.offset,item.position.bytes/4),3));
      geometry.setAttribute('normal',new THREE.BufferAttribute(new Float32Array(buffer,item.normal.offset,item.normal.bytes/4),3));
      geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(buffer,item.index.offset,item.index.bytes/4),1));
      geometry.computeBoundingSphere();geometries.set(item.id,geometry);
    }
    return {model,geometries};
  })();
  return assetPromise;
}

class ArmView{
  constructor(canvas,side,data){
    this.canvas=canvas;this.side=side;this.model=data.model;this.chain=[];this.fingers=[];this.latest=null;
    this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.1;
    this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0xf4f7fa);
    this.camera=new THREE.PerspectiveCamera(34,1,.01,20);
    const base=data.model.arms[side].base_matrix.flat(),bx=base[3],by=base[7],bz=base[11];
    this.camera.position.set(1.05,-1.3,.68);
    this.orbit=new OrbitControls(this.camera,canvas);this.orbit.target.set(0,0,.22);this.orbit.enableDamping=true;this.orbit.dampingFactor=.1;
    this.orbit.minDistance=.45;this.orbit.maxDistance=3.2;this.orbit.update();
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x8b9aaa,2.4));
    const key=new THREE.DirectionalLight(0xffffff,3.0);key.position.set(2,-3,5);this.scene.add(key);
    const fill=new THREE.DirectionalLight(0xdbe9ff,1.2);fill.position.set(-3,2,2);this.scene.add(fill);
    this.build(data.geometries);this.armRoot.position.set(-bx,-by,-bz);
    const grid=new THREE.GridHelper(2,20,0xb8c5d1,0xdde4ea);grid.rotation.x=Math.PI/2;grid.position.z=-.015;this.scene.add(grid);
    this.resize=()=>{const w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();};
    new ResizeObserver(this.resize).observe(canvas);this.resize();
    canvas.dataset.solidReady='true';
  }
  build(geometries){
    const config=this.model.arms[this.side],root=new THREE.Group();this.armRoot=root;this.scene.add(root);
    const ids=new Set([...config.node_ids,...config.gripper.finger_node_ids]);
    for(const node of this.model.nodes){
      if(node.mesh===null||!ids.has(node.id))continue;
      const mesh=new THREE.Mesh(geometries.get(node.mesh),createVehicleMaterial(node,this.model));
      mesh.matrixAutoUpdate=false;mesh.matrix.copy(M(node.world_matrix));root.add(mesh);mesh.userData.nodeId=node.id;
    }
    for(let i=0;i<6;i++){
      const parent=i?this.chain[i-1].group:root;
      const local=i?originMatrix(origins[i]):M(config.base_matrix).multiply(originMatrix(origins[i]));
      const group=new THREE.Group();group.matrixAutoUpdate=false;group.matrix.copy(local);parent.add(group);this.chain.push({group,local});
      const mesh=root.children.find(item=>item.userData.nodeId===config.node_ids[i+1]);
      if(mesh){root.remove(mesh);group.add(mesh);mesh.matrix.copy(M(config.mesh_bind_matrices[i]));}
    }
    const grip=config.gripper,B=M(config.mesh_bind_matrices[5]),axis=new THREE.Vector3(...grip.axis_cad).transformDirection(B);
    grip.finger_node_ids.forEach((id,i)=>{
      const mesh=root.children.find(item=>item.userData.nodeId===id);if(!mesh)return;
      const group=new THREE.Group();root.remove(mesh);this.chain[5].group.add(group);group.add(mesh);mesh.matrix.copy(B);
      this.fingers.push({group,axis:axis.clone(),sign:grip.finger_signs[i]});
    });
    this.setGripper(70);
  }
  setPose(radians,grip){
    if(!Array.isArray(radians)||radians.length!==6||!radians.every(Number.isFinite))return;
    this.latest=radians.slice();
    this.chain.forEach((joint,i)=>joint.group.matrix.copy(joint.local).multiply(new THREE.Matrix4().makeRotationZ(radians[i])));
    if(Number.isFinite(grip))this.setGripper(70*(1-Math.max(0,Math.min(1,grip))));
  }
  setGripper(mm){const config=this.model.arms[this.side].gripper,delta=(mm-config.reference_gap_mm)/2000;for(const f of this.fingers)f.group.position.copy(f.axis).multiplyScalar(f.sign*delta);}
  render(){this.orbit.update();this.renderer.render(this.scene,this.camera);}
}

async function mount(canvas){
  const side=(canvas.id.includes('left')||canvas.id==='vla-trajectory-canvas')?'left':'right';
  const holder=document.createElement('canvas');holder.className='solid-arm-canvas';holder.setAttribute('aria-label',(side==='left'?'左臂':'右臂')+' V3 实体模型');
  canvas.parentElement.style.position='relative';canvas.parentElement.insertBefore(holder,canvas.nextSibling);
  canvas.style.visibility='hidden';
  try{
    const data=await assets(),view=new ArmView(holder,side,data);views.set(canvas.id,{view,source:canvas});
    window.dispatchEvent(new CustomEvent('solid-arm-viewer-ready',{detail:canvas.id}));
    if(view.latest)view.setPose(view.latest);
  }catch(error){window.SolidArmViewerError=String(error&&error.stack||error);canvas.dataset.solidError=String(error);canvas.style.visibility='visible';holder.remove();console.error('实体机械臂预览加载失败，已回退骨架预览',error);}
}

function animate(){for(const {view} of views.values())view.render();requestAnimationFrame(animate);}requestAnimationFrame(animate);
window.SolidArmViewer=Object.freeze({
  setPose(id,radians,grip){const item=views.get(id);if(item)item.view.setPose(radians,grip);},
  isReady(id){return views.has(id);}
});
for(const id of ['arm3d','arm3d-left','actual-right','actual-left','vla-trajectory-canvas','vla-trajectory-canvas-right']){const canvas=document.getElementById(id);if(canvas)mount(canvas);}
