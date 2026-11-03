/**
 * @file arm_model.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm model, including kinematics and dynamics.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <arm_model.h>

template<typename T>
constexpr Eigen::Matrix<T,4,4> getTransformFromRotationAndTranslation(T x, T y, T z, T roll, T pitch, T yaw)
{
    Eigen::Matrix<T,4,4> transform = Eigen::Matrix<T,4,4>::Identity();
    Eigen::AngleAxis<T> angle_x(roll, Eigen::Vector<T,3>::UnitX());
    Eigen::AngleAxis<T> angle_y(pitch, Eigen::Vector<T,3>::UnitY());
    Eigen::AngleAxis<T> angle_z(yaw, Eigen::Vector<T,3>::UnitZ());
    Eigen::Quaternion<T> q = angle_z * angle_y * angle_x;
    transform.template block<3,3>(0,0) = q.toRotationMatrix();
    transform(0,3) = x;
    transform(1,3) = y;
    transform(2,3) = z;
    return transform;
};

template<typename T>
constexpr Eigen::Matrix<T,3,3> getInertial(T ixx, T iyy, T izz, T ixy, T ixz, T iyz)
{
    return (Eigen::Matrix<T,3,3>() << ixx, ixy, ixz, ixy, iyy, iyz, ixz, iyz, izz).finished();
};

const std::array<Eigen::Matrix4d,ArmModel::num_link_> ArmModel::default_transform_ =
{
    getTransformFromRotationAndTranslation<double>(0,0,0.123,0,0,0),
    getTransformFromRotationAndTranslation<double>(0,0,0,M_PI/2,-0.1359,-M_PI),
    getTransformFromRotationAndTranslation<double>(0.28503,0,0,0,0,-1.7939),
    getTransformFromRotationAndTranslation<double>(-0.021984,-0.25075,0,M_PI/2,0,0),
    getTransformFromRotationAndTranslation<double>(0,0,0,-M_PI/2,0,0),
    getTransformFromRotationAndTranslation<double>(0,-0.091,0,M_PI/2,0,0),
    getTransformFromRotationAndTranslation<double>(0,0,0,0,0,0),
    // getTransformFromRotationAndTranslation<double>(0,0,0.1358,M_PI/2,0,0),
    // getTransformFromRotationAndTranslation<double>(0,0,0.1358,M_PI/2,0,-M_PI),
};

const std::array<double,ArmModel::num_link_> ArmModel::mass_ =
{
    0.71, 1.17, 0.5, 0.38, 0.383, 0.007, 0.45,
    // 0.025, 0.025
};

const std::array<Eigen::Matrix3d,ArmModel::num_link_> ArmModel::inertia_ =
{
    getInertial<double>(0.00048916, 0.00040472, 0.00043982, -0.00000036, -0.00000224, -0.00000242),
    getInertial<double>(0.00116918, 0.06785384, 0.06774489, -0.00180037, 0.00025146, -0.00000455),
    getInertial<double>(0.01361711, 0.00045024, 0.01380322, 0.00165794, -0.00000048, -0.00000045),
    getInertial<double>(0.00018501, 0.00018965, 0.00015484, 0.00000054, 0.00000120, -0.00000841),
    getInertial<double>(0.00166169, 0.00018510, 0.00164321, 0.00000006, -0.00000007, 0.00001026),
    getInertial<double>(5.73015540542155E-07, 5.73015540542155E-07, 1.06738869138926E-06, -1.98305403089247E-22, -7.2791893904596E-23, -3.4146026640245E-24),
    getInertial<double>(0.00092934, 0.00071447, 0.00039442, 0.00000034, -0.00000738, 0.00000005),
    // getInertial<double>(0.00007371, 0.00000781, 0.0000747, -0.00000113, 0.00000021, -0.00001372),
    // getInertial<double>(0.00007371, 0.00000781, 0.0000747, -0.00000113, 0.00000021, -0.00001372),
};

const std::array<Eigen::Vector3d,ArmModel::num_link_> ArmModel::center_of_mass_ =
{
    (Eigen::Vector3d() << 0.000121504734057468, 0.000104632162460536, -0.00438597309559853).finished(),
    (Eigen::Vector3d() << 0.198666145229743, -0.010926924140076, 0.00142121714502687).finished(),
    (Eigen::Vector3d() << -0.0202737662122021, -0.133914995944595, -0.000458682652737356).finished(),
    (Eigen::Vector3d() << -9.66635791618542E-05, 0.000876064475651083, -0.00496880904640868).finished(),
    (Eigen::Vector3d() << -4.10554118924211E-05, -0.0566486692356075, -0.0037205791677906).finished(),
    (Eigen::Vector3d() << -8.82590762930069E-05, 9.0598378529832E-06, -0.002).finished(),
    (Eigen::Vector3d() << -0.000183807162235591, 8.05033155577911E-05, 0.0321436689908876).finished(),
    // (Eigen::Vector3d() << 0.00065123185041968, -0.0491929869131989, 0.00972258769184025).finished(),
    // (Eigen::Vector3d() << 0.000651231850419722, -0.0491929869131991, 0.00972258769184024).finished(),
};

const std::array<Eigen::Vector3d,ArmModel::num_link_> ArmModel::joint_axis_ =
{
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 1).finished(),
    (Eigen::Vector3d() << 0, 0, 0).finished(), // fixed joint
    // (Eigen::Vector3d() << 0, 0, -1).finished(),
    // (Eigen::Vector3d() << 0, 0, -1).finished(),
};

const std::array<JointType,ArmModel::num_link_> ArmModel::joint_type_ =
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

const std::array<double,ArmModel::num_dof_> ArmModel::joint_pos_limit_low_ =
{
    -2.618, 0, -2.967, -1.745, -1.22, -2.0944
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_pos_limit_high_ =
{
    2.618, M_PI, 0, 1.745, 1.22, 2.0944
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_vel_limit_low_ =
{
    -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI, -4*M_PI
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_vel_limit_high_ =
{
    4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI, 4*M_PI
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_acc_limit_low_ =
{
    -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI, -2*M_PI
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_acc_limit_high_ =
{
    2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI, 2*M_PI
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_torque_limit_low_ =
{
    -45, -45, -45, -30, -30, -20
};

const std::array<double,ArmModel::num_dof_> ArmModel::joint_torque_limit_high_ =
{
    45, 45, 45, 30, 30, 20
};

void ArmModel::limitJointPosition(Eigen::Vector<double,num_dof_>& joint_pos) const
{
    for ( int i=0 ; i<num_dof_ ; i++ )
    {
        joint_pos(i) = std::clamp(joint_pos(i), joint_pos_limit_low_[i], joint_pos_limit_high_[i]);
    }
}
void ArmModel::limitJointVelocity(Eigen::Vector<double,num_dof_>& joint_vel) const
{
    for ( int i=0 ; i<num_dof_ ; i++ )
    {
        joint_vel(i) = std::clamp(joint_vel(i), joint_vel_limit_low_[i], joint_vel_limit_high_[i]);
    }
}
void ArmModel::limitJointTorque(Eigen::Vector<double,num_dof_>& joint_torque) const
{
    for ( int i=0 ; i<num_dof_ ; i++ )
    {
        joint_torque(i) = std::clamp(joint_torque(i), joint_torque_limit_low_[i], joint_torque_limit_high_[i]);
    }
}

void ArmModel::getTransform(
    std::array<Eigen::Matrix4d,num_link_>& link_transform,
    std::array<Eigen::Matrix4d,num_link_>& com_transform,
    const Eigen::Vector<double,num_dof_>& joint_pos) const
{
    /* Transform of joint rotation */
    Eigen::Matrix4d joint_rotate_transform = Eigen::Matrix4d::Identity();
    Eigen::Matrix4d link_transform_local = Eigen::Matrix4d::Identity();

    /* Calculate transform of other links */
    for ( int i=0 ; i<num_link_ ; i++ )
    {
        joint_rotate_transform = Eigen::Matrix4d::Identity();
        link_transform_local = Eigen::Matrix4d::Identity();

        if ( joint_type_[i] == JOINT_REVOLUTE )
        {
            joint_rotate_transform.block<3,3>(0,0) = Eigen::AngleAxisd(joint_pos[i], joint_axis_[i]).toRotationMatrix();
        }
        else if ( joint_type_[i] == JOINT_PRISMATIC )
        {
            joint_rotate_transform.block<3,1>(0,3) = joint_pos[i] * joint_axis_[i];
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

        com_transform[i].block<3,1>(0,3) += link_transform[i].block<3,3>(0,0) * center_of_mass_[i];
    }
}


