#pragma once

#include "TaskBase.hpp"
#include "ipc/itc/MsgQueue.hpp"

#include <chrono>
#include <thread>
#include <iostream>
#include "../sim/config.h"
#include "../sim/utils.hpp"
#include "../sim/error_codes.h"
#include "../sim/piper_model.hpp"
#include "../sim/trajectory_buffer.hpp"
#include "../sim/arm_planner.hpp"
#include "../sim/arm_controller.hpp"
#include "../sim/mujoco_backend.hpp"

#include "../io/pose_msg.h"

namespace Schedule {

  class TaskRunner {
  public:
    static constexpr std::size_t NumLink = 7;
    static constexpr std::size_t NumDof  = 6;
    explicit TaskRunner()
        : left_arm_model(CONFIG_LEFT_ARM_BASE_X, CONFIG_LEFT_ARM_BASE_Y, CONFIG_LEFT_ARM_BASE_Z, CONFIG_LEFT_ARM_BASE_ROLL,
                         CONFIG_LEFT_ARM_BASE_PITCH, CONFIG_LEFT_ARM_BASE_YAW),
          right_arm_model(CONFIG_RIGHT_ARM_BASE_X, CONFIG_RIGHT_ARM_BASE_Y, CONFIG_RIGHT_ARM_BASE_Z, CONFIG_RIGHT_ARM_BASE_ROLL,
                          CONFIG_RIGHT_ARM_BASE_PITCH, CONFIG_RIGHT_ARM_BASE_YAW),
          controller(1.0 / CONFIG_CONTROLLER_FREQUENCY, {100.0, 100.0, 100.0, 100.0, 100.0, 100.0}, {0, 0, 0, 0, 0, 0},
                     {10.0, 10.0, 10.0, 10.0, 10.0}) {}
    ~TaskRunner() = default;
    void updateLeftArmPlan(Eigen::Matrix<double, 4, 4> pose) {
      Eigen::Vector<double, NumDof> actual_left_arm_joint_pos = mj_backend.getLeftArmJointPosition();
      Eigen::Vector<double, NumDof> ik_result                 = Eigen::Vector<double, NumDof>::Zero();
      if (left_arm_model.getInverseKinematics(ik_result, pose, actual_left_arm_joint_pos) == ErrorCode::NoResult) {
        if (left_arm_model.getDampedLeastSquareInverseKinematics(ik_result, left_arm_model, pose, actual_left_arm_joint_pos)
            == ErrorCode::NoResult) {
          return;
        }
      }
      std::cout << "left arm inverse kinematics: " << ik_result.transpose() << std::endl;
      auto [target_left_arm_joint_pos, left_arm_joint_vel, left_arm_joint_acc]
          = left_arm_trajectory_buffer.interpolate(std::chrono::steady_clock::now());
      auto [time_point, trajectory] = LinearArmPlanner::plan<double, NumDof, CONFIG_WAYPOINT_AMOUNT>(
          std::chrono::steady_clock::now(), 1.0 / CONFIG_PLANNER_FREQUENCY, target_left_arm_joint_pos, ik_result);
      left_arm_trajectory_buffer.write(time_point, trajectory);
    }
    void updateRightArmPlan(Eigen::Matrix<double, 4, 4> pose) {
      Eigen::Vector<double, NumDof> actual_right_arm_joint_pos = mj_backend.getRightArmJointPosition();
      Eigen::Vector<double, NumDof> ik_result                  = Eigen::Vector<double, NumDof>::Zero();
      if (right_arm_model.getInverseKinematics(ik_result, pose, actual_right_arm_joint_pos) == ErrorCode::NoResult) {
        if (right_arm_model.getDampedLeastSquareInverseKinematics(ik_result, right_arm_model, pose, actual_right_arm_joint_pos)
            == ErrorCode::NoResult) {
          return;
        }
      }
      std::cout << "right arm inverse kinematics: " << ik_result.transpose() << std::endl;
      auto [target_right_arm_joint_pos, right_arm_joint_vel, right_arm_joint_acc]
          = right_arm_trajectory_buffer.interpolate(std::chrono::steady_clock::now());
      auto [time_point, trajectory] = LinearArmPlanner::plan<double, NumDof, CONFIG_WAYPOINT_AMOUNT>(
          std::chrono::steady_clock::now(), 1.0 / CONFIG_PLANNER_FREQUENCY, target_right_arm_joint_pos, ik_result);
      right_arm_trajectory_buffer.write(time_point, trajectory);
    };
    void updateControl() {
      {
        auto [target_joint_pos, target_joint_vel, target_joint_acc] = left_arm_trajectory_buffer.interpolate(std::chrono::steady_clock::now());
        JointState<double, NumDof> target_joint_state               = {target_joint_pos, target_joint_vel, target_joint_acc};
        JointState<double, NumDof> current_joint_state
            = {mj_backend.getLeftArmJointPosition(), mj_backend.getLeftArmJointVelocity(), mj_backend.getLeftArmJointAcceleration()};
        auto target_joint_torque
            = controller.computeTorqueControlOutput(left_arm_model, Eigen::Vector<double, 3>::Zero(), target_joint_state, current_joint_state);
        mj_backend.setLeftArmJointControl(target_joint_torque);
        std::cout << "target left arm joint position: " << target_joint_pos.transpose() << std::endl;
        std::cout << "current left arm joint position: " << current_joint_state.joint_pos.transpose() << std::endl;
      }
      {
        auto [target_joint_pos, target_joint_vel, target_joint_acc] = right_arm_trajectory_buffer.interpolate(std::chrono::steady_clock::now());
        JointState<double, NumDof> target_joint_state               = {target_joint_pos, target_joint_vel, target_joint_acc};
        JointState<double, NumDof> current_joint_state
            = {mj_backend.getRightArmJointPosition(), mj_backend.getRightArmJointVelocity(), mj_backend.getRightArmJointAcceleration()};
        auto target_joint_torque
            = controller.computeTorqueControlOutput(right_arm_model, Eigen::Vector<double, 3>::Zero(), target_joint_state, current_joint_state);
        mj_backend.setRightArmJointControl(target_joint_torque);
        std::cout << "target right arm joint position: " << target_joint_pos.transpose() << std::endl;
        std::cout << "current right arm joint position: " << current_joint_state.joint_pos.transpose() << std::endl;
      }
    }
    MujocoBackend<double, NumDof> mj_backend;
    PiperArmModel<double> left_arm_model;
    PiperArmModel<double> right_arm_model;
    ArmController<double, NumLink, NumDof> controller;
    BsplineTrajectoryBuffer<double, NumDof> left_arm_trajectory_buffer;
    BsplineTrajectoryBuffer<double, NumDof> right_arm_trajectory_buffer;
  };

