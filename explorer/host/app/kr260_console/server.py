import json, os, shutil, time, zipfile, io, uuid, threading
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from hub_api import HubMixin
ROOT = Path(__file__).resolve().parent
DOCS = ROOT / 'public/docs'
META = ROOT / 'categories.json'
LOCK = threading.RLock()
MAX_UPLOAD = 64 * 1024 * 1024
ALLOWED = {'.md','.png','.jpg','.jpeg','.gif','.webp','.svg','.pdf','.txt','.csv','.json','.woff','.woff2'}
def metadata():
    data = json.loads(META.read_text()) if META.exists() else {}
    if data.get('version') != 2:
        # Migrate existing document labels, including the original CAN default.
        mapping = dict(data)
        for p in DOCS.rglob('*.md'):
            key = p.relative_to(DOCS).as_posix()
            mapping.setdefault(key, 'CAN 硬件' if key.startswith('CAN_VALIDATION') else '未分类')
        names = sorted(set(mapping.values()) - {'未分类','全部文档'})
        data = {'version':2,'categories':['未分类']+names,'documents':mapping}
        save_meta(data)
    return data
def save_meta(data):
    temp = META.with_suffix('.tmp'); temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8'); temp.replace(META)
def doc_path(value):
    p = (DOCS / value).resolve()
    if not p.is_relative_to(DOCS.resolve()) or p.suffix.lower() != '.md' or not p.is_file():
        raise ValueError('文档不存在')
    return p
class Handler(HubMixin, SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)
    def reply(self, data, code=200):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(payload)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        if urlsplit(self.path).path.startswith('/docs/'):
            self.send_header('Content-Security-Policy','sandbox; default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'')
        super().end_headers()
    def do_GET(self):
        if self.hub_get(): return
        route = urlsplit(self.path).path
        if route == '/api/categories':
            with LOCK: self.reply(metadata()['categories'])
        elif route == '/api/docs':
            with LOCK:
                meta = metadata(); docs = []
                for p in sorted(DOCS.rglob('*')):
                    if p.suffix.lower() != '.md' or not p.is_file() or p.is_symlink(): continue
                    title = p.stem
                    for line in p.read_text(encoding='utf-8-sig', errors='replace').splitlines():
                        if line.startswith('# '): title = line[2:].strip(); break
                    key = p.relative_to(DOCS).as_posix()
                    docs.append({'path':key,'title':title,'category':meta['documents'].get(key,'未分类'),'size':p.stat().st_size,'modified':p.stat().st_mtime})
            self.reply(docs)
        else: super().do_GET()
    def do_POST(self):
        if self.hub_post(): return
        try:
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'): return self.reply({'error':'跨站请求被拒绝'},403)
            if self.headers.get('X-Document-Client') != 'library': return self.reply({'error':'无效请求'},403)
            size = int(self.headers.get('Content-Length','0'))
            if size <= 0 or size > MAX_UPLOAD: return self.reply({'error':'文件上限为 64 MB'},413)
            body = self.rfile.read(size)
            with LOCK:
                route = urlsplit(self.path).path
                if route == '/api/upload': self.import_zip(body)
                elif route == '/api/category':
                    data = json.loads(body); p = doc_path(data['path']); category = str(data['category']).strip()[:60] or '未分类'
                    meta = metadata()
                    if category not in meta['categories']: raise ValueError('分类不存在，请先新增分类')
                    meta['documents'][p.relative_to(DOCS).as_posix()] = category; save_meta(meta); self.reply({'ok':True})
                elif route == '/api/categories':
                    data = json.loads(body); meta = metadata(); operation = data['action']
                    name = str(data.get('name','')).strip()
                    if operation in ('create','rename'):
                        if not name or len(name)>60 or name=='全部文档': raise ValueError('请输入有效分类名称（1–60字）')
                        if name in meta['categories']: raise ValueError('分类名称已存在')
                    if operation == 'create': meta['categories'].append(name)
                    elif operation in ('rename','delete'):
                        old = data['old']
                        if old=='未分类': raise ValueError('默认分类不能编辑或删除')
                        if old not in meta['categories']: raise ValueError('分类不存在')
                        if operation=='rename': meta['categories'][meta['categories'].index(old)] = name
                        else: meta['categories'].remove(old)
                        meta['documents'] = {key:(name if operation=='rename' else '未分类') if value==old else value for key,value in meta['documents'].items()}
                    else: raise ValueError('无效操作')
                    save_meta(meta); self.reply({'ok':True})
                elif route == '/api/delete':
                    data = json.loads(body); p = doc_path(data['path']); key = p.relative_to(DOCS).as_posix()
                    trash = ROOT / 'trash' / (time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]) / key
                    trash.parent.mkdir(parents=True); shutil.move(str(p),str(trash)); self.reply({'ok':True})
                else: self.reply({'error':'接口不存在'},404)
        except (ValueError, KeyError, zipfile.BadZipFile, UnicodeError) as e: self.reply({'error':str(e)},400)
        except Exception: self.reply({'error':'操作失败，请检查服务日志'},500)
    def import_zip(self, body):
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            entries = []; total = 0
            if len(z.infolist()) > 3000: raise ValueError('ZIP 文件数量超过 3000')
            for info in z.infolist():
                name = info.filename.replace('\\','/'); parts = PurePosixPath(name)
                if parts.is_absolute() or '..' in parts.parts or ':' in name: raise ValueError('ZIP 含不安全路径')
                if (info.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('ZIP 不允许符号链接')
                if info.is_dir() or '__MACOSX' in parts.parts or any(s.startswith('.') for s in parts.parts): continue
                if parts.suffix.lower() not in ALLOWED: continue
                total += info.file_size
                if total > 256 * 1024 * 1024: raise ValueError('ZIP 解压内容超过 256 MB')
                entries.append((info, parts))
            if not any(p.suffix.lower()=='.md' for _,p in entries): raise ValueError('压缩包中没有 Markdown 文档')
            package = 'imports/'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
            stage = ROOT / ('upload-'+uuid.uuid4().hex)
            try:
                stage.mkdir()
                for info,p in entries:
                    target = stage.joinpath(*p.parts); target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(info) as src, target.open('wb') as dst: shutil.copyfileobj(src,dst)
                target = DOCS / package; target.parent.mkdir(parents=True,exist_ok=True); stage.rename(target)
            finally:
                if stage.exists(): shutil.rmtree(stage)
            self.reply({'ok':True,'documents':sum(p.suffix.lower()=='.md' for _,p in entries),'resources':sum(p.suffix.lower()!='.md' for _,p in entries),'package':package})
    def list_directory(self, path): self.send_error(403,'Directory listing disabled')
DOCS.mkdir(parents=True,exist_ok=True)
ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8091'))),Handler).serve_forever()
