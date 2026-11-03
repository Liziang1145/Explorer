"""Authenticated hub mapping to one fixed ground display endpoint."""
import json,socket
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
CONFIG=Path('/home/apex/.config/ground-display-control.json')
UPSTREAM='http://192.168.137.131:8080'
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
OPENER=build_opener(ProxyHandler({}),NoRedirect())
ALLOWED={'layout','leftPercent','video','hud','panels','reconnect','view'}

def serve(handler,method='GET',data=None):
    if urlsplit(handler.path).query:return handler.hub_reply({'error':'此接口不接受查询参数'},400)
    if method not in ('GET','POST'):return handler.hub_reply({'error':'不支持的操作'},405)
    if method=='POST' and (not isinstance(data,dict) or not data or set(data)-ALLOWED):
        return handler.hub_reply({'error':'仅支持基站大屏的布局与显示设置'},400)
    try:
        cfg=json.loads(CONFIG.read_text());token=cfg['token']
        headers={'Authorization':'Bearer '+token,'Origin':UPSTREAM,'X-Ground-Client':'display','Content-Type':'application/json'}
        payload=None if method=='GET' else json.dumps(data,allow_nan=False).encode()
        request=Request(UPSTREAM+'/api/display',data=payload,headers=headers,method=method)
        with OPENER.open(request,timeout=3) as response:
            raw=response.read(262145)
            if len(raw)>262144:raise ValueError('Oversized reply')
            result=json.loads(raw)
        if not isinstance(result,dict) or not isinstance(result.get('state'),dict):raise ValueError('Invalid reply')
        handler.hub_reply({**result,'connection':{'reachable':True,'target':'基站','via':'AIPC'}})
    except HTTPError as error:
        if error.code==400:return handler.hub_reply({'error':'基站拒绝此显示设置，请检查布局、组合或参数范围'},400)
        if error.code in (401,403):return handler.hub_reply({'error':'AIPC 与基站的大屏控制认证失败，请检查专用配置','connection':{'reachable':True,'authenticated':False}},502)
        return handler.hub_reply({'error':'基站显示服务暂不可用','connection':{'reachable':False}},503)
    except (URLError,socket.timeout,TimeoutError,OSError):
        return handler.hub_reply({'error':'AIPC 无法连接基站，正在等待恢复；未修改大屏设置','connection':{'reachable':False}},503)
    except (ValueError,KeyError,TypeError):
        return handler.hub_reply({'error':'基站显示映射配置或响应异常'},502)
