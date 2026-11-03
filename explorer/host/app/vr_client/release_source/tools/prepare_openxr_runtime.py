"""Package only the pinned generic OpenXR loader, independent of the former app engine."""
from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
pin=json.loads((root/'vr/openxr-runtime.json').read_text(encoding='utf-8'))
source=root/pin['file']
if hashlib.sha256(source.read_bytes()).hexdigest()!=pin['sha256']:
    raise ValueError('OpenXR loader SHA-256 mismatch')
out=root/'vr/build/generated/runtime/jniLibs/arm64-v8a/libopenxr_loader.so'
out.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(source,out)
print('Prepared generic OpenXR runtime loader; no legacy engine or assets')
