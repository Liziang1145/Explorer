"""Production GLSL material/blur verification in an existing off-screen GLES context."""
import ast
import ctypes as C
import re
from pathlib import Path
from PIL import Image

def verify_and_render(gl, fn, source, out, sky_program, egl, display, context):
    ptr,i,u,f=C.c_void_p,C.c_int,C.c_uint,C.c_float
    def code(name):
        raw=re.search(r'const char\* '+name+r'\s*=\s*R"\((.*?)\)";',source,re.S)
        if raw:return raw[1].encode()
        value=re.search(r'const char\* '+name+r'\s*=(.*?);\s*\nconst char\*',source,re.S)[1]
        return ''.join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"',value)).encode()
    def compile_program(vertex,fragment):
        program=fn(gl,'glCreateProgram',u)()
        for name,kind in [(vertex,0x8B31),(fragment,0x8B30)]:
            shader=fn(gl,'glCreateShader',u,u)(kind);data=code(name);value=C.c_char_p(data);length=i(len(data))
            fn(gl,'glShaderSource',None,u,i,C.POINTER(C.c_char_p),C.POINTER(i))(shader,1,C.byref(value),C.byref(length))
            fn(gl,'glCompileShader',None,u)(shader);ok=i()
            fn(gl,'glGetShaderiv',None,u,u,C.POINTER(i))(shader,0x8B81,C.byref(ok))
            log=C.create_string_buffer(8192);fn(gl,'glGetShaderInfoLog',None,u,i,C.POINTER(i),C.c_char_p)(shader,8192,None,log)
            assert ok.value,(name,log.value.decode())
            fn(gl,'glAttachShader',None,u,u)(program,shader)
        fn(gl,'glLinkProgram',None,u)(program);ok=i();fn(gl,'glGetProgramiv',None,u,u,C.POINTER(i))(program,0x8B82,C.byref(ok));assert ok.value,fragment
        return program
    blur=compile_program('texVertex','blurFragment');glass=compile_program('texVertex','hudFragment')
    vehicle_program=compile_program('colorVertex','colorFragment')
    fn(gl,'glActiveTexture',None,u)(0x84C0)
    uniform=fn(gl,'glGetUniformLocation',i,u,C.c_char_p)
    use=fn(gl,'glUseProgram',None,u)
    bind_tex=fn(gl,'glBindTexture',None,u,u)
    bind_fbo=fn(gl,'glBindFramebuffer',None,u,u)
    viewport=fn(gl,'glViewport',None,i,i,i,i)
    draw=fn(gl,'glDrawArrays',None,u,i,i)
    u1=fn(gl,'glUniform1i',None,i,i);u2=fn(gl,'glUniform2f',None,i,f,f)
    matrix=fn(gl,'glUniformMatrix4fv',None,i,i,u,C.POINTER(f))
    ident=[1.,0,0,0,0,1.,0,0,0,0,1.,0,0,0,0,1.]
    def mat(program,name,value):matrix(uniform(program,name),1,0,(f*16)(*value))
    def texture(width,height,pixels=None):
        value=u();fn(gl,'glGenTextures',None,i,C.POINTER(u))(1,C.byref(value));bind_tex(0x0DE1,value)
        raw=C.create_string_buffer(pixels) if pixels else None
        fn(gl,'glTexImage2D',None,u,i,i,i,i,i,u,u,ptr)(0x0DE1,0,0x1908,width,height,0,0x1908,0x1401,raw)
        for key,val in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)]:fn(gl,'glTexParameteri',None,u,u,i)(0x0DE1,key,val)
        return value
    def framebuffer(tex):
        value=u();fn(gl,'glGenFramebuffers',None,i,C.POINTER(u))(1,C.byref(value));bind_fbo(0x8D40,value)
        fn(gl,'glFramebufferTexture2D',None,u,u,u,u,i)(0x8D40,0x8CE0,0x0DE1,tex,0)
        assert fn(gl,'glCheckFramebufferStatus',u,u)(0x8D40)==0x8CD5
        return value
    verts=(f*30)(-1,-1,0,0,0,1,-1,0,1,0,1,1,0,1,1,-1,-1,0,0,0,1,1,0,1,1,-1,1,0,0,1)
    vbo=u();fn(gl,'glGenBuffers',None,i,C.POINTER(u))(1,C.byref(vbo));fn(gl,'glBindBuffer',None,u,u)(0x8892,vbo)
    fn(gl,'glBufferData',None,u,C.c_ssize_t,ptr,u)(0x8892,C.sizeof(verts),verts,0x88E4)
    fn(gl,'glEnableVertexAttribArray',None,u)(0);fn(gl,'glEnableVertexAttribArray',None,u)(1)
    fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(0,3,0x1406,0,20,None)
    fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(1,2,0x1406,0,20,ptr(12))
    def quad():
        fn(gl,'glBindBuffer',None,u,u)(0x8892,vbo)
        fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(0,3,0x1406,0,20,None)
        fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(1,2,0x1406,0,20,ptr(12))
    car_file=Path(__file__).resolve().parents[1]/'vr/build/view-math-test/vehicle-lines.bin'
    car_data=car_file.read_bytes();car_vbo=u()
    fn(gl,'glGenBuffers',None,i,C.POINTER(u))(1,C.byref(car_vbo))
    fn(gl,'glBindBuffer',None,u,u)(0x8892,car_vbo)
    raw_car=C.create_string_buffer(car_data)
    fn(gl,'glBufferData',None,u,C.c_ssize_t,ptr,u)(0x8892,len(car_data),raw_car,0x88E4)
    quad()
    def car():
        fn(gl,'glDisable',None,u)(0x0BE2)
        fn(gl,'glBindBuffer',None,u,u)(0x8892,car_vbo)
        fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(0,3,0x1406,0,28,None)
        fn(gl,'glVertexAttribPointer',None,u,i,u,u,i,ptr)(1,4,0x1406,0,28,ptr(12))
        use(vehicle_program)
        projection=[1/1.2,0,0,0,0,1/.75,0,0,0,0,-500.05/499.95,-1,0,0,-50/499.95,0]
        view=ident.copy();view[13]=-1.6;view[14]=0
        mvp=[sum(projection[k*4+r]*view[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]
        mat(vehicle_program,b'mvp',mvp);draw(1,0,len(car_data)//28)
        quad()
    tex=[texture(400,250),texture(400,250)];fb=[framebuffer(t) for t in tex]
    bind_fbo(0x8D40,0)
    def snapshot_blur():
        fn(gl,'glDisable',None,u)(0x0BE2)
        bind_fbo(0x8CA8,0);bind_fbo(0x8CA9,fb[0])
        fn(gl,'glBlitFramebuffer',None,i,i,i,i,i,i,i,i,u,u)(0,0,1600,1000,0,0,400,250,0x4000,0x2601)
        viewport(0,0,400,250);use(blur);mat(blur,b'mvp',ident);mat(blur,b'uvMatrix',ident);u1(uniform(blur,b'image'),0)
        for axis in range(2):
            bind_fbo(0x8D40,fb[1-axis]);fn(gl,'glActiveTexture',None,u)(0x84C0);bind_tex(0x0DE1,tex[axis])
            u2(uniform(blur,b'direction'),1.5/400 if axis==0 else 0,1.5/250 if axis==1 else 0);draw(4,0,6)
        bind_fbo(0x8D40,0);viewport(0,0,1600,1000)
    # Sharp checkerboard test makes the Gaussian blur measurable rather than relying on appearance.
    checker=bytes(v for y in range(250) for x in range(400) for v in ([255,255,255,255] if (x+y)%2 else [0,0,0,255]))
    test=texture(400,250,checker);use(blur);mat(blur,b'mvp',ident);mat(blur,b'uvMatrix',ident);u1(uniform(blur,b'image'),0)
    bind_fbo(0x8D40,fb[1]);viewport(0,0,400,250);bind_tex(0x0DE1,test);u2(uniform(blur,b'direction'),1.5/400,0);draw(4,0,6)
    buf=(C.c_ubyte*(400*250*4))();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(0,0,400,250,0x1908,0x1401,buf)
    values=[buf[(y*400+x)*4] for y in range(30,220) for x in range(30,370)]
    assert max(values)-min(values)<100,'Gaussian pass must reduce high-frequency contrast'
    def load_png(path):
        image=Image.open(path).convert('RGBA');pixels=bytearray(image.tobytes())
        for k in range(0,len(pixels),4):
            alpha=pixels[k+3]
            for j in range(3):pixels[k+j]=(pixels[k+j]*alpha+127)//255
        return texture(*image.size,bytes(pixels))
    def hud(t,sx,sy,cy):
        use(glass);projection=ident.copy();projection[0]=sx;projection[5]=sy;projection[13]=cy;mat(glass,b'mvp',projection)
        flip=ident.copy();flip[5]=-1;flip[13]=1;mat(glass,b'uvMatrix',flip)
        fn(gl,'glActiveTexture',None,u)(0x84C1);bind_tex(0x0DE1,tex[0]);u1(uniform(glass,b'backdrop'),1)
        fn(gl,'glActiveTexture',None,u)(0x84C0);bind_tex(0x0DE1,t);u1(uniform(glass,b'image'),0);u2(uniform(glass,b'screenSize'),1600,1000)
        fn(gl,'glEnable',None,u)(0x0BE2);fn(gl,'glBlendFunc',None,u,u)(1,0x0303);draw(4,0,6)
    # Verify the native plate mask using production GLSL, including transparent corners.
    plate=texture(1,1,bytes([102,110,118,128]))
    bind_fbo(0x8D40,0);viewport(0,0,1600,1000)
    fn(gl,'glClearColor',None,f,f,f,f)(0,0,0,0);fn(gl,'glClear',None,u)(0x4000)
    hud(plate,1,1,0);use(glass);u2(uniform(glass,b'plateSize'),1,.6)
    fn(gl,'glDisable',None,u)(0x0BE2);draw(4,0,6)
    mask=(C.c_ubyte*(1600*1000*4))();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(0,0,1600,1000,0x1908,0x1401,mask)
    assert mask[3]==0 and mask[(500*1600+800)*4+3]>200,'Rounded plate corners and opaque centre'
    u2(uniform(glass,b'plateSize'),0,0)
    # Exercise a real EGLImage-backed external texture, rather than a 2D video stand-in.
    external_program=compile_program('texVertex','videoFragment')
    resolved_program=compile_program('texVertex','resolvedVideoFragment')
    address=fn(egl,'eglGetProcAddress',ptr,C.c_char_p)
    create_image=C.WINFUNCTYPE(ptr,ptr,ptr,u,ptr,C.POINTER(i))(address(b'eglCreateImageKHR'))
    destroy_image=C.WINFUNCTYPE(u,ptr,ptr)(address(b'eglDestroyImageKHR'))
    import_image=C.WINFUNCTYPE(None,u,ptr)(address(b'glEGLImageTargetTexture2DOES'))
    fn(gl,'glActiveTexture',None,u)(0x84C0)
    slots=[]
    for stream in range(2):
        rgba=texture(64,64);resolved=texture(64,64);resolved_fb=framebuffer(resolved)
        external=u();fn(gl,'glGenTextures',None,i,C.POINTER(u))(1,C.byref(external))
        slots.append((rgba,resolved,resolved_fb,external))
    ui_pixels=bytes([31,87,143,255])*64*64;ui_texture=texture(64,64,ui_pixels)
    def plain(program,t,target,unit):
        use(program);mat(program,b'mvp',ident);mat(program,b'uvMatrix',ident)
        fn(gl,'glActiveTexture',None,u)(0x84C0+unit);bind_tex(target,t)
        u1(uniform(program,b'image'),unit);draw(4,0,6)
    for frame in range(24):
        colors=[]
        for stream,(rgba,resolved,resolved_fb,external) in enumerate(slots):
            color=([225,17,192,255] if (frame+stream)%2 else [11,213,53,255]);colors.append(color)
            fn(gl,'glActiveTexture',None,u)(0x84C0);bind_tex(0x0DE1,rgba)
            raw=C.create_string_buffer(bytes(color)*64*64)
            fn(gl,'glTexSubImage2D',None,u,i,i,i,i,i,u,u,ptr)(0x0DE1,0,0,0,64,64,0x1908,0x1401,raw)
            attrs=(i*3)(0x30BC,0,0x3038)
            imported=create_image(display,context,0x30B1,ptr(rgba.value),attrs);assert imported,'EGLImage creation'
            fn(gl,'glActiveTexture',None,u)(0x84C2);bind_tex(0x8D65,external)
            for key,val in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)]:fn(gl,'glTexParameteri',None,u,u,i)(0x8D65,key,val)
            import_image(0x8D65,imported)
            fn(gl,'glActiveTexture',None,u)(0x84C0);bind_tex(0x0DE1,0)
            bind_fbo(0x8D40,resolved_fb);viewport(0,0,64,64);fn(gl,'glDisable',None,u)(0x0BE2)
            plain(external_program,external,0x8D65,2);bind_tex(0x8D65,0)
            assert destroy_image(display,imported)
        for eye in range(2):
            bind_fbo(0x8D40,0);viewport(0,0,64,64)
            for stream,(_,resolved,_,_) in enumerate(slots):
                plain(resolved_program,resolved,0x0DE1,0)
                pixel=(C.c_ubyte*4)();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(32,32,1,1,0x1908,0x1401,pixel)
                assert max(abs(pixel[k]-colors[stream][k]) for k in range(4))<=1,'Each stream must preserve its own frame in both eyes'
            plain(resolved_program,ui_texture,0x0DE1,0)
            fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(32,32,1,1,0x1908,0x1401,pixel)
            assert list(pixel)==[31,87,143,255],'Decoder updates must not alter unrelated UI pixels'
    fn(gl,'glActiveTexture',None,u)(0x84C0);bind_fbo(0x8D40,0);viewport(0,0,1600,1000)
    assert fn(gl,'glGetError',u)()==0
    print('PASS: 48 real EGLImage/OES frames across two independent slots resolved on unit 2; 96 eye reads and 48 independent UI pixel checks.')
    if (out/'world-live.png').exists():
        from PIL import ImageDraw, ImageChops
        chart=Image.new('RGBA',(960,540),'#102838');pen=ImageDraw.Draw(chart)
        colors=['#ffffff','#e4ca45','#34c5c8','#50b66b','#bd60b6','#c55a50','#487cc1']
        for k,color in enumerate(colors):pen.rectangle((k*960//7,0,(k+1)*960//7,240),fill=color)
        for y in range(280,480,8):
            for x in range(40,920,8):
                pen.rectangle((x,y,x+7,y+7),fill='#ffffff' if (x//8+y//8)%2 else '#101010')
        pen.text((40,250),'SYNTHETIC CAMERA / sharp detail test / not a live camera',fill='white')
        chart.save(out/'test-video.png')
        fn(gl,'glActiveTexture',None,u)(0x84C0);world=load_png(out/'world-live.png');closed=load_png(out/'world-closed.png');video=load_png(out/'test-video.png')
        def capture():
            pixels=(C.c_ubyte*(1600*1000*4))();fn(gl,'glReadPixels',None,i,i,i,i,u,u,ptr)(0,0,1600,1000,0x1908,0x1401,pixels)
            return Image.frombytes('RGBA',(1600,1000),bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        # Initial eye is above the vehicle origin; no artificial rearward camera offset.
        camera=ident.copy();camera[13]=1.6;camera[14]=0
        use(sky_program);mat(sky_program,b'camera',camera)
        world_scale=6.6/(2*1.2*3.8);world_y=.05/(.75*3.8)
        for mode in range(5):
            fn(gl,'glActiveTexture',None,u)(0x84C0);head=load_png(out/f'hud-{mode if mode<4 else 0}.png')
            bind_fbo(0x8D40,0);viewport(0,0,1600,1000);fn(gl,'glDisable',None,u)(0x0BE2)
            use(sky_program);draw(4,0,6);car()
            # Mirror production ordering: sharp camera first, glass cards and badges above it.
            if mode!=4:hud(video,world_scale*.6,world_scale*.54,world_y+world_scale*.14)
            snapshot_blur();hud(closed if mode==4 else world,world_scale,world_scale,world_y)
            before=capture() if mode==0 else None
            if 0<mode<4:snapshot_blur()
            hud(head,.549242,.549242,0)
            image=capture()
            if mode==0:
                aperture=(456,285,975,634) # Fixed head-relative right-arm overlay occupies the lower right.
                delta=ImageChops.difference(before.crop(aperture),image.crop(aperture))
                assert all(hi==0 for lo,hi in delta.getextrema()),'Main HUD must not obscure live camera pixels'
            ImageDraw.Draw(image).text((24,24),'OFF-DEVICE GLSL / desktop fonts / synthetic data / NOT a Quest capture',fill='#e1edf5')
            image.save(out/f'glass-layout-{mode}.png')
    if (out/'hud-locked.png').exists():
        bind_fbo(0x8D40,0);viewport(0,0,1600,1000);fn(gl,'glDisable',None,u)(0x0BE2)
        use(sky_program);draw(4,0,6);car();snapshot_blur();hud(world,world_scale,world_scale,world_y)
        snapshot_blur();head=load_png(out/'hud-locked.png');hud(head,.549242,.549242,0)
        locked=capture();ImageDraw.Draw(locked).text((24,24),'OFF-DEVICE / production GLSL / NOT a Quest capture',fill='#e1edf5');locked.save(out/'glass-layout-locked.png')
    assert fn(gl,'glGetError',u)()==0
    print('PASS: production glass, Gaussian, vehicle shaders/geometry render; camera pixels intact; five previews including video closed.')

