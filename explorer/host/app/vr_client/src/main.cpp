
#include "openxr/openxr.h"
#include "openxr_app.h"
#include "options.h"
#include "platformplugin.h"
#include "platformdata.h"

#include "OpenXRHelper.h"

// #include "MappingTask.hpp"
#include "ipc/itc/backend/RingBuf.hpp"
#include "ipc/itc/MsgQueue.hpp"
#include "CommTask.hpp"
#include "MappingTask.hpp"
#include "ArmTask.hpp"
#include "algo.hpp"

#include <asio.hpp>
#include <asio/steady_timer.hpp>
#include <fstream>
#include <functional>
#include <iostream>
#include <sstream>
#include <thread>
#include <vector>
#include "render_msg.h"
#include "pose_msg.h"

#include "ipc/msgs/whole_body_msg/whole_body_msg.h"
#include "ipc/msgs/cloud_msg/cloud_msg.h"
#include "ipc/msgs/nav_state_msg/nav_state_msg.h"

#ifdef XR_USE_PLATFORM_ANDROID
#  include <android/asset_manager.h>
#endif
struct Point {
  float x, y, z;
  float intensity;
  float nx, ny, nz;
  float curvature;
};

void readBinFile(std::string const &filename, std::vector<std::byte> &binBuffer) {
  std::ifstream file(filename.c_str(), std::ios::binary | std::ios::ate);
  if (!file.is_open()) {
    std::cerr << "Failed to open file.\n";
    return;
  }
  std::streamsize size = file.tellg();
  if (size == -1) {
    std::cerr << "Failed to get file size.\n";
    return;
  }
  std::cout << "streamsize size " << size << std::endl;
  binBuffer.resize(size);
  file.seekg(0, std::ios::beg);
  if (!file.read(reinterpret_cast<char *>(binBuffer.data()), size)) {
    std::cerr << "Failed to read file. Error: " << strerror(errno) << "\n";
    return;
  }
  return;
}

std::vector<Point> readPLY(const std::string &filename) {
  std::ifstream file(filename);
  if (!file) {
    throw std::runtime_error("Failed to open PLY file.");
  }

  std::string line;
  bool headerEnded = false;
  std::vector<Point> points;

  while (std::getline(file, line)) {
    if (!headerEnded) {
      if (line == "end_header") {
        headerEnded = true;
      }
      continue;
    }
    std::istringstream iss(line);
    float vals[8];
    for (int i = 0; i < 8; ++i) {
      if (!(iss >> vals[i])) {
        std::cerr << "Warning: Skipping malformed line: " << line << std::endl;
        goto skip;
      }
    }
    points.emplace_back(Point{vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7]});
  skip:;
  }

  std::cout << "Loaded " << points.size() << " points from " << filename << std::endl;
  return points;
}
bool appRunning = true;
#ifdef XR_USE_PLATFORM_ANDROID
std::vector<Point> readPLYAndroid(const std::string &filename, AAssetManager *assetManager) {
  if (!assetManager) {
    __android_log_print(ANDROID_LOG_ERROR, "readPLY", "assetManager is null");
    throw std::runtime_error("AAssetManager is null.");
  }

  // 使用 AAssetManager 读取文件
  AAsset *file = AAssetManager_open(assetManager, filename.c_str(), AASSET_MODE_BUFFER);
  if (!file) {
    __android_log_print(ANDROID_LOG_ERROR, "readPLY", "Failed to open asset: %s", filename.c_str());
    throw std::runtime_error("Failed to open PLY file.");
  }

  // 读取文件大小
  size_t fileLength = AAsset_getLength(file);
  if (fileLength == 0) {
    __android_log_print(ANDROID_LOG_WARN, "readPLY", "Empty file: %s", filename.c_str());
    AAsset_close(file);
    return {};
  }

  // 读取整个文件到字符串
  std::vector<char> buffer(fileLength + 1, '\0');
  AAsset_read(file, buffer.data(), fileLength);
  AAsset_close(file);

  // 将数据放入 stringstream
  std::istringstream fileStream(std::string(buffer.data(), fileLength));

  std::string line;
  bool headerEnded = false;
  std::vector<Point> points;
  int cnt = 0;
  while (std::getline(fileStream, line)) {
    if (!headerEnded) {
      if (line == "end_header") {
        headerEnded = true;
      }
      continue;
    }

    std::istringstream iss(line);
    Point p;
    if (!(iss >> p.x >> p.y >> p.z >> p.intensity >> p.nx >> p.ny >> p.nz >> p.curvature)) {
      continue;
    }
    cnt++;
    if (cnt > 250000) break;
    points.push_back(p);
  }

  __android_log_print(ANDROID_LOG_INFO, "readPLY", "Loaded %zu points from %s", points.size(), filename.c_str());
  return points;
}

