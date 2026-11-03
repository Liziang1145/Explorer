/**
 * @file arm_controller.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief Joint space controller for trajectory tracking.
 * @version 0.1
 * @date 2025-06-12
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ARM_CONTROLLER_H__
#define __ARM_CONTROLLER_H__

#include <Eigen/Core>
#include <joint_state.h>
#include <itc/backend/RingBuf.hpp>
#include <arm_planner.h>
#include <arm_interface.h>

class ArmController
{
public:
    ArmController(
        std::shared_ptr<ArmModel> left_arm_model,
        std::shared_ptr<ArmModel> right_arm_model,
        std::shared_ptr<ArmInterface> interface,
        TrajectoryBuffer<ArmPlanner::num_plan_waypoint_>& left_arm_trajectory_buffer,
        TrajectoryBuffer<ArmPlanner::num_plan_waypoint_>& right_arm_trajectory_buffer,
        const size_t freq_ctrl);
    ~ArmController() = default;
    void start();
    void stop();
private:
    bool running_;

    /* Arm Interface */
    std::shared_ptr<ArmInterface> interface_;

    /* Left and right arm model, including kinematics and dynamics */
    std::shared_ptr<ArmModel> left_arm_model_;
    std::shared_ptr<ArmModel> right_arm_model_;

    /* Target joint state buffer to store control sequence */
    TrajectoryBuffer<ArmPlanner::num_plan_waypoint_>& left_arm_trajectory_buffer_;
    TrajectoryBuffer<ArmPlanner::num_plan_waypoint_>& right_arm_trajectory_buffer_;

    /* Frequency of control loop */
    size_t freq_ctrl_;

    /* Thread for control loop */
    std::thread control_thread_;

    void threadControl();
};

#endif // __ARM_CONTROLLER_H__