"""Render the production controller material with loaded/fallback geometry using real GLES."""
import ctypes as C
import math, re
from pathlib import Path
from PIL import Image

def verify_controller(gl,fn,text,out):
    u,i,f,ptr=C.c_uint,C.c_int,C.c_float,C.c_void_p
    program=fn(gl,'glCreateProgram',u)()
    for name,kind in [('controllerVertex',0x8B31),('controllerFragment',0x8B30)]:
        code=re.search(r'const char\* '+name+r'\s*=\s*R"\((.*?)\)";',text,re.S)[1].encode()
        shader=fn(gl,'glCreateShader',u,u)(kind);value=C.c_char_p(code);size=i(len(code))
        fn(gl,'glShaderSource',None,u,i,C.POINTER(C.c_char_p),C.POINTER(i))(shader,1,C.byref(value),C.byref(size))
        fn(gl,'glCompileShader',None,u)(shader);ok=i();fn(gl,'glGetShaderiv',None,u,u,C.POINTER(i))(shader,0x8B81,C.byref(ok))
        log=C.create_string_buffer(8192);fn(gl,'glGetShaderInfoLog',None,u,i,C.POINTER(i),C.c_char_p)(shader,8192,None,log)
        assert ok.value,(name,log.value.decode())
        fn(gl,'glAttachShader',None,u,u)(program,shader)
    fn(gl,'glLinkProgram',None,u)(program);ok=i();fn(gl,'glGetProgramiv',None,u,u,C.POINTER(i))(program,0x8B82,C.byref(ok));assert ok.value
    width,height=1200,700
    color,depth,frame=u(),u(),u()
    fn(gl,'glGenTextures',None,i,C.POINTER(u))(1,C.byref(color));fn(gl,'glBindTexture',None,u,u)(0x0DE1,color)
    fn(gl,'glTexImage2D',None,u,i,i,i,i,i,u,u,ptr)(0x0DE1,0,0x8058,width,height,0,0x1908,0x1401,None)
    fn(gl,'glGenRenderbuffers',None,i,C.POINTER(u))(1,C.byref(depth));fn(gl,'glBindRenderbuffer',None,u,u)(0x8D41,depth)
    fn(gl,'glRenderbufferStorage',None,u,u,i,i)(0x8D41,0x81A6,width,height)
    fn(gl,'glGenFramebuffers',None,i,C.POINTER(u))(1,C.byref(frame));fn(gl,'glBindFramebuffer',None,u,u)(0x8D40,frame)
    fn(gl,'glFramebufferTexture2D',None,u,u,u,u,i)(0x8D40,0x8CE0,0x0DE1,color,0)
    fn(gl,'glFramebufferRenderbuffer',None,u,u,u,u)(0x8D40,0x8D00,0x8D41,depth)
    assert fn(gl,'glCheckFramebufferStatus',u,u)(0x8D40)==0x8CD5
    fn(gl,'glViewport',None,i,i,i,i)(0,0,width,height)
    fn(gl,'glDisable',None,u)(0x0BE2);fn(gl,'glDisable',None,u)(0x0B44)
    fn(gl,'glEnable',None,u)(0x0B71);fn(gl,'glDepthMask',None,u)(1)
    fn(gl,'glClearColor',None,f,f,f,f)(.76,.81,.84,1);fn(gl,'glClear',None,u)(0x4000|0x100)
    fn(gl,'glUseProgram',None,u)(program)
    uniform=fn(gl,'glGetUniformLocation',i,u,C.c_char_p)
    mat=fn(gl,'glUniformMatrix4fv',None,i,i,u,C.POINTER(f))
    vbo=u();fn(gl,'glGenBuffers',None,i,C.POINTER(u))(1,C.byref(vbo));fn(gl,'glBindBuffer',None,u,u)(0x8892,vbo)
    def mul(a,b):return [sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]
    y=.65;x=-.38;cy,sy,cx,sx=math.cos(y),math.sin(y),math.cos(x),math.sin(x)
    ry=[cy,0,-sy,0,0,1,0,0,sy,0,cy,0,0,0,0,1]
    rx=[1,0,0,0,0,cx,sx,0,0,-sx,cx,0,0,0,0,1]
    scale=1/math.tan(math.radians(48)/2)
    projection=[scale/(width/height),0,0,0,0,scale,0,0,0,0,-1.020202,-1,0,0,-.020202,0]
    folder=Path(__file__).resolve().parents[1]/'vr/build/controller-model-test'
    files=[folder/'controller-real.bin',folder/'controller-fallback.bin']
    for side,file in enumerate(files):
        if not file.exists():continue
        raw=file.read_bytes();data=C.create_string_buffer(raw)
        fn(gl,'glBufferData',None,u,C.c_ssize_t,ptr,u)(0x8892,len(raw),data,0x88E4)
        for k in range(3):
            fn(gl,'glEnableVertexAttribArray',None,u)(k)
            fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(k,3,0x1406,0,36,ptr(k*12))
        view=mul(ry,rx);view[12]=-.09 if side==0 else .09;view[14]=-.31
        mat(uniform(program,b'modelView'),1,0,(f*16)(*view));mat(uniform(program,b'mvp'),1,0,(f*16)(*mul(projection,view)))
        fn(gl,'glUniform3f',None,i,f,f,f)(uniform(program,b'accent'),.08,.65,.83)
        fn(gl,'glDrawArrays',None,u,i,i)(4,0,len(raw)//36)
    pixels=(C.c_ubyte*(width*height*4))();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(0,0,width,height,0x1908,0x1401,pixels)
    assert fn(gl,'glGetError',u)()==0
    image=Image.frombytes('RGBA',(width,height),bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    image.save(out/'controller-material.png')
    background=image.getpixel((0,0))
    for side,(a,b) in enumerate([(0,width//2),(width//2,width)]):
        colors={image.getpixel((x,y)) for x in range(a,b,5) for y in range(0,height,5)}
        assert len(colors-{background})>(40 if side==0 else 3),'Material must render geometry with visible shading'
        assert max(max(c[:3]) for c in colors)-min(min(c[:3]) for c in colors)>40
    fn(gl,'glDisableVertexAttribArray',None,u)(2);fn(gl,'glDisable',None,u)(0x0B71)
    fn(gl,'glBindFramebuffer',None,u,u)(0x8D40,0)
    fn(gl,'glDeleteBuffers',None,i,C.POINTER(u))(1,C.byref(vbo))
    fn(gl,'glDeleteFramebuffers',None,i,C.POINTER(u))(1,C.byref(frame))
    fn(gl,'glDeleteTextures',None,i,C.POINTER(u))(1,C.byref(color))
    fn(gl,'glDeleteRenderbuffers',None,i,C.POINTER(u))(1,C.byref(depth))
    fn(gl,'glDeleteProgram',None,u)(program)
    print('PASS: production controller GLES material, real GLB + fallback, opaque shading and depth; off-device preview exported')
