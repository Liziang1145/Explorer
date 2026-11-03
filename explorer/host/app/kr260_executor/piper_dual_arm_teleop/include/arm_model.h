/**
 * @file arm_model.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm model, including kinematics and dynamics.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ARM_MODEL_H__
#define __ARM_MODEL_H__

#include <array>
#include <memory>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <error_codes.h>

typedef enum JointType
{
    JOINT_REVOLUTE = 1,
    JOINT_PRISMATIC = 2,
    JOINT_FIXED = 3
}JointType;

/**
 * @brief AgileX Piper robotics arm kinematics and dynamics
 * 
 */
class ArmModel
{
public:
    static constexpr int num_dof_ = 6;
    static constexpr int num_link_ = 7;

    ArmModel() = delete;
    ArmModel(const Eigen::Matrix4d& base_transform):base_transform_(base_transform){};
    ~ArmModel(){};

    void limitJointPosition(Eigen::Vector<double,num_dof_>& joint_pos) const;
    void limitJointVelocity(Eigen::Vector<double,num_dof_>& joint_vel) const;
    void limitJointTorque(Eigen::Vector<double,num_dof_>& joint_torque) const;

    /**
     * @brief Calculate transformation matrix for each link in base link frame.
     * 
     * @param link_transform output link transform matricies of each link in base frame.
     * @param link_com_transform output link center of mass transform matrices of each link in base frame.
     * @param joint_pos actuated joint position. unit: rad or m.
     */
    void getTransform(
        std::array<Eigen::Matrix4d,num_link_>& link_transform,
        std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
        const Eigen::Vector<double,num_dof_>& joint_pos) const;

    /**
     * @brief Calculate the velocity of each link and center of mass.
     * 
     * @param link_lin_vel 
     * @param link_ang_vel 
     * @param link_com_lin_vel 
     * @param link_com_ang_vel 
     * @param link_transform 
     * @param link_com_transform 
     * @param joint_vel 
     * 
     * @note All the joints are revolute joint, so prismatic and fixed joint 
     * calculation are not implemented.
     * 
     * @return void 
     */
    void getLinkVelocity(
        std::array<Eigen::Vector3d,num_link_>& link_lin_vel,
        std::array<Eigen::Vector3d,num_link_>& link_ang_vel,
        std::array<Eigen::Vector3d,num_link_>& link_com_lin_vel,
        std::array<Eigen::Vector3d,num_link_>& link_com_ang_vel,
        const std::array<Eigen::Matrix4d,num_link_>& link_transform,
        const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
        const Eigen::Vector<double,num_dof_>& joint_vel) const;
    
    void getLinkSpaceJacobian(
        std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
        const std::array<Eigen::Matrix4d,num_link_>& link_transform) const;

    void getLinkComSpaceJacobian(
        std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
        const std::array<Eigen::Matrix4d,num_link_>& link_transform,
        const std::array<Eigen::Matrix4d,num_link_>& link_com_transform) const;

    void getLinkComSpaceJacobianDot(
        std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian_dot,
        const std::array<Eigen::Matrix4d,num_link_>& link_transform,
        const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
        const std::array<Eigen::Vector3d,num_link_>& link_lin_vel,
        const std::array<Eigen::Vector3d,num_link_>& link_ang_vel,
        const std::array<Eigen::Vector3d,num_link_>& link_com_lin_vel) const;

    Eigen::Matrix<double,num_dof_,num_dof_> getJointSpaceMassMatrix(
        const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
        const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian) const;

    Eigen::Matrix<double,num_dof_,num_dof_> getJointSpaceCoriolisMatrix(
        const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
        const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
        const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian_dot,
        const Eigen::Vector<double,num_dof_>& joint_vel) const;

    Eigen::Vector<double,num_dof_> getJointSpaceGravityCompensate(
        const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian)const;

