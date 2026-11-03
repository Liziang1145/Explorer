"""Build the independent OpenXR v2 engine with workspace-local pinned NDK."""
from pathlib import Path
import subprocess,os

root=Path(__file__).resolve().parents[1]
deps=root/'tools/v2_deps'
ndk=Path(os.environ.get('ANDROID_NDK_HOME',str(deps/'android-ndk-r27c')))
clang=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
out=root/'vr/build/generated/v2jni/arm64-v8a'
out.mkdir(parents=True,exist_ok=True)
baseline=root/'vr/build/generated/runtime/jniLibs/arm64-v8a'
command=[str(clang),'--target=aarch64-linux-android24','-std=c++17','-O2','-g','-fPIC','-shared','-static-libstdc++','-Wall','-Wextra','-Wno-missing-field-initializers','-Wl,-z,max-page-size=16384',
 '-I'+str(deps),str(root/'vr/src/main/cpp/terminal_v2.cpp'),'-L'+str(baseline),'-lopenxr_loader','-lEGL','-lGLESv3','-landroid','-llog','-ljnigraphics','-o',str(out/'libtlz_v2.so')]
subprocess.run(command,check=True)
print('Built',out/'libtlz_v2.so')
