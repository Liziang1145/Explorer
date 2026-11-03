"""Read-only export for the physical ground display; no VR session or command routes."""
import asyncio,base64,hmac,json,os,sys,time
from pathlib import Path
import aiohttp
from aiohttp import web
import observer_vr_live
sys.path.insert(0,'/home/apex/tlz-v2')
from tlz2.codec import decode
CONFIG=Path('/home/apex/.config/tlz-v2/ground-observer.json')
def jsonable(value):
    if isinstance(value,dict):return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [jsonable(v) for v in value]
    if isinstance(value,bytes):return {'binary_bytes':len(value)}
    return value
def make_app(cfg):
    @web.middleware
    async def auth(request,handler):
        if observer_vr_live.command_authorized(request):return await handler(request)
        if not hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+cfg['token']):raise web.HTTPUnauthorized()
        if request.method not in ('GET','HEAD'):raise web.HTTPMethodNotAllowed(request.method,['GET'])
        return await handler(request)
    app=web.Application(middlewares=[auth],client_max_size=4096)
    async def operator(request):
        try:
            async with app['unix'].get('http://localhost/operator-input/latest') as r:
                r.raise_for_status();data=await r.json()
            event=data.get('event');result={k:v for k,v in data.items() if k!='event'}
            if event:
                packet=decode(base64.b64decode(event['packet_base64'],validate=True))
                result['event']={k:v for k,v in event.items() if k!='packet_base64'}
                result['body']=jsonable(packet.body)
            result.update(read_only=True,execution_authorized=False,exported_wall_ns=str(time.time_ns()))
            return web.json_response(result,headers={'Cache-Control':'no-store'})
        except (aiohttp.ClientError,ValueError,KeyError):return web.json_response({'available':False,'fresh':False,'read_only':True,'execution_authorized':False,'reason':'AIPC input observer unavailable'},status=503)
    async def proxy(request):
        paths={'snapshot':'/ui/snapshot','cloud':'/ui/source/cloud','media-status':'/ui/hevc/status','camera':'/v2/media/hevc/camera','depth':'/v2/media/hevc/depth'}
        kind=request.match_info['kind']
        if kind not in paths and kind not in ('camera1','camera2','camera3','camera4'):raise web.HTTPNotFound()
        extra=kind in ('camera1','camera2','camera3','camera4')
        url=('http://192.168.137.2:8096/stream/'+kind+'?quality=720p15') if extra else ('http://192.168.137.2:8088'+paths[kind])
        token=app['native_media_token'] if extra else app['observer_token']
        try:
            async with app['http'].get(url,headers={'Authorization':'Bearer '+token}) as upstream:
                if upstream.status!=200:raise web.HTTPServiceUnavailable(text='AIPC source not ready')
                if kind not in ('camera','depth','camera1','camera2','camera3','camera4'):
                    return web.Response(body=await upstream.read(),content_type='application/json',headers={'Cache-Control':'no-store'})
                response=web.StreamResponse(headers={'Content-Type':upstream.headers.get('Content-Type','video/mp4'),'Cache-Control':'no-store'})
                await response.prepare(request)
                async for chunk in upstream.content.iter_any():await asyncio.wait_for(response.write(chunk),3)
                return response
        except (aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
            if 'response' in locals():return response
            raise web.HTTPServiceUnavailable(text='AIPC source disconnected')
    async def start(app):
        native=json.loads(Path('/home/apex/.config/tlz-v2/direct.json').read_text())
        app['observer_token']=native['tokens']['observer']
        app['native_media_token']=json.loads(Path('/home/apex/.config/tlz-v2/native-camera-media.json').read_text())['token']
        timeout=aiohttp.ClientTimeout(total=None,sock_connect=2,sock_read=6)
        app['http']=aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=48))
        app['unix']=aiohttp.ClientSession(connector=aiohttp.UnixConnector(path='/run/tlz-aipc/adapter.sock'),timeout=aiohttp.ClientTimeout(total=2))
    async def stop(app):await app['http'].close();await app['unix'].close()
    observer_vr_live.install(app)
    from camera_channels import install_observer
    install_observer(app)
    app.router.add_get('/observer/operator',operator);app.router.add_get('/observer/{kind}',proxy)
    app.on_startup.append(start);app.on_cleanup.append(stop);return app
if __name__=='__main__':web.run_app(make_app(json.loads(CONFIG.read_text())),host='192.168.137.2',port=8097,access_log=None)