AlignedVector<uint64_t> loadCompressedPoints(const std::string &filename, AAssetManager *assetManager) {
  if (!assetManager) {
    __android_log_print(ANDROID_LOG_ERROR, "loadCompressedPoints", "assetManager is null");
    throw std::runtime_error("AAssetManager is null.");
  }

  // 使用 AAssetManager 读取文件
  AAsset *file = AAssetManager_open(assetManager, filename.c_str(), AASSET_MODE_STREAMING);
  if (!file) {
    __android_log_print(ANDROID_LOG_ERROR, "loadCompressedPoints", "Failed to open asset: %s", filename.c_str());
    throw std::runtime_error("Failed to open PLY file.");
  }

  // 读取文件大小
  size_t fileLength = AAsset_getLength(file);
  if (fileLength == 0) {
    __android_log_print(ANDROID_LOG_WARN, "loadCompressedPoints", "Empty file: %s", filename.c_str());
    AAsset_close(file);
    return {};
  }

  std::vector<std::byte> buffer(static_cast<size_t>(fileLength));
  AAsset_read(file, buffer.data(), buffer.size());
  AAsset_close(file);

  PointPoll<CompressedPoint> compressPoll;
  auto in = zpp::bits::in(buffer, zpp::bits::endian::big{});
  in(compressPoll).or_throw();
  auto compressed_points = compressPoll.ExtractMember<uint64_t>(&CompressedPoint::morton_code);

  __android_log_print(ANDROID_LOG_INFO, "loadCompressedPoints", "Loaded %zu points from %s", compressed_points.size(), filename.c_str());
  return compressed_points;
}

// initialize static members first
static android_app *androidApp = nullptr;
struct AndroidAppState {
  ANativeWindow *NativeWindow = nullptr;
  bool Resumed                = false;
};
static AndroidAppState androidAppState = {};

/**
 * Process the next main command.
 */
static void app_handle_cmd(struct android_app *app, int32_t cmd) {
  AndroidAppState *appState = (AndroidAppState *)app->userData;

  switch (cmd) {
    // There is no APP_CMD_CREATE. The ANativeActivity creates the
    // application thread from onCreate(). The application thread
    // then calls android_main().
    case APP_CMD_START: {
      break;
    }
    case APP_CMD_RESUME: {
      appState->Resumed = true;
      break;
    }
    case APP_CMD_PAUSE: {
      appState->Resumed = false;
      break;
    }
    case APP_CMD_STOP: {
      break;
    }
    case APP_CMD_DESTROY: {
      appState->NativeWindow = NULL;
      break;
    }
    case APP_CMD_INIT_WINDOW: {
      appState->NativeWindow = app->window;
      break;
    }
    case APP_CMD_TERM_WINDOW: {
      appState->NativeWindow = NULL;
      break;
    }
  }
}