  class ArmTask : public TaskBase {
  public:
    // std::vector<std::byte>>>;
    using arm_pose_msg = std::pair<pose_msg, pose_msg>;
    using arm_fb_msg   = std::array<Eigen::Matrix4f, 6>;

  protected:
    void task() override {
      auto arm_pose_msg_queue = quiry_msg_queue("arm_pose_msg");
      auto arm_fb_msg_queue   = quiry_msg_queue("arm_fb_msg");
      arm_pose_msg arm_pose_msg;
      arm_fb_msg fb_msg;
      TaskRunner runner;
      while (1) {
        if (arm_pose_msg_queue->dequeue(arm_pose_msg)) {
          Eigen::Matrix4d left_hand_pose  = Eigen::Matrix4d::Identity();
          Eigen::Matrix4d right_hand_pose = Eigen::Matrix4d::Identity();
          left_hand_pose.block<3, 1>(0, 3)
              = Eigen::Vector3d(arm_pose_msg.first.position[0], arm_pose_msg.first.position[1], arm_pose_msg.first.position[2]);
          left_hand_pose.block<3, 3>(0, 0) = Eigen::Quaternionf(arm_pose_msg.first.orientation.data()).toRotationMatrix().cast<double>();

          right_hand_pose.block<3, 1>(0, 3)
              = Eigen::Vector3d(arm_pose_msg.second.position[0], arm_pose_msg.second.position[1], arm_pose_msg.second.position[2]);
          right_hand_pose.block<3, 3>(0, 0) = Eigen::Quaternionf(arm_pose_msg.second.orientation.data()).toRotationMatrix().cast<double>();
          runner.updateLeftArmPlan(left_hand_pose);
          runner.updateRightArmPlan(right_hand_pose);

          // extract here
          {
            Eigen::Vector<double, 6> left_arm_actual_joint_pos = runner.mj_backend.getLeftArmJointPosition();
            auto [link_transform, link_com_transform]          = runner.left_arm_model.getTransform(left_arm_actual_joint_pos);
            fb_msg[0]                                          = link_transform[1].cast<float>();
            fb_msg[1]                                          = link_transform[2].cast<float>();
            fb_msg[2]                                          = link_transform[4].cast<float>();
          }
          {
            Eigen::Vector<double, 6> right_arm_actual_joint_pos = runner.mj_backend.getRightArmJointPosition();
            auto [link_transform, link_com_transform]           = runner.right_arm_model.getTransform(right_arm_actual_joint_pos);
            fb_msg[3]                                           = link_transform[1].cast<float>();
            fb_msg[4]                                           = link_transform[2].cast<float>();
            fb_msg[5]                                           = link_transform[4].cast<float>();
          }
          arm_fb_msg_queue->enqueue(fb_msg);
        }
        runner.updateControl();
        runner.mj_backend.update();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
    }
  };

};  // namespace Schedule