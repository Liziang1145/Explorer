"""Authenticated workbench proxy over a dedicated, restricted SSH tunnel."""
import gzip,json, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parent
GET_ROUTES={'resources','services','io','gpio','communications','protocols','snapshot'}
POST_ROUTES={'gpio','gpio/renew','protocols','integrations/lidar','integrations/antenna','integrations/switch'}
def fetch(suffix,data=None):
    token=(ROOT/'kr260-agent-token').read_text().strip()
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept-Encoding':'gzip'}
    req=urllib.request.Request('http://127.0.0.1:8092/'+suffix,headers=headers,data=None if data is None else json.dumps(data,allow_nan=False).encode())
    with urllib.request.urlopen(req,timeout=4) as response:
        raw=response.read(2*1024*1024)
        if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
        return json.loads(raw)
def proxy(handler,route,data=None):
    parsed=urlsplit(route);suffix=parsed.path.removeprefix('/api/v1/kr260/')
    if suffix not in (GET_ROUTES if data is None else POST_ROUTES):handler.hub_reply({'error':'接口不存在'},404);return
    try:
        if suffix=='snapshot':suffix+='?frames='+('1' if parse_qs(parsed.query).get('frames',['0'])[0]=='1' else '0')
        result=fetch(suffix,data)
        handler.hub_reply(result)
    except urllib.error.HTTPError as e:
        try:result=json.loads(e.read(65536))
        except Exception:result={'error':'板端接口拒绝请求'}
        handler.hub_reply(result,e.code)
    except Exception:handler.hub_reply({'error':'KR260 监测暂不可达，请检查板端或监测隧道','state':'offline'},503)