void android_main(struct android_app *app) {
  androidApp = app;
  // Allow interaction with JNI and the JVM on this thread.
  // https://developer.android.com/training/articles/perf-jni#threads
  JNIEnv *env;
  app->activity->vm->AttachCurrentThread(&env, nullptr);
  AAssetManager *assetManager = app->activity->assetManager;

  // https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html#XR_KHR_loader_init
  // Load xrInitializeLoaderKHR() function pointer. On Android, the loader must
  // be initialized with variables from android_app *. Without this, there's is
  // no loader and thus our function calls to OpenXR would fail.
  XrInstance m_xrInstance                         = XR_NULL_HANDLE;  // Dummy XrInstance variable for OPENXR_CHECK macro.
  PFN_xrInitializeLoaderKHR xrInitializeLoaderKHR = nullptr;
  OPENXR_CHECK(xrGetInstanceProcAddr(XR_NULL_HANDLE, "xrInitializeLoaderKHR", (PFN_xrVoidFunction *)&xrInitializeLoaderKHR),
               "Failed to get InstanceProcAddr for xrInitializeLoaderKHR.");
  // xrGetInstanceProcAddr(XR_NULL_HANDLE, "xrInitializeLoaderKHR",
  // (PFN_xrVoidFunction *)&xrInitializeLoaderKHR);
  if (!xrInitializeLoaderKHR) {
    return;
  }

  // Fill out an XrLoaderInitInfoAndroidKHR structure and initialize the loader
  // for Android.
  XrLoaderInitInfoAndroidKHR loaderInitializeInfoAndroid{XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR};
  loaderInitializeInfoAndroid.applicationVM      = app->activity->vm;
  loaderInitializeInfoAndroid.applicationContext = app->activity->clazz;
  OPENXR_CHECK(xrInitializeLoaderKHR((XrLoaderInitInfoBaseHeaderKHR *)&loaderInitializeInfoAndroid),
               "Failed to initialize Loader for Android.");
  // xrInitializeLoaderKHR((XrLoaderInitInfoBaseHeaderKHR
  // *)&loaderInitializeInfoAndroid);

  app->userData = &androidAppState;
  app->onAppCmd = app_handle_cmd;

  // std::vector<Point> cloud =
  // readPLY("/home/do/workspace/openXR/cloud_demo/data/maths-institute.ply");
  //   auto cloud = loadCompressedPoints("map/export_cloud.bin", assetManager);
  //   tbb::parallel_sort(cloud.begin(), cloud.end());
  //   auto downsampled_points = VoxelGridDownsample(cloud, 6);
  // auto downsampled_points = cloud;
  std::vector<char> vertexSource                  = ReadBinaryFile("shaders/CompressedVertexShader.spv", assetManager);
  std::vector<char> fragmentSource                = ReadBinaryFile("shaders/PixelShader.spv", assetManager);
  std::vector<char> meshVertexSource              = ReadBinaryFile("shaders/MeshVertexShader.spv", assetManager);
  std::vector<char> meshFragmentSource            = ReadBinaryFile("shaders/MeshFragmentShader.spv", assetManager);
  std::shared_ptr<PlatformData> data              = std::make_shared<PlatformData>();
  data->applicationVM                             = app->activity->vm;
  data->applicationActivity                       = app->activity->clazz;
  std::shared_ptr<Options> options                = std::make_shared<Options>();
  std::shared_ptr<IPlatformPlugin> platformPlugin = CreatePlatformPlugin(options, data);
  std::shared_ptr<IOpenXrApplication> xrApp       = CreateOpenXrProgram(platformPlugin, 10000);

  //   xrApp->compressedPoints = &downsampled_points;

  auto PollSystemEvents = [&](void) {
    // Checks whether Android has requested that application should by
    // destroyed.
    if (androidApp->destroyRequested != 0) {
      __android_log_print(ANDROID_LOG_ERROR, "OpenXRDODO", "got destroy request");
      appRunning = false;
      return;
    }
    while (true) {
      // Poll and process the Android OS system events.
      struct android_poll_source *source = nullptr;
      int events                         = 0;
      // The timeout depends on whether the application is active.
      const int timeoutMilliseconds = (!androidAppState.Resumed && !xrApp->IsSessionRunning() && androidApp->destroyRequested == 0) ? -1 : 0;
      if (ALooper_pollOnce(timeoutMilliseconds, nullptr, &events, (void **)&source) >= 0) {
        if (source != nullptr) {
          source->process(androidApp, source);
        }
      } else {
        break;
      }
    }
    return;
  };

  __android_log_print(ANDROID_LOG_ERROR, "OpenXRDODO", "initialize");
  xrApp->LoadVectexShader(vertexSource);
  xrApp->LoadFragmentShader(fragmentSource);
  xrApp->LoadMeshVectexShader(meshVertexSource);
  xrApp->LoadMeshFragmentShader(meshFragmentSource);

  // Schedule::CommTask communication_task;
  // MsgQueue cmd_msg_queue(RingBuffer<whole_body_msg>{100});
  // xrApp->SetCmdMsg(&cmd_msg_queue);  // bind to xr App
  // communication_task.bind_msg_queue("whole_body_ctrl_cmd", &cmd_msg_queue);

  Schedule::CommTask communication_task;
  MsgQueue cmd_msg_queue(RingBuffer<whole_body_msg>{100});
  MsgQueue nav_msg_queue(RingBuffer<nav_state_msg>{100});
  xrApp->SetCmdMsg(&cmd_msg_queue);  // bind to xr App
  xrApp->SetNavMsg(&nav_msg_queue);  // bind to xr App
  communication_task.bind_msg_queue("whole_body_ctrl_cmd", &cmd_msg_queue);
  communication_task.bind_msg_queue("nav_state_msg", &nav_msg_queue);

  Schedule::MappingTask mapping_task;
  MsgQueue cloud_msg_queue(RingBuffer<std::shared_ptr<std::vector<std::byte>>>{100});
  communication_task.bind_msg_queue("cloud_msg", &cloud_msg_queue);
  mapping_task.bind_msg_queue("cloud_msg", &cloud_msg_queue);

  MsgQueue cam_msg_queue(RingBuffer<std::shared_ptr<std::vector<std::byte>>>{100});
  communication_task.bind_msg_queue("cam_msg", &cam_msg_queue);
  mapping_task.bind_msg_queue("cam_msg", &cam_msg_queue);

  MsgQueue pose_msg_queue(RingBuffer<pose_msg>{100});
  mapping_task.bind_msg_queue("pose_msg", &pose_msg_queue);
  xrApp->SetPoseMsg(&pose_msg_queue);

  MsgQueue map_msg_queue(RingBuffer<std::shared_ptr<render_msg>>{100});
  mapping_task.bind_msg_queue("map_info", &map_msg_queue);
  xrApp->SetMapMsg(&map_msg_queue);

  MsgQueue cam_map_msg_queue(RingBuffer<std::shared_ptr<render_msg>>{100});
  mapping_task.bind_msg_queue("cam_info", &cam_map_msg_queue);
  xrApp->SetCamMsg(&cam_map_msg_queue);

  Schedule::ArmTask arm_task;

  MsgQueue arm_pose_msg_queue(RingBuffer<std::pair<pose_msg, pose_msg>>{100});
  arm_task.bind_msg_queue("arm_pose_msg", &arm_pose_msg_queue);
  xrApp->SetArmMsg(&arm_pose_msg_queue);

  MsgQueue arm_fb_queue(RingBuffer<std::array<Eigen::Matrix4f, 6>>{100});
  arm_task.bind_msg_queue("arm_fb_msg", &arm_fb_queue);
  xrApp->SetArmFbMsg(&arm_fb_queue);

  //   xrApp->SetMapMsg(map_msg_queue);
  xrApp->CreateInstance();
  xrApp->InitializeSystem();
  xrApp->InitializeDevice();
  xrApp->InitializeSession();
  xrApp->CreateSwapchains();
  xrApp->InitializeRenderPipeline();
  __android_log_print(ANDROID_LOG_ERROR, "OpenXRDODO", "start rendering");
  communication_task.start();

  mapping_task.start();

  // arm_task.start();
  while (appRunning) {
    PollSystemEvents();
    xrApp->PollEvents();
    if (xrApp->IsSessionRunning()) {
      // xrApp->PollActions();
      xrApp->RenderFrame();
    }
  }
  __android_log_print(ANDROID_LOG_ERROR, "OpenXRDODO", "LEAVE APP");
  // udp_thread.join();
  return;
}
#else
void PollSystemEvents() { return; }
int main(int argc, char **argv) {
  // std::vector<Point> cloud =
  // readPLY("/home/do/workspace/openXR/cloud_demo/data/maths-institute.ply");
  PointPoll<CompressedPoint> compressPoll;
  std::vector<std::byte> binBuffer;
  readBinFile("/home/do/workspace/openXR/cloud_demo/data/export_cloud_large.bin", binBuffer);
  auto in = zpp::bits::in(binBuffer, zpp::bits::endian::big{});
  in(compressPoll).or_throw();
  std::cout << "size " << compressPoll.size() << std::endl;
  auto compressed_points = compressPoll.ExtractMember<uint64_t>(&CompressedPoint::morton_code);
  std::cout << "loaded point size: " << compressed_points.size() << std::endl;
  tbb::parallel_sort(compressed_points.begin(), compressed_points.end());
  std::cout << "sort done" << std::endl;
  compressed_points.erase(std::unique(compressed_points.begin(), compressed_points.end()), compressed_points.end());
  std::cout << "unique point size: " << compressed_points.size() << std::endl;
  auto range_cloud = RangeSearch<19>(compressed_points, Eigen::Vector3f(0, 0, 0), 9);
  std::cout << "range cloud size " << range_cloud.size() << std::endl;
  // auto downsampled_points = VoxelGridDownsample(compressed_points, 5);
  auto downsampled_points = range_cloud;
  std::cout << "after downsample size " << downsampled_points.size() << std::endl;

  std::vector<char> vertexSource                  = ReadBinaryFile("CompressedVertexShader.spv");
  std::vector<char> fragmentSource                = ReadBinaryFile("PixelShader.spv");
  std::vector<char> meshVertexSource              = ReadBinaryFile("MeshVertexShader.spv");
  std::vector<char> meshFragmentSource            = ReadBinaryFile("MeshFragmentShader.spv");
  std::shared_ptr<PlatformData> data              = std::make_shared<PlatformData>();
  std::shared_ptr<Options> options                = std::make_shared<Options>();
  std::shared_ptr<IPlatformPlugin> platformPlugin = CreatePlatformPlugin(options, data);
  std::shared_ptr<IOpenXrApplication> xrApp       = CreateOpenXrProgram(platformPlugin, downsampled_points.size());
  xrApp->compressedPoints                         = &downsampled_points;
  xrApp->LoadVectexShader(vertexSource);
  xrApp->LoadFragmentShader(fragmentSource);
  xrApp->LoadMeshVectexShader(meshVertexSource);
  xrApp->LoadMeshFragmentShader(meshFragmentSource);

  Schedule::CommTask communication_task;
  MsgQueue cmd_msg_queue(RingBuffer<whole_body_msg>{100});
  xrApp->SetCmdMsg(&cmd_msg_queue);  // bind to xr App
  communication_task.bind_msg_queue("whole_body_ctrl_cmd", &cmd_msg_queue);

  Schedule::MappingTask mapping_task;
  MsgQueue cloud_msg_queue(RingBuffer<std::shared_ptr<std::vector<std::byte>>>{100});
  communication_task.bind_msg_queue("cloud_msg", &cloud_msg_queue);
  mapping_task.bind_msg_queue("cloud_msg", &cloud_msg_queue);

  MsgQueue map_msg_queue(RingBuffer<std::shared_ptr<render_msg>>{100});
  mapping_task.bind_msg_queue("map_info", &map_msg_queue);
  xrApp->SetMapMsg(&map_msg_queue);

  //   IMsgQueue *map_msg_queue = new MsgQueueImpl<std::shared_ptr<MapInfo>>(100);
  //   Schedule::MappingTask mapping_task;
  //   mapping_task.bind_msg_queue("map_info", map_msg_queue);

  //   mapping_task.bind_msg_queue("pose_msg", xrApp->GetPoseMsg());

  //   IMsgQueue *cloud_msg_queue =
  //       new MsgQueueImpl<std::shared_ptr<std::vector<std::byte>>>(100);
  //   communication_task.bind_msg_queue("cloud_msg", cloud_msg_queue);
  //   mapping_task.bind_msg_queue("cloud_msg", cloud_msg_queue);

  //   xrApp->SetMapMsg(map_msg_queue);

  // xrApp->GenRandomPoints();
  xrApp->CreateInstance();
  xrApp->InitializeSystem();
  xrApp->InitializeDevice();
  xrApp->InitializeSession();
  xrApp->CreateSwapchains();
  xrApp->InitializeRenderPipeline();

  communication_task.start();

  mapping_task.start();
  while (appRunning) {
    PollSystemEvents();
    xrApp->PollEvents();
    if (xrApp->IsSessionRunning()) {
      xrApp->RenderFrame();
      // std::cout<<cloud_msg_queue.size()<<std::endl;
    }
  }
  xrApp->Run();
  return 0;
}
#endif
