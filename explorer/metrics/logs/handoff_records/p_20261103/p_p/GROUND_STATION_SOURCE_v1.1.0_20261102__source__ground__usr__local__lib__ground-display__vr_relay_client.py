"""Ground subscribes to AIPC's shared VR receiver, never directly to Quest."""
import asyncio,json
from pathlib import Path
import aiohttp
from aiohttp import web

def install(app,session):
    async def get(r):
        try:
            async with app['http'].get(app['cfg']['upstream']+'/observer/vr-status',headers={'Authorization':'Bearer '+app['cfg']['token']},timeout=aiohttp.ClientTimeout(total=4)) as source:
                source.raise_for_status();data=await source.json()
                return web.json_response({**data,'relay':'AIPC'},headers={'Cache-Control':'no-store'})
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError):
            return web.json_response({'upstream_unavailable':True,'reachable':False,'host':'','status':None,'codec':None,'relay':'AIPC','stats':{},'error':'基站无法连接 AIPC VR 直播服务，正在自动重试'},headers={'Cache-Control':'no-store'})
    async def command(r):
        if not session(r) or session(r)['role']!='admin':raise web.HTTPForbidden()
        try:
            data=await r.json()
            if not isinstance(data,dict) or data.get('action') not in ('configure','start','stop','keyframe','capture'):raise ValueError('未知 VR 直播操作')
            token=Path('/etc/ground-display/vr-live-control.token').read_text().strip()
            async with app['http'].post(app['cfg']['upstream']+'/observer/vr-command',json=data,headers={'Authorization':'Bearer '+token},timeout=aiohttp.ClientTimeout(total=18)) as source:
                result=await source.json();return web.json_response(result,status=source.status,headers={'Cache-Control':'no-store'})
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,OSError):return web.json_response({'error':'AIPC VR 直播操作暂不可用，请查询状态后再试'},status=503)
    async def stream(r):
        result=None
        try:
            async with app['http'].get(app['cfg']['upstream']+'/observer/vr-stream',headers={'Authorization':'Bearer '+app['cfg']['token']},timeout=aiohttp.ClientTimeout(total=None,sock_connect=3,sock_read=7)) as source:
                if source.status!=200:raise web.HTTPServiceUnavailable(text='VR live not ready')
                result=web.StreamResponse(headers={'Content-Type':'video/mp4','Cache-Control':'no-store'});await result.prepare(r)
                async for block in source.content.iter_any():await asyncio.wait_for(result.write(block),3)
                return result
        except (aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
            if result is not None:return result
            raise web.HTTPServiceUnavailable(text='AIPC VR relay disconnected')
    app.router.add_get('/api/vr-view',get);app.router.add_post('/api/vr-view',command);app.router.add_get('/ui/vr-view.mp4',stream)
