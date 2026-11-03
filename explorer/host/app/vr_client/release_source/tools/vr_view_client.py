"""VR view service client (stdlib only; preview additionally needs ffplay).

Example: python vr_view_client.py --host 192.168.1.50 status
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import urllib.request

def exact(stream,size):
    chunks=[]
    while size:
        data=stream.read(size)
        if not data:raise EOFError('VR stream ended')
        chunks.append(data);size-=len(data)
    return b''.join(chunks)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True,help='Quest Wi-Fi IP, not AIPC IP')
    p.add_argument('--port',type=int,default=8095)
    p.add_argument('--token',default='1')
    p.add_argument('action',choices=['status','config','record-start','record-stop','live-start','live-stop','files','download','preview','watch'])
    p.add_argument('--config-file',type=Path,help='JSON config file for config action; omitted means read current config')
    p.add_argument('--name',help='finalized recording filename for download')
    p.add_argument('--out',type=Path,help='download destination')
    p.add_argument('--ffplay',default='ffplay')
    a=p.parse_args()
    if not 1<=a.port<=65535:p.error('invalid port')
    # Disable environment HTTP proxies: the target is the explicitly selected LAN headset.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    root=f'http://{a.host}:{a.port}/v1/view'
    def request(path,method='GET',data=None,timeout=8):
        body=json.dumps(data).encode('utf8') if data is not None else None
        headers={'Authorization':'Bearer '+a.token}
        if body is not None:headers['Content-Type']='application/json'
        return opener.open(urllib.request.Request(root+path,data=body,headers=headers,method=method),timeout=timeout)
    def rpc(path,method='GET',data=None):
        with request(path,method,data) as response:return json.load(response)
    paths={'record-start':'/record/start','record-stop':'/record/stop','live-start':'/live/start','live-stop':'/live/stop'}
    if a.action in paths:print(json.dumps(rpc(paths[a.action],'POST',{}),ensure_ascii=False,indent=2));return
    if a.action=='config':
        config=json.loads(a.config_file.read_text(encoding='utf-8-sig')) if a.config_file else None
        print(json.dumps(rpc('/config','PUT' if config is not None else 'GET',config),ensure_ascii=False,indent=2));return
    if a.action in ('status','files'):
        print(json.dumps(rpc('/status' if a.action=='status' else '/recordings'),ensure_ascii=False,indent=2));return
    if a.action=='download':
        if not a.name or Path(a.name).name!=a.name:p.error('download requires a plain --name from files')
        target=a.out or Path(a.name)
        # Exclusive creation prevents silently overwriting a previous recording.
        with request('/recordings/'+a.name,timeout=15) as response,target.open('xb') as output:shutil.copyfileobj(response,output,128*1024)
        print(target.resolve());return
    player=shutil.which(a.ffplay)
    if not player:p.error('ffplay not found; pass --ffplay with its executable path')
    if a.action=='preview':rpc('/live/start','POST',{})
    elif not rpc('/status').get('streaming'):raise RuntimeError('Live is off; use an explicit live-start command to start it')
    print('Live receiver connected. Ctrl+C closes this receiver; use live-stop or the VR button to stop the shared stream.',file=sys.stderr)
    try:
        while True:
            process=None
            try:
                with request('/live.tlzv',timeout=5) as stream:
                    process=subprocess.Popen([player,'-fflags','nobuffer','-flags','low_delay','-framedrop','-f','h264','-i','pipe:0'],stdin=subprocess.PIPE)
                    while process.poll() is None:
                        magic,version,flags,size,seq,pts,width,height,length,reserved=struct.unpack('>4sBBHIQHHII',exact(stream,32))
                        if magic!=b'TLZV' or version!=1 or size!=32 or reserved or flags&~1 or length<1 or length>8*1024*1024 or not(0<width<=1920 and 0<height<=1920):raise ValueError('invalid TLZV frame')
                        process.stdin.write(exact(stream,length));process.stdin.flush()
                    return
            except BrokenPipeError:
                return
            except (EOFError,OSError) as e:
                print(f'Receiver reconnect: {e}',file=sys.stderr)
                status=rpc('/status')
                if not status.get('streaming'):return
                time.sleep(.5)
            finally:
                if process is not None:
                    if process.stdin:
                        try:process.stdin.close()
                        except OSError:pass
                    if process.poll() is None:
                        process.terminate()
                        try:process.wait(timeout=2)
                        except subprocess.TimeoutExpired:process.kill();process.wait()
    except KeyboardInterrupt:pass

if __name__=='__main__':
    try:main()
    except Exception as error:print(f'Error: {error}',file=sys.stderr);sys.exit(1)
