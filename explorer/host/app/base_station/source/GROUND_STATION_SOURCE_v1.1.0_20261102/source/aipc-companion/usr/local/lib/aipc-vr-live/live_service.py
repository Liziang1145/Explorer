"""One Quest subscriber on AIPC. Shared preview and explicit remote recording control; no implicit start."""
import hmac,json,asyncio
import aiohttp
from pathlib import Path
from aiohttp import web
from managed_receiver import ManagedVRView as VRView
CONTROL=Path('/home/apex/.config/aipc-vr-live-control.token')

def make_app(service=None):
    service=service or VRView('/home/apex/.config/aipc-vr-live.json')
    app=web.Application(client_max_size=8192);app['receiver']=service
    from recording_api import install as install_recording
    install_recording(app,service,CONTROL)
    from preview_feedback import PreviewFeedback
    service.feedback=PreviewFeedback(service)
    async def status(r):return web.json_response(service.public(),headers={'Cache-Control':'no-store'})
    async def command(r):
        token=CONTROL.read_text().strip()
        if not token or not hmac.compare_digest(r.headers.get('Authorization',''),'Bearer '+token):raise web.HTTPUnauthorized()
        try:
            data=await r.json()
            if not isinstance(data,dict):raise ValueError('直播操作须为对象')
            return web.json_response(await service.command(data),headers={'Cache-Control':'no-store'})
        except (ValueError,TypeError) as error:return web.json_response({'error':str(error)[:200]},status=400)
        except (aiohttp.ClientError,asyncio.TimeoutError):return web.json_response({'error':'Quest 请求超时，请查询状态后再决定是否恢复直播'},status=503)
    app.router.add_get('/status',status);app.router.add_get('/stream',service.stream);app.router.add_post('/command',command)
    async def feedback_start(app):service.feedback.task=asyncio.create_task(service.feedback.run())
    async def feedback_stop(app):
        if service.feedback.task:service.feedback.task.cancel();await asyncio.gather(service.feedback.task,return_exceptions=True)
    app.on_startup.append(service.start);app.on_startup.append(feedback_start);app.on_cleanup.append(feedback_stop);app.on_cleanup.append(service.stop)
    return app
if __name__=='__main__':web.run_app(make_app(),host='127.0.0.1',port=8101,access_log=None,shutdown_timeout=3)
