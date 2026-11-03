/**
 * @file waypoint.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief Arm trajectory waypoint definition.
 * @version 0.1
 * @date 2025-06-30
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __WAYPOINT_H__
#define __WAYPOINT_H__

#include <Eigen/Core>
#include <arm_model.h>

struct JointState
{
    /* Joint Position */
    Eigen::Vector<double,ArmModel::num_dof_> joint_pos;
    /* Joint Velocity */
    Eigen::Vector<double,ArmModel::num_dof_> joint_vel;
    /* Joint Acceleration */
    Eigen::Vector<double,ArmModel::num_dof_> joint_acc;
    /* Joint Torque */
    Eigen::Vector<double,ArmModel::num_dof_> joint_torq;
};

#endif // __WAYPOINT_H__