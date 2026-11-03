"""Exercise the real encoder shader with shared GLES contexts and GPU fences.

No Android Surface/MediaCodec is available here; that remains a device check.
"""
import ctypes as C
import re
from pathlib import Path

def verify_capture(gl,fn,egl,display,parent):
    ptr,i,u,f=C.c_void_p,C.c_int,C.c_uint,C.c_float
    surface=fn(egl,'eglGetCurrentSurface',ptr,i)(0x3059)
    config_id=i();assert fn(egl,'eglQueryContext',u,ptr,ptr,i,C.POINTER(i))(display,parent,0x3028,C.byref(config_id))
    config=ptr();count=i();attributes=(i*3)(0x3028,config_id.value,0x3038)
    assert fn(egl,'eglChooseConfig',u,ptr,C.POINTER(i),C.POINTER(ptr),i,C.POINTER(i))(display,attributes,C.byref(config),1,C.byref(count))
    consumer=fn(egl,'eglCreateContext',ptr,ptr,ptr,ptr,C.POINTER(i))(display,config,parent,(i*3)(0x3098,3,0x3038))
    parking=fn(egl,'eglCreatePbufferSurface',ptr,ptr,ptr,C.POINTER(i))(display,config,(i*5)(0x3057,320,0x3056,180,0x3038))
    assert consumer and parking
    switch=fn(egl,'eglMakeCurrent',u,ptr,ptr,ptr,ptr)
    source=(Path(__file__).resolve().parents[1]/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2/CaptureEgl.java').read_text(encoding='utf8')
    program=fn(gl,'glCreateProgram',u)()
    matches=re.findall(r'shader\(\s*GLES20.GL_(VERTEX|FRAGMENT)_SHADER,\s*"([^"]+)"',source)
    assert len(matches)==2
    for kind,text in matches:
        shader=fn(gl,'glCreateShader',u,u)(0x8B31 if kind=='VERTEX' else 0x8B30);data=text.encode();value=C.c_char_p(data);length=i(len(data))
        fn(gl,'glShaderSource',None,u,i,C.POINTER(C.c_char_p),C.POINTER(i))(shader,1,C.byref(value),C.byref(length));fn(gl,'glCompileShader',None,u)(shader);ok=i();fn(gl,'glGetShaderiv',None,u,u,C.POINTER(i))(shader,0x8B81,C.byref(ok));assert ok.value,(kind,text)
        fn(gl,'glAttachShader',None,u,u)(program,shader)
    fn(gl,'glBindAttribLocation',None,u,u,C.c_char_p)(program,0,b'position');fn(gl,'glBindAttribLocation',None,u,u,C.c_char_p)(program,1,b'texCoord');fn(gl,'glLinkProgram',None,u)(program)
    ok=i();fn(gl,'glGetProgramiv',None,u,u,C.POINTER(i))(program,0x8B82,C.byref(ok));assert ok.value
    def texture(w,h):
        texture=u();fbo=u();fn(gl,'glGenTextures',None,i,C.POINTER(u))(1,C.byref(texture));fn(gl,'glBindTexture',None,u,u)(0x0DE1,texture)
        fn(gl,'glTexImage2D',None,u,i,i,i,i,i,u,u,ptr)(0x0DE1,0,0x8C43,w,h,0,0x1908,0x1401,None)
        for key,val in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)]:fn(gl,'glTexParameteri',None,u,u,i)(0x0DE1,key,val)
        fn(gl,'glGenFramebuffers',None,i,C.POINTER(u))(1,C.byref(fbo));fn(gl,'glBindFramebuffer',None,u,u)(0x8D40,fbo);fn(gl,'glFramebufferTexture2D',None,u,u,u,u,i)(0x8D40,0x8CE0,0x0DE1,texture,0)
        assert fn(gl,'glCheckFramebufferStatus',u,u)(0x8D40)==0x8CD5
        return texture,fbo
    fn(gl,'glActiveTexture',None,u)(0x84C0)
    image,read_fbo=texture(128,128);slots=[texture(320,180) for _ in range(3)]
    assert switch(display,parking,parking,consumer)
    vao=u();vbo=u();fn(gl,'glGenVertexArrays',None,i,C.POINTER(u))(1,C.byref(vao));fn(gl,'glBindVertexArray',None,u)(vao)
    quad=[float(v.strip()) for v in re.search(r'float\[\]\s+quad\s*=\s*\{([^}]+)\}',source)[1].split(',')]
    vertices=(f*len(quad))(*quad);fn(gl,'glGenBuffers',None,i,C.POINTER(u))(1,C.byref(vbo));fn(gl,'glBindBuffer',None,u,u)(0x8892,vbo);fn(gl,'glBufferData',None,u,C.c_ssize_t,ptr,u)(0x8892,C.sizeof(vertices),vertices,0x88E4)
    for index,offset in [(0,0),(1,8)]:fn(gl,'glEnableVertexAttribArray',None,u)(index);fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(index,2,0x1406,0,16,ptr(offset))
    checks=0
    for frame in range(12):
        assert switch(display,surface,surface,parent)
        colors=[(128+frame,64,32,255),(33,144,63,255),(45,68,189,255),(207,170,88,255)]
        pixels=bytes(v for y in range(128) for x in range(128) for v in colors[(x>=64)+2*(y>=64)])
        fn(gl,'glActiveTexture',None,u)(0x84C0);fn(gl,'glBindTexture',None,u,u)(0x0DE1,image);data=C.create_string_buffer(pixels);fn(gl,'glTexSubImage2D',None,u,i,i,i,i,i,u,u,ptr)(0x0DE1,0,0,0,128,128,0x1908,0x1401,data)
        tex,draw_fbo=slots[frame%3];fn(gl,'glBindFramebuffer',None,u,u)(0x8CA8,read_fbo);fn(gl,'glBindFramebuffer',None,u,u)(0x8CA9,draw_fbo);fn(gl,'glDisable',None,u)(0x0C11)
        fn(gl,'glBlitFramebuffer',None,i,i,i,i,i,i,i,i,u,u)(16,16,112,112,0,0,320,180,0x4000,0x2601)
        fence=fn(gl,'glFenceSync',ptr,u,u)(0x9117,0);assert fence;fn(gl,'glFlush',None)()
        assert switch(display,parking,parking,consumer)
        fn(gl,'glWaitSync',None,ptr,u,C.c_uint64)(fence,0,0xFFFFFFFFFFFFFFFF);fn(gl,'glDeleteSync',None,ptr)(fence)
        fn(gl,'glBindFramebuffer',None,u,u)(0x8D40,0);fn(gl,'glViewport',None,i,i,i,i)(0,0,320,180);fn(gl,'glDisable',None,u)(0x0BE2);fn(gl,'glDisable',None,u)(0x0B71);fn(gl,'glUseProgram',None,u)(program);fn(gl,'glActiveTexture',None,u)(0x84C0);fn(gl,'glBindTexture',None,u,u)(0x0DE1,tex)
        location=fn(gl,'glGetUniformLocation',i,u,C.c_char_p)(program,b'image');fn(gl,'glUniform1i',None,i,i)(location,0);fn(gl,'glDrawArrays',None,u,i,i)(4,0,6)
        for k,(x,y) in enumerate([(40,30),(280,30),(40,150),(280,150)]):
            pixel=(C.c_ubyte*4)();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(x,y,1,1,0x1908,0x1401,pixel)
            assert max(abs(pixel[j]-colors[k][j]) for j in range(4))<=2,(frame,k,list(pixel),colors[k]);checks+=1
        fn(gl,'glFinish',None)();assert fn(gl,'glGetError',u)()==0
    assert switch(display,surface,surface,parent)
    fn(egl,'eglDestroySurface',u,ptr,ptr)(display,parking);fn(egl,'eglDestroyContext',u,ptr,ptr)(display,consumer)
    print(f'PASS: {checks} encoder-shader color/orientation checks across shared EGL contexts, GPU fences and three export slots; no MediaCodec/device simulation.')
