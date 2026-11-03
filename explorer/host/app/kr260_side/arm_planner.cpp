/**
 * @file arm_planner.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm trajectory planner.
 * @version 0.1
 * @date 2025-06-12
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <log.hpp>
#include <arm_planner.h>

ArmPlanner::ArmPlanner(
    TrajectoryBuffer<num_plan_waypoint_>& left_arm_trajectory_buffer,
    TrajectoryBuffer<num_plan_waypoint_>& right_arm_trajectory_buffer,
    size_t freq_plan):
    dt_plan_(1.0/static_cast<double>(freq_plan)),
    left_arm_trajectory_buffer_(left_arm_trajectory_buffer),
    right_arm_trajectory_buffer_(right_arm_trajectory_buffer),
    left_arm_target_joint_pos_(M_PI/2, 0.1, 0, 0, 0, 0),
    right_arm_target_joint_pos_(-M_PI/2, 0.1, 0, 0, 0, 0)
{
}

void ArmPlanner::start()
{
    this->running_ = true;
    this->plan_thread_ = std::thread(&ArmPlanner::threadPlan, this);

}

void ArmPlanner::stop()
{
    this->running_ = false;
    if ( this->plan_thread_.joinable() )
    {
        plan_thread_.join();  // Ensure thread finishes before destruction
    }
}

void ArmPlanner::freezeLeftArmAtSmoothPosition()
{
    std::lock_guard<std::mutex> lock(this->left_arm_target_joint_pos_mtx_);
    if ( this->left_arm_smooth_init_ )
    {
        this->left_arm_target_joint_pos_ = this->left_arm_smooth_joint_pos_;
    }
}

void ArmPlanner::freezeRightArmAtSmoothPosition()
{
    std::lock_guard<std::mutex> lock(this->right_arm_target_joint_pos_mtx_);
    if ( this->right_arm_smooth_init_ )
    {
        this->right_arm_target_joint_pos_ = this->right_arm_smooth_joint_pos_;
    }
}

void ArmPlanner::freezeDualArmAtSmoothPosition()
{
    /* 与 threadPlan() 保持左、右相同的加锁顺序，保证目标和平滑值来自同一快照。 */
    std::lock_guard<std::mutex> left_arm_lock(this->left_arm_target_joint_pos_mtx_);
    std::lock_guard<std::mutex> right_arm_lock(this->right_arm_target_joint_pos_mtx_);
    if ( this->left_arm_smooth_init_ )
    {
        this->left_arm_target_joint_pos_ = this->left_arm_smooth_joint_pos_;
    }
    if ( this->right_arm_smooth_init_ )
    {
        this->right_arm_target_joint_pos_ = this->right_arm_smooth_joint_pos_;
    }
}

void ArmPlanner::setLeftArmTargetJointPosition(const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos)
{
    std::lock_guard<std::mutex> lock(this->left_arm_target_joint_pos_mtx_);
    if ( !this->left_arm_smooth_init_ )
    {
        this->left_arm_smooth_joint_pos_ = joint_pos;
        this->left_arm_smooth_init_ = true;
    }
    this->left_arm_target_joint_pos_ = joint_pos;
    this->left_arm_target_set_ = true;
}

void ArmPlanner::setRightArmTargetJointPosition(const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos)
{
    std::lock_guard<std::mutex> lock(this->right_arm_target_joint_pos_mtx_);
    if ( !this->right_arm_smooth_init_ )
    {
        this->right_arm_smooth_joint_pos_ = joint_pos;
        this->right_arm_smooth_init_ = true;
    }
    this->right_arm_target_joint_pos_ = joint_pos;
    this->right_arm_target_set_ = true;
}

void ArmPlanner::planDualArmLinear(
    const std::chrono::steady_clock::time_point& start_timepoint,
    const Eigen::Vector<double,ArmModel::num_dof_>& left_arm_begin,
    const Eigen::Vector<double,ArmModel::num_dof_>& left_arm_end,
    const Eigen::Vector<double,ArmModel::num_dof_>& right_arm_begin,
    const Eigen::Vector<double,ArmModel::num_dof_>& right_arm_end)
{
    /* Use L2-norm to determine the trajectory duration */
    double left_arm_duration = this->dt_plan_ + 3.0 * (left_arm_end - left_arm_begin).squaredNorm();
    double right_arm_duration = this->dt_plan_ + 3.0 * (right_arm_end - right_arm_begin).squaredNorm();
    std::chrono::steady_clock::duration left_arm_waypoint_interval = 
        std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(left_arm_duration/this->num_plan_waypoint_));
    std::chrono::steady_clock::duration right_arm_waypoint_interval = 
        std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(right_arm_duration/this->num_plan_waypoint_));

    /* Create a trajectory waypoint */
    TrajectoryBuffer<this->num_plan_waypoint_>::TrajectoryPoint left_arm_waypoint;
    TrajectoryBuffer<this->num_plan_waypoint_>::TrajectoryPoint right_arm_waypoint;

    /* zero velocities/accelerations/torque here, to be filled by interpolation */
    left_arm_waypoint.state.joint_vel.setZero();
    left_arm_waypoint.state.joint_acc.setZero();
    left_arm_waypoint.state.joint_torq.setZero();
    left_arm_waypoint.timestamp = start_timepoint;
    right_arm_waypoint.state.joint_vel.setZero();
    right_arm_waypoint.state.joint_acc.setZero();
    right_arm_waypoint.state.joint_torq.setZero();
    right_arm_waypoint.timestamp = start_timepoint;

    // fill internal_waypoints_[0..N-1]
    for ( size_t i = 0; i < this->num_plan_waypoint_; ++i )
    {
        double alpha = double(i+1) / (this->num_plan_waypoint_ + 1);

        if ( i>0 )
        {
            left_arm_waypoint.timestamp += left_arm_waypoint_interval;
        }
        /* Compute left arm waypoint. */
        left_arm_waypoint.state.joint_pos = left_arm_begin + alpha * (left_arm_end - left_arm_begin);

        /* Push waypoint to left arm trajectory buffer. */
        this->left_arm_trajectory_buffer_.push(left_arm_waypoint);

        LOG_DEBUG("Left arm linear plan waypoint({:d}):{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",i,
            left_arm_waypoint.state.joint_pos(0),left_arm_waypoint.state.joint_pos(1),left_arm_waypoint.state.joint_pos(2),
            left_arm_waypoint.state.joint_pos(3),left_arm_waypoint.state.joint_pos(4),left_arm_waypoint.state.joint_pos(5));
        
        if ( i>0 )
        {
            right_arm_waypoint.timestamp += right_arm_waypoint_interval;
        }
        /* Compute right arm waypoint. */
        right_arm_waypoint.state.joint_pos = right_arm_begin + alpha * (right_arm_end - right_arm_begin);

        /* Push waypoint to right arm trajectory buffer. */
        this->right_arm_trajectory_buffer_.push(right_arm_waypoint);

        LOG_DEBUG("Right arm linear plan waypoint({:d}):{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",i,
            right_arm_waypoint.state.joint_pos(0),right_arm_waypoint.state.joint_pos(1),right_arm_waypoint.state.joint_pos(2),
            right_arm_waypoint.state.joint_pos(3),right_arm_waypoint.state.joint_pos(4),right_arm_waypoint.state.joint_pos(5));
    }
    /* Commit the pre-computation operation to swap the ping-pong buffer in the trajectory buffer. */
    this->left_arm_trajectory_buffer_.commit();
    this->right_arm_trajectory_buffer_.commit();
}

