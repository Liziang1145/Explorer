"""Fixed Quest recording/preview API; upstream credentials stay on AIPC."""
import asyncio,hmac,json,math,re,time
from aiohttp import web,ClientTimeout,ClientError
from vr_directory import private_host

NAME=r'view-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.mp4'
def route(method,tail):
 allowed={'capabilities':{'GET'},'config':{'GET','PUT'},'record/config':{'GET','PUT'},'record/status':{'GET'},'record/start':{'POST'},'record/stop':{'POST'},'recordings':{'GET'},'player-feedback':{'POST'}}
 if tail in allowed:return method in allowed[tail],False
 if re.fullmatch('recordings/'+NAME+'(/download)?',tail):return method in({'GET','HEAD'}if tail.endswith('/download')else{'GET','HEAD','DELETE'}),True
 return False,False

def validate_config(data,record):
 if not isinstance(data,dict)or not data:raise ValueError('配置须为非空对象')
 keys={'width','height','fps','bitrate','eye','vertical_fov_deg','margin_left','margin_right','margin_top','margin_bottom','center_x','center_y'}
 if set(data)-keys:raise ValueError('包含未知配置字段')
 for k in('width','height'):
  if k in data and(type(data[k])is not int or not 2<=data[k]<=2560 or data[k]%2):raise ValueError('宽高须为不超过2560的正偶数')
 if all(k in data for k in('width','height'))and data['width']*data['height']>(2560*1440 if record else 1920*1080):raise ValueError('画幅超过该编码通路上限')
 for k,lo,hi in [('fps',5,60),('bitrate',250000 if record else 500000,80000000 if record else 16000000),('eye',0,1)]:
  if k in data and(type(data[k])is not int or not lo<=data[k]<=hi):raise ValueError('非法'+k)
 for k in keys-{'width','height','fps','bitrate','eye'}:
  if k in data:
   v=data[k];lo,hi=(20,120)if k=='vertical_fov_deg'else(0,.45)if k.startswith('margin_')else(0,1)
   if type(v)not in(int,float)or not math.isfinite(v)or not lo<=v<=hi:raise ValueError('非法'+k)

def install(app,service,control):
 file_slots=asyncio.Semaphore(2)
 async def proxy(r):
  token=control.read_text().strip()
  if not token or not hmac.compare_digest(r.headers.get('Authorization',''),'Bearer '+token):raise web.HTTPUnauthorized()
  tail=r.match_info['tail'];ok,isfile=route(r.method,tail)
  if not ok or r.query:raise web.HTTPNotFound()
  if tail=='player-feedback':
   try:return web.json_response(service.feedback.accept(await r.json()))
   except (ValueError,TypeError)as e:return web.json_response({'error':str(e)},status=400)
  host=service.config.get('host','')
  if not private_host(host):return web.json_response({'error':'尚未选择可认证的VR设备'},status=503)
  data=None
  if r.method in('POST','PUT'):
   if r.content_length is not None and r.content_length>8192:raise web.HTTPRequestEntityTooLarge(max_size=8192,actual_size=r.content_length)
   raw=await r.read()
   try:
    data=json.loads(raw)if raw else{}
    if r.method=='PUT':validate_config(data,tail.startswith('record/'))
    elif data!={}:raise ValueError('录制开始/停止只接受空对象，参数请先PUT record/config')
   except (ValueError,TypeError)as e:return web.json_response({'error':str(e)},status=400)
  if isfile and file_slots.locked():return web.json_response({'error':'最多两个录像文件读取'},status=429,headers={'Retry-After':'1'})
  acquired=False;response=None
  try:
   if isfile:await file_slots.acquire();acquired=True
   hs={'Authorization':'Bearer '+service.config['token'],'Accept-Encoding':'identity'}
   for k in('Range','If-Range'):
    if r.headers.get(k):hs[k]=r.headers[k]
   async with service.http.request(r.method,service.url(tail),json=data if data is not None else None,headers=hs,allow_redirects=False,auto_decompress=False,timeout=ClientTimeout(total=None if isfile else 18,sock_connect=3,sock_read=15))as upstream:
    headers={'Cache-Control':'no-store'}
    for k in('Content-Type','Content-Length','Content-Range','Accept-Ranges','ETag','Content-Disposition','Retry-After'):
     if upstream.headers.get(k):headers[k]=upstream.headers[k]
    if isfile:
     response=web.StreamResponse(status=upstream.status,headers=headers);await response.prepare(r)
     if r.method!='HEAD':
      async for block in upstream.content.iter_chunked(65536):await asyncio.wait_for(response.write(block),5)
     return response
    parts=[];size=0
    async for part in upstream.content.iter_chunked(16384):
     size+=len(part)
     if size>2097152:raise ValueError('VR元数据过大')
     parts.append(part)
    body=b''.join(parts)
    try:parsed=json.loads(body)
    except ValueError:parsed={'error':'VR返回非JSON响应','upstream_status':upstream.status}
    # Preserve 400/404/409/429 rather than disguising them as success or retrying a command.
    return web.json_response(parsed,status=upstream.status,headers={'Cache-Control':'no-store',**({'Retry-After':upstream.headers['Retry-After']}if'Retry-After'in upstream.headers else{})})
  except (ClientError,asyncio.TimeoutError,OSError,ValueError)as e:
   if response is not None:return response
   return web.json_response({'error':'VR录像服务暂不可用；操作超时后请先查询状态，不自动重发开始命令','detail':type(e).__name__},status=503)
  finally:
   if acquired:file_slots.release()
 app.router.add_route('*','/view-api/{tail:.*}',proxy)
