"""Fetch pinned VR v2 build inputs into the workspace, with recorded SHA-256."""
from pathlib import Path
import hashlib, json, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'v2_deps'
OUT.mkdir(parents=True, exist_ok=True)
items = {
 'android-ndk-r27c-windows.zip': 'https://dl.google.com/android/repository/android-ndk-r27c-windows.zip',
 'webrtc-144.7559.09.aar': 'https://repo.maven.apache.org/maven2/io/github/webrtc-sdk/android/144.7559.09/android-144.7559.09.aar',
 'okhttp-4.12.0.jar': 'https://repo.maven.apache.org/maven2/com/squareup/okhttp3/okhttp/4.12.0/okhttp-4.12.0.jar',
 'okio-jvm-3.6.0.jar': 'https://repo.maven.apache.org/maven2/com/squareup/okio/okio-jvm/3.6.0/okio-jvm-3.6.0.jar',
 'kotlin-stdlib-1.9.10.jar': 'https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/1.9.10/kotlin-stdlib-1.9.10.jar',
 'annotations-13.0.jar': 'https://repo.maven.apache.org/maven2/org/jetbrains/annotations/13.0/annotations-13.0.jar',
}
for name in ('openxr.h', 'openxr_platform.h', 'openxr_platform_defines.h'):
 items[name] = 'https://raw.githubusercontent.com/KhronosGroup/OpenXR-SDK/release-1.1.40/include/openxr/' + name
manifest = {}
lock=json.loads((ROOT/'tools/v2_dependencies.lock.json').read_text(encoding='utf-8'))
def digest_file(path,algorithm='sha256'):
 digest=hashlib.new(algorithm)
 with path.open('rb') as source:
  while block:=source.read(1024*1024):digest.update(block)
 return digest.hexdigest()
for name, url in items.items():
 path = OUT / name
 if not path.exists():
  print('Downloading', name, flush=True)
  with urllib.request.urlopen(url, timeout=90) as response, path.with_suffix(path.suffix+'.part').open('wb') as target:
   while data := response.read(1024*1024): target.write(data)
  path.with_suffix(path.suffix+'.part').rename(path)
 digest = digest_file(path)
 assert digest==lock[name]['sha256'], 'Pinned input mismatch: '+name
 manifest[name] = {'url': url, 'sha256': digest, 'bytes': path.stat().st_size}
 print(name, path.stat().st_size, digest, flush=True)
 if name.startswith('android-ndk'):
  # Google's repository metadata pins this archive independently of download.
  assert digest_file(path,'sha1') == 'ac5f7762764b1f15341094e148ad4f847d050c38'
  if not (OUT/'android-ndk-r27c'/'source.properties').exists():
   print('Extracting NDK', flush=True)
   with zipfile.ZipFile(path) as archive: archive.extractall(OUT)
(OUT/'inputs.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Dependencies ready', flush=True)