void ArmPlanner::threadPlan()
{
    auto increase_time_spec = [](struct timespec* time, const struct timespec* increasement)
    {
        time->tv_sec += increasement->tv_sec;
        time->tv_nsec += increasement->tv_nsec;

        if (time->tv_nsec >= 1000000000)
        {
            time->tv_sec++;
            time->tv_nsec -= 1000000000;
        }
    };

    struct timespec wakeup_time = {0,0};
    static struct timespec cycletime = {0, static_cast<long>(this->dt_plan_ * 1e9)};
    clock_gettime(CLOCK_MONOTONIC, &wakeup_time);

    while ( this->running_ )
    {
        increase_time_spec(&wakeup_time, &cycletime);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wakeup_time, NULL);

        std::lock_guard<std::mutex> left_arm_lock(this->left_arm_target_joint_pos_mtx_);
        std::lock_guard<std::mutex> right_arm_lock(this->right_arm_target_joint_pos_mtx_);

        /* 未收到过遥操作目标前不生成任何轨迹——否则会把手臂拉向初始值（全零），
         * 2026-10-14 曾因此撞支架。目标由 setXXXArmTargetJointPosition 首次设置。 */
        if ( !this->left_arm_target_set_ && !this->right_arm_target_set_ )
        {
            continue;
        }

        JointState left_arm_trajectory_begin_state;
        JointState right_arm_trajectory_begin_state;
        std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
        /* 缓冲区为空（尚未插值出有效起点）时，以目标自身作为起点，
         * 生成「原地不动」的静止轨迹，避免使用未初始化的垃圾起点（2026-10-14 事故） */
        if ( this->left_arm_trajectory_buffer_.interpolate(left_arm_trajectory_begin_state, now) != OK )
        {
            left_arm_trajectory_begin_state.joint_pos = this->left_arm_target_joint_pos_;
            left_arm_trajectory_begin_state.joint_vel.setZero();
            left_arm_trajectory_begin_state.joint_acc.setZero();
            left_arm_trajectory_begin_state.joint_torq.setZero();
        }
        if ( this->right_arm_trajectory_buffer_.interpolate(right_arm_trajectory_begin_state, now) != OK )
        {
            right_arm_trajectory_begin_state.joint_pos = this->right_arm_target_joint_pos_;
            right_arm_trajectory_begin_state.joint_vel.setZero();
            right_arm_trajectory_begin_state.joint_acc.setZero();
            right_arm_trajectory_begin_state.joint_torq.setZero();
        }
        /* 平滑目标爬行限速：每周期最多逼近 kMaxJointVel*dt_plan_（2026-10-15） */
        const double max_step = kMaxJointVel * this->dt_plan_;
        for ( int i=0 ; i<ArmModel::num_dof_ ; i++ )
        {
            double dl = this->left_arm_target_joint_pos_(i) - this->left_arm_smooth_joint_pos_(i);
            if ( dl >  max_step ) dl =  max_step;
            if ( dl < -max_step ) dl = -max_step;
            this->left_arm_smooth_joint_pos_(i) += dl;
            double dr = this->right_arm_target_joint_pos_(i) - this->right_arm_smooth_joint_pos_(i);
            if ( dr >  max_step ) dr =  max_step;
            if ( dr < -max_step ) dr = -max_step;
            this->right_arm_smooth_joint_pos_(i) += dr;
        }
        /* Use linear plan to generate internal waypoints */
        this->planDualArmLinear(now,
            left_arm_trajectory_begin_state.joint_pos, this->left_arm_smooth_joint_pos_,
            right_arm_trajectory_begin_state.joint_pos, this->right_arm_smooth_joint_pos_);
    }
}