/**
 * @file trajectory_buffer.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Trajectory buffer stores the trajectory points and has a series of trajectory management.
 * @version 0.1
 * @date 2025-07-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __TRAJECTORY_BUFFER_HPP__
#define __TRAJECTORY_BUFFER_HPP__
#pragma once
#include <iostream>
#include <vector>
#include <chrono>
#include <log.hpp>
#include <error_codes.h>
#include <joint_state.h>

template <std::size_t Capacity = 10>
class TrajectoryBuffer
{
public:
    using TimePoint = std::chrono::steady_clock::time_point;

    struct TrajectoryPoint
    {
        TimePoint timestamp;
        JointState state;
    };

    struct StaticMemoryBuffer
    {
        std::array<TrajectoryPoint, Capacity> buffer;
        std::size_t size = 0;
        std::size_t head = 0;
    };

    TrajectoryBuffer():
        write_buffer_(&this->buffer_a_), read_buffer_(&this->buffer_b_)
    {
        this->buffer_a_.head = 0;
        this->buffer_a_.size = 0;
        this->buffer_b_.head = 0;
        this->buffer_b_.size = 0;
    };

    ~TrajectoryBuffer() = default;

    bool push(const TrajectoryPoint &point)
    {
        if ( this->write_buffer_->head >= Capacity )
        {
            return false;
        }
        this->write_buffer_->buffer.at(this->write_buffer_->head) = point;
        this->write_buffer_->head = (this->write_buffer_->head + 1) % Capacity;
        this->write_buffer_->size++;

        return true;
    };

    void clear()
    {
        this->write_buffer_ = &this->buffer_a_;
        this->write_buffer_->head = 0;
        this->write_buffer_->size = 0;
        this->read_buffer_ = &this->buffer_b_;
        this->read_buffer_->head = 0;
        this->read_buffer_->size = 0;
    }

    std::size_t size() const
    {
        return this->read_buffer_->size;
    };
    /**
     * @brief Commit the trajectory write operation and interpolation coefficients pre-computation.
     * This function will swap the write and read buffer atomic pointer.
     */
    void commit()
    {
        // Memory barrier: ensure all writes are visible before swapping
        std::atomic_thread_fence(std::memory_order_release);

        // Atomically swap reader pointer
        this->read_buffer_.store(this->write_buffer_, std::memory_order_release);

        // Now use the old read buffer as the next write buffer
        this->write_buffer_ = (this->write_buffer_ == &this->buffer_a_) ? &this->buffer_b_ : &this->buffer_a_;

        this->write_buffer_->head = 0;
        this->write_buffer_->size = 0;
    };

    /**
     * @brief Perform B-Spline interpolation algorithm with trajectory waypoints.
     * 
     * @param type `InterpolationType` interpolation type choice.
     * @param query_time time of querying the target joint state.
     * @return JointState the target joint state at time point `query_time`.
     */
    ErrorCode interpolate(JointState& joint_state, TimePoint query_time) const
    {
        StaticMemoryBuffer* buf = read_buffer_.load(std::memory_order_acquire);
        const size_t N = buf->size;
        if (N < BSPLINE_DEGREE + 1)
            return ErrorCode::InvalidData;

        double query_sec = std::chrono::duration<double>(query_time.time_since_epoch()).count();

        size_t seg_idx = 0;
        double t0 = 0.0, t1 = 0.0;

        for (size_t i = 0; i + BSPLINE_DEGREE < N; ++i)
        {
            t0 = std::chrono::duration<double>(buf->buffer[i].timestamp.time_since_epoch()).count();
            t1 = std::chrono::duration<double>(buf->buffer[i + 1].timestamp.time_since_epoch()).count();

            if (query_sec >= t0 && query_sec < t1)
            {
                seg_idx = i;
                break;
            }
        }

        double u = (query_sec - t0) / (t1 - t0); // normalized [0,1]

        Eigen::Vector4d B, dB, ddB;
        B(0) = (1 - u) * (1 - u) * (1 - u);
        B(1) = 3 * u * (1 - u) * (1 - u);
        B(2) = 3 * u * u * (1 - u);
        B(3) = u * u * u;

        dB(0) = -3 * (1 - u) * (1 - u);
        dB(1) = 3 * (1 - u) * (1 - 3 * u);
        dB(2) = 3 * u * (2 - 3 * u);
        dB(3) = 3 * u * u;

        ddB(0) = 6 * (1 - u);
        ddB(1) = 6 * (6 * u - 4);
        ddB(2) = 6 * (2 - 6 * u);
        ddB(3) = 6 * u;

        Eigen::Matrix<double, ArmModel::num_dof_, COEFF_COUNT> P;
        for (size_t j = 0; j < COEFF_COUNT; ++j)
        {
            P.col(j) = buf->buffer[seg_idx + j].state.joint_pos;
        }

        joint_state.joint_pos = P * B;
        joint_state.joint_vel = P * dB / (t1 - t0);
        joint_state.joint_acc = P * ddB / ((t1 - t0) * (t1 - t0));
        joint_state.joint_torq.setZero();

        return ErrorCode::OK;
    };

private:
    constexpr static std::size_t BSPLINE_DEGREE = 3;
    constexpr static std::size_t COEFF_COUNT = BSPLINE_DEGREE + 1;

    StaticMemoryBuffer buffer_a_;
    StaticMemoryBuffer buffer_b_;
    StaticMemoryBuffer* write_buffer_;
    std::atomic<StaticMemoryBuffer*> read_buffer_;

    std::size_t index(std::size_t i) const
    {
        StaticMemoryBuffer* buf = this->read_buffer_.load(std::memory_order_acquire);
        return (buf->head + Capacity - buf->size + i) % Capacity;
    };
    const TrajectoryPoint &at_index(std::size_t i) const
    {
        StaticMemoryBuffer* buf = this->read_buffer_.load(std::memory_order_acquire);
        return buf->buffer.at(index(i));
    };
};
#endif //__TRAJECTORY_BUFFER_H__