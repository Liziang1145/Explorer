/**
 * @file arm_interface.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm communication and packet parser.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ARM_INTERFACE_H__
#define __ARM_INTERFACE_H__

#include <Eigen/Core>
#include <arm_model.h>

class ArmInterface
{
public:
    virtual ~ArmInterface() = default;

    virtual void setLeftJointControl(
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque) = 0;
    virtual void setLeftGripperControl(const double& position, const double& torque) = 0;
    virtual void setLeftMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation) = 0;
    virtual void setRightJointControl(
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque) = 0;
    virtual void setRightGripperControl(const double& position, const double& torque) = 0;
    virtual void setRightMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation) = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointPosition() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointVelocity() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointAcceleration() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointTorque() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointPosition() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointVelocity() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointAcceleration() = 0;
    virtual const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointTorque() = 0;
};

#endif // __ARM_INTERFACE_H__