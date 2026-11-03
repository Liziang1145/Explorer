/**
 * @file piper_arm_model.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm model, including kinematics and dynamics.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#pragma once

#include <array>
#include <memory>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <error_codes.h>

template<typename T>
constexpr Eigen::Matrix<T, 4, 4> getTransformFromRotationAndTranslation(T x, T y, T z, T roll, T pitch, T yaw)
{
    Eigen::Matrix<T, 4, 4> transform = Eigen::Matrix<T, 4, 4>::Identity();
    Eigen::AngleAxis<T> angle_x(roll, Eigen::Vector<T, 3>::UnitX());
    Eigen::AngleAxis<T> angle_y(pitch, Eigen::Vector<T, 3>::UnitY());
    Eigen::AngleAxis<T> angle_z(yaw, Eigen::Vector<T, 3>::UnitZ());
    Eigen::Quaternion<T> q = angle_z * angle_y * angle_x;
    transform.template block<3, 3>(0, 0) = q.toRotationMatrix();
    transform(0, 3) = x;
    transform(1, 3) = y;
    transform(2, 3) = z;
    return transform;
}

template<typename T>
constexpr Eigen::Matrix<T, 3, 3> getInertial(T ixx, T iyy, T izz, T ixy, T ixz, T iyz)
{
    return (Eigen::Matrix<T, 3, 3>() << ixx, ixy, ixz, ixy, iyy, iyz, ixz, iyz, izz).finished();
}

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
template<typename T>
class PiperArmModel
{
public:
    static constexpr int NumDof = 6;
    static constexpr int NumLink = 7;

    PiperArmModel() = delete;
    PiperArmModel(const T x, const T y, const T z, const T roll, const T pitch, const T yaw)
    {
        this->base_transform_ = getTransformFromRotationAndTranslation(x, y, z, roll, pitch, yaw);
    }

    ~PiperArmModel()
    {
    }

    Eigen::Vector<T, NumDof> limitJointPosition(const Eigen::Vector<T, NumDof>& joint_pos) const
    {
        Eigen::Vector<T, NumDof> limited_joint_pos = joint_pos;
        for ( int i = 0; i < NumDof; i++ )
        {
            limited_joint_pos(i) = std::clamp(limited_joint_pos(i), joint_pos_limit_low_[i], joint_pos_limit_high_[i]);
        }
        return limited_joint_pos;
    }

    Eigen::Vector<T, NumDof> limitJointVelocity(const Eigen::Vector<T, NumDof>& joint_vel) const
    {
        Eigen::Vector<T, NumDof> limited_joint_vel = joint_vel;
        for ( int i = 0; i < NumDof; i++ )
        {
            limited_joint_vel(i) = std::clamp(limited_joint_vel(i), joint_vel_limit_low_[i], joint_vel_limit_high_[i]);
        }
        return limited_joint_vel;
    }

    Eigen::Vector<T, NumDof> limitJointTorque(const Eigen::Vector<T, NumDof>& joint_torque) const
    {
        Eigen::Vector<T, NumDof> limited_joint_torque = joint_torque;
        for ( int i = 0; i < NumDof; i++ )
        {
            limited_joint_torque(i) = std::clamp(limited_joint_torque(i), joint_torque_limit_low_[i], joint_torque_limit_high_[i]);
        }
        return limited_joint_torque;
    }

    std::array<std::array<T, 2>, NumDof> getJointPositionLimits() const
    {
        std::array<std::array<T, 2>, NumDof> limits;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            limits[i][0] = this->joint_pos_limit_low_[i];
            limits[i][1] = this->joint_pos_limit_high_[i];
        }
        return limits;
    }

    Eigen::Matrix<T, 4, 4> getBaseTransform() const
    {
        return this->base_transform_;
    }

    /**
     * @brief Calculate transformation matrix for each link in base link frame.
     * 
     * @param joint_pos actuated joint position. unit: rad or m.
     * @return std::tuple containing link_transform and link_com_transform
     */
    std::tuple<std::array<Eigen::Matrix<T, 4, 4>, NumLink>, std::array<Eigen::Matrix<T, 4, 4>, NumLink>> 
    getTransform(const Eigen::Vector<T, NumDof>& joint_pos) const
    {
        std::array<Eigen::Matrix<T, 4, 4>, NumLink> link_transform;
        std::array<Eigen::Matrix<T, 4, 4>, NumLink> com_transform;

        /* Transform of joint rotation */
        Eigen::Matrix<T, 4, 4> joint_rotate_transform = Eigen::Matrix<T, 4, 4>::Identity();
        Eigen::Matrix<T, 4, 4> link_transform_local = Eigen::Matrix<T, 4, 4>::Identity();

        /* Calculate transform of other links */
        for ( int i = 0; i < NumLink; i++ )
        {
            joint_rotate_transform = Eigen::Matrix<T, 4, 4>::Identity();
            link_transform_local = Eigen::Matrix<T, 4, 4>::Identity();

            if ( joint_type_[i] == JOINT_REVOLUTE )
            {
                joint_rotate_transform.template block<3, 3>(0, 0) = Eigen::AngleAxis<T>(joint_pos[i], joint_axis_[i]).toRotationMatrix();
            }
            else if ( joint_type_[i] == JOINT_PRISMATIC )
            {
                joint_rotate_transform.template block<3, 1>(0, 3) = joint_pos[i] * joint_axis_[i];
            }

            link_transform_local = default_transform_[i] * joint_rotate_transform;

            if ( i == 0 )
            {
                link_transform[i] = base_transform_ * link_transform_local;
            }
            else
            {
                link_transform[i] = link_transform[i-1] * link_transform_local;
            }
            
            com_transform[i] = link_transform[i];
            com_transform[i].template block<3, 1>(0, 3) += link_transform[i].template block<3, 3>(0, 0) * center_of_mass_[i];
        }
        
        return std::make_tuple(link_transform, com_transform);
    }

    /**
     * @brief Calculate the velocity of each link and center of mass.
     * 
     * @param link_transform 
     * @param link_com_transform 
     * @param joint_vel 
     * 
     * @note All the joints are revolute joint, so prismatic and fixed joint 
     * calculation are not implemented.
     * 
     * @return std::tuple containing link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel
     */
    std::tuple<std::array<Eigen::Vector<T, 3>, NumLink>, 
               std::array<Eigen::Vector<T, 3>, NumLink>,
               std::array<Eigen::Vector<T, 3>, NumLink>,
               std::array<Eigen::Vector<T, 3>, NumLink>>
    getLinkVelocity(
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_transform,
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_com_transform,
        const Eigen::Vector<T, NumDof>& joint_vel) const
    {
        std::array<Eigen::Vector<T, 3>, NumLink> link_lin_vel;
        std::array<Eigen::Vector<T, 3>, NumLink> link_ang_vel;
        std::array<Eigen::Vector<T, 3>, NumLink> link_com_lin_vel;
        std::array<Eigen::Vector<T, 3>, NumLink> link_com_ang_vel;

        Eigen::Matrix<T, 3, 3> rotation = Eigen::Matrix<T, 3, 3>::Identity();
        Eigen::Vector<T, 3> link_translation;
        Eigen::Vector<T, 3> link_com_translation;

        for ( int i = 0; i < NumLink; i++ )
        {
            rotation = link_transform[i].template block<3, 3>(0, 0);
            if ( i == 0 )
            {
                link_translation = link_transform[i].template block<3, 1>(0, 3);
                link_com_translation = link_com_transform[i].template block<3, 1>(0, 3);
            }
            else
            {
                link_translation = link_transform[i].template block<3, 1>(0, 3) - link_transform[i-1].template block<3, 1>(0, 3);
                link_com_translation = link_com_transform[i].template block<3, 1>(0, 3) - link_transform[i].template block<3, 1>(0, 3);
            }
            if ( joint_type_[i] == JOINT_REVOLUTE )
            {
                if ( i == 0 )
                {
                    link_ang_vel[i] = rotation * joint_axis_[i] * joint_vel[i];
                    link_lin_vel[i] = link_ang_vel[i].cross(link_translation);
                    link_com_lin_vel[i] = link_ang_vel[i].cross(link_com_translation);
                }
                else
                {
                    link_ang_vel[i] = link_ang_vel[i-1] + rotation * joint_axis_[i] * joint_vel[i];
                    link_lin_vel[i] = link_lin_vel[i-1] + link_ang_vel[i-1].cross(link_translation);
                    link_com_lin_vel[i] = link_lin_vel[i] + link_ang_vel[i].cross(link_com_translation);
                }
            }
            else if ( joint_type_[i] == JOINT_PRISMATIC )
            {
                if ( i == 0 )
                {
                    link_ang_vel[i].setZero();
                    link_lin_vel[i] = link_ang_vel[i].cross(link_translation) + rotation * joint_axis_[i] * joint_vel[i];
                }
                else
                {
                    link_ang_vel[i] = link_ang_vel[i-1];
                    link_lin_vel[i] = link_lin_vel[i-1] + link_ang_vel[i].cross(link_translation) + rotation * joint_axis_[i] * joint_vel[i];
                }
            }
            else if ( joint_type_[i] == JOINT_FIXED )
            {
                if ( i == 0 )
                {
                    link_ang_vel[i].setZero();
                    link_lin_vel[i].setZero();
                    link_com_lin_vel[i].setZero();
                }
                else
                {
                    link_ang_vel[i] = link_ang_vel[i-1];
                    link_lin_vel[i] = link_lin_vel[i-1] + link_ang_vel[i-1].cross(link_translation);
                    link_com_lin_vel[i] = link_lin_vel[i] + link_ang_vel[i].cross(link_com_translation);
                }
            }
            link_com_ang_vel[i] = link_ang_vel[i];
        }
        
        return std::make_tuple(link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel);
    }
    
    std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> 
    getLinkSpaceJacobian(const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_transform) const
    {
        std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> link_com_jacobian;
        
        for ( int i = 0; i < NumLink; i++ )
        {
            link_com_jacobian[i].setZero();
            for ( int j = 0, col = 0; j <= i; j++ )
            {
                Eigen::Matrix<T, 3, 3> rotation = link_transform[j].template block<3, 3>(0, 0);
                Eigen::Vector<T, 3> pos_i = link_transform[i].template block<3, 1>(0, 3);
                Eigen::Vector<T, 3> pos_j = link_transform[j].template block<3, 1>(0, 3);
                if ( joint_type_[j] == JOINT_REVOLUTE )
                {
                    link_com_jacobian[i].template block<3, 1>(0, col) = (rotation * joint_axis_[j]).cross(pos_i - pos_j);
                    link_com_jacobian[i].template block<3, 1>(3, col) = rotation * joint_axis_[j];
                    col++;
                }
                else if ( joint_type_[j] == JOINT_PRISMATIC )
                {
                    link_com_jacobian[i].template block<3, 1>(0, col) = rotation * joint_axis_[j];
                    link_com_jacobian[i].template block<3, 1>(3, col).setZero();
                    col++;
                }
                // else if ( joint_type_[j] == JOINT_FIXED )
                // {
                //     link_com_jacobian[i].block<6,1>(0,j).setZero(); 
                // }
            }
        }
        
        return link_com_jacobian;
    }

    std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> 
    getLinkComSpaceJacobian(
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_transform,
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_com_transform) const
    {
        std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> link_com_jacobian;
        
        for ( int i = 0; i < NumLink; i++ )
        {
            link_com_jacobian[i].setZero();
            for ( int j = 0, col = 0; j <= i; j++ )
            {
                Eigen::Matrix<T, 3, 3> rotation = link_transform[j].template block<3, 3>(0, 0);
                Eigen::Vector<T, 3> pos_i = link_com_transform[i].template block<3, 1>(0, 3);
                Eigen::Vector<T, 3> pos_j = link_transform[j].template block<3, 1>(0, 3);
                if ( joint_type_[j] == JOINT_REVOLUTE )
                {
                    link_com_jacobian[i].template block<3, 1>(0, col) = (rotation * joint_axis_[j]).cross(pos_i - pos_j);
                    link_com_jacobian[i].template block<3, 1>(3, col) = rotation * joint_axis_[j];
                    col++;
                }
                else if ( joint_type_[j] == JOINT_PRISMATIC )
                {
                    link_com_jacobian[i].template block<3, 1>(0, col) = rotation * joint_axis_[j];
                    link_com_jacobian[i].template block<3, 1>(3, col).setZero();
                    col++;
                }
                // else if ( joint_type_[j] == JOINT_FIXED )
                // {
                //     link_com_jacobian[i].block<6,1>(0,j).setZero(); 
                // }
            }
        }
        
        return link_com_jacobian;
    }

    std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> 
    getLinkComSpaceJacobianDot(
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_transform,
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_com_transform,
        const std::array<Eigen::Vector<T, 3>, NumLink>& link_lin_vel,
        const std::array<Eigen::Vector<T, 3>, NumLink>& link_ang_vel,
        const std::array<Eigen::Vector<T, 3>, NumLink>& link_com_lin_vel) const
    {
        std::array<Eigen::Matrix<T, 6, NumDof>, NumLink> link_com_jacobian_dot;
        
        for ( int i = 0; i < NumLink; i++ )
        {
            link_com_jacobian_dot[i].setZero();
            for ( int j = 0, col = 0; j <= i; j++ )
            {
                Eigen::Matrix<T, 3, 3> rotation = link_transform[j].template block<3, 3>(0, 0);
                Eigen::Vector<T, 3> pos_i = link_com_transform[i].template block<3, 1>(0, 3);
                Eigen::Vector<T, 3> pos_j = link_transform[j].template block<3, 1>(0, 3);
                Eigen::Vector<T, 3> vel_i = link_com_lin_vel[i];
                Eigen::Vector<T, 3> vel_j = link_lin_vel[j];
                if ( joint_type_[j] == JOINT_REVOLUTE )
                {
                    link_com_jacobian_dot[i].template block<3, 1>(0, col) = (link_ang_vel[j].cross(rotation * joint_axis_[j])).cross(pos_i - pos_j) + (rotation * joint_axis_[j]).cross(vel_i - vel_j);
                    link_com_jacobian_dot[i].template block<3, 1>(3, col) = link_ang_vel[j].cross(rotation * joint_axis_[j]);
                    col++;
                }
                else if ( joint_type_[j] == JOINT_PRISMATIC )
                {
                    link_com_jacobian_dot[i].template block<3, 1>(0, col) = link_ang_vel[j].cross(rotation * joint_axis_[j]);
                    link_com_jacobian_dot[i].template block<3, 1>(3, col).setZero();
                    col++;
                }
                // else if ( joint_type_[j] == JOINT_FIXED )
                // {
                //     link_com_jacobian_dot[i].block<6,1>(0,j).setZero();
                // }
            }
        }
        
        return link_com_jacobian_dot;
    }

    Eigen::Matrix<T, NumDof, NumDof> getJointSpaceMassMatrix(
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_com_transform,
        const std::array<Eigen::Matrix<T, 6, NumDof>, NumLink>& link_com_jacobian) const
    {
        Eigen::Matrix<T, NumDof, NumDof> generalized_mass_matrix;
        generalized_mass_matrix.setZero();

        Eigen::Matrix<T, 3, NumDof> J_v;
        Eigen::Matrix<T, 3, NumDof> J_w;
        Eigen::Matrix<T, 3, 3> inertia_g;

        for ( int i = 0; i < NumLink; i++ )
        {
            /* Extract linear velocity part of jacobian matrix */
            J_v = link_com_jacobian[i].template block<3, NumDof>(0, 0);
            /* Extract angular velocity part of jacobian matrix */
            J_w = link_com_jacobian[i].template block<3, NumDof>(3, 0);

            /* rotate inertia matrix to base frame */
            inertia_g = link_com_transform[i].template block<3, 3>(0, 0) * inertia_[i] * link_com_transform[i].template block<3, 3>(0, 0).transpose();

            generalized_mass_matrix = generalized_mass_matrix + 
                J_v.transpose() * mass_[i] * J_v + J_w.transpose() * inertia_g * J_w;
        }

        return generalized_mass_matrix;
    }

    Eigen::Matrix<T, NumDof, NumDof> getJointSpaceCoriolisMatrix(
        const std::array<Eigen::Matrix<T, 4, 4>, NumLink>& link_com_transform,
        const std::array<Eigen::Matrix<T, 6, NumDof>, NumLink>& link_com_jacobian,
        const std::array<Eigen::Matrix<T, 6, NumDof>, NumLink>& link_com_jacobian_dot,
        const Eigen::Vector<T, NumDof>& joint_vel) const
    {
        Eigen::Matrix<T, NumDof, NumDof> centrifugal_coriolis_matrix;

        Eigen::Matrix<T, 3, NumDof> J_v;
        Eigen::Matrix<T, 3, NumDof> J_w;
        Eigen::Matrix<T, 3, NumDof> Jd_v;
        Eigen::Matrix<T, 3, NumDof> Jd_w;
        Eigen::Matrix<T, 3, 3> inertia_g;

        auto getSymmetricSkew = [](const Eigen::Vector<T, 3>& vec)
        {
            Eigen::Matrix<T, 3, 3> skew_matrix;
            skew_matrix << 0, -vec(2), vec(1),
                           vec(2), 0, -vec(0),
                          -vec(1), vec(0), 0;
            return skew_matrix;
        };

        centrifugal_coriolis_matrix.setZero();

        for ( int i = 0; i < NumLink; i++ )
        {
            /* Extract linear velocity part of jacobian matrix */
            J_v = link_com_jacobian[i].template block<3, NumDof>(0, 0);
            /* Extract angular velocity part of jacobian matrix */
            J_w = link_com_jacobian[i].template block<3, NumDof>(3, 0);
            /* Extract linear velocity part of time derivative jacobian matrix */
            Jd_v = link_com_jacobian_dot[i].template block<3, NumDof>(0, 0);
            /* Extract angular velocity part of time derivative jacobian matrix */
            Jd_w = link_com_jacobian_dot[i].template block<3, NumDof>(3, 0);
            /* rotate inertia matrix to base frame */
            inertia_g = link_com_transform[i].template block<3, 3>(0, 0) * inertia_[i] * link_com_transform[i].template block<3, 3>(0, 0).transpose();

            centrifugal_coriolis_matrix = centrifugal_coriolis_matrix +
                J_v.transpose() * mass_[i] * Jd_v + J_w.transpose() * inertia_g * Jd_w + J_w.transpose() * getSymmetricSkew(J_w * joint_vel) * inertia_g * J_w;
        }

        return centrifugal_coriolis_matrix;
    }

    Eigen::Vector<T, NumDof> getJointSpaceGravityCompensate(
        const std::array<Eigen::Matrix<T, 6, NumDof>, NumLink>& link_com_jacobian) const
    {
        Eigen::Vector<T, NumDof> gravity_compensate;
        gravity_compensate.setZero();

        Eigen::Matrix<T, 3, NumDof> J_v;
        /* reverse of gravity force */
        static const Eigen::Vector<T, 3> base_gravity(0, 0, 9.81);

        for ( int i = 0; i < NumLink; i++ )
        {
            /* Extract linear velocity part of jacobian matrix */
            J_v = link_com_jacobian[i].template block<3, NumDof>(0, 0);
            
            gravity_compensate = gravity_compensate +
                J_v.transpose() * (mass_[i] * base_gravity);
        }

        return gravity_compensate;
    }

    /**
     * @brief Get task space inverse dynamics matricies.
     * 
     * @param joint_pos 
     * @param joint_vel 
     * 
     * @note From "Modern Robotics - Mechanics, Planning and Control" eq8.90 and eq8.91
     * @return std::tuple containing task_space_mass_matrix and task_space_bias_force
     */
    std::tuple<Eigen::Matrix<T, 6, 6>, Eigen::Vector<T, 6>>
    getTaskSpaceInverseDynamics(
        const Eigen::Vector<T, NumDof>& joint_pos,
        const Eigen::Vector<T, NumDof>& joint_vel) const
    {
        auto [link_transform, link_com_transform] = getTransform(joint_pos);
        auto [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = getLinkVelocity(link_transform, link_com_transform, joint_vel);
        auto link_com_jacobian = getLinkComSpaceJacobian(link_transform, link_com_transform);
        auto link_com_jacobian_dot = getLinkComSpaceJacobianDot(link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
        Eigen::Matrix<T, NumDof, NumDof> generalized_mass_matrix = getJointSpaceMassMatrix(link_com_transform, link_com_jacobian);
        Eigen::Matrix<T, NumDof, NumDof> centrifugal_coriolis_matrix = getJointSpaceCoriolisMatrix(link_com_transform, link_com_jacobian, link_com_jacobian_dot, joint_vel);
        Eigen::Vector<T, NumDof> gravity_compensate = getJointSpaceGravityCompensate(link_com_jacobian);

        Eigen::Matrix<T, 6, NumDof> jacobian = link_com_jacobian[NumLink-1]; // end effector center of mass jacobian
        Eigen::Matrix<T, NumDof, 6> jacobian_inv;   // inverse or pseudoinverse of end effector center of mass jacobian
        Eigen::Matrix<T, NumDof, 6> jacobian_inv_T; // transpose of inverse or pseudoinverse of end effector center of mass jacobian
        Eigen::Vector<T, 6> twist;

        /* TODO: Consider psuedoinverse if DOF > 6 */
        jacobian_inv = jacobian.inverse();
        jacobian_inv_T = jacobian_inv.transpose();

        twist = jacobian * joint_vel;

        Eigen::Matrix<T, 6, 6> task_space_mass_matrix_inv = jacobian * generalized_mass_matrix.inverse() * jacobian.transpose();
        Eigen::Matrix<T, 6, 6> task_space_mass_matrix;
        if ( std::abs(task_space_mass_matrix_inv.determinant()) > 1e-2 )
        {
            task_space_mass_matrix = task_space_mass_matrix_inv.inverse();
        }
        else
        {
            task_space_mass_matrix = task_space_mass_matrix_inv.completeOrthogonalDecomposition().pseudoInverse();
        }

        Eigen::Vector<T, 6> task_space_bias_force;
        /* TODO: potential calculation error due to sigularity of jacobian (invalid inverse of jacobian matrix) */
        task_space_bias_force = (jacobian_inv_T * centrifugal_coriolis_matrix * jacobian_inv - task_space_mass_matrix * link_com_jacobian_dot[NumLink-1] * jacobian_inv) * twist + jacobian_inv_T * gravity_compensate;
        
        return std::make_tuple(task_space_mass_matrix, task_space_bias_force);
    }
    /**
     * @brief Get inverse of transformation matrix
     */
    static Eigen::Matrix<T, 4, 4> getInverseTransform(const Eigen::Matrix<T, 4, 4>& transform)
    {
        Eigen::Matrix<T, 4, 4> inv_transform = Eigen::Matrix<T, 4, 4>::Identity();
        inv_transform.template block<3, 3>(0, 0) = transform.template block<3, 3>(0, 0).transpose();
        inv_transform.template block<3, 1>(0, 3) = -inv_transform.template block<3, 3>(0, 0) * transform.template block<3, 1>(0, 3);
        return inv_transform;
    }

    ErrorCode getShoulderJointPos(
        Eigen::Vector<T, 3>& shoulder_joint_pos,
        const Eigen::Matrix<T, 4, 4> &pose,
        const Eigen::Vector<T, 3>& ref_conf)
    {
        Eigen::Matrix<T, 3, 4> possible_joint_pos;

        int result_count = 0;

        // Inverse of base transform matrix
        Eigen::Matrix<T, 4, 4> base_transform_inv = Eigen::Matrix<T, 4, 4>::Identity();
        base_transform_inv.template block<3, 3>(0, 0) = this->base_transform_.template block<3, 3>(0, 0).transpose();
        base_transform_inv.template block<3, 1>(0, 3) = -base_transform_inv.template block<3, 3>(0, 0) * this->base_transform_.template block<3, 1>(0, 3);

        // Pose in arm base frame
        Eigen::Matrix<T, 4, 4> pose_base = base_transform_inv * pose;

        // Wrist position in arm base frame
        Eigen::Vector<T, 3> pw0 = pose_base.template block<3, 1>(0, 3) - d6 * pose_base.template block<3, 1>(0, 2);

        Eigen::Vector<T, 2> theta1;
        Eigen::Vector<T, 2> theta2;
        Eigen::Vector<T, 2> theta3;

        theta1(0) = atan2(pw0(1), pw0(0));

        if (theta1(0) > 0)
        {
            theta1(1) = theta1(0) - M_PI;
        }
        else
        {
            theta1(1) = theta1(0) + M_PI;
        }

        for (int i = 0; i < 2; ++i)
        {
            // Transform matrix from arm base frame to link 1 frame
            Eigen::Matrix<T, 4, 4> T01;
            T01 << cos(theta1(i)), -sin(theta1(i)), 0, 0,
                sin(theta1(i)), cos(theta1(i)), 0, 0,
                0, 0, 1, d1,
                0, 0, 0, 1;
            Eigen::Matrix<T, 4, 4> T01_inv = Eigen::Matrix<T, 4, 4>::Identity();
            T01_inv.template block<3, 3>(0, 0) = T01.template block<3, 3>(0, 0).transpose();
            T01_inv.template block<3, 1>(0, 3) = -T01_inv.template block<3, 3>(0, 0) * T01.template block<3, 1>(0, 3);

            // Wrist pose transformation matrix in link 1 frame
            Eigen::Vector<T, 4> pos_wrist_1 = T01_inv * Eigen::Vector<T, 4>(pw0(0),pw0(1),pw0(2),1);
            
            // X, Y, Z position of wrist in link 1 frame
            T xw1 = pos_wrist_1(0);
            T zw1 = pos_wrist_1(2);

            T temp1 = (xw1 * xw1 + zw1 * zw1 - d4 * d4 - a4 * a4 + a3 * a3) / (2 * zw1);
            T temp2 = xw1 / zw1;

            T delta = temp1 * temp1 * temp2 * temp2 - (1 + temp2 * temp2) * (temp1 * temp1 - a3 * a3);
            if (delta < 0)
            {
                if (delta > 1e-5)
                {
                    delta = 0;
                }
                else
                {
                    /* no wrist position solution. */
                    shoulder_joint_pos.setZero();
                    return ErrorCode::NoResult;
                }
            }

            T x31_1 = (temp1 * temp2 + sqrt(delta)) / (1 + temp2 * temp2);
            T x31_2 = (temp1 * temp2 - sqrt(delta)) / (1 + temp2 * temp2);

            T z31_1 = temp1 - temp2 * x31_1;
            T z31_2 = temp1 - temp2 * x31_2;

            theta2(0) = -atan2(z31_1, x31_1);
            theta2(1) = -atan2(z31_2, x31_2);

            T temp3 = atan2(d4, -a4);
            T temp4 = acos(std::max(static_cast<T>(-1.0), std::min(static_cast<T>(1.0), (a4 * a4 + d4 * d4 + x31_1 * x31_1 + z31_1 * z31_1 - xw1 * xw1 - zw1 * zw1) /
                                            (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_1 * x31_1 + z31_1 * z31_1)))));
            T temp5 = acos(std::max(static_cast<T>(-1.0), std::min(static_cast<T>(1.0), (a4 * a4 + d4 * d4 + x31_2 * x31_2 + z31_2 * z31_2 - xw1 * xw1 - zw1 * zw1) /
                                            (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_2 * x31_2 + z31_2 * z31_2)))));

            T theta3_1 = -temp3 - temp4;
            T theta3_2 = -temp3 - temp5;
            T theta3_3 = temp4 - temp3;
            T theta3_4 = temp5 - temp3;

            if (abs(a4 * cos(theta2(0) + theta3_1) + d4 * sin(theta2(0) + theta3_1) + a3 * cos(theta2(0)) - xw1) < 1e-3)
            {
                theta3(0) = theta3_1;
            }
            else
            {
                theta3(0) = theta3_3;
            }

            if (abs(a4 * cos(theta2(1) + theta3_2) + d4 * sin(theta2(1) + theta3_2) + a3 * cos(theta2(1)) - xw1) < 1e-3)
            {
                theta3(1) = theta3_2;
            }
            else
            {
                theta3(1) = theta3_4;
            }

            if (theta3(0) > -102.78 / 180 * M_PI)
            {
                theta3(0) = theta3(0) - 2 * M_PI;
            }
            if (theta3(1) > -102.78 / 180 * M_PI)
            {
                theta3(1) = theta3(1) - 2 * M_PI;
            }
            for ( int j=0 ; j<2 ; j++ )
            {
                possible_joint_pos.col(result_count) << theta1(i),
                                                theta2(j) + 172.22 / 180 * M_PI,
                                                theta3(j) + 102.78 / 180 * M_PI;
                result_count++;
            }
        }
        int best_id = -1;
        T min_movement = std::numeric_limits<T>::max();
        for (int i = 0; i < result_count; ++i)
        {
            if (possible_joint_pos(0,i) < joint_pos_limit_low_[0] &&
                possible_joint_pos(1,i) < joint_pos_limit_low_[1] &&
                possible_joint_pos(2,i) < joint_pos_limit_low_[2] &&
                possible_joint_pos(0,i) > joint_pos_limit_high_[0] &&
                possible_joint_pos(1,i) > joint_pos_limit_high_[1] &&
                possible_joint_pos(2,i) > joint_pos_limit_high_[2])
            {
                T movement = (possible_joint_pos.col(i) - ref_conf).squaredNorm();
                if (movement < min_movement)
                {
                    min_movement = movement;
                    best_id = i;
                }
            }
        }
        if ( best_id == -1 )
        {
            shoulder_joint_pos.setZero();
            return ErrorCode::NoResult;
        }
        shoulder_joint_pos = possible_joint_pos.col(best_id);
        return ErrorCode::OK;
    }

    ErrorCode getInverseKinematics(
        Eigen::Vector<T, NumDof>& joint_pos,
        const Eigen::Matrix<T, 4, 4>& pose,
        const Eigen::Vector<T, NumDof>& ref_conf)
    {
        Eigen::Matrix<T, NumDof, 8> joint_pos_list;

        int result_count = 0;

        // Inverse of base transform matrix
        Eigen::Matrix<T, 4, 4> base_transform_inv = Eigen::Matrix<T, 4, 4>::Identity();
        base_transform_inv.template block<3, 3>(0, 0) = this->base_transform_.template block<3, 3>(0, 0).transpose();
        base_transform_inv.template block<3, 1>(0, 3) = -base_transform_inv.template block<3, 3>(0, 0) * this->base_transform_.template block<3, 1>(0, 3);

        // Pose in arm base frame
        Eigen::Matrix<T, 4, 4> pose_base = base_transform_inv * pose;

        // Wrist position in arm base frame
        Eigen::Vector<T, 3> pw0 = pose_base.template block<3, 1>(0, 3) - d6 * pose_base.template block<3, 1>(0, 2);

        Eigen::Vector<T, 2> theta1;
        Eigen::Vector<T, 2> theta2;
        Eigen::Vector<T, 2> theta3;

        theta1(0) = atan2(pw0(1), pw0(0));

        if (theta1(0) > 0)
        {
            theta1(1) = theta1(0) - M_PI;
        }
        else
        {
            theta1(1) = theta1(0) + M_PI;
        }

        for (int i = 0; i < 2; ++i)
        {
            // Transform matrix from arm base frame to link 1 frame
            Eigen::Matrix<T, 4, 4> T01;
            T01 << cos(theta1(i)), -sin(theta1(i)), 0, 0,
                sin(theta1(i)), cos(theta1(i)), 0, 0,
                0, 0, 1, d1,
                0, 0, 0, 1;
            Eigen::Matrix<T, 4, 4> T01_inv;
            T01_inv.template block<3, 3>(0, 0) = T01.template block<3, 3>(0, 0).transpose();
            T01_inv.template block<3, 1>(0, 3) = -T01_inv.template block<3, 3>(0, 0) * T01.template block<3, 1>(0, 3);
            T01_inv.template block<1, 4>(3, 0) << 0, 0, 0, 1;

            // Wrist pose transformation matrix in link 1 frame
            // Eigen::Matrix<T, 4, 4> pose_wrist_1 = T01_inv * pose_wrist_base;
            Eigen::Vector<T, 4> pos_wrist_1 = T01_inv * Eigen::Vector<T, 4>(pw0(0),pw0(1),pw0(2),1);

            // X, Y, Z position of wrist in link 1 frame
            T xw1 = pos_wrist_1(0);
            T zw1 = pos_wrist_1(2);

            T temp1 = (xw1 * xw1 + zw1 * zw1 - d4 * d4 - a4 * a4 + a3 * a3) / (2 * zw1);
            T temp2 = xw1 / zw1;

            T delta = temp1 * temp1 * temp2 * temp2 - (1 + temp2 * temp2) * (temp1 * temp1 - a3 * a3);
            if (delta < 0)
            {
                if (delta > 1e-5)
                {
                    delta = 0;
                }
                else
                {
                    /* no wrist position solution. */
                    return NoResult;
                }
            }

            T x31_1 = (temp1 * temp2 + sqrt(delta)) / (1 + temp2 * temp2);
            T x31_2 = (temp1 * temp2 - sqrt(delta)) / (1 + temp2 * temp2);

            T z31_1 = temp1 - temp2 * x31_1;
            T z31_2 = temp1 - temp2 * x31_2;

            theta2(0) = -atan2(z31_1, x31_1);
            theta2(1) = -atan2(z31_2, x31_2);

            T temp3 = atan2(d4, -a4);
            T temp4 = acos(std::max(static_cast<T>(-1.0), std::min(static_cast<T>(1.0), (a4 * a4 + d4 * d4 + x31_1 * x31_1 + z31_1 * z31_1 - xw1 * xw1 - zw1 * zw1) /
                                            (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_1 * x31_1 + z31_1 * z31_1)))));
            T temp5 = acos(std::max(static_cast<T>(-1.0), std::min(static_cast<T>(1.0), (a4 * a4 + d4 * d4 + x31_2 * x31_2 + z31_2 * z31_2 - xw1 * xw1 - zw1 * zw1) /
                                            (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_2 * x31_2 + z31_2 * z31_2)))));

            T theta3_1 = -temp3 - temp4;
            T theta3_2 = -temp3 - temp5;
            T theta3_3 = temp4 - temp3;
            T theta3_4 = temp5 - temp3;

            if (abs(a4 * cos(theta2(0) + theta3_1) + d4 * sin(theta2(0) + theta3_1) + a3 * cos(theta2(0)) - xw1) < 1e-3)
            {
                theta3(0) = theta3_1;
            }
            else
            {
                theta3(0) = theta3_3;
            }

            if (abs(a4 * cos(theta2(1) + theta3_2) + d4 * sin(theta2(1) + theta3_2) + a3 * cos(theta2(1)) - xw1) < 1e-3)
            {
                theta3(1) = theta3_2;
            }
            else
            {
                theta3(1) = theta3_4;
            }

            if (theta3(0) > -102.78 / 180 * M_PI)
            {
                theta3(0) = theta3(0) - 2 * M_PI;
            }
            if (theta3(1) > -102.78 / 180 * M_PI)
            {
                theta3(1) = theta3(1) - 2 * M_PI;
            }

            for (int j = 0; j < 2; ++j)
            {
                Eigen::Matrix<T, 3, 3> R1, R2, R3;
                R1 = Eigen::AngleAxis<T>(theta1(i), Eigen::Vector<T, 3>::UnitZ()).toRotationMatrix();
                R2 = Eigen::AngleAxis<T>(theta2(j), Eigen::Vector<T, 3>::UnitY()).toRotationMatrix();
                R3 = Eigen::AngleAxis<T>(theta3(j), Eigen::Vector<T, 3>::UnitY()).toRotationMatrix();

                Eigen::Matrix<T, 3, 3> R = R3.transpose() * R2.transpose() * R1.transpose() * pose_base.template block<3, 3>(0, 0);

                Eigen::Vector<T, 2> theta4;
                Eigen::Vector<T, 2> theta5;
                Eigen::Vector<T, 2> theta6;

                theta4(0) = atan2(R(1, 2), R(0, 2));
                if (theta4(0) > 0)
                {
                    theta4(1) = theta4(0) - M_PI;
                }
                else
                {
                    theta4(1) = theta4(0) + M_PI;
                }

                theta5(0) = atan2(sqrt(R(2, 0) * R(2, 0) + R(2, 1) * R(2, 1)), R(2, 2));
                theta5(1) = -theta5(0);

                theta6(0) = atan2(R(2, 1), -R(2, 0));
                if (theta6(0) > 0)
                {
                    theta6(1) = theta6(0) - M_PI;
                }
                else
                {
                    theta6(1) = theta6(0) + M_PI;
                }

                for (int k = 0; k < 2; ++k)
                {
                    joint_pos_list.col(result_count) << theta1(i),
                                                theta2(j) + 172.22 / 180 * M_PI,
                                                theta3(j) + 102.78 / 180 * M_PI,
                                                theta4(k),
                                                theta5(k),
                                                theta6(k);
                    result_count++;
                }
            }
        }

        int best_id = -1;
        T min_movement = std::numeric_limits<T>::max();

        for (int i = 0; i < result_count; ++i)
        {
            int greater = 1;
            for ( int j=0 ; j<NumDof ; j++ )
            {
                if ( joint_pos_list(j,i) < joint_pos_limit_low_[j] )
                {
                    greater = 0;
                }
            }
            int less = 1;
            for ( int j=0 ; j<NumDof ; j++ )
            {
                if ( joint_pos_list(j,i) > joint_pos_limit_high_[j] )
                {
                    less = 0;
                }
            }
            if (less && greater)
            {
                T movement = (joint_pos_list.col(i) - ref_conf).squaredNorm();
                if (movement < min_movement)
                {
                    min_movement = movement;
                    best_id = i;
                }
            }
        }
        if ( best_id == -1 )
        {
            return NoResult;
        }

        joint_pos = joint_pos_list.col(best_id);

        return OK;
    }

    ErrorCode getDampedLeastSquareInverseKinematics(
        Eigen::Vector<T,NumDof>& joint_pos, 
        const PiperArmModel<T>& model,
        const Eigen::Matrix<T, 4, 4> &pose,
        const Eigen::Vector<T, 6>& ref_conf,
        const T lambda = 0.1,
        const Eigen::Vector<T, 6> tolerance = Eigen::Vector<T, 6>(0.05, 0.05, 0.05, 0.1, 0.1, 0.1),
        const size_t max_iteration = 200)
    {
        auto getPoseDiff = [](const Eigen::Matrix<T, 4, 4>& target_pose, const Eigen::Matrix<T, 4, 4>& current_pose)
        {
            Eigen::Vector<T,6> pose_diff = Eigen::Vector<T,6>::Zero();
            pose_diff.template block<3,1>(0,0) = target_pose.template block<3,1>(0,3) - current_pose.template block<3,1>(0,3);
            Eigen::Quaternion<T> target_quat(target_pose.template block<3,3>(0,0));
            Eigen::Quaternion<T> current_quat(current_pose.template block<3,3>(0,0));
            pose_diff.template block<3,1>(3,0) = (target_quat * current_quat.conjugate()).vec();
            return pose_diff;
        };
        auto getDampedLeastSquares = [](const Eigen::Matrix<T,6,NumDof>& J, const Eigen::Vector<T,6>& dx, T lambda = 0.1)
        {
            Eigen::Matrix<T,NumDof,NumDof> I = Eigen::Matrix<T,NumDof,NumDof>::Identity();
            Eigen::Matrix<T,NumDof,NumDof> JJT_plus_lambdaI = J * J.transpose() + lambda * lambda * I;
            Eigen::Matrix<T,NumDof,NumDof> dls_pinv = J.transpose() * JJT_plus_lambdaI.completeOrthogonalDecomposition().pseudoInverse();
            return dls_pinv * dx;
        };

        ErrorCode err = OK;
        
        Eigen::Vector<T,NumDof> best_joint_pos = Eigen::Vector<T,NumDof>::Zero();
        Eigen::Vector<T,NumDof> joint_pos_diff = Eigen::Vector<T,NumDof>::Zero();
        Eigen::Vector<T, 3> shoulder_joint_pos = Eigen::Vector<T, 3>::Zero();

        err = getShoulderJointPos(shoulder_joint_pos, pose, ref_conf.template block<3,1>(0,0));

        if ( err == NoResult )
        {
            return err;
        }

        best_joint_pos.template block<3,1>(0,0) = shoulder_joint_pos;

        for ( size_t i=0 ; i<max_iteration ; i++ )
        {
            auto [link_transform, link_com_transform] = model.getTransform(best_joint_pos);
            auto link_jacobian = model.getLinkSpaceJacobian(link_transform);
            Eigen::Vector<T, 6> pose_diff = getPoseDiff(pose, link_transform[5]);

            /* Check if the pose difference is within the tolerance */
            if ( (pose_diff.array() < tolerance.array()).all() )
            {
                joint_pos = best_joint_pos;
                return OK;
            }

            joint_pos_diff = getDampedLeastSquares(link_jacobian[5], pose_diff, lambda);

            best_joint_pos += joint_pos_diff;
        }
        joint_pos = best_joint_pos;

        return err;
    }

