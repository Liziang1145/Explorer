"""Fixed-camera, bounded WebSocket forwarding. No arbitrary URL or device access."""
import asyncio
import uuid
from contextlib import suppress
import aiohttp
from aiohttp import web

CAMERAS=('camera1','camera2','camera3','camera4')

async def bridge(request,client,url,token):
    try:
        upstream=await client.ws_connect(url,headers={'Authorization':'Bearer '+token},heartbeat=20,max_msg_size=4*1024*1024)
    except (aiohttp.ClientError,asyncio.TimeoutError):
        raise web.HTTPServiceUnavailable(text='Camera source unavailable; retry')
    downstream=web.WebSocketResponse(heartbeat=20,max_msg_size=4096)
    async def copy(source,destination,feedback=False):
        async for message in source:
            if message.type==aiohttp.WSMsgType.TEXT:
                await asyncio.wait_for(destination.send_str(message.data),3)
            elif message.type==aiohttp.WSMsgType.BINARY and not feedback:
                await asyncio.wait_for(destination.send_bytes(message.data),3)
            elif message.type in (aiohttp.WSMsgType.ERROR,aiohttp.WSMsgType.CLOSE):
                break
    tasks=[]
    try:
        await downstream.prepare(request)
        request.app['camera_connections'].add((downstream,upstream))
        tasks=[asyncio.create_task(copy(upstream,downstream)),asyncio.create_task(copy(downstream,upstream,True))]
        done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if not task.cancelled():task.exception()
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        request.app['camera_connections'].discard((downstream,upstream))
        with suppress(aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
            await asyncio.wait_for(upstream.close(),3)
        if downstream.prepared:
            with suppress(aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
                await asyncio.wait_for(downstream.close(),3)
    return downstream

def install_ground(app):
    install_cleanup(app)
    async def websocket(request):
        kind=request.match_info['kind']
        if kind not in CAMERAS:raise web.HTTPNotFound()
        if request.query:raise web.HTTPBadRequest()
        origin=request.headers.get('Origin')
        if origin and origin!=request.scheme+'://'+request.host:raise web.HTTPForbidden()
        cfg=app['cfg']
        return await bridge(request,app['http'],cfg['upstream']+'/observer/ws/'+kind,cfg['token'])
    app.router.add_get('/ui/video-ws/{kind}',websocket)
    async def jpeg(request):
        kind=request.match_info['kind']
        if kind not in CAMERAS:raise web.HTTPNotFound()
        if request.query:raise web.HTTPBadRequest()
        origin=request.headers.get('Origin')
        if origin and origin!=request.scheme+'://'+request.host:raise web.HTTPForbidden()
        feed=app['jpeg'][kind];queue=asyncio.Queue(maxsize=1)
        ws=web.WebSocketResponse(heartbeat=20,max_msg_size=1024)
        await ws.prepare(request);feed.clients.add(queue);app['camera_connections'].add((ws,))
        if feed.task is None:feed.task=asyncio.create_task(feed.run())
        async def send():
            while not ws.closed:
                frame=await asyncio.wait_for(queue.get(),12)
                await asyncio.wait_for(ws.send_bytes(frame),3)
        async def receive():
            async for _ in ws:pass
        tasks=[asyncio.create_task(send()),asyncio.create_task(receive())]
        try:
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if not task.cancelled():task.exception()
        finally:
            feed.clients.discard(queue);app['camera_connections'].discard((ws,))
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            with suppress(aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
                await asyncio.wait_for(ws.close(),3)
        return ws
    app.router.add_get('/ui/jpeg-ws/{kind}',jpeg)

def install_observer(app):
    install_cleanup(app)
    async def websocket(request):
        kind=request.match_info['kind']
        if kind not in CAMERAS:raise web.HTTPNotFound()
        if request.query:raise web.HTTPBadRequest()
        url='http://192.168.137.2:8096/ws/'+kind+'?quality=auto&client_id='+uuid.uuid4().hex
        return await bridge(request,app['http'],url,app['native_media_token'])
    app.router.add_get('/observer/ws/{kind}',websocket)

def install_cleanup(app):
    app['camera_connections']=set()
    async def shutdown(app):
        async def close(ws):
            with suppress(aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
                await asyncio.wait_for(ws.close(code=1001),3)
        await asyncio.gather(*(close(ws) for pair in tuple(app['camera_connections']) for ws in pair))
    app.on_shutdown.append(shutdown)
