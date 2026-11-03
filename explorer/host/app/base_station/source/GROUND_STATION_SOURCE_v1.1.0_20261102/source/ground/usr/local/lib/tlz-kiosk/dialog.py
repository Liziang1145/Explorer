"""Native password dialog. No password passes through the web page."""
import json,socket,threading
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
dialog=Gtk.Dialog(title='退出预览',modal=True);dialog.set_default_size(340,140);dialog.set_resizable(False);dialog.add_button('取消',Gtk.ResponseType.CANCEL);dialog.add_button('验证并进入桌面',Gtk.ResponseType.OK);dialog.set_default_response(Gtk.ResponseType.OK)
box=dialog.get_content_area();box.set_border_width(22);box.set_spacing(12);box.add(Gtk.Label(label='apex 密码',xalign=0));entry=Gtk.Entry();entry.set_visibility(False);entry.set_input_purpose(Gtk.InputPurpose.PASSWORD);entry.set_activates_default(True);box.add(entry);message=Gtk.Label(xalign=0);box.add(message)
def response(d,code):
 if code!=Gtk.ResponseType.OK:d.destroy();Gtk.main_quit();return
 password=entry.get_text();entry.set_text('');d.set_response_sensitive(Gtk.ResponseType.OK,False);message.set_text('正在验证…')
 def worker():
  ok=False
  try:
   with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(10);s.connect('/run/tlz-kiosk/auth.sock');s.sendall(json.dumps({'action':'unlock','password':password}).encode()+b'\n');ok=json.loads(s.recv(1024)).get('ok',False)
  except (OSError,ValueError):pass
  GLib.idle_add(done,ok)
 threading.Thread(target=worker,daemon=True).start()
def done(ok):
 if ok:dialog.destroy();Gtk.main_quit()
 else:message.set_text('密码错误或验证暂不可用');dialog.set_response_sensitive(Gtk.ResponseType.OK,True);entry.grab_focus()
 return False
dialog.connect('response',response);dialog.show_all();entry.grab_focus();Gtk.main()
