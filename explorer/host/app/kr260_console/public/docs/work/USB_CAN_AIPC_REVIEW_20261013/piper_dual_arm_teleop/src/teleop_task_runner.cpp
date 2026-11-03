/**
 * @file teleop_task_runner.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Task runner for dual arm teleoperation.
 * @version 0.1
 * @date 2025-06-12
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <termination.h>
#include <teleop_task_runner.h>

const Eigen::Vector3d TeleopTaskRunner::head_position_ = Eigen::Vector3d(0.5,0,1.0);
const Eigen::Quaterniond TeleopTaskRunner::left_hand_orientation_offset_ = Eigen::Quaterniond(Eigen::AngleAxisd(M_PI/2, Eigen::Vector3d::UnitY()));
const Eigen::Quaterniond TeleopTaskRunner::right_hand_orientation_offset_ = Eigen::Quaterniond(Eigen::AngleAxisd(M_PI/2, Eigen::Vector3d::UnitY()));
const Eigen::Matrix4d TeleopTaskRunner::left_arm_base_transform_ = (Eigen::Matrix4d() << 
    0,  0,  1, 0.23805,
   -1,  0,  0, 0.19675,
    0, -1,  0, 0.74065,
    0,  0,  0, 1).finished();
const Eigen::Matrix4d TeleopTaskRunner::right_arm_base_transform_ = (Eigen::Matrix4d() <<
    0, 0, 1, 0.23805,
    1, 0, 0,-0.19675,
    0, 1, 0, 0.74065,
    0, 0, 0, 1).finished();

TeleopTaskRunner::TeleopTaskRunner(std::shared_ptr<ArmInterface> interface, size_t freq_plan, size_t freq_ctrl):
    freq_plan_(freq_plan), freq_ctrl_(freq_ctrl),
    interface_(interface),
    left_hand_target_pos_(Eigen::Vector3d::Zero()),
    left_hand_target_orientation_(Eigen::Quaterniond::Identity()),
    left_hand_target_pose_(Eigen::Matrix4d::Identity()),
    left_hand_actual_orientation_(Eigen::Quaterniond::Identity()),
    left_gripper_control_(0),
    right_hand_target_pos_(Eigen::Vector3d::Zero()),
    right_hand_target_orientation_(Eigen::Quaterniond::Identity()),
    right_hand_target_pose_(Eigen::Matrix4d::Identity()),
    right_hand_actual_orientation_(Eigen::Quaterniond::Identity()),
    right_gripper_control_(0),
    left_arm_joint_state_history_(32),
    right_arm_joint_state_history_(32),
    left_arm_trajectory_buffer_(),
    right_arm_trajectory_buffer_(),
    channel_(this->io_context_, "/workspace/tmp/arm_solve", "/workspace/tmp/arm_station"),
    send_mq_(RingBuffer<nav_state_msg>{32}),
    recv_mq_(RingBuffer<whole_body_msg>{32})
{
}

void TeleopTaskRunner::initialize()
{
    this->channel_.bind_message_queue("nav_state_sender", ParserType::Sender, this->send_mq_);
    this->channel_.bind_message_queue("whole_body_receiver", ParserType::Receiver, this->recv_mq_);
    while(!this->channel_.enable_sender())
    {
	LOG_INFO("1");
    }
    while(!this->channel_.enable_receiver());

    this->io_context_thread_ = std::thread([&]() { this->io_context_.run(); });

    this->left_arm_model_ = std::make_shared<ArmModel>(left_arm_base_transform_);
    this->right_arm_model_ = std::make_shared<ArmModel>(right_arm_base_transform_);

    this->planner_ = std::make_unique<ArmPlanner>(
        this->left_arm_trajectory_buffer_,
        this->right_arm_trajectory_buffer_,
        this->freq_plan_);

    this->controller_ = std::make_unique<ArmController>(
        this->left_arm_model_,
        this->right_arm_model_,
        this->interface_,
        this->left_arm_trajectory_buffer_,
        this->right_arm_trajectory_buffer_,
        this->freq_ctrl_);

    this->planner_->start();
    this->controller_->start();
}

void TeleopTaskRunner::run()
{
    whole_body_msg msg;

    ErrorCode err;

    std::chrono::steady_clock::time_point report_time = std::chrono::steady_clock::now();

    this->running_ = true;

    while ( this->running_ )
    {
        if ( TerminationHandler::stop_requested.load() )
        {
            return;
        }
        /* If reaches report time, send joint position */
        if ( (std::chrono::steady_clock::now() - report_time) >= std::chrono::milliseconds(20) )
        {
            nav_state_msg nav_msg = {0};
            Eigen::Vector<double,ArmModel::num_dof_> joint_pos;
            joint_pos = this->interface_->getLeftJointPosition();
            for ( int i=0 ; i<ArmModel::num_dof_ ; i++)
            {
                nav_msg.left_joints[i] = joint_pos(i);
            }
            joint_pos = this->interface_->getRightJointPosition();
            for ( int i=0 ; i<ArmModel::num_dof_ ; i++)
            {
                nav_msg.right_joints[i] = joint_pos(i);
            }
            this->send_mq_.enqueue(nav_msg);
            report_time += std::chrono::milliseconds(20);
        }
        if ( this->recv_mq_.empty() )
        {
            continue;
        }
        this->recv_mq_.dequeue(msg);
        /* Check for system control enable signal */
        if ( !(msg.mask&(1<<15)) )
        {
            continue;
        }
        /* Check for left arm control enable signal */
        if ( msg.mask&(1<<13) )
        {
            /* Assign position to Eigen::Vector3d */
            this->left_hand_target_pos_(0) = msg.left_hand_pos[0];
            this->left_hand_target_pos_(1) = msg.left_hand_pos[1];
            this->left_hand_target_pos_(2) = msg.left_hand_pos[2];
            /* Assign quaternion to Eigen::Quaterniond */
            this->left_hand_target_orientation_.x() = msg.left_hand_quat[0];
            this->left_hand_target_orientation_.y() = msg.left_hand_quat[1];
            this->left_hand_target_orientation_.z() = msg.left_hand_quat[2];
            this->left_hand_target_orientation_.w() = msg.left_hand_quat[3];

            LOG_DEBUG("Original left hand target position:x={:.4f},y={:.4f},z={:.4f}.Orientation:x={:.4f},y={:.4f},z={:.4f},w={:.4f}.",
                this->left_hand_target_pos_(0), this->left_hand_target_pos_(1), this->left_hand_target_pos_(2),
                this->left_hand_target_orientation_.x(), this->left_hand_target_orientation_.y(),
                this->left_hand_target_orientation_.z(), this->left_hand_target_orientation_.w());

            this->scaleLeftHandPose(this->left_hand_target_pos_, this->left_hand_target_orientation_);

            /* Set motion capture object's position and orientation in simulator. */
            this->interface_->setLeftMocapPose(this->left_hand_target_pos_, this->left_hand_target_orientation_);

            /* Construct transformation matrix from orientation and position */
            this->left_hand_target_pose_.block<3,3>(0,0) = this->left_hand_target_orientation_.toRotationMatrix();
            this->left_hand_target_pose_.block<3,1>(0,3) = this->left_hand_target_pos_;
            this->left_hand_target_pose_(3,3) = 1;

            LOG_DEBUG("Scaled left hand target position:x={:.4f},y={:.4f},z={:.4f}.Orientation:x={:.4f},y={:.4f},z={:.4f},w={:.4f}.",
                this->left_hand_target_pos_(0), this->left_hand_target_pos_(1), this->left_hand_target_pos_(2),
                this->left_hand_target_orientation_.x(), this->left_hand_target_orientation_.y(),
                this->left_hand_target_orientation_.z(), this->left_hand_target_orientation_.w());

            this->interface_->setLeftGripperControl(0.07 - 0.07 * msg.left_grip, 0);
            this->interface_->setRightGripperControl(0.07 - 0.07 * msg.right_grip, 0);
            /* Get least damped inverse kinematics */
            err = this->left_arm_model_->getDampedLeastSquareInverseKinematics(this->left_arm_target_joint_pos_,
                0.1, Eigen::Vector<double,6>(0.05,0.05,0.05,0.1,0.1,0.1), 200, this->left_hand_target_pose_, this->interface_->getLeftJointPosition());
            if ( err == NoResult )
            {
                LOG_WARN("No left hand inverse kinematics result.");
                continue;
            }

            if ( !this->checkInvalidJointPosition(this->left_arm_target_joint_pos_) )
            {
                continue;
            }

            LOG_DEBUG("Left arm IK solution:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                this->left_arm_target_joint_pos_(0),this->left_arm_target_joint_pos_(1),this->left_arm_target_joint_pos_(2),
                this->left_arm_target_joint_pos_(3),this->left_arm_target_joint_pos_(4),this->left_arm_target_joint_pos_(5));
            this->planner_->setLeftArmTargetJointPosition(this->left_arm_target_joint_pos_);
            this->left_arm_joint_state_history_.push(this->left_arm_target_joint_pos_);
        }
        /* Check for right arm control enable signal */
        if ( msg.mask&(1<<12) )
        {
            /* Assign position to Eigen::Vector3d */
            this->right_hand_target_pos_(0) = msg.right_hand_pos[0];
            this->right_hand_target_pos_(1) = msg.right_hand_pos[1];
            this->right_hand_target_pos_(2) = msg.right_hand_pos[2];
            /* Assign quaternion to Eigen::Quaterniond */
            this->right_hand_target_orientation_.x() = msg.right_hand_quat[0];
            this->right_hand_target_orientation_.y() = msg.right_hand_quat[1];
            this->right_hand_target_orientation_.z() = msg.right_hand_quat[2];
            this->right_hand_target_orientation_.w() = msg.right_hand_quat[3];

            LOG_DEBUG("Original right hand target position:x={:.4f},y={:.4f},z={:.4f}.Orientation:x={:.4f},y={:.4f},z={:.4f},w={:.4f}.",
                this->right_hand_target_pos_(0), this->right_hand_target_pos_(1), this->right_hand_target_pos_(2),
                this->right_hand_target_orientation_.x(), this->right_hand_target_orientation_.y(),
                this->right_hand_target_orientation_.z(), this->right_hand_target_orientation_.w());

            this->scaleRightHandPose(this->right_hand_target_pos_, this->right_hand_target_orientation_);

            /* Set motion capture object's position and orientation in simulator. */
            this->interface_->setRightMocapPose(this->right_hand_target_pos_, this->right_hand_target_orientation_);

            /* Construct transformation matrix from orientation and position */
            this->right_hand_target_pose_.block<3,3>(0,0) = this->right_hand_target_orientation_.toRotationMatrix();
            this->right_hand_target_pose_.block<3,1>(0,3) = this->right_hand_target_pos_;
            this->right_hand_target_pose_(3,3) = 1;

            LOG_DEBUG("Scaled right hand target position:x={:.4f},y={:.4f},z={:.4f}.Orientation:x={:.4f},y={:.4f},z={:.4f},w={:.4f}.",
                this->right_hand_target_pos_(0), this->right_hand_target_pos_(1), this->right_hand_target_pos_(2),
                this->right_hand_target_orientation_.x(), this->right_hand_target_orientation_.y(),
                this->right_hand_target_orientation_.z(), this->right_hand_target_orientation_.w());

            /* Get least damped inverse kinematics */
            err = this->right_arm_model_->getDampedLeastSquareInverseKinematics(this->right_arm_target_joint_pos_,
                0.1, Eigen::Vector<double,6>(0.05,0.05,0.05,0.1,0.1,0.1), 200, this->right_hand_target_pose_, this->interface_->getRightJointPosition());
            if ( err == NoResult )
            {
                LOG_WARN("No right hand inverse kinematics result.");
                continue;
            }

            if ( !this->checkInvalidJointPosition(this->right_arm_target_joint_pos_) )
            {
                continue;
            }

            LOG_DEBUG("Right arm IK solution:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                this->right_arm_target_joint_pos_(0),this->right_arm_target_joint_pos_(1),this->right_arm_target_joint_pos_(2),
                this->right_arm_target_joint_pos_(3),this->right_arm_target_joint_pos_(4),this->right_arm_target_joint_pos_(5));
            this->planner_->setRightArmTargetJointPosition(this->right_arm_target_joint_pos_);
            this->right_arm_joint_state_history_.push(this->right_arm_target_joint_pos_);
        }
    }
}

