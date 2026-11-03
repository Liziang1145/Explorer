"""Validated, persistent display settings shared by the preview and physical kiosk."""
import json,math,time
from pathlib import Path
DEFAULT={'layout':'split','leftPercent':42,'video':'auto','hud':True,'view':{'azimuth':.65,'elevation':.55,'radius':14,'center':[0,0,0]},'revision':0,'streamRevision':0,'panels':['camera','depth','map','vr']}
def validate(patch,current):
 if not isinstance(patch,dict) or set(patch)-{'layout','leftPercent','video','hud','view','reconnect','panels'}:raise ValueError('无效展示设置')
 result={**current}
 for key,value in patch.items():
  if key=='reconnect':
   if value is not True:raise ValueError('重连指令无效')
   result['streamRevision']=current.get('streamRevision',0)+1;continue
  if key=='panels' and (not isinstance(value,list) or not 1<=len(value)<=8 or any(x not in ('camera','depth','map','vr','camera1','camera2','camera3','camera4') for x in value) or len(set(value))!=len(value)):raise ValueError('画面组合无效')
  if key=='layout' and value not in ('split','triple','camera','depth','map','vr','vr-camera','vr-map','quad','custom','cameras','camera1','camera2','camera3','camera4'):raise ValueError('未知布局')
  if key=='video' and value not in ('auto','hevc','mjpeg'):raise ValueError('未知视频模式')
  if key=='hud' and type(value) is not bool:raise ValueError('状态信息开关无效')
  if key=='leftPercent' and (type(value) not in (int,float) or not math.isfinite(value) or not 25<=value<=75):raise ValueError('画面比例须为 25–75')
  if key=='view':
   if not isinstance(value,dict) or set(value)!={'azimuth','elevation','radius','center'}:raise ValueError('三维视角无效')
   coords=[value.get('azimuth'),value.get('elevation'),value.get('radius')];center=value.get('center')
   if not isinstance(center,list) or len(center)!=3:raise ValueError('视角中心无效')
   if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e6 for x in coords+center):raise ValueError('视角数值无效')
   if not .02<=value['elevation']<=1.55 or not .5<=value['radius']<=500:raise ValueError('视角范围无效')
  result[key]=value
 result['revision']=current.get('revision',0)+1;result['updated_at']=time.time();return result
class Store:
 def __init__(self,path='/var/lib/ground-display/display.json'):
  self.path=Path(path);self.value={**DEFAULT,'view':dict(DEFAULT['view'])}
  if self.path.exists():
   try:
    raw=json.loads(self.path.read_text());self.value=validate({k:v for k,v in raw.items() if k in DEFAULT and k not in ('revision','streamRevision')},self.value);self.value['revision']=int(raw.get('revision',0));self.value['streamRevision']=int(raw.get('streamRevision',0))
   except (ValueError,TypeError,KeyError):pass
 def update(self,patch):
  value=validate(patch,self.value);self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(value));temp.replace(self.path);self.value=value;return value