    /**
     * @brief Get task space inverse dynamics matricies.
     * 
     * @param task_space_mass_matrix 
     * @param task_space_bias_force 
     * @param joint_pos 
     * @param twist 
     * 
     * @note From "Modern Robotics - Mechanics, Planning and Control" eq8.90 and eq8.91
     */
    void getTaskSpaceInverseDynamics(
        Eigen::Matrix<double,6,6>& task_space_mass_matrix,
        Eigen::Vector<double,6>& task_space_bias_force,
        const Eigen::Vector<double,num_dof_>& joint_pos,
        const Eigen::Vector<double,num_dof_>& joint_vel) const;

    Eigen::Vector<double,num_dof_> getTaskSpaceControl(
        const Eigen::Vector<double,num_dof_>& joint_pos,
        const Eigen::Vector<double,num_dof_>& joint_vel,
        const Eigen::Vector3d& target_pos,
        const Eigen::Vector3d& actual_pos,
        const Eigen::Quaterniond& target_orientation,
        const Eigen::Quaterniond& actual_orientation) const;
    
    /**
     * @brief 
     * 
     * @param joint_pos actual joint position from actuator encoder. unit: rad.
     * @param joint_vel actual joint angular velocity from actuator encoder or tachometer. unit: rad/s.
     * @param target_pos desired end effector position in base frame. unit: m.
     * @param actual_pos actual end effector position in base frame, often from forward kinematics. unit: m.
     * @param target_orientation desired end effector orientation (expressed in quaternion) in base frame.
     * @param actual_orientation actual end effector orientation (expressed in quaternion) in base frame.
     * @param target_twist desired end effector twist (3-axis linear velocity and 3-axis angular velocity) in base frame.
     * 
     * @return Eigen::Vector<double,ArmModel::num_dof_> joint torque for control.
     */
    Eigen::Vector<double,num_dof_> getImpedanceControl(
        const Eigen::Vector<double,num_dof_>& actual_joint_pos,
        const Eigen::Vector<double,num_dof_>& actual_joint_vel,
        const Eigen::Vector3d& target_pos,
        const Eigen::Quaterniond& target_orientation) const;

    Eigen::Vector<double,num_dof_> getDiffIKControl(
        const Eigen::Vector<double,num_dof_>& actual_joint_pos,
        const Eigen::Vector<double,num_dof_>& actual_joint_vel,
        const Eigen::Vector3d& target_pos,
        const Eigen::Quaterniond& target_orientation);

    ErrorCode getShoulderJointPos(
        Eigen::Vector3d& joint_pos,
        const Eigen::Matrix4d &pose,
        const Eigen::Vector3d& ref_conf) const;

    ErrorCode getInverseKinematics(
        Eigen::Vector<double,6>& joint_pos,
        const Eigen::Matrix4d& pose,
        const Eigen::Vector<double,6>& ref_conf) const;

    ErrorCode getDampedLeastSquareInverseKinematics(
        Eigen::Vector<double,num_dof_>& joint_pos,
        const double lambda,
        const Eigen::Vector<double,6> tolerance,
        const size_t max_iteration,
        const Eigen::Matrix4d &pose,
        const Eigen::Vector<double,6>& ref_conf) const;
private:

    Eigen::Matrix4d base_transform_;
    static const std::array<Eigen::Matrix4d,num_link_> default_transform_;
    static const std::array<double,num_link_> mass_;
    static const std::array<Eigen::Matrix3d,num_link_> inertia_;
    static const std::array<Eigen::Vector3d,num_link_> center_of_mass_;
    static const std::array<Eigen::Vector3d,num_link_> joint_axis_;
    static const std::array<JointType,num_link_> joint_type_;
    static const std::array<double,num_dof_> joint_pos_limit_low_;
    static const std::array<double,num_dof_> joint_pos_limit_high_;
    static const std::array<double,num_dof_> joint_vel_limit_low_;
    static const std::array<double,num_dof_> joint_vel_limit_high_;
    static const std::array<double,num_dof_> joint_acc_limit_low_;
    static const std::array<double,num_dof_> joint_acc_limit_high_;
    static const std::array<double,num_dof_> joint_torque_limit_low_;
    static const std::array<double,num_dof_> joint_torque_limit_high_;
};

#endif //__ARM_MODEL_H__