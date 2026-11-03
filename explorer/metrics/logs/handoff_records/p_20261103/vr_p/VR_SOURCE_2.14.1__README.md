# VR 2.14.1 源码交接包

当前包名 `com.tanluzhe.controlterminal.vr`，versionName **2.14.1**，versionCode **25**。功能及验收边界见 [VR 端工作总结](VR端工作总结.md)。此包是当前独立 OpenXR VR 业务工程的源码快照。

## 包内内容

- `vr/`：Android 启动 / 日志 / VR 页面、OpenXR 原生渲染、视频、输入、遥测、场景、录播和仪器测试源码。
- `shared/`：共用点云协议、缓存、设置、JNI、GPU 渲染和场景资源。
- `tools/`、`tests/java/`：构建、协议、交互、视频重连、场景、录播及离线 GLES 验证。
- `docs/`、`reference/`：接口、阶段工作记录及外部协议快照。历史文档中的旧路径 / 版本仅供回溯，当前构建入口以本文件为准。
- `tools/v2_deps/`：固定版本的 WebRTC AAR、OpenXR 头文件与 ARM64 通用 loader，以及主机回归所需 JAR。它们属于第三方构建输入，并非本项目编译产物；版本与校验见 lock、runtime pin 及清单，原有版权信息保留。
- `SOURCE_MANIFEST.json`、`SHA256SUMS.txt`：文件类别、长度、SHA256 与快照完整性记录。

不含项目 build / Gradle 缓存、SDK / NDK 安装树、APK、调试日志、签名私钥、手机专属页面或旧 Qt 工程。也不含完整现场点云数据服务，只有工程随附的场景 / 粗图资源。

## 构建环境

验证环境为 Windows x64、Android Studio JBR、Android SDK 36、NDK r27c（27.2.12479018）、Python 3、Gradle 9.4.1、Android Gradle Plugin 9.2.1。Media3 固定 1.8.0，WebRTC 固定 144.7559.09。

SDK / NDK / JBR 需自行安装，或使用已有安装。首次 Gradle / Maven 依赖解析需要网络；包内库不等于完整离线构建缓存。当前脚本面向 Windows，其他宿主系统需调整 NDK 编译器路径。

在本包根目录执行，按实际安装目录修改：

```powershell
$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'
$env:ANDROID_HOME='C:/Users/你的用户名/AppData/Local/Android/Sdk'
$env:ANDROID_NDK_HOME='C:/Android/android-ndk-r27c'
.\gradlew.bat -p vr assembleDebug
```

如已有全部 Gradle / Maven 缓存，可增加 `--offline`。输出：`vr/build/outputs/apk/debug/TanLuZheVR-debug.apk`。Debug 包由本机 Android debug keystore 签名；换电脑构建的签名不保证与旧安装包一致。

如果没有单独安装 NDK，也可以运行 `python tools/prepare_v2_dependencies.py`，按锁定版本下载并解压到 `tools/v2_deps/`；该步骤会下载约 782 MB 的 NDK 压缩包。这时可不设置 ANDROID_NDK_HOME。OpenXR loader 已随包提供，并由 `prepare_openxr_runtime.py` 校验哈希。

**打包副本的两项环境整理**：根 Gradle wrapper 从旧工程遗留的 8.14 对齐为实际使用的 9.4.1；`tools/build_v2_native.py` 支持 ANDROID_NDK_HOME，未设置时沿用原工作区 NDK 路径。业务 Java / C++ / 资源和测试源码按当前工作区原样复制，打包前已逐文件比较。

## 连接与配置

连接启动页可配置 AIPC 控制、遥测与媒体入口。现有默认值来自项目源码与接口约定，可在应用中修改。

本机 `shared/src/main/assets/cloud_provision.json` 已排除；附带 `cloud_provision.example.json` 作为格式参考，不会自动作为正式预配置加载。应用仍可使用现有默认设置或菜单配置。需要部署私有预配置时，复制示例为 cloud_provision.json 并填入部署值，不要将私有凭据提交到公共仓库。现场只读点云服务与完整数据需另行部署。

## 验证

先运行协议测试生成公共主机测试 classpath，再执行后续检查：

```powershell
python tools/test_v2_contract.py
python tools/test_vr_ui_recovery.py
python tools/test_video_recovery.py
python tools/test_camera_layout.py
python tools/test_view_capture.py
python tools/test_recording_protocol.py
python tools/test_cloud_stream.py
python tools/test_scene_streaming_v2.py
```

离线图形检查另需 Pillow、Visual Studio C++ 工具链和 Android SDK emulator 附带的 ANGLE DLL；这些检查不启动模拟器：

```powershell
python tools/test_vr_view_math.py
python tools/test_controller_model.py
python tools/preview_vr_hud.py
python tools/check_vr_environment.py
```

部分主机脚本保留已验证机器上的 JBR、Visual Studio 和 SDK 默认路径，换电脑后应先检查各脚本顶部的路径。它们不是 Android 应用运行时路径。`vr/src/androidTest/` 中包含设备检查源码，但本包整理过程不执行 ADB 安装或设备测试。

HTTP 回归只使用本地故障服务；Android 调度、播放器或编解码器采用主机适配器。真实视频硬解、Quest 交互、并发编码、现场网络和机器人执行仍需实机验收。历史实景数据服务检查依赖的独立大数据包未随附。
