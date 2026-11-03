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

/* AI PC 通信参数（按 2026-10-13 实机联调记录设置）：
 * KR260 eth1 (192.168.137.224) 绑定 54321/UDP 接收 whole_body_msg（78 字节）；
 * nav_state_msg 回传至 AI PC eno1 (192.168.137.2) 的 54322 端口。
 * 注意：54322 为暂定回传端口，需与 AI PC 侧接收程序确认后统一。 */
static constexpr const char* AI_PC_IP = "192.168.137.2";
static constexpr int AI_PC_ARM_PORT = 54322;
static constexpr int KR260_LOCAL_PORT = 54321;

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
    channel_(this->io_context_, "0.0.0.0", KR260_LOCAL_PORT, AI_PC_IP, AI_PC_ARM_PORT),
    send_mq_(RingBuffer<nav_state_msg>{32}),
    recv_mq_(RingBuffer<whole_body_msg>{32}),
    recv2_mq_(RingBuffer<teleop_setpoint_msg>{32})
{
}

void TeleopTaskRunner::initialize()
{
    this->channel_.bind_message_queue("nav_state_sender", ParserType::Sender, this->send_mq_);
    this->channel_.bind_message_queue("whole_body_receiver", ParserType::Receiver, this->recv_mq_);
    this->channel_.bind_message_queue("teleop_setpoint_receiver", ParserType::Receiver, this->recv2_mq_);
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

    /* C25：构建与运行参数可追溯。以前只知道用了哪个二进制，不知道它何时构建、
     * 实际限速多少（本地源码 0.08 / 现网二进制 0.4 曾长期不一致）。 */
    LOG_INFO("deploy runner init | build {} {} | kMaxJointVel={:.3f} rad/s",
             __DATE__, __TIME__, ArmPlanner::maxJointVelocity());
    this->planner_->setLeftArmTargetJointPosition(this->interface_->getLeftJointPosition());
    this->planner_->setRightArmTargetJointPosition(this->interface_->getRightJointPosition());

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
        /* v2 teleop_setpoint：逐条处理到空（语义按规范第 7 节，替代旧 whole_body 路径） */
        while ( !this->recv2_mq_.empty() )
        {
            teleop_setpoint_msg sp;
            this->recv2_mq_.dequeue(sp);
            this->processTeleopSetpoint(sp);
        }
        /* 规范 7.3 watchdog：100ms 无新有效命令 → 目标保持（planner 原地插值即受控停止），
         * 告警降级为节流日志，避免刷屏 */
        if ( this->setpoint_seen_ )
        {
            auto age = std::chrono::steady_clock::now() - this->last_setpoint_time_;
            if ( age > std::chrono::milliseconds(kSetpointWatchdogMs) )
            {
                /* 沉默超 1s 视为发送方已重启：重置 seq 允许重新同步（规范 sync 事务语义）。
                 * 否则发送方重启后 seq 回退会被去重逻辑静默全丢（2026-10-19 联调踩坑） */
                if ( age > std::chrono::milliseconds(1000) )
                {
                    this->last_setpoint_seq_ = 0;
                }
                /* 2026-10-23 回退（现场决定）：此处原为 C01 的「断流即冻结」。
                 * 实测 KR260 过载（4 核 load≈12），帧流每 1~3 秒就断一次，
                 * 于是每次断流都被冻结成一次急停 —— 手臂"一卡一卡"，比原问题更糟。
                 * 现恢复原行为：看门狗只记日志，planner 继续朝最后目标插值。
                 * watchdog_hold_ 成员保留（别处仍写），但不再改写任何目标。 */
                this->watchdog_hold_ = true;
                /* 节流告警：每 2s 最多一条 */
                static std::chrono::steady_clock::time_point last_warn{};
                auto now = std::chrono::steady_clock::now();
                if ( now - last_warn > std::chrono::milliseconds(2000) )
                {
                    last_warn = now;
                    LOG_WARN("teleop_setpoint watchdog: no new command for {}ms, holding last target.",
                        std::chrono::duration_cast<std::chrono::milliseconds>(age).count());
                }
            }
        }
        if ( this->recv_mq_.empty() )
        {
            /* 无命令时让出 CPU：原实现是 continue 空转，主线程烧满一核
             * （2026-10-20 排查：load 8+/4核）。1ms 粒度对 20ms nav_state
             * 节拍与 100ms 看门狗均无影响。 */
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
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
            /* Get least damped inverse kinematics */
            err = this->left_arm_model_->getDampedLeastSquareInverseKinematics(this->left_arm_target_joint_pos_,
                0.1, Eigen::Vector<double,6>(0.002,0.002,0.002,0.01,0.01,0.01), 400, this->left_hand_target_pose_, this->interface_->getLeftJointPosition());
            if ( err == NoResult )
            {
                LOG_WARN("No left hand inverse kinematics result.");
                continue;
            }

            if ( !this->checkInvalidJointPosition(this->left_arm_target_joint_pos_) )
            {
                continue;
            }

            /* IK 残差守卫：DLS-IK 对不可达目标也会返回 OK（最多迭代后直接退出），
             * 必须 FK 验算，防止不可达/跳支解直接驱动机械臂（2026-10-15 事故修复） */
            double left_pos_err = 0, left_ori_err = 0;
            if ( !this->checkIkResidual(this->left_arm_model_, this->left_hand_target_pose_,
                this->left_arm_target_joint_pos_, left_pos_err, left_ori_err) )
            {
                static int left_reject_cnt = 0;
                if ( ++left_reject_cnt % 20 == 1 )
                {
                    LOG_WARN("Left arm IK residual too large, target rejected: pos_err={:.3f}m, ori_err={:.2f}rad (rejected {} frames)",
                        left_pos_err, left_ori_err, left_reject_cnt);
                }
                continue;
            }

            LOG_DEBUG("Left arm IK solution:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                this->left_arm_target_joint_pos_(0),this->left_arm_target_joint_pos_(1),this->left_arm_target_joint_pos_(2),
                this->left_arm_target_joint_pos_(3),this->left_arm_target_joint_pos_(4),this->left_arm_target_joint_pos_(5));
            /* 限速平滑已下沉到规划器（arm_planner 每周期爬行逼近），此处直接下发 */
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

            /* 右夹爪指令放到右臂分支内（2026-10-17 修复：原先误写在左臂分支，
             * mask 仅含右臂使能位时夹爪永远不响应）。放在 IK 之前，
             * 即使当帧 IK 目标被拒，夹爪动作也不受影响。 */
            this->interface_->setRightGripperControl(0.07 - 0.07 * msg.right_grip, 0);

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
                0.1, Eigen::Vector<double,6>(0.002,0.002,0.002,0.01,0.01,0.01), 400, this->right_hand_target_pose_, this->interface_->getRightJointPosition());
            if ( err == NoResult )
            {
                LOG_WARN("No right hand inverse kinematics result.");
                continue;
            }

            if ( !this->checkInvalidJointPosition(this->right_arm_target_joint_pos_) )
            {
                continue;
            }

            /* IK 残差守卫：同左臂（2026-10-15 事故修复） */
            double right_pos_err = 0, right_ori_err = 0;
            if ( !this->checkIkResidual(this->right_arm_model_, this->right_hand_target_pose_,
                this->right_arm_target_joint_pos_, right_pos_err, right_ori_err) )
            {
                static int right_reject_cnt = 0;
                if ( ++right_reject_cnt % 20 == 1 )
                {
                    LOG_WARN("Right arm IK residual too large, target rejected: pos_err={:.3f}m, ori_err={:.2f}rad (rejected {} frames)",
                        right_pos_err, right_ori_err, right_reject_cnt);
                }
                continue;
            }

            LOG_DEBUG("Right arm IK solution:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                this->right_arm_target_joint_pos_(0),this->right_arm_target_joint_pos_(1),this->right_arm_target_joint_pos_(2),
                this->right_arm_target_joint_pos_(3),this->right_arm_target_joint_pos_(4),this->right_arm_target_joint_pos_(5));
            /* 限速平滑已下沉到规划器（arm_planner 每周期爬行逼近），此处直接下发 */
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

    /* 优雅退出：目标与平滑值同步冻结在最近规划位置，保留 300ms 指令流。
     * 不再改设为滞后的实际反馈角，否则平滑器会在退出前反向插值，表现为停止时回退。
     * 300ms 保护用于避免指令流突然中断触发驱动器 0xa4 故障锁存，不能删除。 */
    LOG_INFO("Graceful shutdown: freezing target and smoother at last commanded positions for 300ms...");
    this->planner_->freezeDualArmAtSmoothPosition();
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    this->planner_->stop();
    this->controller_->stop();
    LOG_INFO("Planner and controller stopped gracefully.");
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

bool TeleopTaskRunner::checkIkResidual(const std::shared_ptr<ArmModel>& model,
    const Eigen::Matrix4d& target_pose,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    double& pos_err, double& ori_err) const
{
    std::array<Eigen::Matrix4d,ArmModel::num_link_> link_transform;
    std::array<Eigen::Matrix4d,ArmModel::num_link_> link_com_transform;
    model->getTransform(link_transform, link_com_transform, joint_pos);
    /* 与 DLS-IK 内部误差计算保持同一索引（link_transform[5]，见 arm_model.cpp） */
    const Eigen::Matrix4d& actual = link_transform[5];
    pos_err = (target_pose.block<3,1>(0,3) - actual.block<3,1>(0,3)).norm();
    Eigen::Quaterniond q_target(target_pose.block<3,3>(0,0));
    Eigen::Quaterniond q_actual(actual.block<3,3>(0,0));
    Eigen::Quaterniond q_diff = q_target * q_actual.conjugate();
    double vec_norm = q_diff.vec().norm();
    ori_err = 2.0 * std::asin(vec_norm > 1.0 ? 1.0 : vec_norm);
    return ( pos_err < kIkPosTol ) && ( ori_err < kIkOriTol );
}

/* ==================== v2 teleop_setpoint（规范 v2.0 语义子集） ====================
 * 与旧 whole_body 路径的差异：
 * 1. 位姿目标已是「deploy 世界系」终态——缩放/偏置/标定由 AIPC 按规范第 6 节
 *    完成且只应用一次，这里不再调 scaleXXXHandPose；
 * 2. 支持 mode=2 关节位置直达（绕过 IK，仍过限速规划器与限位钳制）；
 * 3. 夹爪为归一化开口 [0,1]（1=全开），替换旧扳机语义 0.07-0.07*grip；
 * 4. seq 递增去重、reference_revision 校验（联调前仅告警）、100ms watchdog（run 循环内）。
 * 关节目标约定：deploy 内部符号约定（J1 已取反，与网页控制台一致），单位 rad。
 */
void TeleopTaskRunner::processTeleopSetpoint(const teleop_setpoint_msg& msg)
{
    /* 总使能 */
    if ( !(msg.enable_mask & 0x1) )
    {
        return;
    }
    this->watchdog_hold_ = false;      /* C01：收到新命令，解除冻结态 */
    /* 序号去重（规范 7.2：seq<=last_seen 丢弃） */
    if ( msg.seq <= this->last_setpoint_seq_ )
    {
        return;
    }
    this->last_setpoint_seq_ = msg.seq;
    this->last_setpoint_time_ = std::chrono::steady_clock::now();
    this->setpoint_seen_ = true;

    /* 标定版本校验：过渡期只告警不拒绝 */
    if ( msg.reference_revision != kExpectedRefRevision )
    {
        static uint32_t last_warned_rev = 0xFFFFFFFF;
        if ( msg.reference_revision != last_warned_rev )
        {
            last_warned_rev = msg.reference_revision;
            LOG_WARN("teleop_setpoint reference_revision={} != local {}, accepting anyway (pre-calibration).",
                msg.reference_revision, kExpectedRefRevision);
        }
    }

    struct Side {
        uint8_t mode;
        uint32_t enable_bit, gripper_bit;
        const teleop_setpoint_msg::vec3& pos;
        const teleop_setpoint_msg::quat& quat;
        const teleop_setpoint_msg::joints& joints;
        float gripper;
        std::shared_ptr<ArmModel>& model;
        Eigen::Vector<double,ArmModel::num_dof_>& target_joint;
        Eigen::Vector<double,ArmModel::num_dof_> (ArmInterface::*getJoints)();   // C14：返回值类型（一致快照）
        void (ArmInterface::*setGripper)(const double&, const double&);
        void (ArmInterface::*setMocap)(const Eigen::Vector3d&, const Eigen::Quaterniond&);
        void (ArmPlanner::*setTarget)(const Eigen::Vector<double,ArmModel::num_dof_>&);
        void (ArmPlanner::*freezeAtSmooth)();
        const char* name;
    };
    Side sides[2] = {
        { msg.left_mode, 1u<<2, 1u<<4, msg.left_target_pos, msg.left_target_quat, msg.left_joint_target, msg.left_gripper,
          this->left_arm_model_, this->left_arm_target_joint_pos_,
          &ArmInterface::getLeftJointPosition, &ArmInterface::setLeftGripperControl,
          &ArmInterface::setLeftMocapPose, &ArmPlanner::setLeftArmTargetJointPosition,
          &ArmPlanner::freezeLeftArmAtSmoothPosition, "left" },
        { msg.right_mode, 1u<<3, 1u<<5, msg.right_target_pos, msg.right_target_quat, msg.right_joint_target, msg.right_gripper,
          this->right_arm_model_, this->right_arm_target_joint_pos_,
          &ArmInterface::getRightJointPosition, &ArmInterface::setRightGripperControl,
          &ArmInterface::setRightMocapPose, &ArmPlanner::setRightArmTargetJointPosition,
          &ArmPlanner::freezeRightArmAtSmoothPosition, "right" },
    };

    for ( auto& s : sides )
    {
        /* 夹爪独立使能位：归一化开口 [0,1] → 开口米数（0.07m 全行程）。
         * 实测夹持力偏弱：闭合限矩由 0.16 提高 1.2 倍至 0.192 N·m；张开及半开不限矩。 */
        if ( msg.enable_mask & s.gripper_bit )
        {
            float v = std::max(0.0f, std::min(1.0f, s.gripper));
            const double torque = (v <= 0.01f) ? 0.192 : 0.0;
            (this->interface_.get()->*s.setGripper)(0.07 * v, torque);
        }
        if ( !(msg.enable_mask & s.enable_bit) )
        {
            /* C01：撤使能 = 该臂停止追击。原来直接 continue，planner 会继续朝旧目标插值
             * （本固件即使 DISABLED 仍执行位置指令），等于"停了指令却没停车"。 */
            (this->planner_.get()->*s.freezeAtSmooth)();
            continue;
        }
        if ( s.mode == 0 )   /* 保持：C01 冻结在当前位置，不再逼近旧目标 */
        {
            (this->planner_.get()->*s.freezeAtSmooth)();
            continue;
        }
        if ( s.mode > 2 )    /* C24：未定义模式。原来会落进 mode==1 分支当位姿用，
                              * 协议升级或字段错位时会按错误语义驱动机械臂。 */
        {
            static std::chrono::steady_clock::time_point last_bad_mode{};
            auto now_bad = std::chrono::steady_clock::now();
            if ( now_bad - last_bad_mode > std::chrono::milliseconds(2000) )
            {
                last_bad_mode = now_bad;
                LOG_WARN("v2 setpoint: {} arm mode={} 未定义（合法 0/1/2），按保持处理",
                    s.name, static_cast<int>(s.mode));
            }
            (this->planner_.get()->*s.freezeAtSmooth)();
            continue;
        }
        if ( s.mode == 2 )   /* 关节位置直达（绕过 IK，过规划器限速） */
        {
            // J1 使用松灵官方机械范围 ±150°；J2～J6 保留原安全余量。
            static const double LO[6] = {-2.618, 0.05, -2.917, -1.695, -1.17, -2.0444};
            static const double HI[6] = { 2.618, 3.092, -0.05,  1.695,  1.17,  2.0444};
            for ( int i=0 ; i<ArmModel::num_dof_ ; i++ )
            {
                double v = static_cast<double>(s.joints[i]);
                /* J1 取反：发送方（AIPC/查看器）用物理约定角度，deploy 内部
                 * 符号相反（2026-10-19 定稿；2026-10-20 曾因源码覆盖丢失，勿删） */
                if ( i == 0 ) v = -v;
                double c = std::max(LO[i], std::min(HI[i], v));
                /* C11：执行端限位比发送端更紧时，原来的钳制是静默的。留痕（节流）。 */
                if ( std::abs(c - v) > 1e-9 )
                {
                    static std::chrono::steady_clock::time_point last_clip{};
                    auto now_clip = std::chrono::steady_clock::now();
                    if ( now_clip - last_clip > std::chrono::milliseconds(2000) )
                    {
                        last_clip = now_clip;
                        LOG_WARN("mode=2 {} arm J{} clipped: sent={:.4f} accepted={:.4f} (limit [{:.3f},{:.3f}])",
                            s.name, i + 1, v, c, LO[i], HI[i]);
                    }
                }
                s.target_joint(i) = c;
            }
            (this->planner_.get()->*s.setTarget)(s.target_joint);
            continue;
        }
        /* mode==1：末端位姿（deploy 世界系，已含 AIPC 标定） */
        Eigen::Vector3d pos(s.pos[0], s.pos[1], s.pos[2]);
        Eigen::Quaterniond quat(s.quat[3], s.quat[0], s.quat[1], s.quat[2]);
        quat.normalize();
        (this->interface_.get()->*s.setMocap)(pos, quat);

        Eigen::Matrix4d target_pose = Eigen::Matrix4d::Identity();
        target_pose.block<3,3>(0,0) = quat.toRotationMatrix();
        target_pose.block<3,1>(0,3) = pos;

        ErrorCode err = s.model->getDampedLeastSquareInverseKinematics(s.target_joint,
            0.1, Eigen::Vector<double,6>(0.002,0.002,0.002,0.01,0.01,0.01), 400,
            target_pose, (this->interface_.get()->*s.getJoints)());
        if ( err == NoResult )
        {
            LOG_WARN("v2 setpoint: no {} arm IK result.", s.name);
            continue;
        }
        double pos_err = 0, ori_err = 0;
        if ( !this->checkIkResidual(s.model, target_pose, s.target_joint, pos_err, ori_err) )
        {
            static int reject_cnt[2] = {0, 0};
            int idx = (s.name[0] == 'l') ? 0 : 1;
            if ( ++reject_cnt[idx] % 20 == 1 )
            {
                LOG_WARN("v2 setpoint: {} arm IK residual too large, rejected: pos_err={:.3f}m, ori_err={:.2f}rad ({} frames)",
                    s.name, pos_err, ori_err, reject_cnt[idx]);
            }
            continue;
        }
        (this->planner_.get()->*s.setTarget)(s.target_joint);
    }
}