private:
    Eigen::Matrix<T, 4, 4> base_transform_;
    static const std::array<Eigen::Matrix<T, 4, 4>, NumLink> default_transform_;
    static const std::array<T, NumLink> mass_;
    static const std::array<Eigen::Matrix<T, 3, 3>, NumLink> inertia_;
    static const std::array<Eigen::Vector<T, 3>, NumLink> center_of_mass_;
    static const std::array<Eigen::Vector<T, 3>, NumLink> joint_axis_;
    static const std::array<JointType, NumLink> joint_type_;
    static const std::array<T, NumDof> joint_pos_limit_low_;
    static const std::array<T, NumDof> joint_pos_limit_high_;
    static const std::array<T, NumDof> joint_vel_limit_low_;
    static const std::array<T, NumDof> joint_vel_limit_high_;
    static const std::array<T, NumDof> joint_acc_limit_low_;
    static const std::array<T, NumDof> joint_acc_limit_high_;
    static const std::array<T, NumDof> joint_torque_limit_low_;
    static const std::array<T, NumDof> joint_torque_limit_high_;

    /* Inverse Kinematics Parameters */
    static constexpr T d1 = 0.123;
    static constexpr T alpha2 = -M_PI / 2;
    static constexpr T a3 = 0.28503;
    static constexpr T d4 = 0.25075;
    static constexpr T a4 = -0.02198;
    static constexpr T alpha5 = -M_PI / 2;
    static constexpr T d6 = 0.091;
    static constexpr T alpha6 = M_PI / 2;
};

