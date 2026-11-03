#include "openxr/openxr.h"
#include <Eigen/Dense>  // must be included before openXr
#include <set>

#include "GraphicsAPI_Vulkan.h"
#include "base_type.hpp"
#include "mathHelper.h"
#include "openxr_app.h"
#include "platformplugin.h"
#include "types.h"
#include <algorithm>
#include <random>
#include <tbb/task_arena.h>
#include <tbb/task_group.h>
#ifdef USE_PLATFORM_ANDROID
#  include <android/log.h>
#endif
#include "render_msg.h"
#include "pose_msg.h"
#include "ipc/msgs/whole_body_msg/whole_body_msg.h"
#include "ipc/msgs/nav_state_msg/nav_state_msg.h"

#include "EmbeddedLie.hpp"
#include "arm_model.hpp"

struct Switch {
  bool arm_enable = false;
  bool car_enable = false;
  bool try_sync   = false;
};

Switch m_switch = {false, false, false};

struct CameraConstants {
  Eigen::Matrix4f viewProj;
  Eigen::Matrix4f view;
  Eigen::Matrix<uint32_t, 4, 1> padding;
};
CameraConstants cameraConstants;

ArmModel left_arm{ArmType::LEFT_ARM};
ArmModel right_arm{ArmType::RIGHT_ARM};

struct DeltaMove {
  Eigen::Vector3f diffPos    = Eigen::Vector3f::Zero();
  Eigen::Quaternionf diffRot = Eigen::Quaternionf::Identity();
};

DeltaMove diffMove;

Eigen::Matrix4f RotateMatrix4f(Eigen::Matrix4f mat) {
  const auto offset_quat   = Eigen::Quaternionf(0.5, 0.5, -0.5, -0.5).inverse();
  Eigen::Vector3f position = mat.block<3, 1>(0, 3);
  position                 = offset_quat.toRotationMatrix() * position;
  Eigen::Quaternionf quaternion(mat.block<3, 3>(0, 0));
  quaternion                      = offset_quat * quaternion * offset_quat.inverse();
  Eigen::Matrix4f realTransform   = Eigen::Matrix4f::Identity();
  realTransform.block<3, 3>(0, 0) = quaternion.toRotationMatrix();
  realTransform.block<3, 1>(0, 3) = position;
  return realTransform;
}
Eigen::Matrix4f feedback_end_left  = Eigen::Matrix4f::Identity();
Eigen::Matrix4f feedback_end_right = Eigen::Matrix4f::Identity();

Eigen::Matrix4f arm_bottom[2] = {RotateMatrix4f((Eigen::Matrix4f() << -0.9908, 0.1354, 0, -0.1000, -0.0000, -0.0000, 1.0000, 0.1500, 0.1354,
                                                 0.9908, 0.0000, -0.3070, 0, 0, 0, 1.0000)
                                                    .finished()),
                                 RotateMatrix4f((Eigen::Matrix4f() << -0.9908, 0.1354, 0, -0.1000, -0.0000, -0.0000, 1.0000, -0.1500, 0.1354,
                                                 0.9908, 0.0000, -0.3070, 0, 0, 0, 1.0000)
                                                    .finished())};
Eigen::Matrix4f arm_middle[2] = {RotateMatrix4f((Eigen::Matrix4f() << 0.0872, -0.9962, 0, -0.3824, 0.0000, 0.0000, 1.0000, 0.1500, -0.9962,
                                                 -0.0872, 0.0000, -0.2684, 0, 0, 0, 1.0000)
                                                    .finished()),
                                 RotateMatrix4f((Eigen::Matrix4f() << 0.0872, -0.9962, 0, -0.3824, 0.0000, 0.0000, 1.0000, -0.1500, -0.9962,
                                                 -0.0872, 0.0000, -0.2684, 0, 0, 0, 1.0000)
                                                    .finished())};
Eigen::Matrix4f arm_top[2]    = {RotateMatrix4f((Eigen::Matrix4f() << 0.0872, -0.9962, 0, -0.1345, 0.0000, 0.0000, 1.0000, 0.1500, -0.9962,
                                              -0.0872, 0.0000, -0.2247, 0, 0, 0, 1.0000)
                                                    .finished()),
                                 RotateMatrix4f((Eigen::Matrix4f() << 0.0872, -0.9962, 0, -0.1345, 0.0000, 0.0000, 1.0000, -0.1500, -0.9962,
                                              -0.0872, 0.0000, -0.2247, 0, 0, 0, 1.0000)
                                                    .finished())};

Eigen::Matrix4f grip[4]  = {Eigen::Matrix4f::Identity(), Eigen::Matrix4f::Identity(), Eigen::Matrix4f::Identity(), Eigen::Matrix4f::Identity()};
void *cam_cloudBuffer[2] = {nullptr, nullptr};
void *cam_colorBuffer[2] = {nullptr, nullptr};
void *cam_normalBuffer[2] = {nullptr, nullptr};
struct InputState {
  XrActionSet actionSet{XR_NULL_HANDLE};
  XrAction grabAction{XR_NULL_HANDLE};
  XrAction poseAction{XR_NULL_HANDLE};
  XrAction vibrateAction{XR_NULL_HANDLE};
  XrAction quitAction{XR_NULL_HANDLE};
  XrAction moveAction{XR_NULL_HANDLE};
  XrAction armEnableAction{XR_NULL_HANDLE};
  XrAction carEnableAction{XR_NULL_HANDLE};
  XrAction poseSyncAction{XR_NULL_HANDLE};
  std::array<XrPath, 2> handSubactionPath;
  std::array<XrSpace, 2> handSpace;
  std::array<float, 2> handScale = {{0.0f, 0.0f}};
  std::array<XrBool32, 2> handActive;
};

Eigen::Matrix4f realTransform = Eigen::Matrix4f::Identity();  // real position
InputState m_input;
Eigen::Matrix4f currentTransform = Eigen::Matrix4f::Identity();
Eigen::Matrix4f carTransform     = Eigen::Matrix4f::Identity();
Eigen::Matrix4f lastTransform    = Eigen::Matrix4f::Identity();
Eigen::Matrix4f relativeHandPose[2]{Eigen::Matrix4f::Identity(), Eigen::Matrix4f::Identity()};
Eigen::Matrix4f viewHandPose[2]{Eigen::Matrix4f::Identity(), Eigen::Matrix4f::Identity()};
Eigen::Matrix<float, 6, 1> relativeHandVelocity[2]{Eigen::Matrix<float, 6, 1>::Zero(), Eigen::Matrix<float, 6, 1>::Zero()};

// shader related pointer
void *m_vertexShader = nullptr, *m_fragmentShader = nullptr;

void *m_meshVertexShader = nullptr, *m_meshFragmentShader = nullptr;

void *cam_vertexShader = nullptr, *cam_fragmentShader = nullptr;

class OpenXrApplication : public IOpenXrApplication {
#if !defined(XR_USE_PLATFORM_WIN32)
#  define strcpy_s(dest, source) strncpy((dest), (source), sizeof(dest))
#endif
public:
  EIGEN_MAKE_ALIGNED_OPERATOR_NEW
  OpenXrApplication(const std::shared_ptr<IPlatformPlugin> &platformPlugin, const int pointNUm)
      : m_platformPlugin(platformPlugin),
        totalPointNum(pointNUm),
        low_priority_arena(1),
        cam_low_priority_arena(1)
  // left_arm(ArmType::LEFT_ARM),
  // right_arm(ArmType::RIGHT_ARM)
  {
    meshPtr = std::make_shared<Mesh>(1024);
  }

  ~OpenXrApplication() noexcept override = default;

  size_t add_cube(float cx, float cy, float cz, float x, float y, float z) {
    size_t base_index = vertexs.size();

    float hx = x / 2.0f;
    float hy = y / 2.0f;
    float hz = z / 2.0f;

    Eigen::Vector4f p[8] = {
        {cx - hx, cy - hy, cz - hz, 1.0f}, {cx + hx, cy - hy, cz - hz, 1.0f}, {cx + hx, cy + hy, cz - hz, 1.0f},
        {cx - hx, cy + hy, cz - hz, 1.0f}, {cx - hx, cy - hy, cz + hz, 1.0f}, {cx + hx, cy - hy, cz + hz, 1.0f},
        {cx + hx, cy + hy, cz + hz, 1.0f}, {cx - hx, cy + hy, cz + hz, 1.0f},
    };

    for (int i = 0; i < 8; ++i) {
      vertexs.push_back(p[i]);
    }

    std::vector<std::pair<int, int>> edges = {{0, 1}, {1, 2}, {2, 3}, {3, 0}, {4, 5}, {5, 6}, {6, 7}, {7, 4}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};

    for (auto &e : edges) {
      indexes.push_back(base_index + e.first);
      indexes.push_back(base_index + e.second);
    }

    return indexes.size();
  }

  void Run() override {
    CreateInstance();
    InitializeSystem();
    InitializeDevice();
    InitializeSession();
    CreateSwapchains();
    InitializeRenderPipeline();
    while (m_applicationRunning) {
      // PollSystemEvents();
      PollEvents();
      if (m_sessionRunning) {
        RenderFrame();
      }
    }
  }

  void CreateInstance() override {
    XrApplicationInfo AI;
    strncpy(AI.applicationName, "OpenXR Point Cloud Demo", XR_MAX_APPLICATION_NAME_SIZE);
    AI.applicationVersion = 1;
    strncpy(AI.engineName, "OpenXR Engine", XR_MAX_ENGINE_NAME_SIZE);
    AI.engineVersion = 1;
    AI.apiVersion    = XR_CURRENT_API_VERSION;

    std::vector<const char *> extensions;
    const std::vector<std::string> platformExtensions = m_platformPlugin->GetInstanceExtensions();
    std::transform(platformExtensions.begin(), platformExtensions.end(), std::back_inserter(extensions),
                   [](const std::string &ext) { return ext.c_str(); });
    const std::string graphicExtension = GetGraphicsAPIInstanceExtensionString(m_apiType);
    extensions.push_back(graphicExtension.c_str());

    XrInstanceCreateInfo instanceCI{XR_TYPE_INSTANCE_CREATE_INFO};
    instanceCI.createFlags           = 0;
    instanceCI.applicationInfo       = AI;
    instanceCI.next                  = m_platformPlugin->GetInstanceCreateExtension();
    instanceCI.enabledExtensionCount = (uint32_t)extensions.size();
    instanceCI.enabledExtensionNames = extensions.data();
    OPENXR_CHECK(xrCreateInstance(&instanceCI, &m_xrInstance), "Failed to create instance");
    // XrResult result = xrCreateInstance(&instanceCI, &m_xrInstance);
    // if (result != XR_SUCCESS)
    // {
    //     __android_log_print(ANDROID_LOG_ERROR, "OpenXR", "xrCreateInstance
    //     failed: %d", result); abort(); // 强制触发崩溃，方便在 `adb logcat`
    //     里查看
    // }
    // xrCreateInstance(&instanceCI, &m_xrInstance);
    return;
  }

  void InitializeSystem() override {
    XrSystemGetInfo systemGI{XR_TYPE_SYSTEM_GET_INFO};
    systemGI.formFactor = m_formFactor;
    OPENXR_CHECK(xrGetSystem(m_xrInstance, &systemGI, &m_xrSystemId), "Failed to get SystemID.");
    OPENXR_CHECK(xrGetSystemProperties(m_xrInstance, m_xrSystemId, &m_systemProperties), "Failed to get SystemProperties.");
    // xrGetSystem(m_xrInstance, &systemGI, &m_xrSystemId);
    // xrGetSystemProperties(m_xrInstance, m_xrSystemId, &m_systemProperties);
    return;
  }

