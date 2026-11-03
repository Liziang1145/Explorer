/**
 * @file arm_controller.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Joint space controller for robotic arm.
 * @version 0.1
 * @date 2025-08-08
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ARM_CONTROLLER_HPP__
#define __ARM_CONTROLLER_HPP__

#include <Eigen/Core>
#include <joint_state.h>
#include <piper_model.hpp>

template <typename T, std::size_t NumLink, std::size_t NumDof>
class ArmController
{
public:
    explicit ArmController() :
        dt(0), integral_error(0), prev_error(0),
        Kp(Eigen::Vector<T, NumDof>::Zero()),
        Ki(Eigen::Vector<T, NumDof>::Zero()),
        Kd(Eigen::Vector<T, NumDof>::Zero()){}
    explicit ArmController(const T dt, const std::array<T, NumDof>& Kp, const std::array<T, NumDof>& Ki, const std::array<T, NumDof>& Kd) :
        dt(dt), integral_error(Eigen::Vector<T, NumDof>::Zero()), prev_error(Eigen::Vector<T, NumDof>::Zero())
    {
        for ( std::size_t i=0 ; i<NumDof ; i++ )
        {
            this->Kp(i) = Kp[i];
            this->Ki(i) = Ki[i];
            this->Kd(i) = Kd[i];
        }
    }
    ~ArmController() = default;
    void setControlTimeInterval(const T dt)
    {
        this->dt = dt;
    }
    void setPIDParameters(const std::array<T, NumDof> Kp, const std::array<T, NumDof> Ki, const std::array<T, NumDof> Kd)
    {
        this->Kp = Eigen::Map<Eigen::Vector<T, NumDof>>(Kp.data());
        this->Ki = Eigen::Map<Eigen::Vector<T, NumDof>>(Ki.data());
        this->Kd = Eigen::Map<Eigen::Vector<T, NumDof>>(Kd.data());
    }
    void setPIDParameters(const Eigen::Vector<T, NumDof>& Kp, const Eigen::Vector<T, NumDof>& Ki, const Eigen::Vector<T, NumDof>& Kd)
    {
        this->Kp = Kp;
        this->Ki = Ki;
        this->Kd = Kd;
    }
    Eigen::Vector<T, NumDof> computeTorqueControlOutput(
        const PiperArmModel<T>& model,
        const Eigen::Vector<T, 3>& external_force,
        const JointState<T, NumDof>& target_joint_state,
        const JointState<T, NumDof>& current_joint_state) const
    {
        auto [link_transform, link_com_transform] = model.getTransform(current_joint_state.joint_pos);
        auto link_com_jacobian = model.getLinkSpaceJacobian(link_transform);
        auto [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = model.getLinkVelocity(link_transform, link_com_transform, current_joint_state.joint_vel);
        auto link_com_jacobian_dot = model.getLinkComSpaceJacobianDot(link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
        auto mass_matrix = model.getJointSpaceMassMatrix(link_com_transform, link_com_jacobian);
        auto coriolis_matrix = model.getJointSpaceCoriolisMatrix(link_com_transform, link_com_jacobian, link_com_jacobian_dot, current_joint_state.joint_vel);

        Eigen::Vector<T, NumDof> control_output =
            mass_matrix * (
                // target_joint_state.joint_acc +
                Kd.cwiseProduct(- current_joint_state.joint_vel) +
                Kp.cwiseProduct(target_joint_state.joint_pos - current_joint_state.joint_pos)) +
            coriolis_matrix * current_joint_state.joint_vel;
 
        control_output += computeGravityCompensate(model, current_joint_state);
        control_output += computeFrictionCompensate(current_joint_state);
        control_output += computeExternalForceCompensate(model, external_force);

        return control_output;
    }

    Eigen::Vector<T, NumDof> computeDynamicsCompensate(
        const PiperArmModel<T>& model,
        const JointState<T, NumDof>& joint_state) const
    {
        Eigen::Vector<T, NumDof> compensation = Eigen::Vector<T, NumDof>::Zero();

        auto [link_transform, link_com_transform] = model.getTransform(joint_state.joint_pos);
        auto link_com_jacobian = model.getLinkSpaceJacobian(link_transform);
        auto [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = model.getLinkVelocity(link_transform, link_com_transform, joint_state.joint_vel);
        auto link_com_jacobian_dot = model.getLinkComSpaceJacobianDot(link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
        auto mass_matrix = model.getJointSpaceMassMatrix(link_com_transform, link_com_jacobian);
        auto coriolis_matrix = model.getJointSpaceCoriolisMatrix(link_com_transform, link_com_jacobian, link_com_jacobian_dot, joint_state.joint_vel);

        compensation = mass_matrix * joint_state.joint_acc + coriolis_matrix * joint_state.joint_vel;
        return compensation;
    }
    Eigen::Vector<T, NumDof> computeGravityCompensate(
        const PiperArmModel<T>& model,
        const JointState<T, NumDof>& joint_state) const
    {
        auto [link_transform, link_com_transform] = model.getTransform(joint_state.joint_pos);
        auto link_com_jacobian = model.getLinkComSpaceJacobian(link_transform, link_com_transform);
        auto gravity_compensate = model.getJointSpaceGravityCompensate(link_com_jacobian);
        return gravity_compensate;
    }
    Eigen::Vector<T, NumDof> computeFrictionCompensate(
        const JointState<T, NumDof>& joint_state) const
    {
        return Eigen::Vector<T, NumDof>::Zero(); // Placeholder, actual implementation needed
    }
    Eigen::Vector<T, NumDof> computeExternalForceCompensate(
        const PiperArmModel<T>& model,
        const Eigen::Vector<T, 3>& external_force) const
    {
        return Eigen::Vector<T, NumDof>::Zero(); // Placeholder, actual implementation needed
    }
private:
    Eigen::Vector<T, NumDof> Kp;
    Eigen::Vector<T, NumDof> Ki;
    Eigen::Vector<T, NumDof> Kd;
    Eigen::Vector<T, NumDof> integral_error;
    Eigen::Vector<T, NumDof> prev_error;
    T dt;

};

#endif // __ARM_CONTROLLER_HPP__