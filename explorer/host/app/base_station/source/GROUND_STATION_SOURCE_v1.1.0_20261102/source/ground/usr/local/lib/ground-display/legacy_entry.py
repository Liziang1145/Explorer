"""Compatibility redirect for bookmarks to the removed hotspot administration UI."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
TARGET='http://192.168.137.131:8080/'
class Entry(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(302);self.send_header('Location',TARGET);self.send_header('Cache-Control','no-store, max-age=0');self.send_header('Content-Length','0');self.end_headers()
 do_HEAD=do_GET
 def do_POST(self):
  data=json.dumps({'error':'旧基站后台已停用，请刷新页面进入新后台后登录。','url':TARGET},ensure_ascii=False).encode()
  self.send_response(410);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.send_header('Connection','close');self.end_headers();self.wfile.write(data);self.close_connection=True
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8085),Entry).serve_forever()