void TeleopTaskRunner::stop()
{
    this->running_ = false;
    this->io_context_.stop();
    this->io_context_thread_.join();
    this->planner_->stop();
    this->controller_->stop();
}

void TeleopTaskRunner::setHomeConfiguration()
{
    
}

void TeleopTaskRunner::scaleLeftHandPose(Eigen::Vector3d& position, Eigen::Quaterniond& orientation)
{
    /* Scale the end effector position. */
    position *= 1.1;
    /* Add position offset because VR remote controller position is based on headset,
     * so the base position should be converted to the arm model base. */
    position += this->head_position_;
    orientation = orientation * this->left_hand_orientation_offset_;
}

void TeleopTaskRunner::scaleRightHandPose(Eigen::Vector3d& position, Eigen::Quaterniond& orientation)
{
    /* Scale the end effector position. */
    position *= 1.1;
    /* Add position offset because VR remote controller position is based on headset,
     * so the base position should be converted to the arm model base. */
    position += this->head_position_;
    orientation = orientation * this->right_hand_orientation_offset_;
}

bool TeleopTaskRunner::checkInvalidJointPosition(const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos)
{
    // for ( auto it=this->left_arm_joint_state_history_.crbegin() ; it!=this->left_arm_joint_state_history_.crend() ; ++it )
    // {
        
    // }
    return true;
}
