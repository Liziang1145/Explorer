"""Read-only VR live exports and a separately authorized explicit command path."""
import asyncio,hmac
from pathlib import Path
import aiohttp
from aiohttp import web
CONTROL=Path('/home/apex/.config/aipc-vr-live-control.token')
def command_authorized(request):
    if request.path!='/observer/vr-command' or request.method!='POST':return False
    try:token=CONTROL.read_text().strip()
    except OSError:return False
    return len(token)>=32 and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+token)

def install(app):
    async def status(r):
        try:
            async with app['http'].get('http://127.0.0.1:8101/status',timeout=aiohttp.ClientTimeout(total=3)) as source:
                source.raise_for_status();return web.json_response(await source.json(),headers={'Cache-Control':'no-store'})
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError):raise web.HTTPServiceUnavailable(text='VR live receiver unavailable')
    async def command(r):
        if not command_authorized(r):raise web.HTTPUnauthorized()
        try:
            data=await r.json()
            if not isinstance(data,dict) or data.get('action') not in ('configure','start','stop','keyframe','capture'):raise web.HTTPBadRequest()
            async with app['http'].post('http://127.0.0.1:8101/command',json=data,headers={'Authorization':'Bearer '+CONTROL.read_text().strip()},timeout=aiohttp.ClientTimeout(total=18)) as source:
                return web.json_response(await source.json(),status=source.status,headers={'Cache-Control':'no-store'})
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError):raise web.HTTPServiceUnavailable(text='VR live command unavailable')
    async def stream(r):
        result=None
        try:
            async with app['http'].get('http://127.0.0.1:8101/stream',timeout=aiohttp.ClientTimeout(total=None,sock_connect=2,sock_read=7)) as source:
                if source.status!=200:raise web.HTTPServiceUnavailable(text='VR live is not ready')
                result=web.StreamResponse(headers={'Content-Type':'video/mp4','Cache-Control':'no-store'});await result.prepare(r)
                async for block in source.content.iter_any():await asyncio.wait_for(result.write(block),3)
                return result
        except (aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
            if result is not None:return result
            raise web.HTTPServiceUnavailable(text='VR live source disconnected')
    app.router.add_get('/observer/vr-status',status);app.router.add_get('/observer/vr-stream',stream);app.router.add_post('/observer/vr-command',command)