  void InitializeDevice() override {
    // Enumerate twice, the first time to get the number of view configurations,
    // the second time to fill up the actual configurations.
    uint32_t viewConfigurationCount = 0;
    OPENXR_CHECK(xrEnumerateViewConfigurations(m_xrInstance, m_xrSystemId, 0, &viewConfigurationCount, nullptr),
                 "Failed to enumerate View Configurations.");
    // xrEnumerateViewConfigurations(m_xrInstance, m_xrSystemId, 0,
    // &viewConfigurationCount, nullptr);
    std::vector<XrViewConfigurationType> viewConfigTypes(viewConfigurationCount);
    OPENXR_CHECK(
        xrEnumerateViewConfigurations(m_xrInstance, m_xrSystemId, viewConfigurationCount, &viewConfigurationCount, viewConfigTypes.data()),
        "Failed to enumerate View Configurations.");
    // xrEnumerateViewConfigurations(m_xrInstance, m_xrSystemId,
    // viewConfigurationCount, &viewConfigurationCount, viewConfigTypes.data());

    // Pick the first application supported View Configuration Type con
    // supported by the hardware.
    std::vector<XrViewConfigurationType> m_applicationViewConfigurations
        = {XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_MONO};
    for (const XrViewConfigurationType &viewConfiguration : m_applicationViewConfigurations) {
      if (std::find(viewConfigTypes.begin(), viewConfigTypes.end(), viewConfiguration) != viewConfigTypes.end()) {
        m_viewConfiguration = viewConfiguration;
        break;
      }
    }
    if (m_viewConfiguration == XR_VIEW_CONFIGURATION_TYPE_MAX_ENUM) {
      std::cerr << "Failed to find a view configuration type. Defaulting to "
                   "XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO."
                << std::endl;
      m_viewConfiguration = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
    }

    uint32_t viewConfigurationViewCount = 0;
    OPENXR_CHECK(xrEnumerateViewConfigurationViews(m_xrInstance, m_xrSystemId, m_viewConfiguration, 0, &viewConfigurationViewCount, nullptr),
                 "Failed to enumerate ViewConfiguration Views.");
    // xrEnumerateViewConfigurationViews(m_xrInstance, m_xrSystemId,
    // m_viewConfiguration, 0, &viewConfigurationViewCount, nullptr);
    m_viewConfigurationViews.resize(viewConfigurationViewCount, {XR_TYPE_VIEW_CONFIGURATION_VIEW});
    OPENXR_CHECK(xrEnumerateViewConfigurationViews(m_xrInstance, m_xrSystemId, m_viewConfiguration, viewConfigurationViewCount,
                                                   &viewConfigurationViewCount, m_viewConfigurationViews.data()),
                 "Failed to enumerate ViewConfiguration Views.");
    // xrEnumerateViewConfigurationViews(m_xrInstance, m_xrSystemId,
    // m_viewConfiguration, viewConfigurationViewCount,
    // &viewConfigurationViewCount, m_viewConfigurationViews.data());

    m_environmentBlendMode = GetPreferredBlendMode();
    return;
  }

  void InitializeActions() {
    {
      XrActionSetCreateInfo actionSetInfo{XR_TYPE_ACTION_SET_CREATE_INFO};
      strcpy_s(actionSetInfo.actionSetName, "cloud_demo");
      strcpy_s(actionSetInfo.localizedActionSetName, "CloudDemo");
      actionSetInfo.priority = 0;
      OPENXR_CHECK(xrCreateActionSet(m_xrInstance, &actionSetInfo, &m_input.actionSet), "CLOUDDEMO Failed to create ActionSet.");
    }
    OPENXR_CHECK(xrStringToPath(m_xrInstance, "/user/hand/left", &m_input.handSubactionPath[0]),
                 "CLOUDDEMO Failed to get Left Hand Subaction Path.");
    OPENXR_CHECK(xrStringToPath(m_xrInstance, "/user/hand/right", &m_input.handSubactionPath[1]),
                 "CLOUDDEMO Failed to get Right Hand Subaction Path.");

    // Create actions.
    {
      // Create an input action for grabbing objects with the left and right
      // hands.
      XrActionCreateInfo actionInfo{XR_TYPE_ACTION_CREATE_INFO};
      actionInfo.actionType = XR_ACTION_TYPE_FLOAT_INPUT;
      strcpy_s(actionInfo.actionName, "grab_object");
      strcpy_s(actionInfo.localizedActionName, "Grab Object");
      actionInfo.countSubactionPaths = uint32_t(m_input.handSubactionPath.size());
      actionInfo.subactionPaths      = m_input.handSubactionPath.data();
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.grabAction), "CLOUDDEMO Failed to create Grab Object Action");

