#pragma once
#include "base_type.hpp"
#include "platformplugin.h"
#include <memory>
#include <vector>

#include "ipc/itc/MsgQueue.hpp"
#include "ipc/itc/backend/RingBuf.hpp"
// #include "protocol.hpp"
/// @brief
class IOpenXrApplication {
public:
  IOpenXrApplication() {};
  virtual ~IOpenXrApplication() noexcept = default;

  // Create an Instance and other basic instance-level initialization.
  virtual void CreateInstance() = 0;

  // Select a System for the view configuration specified in the Options
  virtual void InitializeSystem() = 0;

  // Initialize the graphics device for the selected system.
  virtual void InitializeDevice() = 0;

  // Create a Session and other basic session-level initialization.
  virtual void InitializeSession() = 0;

  // Create a Session and other basic session-level initialization.
  virtual void InitializeRenderPipeline() = 0;

  // Create a Swapchain which requires coordinating with the graphics plugin to
  // select the format, getting the system graphics properties, getting the view
  // configuration and grabbing the resulting swapchain images.
  virtual void CreateSwapchains() = 0;

  // // Process any events in the event queue.
  virtual void PollEvents() = 0;

  // virtual void PollSystemEvents() = 0;
  // // Manage session lifecycle to track if RenderFrame should be called.
  virtual bool IsSessionRunning() const = 0;

  // // Manage session state to track if input should be processed.
  // virtual bool IsSessionFocused() const = 0;

  // // Sample input actions and generate haptic feedback.
  virtual void PollActions(XrTime time) = 0;

  // Create and submit a frame.
  virtual void RenderFrame() = 0;

  virtual void Run() = 0;

  virtual void AddVertex(float x, float y, float z) = 0;

  virtual void AddIndex(uint32_t vertex1, uint32_t vertex2, uint32_t vertex3) = 0;

  virtual void LoadVectexShader(const std::vector<char> &shader) = 0;

  virtual void LoadFragmentShader(const std::vector<char> &shader) = 0;

  virtual void LoadMeshVectexShader(const std::vector<char> &shader) = 0;

  virtual void LoadMeshFragmentShader(const std::vector<char> &shader) = 0;

  // Get preferred blend mode based on the view configuration specified in the
  // Options
  virtual XrEnvironmentBlendMode GetPreferredBlendMode() const = 0;

  // virtual void UpdateMaps(const AlignedVector<uint64_t> *points, const
  // AlignedVector<uint32_t> *color = nullptr, const AlignedVector<uint32_t>
  // *normal = nullptr) = 0;

  AlignedVector<uint64_t> *compressedPoints;

  virtual void SetCmdMsg(MsgQueue *msg_queue)  = 0;
  virtual void SetPoseMsg(MsgQueue *msg_queue) = 0;
  virtual void SetMapMsg(MsgQueue *msg_queue)  = 0;
  virtual void SetNavMsg(MsgQueue *msg_queue)  = 0;
  virtual void SetCamMsg(MsgQueue *msg_queue)  = 0;
  virtual void SetArmMsg(MsgQueue *msg_queue)  = 0;
  virtual void SetArmFbMsg(MsgQueue *msg_queue)  = 0;
};

std::shared_ptr<IOpenXrApplication> CreateOpenXrProgram(const std::shared_ptr<IPlatformPlugin> &platformPlugin, const int pointNum);
