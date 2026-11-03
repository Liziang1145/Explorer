#ifndef __ARM_MODEL_HPP__
#define __ARM_MODEL_HPP__

#include <array>
#include <memory>
#include <Eigen/Core>
#include <Eigen/Geometry>

enum ErrorCode
{
    OK = 0,
    InvalidArgument,
    Timeout,
    NotInitialized,
    NotImplemented,
    OutOfRange,
    HardwareFailure,
    CommunicationError,
    InvalidData,
    NoResult,
    UnknownError
};

enum JointType
{
    JOINT_REVOLUTE = 1,
    JOINT_PRISMATIC = 2,
    JOINT_FIXED = 3
};

enum ArmType
{
    LEFT_ARM = 1,
    RIGHT_ARM
};


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
    ArmModel(ArmType arm_type):arm_type_(arm_type)
    {
        if ( arm_type == ArmType::LEFT_ARM )
        {
            this->base_transform_ = this->left_arm_base_transform_;
        }
        else
        {
            this->base_transform_ = this->right_arm_base_transform_;
        }
    };
    ~ArmModel() = default;

    bool getPredictedPose(Eigen::Matrix4d& pose_out, const Eigen::Matrix4d& pose_in);
    Eigen::Matrix4d getFeedbackPose(const Eigen::Vector<double,num_dof_>& joint_pos);
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

    void getLinkSpaceJacobian(
        std::array<Eigen::Matrix<double,6,num_dof_>,num_link_>& link_com_jacobian,
        const std::array<Eigen::Matrix4d,num_link_>& link_transform) const;

    ErrorCode getShoulderJointPos(
        Eigen::Vector3d& joint_pos,
        const Eigen::Matrix4d &pose,
        const Eigen::Vector3d& ref_conf) const;

    ErrorCode getDampedLeastSquareInverseKinematics(
        Eigen::Vector<double,num_dof_>& joint_pos,
        const double lambda,
        const Eigen::Vector<double,6> tolerance,
        const size_t max_iteration,
        const Eigen::Matrix4d &pose,
        const Eigen::Vector<double,6>& ref_conf) const;
private:
    ArmType arm_type_;
    Eigen::Matrix4d base_transform_;
    static const Eigen::Vector3d head_position_;
    static const Eigen::Quaterniond left_hand_orientation_offset_;
    static const Eigen::Quaterniond right_hand_orientation_offset_;
    static const Eigen::Matrix4d left_arm_base_transform_;
    static const Eigen::Matrix4d right_arm_base_transform_;
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
const Eigen::Vector3d ArmModel::head_position_ = Eigen::Vector3d(0.5,0,1.0);
const Eigen::Quaterniond ArmModel::left_hand_orientation_offset_ = Eigen::Quaterniond(Eigen::AngleAxisd(M_PI/2, Eigen::Vector3d::UnitY()));
const Eigen::Quaterniond ArmModel::right_hand_orientation_offset_ = Eigen::Quaterniond(Eigen::AngleAxisd(M_PI/2, Eigen::Vector3d::UnitY()));
const Eigen::Matrix4d ArmModel::left_arm_base_transform_ = (Eigen::Matrix4d() << 
    0,  0,  1, 0.23805,
   -1,  0,  0, 0.19675,
    0, -1,  0, 0.74065,
    0,  0,  0, 1).finished();
const Eigen::Matrix4d ArmModel::right_arm_base_transform_ = (Eigen::Matrix4d() <<
    0, 0, 1, 0.23805,
    1, 0, 0,-0.19675,
    0, 1, 0, 0.74065,
    0, 0, 0, 1).finished();

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

bool ArmModel::getPredictedPose(Eigen::Matrix4d& pose_out, const Eigen::Matrix4d& pose_in)
{
    static const Eigen::Vector<double,num_dof_> reference = Eigen::Vector<double,num_dof_>::Zero();
    ErrorCode err = OK;
    Eigen::Vector3d position = pose_in.block<3,1>(0,3);
    Eigen::Quaterniond orientation(pose_in.block<3,3>(0,0));
    Eigen::Vector<double,num_dof_> joint_pos;
    std::array<Eigen::Matrix4d,num_link_> link_transform;
    std::array<Eigen::Matrix4d,num_link_> com_transform;
    position *= 1.1;
    position += this->head_position_;
    if ( this->arm_type_ == ArmType::LEFT_ARM )
    {
        orientation *= this->left_hand_orientation_offset_;
    }
    else
    {
        orientation *= this->right_hand_orientation_offset_;
    }
    Eigen::Matrix4d target_pose = Eigen::Matrix4d::Identity();
    target_pose.block<3,3>(0,0) = orientation.toRotationMatrix();
    target_pose.block<3,1>(0,3) = position;
    err = getDampedLeastSquareInverseKinematics(joint_pos,
        0.1, Eigen::Vector<double,6>(0.05,0.05,0.05,0.1,0.1,0.1), 200, target_pose, reference);
    if ( err == ErrorCode::NoResult )
    {
        return false;
    }
    getTransform(link_transform, com_transform, joint_pos);
    orientation = Eigen::Quaterniond(link_transform[6].block<3,3>(0,0));
    if ( this->arm_type_ == ArmType::LEFT_ARM )
    {
        orientation *= this->left_hand_orientation_offset_.conjugate();
    }
    else
    {
        orientation *= this->right_hand_orientation_offset_.conjugate();
    }
    position = link_transform[6].block<3,1>(0,3);
    position -= this->head_position_;
    pose_out.setIdentity();
    pose_out.block<3,3>(0,0) = orientation.toRotationMatrix();
    pose_out.block<3,1>(0,3) = link_transform[6].block<3,1>(0,3) - this->head_position_;
    return true;
}

Eigen::Matrix4d ArmModel::getFeedbackPose(const Eigen::Vector<double,num_dof_>& joint_pos)
{
    Eigen::Matrix4d pose = Eigen::Matrix4d::Zero();
    std::array<Eigen::Matrix4d,ArmModel::num_link_> link_transform;
    std::array<Eigen::Matrix4d,ArmModel::num_link_> com_transform;
    getTransform(link_transform, com_transform, joint_pos);
    
    Eigen::Quaterniond orientation(link_transform[6].block<3,3>(0,0));
    if ( this->arm_type_ == ArmType::LEFT_ARM )
    {
        orientation *= this->left_hand_orientation_offset_.conjugate();
    }
    else
    {
        orientation *= this->right_hand_orientation_offset_.conjugate();
    }
    pose.block<3,3>(0,0) = orientation.toRotationMatrix();
    pose.block<3,1>(0,3) = link_transform[6].block<3,1>(0,3) - this->head_position_;
    return pose;
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

#endif //__ARM_MODEL_HPP__