      // Create an input action getting the left and right hand poses.
      actionInfo.actionType = XR_ACTION_TYPE_POSE_INPUT;
      strcpy_s(actionInfo.actionName, "hand_pose");
      strcpy_s(actionInfo.localizedActionName, "Hand Pose");
      actionInfo.countSubactionPaths = uint32_t(m_input.handSubactionPath.size());
      actionInfo.subactionPaths      = m_input.handSubactionPath.data();
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.poseAction), "CLOUDDEMO Failed to create Hand Pose Action");

      // Create output actions for vibrating the left and right controller.
      actionInfo.actionType = XR_ACTION_TYPE_VIBRATION_OUTPUT;
      strcpy_s(actionInfo.actionName, "vibrate_hand");
      strcpy_s(actionInfo.localizedActionName, "Vibrate Hand");
      actionInfo.countSubactionPaths = uint32_t(m_input.handSubactionPath.size());
      actionInfo.subactionPaths      = m_input.handSubactionPath.data();
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.vibrateAction), "CLOUDDEMO Failed to create Vibrate Hand Action");

      actionInfo.actionType = XR_ACTION_TYPE_VECTOR2F_INPUT;
      strcpy_s(actionInfo.actionName, "move_camera");
      strcpy_s(actionInfo.localizedActionName, "Move Head");
      actionInfo.countSubactionPaths = uint32_t(m_input.handSubactionPath.size());
      actionInfo.subactionPaths      = m_input.handSubactionPath.data();
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.moveAction), "CLOUDDEMO Failed to create Move Action");

      // Create input actions for quitting the session using the left and right
      // controller. Since it doesn't matter which hand did this, we do not
      // specify subaction paths for it. We will just suggest bindings for both
      // hands, where possible.
      actionInfo.actionType = XR_ACTION_TYPE_BOOLEAN_INPUT;
      strcpy_s(actionInfo.actionName, "quit_session");
      strcpy_s(actionInfo.localizedActionName, "Quit Session");
      actionInfo.countSubactionPaths = 0;
      actionInfo.subactionPaths      = nullptr;
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.quitAction), "CLOUDDEMO Failed to create Quit Session Action");

      // enableArmAction
      actionInfo.actionType = XR_ACTION_TYPE_BOOLEAN_INPUT;
      strcpy_s(actionInfo.actionName, "enable_arm");
      strcpy_s(actionInfo.localizedActionName, "Arm Session");
      actionInfo.countSubactionPaths = 0;
      actionInfo.subactionPaths      = nullptr;
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.armEnableAction), "CLOUDDEMO Failed to create Quit Session Action");

      // enableArmAction
      actionInfo.actionType = XR_ACTION_TYPE_BOOLEAN_INPUT;
      strcpy_s(actionInfo.actionName, "enable_car");
      strcpy_s(actionInfo.localizedActionName, "car Session");
      actionInfo.countSubactionPaths = 0;
      actionInfo.subactionPaths      = nullptr;
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.carEnableAction), "CLOUDDEMO Failed to create Quit Session Action");

      actionInfo.actionType = XR_ACTION_TYPE_BOOLEAN_INPUT;
      strcpy_s(actionInfo.actionName, "sync_pose");
      strcpy_s(actionInfo.localizedActionName, "sync Session");
      actionInfo.countSubactionPaths = 0;
      actionInfo.subactionPaths      = nullptr;
      OPENXR_CHECK(xrCreateAction(m_input.actionSet, &actionInfo, &m_input.poseSyncAction), "CLOUDDEMO Failed to create Pose Sync Action");
    }

    std::array<XrPath, 2> selectPath;
    std::array<XrPath, 2> squeezeValuePath;
    std::array<XrPath, 2> squeezeForcePath;
    std::array<XrPath, 2> squeezeClickPath;
    std::array<XrPath, 2> posePath;
    std::array<XrPath, 2> hapticPath;
    std::array<XrPath, 2> menuClickPath;
    std::array<XrPath, 3> bClickPath;
    std::array<XrPath, 2> triggerValuePath;
    std::array<XrPath, 2> thumbStickPath;
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/select/click", &selectPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/select/click", &selectPath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/squeeze/value",
                    &squeezeValuePath[0]));  // middle finger
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/squeeze/value", &squeezeValuePath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/squeeze/force", &squeezeForcePath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/squeeze/force", &squeezeForcePath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/squeeze/click", &squeezeClickPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/squeeze/click", &squeezeClickPath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/grip/pose", &posePath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/grip/pose", &posePath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/output/haptic", &hapticPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/output/haptic", &hapticPath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/menu/click", &menuClickPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/menu/click", &menuClickPath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/x/click", &bClickPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/b/click", &bClickPath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/y/click", &bClickPath[2]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/trigger/value", &triggerValuePath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/trigger/value", &triggerValuePath[1]));
    (xrStringToPath(m_xrInstance, "/user/hand/left/input/thumbstick", &thumbStickPath[0]));
    (xrStringToPath(m_xrInstance, "/user/hand/right/input/thumbstick", &thumbStickPath[1]));

    // Suggest bindings for the Oculus Touch.
    {
      XrPath oculusTouchInteractionProfilePath;
      xrStringToPath(m_xrInstance, "/interaction_profiles/oculus/touch_controller", &oculusTouchInteractionProfilePath);
      std::vector<XrActionSuggestedBinding> bindings{{{m_input.grabAction, triggerValuePath[0]},
                                                      {m_input.grabAction, triggerValuePath[1]},
                                                      {m_input.poseAction, posePath[0]},
                                                      {m_input.poseAction, posePath[1]},
                                                      {m_input.quitAction, menuClickPath[0]},
                                                      {m_input.poseSyncAction, bClickPath[0]},
                                                      {m_input.armEnableAction, bClickPath[1]},
                                                      {m_input.carEnableAction, bClickPath[2]},
                                                      {m_input.vibrateAction, hapticPath[0]},
                                                      {m_input.vibrateAction, hapticPath[1]},
                                                      {m_input.moveAction, thumbStickPath[0]},
                                                      {m_input.moveAction, thumbStickPath[1]}}};
      XrInteractionProfileSuggestedBinding suggestedBindings{XR_TYPE_INTERACTION_PROFILE_SUGGESTED_BINDING};
      suggestedBindings.interactionProfile     = oculusTouchInteractionProfilePath;
      suggestedBindings.suggestedBindings      = bindings.data();
      suggestedBindings.countSuggestedBindings = (uint32_t)bindings.size();
      OPENXR_CHECK(xrSuggestInteractionProfileBindings(m_xrInstance, &suggestedBindings), "Sugessted Binding Failed");
    }
    XrActionSpaceCreateInfo actionSpaceInfo{XR_TYPE_ACTION_SPACE_CREATE_INFO};
    actionSpaceInfo.action                          = m_input.poseAction;
    actionSpaceInfo.poseInActionSpace.orientation.w = 1.f;
    actionSpaceInfo.subactionPath                   = m_input.handSubactionPath[0];
    OPENXR_CHECK(xrCreateActionSpace(m_session, &actionSpaceInfo, &m_input.handSpace[0]), "Create left action space failed ");
    actionSpaceInfo.subactionPath = m_input.handSubactionPath[1];
    OPENXR_CHECK(xrCreateActionSpace(m_session, &actionSpaceInfo, &m_input.handSpace[1]), "Create right action space failed ");

    XrSessionActionSetsAttachInfo attachInfo{XR_TYPE_SESSION_ACTION_SETS_ATTACH_INFO};
    attachInfo.countActionSets = 1;
    attachInfo.actionSets      = &m_input.actionSet;
    OPENXR_CHECK(xrAttachSessionActionSets(m_session, &attachInfo), "Attach Action Set Failed");
  }

  void InitializeSession() override {
    XrSessionCreateInfo sessionCI{XR_TYPE_SESSION_CREATE_INFO};
    if (m_apiType == VULKAN) {
      m_graphicsAPI = std::make_unique<GraphicsAPI_Vulkan>(m_xrInstance, m_xrSystemId);
    } else {
      std::cerr << "Unsupported Graphics API" << std::endl;
    }

    sessionCI.next        = m_graphicsAPI->GetGraphicsBinding();
    sessionCI.createFlags = 0;
    sessionCI.systemId    = m_xrSystemId;

    OPENXR_CHECK(xrCreateSession(m_xrInstance, &sessionCI, &m_session), "Failed to create Session.");
    // xrCreateSession(m_xrInstance, &sessionCI, &m_session);
    InitializeActions();
    {
      XrReferenceSpaceCreateInfo referenceSpaceCI{XR_TYPE_REFERENCE_SPACE_CREATE_INFO};
      referenceSpaceCI.referenceSpaceType   = XR_REFERENCE_SPACE_TYPE_LOCAL;
      referenceSpaceCI.poseInReferenceSpace = {{0.0f, 0.0f, 0.0f, 1.0f}, {0.0f, 0.0f, 0.0f}};
      OPENXR_CHECK(xrCreateReferenceSpace(m_session, &referenceSpaceCI, &m_localSpace), "Failed to create ReferenceSpace.");
    }

    {
      XrReferenceSpaceCreateInfo referenceSpaceCI{XR_TYPE_REFERENCE_SPACE_CREATE_INFO};
      referenceSpaceCI.referenceSpaceType   = XR_REFERENCE_SPACE_TYPE_VIEW;
      referenceSpaceCI.poseInReferenceSpace = {{0.0f, 0.0f, 0.0f, 1.0f}, {0.0f, 0.0f, 0.0f}};
      OPENXR_CHECK(xrCreateReferenceSpace(m_session, &referenceSpaceCI, &m_headSpace), "Failed to create ReferenceSpace.");
    }

    // xrCreateReferenceSpace(m_session, &referenceSpaceCI, &m_localSpace);
    return;
  }

  void InitializeRenderPipeline() override {
    if (m_apiType == VULKAN) {
      m_vertexShader = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::VERTEX, vertexSource.data(), vertexSource.size()});
      m_fragmentShader
          = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::FRAGMENT, fragmentSource.data(), fragmentSource.size()});
    }
    if (m_vertexShader == nullptr) {
    }
    std::cout << "creating buffer" << std::endl;
    m_uniformBuffer_Camera
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::UNIFORM, 0, sizeof(CameraConstants) * 2, nullptr});
    m_cloudBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint64_t), sizeof(uint64_t) * 2097152, nullptr});
    m_cloudBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint64_t), sizeof(uint64_t) * 2097152, nullptr});

    m_colorBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 2097152, nullptr});
    m_colorBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 2097152, nullptr});

    m_normalBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 2097152, nullptr});
    m_normalBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 2097152, nullptr});

    __android_log_print(ANDROID_LOG_ERROR, "cloud_memory", "%16x %16x %16x %16x %16x %16x \n ", m_cloudBuffer[0], m_cloudBuffer[1],
                        m_colorBuffer[0], m_colorBuffer[1], m_normalBuffer[0], m_normalBuffer[1]);

    GraphicsAPI::PipelineCreateInfo pipelineCI;
    pipelineCI.shaders                     = {m_vertexShader, m_fragmentShader};
    pipelineCI.vertexInputState.attributes = {};
    pipelineCI.vertexInputState.bindings   = {};
    pipelineCI.inputAssemblyState          = {GraphicsAPI::PrimitiveTopology::POINT_LIST, false};
    pipelineCI.rasterisationState          = {false,
                                              false,
                                              GraphicsAPI::PolygonMode::POINT,
                                              GraphicsAPI::CullMode::NONE,
                                              GraphicsAPI::FrontFace::COUNTER_CLOCKWISE,
                                              false,
                                              0.0f,
                                              0.0f,
                                              0.0f,
                                              1.0f};
    pipelineCI.multisampleState            = {1, false, 1.0f, 0xFFFFFFFF, false, false};
    pipelineCI.depthStencilState           = {true, true, GraphicsAPI::CompareOp::LESS_OR_EQUAL, false, false, {}, {}, 0.0f, 1.0f};
    pipelineCI.colorBlendState             = {false,
                                              GraphicsAPI::LogicOp::NO_OP,
                                              {{true, GraphicsAPI::BlendFactor::SRC_ALPHA, GraphicsAPI::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                GraphicsAPI::BlendOp::ADD, GraphicsAPI::BlendFactor::ONE, GraphicsAPI::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                GraphicsAPI::BlendOp::ADD, (GraphicsAPI::ColorComponentBit)15}},
                                              {0.0f, 0.0f, 0.0f, 0.0f}};
    pipelineCI.colorFormats                = {m_colorSwapchainInfos[0].swapchainFormat};
    pipelineCI.depthFormat                 = m_depthSwapchainInfos[0].swapchainFormat;
    pipelineCI.layout = {{0, m_uniformBuffer_Camera, GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX},
                         {1, m_cloudBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX, true},
                         {2, m_colorBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX, true},
                         {3, m_normalBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::FRAGMENT, true}};
    m_pipeline        = m_graphicsAPI->CreatePipeline(pipelineCI);
    if (!m_pipeline) {
      // __android_log_print(ANDROID_LOG_ERROR, "CloudDemo", "m_pipeline is
      // NULL!");
      return;
    }

    /*****************************************************************************************
     */
    /***********************************SECOND
     * PIPELINE*************************************** */
    /*****************************************************************************************
     */

    // initialize mesh shader pipeline
    if (m_apiType == VULKAN) {
      m_meshVertexShader
          = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::VERTEX, meshVertexSource.data(), meshVertexSource.size()});
      m_meshFragmentShader
          = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::FRAGMENT, meshFragmentSource.data(), meshFragmentSource.size()});
    }
    if (m_meshVertexShader == nullptr) {
      std::cerr << "No shader" << std::endl;
    }
    // share the camera buffer

    // vertex and index buffer
    m_vertexBuffer
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::VERTEX, sizeof(float) * 4, sizeof(float) * 4 * 1024, nullptr});
    m_indexBuffer
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::INDEX, sizeof(uint32_t), sizeof(uint32_t) * 3 * 1024, nullptr});

    GraphicsAPI::PipelineCreateInfo meshPipelineCI;
    meshPipelineCI.shaders                     = {m_meshVertexShader, m_meshFragmentShader};
    meshPipelineCI.vertexInputState.attributes = {{0, 0, GraphicsAPI::VertexType::VEC4, 0, "POSITION"}};
    meshPipelineCI.vertexInputState.bindings   = {{0, 0, 4 * sizeof(float)}};
    meshPipelineCI.inputAssemblyState          = {GraphicsAPI::PrimitiveTopology::LINE_LIST, false};
    meshPipelineCI.rasterisationState          = {
        false, false, GraphicsAPI::PolygonMode::FILL, GraphicsAPI::CullMode::NONE, GraphicsAPI::FrontFace::COUNTER_CLOCKWISE, false, 0.0f, 0.0f,
        0.0f,  6.0f};
    meshPipelineCI.multisampleState  = {1, false, 1.0f, 0xFFFFFFFF, false, false};
    meshPipelineCI.depthStencilState = {true, true, GraphicsAPI::CompareOp::LESS_OR_EQUAL, false, false, {}, {}, 0.0f, 1.0f};
    meshPipelineCI.colorBlendState
        = {false,
           GraphicsAPI::LogicOp::NO_OP,
           {{true, GraphicsAPI::BlendFactor::SRC_ALPHA, GraphicsAPI::BlendFactor::ONE_MINUS_SRC_ALPHA, GraphicsAPI::BlendOp::ADD,
             GraphicsAPI::BlendFactor::ONE, GraphicsAPI::BlendFactor::ZERO, GraphicsAPI::BlendOp::ADD, (GraphicsAPI::ColorComponentBit)15}},
           {0.0f, 0.0f, 0.0f, 0.0f}};
    meshPipelineCI.colorFormats = {m_colorSwapchainInfos[0].swapchainFormat};
    meshPipelineCI.depthFormat  = m_depthSwapchainInfos[0].swapchainFormat;
    meshPipelineCI.layout       = {{0, nullptr, GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX}};
    m_pipeline_model            = m_graphicsAPI->CreatePipeline(meshPipelineCI);
    if (!m_pipeline_model) {
      return;
    }

    /*****************************************************************************************
     */
    /***********************************THIRD
     * PIPELINE*************************************** */
    /*****************************************************************************************
     */
    if (m_apiType == VULKAN) {
      cam_vertexShader = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::VERTEX, vertexSource.data(), vertexSource.size()});
      cam_fragmentShader
          = m_graphicsAPI->CreateShader({GraphicsAPI::ShaderCreateInfo::Type::FRAGMENT, fragmentSource.data(), fragmentSource.size()});
    }
    cam_cloudBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint64_t), sizeof(uint64_t) * 1048576, nullptr});
    cam_cloudBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint64_t), sizeof(uint64_t) * 1048576, nullptr});

    cam_colorBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 1048576, nullptr});
    cam_colorBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 1048576, nullptr});

    cam_normalBuffer[0]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 1048576, nullptr});
    cam_normalBuffer[1]
        = m_graphicsAPI->CreateBuffer({GraphicsAPI::BufferCreateInfo::Type::STORAGE, sizeof(uint32_t), sizeof(uint32_t) * 1048576, nullptr});

    GraphicsAPI::PipelineCreateInfo camPipelineCI;
    camPipelineCI.shaders                     = {cam_vertexShader, cam_fragmentShader};
    camPipelineCI.vertexInputState.attributes = {};
    camPipelineCI.vertexInputState.bindings   = {};
    camPipelineCI.inputAssemblyState          = {GraphicsAPI::PrimitiveTopology::POINT_LIST, false};
    camPipelineCI.rasterisationState          = {false,
                                                 false,
                                                 GraphicsAPI::PolygonMode::POINT,
                                                 GraphicsAPI::CullMode::NONE,
                                                 GraphicsAPI::FrontFace::COUNTER_CLOCKWISE,
                                                 false,
                                                 0.0f,
                                                 0.0f,
                                                 0.0f,
                                                 1.0f};
    camPipelineCI.multisampleState            = {1, false, 1.0f, 0xFFFFFFFF, false, false};
    camPipelineCI.depthStencilState           = {true, true, GraphicsAPI::CompareOp::LESS_OR_EQUAL, false, false, {}, {}, 0.0f, 1.0f};
    camPipelineCI.colorBlendState             = {false,
                                                 GraphicsAPI::LogicOp::NO_OP,
                                                 {{true, GraphicsAPI::BlendFactor::SRC_ALPHA, GraphicsAPI::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                   GraphicsAPI::BlendOp::ADD, GraphicsAPI::BlendFactor::ONE, GraphicsAPI::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                   GraphicsAPI::BlendOp::ADD, (GraphicsAPI::ColorComponentBit)15}},
                                                 {0.0f, 0.0f, 0.0f, 0.0f}};
    camPipelineCI.colorFormats                = {m_colorSwapchainInfos[0].swapchainFormat};
    camPipelineCI.depthFormat                 = m_depthSwapchainInfos[0].swapchainFormat;
    camPipelineCI.layout
        = {{0, m_uniformBuffer_Camera, GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX},
           {1, cam_cloudBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX, true},
           {2, cam_colorBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::VERTEX, true},
           {3, cam_normalBuffer[0], GraphicsAPI::DescriptorInfo::Type::BUFFER, GraphicsAPI::DescriptorInfo::Stage::FRAGMENT, true}};
    cam_pipeline = m_graphicsAPI->CreatePipeline(camPipelineCI);
    if (!cam_pipeline) {
      // __android_log_print(ANDROID_LOG_ERROR, "CloudDemo", "m_pipeline is
      // NULL!");
      return;
    }

    std::cout << "Rendering Pipeline initalized" << std::endl;

    add_cube(0, -0.6, 0.3, 0.6, 0.4, 0.6);
    add_cube(0, -0.6, 0.3, 0.6, 0.4, 0.6);

    add_cube(0, 0.0, 0.0, 0.1, 0.1, 0.1);
    add_cube(0, 0.0, 0.0, 0.1, 0.1, 0.1);

    add_cube(0, 0.0, 0.0, 0.1, 0.1, 0.1);
    add_cube(0, 0.0, 0.0, 0.1, 0.1, 0.1);

    // arm0 bottom stick
    // add_cube(0.0, 0.0, -0.285 * 0.5, 0.05, 0.05, 0.285);

    // // arm0 middle stick
    // add_cube(0.251 * 0.5, 0.0, 0.0, 0.251, 0.04, 0.04);

    // // arm0 top stick
    // add_cube(0.091 * 0.5, 0.0, 0.0, 0.091, 0.05, 0.05);

    // // arm1 bottom stick
    // add_cube(0.0, 0.0, -0.285 * 0.5, 0.05, 0.05, 0.285);

    // // arm1 middle stick
    // add_cube(0.251 * 0.5, 0.0, 0.0, 0.251, 0.04, 0.04);

    // // arm1 top stick
    // add_cube(0.091 * 0.5, 0.0, 0.0, 0.091, 0.05, 0.05);

    add_cube(0.0, 0.0, 0.0, 0.02, 0.02, 0.02);
    add_cube(0.0, 0.0, 0.0, 0.02, 0.02, 0.02);
    add_cube(0.0, 0.0, 0.0, 0.02, 0.02, 0.02);
    add_cube(0.0, 0.0, 0.0, 0.02, 0.02, 0.02);
    return;
  }

  void CreateSwapchains() override {
    uint32_t formatCount = 0;
    OPENXR_CHECK(xrEnumerateSwapchainFormats(m_session, 0, &formatCount, nullptr), "Failed to enumerate Swapchain Formats");
    // xrEnumerateSwapchainFormats(m_session, 0, &formatCount, nullptr);
    std::vector<int64_t> formats(formatCount);
    OPENXR_CHECK(xrEnumerateSwapchainFormats(m_session, formatCount, &formatCount, formats.data()), "Failed to enumerate Swapchain Formats");
    // xrEnumerateSwapchainFormats(m_session, formatCount, &formatCount,
    // formats.data());
    if (m_graphicsAPI->SelectDepthSwapchainFormat(formats) == 0) {
      std::cerr << "Failed to find depth format for Swapchain." << std::endl;
    }

    m_colorSwapchainInfos.resize(m_viewConfigurationViews.size());
    m_depthSwapchainInfos.resize(m_viewConfigurationViews.size());

    for (size_t i = 0; i < m_viewConfigurationViews.size(); i++) {
      SwapchainInfo &colorSwapchainInfo = m_colorSwapchainInfos[i];
      SwapchainInfo &depthSwapchainInfo = m_depthSwapchainInfos[i];

      // Fill out an XrSwapchainCreateInfo structure and create an XrSwapchain.
      // Color.
      XrSwapchainCreateInfo swapchainCI{XR_TYPE_SWAPCHAIN_CREATE_INFO};
      swapchainCI.createFlags = 0;
      swapchainCI.usageFlags  = XR_SWAPCHAIN_USAGE_SAMPLED_BIT | XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT;
      swapchainCI.format      = m_graphicsAPI->SelectColorSwapchainFormat(formats);  // Use GraphicsAPI to select the first compatible format.
      swapchainCI.sampleCount = m_viewConfigurationViews[i].recommendedSwapchainSampleCount;  // Use the recommended values
                                                                                              // from the
                                                                                              // XrViewConfigurationView.
      swapchainCI.width     = m_viewConfigurationViews[i].recommendedImageRectWidth;
      swapchainCI.height    = m_viewConfigurationViews[i].recommendedImageRectHeight;
      swapchainCI.faceCount = 1;
      swapchainCI.arraySize = 1;
      swapchainCI.mipCount  = 1;
      OPENXR_CHECK(xrCreateSwapchain(m_session, &swapchainCI, &colorSwapchainInfo.swapchain), "Failed to create Color Swapchain");
      // xrCreateSwapchain(m_session, &swapchainCI,
      // &colorSwapchainInfo.swapchain);
      colorSwapchainInfo.swapchainFormat = swapchainCI.format;  // Save the swapchain format for later use.

      // Depth.
      swapchainCI.createFlags = 0;
      swapchainCI.usageFlags  = XR_SWAPCHAIN_USAGE_SAMPLED_BIT | XR_SWAPCHAIN_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
      swapchainCI.format      = m_graphicsAPI->SelectDepthSwapchainFormat(formats);  // Use GraphicsAPI to select the first compatible format.
      swapchainCI.sampleCount = m_viewConfigurationViews[i].recommendedSwapchainSampleCount;  // Use the recommended values
                                                                                              // from the
                                                                                              // XrViewConfigurationView.
      swapchainCI.width     = m_viewConfigurationViews[i].recommendedImageRectWidth;
      swapchainCI.height    = m_viewConfigurationViews[i].recommendedImageRectHeight;
      swapchainCI.faceCount = 1;
      swapchainCI.arraySize = 1;
      swapchainCI.mipCount  = 1;
      OPENXR_CHECK(xrCreateSwapchain(m_session, &swapchainCI, &depthSwapchainInfo.swapchain), "Failed to create Depth Swapchain");
      // xrCreateSwapchain(m_session, &swapchainCI,
      // &depthSwapchainInfo.swapchain);
      depthSwapchainInfo.swapchainFormat = swapchainCI.format;  // Save the swapchain format for later use.

      // Get the number of images in the color/depth swapchain and allocate
      // Swapchain image data via GraphicsAPI to store the returned array.
      uint32_t colorSwapchainImageCount = 0;
      OPENXR_CHECK(xrEnumerateSwapchainImages(colorSwapchainInfo.swapchain, 0, &colorSwapchainImageCount, nullptr),
                   "Failed to enumerate Color Swapchain Images.");
      // xrEnumerateSwapchainImages(colorSwapchainInfo.swapchain, 0,
      // &colorSwapchainImageCount, nullptr);
      XrSwapchainImageBaseHeader *colorSwapchainImages = m_graphicsAPI->AllocateSwapchainImageData(
          colorSwapchainInfo.swapchain, GraphicsAPI::SwapchainType::COLOR, colorSwapchainImageCount);
      OPENXR_CHECK(
          xrEnumerateSwapchainImages(colorSwapchainInfo.swapchain, colorSwapchainImageCount, &colorSwapchainImageCount, colorSwapchainImages),
          "Failed to enumerate Color Swapchain Images.");
      // xrEnumerateSwapchainImages(colorSwapchainInfo.swapchain,
      // colorSwapchainImageCount, &colorSwapchainImageCount,
      // colorSwapchainImages);

      uint32_t depthSwapchainImageCount = 0;
      OPENXR_CHECK(xrEnumerateSwapchainImages(depthSwapchainInfo.swapchain, 0, &depthSwapchainImageCount, nullptr),
                   "Failed to enumerate Depth Swapchain Images.");
      // xrEnumerateSwapchainImages(depthSwapchainInfo.swapchain, 0,
      // &depthSwapchainImageCount, nullptr);
      XrSwapchainImageBaseHeader *depthSwapchainImages = m_graphicsAPI->AllocateSwapchainImageData(
          depthSwapchainInfo.swapchain, GraphicsAPI::SwapchainType::DEPTH, depthSwapchainImageCount);
      OPENXR_CHECK(
          xrEnumerateSwapchainImages(depthSwapchainInfo.swapchain, depthSwapchainImageCount, &depthSwapchainImageCount, depthSwapchainImages),
          "Failed to enumerate Depth Swapchain Images.");
      // xrEnumerateSwapchainImages(depthSwapchainInfo.swapchain,
      // depthSwapchainImageCount, &depthSwapchainImageCount,
      // depthSwapchainImages);

      // Per image in the swapchains, fill out a
      // GraphicsAPI::ImageViewCreateInfo structure and create a color/depth
      // image view.
      for (uint32_t j = 0; j < colorSwapchainImageCount; j++) {
        GraphicsAPI::ImageViewCreateInfo imageViewCI;
        imageViewCI.image          = m_graphicsAPI->GetSwapchainImage(colorSwapchainInfo.swapchain, j);
        imageViewCI.type           = GraphicsAPI::ImageViewCreateInfo::Type::RTV;
        imageViewCI.view           = GraphicsAPI::ImageViewCreateInfo::View::TYPE_2D;
        imageViewCI.format         = colorSwapchainInfo.swapchainFormat;
        imageViewCI.aspect         = GraphicsAPI::ImageViewCreateInfo::Aspect::COLOR_BIT;
        imageViewCI.baseMipLevel   = 0;
        imageViewCI.levelCount     = 1;
        imageViewCI.baseArrayLayer = 0;
        imageViewCI.layerCount     = 1;
        colorSwapchainInfo.imageViews.push_back(m_graphicsAPI->CreateImageView(imageViewCI));
      }
      for (uint32_t j = 0; j < depthSwapchainImageCount; j++) {
        GraphicsAPI::ImageViewCreateInfo imageViewCI;
        imageViewCI.image          = m_graphicsAPI->GetSwapchainImage(depthSwapchainInfo.swapchain, j);
        imageViewCI.type           = GraphicsAPI::ImageViewCreateInfo::Type::DSV;
        imageViewCI.view           = GraphicsAPI::ImageViewCreateInfo::View::TYPE_2D;
        imageViewCI.format         = depthSwapchainInfo.swapchainFormat;
        imageViewCI.aspect         = GraphicsAPI::ImageViewCreateInfo::Aspect::DEPTH_BIT;
        imageViewCI.baseMipLevel   = 0;
        imageViewCI.levelCount     = 1;
        imageViewCI.baseArrayLayer = 0;
        imageViewCI.layerCount     = 1;
        depthSwapchainInfo.imageViews.push_back(m_graphicsAPI->CreateImageView(imageViewCI));
      }
    }
  }

  void PollEvents() override {
    XrEventDataBuffer eventData{XR_TYPE_EVENT_DATA_BUFFER};
    auto XrPollEvents = [&]() -> bool {
      eventData = {XR_TYPE_EVENT_DATA_BUFFER};
      return xrPollEvent(m_xrInstance, &eventData) == XR_SUCCESS;
    };

    while (XrPollEvents()) {
      switch (eventData.type) {
        // Log the number of lost events from the runtime.
        case XR_TYPE_EVENT_DATA_EVENTS_LOST: {
          XrEventDataEventsLost *eventsLost = reinterpret_cast<XrEventDataEventsLost *>(&eventData);
          break;
        }
        // Log that an instance loss is pending and shutdown the application.
        case XR_TYPE_EVENT_DATA_INSTANCE_LOSS_PENDING: {
          XrEventDataInstanceLossPending *instanceLossPending = reinterpret_cast<XrEventDataInstanceLossPending *>(&eventData);
          m_sessionRunning                                    = false;
          m_applicationRunning                                = false;
          break;
        }
        // Log that the interaction profile has changed.
        case XR_TYPE_EVENT_DATA_INTERACTION_PROFILE_CHANGED: {
          XrEventDataInteractionProfileChanged *interactionProfileChanged
              = reinterpret_cast<XrEventDataInteractionProfileChanged *>(&eventData);
          if (interactionProfileChanged->session != m_session) {
            break;
          }
          break;
        }
        // Log that there's a reference space change pending.
        case XR_TYPE_EVENT_DATA_REFERENCE_SPACE_CHANGE_PENDING: {
          XrEventDataReferenceSpaceChangePending *referenceSpaceChangePending
              = reinterpret_cast<XrEventDataReferenceSpaceChangePending *>(&eventData);
          if (referenceSpaceChangePending->session != m_session) {
            break;
          }
          break;
        }
        // Session State changes:
        case XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED: {
          XrEventDataSessionStateChanged *sessionStateChanged = reinterpret_cast<XrEventDataSessionStateChanged *>(&eventData);
          if (sessionStateChanged->session != m_session) {
            break;
          }

          if (sessionStateChanged->state == XR_SESSION_STATE_READY) {
            // SessionState is ready. Begin the XrSession using the
            // XrViewConfigurationType.
            XrSessionBeginInfo sessionBeginInfo{XR_TYPE_SESSION_BEGIN_INFO};
            sessionBeginInfo.primaryViewConfigurationType = m_viewConfiguration;
            OPENXR_CHECK(xrBeginSession(m_session, &sessionBeginInfo), "Failed to begin Session.");
            // xrBeginSession(m_session, &sessionBeginInfo);
            m_sessionRunning = true;
          }
          if (sessionStateChanged->state == XR_SESSION_STATE_STOPPING) {
            // SessionState is stopping. End the XrSession.
            OPENXR_CHECK(xrEndSession(m_session), "Failed to end Session.");
            // xrEndSession(m_session);
            m_sessionRunning = false;
          }
          if (sessionStateChanged->state == XR_SESSION_STATE_EXITING) {
            // SessionState is exiting. Exit the application.
            m_sessionRunning     = false;
            m_applicationRunning = false;
          }
          if (sessionStateChanged->state == XR_SESSION_STATE_LOSS_PENDING) {
            // SessionState is loss pending. Exit the application.
            // It's possible to try a reestablish an XrInstance and XrSession, but
            // we will simply exit here.
            m_sessionRunning     = false;
            m_applicationRunning = false;
          }
          // Store state for reference across the application.
          m_sessionState = sessionStateChanged->state;
          break;
        }
        default: {
          break;
        }
      }
    }
    return;
  }

  void PollActions(XrTime time) override {
    m_input.handActive = {XR_FALSE, XR_FALSE};
    // Sync actions
    const XrActiveActionSet activeActionSet{m_input.actionSet, XR_NULL_PATH};
    XrActionsSyncInfo syncInfo{XR_TYPE_ACTIONS_SYNC_INFO};
    syncInfo.countActiveActionSets = 1;
    syncInfo.activeActionSets      = &activeActionSet;
    OPENXR_CHECK(xrSyncActions(m_session, &syncInfo), "Sync Action Failed");

    for (auto hand : {0, 1}) {
      XrActionStateGetInfo getInfo{XR_TYPE_ACTION_STATE_GET_INFO};
      getInfo.action        = m_input.grabAction;
      getInfo.subactionPath = m_input.handSubactionPath[hand];

      XrActionStateFloat grabValue{XR_TYPE_ACTION_STATE_FLOAT};
      OPENXR_CHECK(xrGetActionStateFloat(m_session, &getInfo, &grabValue), "Get Action State Failed");
      if (grabValue.isActive == XR_TRUE) {
        // Scale the rendered hand by 1.0f (open) to 0.5f (fully squeezed).
        m_input.handScale[hand] = grabValue.currentState;
        if (grabValue.currentState > 0.9f) {
          XrHapticVibration vibration{XR_TYPE_HAPTIC_VIBRATION};
          vibration.amplitude = 0.5;
          vibration.duration  = XR_MIN_HAPTIC_DURATION;
          vibration.frequency = XR_FREQUENCY_UNSPECIFIED;

          XrHapticActionInfo hapticActionInfo{XR_TYPE_HAPTIC_ACTION_INFO};
          hapticActionInfo.action        = m_input.vibrateAction;
          hapticActionInfo.subactionPath = m_input.handSubactionPath[hand];
          // OPENXR_CHECK(xrApplyHapticFeedback(m_session, &hapticActionInfo,
          // (XrHapticBaseHeader *)&vibration), "Set Haptic Feedback Failed");
        }
      }

      getInfo.action = m_input.moveAction;
      XrActionStateVector2f moveValue{XR_TYPE_ACTION_STATE_VECTOR2F};
      OPENXR_CHECK(xrGetActionStateVector2f(m_session, &getInfo, &moveValue), "Get Move Action Value Failed");
      if (moveValue.isActive == XR_TRUE) {
        if (hand == 0) {
          if (abs(moveValue.currentState.x) > 0.1 || abs(moveValue.currentState.y) > 0.1) {
            diffMove.diffPos.x() = moveValue.currentState.x * 2.0f / 72.0f;
            diffMove.diffPos.z() = -moveValue.currentState.y * 2.0f / 72.0f;
          } else {
            diffMove.diffPos = Eigen::Vector3f::Zero();
          }
        } else {
          if (abs(moveValue.currentState.x) > 0.1) {
            Eigen::Vector3f delta_w = Eigen::Vector3f(0, -moveValue.currentState.x * 2 * M_PI / (5 * 72.0f), 0);
            diffMove.diffRot        = EmbeddedLie::quat_Exp(delta_w);
          } else {
            diffMove.diffRot = Eigen::Quaternionf::Identity();
          }
        }
      }

      getInfo.action = m_input.poseAction;
      XrActionStatePose poseState{XR_TYPE_ACTION_STATE_POSE};
      OPENXR_CHECK(xrGetActionStatePose(m_session, &getInfo, &poseState), "Get Action Pose State Failed");

      XrSpaceLocation location{XR_TYPE_SPACE_LOCATION};
      XrSpaceVelocity velocity{XR_TYPE_SPACE_VELOCITY, nullptr};
      location.next = &velocity;
      xrLocateSpace(m_input.handSpace[hand], m_headSpace, time, &location);
      if ((location.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT) && (location.locationFlags & XR_SPACE_LOCATION_ORIENTATION_VALID_BIT)
          && (velocity.velocityFlags & XR_SPACE_VELOCITY_LINEAR_VALID_BIT)
          && (velocity.velocityFlags & XR_SPACE_VELOCITY_ANGULAR_VALID_BIT))  // need test
      {
        relativeHandPose[hand].block<3, 3>(0, 0) = Eigen::Quaternionf(location.pose.orientation.w, location.pose.orientation.x,
                                                                      location.pose.orientation.y, location.pose.orientation.z)
                                                       .toRotationMatrix();
        relativeHandPose[hand].block<3, 1>(0, 3)
            = Eigen::Vector3f(location.pose.position.x, location.pose.position.y, location.pose.position.z);
        relativeHandVelocity[hand].head<3>() = Eigen::Vector3f(velocity.linearVelocity.x, velocity.linearVelocity.y, velocity.linearVelocity.z);
        relativeHandVelocity[hand].tail<3>()
            = Eigen::Vector3f(velocity.angularVelocity.x, velocity.angularVelocity.y, velocity.angularVelocity.z);
      }
      m_input.handActive[hand] = poseState.isActive;
    }

    // There were no subaction paths specified for the quit action, because we
    // don't care which hand did it.
    XrActionStateGetInfo getInfo{XR_TYPE_ACTION_STATE_GET_INFO, nullptr, m_input.quitAction, XR_NULL_PATH};
    XrActionStateBoolean quitValue{XR_TYPE_ACTION_STATE_BOOLEAN};
    OPENXR_CHECK(xrGetActionStateBoolean(m_session, &getInfo, &quitValue), "Get Action Boolean State Failed");
    if ((quitValue.isActive == XR_TRUE) && (quitValue.changedSinceLastSync == XR_TRUE) && (quitValue.currentState == XR_TRUE)) {
      OPENXR_CHECK(xrRequestExitSession(m_session), "Request Exit Session Failed");
    }

    // quiry for arm enable button
    getInfo.action = m_input.armEnableAction;
    XrActionStateBoolean armEnableValue{XR_TYPE_ACTION_STATE_BOOLEAN};
    OPENXR_CHECK(xrGetActionStateBoolean(m_session, &getInfo, &armEnableValue), "Get Arm Enable State Failed");
    if ((armEnableValue.isActive == XR_TRUE) && (armEnableValue.changedSinceLastSync == XR_TRUE) && (armEnableValue.currentState == XR_TRUE)) {
      // switch arm
      m_switch.arm_enable = !m_switch.arm_enable;
      XrHapticVibration vibration{XR_TYPE_HAPTIC_VIBRATION};
      vibration.amplitude = 0.5;
      if (m_switch.arm_enable)
        vibration.duration = 300000000;
      else
        vibration.duration = XR_MIN_HAPTIC_DURATION;
      vibration.frequency = XR_FREQUENCY_UNSPECIFIED;

      XrHapticActionInfo hapticActionInfo{XR_TYPE_HAPTIC_ACTION_INFO};
      hapticActionInfo.action        = m_input.vibrateAction;
      hapticActionInfo.subactionPath = m_input.handSubactionPath[1];
      OPENXR_CHECK(xrApplyHapticFeedback(m_session, &hapticActionInfo, (XrHapticBaseHeader *)&vibration), "Set Haptic Feedback Failed");
    }

    // quiry for car enable button
    getInfo.action = m_input.carEnableAction;
    XrActionStateBoolean carEnableValue{XR_TYPE_ACTION_STATE_BOOLEAN};
    OPENXR_CHECK(xrGetActionStateBoolean(m_session, &getInfo, &carEnableValue), "Get Car Enable State Failed");
    if ((carEnableValue.isActive == XR_TRUE) && (carEnableValue.changedSinceLastSync == XR_TRUE) && (carEnableValue.currentState == XR_TRUE)) {
      // switch car
      m_switch.car_enable = !m_switch.car_enable;
      XrHapticVibration vibration{XR_TYPE_HAPTIC_VIBRATION};
      vibration.amplitude = 0.5;
      if (m_switch.car_enable)
        vibration.duration = 300000000;
      else
        vibration.duration = XR_MIN_HAPTIC_DURATION;
      vibration.frequency = XR_FREQUENCY_UNSPECIFIED;

      XrHapticActionInfo hapticActionInfo{XR_TYPE_HAPTIC_ACTION_INFO};
      hapticActionInfo.action        = m_input.vibrateAction;
      hapticActionInfo.subactionPath = m_input.handSubactionPath[1];
      OPENXR_CHECK(xrApplyHapticFeedback(m_session, &hapticActionInfo, (XrHapticBaseHeader *)&vibration), "Set Haptic Feedback Failed");
    }

    // quiry if sync pose
    getInfo.action = m_input.poseSyncAction;
    XrActionStateBoolean syncPoseValue{XR_TYPE_ACTION_STATE_BOOLEAN};
    OPENXR_CHECK(xrGetActionStateBoolean(m_session, &getInfo, &syncPoseValue), "Get Sync Enable State Failed");
    if ((syncPoseValue.isActive == XR_TRUE) && (syncPoseValue.changedSinceLastSync == XR_TRUE) && (syncPoseValue.currentState == XR_TRUE)) {
      // switch arm
      m_switch.try_sync = true;
      XrHapticVibration vibration{XR_TYPE_HAPTIC_VIBRATION};
      vibration.amplitude = 0.5;
      vibration.duration  = XR_MIN_HAPTIC_DURATION;
      vibration.frequency = XR_FREQUENCY_UNSPECIFIED;

      XrHapticActionInfo hapticActionInfo{XR_TYPE_HAPTIC_ACTION_INFO};
      hapticActionInfo.action        = m_input.vibrateAction;
      hapticActionInfo.subactionPath = m_input.handSubactionPath[0];
      OPENXR_CHECK(xrApplyHapticFeedback(m_session, &hapticActionInfo, (XrHapticBaseHeader *)&vibration), "Set Haptic Feedback Failed");
    }

    // send cmd
    static uint32_t cmd_cnt = 0;
    const auto offset_quat  = Eigen::Quaternionf(0.5, 0.5, -0.5, -0.5);
    whole_body_msg currentCmd{};
    currentCmd.mask = 0;

    if (m_switch.car_enable) {
      currentCmd.mask |= 0b1100000000000000;
    }
    if (m_switch.arm_enable) {
      currentCmd.mask |= 0b1011000000000000;
    }

    if (m_switch.try_sync == true) {
      currentCmd.mask = 0b0000000010000000;
    }

    currentCmd.cnt  = cmd_cnt++;
    currentCmd.time = time;

    float *iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * carTransform.block<3, 1>(0, 3)).data();
    std::copy(iter, iter + 3, currentCmd.base_pos.begin());

    iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandPose[0].block<3, 1>(0, 3)).data();
    std::copy(iter, iter + 3, currentCmd.left_hand_pos.begin());
    iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandPose[1].block<3, 1>(0, 3)).data();
    std::copy(iter, iter + 3, currentCmd.right_hand_pos.begin());

    iter = (offset_quat * Eigen::Quaternionf(carTransform.block<3, 3>(0, 0)) * offset_quat.inverse()).coeffs().data();
    std::copy(iter, iter + 4, currentCmd.base_quat.begin());

    iter = (offset_quat * Eigen::Quaternionf(relativeHandPose[0].block<3, 3>(0, 0)) * offset_quat.inverse()).coeffs().data();
    std::copy(iter, iter + 4, currentCmd.left_hand_quat.begin());
    iter = (offset_quat * Eigen::Quaternionf(relativeHandPose[1].block<3, 3>(0, 0)) * offset_quat.inverse()).coeffs().data();
    std::copy(iter, iter + 4, currentCmd.right_hand_quat.begin());

    currentCmd.base_lin_vel = std::array{0.0f, 0.0f, 0.0f, 0.0f};
    //
    // iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandVelocity[0].head<3>()).data();
    // std::copy(iter, iter + 3, currentCmd.left_hand_lin_vel.begin());
    // iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandVelocity[1].head<3>()).data();
    // std::copy(iter, iter + 3, currentCmd.right_hand_lin_vel.begin());

    currentCmd.base_ang_vel = std::array{0.0f, 0.0f, 0.0f, 0.0f};
    //
    // iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandVelocity[0].tail<3>()).data();
    // std::copy(iter, iter + 3, currentCmd.left_hand_ang_vel.begin());
    // iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandVelocity[1].tail<3>()).data();
    // std::copy(iter, iter + 3, currentCmd.right_hand_ang_vel.begin());

    currentCmd.left_grip  = m_input.handScale[0];
    currentCmd.right_grip = m_input.handScale[1];

    cmdMsgQueue->enqueue(currentCmd);

    pose_msg poseMsg;
    poseMsg.position    = currentCmd.base_pos;
    poseMsg.orientation = currentCmd.base_quat;
    poseMsgQueue->enqueue(poseMsg);

    std::pair<pose_msg, pose_msg> arm_pose_msg;
    iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandPose[0].block<3, 1>(0, 3)).data();
    std::copy(iter, iter + 3, arm_pose_msg.first.position.begin());
    iter = Eigen::Vector3f(offset_quat.toRotationMatrix() * relativeHandPose[1].block<3, 1>(0, 3)).data();
    std::copy(iter, iter + 3, arm_pose_msg.second.position.begin());
    iter = (offset_quat * Eigen::Quaternionf(relativeHandPose[0].block<3, 3>(0, 0)) * offset_quat.inverse()
            * Eigen::Quaternionf(Eigen::AngleAxisf(M_PI / 2, Eigen::Vector3f::UnitY())))
               .coeffs()
               .data();
    std::copy(iter, iter + 4, arm_pose_msg.first.orientation.begin());
    iter = (offset_quat * Eigen::Quaternionf(relativeHandPose[1].block<3, 3>(0, 0)) * offset_quat.inverse()
            * Eigen::Quaternionf(Eigen::AngleAxisf(M_PI / 2, Eigen::Vector3f::UnitY())))
               .coeffs()
               .data();
    std::copy(iter, iter + 4, arm_pose_msg.second.orientation.begin());
    armMsgQueue->enqueue(arm_pose_msg);

    // get feedback here
    std::array<Eigen::Matrix4f, 6> arm_fb_msg;
    if (armFbMsgQueue->dequeue(arm_fb_msg)) {
      arm_bottom[0] = arm_fb_msg[0];
      arm_middle[0] = arm_fb_msg[1];
      arm_top[0]    = arm_fb_msg[2];
      arm_bottom[1] = arm_fb_msg[3];
      arm_middle[1] = arm_fb_msg[4];
      arm_top[1]    = arm_fb_msg[5];
    }

    // get arm model

    // Eigen::Matrix4f pose_in        = Eigen::Matrix4f::Identity();
    // pose_in.block<3, 3>(0, 0)      = Eigen::Quaternionf(currentCmd.left_hand_quat.begin()).toRotationMatrix();
    // pose_in.block<3, 1>(0, 3)      = Eigen::Vector3f(currentCmd.left_hand_pos.begin());
    // Eigen::Matrix4d pose_out       = Eigen::Matrix4d::Identity();
    // Eigen::Matrix4d pose_in_double = pose_in.cast<double>();
    // if (left_arm.getPredictedPose(pose_out, pose_in_double)) {
    //   Eigen::Matrix4f tmpTf   = pose_out.cast<float>();
    //   tmpTf.block<3, 3>(0, 0) = (offset_quat.toRotationMatrix().transpose() * tmpTf.block<3, 3>(0, 0) *
    //   offset_quat.toRotationMatrix()).eval(); tmpTf.block<3, 1>(0, 3) = (offset_quat.toRotationMatrix().transpose() * tmpTf.block<3, 1>(0,
    //   3)).eval(); viewHandPose[0]         = currentTransform * tmpTf;
    // }
    // pose_in.block<3, 3>(0, 0) = Eigen::Quaternionf(currentCmd.right_hand_quat.begin()).toRotationMatrix();
    // pose_in.block<3, 1>(0, 3) = Eigen::Vector3f(currentCmd.right_hand_pos.begin());
    // pose_out                  = Eigen::Matrix4d::Identity();
    // pose_in_double            = pose_in.cast<double>();
    // if (right_arm.getPredictedPose(pose_out, pose_in_double)) {
    //   Eigen::Matrix4f tmpTf   = pose_out.cast<float>();
    //   tmpTf.block<3, 3>(0, 0) = (offset_quat.toRotationMatrix().transpose() * tmpTf.block<3, 3>(0, 0) *
    //   offset_quat.toRotationMatrix()).eval(); tmpTf.block<3, 1>(0, 3) = (offset_quat.toRotationMatrix().transpose() * tmpTf.block<3, 1>(0,
    //   3)).eval(); viewHandPose[1]         = currentTransform * tmpTf;
    // }
    viewHandPose[0] = currentTransform * relativeHandPose[0];
    viewHandPose[1] = currentTransform * relativeHandPose[1];
  }

  void RenderFrame() override {
    XrFrameState frameState{XR_TYPE_FRAME_STATE};
    XrFrameWaitInfo frameWaitInfo{XR_TYPE_FRAME_WAIT_INFO};
    OPENXR_CHECK(xrWaitFrame(m_session, &frameWaitInfo, &frameState), "Failed to wait for XR Frame.");
    // xrWaitFrame(m_session, &frameWaitInfo, &frameState);

    // sync action
    PollActions(frameState.predictedDisplayTime);

    // Tell the OpenXR compositor that the application is beginning the frame.
    XrFrameBeginInfo frameBeginInfo{XR_TYPE_FRAME_BEGIN_INFO};
    OPENXR_CHECK(xrBeginFrame(m_session, &frameBeginInfo), "Failed to begin the XR Frame.");
    // xrBeginFrame(m_session, &frameBeginInfo);

    std::vector<XrCompositionLayerBaseHeader *> layers;
    XrCompositionLayerProjection layer{XR_TYPE_COMPOSITION_LAYER_PROJECTION};
    std::vector<XrCompositionLayerProjectionView> projectionLayerViews;
    if (frameState.shouldRender == XR_TRUE) {
      if (RenderLayer(frameState.predictedDisplayTime, projectionLayerViews, layer)) {
        layers.push_back(reinterpret_cast<XrCompositionLayerBaseHeader *>(&layer));
      }
    }

    XrFrameEndInfo frameEndInfo{XR_TYPE_FRAME_END_INFO};
    frameEndInfo.displayTime          = frameState.predictedDisplayTime;
    frameEndInfo.environmentBlendMode = m_environmentBlendMode;
    frameEndInfo.layerCount           = (uint32_t)layers.size();
    frameEndInfo.layers               = layers.data();
    OPENXR_CHECK(xrEndFrame(m_session, &frameEndInfo), "Failed to end the XR Frame.");
    // xrEndFrame(m_session, &frameEndInfo);
    return;
  }

  bool IsSessionRunning() const override { return m_sessionRunning; }

  bool RenderLayer(XrTime predictedDisplayTime, std::vector<XrCompositionLayerProjectionView> &projectionLayerViews,
                   XrCompositionLayerProjection &layer) {
    std::vector<XrView> views(m_viewConfigurationViews.size(), {XR_TYPE_VIEW});
    XrViewState viewState{XR_TYPE_VIEW_STATE};  // Will contain information on whether the position
                                                // and/or orientation is valid and/or tracked.
    XrViewLocateInfo viewLocateInfo{XR_TYPE_VIEW_LOCATE_INFO};
    viewLocateInfo.viewConfigurationType = m_viewConfiguration;
    viewLocateInfo.displayTime           = predictedDisplayTime;
    viewLocateInfo.space                 = m_localSpace;
    uint32_t viewCount                   = 0;
    XrResult result = xrLocateViews(m_session, &viewLocateInfo, &viewState, static_cast<uint32_t>(views.size()), &viewCount, views.data());
    if (result != XR_SUCCESS) {
      std::cerr << "Failed to locate views" << std::endl;
      return false;
    }

    projectionLayerViews.resize(viewCount);

    // render views
    for (int i = 0; i < viewCount; i++) {
      // aquire swapchain images of different views
      SwapchainInfo &colorSwapchainInfo = m_colorSwapchainInfos[i];
      SwapchainInfo &depthSwapchainInfo = m_depthSwapchainInfos[i];

      uint32_t colorImageIndex = 0;
      uint32_t depthImageIndex = 0;
      XrSwapchainImageAcquireInfo acquireInfo{XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO};
      OPENXR_CHECK(xrAcquireSwapchainImage(colorSwapchainInfo.swapchain, &acquireInfo, &colorImageIndex),
                   "Failed to acquire Image from the Color Swapchian");
      // xrAcquireSwapchainImage(colorSwapchainInfo.swapchain, &acquireInfo,
      // &colorImageIndex);
      OPENXR_CHECK(xrAcquireSwapchainImage(depthSwapchainInfo.swapchain, &acquireInfo, &depthImageIndex),
                   "Failed to acquire Image from the Depth Swapchian");
      // xrAcquireSwapchainImage(depthSwapchainInfo.swapchain, &acquireInfo,
      // &depthImageIndex);

      XrSwapchainImageWaitInfo waitInfo = {XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO};
      waitInfo.timeout                  = XR_INFINITE_DURATION;
      OPENXR_CHECK(xrWaitSwapchainImage(colorSwapchainInfo.swapchain, &waitInfo), "Failed to wait for Image from the Color Swapchain");
      OPENXR_CHECK(xrWaitSwapchainImage(depthSwapchainInfo.swapchain, &waitInfo), "Failed to wait for Image from the Depth Swapchain");
      // xrWaitSwapchainImage(colorSwapchainInfo.swapchain, &waitInfo);
      // xrWaitSwapchainImage(depthSwapchainInfo.swapchain, &waitInfo);
      //*******************************************/
      //**************Start rendering**************/
      //*******************************************/

      const uint32_t &width          = m_viewConfigurationViews[i].recommendedImageRectWidth;
      const uint32_t &height         = m_viewConfigurationViews[i].recommendedImageRectHeight;
      GraphicsAPI::Viewport viewport = {0.0f, 0.0f, (float)width, (float)height, 0.0f, 1.0f};
      GraphicsAPI::Rect2D scissor    = {{(int32_t)0, (int32_t)0}, {width, height}};
      float nearZ                    = 0.05f;
      float farZ                     = 200.0f;

      // Fill render view infos
      projectionLayerViews[i]                           = {XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW};
      projectionLayerViews[i].pose                      = views[i].pose;
      projectionLayerViews[i].fov                       = views[i].fov;
      projectionLayerViews[i].subImage.swapchain        = colorSwapchainInfo.swapchain;
      projectionLayerViews[i].subImage.imageRect.offset = {0, 0};
      projectionLayerViews[i].subImage.imageRect.extent = {static_cast<int32_t>(width), static_cast<int32_t>(height)};
      projectionLayerViews[i].subImage.imageArrayIndex  = 0;

      Eigen::Matrix4f proj
          = CreateProjectionMatrix(views[i].fov.angleLeft, views[i].fov.angleRight, views[i].fov.angleUp, views[i].fov.angleDown, nearZ, farZ);
      Eigen::Matrix4f toView   = Eigen::Matrix4f::Identity();
      toView.block<3, 3>(0, 0) = Eigen::Quaternionf(views[i].pose.orientation.w, views[i].pose.orientation.x, views[i].pose.orientation.y,
                                                    views[i].pose.orientation.z)
                                     .toRotationMatrix();
      toView.block<3, 1>(0, 3) = Eigen::Vector3f(views[i].pose.position.x, views[i].pose.position.y, views[i].pose.position.z);
      // toView.block<3, 1>(0, 3)      = Eigen::Vector3f(0, 0, 0);
      Eigen::Matrix4f diffTransform = lastTransform.inverse() * toView;
      // Eigen::Matrix4f diffTransform = lastView[i].inverse() * toView;

      currentTransform = currentTransform * diffTransform;

      carTransform.block<3, 3>(0, 0) = (carTransform.block<3, 3>(0, 0) * diffMove.diffRot.toRotationMatrix()).eval();
      carTransform.block<3, 1>(0, 3) += (carTransform.block<3, 3>(0, 0) * diffMove.diffPos).eval();

      auto tmp_diff_move = (carTransform.block<3, 3>(0, 0) * diffMove.diffPos).eval();
      tmp_diff_move.y()  = 0;
      currentTransform.block<3, 1>(0, 3) += tmp_diff_move;

      currentTransform.block<3, 3>(0, 0) = (diffMove.diffRot.toRotationMatrix() * currentTransform.block<3, 3>(0, 0)).eval();  // comment this

      lastTransform = toView;

      Eigen::Matrix4f toViewInv = currentTransform.inverse();
      Eigen::Matrix4f view      = proj * toViewInv;
      auto _viewport            = Eigen::Vector2f(viewport.width, viewport.height);

      m_graphicsAPI->BeginRendering();
      if (m_environmentBlendMode == XR_ENVIRONMENT_BLEND_MODE_OPAQUE) {
        // VR mode use a background color.
        m_graphicsAPI->ClearColor(colorSwapchainInfo.imageViews[colorImageIndex], 0.16f, 0.22f, 0.21f, 1.0f);
      } else {
        // In AR mode make the background color black.
        m_graphicsAPI->ClearColor(colorSwapchainInfo.imageViews[colorImageIndex], 0.00f, 0.00f, 0.00f, 0.0f);
      }

      m_graphicsAPI->ClearDepth(depthSwapchainInfo.imageViews[depthImageIndex], 1.0f);
      m_graphicsAPI->SetRenderAttachments(&colorSwapchainInfo.imageViews[colorImageIndex], 1, depthSwapchainInfo.imageViews[depthImageIndex],
                                          width, height, m_pipeline);
      m_graphicsAPI->SetViewports(&viewport, 1);
      m_graphicsAPI->SetScissors(&scissor, 1);
      // auto start = std::chrono::high_resolution_clock::now();
      renderCloud(view, toViewInv, _viewport);
      // auto end = std::chrono::high_resolution_clock::now();
      // auto duration =
      // std::chrono::duration_cast<std::chrono::microseconds>(end - start);
      // std::cout << "render cloud time: " << duration.count() << "us" <<
      // std::endl;

      // switch to mesh pipeline
      m_graphicsAPI->SetRenderAttachments(&colorSwapchainInfo.imageViews[colorImageIndex], 1, depthSwapchainInfo.imageViews[depthImageIndex],
                                          width, height, m_pipeline_model);
      m_graphicsAPI->SetViewports(&viewport, 1);
      m_graphicsAPI->SetScissors(&scissor, 1);

      renderMesh(view, toViewInv, _viewport);

      m_graphicsAPI->SetRenderAttachments(&colorSwapchainInfo.imageViews[colorImageIndex], 1, depthSwapchainInfo.imageViews[depthImageIndex],
                                          width, height, cam_pipeline);
      m_graphicsAPI->SetViewports(&viewport, 1);
      m_graphicsAPI->SetScissors(&scissor, 1);
      // auto start = std::chrono::high_resolution_clock::now();
      renderCam(view, toViewInv, _viewport);

      m_graphicsAPI->EndRendering();
      //*******************************************/
      //***************End rendering***************/
      //*******************************************/

      XrSwapchainImageReleaseInfo releaseInfo{XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO};
      OPENXR_CHECK(xrReleaseSwapchainImage(colorSwapchainInfo.swapchain, &releaseInfo), "Failed to release Image back to the Color Swapchain");
      OPENXR_CHECK(xrReleaseSwapchainImage(depthSwapchainInfo.swapchain, &releaseInfo), "Failed to release Image back to the Depth Swapchain");
      // xrReleaseSwapchainImage(colorSwapchainInfo.swapchain, &releaseInfo);
      // xrReleaseSwapchainImage(depthSwapchainInfo.swapchain, &releaseInfo);
    }

    layer.space      = m_localSpace;
    layer.layerFlags = 0;
    layer.viewCount  = (uint32_t)projectionLayerViews.size();
    layer.views      = projectionLayerViews.data();
    return true;
  }

  void renderCam(Eigen::Matrix4f &viewProj, Eigen::Matrix4f &view, Eigen::Vector2f &viewport) {
    m_graphicsAPI->SetPipeline(cam_pipeline);
    m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0, sizeof(CameraConstants), &cameraConstants);

    std::shared_ptr<render_msg> camMsg;
    if (camMsgQueue->dequeue(camMsg))  // new
    {
      uint8_t free_buffer = (cam_buffer_state.load().active_index + 1) % 2;
      cam_low_priority_arena.enqueue([free_buffer, camMsg, this]() {
        m_graphicsAPI->SetBufferData(reinterpret_cast<void *>(cam_cloudBuffer[free_buffer]), 0,
                                     sizeof(uint64_t) * camMsg->points_resource->size(),
                                     reinterpret_cast<void *>(camMsg->points_resource->data()));
        m_graphicsAPI->SetBufferData(reinterpret_cast<void *>(cam_colorBuffer[free_buffer]), 0,
                                     sizeof(uint64_t) * camMsg->colors_resource->size(),
                                     reinterpret_cast<void *>(camMsg->colors_resource->data()));
        CloudBufferState new_state{};
        new_state.active_index = free_buffer;
        new_state.init_size    = camMsg->size;
        new_state.init_offset  = camMsg->offset;
        cam_buffer_state.store(new_state, std::memory_order_release);
      });
    }
    auto curr_buffer_state     = cam_buffer_state.load(std::memory_order_acquire);
    cameraConstants.viewProj   = viewProj;
    cameraConstants.view       = view;
    cameraConstants.padding[0] = curr_buffer_state.init_offset;
    m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0, sizeof(CameraConstants), &cameraConstants);
    m_graphicsAPI->SetDescriptor({0, m_uniformBuffer_Camera, GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, false, 0, sizeof(CameraConstants)});
    m_graphicsAPI->SetDescriptor({1, cam_cloudBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, true, 0, sizeof(uint64_t) * curr_buffer_state.init_size});
    m_graphicsAPI->SetDescriptor({2, cam_colorBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, true, 0, sizeof(uint32_t) * curr_buffer_state.init_size});
    m_graphicsAPI->SetDescriptor({3, cam_normalBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::FRAGMENT, true, 0, sizeof(uint32_t) * curr_buffer_state.init_size});

    m_graphicsAPI->UpdateDescriptors();
    m_graphicsAPI->Draw(curr_buffer_state.init_size);
    return;
  }

  void renderCloud(Eigen::Matrix4f &viewProj, Eigen::Matrix4f &view, Eigen::Vector2f &viewport) {
    // cameraConstants.padding = viewport;
    // point cloud is already stored in the class

    m_graphicsAPI->SetPipeline(m_pipeline);
    m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0, sizeof(CameraConstants), &cameraConstants);
    // m_graphicsAPI->SetBufferData(m_cloudBuffer[0], 0, sizeof(uint64_t) *
    // compressedPoints->size(), reinterpret_cast<void
    // *>(compressedPoints->data()));
    //  m_graphicsAPI->SetBufferData(m_cloudBuffer[0], 0, sizeof(uint64_t) *
    //  5000, reinterpret_cast<void *>(compressedPoints->data()));
    // m_graphicsAPI->SetBufferData(m_colorBuffer, 0, sizeof(float) * 4 *
    // pointCloudPtr->size(), reinterpret_cast<void
    // *>(pointCloudPtr->getColorBasePtr()));
    //--------------------------------uncomment this
    std::shared_ptr<render_msg> mapMsg;

    if (mapMsgQueue->dequeue(mapMsg))  // new
    {
      uint8_t free_buffer = (buffer_state.load().active_index + 1) % 2;
      // std::thread copy_worker([free_buffer, buffer_copy, mapMsg, this]() ->
      // void
      //                         {
      //                             m_graphicsAPI->SetBufferData(reinterpret_cast<void
      //                             *>(m_cloudBuffer[free_buffer]), 0,
      //                             sizeof(uint64_t) *
      //                             mapMsg->points_resource->size(),
      //                             reinterpret_cast<void
      //                             *>(mapMsg->points_resource->data()));
      //                             init_size =
      //                             mapMsg->points_resource->size();
      //                             avtive_cloud_buffer.store(free_buffer);
      //                             return; });
      // copy_worker.detach();

      low_priority_arena.enqueue([free_buffer, mapMsg, this]() {
        m_graphicsAPI->SetBufferData(reinterpret_cast<void *>(m_cloudBuffer[free_buffer]), 0,
                                     sizeof(uint64_t) * mapMsg->points_resource->size(),
                                     reinterpret_cast<void *>(mapMsg->points_resource->data()));
        m_graphicsAPI->SetBufferData(reinterpret_cast<void *>(m_colorBuffer[free_buffer]), 0,
                                     sizeof(uint64_t) * mapMsg->colors_resource->size(),
                                     reinterpret_cast<void *>(mapMsg->colors_resource->data()));
        // m_graphicsAPI->SetBufferData(reinterpret_cast<void
        // *>(m_normalBuffer[free_buffer]), 0,
        //         sizeof(uint64_t) * mapMsg->normals_resource->size(),
        //         reinterpret_cast<void *>(mapMsg->normals_resource->data()));
        // m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0,
        // sizeof(CameraConstants), &cameraConstants);

        CloudBufferState new_state{};
        new_state.active_index = free_buffer;
        new_state.init_size    = mapMsg->size;
        new_state.init_offset  = mapMsg->offset;
        buffer_state.store(new_state, std::memory_order_release);
        // avtive_color_buffer.store(free_buffer);
      });
    }
    // --------------------------------uncomment this
    //  m_graphicsAPI->SetBufferData(m_cloudBuffer[0], 0, sizeof(uint64_t) *
    //  compressedPoints->size(), reinterpret_cast<void
    //  *>(compressedPoints->data()));

    auto curr_buffer_state     = buffer_state.load(std::memory_order_acquire);
    cameraConstants.viewProj   = viewProj;
    cameraConstants.view       = view;
    cameraConstants.padding[0] = curr_buffer_state.init_offset;
    m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0, sizeof(CameraConstants), &cameraConstants);
    m_graphicsAPI->SetDescriptor({0, m_uniformBuffer_Camera, GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, false, 0, sizeof(CameraConstants)});
    m_graphicsAPI->SetDescriptor({1, m_cloudBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, true, 0, sizeof(uint64_t) * curr_buffer_state.init_size});
    m_graphicsAPI->SetDescriptor({2, m_colorBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, true, 0, sizeof(uint32_t) * curr_buffer_state.init_size});
    m_graphicsAPI->SetDescriptor({3, m_normalBuffer[curr_buffer_state.active_index], GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::FRAGMENT, true, 0, sizeof(uint32_t) * curr_buffer_state.init_size});

    m_graphicsAPI->UpdateDescriptors();
    m_graphicsAPI->Draw(curr_buffer_state.init_size);
    return;
  }

  void renderMesh(Eigen::Matrix4f &viewProj, Eigen::Matrix4f &view, Eigen::Vector2f &viewport) {
    cameraConstants.viewProj = viewProj;
    cameraConstants.view     = view;
    // cameraConstants.padding = viewport;

    nav_state_msg real_state;
    if (navMsgQueue->dequeue(real_state)) {
      const auto offset_quat   = Eigen::Quaternionf(0.5, 0.5, -0.5, -0.5).inverse();
      Eigen::Vector3f position = Eigen::Vector3f(real_state.base_pos[0], real_state.base_pos[1], real_state.base_pos[2]);
      position                 = offset_quat.toRotationMatrix() * position;
      Eigen::Quaternionf quaternion(real_state.base_quat.data());
      quaternion                      = offset_quat * quaternion * offset_quat.inverse();
      realTransform.block<3, 3>(0, 0) = quaternion.toRotationMatrix();
      realTransform.block<3, 1>(0, 3) = position;

      // Eigen::Vector<float, 6> left_joints  = Eigen::Vector<float, 6>(real_state.left_joints.begin());
      // Eigen::Vector<float, 6> right_joints = Eigen::Vector<float, 6>(real_state.right_joints.begin());
      // Eigen::Vector<double, 6> left__      = left_joints.cast<double>();
      // Eigen::Vector<double, 6> right__     = right_joints.cast<double>();
      // feedback_end_left                    = left_arm.getFeedbackPose(left__).cast<float>();
      // feedback_end_right                   = right_arm.getFeedbackPose(right__).cast<float>();

      grip[0].block<3, 1>(0, 3)
          = Eigen::Vector3f(real_state.left_grip_one_pos[0], real_state.left_grip_one_pos[1], real_state.left_grip_one_pos[2]);
      grip[0].block<3, 3>(0, 0) = Eigen::Quaternionf(real_state.left_grip_one_quat.data()).toRotationMatrix();
      grip[0]                   = RotateMatrix4f(grip[0]).eval();

      grip[1].block<3, 1>(0, 3)
          = Eigen::Vector3f(real_state.left_grip_two_pos[0], real_state.left_grip_two_pos[1], real_state.left_grip_two_pos[2]);
      grip[1].block<3, 3>(0, 0) = Eigen::Quaternionf(real_state.left_grip_two_quat.data()).toRotationMatrix();
      grip[1]                   = RotateMatrix4f(grip[1]).eval();

      grip[2].block<3, 1>(0, 3)
          = Eigen::Vector3f(real_state.right_grip_one_pos[0], real_state.right_grip_one_pos[1], real_state.right_grip_one_pos[2]);
      grip[2].block<3, 3>(0, 0) = Eigen::Quaternionf(real_state.right_grip_one_quat.data()).toRotationMatrix();
      grip[2]                   = RotateMatrix4f(grip[2]).eval();

      grip[3].block<3, 1>(0, 3)
          = Eigen::Vector3f(real_state.right_grip_two_pos[0], real_state.right_grip_two_pos[1], real_state.right_grip_two_pos[2]);
      grip[3].block<3, 3>(0, 0) = Eigen::Quaternionf(real_state.right_grip_two_quat.data()).toRotationMatrix();
      grip[3]                   = RotateMatrix4f(grip[3]).eval();
      // sync
      if (real_state.mask & 0b0000000001000000) {
        currentTransform  = realTransform;
        carTransform      = realTransform;
        m_switch.try_sync = false;
        XrHapticVibration vibration{XR_TYPE_HAPTIC_VIBRATION};
        vibration.amplitude = 0.8;
        vibration.duration  = 300000000;
        vibration.frequency = XR_FREQUENCY_UNSPECIFIED;
        XrHapticActionInfo hapticActionInfo{XR_TYPE_HAPTIC_ACTION_INFO};
        hapticActionInfo.action        = m_input.vibrateAction;
        hapticActionInfo.subactionPath = m_input.handSubactionPath[0];
        OPENXR_CHECK(xrApplyHapticFeedback(m_session, &hapticActionInfo, (XrHapticBaseHeader *)&vibration), "Set Haptic Feedback Failed");
      }
    }

    m_graphicsAPI->SetPipeline(m_pipeline_model);
    if (m_switch.arm_enable) {
      cameraConstants.padding[1] = 1;
    } else {
      cameraConstants.padding[1] = 0;
    }
    m_graphicsAPI->SetBufferData(m_uniformBuffer_Camera, 0, sizeof(CameraConstants), &cameraConstants);
    m_graphicsAPI->SetDescriptor({0, m_uniformBuffer_Camera, GraphicsAPI::DescriptorInfo::Type::BUFFER,
                                  GraphicsAPI::DescriptorInfo::Stage::VERTEX, false, 0, sizeof(CameraConstants)});
    {
      // do transform
      std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> tmp_vertexs;
      for (int i = 0; i < indexes.size(); i++) {
        if (i < 8) {
          tmp_vertexs.push_back(realTransform * vertexs[i]);
        } else if (i >= 0 && i < 16) {
          tmp_vertexs.push_back(carTransform * vertexs[i]);
        } else if (i >= 16 && i < 24) {
          tmp_vertexs.push_back(viewHandPose[0] * vertexs[i]);
        } else if (i >= 24 && i < 32) {
          tmp_vertexs.push_back(viewHandPose[1] * vertexs[i]);
        } else if (i >= 32 && i < 40) {
          tmp_vertexs.push_back(feedback_end_left * vertexs[i]);
        } else if (i >= 40 && i < 48) {
          tmp_vertexs.push_back(feedback_end_right * vertexs[i]);
        } else if (i >= 48 && i < 56) {
          // arm0 botton stick
          tmp_vertexs.push_back(realTransform * grip[0] * vertexs[i]);
        } else if (i >= 56 && i < 64) {
          // arm0 middle stick
          tmp_vertexs.push_back(realTransform * grip[1] * vertexs[i]);
        } else if (i >= 64 && i < 72) {
          // arm0 top stick
          tmp_vertexs.push_back(realTransform * grip[2] * vertexs[i]);
        } else if (i >= 72 && i < 80) {
          // arm1 botton stick
          tmp_vertexs.push_back(realTransform * grip[3] * vertexs[i]);
        }
        // else if (i >= 80 && i < 88) {
        //   // arm1 middle stick
        //   tmp_vertexs.push_back(realTransform * arm_middle[1] * vertexs[i]);
        // } else if (i >= 88 && i < 96) {
        //   // arm1 top stick
        //   tmp_vertexs.push_back(realTransform * arm_top[1] * vertexs[i]);
        // }
        else {
          tmp_vertexs.push_back(realTransform * grip[3] * vertexs[i]);
        }
      }
      m_graphicsAPI->SetBufferData(m_vertexBuffer, 0, sizeof(float) * 4 * tmp_vertexs.size(), tmp_vertexs.data());
      m_graphicsAPI->SetBufferData(m_indexBuffer, 0, sizeof(int) * indexes.size(), indexes.data());  // TODO: edit here
    }
    m_graphicsAPI->UpdateDescriptors();
    m_graphicsAPI->SetVertexBuffers(&m_vertexBuffer, 1);
    m_graphicsAPI->SetIndexBuffer(m_indexBuffer);

    m_graphicsAPI->DrawIndexed(indexes.size(), 1, 0, 0, 0);
    // m_graphicsAPI->Draw(3);

    return;
  }

  XrEnvironmentBlendMode GetPreferredBlendMode() const override {
    uint32_t count;
    OPENXR_CHECK(xrEnumerateEnvironmentBlendModes(m_xrInstance, m_xrSystemId, m_viewConfiguration, 0, &count, nullptr),
                 "Failed to enumerate Environment Blend Modes.");
    // xrEnumerateEnvironmentBlendModes(m_xrInstance, m_xrSystemId,
    // m_viewConfiguration, 0, &count, nullptr);
    assert(count > 0);

    std::vector<XrEnvironmentBlendMode> blendModes(count);
    OPENXR_CHECK(xrEnumerateEnvironmentBlendModes(m_xrInstance, m_xrSystemId, m_viewConfiguration, count, &count, blendModes.data()),
                 "Failed to enumerate Environment Blend Modes.");
    // xrEnumerateEnvironmentBlendModes(m_xrInstance, m_xrSystemId,
    // m_viewConfiguration, count, &count,
    //                 blendModes.data());
    for (const auto &blendMode : blendModes) {
      if (m_acceptableBlendModes.count(blendMode)) return blendMode;
    }
    return XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
  }

  void AddVertex(float x, float y, float z) override {
    Eigen::Vector4f vertex(x, y, z, 1.0f);
    Eigen::Vector3f norm(0.0f, 0.0f, 0.0f);
    meshPtr->addVertex(vertex, norm);
    return;
  }

  void AddIndex(uint32_t vertex1, uint32_t vertex2, uint32_t vertex3) override {
    std::array<uint32_t, 3> index_set = {vertex1, vertex2, vertex3};
    meshPtr->addTriangle(index_set);
    return;
  }

  void LoadVectexShader(const std::vector<char> &shader) override {
    vertexSource = shader;
    return;
  }

  void LoadFragmentShader(const std::vector<char> &shader) override {
    fragmentSource = shader;
    return;
  }

  void LoadMeshVectexShader(const std::vector<char> &shader) override {
    meshVertexSource = shader;
    return;
  }

  void LoadMeshFragmentShader(const std::vector<char> &shader) override {
    meshFragmentSource = shader;
    return;
  }

  void SetCmdMsg(MsgQueue *msg_queue) override {
    cmdMsgQueue = msg_queue;
    return;
  }
  void SetPoseMsg(MsgQueue *msg_queue) override {
    poseMsgQueue = msg_queue;
    return;
  }
  void SetMapMsg(MsgQueue *msg_queue) override {
    mapMsgQueue = msg_queue;
    return;
  }
  void SetCamMsg(MsgQueue *msg_queue) override {
    camMsgQueue = msg_queue;
    return;
  }
  void SetNavMsg(MsgQueue *msg_queue) override {
    navMsgQueue = msg_queue;
    return;
  }
  void SetArmMsg(MsgQueue *msg_queue) override {
    armMsgQueue = msg_queue;
    return;
  }
  void SetArmFbMsg(MsgQueue *msg_queue) override {
    armFbMsgQueue = msg_queue;
    return;
  }
  XrInstance m_xrInstance{XR_NULL_HANDLE};
  XrSession m_xrSession{XR_NULL_HANDLE};
  XrSpace m_localSpace{XR_NULL_HANDLE};
  XrSpace m_headSpace{XR_NULL_HANDLE};
  XrSystemId m_xrSystemId{XR_NULL_SYSTEM_ID};
  XrSystemProperties m_systemProperties       = {XR_TYPE_SYSTEM_PROPERTIES};
  XrViewConfigurationType m_viewConfiguration = XR_VIEW_CONFIGURATION_TYPE_MAX_ENUM;
  std::vector<XrViewConfigurationView> m_viewConfigurationViews;

  XrSession m_session                        = {};
  XrSessionState m_sessionState              = XR_SESSION_STATE_UNKNOWN;
  std::unique_ptr<GraphicsAPI> m_graphicsAPI = nullptr;

  struct SwapchainInfo {
    XrSwapchain swapchain   = XR_NULL_HANDLE;
    int64_t swapchainFormat = 0;
    std::vector<void *> imageViews;
  };
  std::vector<SwapchainInfo> m_colorSwapchainInfos = {};
  std::vector<SwapchainInfo> m_depthSwapchainInfos = {};

  bool m_sessionRunning{false};
  bool m_applicationRunning{true};

  const int totalPointNum;
  const XrFormFactor m_formFactor  = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
  const GraphicsAPI_Type m_apiType = GraphicsAPI_Type::VULKAN;  // for This application fix this to Vulkan
  const std::set<XrEnvironmentBlendMode> m_acceptableBlendModes;
  XrEnvironmentBlendMode m_environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_MAX_ENUM;

  std::shared_ptr<IPlatformPlugin> m_platformPlugin;

  // AlignedVector<uint64_t, 256> *compressedPoints;

  std::shared_ptr<Mesh> meshPtr;

  std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> vertexs;
  std::vector<int> indexes;

  void *m_cloudBuffer[2]  = {nullptr, nullptr};
  void *m_colorBuffer[2]  = {nullptr, nullptr};
  void *m_normalBuffer[2] = {nullptr, nullptr};

  int num_vertex       = 0;
  void *m_vertexBuffer = nullptr;
  void *m_indexBuffer  = nullptr;
  // Camera values constant buffer for the shaders.
  void *m_uniformBuffer_Camera = nullptr;

  // The pipeline is a graphics-API specific state object.
  void *m_pipeline = nullptr;

  void *m_pipeline_model = nullptr;

  void *cam_pipeline = nullptr;

  std::vector<char> vertexSource;
  std::vector<char> fragmentSource;
  std::vector<char> meshVertexSource;
  std::vector<char> meshFragmentSource;

  MsgQueue *cmdMsgQueue;
  MsgQueue *mapMsgQueue;
  MsgQueue *poseMsgQueue;
  MsgQueue *navMsgQueue;
  MsgQueue *camMsgQueue;
  MsgQueue *armMsgQueue;
  MsgQueue *armFbMsgQueue;

  tbb::task_arena low_priority_arena;
  tbb::task_arena cam_low_priority_arena;
  tbb::task_group tg;

  struct CloudBufferState {
    uint8_t active_index;
    size_t init_size;
    uint32_t init_offset;
  };
  std::atomic<CloudBufferState> buffer_state;
  std::atomic<CloudBufferState> cam_buffer_state;
};

std::shared_ptr<IOpenXrApplication> CreateOpenXrProgram(const std::shared_ptr<IPlatformPlugin> &platformPlugin, const int pointNum) {
  return std::make_shared<OpenXrApplication>(platformPlugin, pointNum);
}