template<typename T>
const std::array<Eigen::Matrix<T, 4, 4>, PiperArmModel<T>::NumLink> PiperArmModel<T>::default_transform_ =
{
    getTransformFromRotationAndTranslation<T>(0, 0, 0.123, 0, 0, 0),
    getTransformFromRotationAndTranslation<T>(0, 0, 0, M_PI/2, -0.1359, -M_PI),
    getTransformFromRotationAndTranslation<T>(0.28503, 0, 0, 0, 0, -1.7939),
    getTransformFromRotationAndTranslation<T>(-0.021984, -0.25075, 0, M_PI/2, 0, 0),
    getTransformFromRotationAndTranslation<T>(0, 0, 0, -M_PI/2, 0, 0),
    getTransformFromRotationAndTranslation<T>(0, -0.091, 0, M_PI/2, 0, 0),
    getTransformFromRotationAndTranslation<T>(0, 0, 0, 0, 0, 0),
    // getTransformFromRotationAndTranslation<T>(0, 0, 0.1358, M_PI/2, 0, 0),
    // getTransformFromRotationAndTranslation<T>(0, 0, 0.1358, M_PI/2, 0, -M_PI),
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumLink> PiperArmModel<T>::mass_ =
{
    0.71, 1.17, 0.5, 0.38, 0.383, 0.007, 0.45,
    // 0.025, 0.025
};

template<typename T>
const std::array<Eigen::Matrix<T, 3, 3>, PiperArmModel<T>::NumLink> PiperArmModel<T>::inertia_ =
{
    getInertial<T>(0.00048916, 0.00040472, 0.00043982, -0.00000036, -0.00000224, -0.00000242),
    getInertial<T>(0.00116918, 0.06785384, 0.06774489, -0.00180037, 0.00025146, -0.00000455),
    getInertial<T>(0.01361711, 0.00045024, 0.01380322, 0.00165794, -0.00000048, -0.00000045),
    getInertial<T>(0.00018501, 0.00018965, 0.00015484, 0.00000054, 0.00000120, -0.00000841),
    getInertial<T>(0.00166169, 0.00018510, 0.00164321, 0.00000006, -0.00000007, 0.00001026),
    getInertial<T>(5.73015540542155E-07, 5.73015540542155E-07, 1.06738869138926E-06, -1.98305403089247E-22, -7.2791893904596E-23, -3.4146026640245E-24),
    getInertial<T>(0.00092934, 0.00071447, 0.00039442, 0.00000034, -0.00000738, 0.00000005),
    // getInertial<T>(0.00007371, 0.00000781, 0.0000747, -0.00000113, 0.00000021, -0.00001372),
    // getInertial<T>(0.00007371, 0.00000781, 0.0000747, -0.00000113, 0.00000021, -0.00001372),
};

template<typename T>
const std::array<Eigen::Vector<T, 3>, PiperArmModel<T>::NumLink> PiperArmModel<T>::center_of_mass_ =
{
    (Eigen::Vector<T, 3>() << 0.000121504734057468, 0.000104632162460536, -0.00438597309559853).finished(),
    (Eigen::Vector<T, 3>() << 0.198666145229743, -0.010926924140076, 0.00142121714502687).finished(),
    (Eigen::Vector<T, 3>() << -0.0202737662122021, -0.133914995944595, -0.000458682652737356).finished(),
    (Eigen::Vector<T, 3>() << -9.66635791618542E-05, 0.000876064475651083, -0.00496880904640868).finished(),
    (Eigen::Vector<T, 3>() << -4.10554118924211E-05, -0.0566486692356075, -0.0037205791677906).finished(),
    (Eigen::Vector<T, 3>() << -8.82590762930069E-05, 9.0598378529832E-06, -0.002).finished(),
    (Eigen::Vector<T, 3>() << -0.000183807162235591, 8.05033155577911E-05, 0.0321436689908876).finished(),
    // (Eigen::Vector<T, 3>() << 0.00065123185041968, -0.0491929869131989, 0.00972258769184025).finished(),
    // (Eigen::Vector<T, 3>() << 0.000651231850419722, -0.0491929869131991, 0.00972258769184024).finished(),
};

template<typename T>
const std::array<Eigen::Vector<T, 3>, PiperArmModel<T>::NumLink> PiperArmModel<T>::joint_axis_ =
{
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 1).finished(),
    (Eigen::Vector<T, 3>() << 0, 0, 0).finished(), // fixed joint
    // (Eigen::Vector<T, 3>() << 0, 0, -1).finished(),
    // (Eigen::Vector<T, 3>() << 0, 0, -1).finished(),
};

template<typename T>
const std::array<JointType, PiperArmModel<T>::NumLink> PiperArmModel<T>::joint_type_ =
{
    JOINT_REVOLUTE,
    JOINT_REVOLUTE,
    JOINT_REVOLUTE,
    JOINT_REVOLUTE,
    JOINT_REVOLUTE,
    JOINT_REVOLUTE,
    JOINT_FIXED,
    // JOINT_PRISMATIC,
    // JOINT_PRISMATIC
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_pos_limit_low_ =
{
    -2.618, 0, -2.967, -1.745, -1.22, -2.0944
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_pos_limit_high_ =
{
    2.618, M_PI, 0, 1.745, 1.22, 2.0944
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_vel_limit_low_ =
{
    -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_vel_limit_high_ =
{
    4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_acc_limit_low_ =
{
    -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_acc_limit_high_ =
{
    2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_torque_limit_low_ =
{
    -45, -45, -45, -30, -30, -20
};

template<typename T>
const std::array<T, PiperArmModel<T>::NumDof> PiperArmModel<T>::joint_torque_limit_high_ =
{
    45, 45, 45, 30, 30, 20
};