void ArmModel::getLinkVelocity(
    std::array<Eigen::Vector3d,num_link_>& link_lin_vel,
    std::array<Eigen::Vector3d,num_link_>& link_ang_vel,
    std::array<Eigen::Vector3d,num_link_>& link_com_lin_vel,
    std::array<Eigen::Vector3d,num_link_>& link_com_ang_vel,
    const std::array<Eigen::Matrix4d,num_link_>& link_transform,
    const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
    const Eigen::Vector<double,num_dof_>& joint_vel) const
{
    Eigen::Matrix3d rotation = Eigen::Matrix3d::Identity();
    Eigen::Vector3d link_translation;
    Eigen::Vector3d link_com_translation;

    for ( int i=0 ; i<num_link_ ; i++ )
    {
        rotation = link_transform[i].block<3,3>(0,0);
        if ( i == 0 )
        {
            link_translation = link_transform[i].block<3,1>(0,3);
            link_com_translation = link_com_transform[i].block<3,1>(0,3);
        }
        else
        {
            link_translation = link_transform[i].block<3,1>(0,3) - link_transform[i-1].block<3,1>(0,3);
            link_com_translation = link_com_transform[i].block<3,1>(0,3) - link_transform[i].block<3,1>(0,3);
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
}

void ArmModel::getLinkSpaceJacobian(
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
    const std::array<Eigen::Matrix4d,num_link_>& link_transform) const
{
    for ( int i=0 ; i<num_link_ ; i++ )
    {
        link_com_jacobian[i].setZero();
        for ( int j=0, col=0; j<=i ; j++ )
        {
            Eigen::Matrix3d rotation = link_transform[j].block<3,3>(0,0);
            Eigen::Vector3d pos_i = link_transform[i].block<3,1>(0,3);
            Eigen::Vector3d pos_j = link_transform[j].block<3,1>(0,3);
            if ( joint_type_[j] == JOINT_REVOLUTE )
            {
                link_com_jacobian[i].block<3,1>(0,col) = (rotation * joint_axis_[j]).cross(pos_i - pos_j);
                link_com_jacobian[i].block<3,1>(3,col) = rotation * joint_axis_[j];
                col++;
            }
            else if ( joint_type_[j] == JOINT_PRISMATIC )
            {
                link_com_jacobian[i].block<3,1>(0,col) = rotation * joint_axis_[j];
                link_com_jacobian[i].block<3,1>(3,col).setZero();
                col++;
            }
            // else if ( joint_type_[j] == JOINT_FIXED )
            // {
            //     link_com_jacobian[i].block<6,1>(0,j).setZero(); 
            // }
        }
    }
}

void ArmModel::getLinkComSpaceJacobian(
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
    const std::array<Eigen::Matrix4d,num_link_>& link_transform,
    const std::array<Eigen::Matrix4d,num_link_>& link_com_transform) const
{
    for ( int i=0 ; i<num_link_ ; i++ )
    {
        link_com_jacobian[i].setZero();
        for ( int j=0, col=0; j<=i ; j++ )
        {
            Eigen::Matrix3d rotation = link_transform[j].block<3,3>(0,0);
            Eigen::Vector3d pos_i = link_com_transform[i].block<3,1>(0,3);
            Eigen::Vector3d pos_j = link_transform[j].block<3,1>(0,3);
            if ( joint_type_[j] == JOINT_REVOLUTE )
            {
                link_com_jacobian[i].block<3,1>(0,col) = (rotation * joint_axis_[j]).cross(pos_i - pos_j);
                link_com_jacobian[i].block<3,1>(3,col) = rotation * joint_axis_[j];
                col++;
            }
            else if ( joint_type_[j] == JOINT_PRISMATIC )
            {
                link_com_jacobian[i].block<3,1>(0,col) = rotation * joint_axis_[j];
                link_com_jacobian[i].block<3,1>(3,col).setZero();
                col++;
            }
            // else if ( joint_type_[j] == JOINT_FIXED )
            // {
            //     link_com_jacobian[i].block<6,1>(0,j).setZero(); 
            // }
        }
    }
}

void ArmModel::getLinkComSpaceJacobianDot(
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian_dot,
    const std::array<Eigen::Matrix4d,num_link_>& link_transform,
    const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
    const std::array<Eigen::Vector3d,num_link_>& link_lin_vel,
    const std::array<Eigen::Vector3d,num_link_>& link_ang_vel,
    const std::array<Eigen::Vector3d,num_link_>& link_com_lin_vel) const
{
    for ( int i=0 ; i<num_link_ ; i++ )
    {
        link_com_jacobian_dot[i].setZero();
        for ( int j=0,col=0 ; j<=i ; j++ )
        {
            Eigen::Matrix3d rotation = link_transform[j].block<3,3>(0,0);
            Eigen::Vector3d pos_i = link_com_transform[i].block<3,1>(0,3);
            Eigen::Vector3d pos_j = link_transform[j].block<3,1>(0,3);
            Eigen::Vector3d vel_i = link_com_lin_vel[i];
            Eigen::Vector3d vel_j = link_lin_vel[j];
            if ( joint_type_[j] == JOINT_REVOLUTE )
            {
                link_com_jacobian_dot[i].block<3,1>(0,col) = (link_ang_vel[j].cross(rotation * joint_axis_[j])).cross(pos_i - pos_j) + (rotation * joint_axis_[j]).cross(vel_i - vel_j);
                link_com_jacobian_dot[i].block<3,1>(3,col) = link_ang_vel[j].cross(rotation * joint_axis_[j]);
                col++;
            }
            else if ( joint_type_[j] == JOINT_PRISMATIC )
            {
                link_com_jacobian_dot[i].block<3,1>(0,col) = link_ang_vel[j].cross(rotation * joint_axis_[j]);
                link_com_jacobian_dot[i].block<3,1>(3,col).setZero();
                col++;
            }
            // else if ( joint_type_[j] == JOINT_FIXED )
            // {
            //     link_com_jacobian_dot[i].block<6,1>(0,j).setZero();
            // }
        }
    }
}

Eigen::Matrix<double,ArmModel::num_dof_,ArmModel::num_dof_> ArmModel::getJointSpaceMassMatrix(
    const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
    const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian) const
{
    Eigen::Matrix<double,num_dof_,num_dof_> generalized_mass_matrix;

    generalized_mass_matrix.setZero();

    Eigen::Matrix<double,3,num_dof_> J_v;
    Eigen::Matrix<double,3,num_dof_> J_w;
    Eigen::Matrix3d inertia_g;

    for ( int i=0 ; i<num_link_ ; i++ )
    {
        /* Extract linear velocity part of jacobian matrix */
        J_v = link_com_jacobian[i].block<3,num_dof_>(0,0);
        /* Extract angular velocity part of jacobian matrix */
        J_w = link_com_jacobian[i].block<3,num_dof_>(3,0);

        /* rotate inertia matrix to base frame */
        inertia_g = link_com_transform[i].block<3,3>(0,0) * inertia_[i] * link_com_transform[i].block<3,3>(0,0).transpose();

        generalized_mass_matrix = generalized_mass_matrix + 
            J_v.transpose() * mass_[i] * J_v + J_w.transpose() * inertia_g * J_w;
    }

    return generalized_mass_matrix;
}

Eigen::Matrix<double,ArmModel::num_dof_,ArmModel::num_dof_> ArmModel::getJointSpaceCoriolisMatrix(
    const std::array<Eigen::Matrix4d,num_link_>& link_com_transform,
    const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
    const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian_dot,
    const Eigen::Vector<double,num_dof_>& joint_vel) const
{
    Eigen::Matrix<double,num_dof_,num_dof_> centrifugal_coriolis_matrix;

    Eigen::Matrix<double,3,num_dof_> J_v;
    Eigen::Matrix<double,3,num_dof_> J_w;
    Eigen::Matrix<double,3,num_dof_> Jd_v;
    Eigen::Matrix<double,3,num_dof_> Jd_w;
    Eigen::Matrix3d inertia_g;

    auto getSymmetricSkew = [](const Eigen::Vector3d& vec)
    {
        Eigen::Matrix3d skew_matrix;
        skew_matrix << 0, -vec(2), vec(1),
                       vec(2), 0, -vec(0),
                      -vec(1), vec(0), 0;
        return skew_matrix;
    };

    centrifugal_coriolis_matrix.setZero();

    for ( int i=0 ; i<num_link_ ; i++ )
    {
        /* Extract linear velocity part of jacobian matrix */
        J_v = link_com_jacobian[i].block<3,num_dof_>(0,0);
        /* Extract angular velocity part of jacobian matrix */
        J_w = link_com_jacobian[i].block<3,num_dof_>(3,0);
        /* Extract linear velocity part of time derivative jacobian matrix */
        Jd_v = link_com_jacobian_dot[i].block<3,num_dof_>(0,0);
        /* Extract angular velocity part of time derivative jacobian matrix */
        Jd_w = link_com_jacobian_dot[i].block<3,num_dof_>(3,0);
        /* rotate inertia matrix to base frame */
        inertia_g = link_com_transform[i].block<3,3>(0,0) * inertia_[i] * link_com_transform[i].block<3,3>(0,0).transpose();

        centrifugal_coriolis_matrix = centrifugal_coriolis_matrix +
            J_v.transpose() * mass_[i] * Jd_v + J_w.transpose() * inertia_g * Jd_w + J_w.transpose() * getSymmetricSkew(J_w * joint_vel) * inertia_g * J_w;
    }

    return centrifugal_coriolis_matrix;
}
Eigen::Vector<double,ArmModel::num_dof_> ArmModel::getJointSpaceGravityCompensate(
    const std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian) const
{
    Eigen::Vector<double,ArmModel::num_dof_> gravity_compensate;

    gravity_compensate.setZero();

    Eigen::Matrix<double,3,num_dof_> J_v;
    Eigen::Matrix<double,3,num_dof_> J_w;
    // Eigen::Vector3d base_gravity = base_transform_.block<3,3>(0,0).transpose() * Eigen::Vector3d(0,0,-9.81);
    /* reverse of gravity force */
    Eigen::Vector3d base_gravity(0,0,9.81);

    for ( int i=0 ; i<num_link_ ; i++ )
    {
        /* Extract linear velocity part of jacobian matrix */
        J_v = link_com_jacobian[i].block<3,num_dof_>(0,0);
        /* Extract angular velocity part of jacobian matrix */
        J_w = link_com_jacobian[i].block<3,num_dof_>(3,0);
        
        gravity_compensate = gravity_compensate +
            J_v.transpose() * (mass_[i] * base_gravity);
    }

    return gravity_compensate;
}

void ArmModel::getTaskSpaceInverseDynamics(
    Eigen::Matrix<double,6,6>& task_space_mass_matrix,
    Eigen::Vector<double,6>& task_space_bias_force,
    const Eigen::Vector<double,num_dof_>& joint_pos,
    const Eigen::Vector<double,num_dof_>& joint_vel) const
{
    std::array<Eigen::Matrix4d,num_link_> link_transform;
    std::array<Eigen::Matrix4d,num_link_> link_com_transform;
    std::array<Eigen::Vector3d,num_link_> link_lin_vel;
    std::array<Eigen::Vector3d,num_link_> link_ang_vel;
    std::array<Eigen::Vector3d,num_link_> link_com_lin_vel;
    std::array<Eigen::Vector3d,num_link_> link_com_ang_vel;
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_> link_com_jacobian;
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_> link_com_jacobian_dot;
    Eigen::Matrix<double,6,num_dof_> jacobian;       // end effector center of mass jacobian
    Eigen::Matrix<double,num_dof_,6> jacobian_inv;   // inverse or pseudoinverse of end effector center of mass jacobian
    Eigen::Matrix<double,num_dof_,6> jacobian_inv_T; // transpose of inverse or pseudoinverse of end effector center of mass jacobian
    Eigen::Vector<double,6> twist;

    getTransform(link_transform, link_com_transform, joint_pos);
    getLinkVelocity(link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel, link_transform, link_com_transform, joint_vel);
    getLinkComSpaceJacobian(link_com_jacobian, link_transform, link_com_transform);
    getLinkComSpaceJacobianDot(link_com_jacobian_dot, link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
    Eigen::Matrix<double,num_dof_,num_dof_> generalized_mass_matrix = getJointSpaceMassMatrix(link_com_transform,link_com_jacobian);
    Eigen::Matrix<double,num_dof_,num_dof_> centrifugal_coriolis_matrix = getJointSpaceCoriolisMatrix(link_com_transform,link_com_jacobian,link_com_jacobian_dot, joint_vel);
    Eigen::Vector<double,num_dof_> gravity_compensate = getJointSpaceGravityCompensate(link_com_jacobian);

    jacobian = link_com_jacobian[num_link_-1];
    /* TODO: Consider psuedoinverse if DOF > 6 */
    jacobian_inv = jacobian.inverse();
    jacobian_inv_T = jacobian_inv.transpose();

    twist = jacobian * joint_vel;

    Eigen::Matrix<double,6,6> task_space_mass_matrix_inv = jacobian * generalized_mass_matrix.inverse() * jacobian.transpose();
    if ( abs( task_space_mass_matrix_inv.determinant() ) > 1e-2 )
    {
        task_space_mass_matrix = task_space_mass_matrix_inv.inverse();
    }
    else
    {
        task_space_mass_matrix = task_space_mass_matrix_inv.completeOrthogonalDecomposition().pseudoInverse();
    }

    /* TODO: potential calculation error due to sigularity of jacobian (invalid inverse of jacobian matrix) */
    task_space_bias_force = (jacobian_inv_T * centrifugal_coriolis_matrix * jacobian_inv - task_space_mass_matrix * link_com_jacobian_dot[num_link_-1] * jacobian_inv) * twist + jacobian_inv_T * gravity_compensate;
}

Eigen::Vector<double,ArmModel::num_dof_> ArmModel::getImpedanceControl(
    const Eigen::Vector<double,num_dof_>& actual_joint_pos,
    const Eigen::Vector<double,num_dof_>& actual_joint_vel,
    const Eigen::Vector3d& target_pos,
    const Eigen::Quaterniond& target_orientation) const
{
    static const double integration_dt = 0.8;
    static const double Kpos = 0.95;
    static const double Kori = 0.95;
    static const Eigen::Vector<double,6> Kp(100.0,100.0,100.0,60.0,60.0,60.0);
    static const Eigen::Vector<double,6> Ki(10.0,10.0,10.0,7.0,7.0,7.0);
    static const Eigen::Vector<double,6> Kd(20.0,20.0,20.0,14.0,14.0,14.0);
    static const Eigen::Vector<double,6> Kp_null(75.0, 75.0, 50.0, 50.0, 40.0, 25.0);
    static const Eigen::Vector<double,6> Kd_null(17,17,14,14,12.6,10);
    Eigen::Vector<double,num_dof_> torque;

    static Eigen::Vector<double,6> pose_error_int = Eigen::Vector<double,6>::Zero();
    Eigen::Vector<double,6> pose_error;
    Eigen::Vector<double,6> twist_error;

    std::array<Eigen::Matrix4d,num_link_> link_transform;
    std::array<Eigen::Matrix4d,num_link_> link_com_transform;
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_> link_com_jacobian;
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_> link_com_jacobian_dot;
    std::array<Eigen::Vector3d,num_link_> link_lin_vel;
    std::array<Eigen::Vector3d,num_link_> link_ang_vel;
    std::array<Eigen::Vector3d,num_link_> link_com_lin_vel;
    std::array<Eigen::Vector3d,num_link_> link_com_ang_vel;

    getTransform(link_transform, link_com_transform, actual_joint_pos);
    getLinkVelocity(link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel, link_transform, link_com_transform, actual_joint_vel);
    getLinkComSpaceJacobian(link_com_jacobian, link_transform, link_com_transform);
    getLinkComSpaceJacobianDot(link_com_jacobian_dot, link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
    Eigen::Matrix<double,num_dof_,num_dof_> generalized_mass_matrix = getJointSpaceMassMatrix(link_com_transform,link_com_jacobian);
    Eigen::Matrix<double,num_dof_,num_dof_> centrifugal_coriolis_matrix = getJointSpaceCoriolisMatrix(link_com_transform,link_com_jacobian,link_com_jacobian_dot, actual_joint_vel);
    Eigen::Vector<double,num_dof_> gravity_compensate = getJointSpaceGravityCompensate(link_com_jacobian);
    Eigen::Matrix<double,num_dof_,6> generalized_mass_matrix_inv = generalized_mass_matrix.inverse();

    /* Get end effector center of mass jacobian matrix assuming the last link is end effector link. */
    Eigen::Matrix<double,6,num_dof_> jacobian = link_com_jacobian[num_link_-1];

    Eigen::Matrix<double,6,6> task_space_mass_matrix_inv = jacobian * generalized_mass_matrix_inv * jacobian.transpose();
    Eigen::Matrix<double,6,6> task_space_mass_matrix;
    if ( abs( task_space_mass_matrix_inv.determinant() ) > 1e-2 )
    {
        task_space_mass_matrix = task_space_mass_matrix_inv.inverse();
    }
    else
    {
        task_space_mass_matrix = task_space_mass_matrix_inv.completeOrthogonalDecomposition().pseudoInverse();
    }

    /* BEGIN - pose error calculation with SE(3) log */
    // Eigen::Matrix4d target_pose = Eigen::Matrix4d::Identity();
    // target_pose.block<3,3>(0,0) = target_orientation.normalized().toRotationMatrix();
    // target_pose.block<3,1>(0,3) = target_pos;
    // pose_error = getSE3Log(target_pose * link_com_transform[num_link_-1].inverse());
    /* END - pose error calculation with SE(3) log */

    /* BEGIN - pose error calculation with quaternion */
    Eigen::Vector3d actual_pos = link_com_transform[num_link_-1].block<3,1>(0,3);
    pose_error.block<3,1>(0,0) = Kpos * ( target_pos - actual_pos ) / integration_dt;
    // pose_error.block<3,1>(0,0) = target_pos - actual_pos;

    Eigen::Quaterniond actual_orientation(link_com_transform[num_link_-1].block<3,3>(0,0));
    Eigen::Quaterniond error_quat = target_orientation * actual_orientation.conjugate();

    Eigen::Vector3d axis(error_quat.x(),error_quat.y(),error_quat.z());
    double sin_a_2 = axis.norm();
    axis.normalize();
    double speed = 2 * atan2(sin_a_2,error_quat.w());
    if ( speed > M_PI )
    {
        speed -= 2 * M_PI;
    }
    speed /= integration_dt;
    pose_error.block<3,1>(3,0) = Kori / integration_dt * axis * speed;
    // pose_error.block<3,1>(3,0) = Kori / integration_dt * error_quat.vec(); // Axis-angle error
    /* END - pose error calculation with quaternion */

    pose_error_int += pose_error * 0.05;

    /* Calculate end effector actual twist with actual joint angular velocity and end effector center of mass jacobian matrix */
    twist_error = - jacobian * actual_joint_vel;

    torque = jacobian.transpose() * ( task_space_mass_matrix * ( Kp.cwiseProduct(pose_error) + Ki.cwiseProduct(pose_error_int) + Kd.cwiseProduct(twist_error) ) );
    // std::cout << "error torque:" << std::endl << torque << std::endl;

    Eigen::Vector<double,6> joint_acc =  -Kp_null.cwiseProduct(actual_joint_pos) - Kd_null.cwiseProduct(actual_joint_vel);

    /* implementation in "git@github.com:kevinzakka/mjctrl.git" */
    // Eigen::Matrix<double,6,6> jacobian_bar = generalized_mass_matrix_inv * jacobian.transpose() * task_space_mass_matrix;
    // torque += ( Eigen::Matrix<double,6,6>::Identity() - jacobian.transpose() * jacobian_bar.transpose() ) * joint_acc;

    // Compute null-space projection matrix
    Eigen::MatrixXd J = jacobian;
    Eigen::MatrixXd J_JT_inv = (J * J.transpose()).completeOrthogonalDecomposition().pseudoInverse();
    Eigen::MatrixXd null_space_proj = Eigen::MatrixXd::Identity(jacobian.rows(), jacobian.cols()) - J.transpose() * J_JT_inv * J;
    torque += (null_space_proj * generalized_mass_matrix) * joint_acc;
    
    /* Add centrifugal and coriolis compensation */
    torque += centrifugal_coriolis_matrix * actual_joint_vel;

    /* Add gravity compensation */
    torque += gravity_compensate;

    // limitJointTorque(torque);
    
    return torque;
}

Eigen::Vector<double,ArmModel::num_dof_> ArmModel::getDiffIKControl(
    const Eigen::Vector<double,num_dof_>& actual_joint_pos,
    const Eigen::Vector<double,num_dof_>& actual_joint_vel,
    const Eigen::Vector3d& target_pos,
    const Eigen::Quaterniond& target_orientation)
{
    static const double integration_dt = 0.05;
    static const Eigen::Vector<double,6> k(0.1,0.1,0.1,2,2,2);
    Eigen::Vector<double,6> pose_error;

    std::array<Eigen::Matrix4d,num_link_> link_transform;
    std::array<Eigen::Matrix4d,num_link_> link_com_transform;
    std::array<Eigen::Matrix<double,6,num_dof_>,num_link_> link_com_jacobian;

    getTransform(link_transform, link_com_transform, actual_joint_pos);
    getLinkComSpaceJacobian(link_com_jacobian, link_transform, link_com_transform);

    Eigen::Matrix<double,6,num_dof_> jacobian = link_com_jacobian[num_link_-1];

    Eigen::Vector3d actual_pos = link_com_transform[num_link_-1].block<3,1>(0,3);
    pose_error.block<3,1>(0,0) = (target_pos - actual_pos);

    Eigen::Quaterniond actual_orientation(link_com_transform[num_link_-1].block<3,3>(0,0));
    Eigen::Quaterniond error_quat = target_orientation * actual_orientation.conjugate();
    pose_error.block<3,1>(3,0) = error_quat.vec();

    Eigen::Vector<double,num_dof_> target_joint_vel = jacobian.completeOrthogonalDecomposition().pseudoInverse() * k.cwiseProduct(pose_error);

    Eigen::Vector<double,6> target_joint_pos = actual_joint_pos + target_joint_vel * integration_dt;

    limitJointPosition(target_joint_pos);
    
    return target_joint_pos;
}

ErrorCode ArmModel::getShoulderJointPos(Eigen::Vector3d& shoulder_joint_pos, const Eigen::Matrix4d &pose, const Eigen::Vector3d& ref_conf) const
{
    ErrorCode err = OK;

    Eigen::Matrix<double, 3, 4> possible_joint_pos;

    int result_count = 0;

    double d1 = 0.123;
    double alpha2 = -M_PI / 2;
    double a3 = 0.28503;
    double d4 = 0.25075;
    double a4 = -0.02198;
    double alpha5 = -M_PI / 2;
    double d6 = 0.091;
    double alpha6 = M_PI / 2;

    // Inverse of base transform matrix
    Eigen::Matrix4d base_transform_inv = Eigen::Matrix4d::Identity();
    base_transform_inv.block<3, 3>(0, 0) = base_transform_.block<3, 3>(0, 0).transpose();
    base_transform_inv.block<3, 1>(0, 3) = -base_transform_inv.block<3, 3>(0, 0) * base_transform_.block<3, 1>(0, 3);

    // Pose in arm base frame
    Eigen::Matrix4d pose_base = base_transform_inv * pose;

    // Wrist position in arm base frame
    Eigen::Vector3d pw0 = pose_base.block<3, 1>(0, 3) - d6 * pose_base.block<3, 1>(0, 2);

    Eigen::Vector2d theta1;
    Eigen::Vector2d theta2;
    Eigen::Vector2d theta3;

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
        Eigen::Matrix4d T01;
        T01 << cos(theta1(i)), -sin(theta1(i)), 0, 0,
               sin(theta1(i)), cos(theta1(i)), 0, 0,
               0, 0, 1, d1,
               0, 0, 0, 1;
        Eigen::Matrix4d T01_inv = Eigen::Matrix4d::Identity();
        T01_inv.block<3, 3>(0, 0) = T01.block<3, 3>(0, 0).transpose();
        T01_inv.block<3, 1>(0, 3) = -T01_inv.block<3, 3>(0, 0) * T01.block<3, 1>(0, 3);

        // Wrist pose transformation matrix in link 1 frame
        Eigen::Vector4d pos_wrist_1 = T01_inv * Eigen::Vector4d(pw0(0),pw0(1),pw0(2),1);
        
        // X, Y, Z position of wrist in link 1 frame
        double xw1 = pos_wrist_1(0);
        double zw1 = pos_wrist_1(2);

        double temp1 = (xw1 * xw1 + zw1 * zw1 - d4 * d4 - a4 * a4 + a3 * a3) / (2 * zw1);
        double temp2 = xw1 / zw1;

        double delta = temp1 * temp1 * temp2 * temp2 - (1 + temp2 * temp2) * (temp1 * temp1 - a3 * a3);
        if (delta < 0)
        {
            if (delta > 1e-5)
            {
                delta = 0;
            }
            else
            {
                /* no wrist position solution. */
                err = NoResult;
                return err;
            }
        }

        double x31_1 = (temp1 * temp2 + sqrt(delta)) / (1 + temp2 * temp2);
        double x31_2 = (temp1 * temp2 - sqrt(delta)) / (1 + temp2 * temp2);

        double z31_1 = temp1 - temp2 * x31_1;
        double z31_2 = temp1 - temp2 * x31_2;

        theta2(0) = -atan2(z31_1, x31_1);
        theta2(1) = -atan2(z31_2, x31_2);

        double temp3 = atan2(d4, -a4);
        double temp4 = acos(std::max(-1.0, std::min(1.0, (a4 * a4 + d4 * d4 + x31_1 * x31_1 + z31_1 * z31_1 - xw1 * xw1 - zw1 * zw1) /
                                        (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_1 * x31_1 + z31_1 * z31_1)))));
        double temp5 = acos(std::max(-1.0, std::min(1.0, (a4 * a4 + d4 * d4 + x31_2 * x31_2 + z31_2 * z31_2 - xw1 * xw1 - zw1 * zw1) /
                                        (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_2 * x31_2 + z31_2 * z31_2)))));

        double theta3_1 = -temp3 - temp4;
        double theta3_2 = -temp3 - temp5;
        double theta3_3 = temp4 - temp3;
        double theta3_4 = temp5 - temp3;

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
    int best_id = 0;
    double min_movement = std::numeric_limits<double>::max();
    for (int i = 0; i < result_count; ++i)
    {
        int greater = 1;
        for ( int j=0 ; j<3 ; j++ )
        {
            if ( possible_joint_pos(j,i) < joint_pos_limit_low_[j] )
            {
                greater = 0;
            }
        }
        int less = 1;
        for ( int j=0 ; j<3 ; j++ )
        {
            if ( possible_joint_pos(j,i) > joint_pos_limit_high_[j] )
            {
                less = 0;
            }
        }
        if (less && greater)
        {
            double movement = (possible_joint_pos.col(i) - ref_conf).squaredNorm();
            if (movement < min_movement)
            {
                min_movement = movement;
                best_id = i;
            }
        }
    }
    shoulder_joint_pos = possible_joint_pos.col(best_id);

    return err;
}

ErrorCode ArmModel::getInverseKinematics(
    Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    const Eigen::Matrix4d& pose,
    const Eigen::Vector<double,6>& ref_conf) const
{
    Eigen::Matrix<double, 6, 8> joint_pos_list;

    int result_count = 0;

    double d1 = 0.123;
    double alpha2 = -M_PI / 2;
    double a3 = 0.28503;
    double d4 = 0.25075;
    double a4 = -0.02198;
    double alpha5 = -M_PI / 2;
    double d6 = 0.091;
    double alpha6 = M_PI / 2;

    // Inverse of base transform matrix
    Eigen::Matrix4d base_transform_inv = Eigen::Matrix4d::Identity();
    base_transform_inv.block<3, 3>(0, 0) = base_transform_.block<3, 3>(0, 0).transpose();
    base_transform_inv.block<3, 1>(0, 3) = -base_transform_inv.block<3, 3>(0, 0) * base_transform_.block<3, 1>(0, 3);

    // Pose in arm base frame
    Eigen::Matrix4d pose_base = base_transform_inv * pose;

    // Wrist position in arm base frame
    Eigen::Vector3d pw0 = pose_base.block<3, 1>(0, 3) - d6 * pose_base.block<3, 1>(0, 2);

    Eigen::Vector2d theta1;
    Eigen::Vector2d theta2;
    Eigen::Vector2d theta3;

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
        Eigen::Matrix4d T01;
        T01 << cos(theta1(i)), -sin(theta1(i)), 0, 0,
               sin(theta1(i)), cos(theta1(i)), 0, 0,
               0, 0, 1, d1,
               0, 0, 0, 1;
        Eigen::Matrix4d T01_inv;
        T01_inv.block<3, 3>(0, 0) = T01.block<3, 3>(0, 0).transpose();
        T01_inv.block<3, 1>(0, 3) = -T01_inv.block<3, 3>(0, 0) * T01.block<3, 1>(0, 3);
        T01_inv.block<1, 4>(3, 0) << 0, 0, 0, 1;

        // Wrist pose transformation matrix in link 1 frame
        // Eigen::Matrix4d pose_wrist_1 = T01_inv * pose_wrist_base;
        Eigen::Vector4d pos_wrist_1 = T01_inv * Eigen::Vector4d(pw0(0),pw0(1),pw0(2),1);

        // X, Y, Z position of wrist in link 1 frame
        double xw1 = pos_wrist_1(0);
        double zw1 = pos_wrist_1(2);

        double temp1 = (xw1 * xw1 + zw1 * zw1 - d4 * d4 - a4 * a4 + a3 * a3) / (2 * zw1);
        double temp2 = xw1 / zw1;

        double delta = temp1 * temp1 * temp2 * temp2 - (1 + temp2 * temp2) * (temp1 * temp1 - a3 * a3);
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

        double x31_1 = (temp1 * temp2 + sqrt(delta)) / (1 + temp2 * temp2);
        double x31_2 = (temp1 * temp2 - sqrt(delta)) / (1 + temp2 * temp2);

        double z31_1 = temp1 - temp2 * x31_1;
        double z31_2 = temp1 - temp2 * x31_2;

        theta2(0) = -atan2(z31_1, x31_1);
        theta2(1) = -atan2(z31_2, x31_2);

        double temp3 = atan2(d4, -a4);
        double temp4 = acos(std::max(-1.0, std::min(1.0, (a4 * a4 + d4 * d4 + x31_1 * x31_1 + z31_1 * z31_1 - xw1 * xw1 - zw1 * zw1) /
                                        (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_1 * x31_1 + z31_1 * z31_1)))));
        double temp5 = acos(std::max(-1.0, std::min(1.0, (a4 * a4 + d4 * d4 + x31_2 * x31_2 + z31_2 * z31_2 - xw1 * xw1 - zw1 * zw1) /
                                        (2 * sqrt(a4 * a4 + d4 * d4) * sqrt(x31_2 * x31_2 + z31_2 * z31_2)))));

        double theta3_1 = -temp3 - temp4;
        double theta3_2 = -temp3 - temp5;
        double theta3_3 = temp4 - temp3;
        double theta3_4 = temp5 - temp3;

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
            Eigen::Matrix3d R1, R2, R3;
            R1 = Eigen::AngleAxisd(theta1(i), Eigen::Vector3d::UnitZ()).toRotationMatrix();
            R2 = Eigen::AngleAxisd(theta2(j), Eigen::Vector3d::UnitY()).toRotationMatrix();
            R3 = Eigen::AngleAxisd(theta3(j), Eigen::Vector3d::UnitY()).toRotationMatrix();

            Eigen::Matrix3d R = R3.transpose() * R2.transpose() * R1.transpose() * pose_base.block<3, 3>(0, 0);

            Eigen::Vector2d theta4;
            Eigen::Vector2d theta5;
            Eigen::Vector2d theta6;

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
    double min_movement = std::numeric_limits<double>::max();

    for (int i = 0; i < result_count; ++i)
    {
        int greater = 1;
        for ( int j=0 ; j<num_dof_ ; j++ )
        {
            if ( joint_pos_list(j,i) < joint_pos_limit_low_[j] )
            {
                greater = 0;
            }
        }
        int less = 1;
        for ( int j=0 ; j<num_dof_ ; j++ )
        {
            if ( joint_pos_list(j,i) > joint_pos_limit_high_[j] )
            {
                less = 0;
            }
        }
        if (less && greater)
        {
            double movement = (joint_pos_list.col(i) - ref_conf).squaredNorm();
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

ErrorCode ArmModel::getDampedLeastSquareInverseKinematics(
    Eigen::Vector<double,ArmModel::num_dof_>& joint_pos, 
    const double lambda,
    const Eigen::Vector<double,6> tolerance,
    const size_t max_iteration,
    const Eigen::Matrix4d &pose,
    const Eigen::Vector<double,6>& ref_conf) const
{
    auto getPoseDiff = [](const Eigen::Matrix4d& target_pose, const Eigen::Matrix4d& current_pose)
    {
        Eigen::Vector<double,6> pose_diff = Eigen::Vector<double,6>::Zero();
        pose_diff.block<3,1>(0,0) = target_pose.block<3,1>(0,3) - current_pose.block<3,1>(0,3);
        Eigen::Quaterniond target_quat(target_pose.block<3,3>(0,0));
        Eigen::Quaterniond current_quat(current_pose.block<3,3>(0,0));
        pose_diff.block<3,1>(3,0) = (target_quat * current_quat.conjugate()).vec();
        return pose_diff;
    };
    auto getDampedLeastSquares = [](const Eigen::Matrix<double,6,num_dof_>& J, const Eigen::Vector<double,6>& dx, double lambda = 0.1)
    {
        Eigen::Matrix<double,num_dof_,num_dof_> I = Eigen::Matrix<double,num_dof_,num_dof_>::Identity();
        Eigen::Matrix<double,num_dof_,num_dof_> JJT_plus_lambdaI = J * J.transpose() + lambda * lambda * I;
        Eigen::Matrix<double,num_dof_,num_dof_> dls_pinv = J.transpose() * JJT_plus_lambdaI.completeOrthogonalDecomposition().pseudoInverse();
        return dls_pinv * dx;
    };

    ErrorCode err = OK;
    
    Eigen::Vector<double,num_dof_> best_joint_pos = Eigen::Vector<double,num_dof_>::Zero();
    Eigen::Vector<double,num_dof_> joint_pos_diff = Eigen::Vector<double,num_dof_>::Zero();
    Eigen::Vector3d shoulder_joint_pos = Eigen::Vector3d::Zero();

    err = getShoulderJointPos(shoulder_joint_pos, pose, ref_conf.block<3,1>(0,0));

    if ( err == NoResult )
    {
        return err;
    }

    best_joint_pos.block<3,1>(0,0) = shoulder_joint_pos;

    for ( size_t i=0 ; i<max_iteration ; i++ )
    {
        std::array<Eigen::Matrix4d,ArmModel::num_link_> link_transform;
        std::array<Eigen::Matrix4d,ArmModel::num_link_> link_com_transform;
        std::array<Eigen::Matrix<double,6,ArmModel::num_dof_>,ArmModel::num_link_> link_jacobian;
        this->getTransform(link_transform, link_com_transform, best_joint_pos);
        this->getLinkSpaceJacobian(link_jacobian, link_transform);
        Eigen::Vector<double,6> pose_diff = getPoseDiff(pose, link_transform[5]);

        /* Check if the pose difference is within the tolerance (use abs: signed compare
         * would falsely "converge" when any error component is negative, e.g. -0.5 < 0.01) */
        if ( (pose_diff.array().abs() < tolerance.array()).all() )
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
