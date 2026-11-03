"""Compile the production GLES environment shaders off-device; no emulator/device is started."""
from pathlib import Path
import ctypes as C
import os
import re

root = Path(__file__).resolve().parents[1]
sdk = Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/emulator/lib64' / os.environ.get('TLZ_GL_BACKEND', 'gles_angle')
os.add_dll_directory(str(sdk))
egl = C.WinDLL(str(sdk / 'libEGL.dll'))
gl = C.WinDLL(str(sdk / 'libGLESv2.dll'))

def fn(lib, name, result, *args):
    f = getattr(lib, name)
    f.restype = result
    f.argtypes = list(args)
    return f

ptr, i, u, f = C.c_void_p, C.c_int, C.c_uint, C.c_float
display = fn(egl, 'eglGetDisplay', ptr, ptr)(None)
major, minor = i(), i()
assert fn(egl, 'eglInitialize', u, ptr, C.POINTER(i), C.POINTER(i))(display, C.byref(major), C.byref(minor))
attrs = (i * 13)(0x3033, 1, 0x3040, 0x40, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
config, count = ptr(), i()
assert fn(egl, 'eglChooseConfig', u, ptr, C.POINTER(i), C.POINTER(ptr), i, C.POINTER(i))(display, attrs, C.byref(config), 1, C.byref(count)) and count.value
surface_attrs = (i * 5)(0x3057, 1600, 0x3056, 1000, 0x3038)
surface = fn(egl, 'eglCreatePbufferSurface', ptr, ptr, ptr, C.POINTER(i))(display, config, surface_attrs)
ctx_attrs = (i * 3)(0x3098, 3, 0x3038)
ctx = fn(egl, 'eglCreateContext', ptr, ptr, ptr, ptr, C.POINTER(i))(display, config, None, ctx_attrs)
assert surface and ctx
assert fn(egl, 'eglMakeCurrent', u, ptr, ptr, ptr, ptr)(display, surface, surface, ctx)
create = fn(gl, 'glCreateShader', u, u)
source = fn(gl, 'glShaderSource', None, u, i, C.POINTER(C.c_char_p), C.POINTER(i))
compile_shader = fn(gl, 'glCompileShader', None, u)
get_shader = fn(gl, 'glGetShaderiv', None, u, u, C.POINTER(i))
info = fn(gl, 'glGetShaderInfoLog', None, u, i, C.POINTER(i), C.c_char_p)
text = (root / 'vr/src/main/cpp/terminal_v2.cpp').read_text(encoding='utf-8')
shaders = []
for name, kind in [('skyVertex', 0x8B31), ('skyFragment', 0x8B30)]:
    code = re.search(r'const char\* ' + name + r'\s*=\s*R"\((.*?)\)";', text, re.S)[1].encode()
    shader = create(kind)
    data, length = C.c_char_p(code), i(len(code))
    source(shader, 1, C.byref(data), C.byref(length))
    compile_shader(shader)
    ok = i()
    get_shader(shader, 0x8B81, C.byref(ok))
    log = C.create_string_buffer(8192)
    info(shader, len(log), None, log)
    assert ok.value, name + ': ' + log.value.decode()
    shaders.append(shader)
program = fn(gl, 'glCreateProgram', u)()
attach = fn(gl, 'glAttachShader', None, u, u)
for shader in shaders:
    attach(program, shader)
fn(gl, 'glLinkProgram', None, u)(program)
ok = i()
fn(gl, 'glGetProgramiv', None, u, u, C.POINTER(i))(program, 0x8B82, C.byref(ok))
assert ok.value, 'Environment shader link failed'
fn(gl, 'glUseProgram', None, u)(program)
uniform = fn(gl, 'glGetUniformLocation', i, u, C.c_char_p)
camera = (f * 16)(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1.6, 0, 1)
fn(gl, 'glUniformMatrix4fv', None, i, i, u, C.POINTER(f))(uniform(program, b'camera'), 1, 0, camera)
fn(gl, 'glUniform4f', None, i, f, f, f, f)(uniform(program, b'fov'), -1.2, 1.2, -.75, .75)
fn(gl, 'glUniform1f', None, i, f)(uniform(program, b'floorY'), 0)
vertices = (f * 18)(-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1, 1, 0)
buffer = u()
fn(gl, 'glGenBuffers', None, i, C.POINTER(u))(1, C.byref(buffer))
fn(gl, 'glBindBuffer', None, u, u)(0x8892, buffer)
fn(gl, 'glBufferData', None, u, C.c_ssize_t, ptr, u)(0x8892, C.sizeof(vertices), vertices, 0x88E4)
fn(gl, 'glVertexAttribPointer', None, u, i, u, u, i, ptr)(0, 3, 0x1406, 0, 12, None)
fn(gl, 'glEnableVertexAttribArray', None, u)(0)
fn(gl, 'glViewport', None, i, i, i, i)(0, 0, 1600, 1000)
fn(gl, 'glDrawArrays', None, u, i, i)(4, 0, 6)
pixels = (C.c_ubyte * (1600 * 1000 * 4))()
fn(gl, 'glReadPixels', None, i, i, i, i, u, u, ptr)(0, 0, 1600, 1000, 0x1908, 0x1401, pixels)
assert fn(gl, 'glGetError', u)() == 0
from PIL import Image
out = root / 'vr/build/ui-preview'
out.mkdir(parents=True, exist_ok=True)
image = Image.frombytes('RGBA', (1600, 1000), bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
image.save(out / 'environment.png')
assert image.getpixel((800, 100)) != image.getpixel((800, 900)), 'Sky and ground must differ'
from render_vr_glass_offscreen import verify_and_render
verify_and_render(gl, fn, text, out, program, egl, display, ctx)
from render_view_capture_offscreen import verify_capture
verify_capture(gl,fn,egl,display,ctx)
from render_controller_offscreen import verify_controller
verify_controller(gl,fn,text,out)
fn(egl, 'eglMakeCurrent', u, ptr, ptr, ptr, ptr)(display, None, None, None)
fn(egl, 'eglDestroyContext', u, ptr, ptr)(display, ctx)
fn(egl, 'eglDestroySurface', u, ptr, ptr)(display, surface)
fn(egl, 'eglTerminate', u, ptr)(display)
print('PASS: production GLES sky/ground shaders compiled, linked and rendered off-device; no device/emulator installation.')
