/**
 * @file trajectory_buffer.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Trajectory buffer stores the trajectory points and provides interpolation capabilities.
 * @version 0.2
 * @date 2025-07-06
 *
 * @copyright Copyright (c) 2025
 *
 */

#pragma once

#include <vector>
#include <array>
#include <chrono>
#include <mutex>
#include <atomic>
#include <concepts>
#include <Eigen/Core>

// --- Base Class Declaration ---

template <typename T, std::size_t NumDof, std::size_t Capacity = 10>
class TrajectoryBuffer
{

public:
    using TimePoint = std::chrono::steady_clock::time_point;

    struct TrajectoryPoint
    {
        TimePoint timestamp;
        Eigen::Vector<T, NumDof> joint_pos;
    };

    TrajectoryBuffer() = default;
    virtual ~TrajectoryBuffer() = default;

    /**
     * @brief Writes a vector of trajectory points to the buffer, replacing existing content.
     * Thread-safe operation using a mutex lock.
     *
     * @param points The vector of trajectory points to write.
     * @return true if successful, false if the input vector exceeds capacity.
     */
    bool write(const std::array<TimePoint, Capacity>& time_points, const Eigen::Matrix<T, NumDof, Capacity>& trajectory)
    {
        std::lock_guard<std::mutex> lock(buffer_mutex_);
        for (std::size_t i = 0; i < Capacity; ++i)
        {
            buffer_[i].timestamp = time_points[i];
            buffer_[i].joint_pos = trajectory.col(i);
        }
        return true;
    }

    /**
     * @brief Pure virtual function for interpolating trajectory data.
     * Must be implemented by derived classes.
     *
     * @param query_time The time point for which to interpolate data.
     * @return The interpolated data point of type TrajPointDataType.
     *         Return value semantics for error/success need definition (e.g., optional, error code via reference).
     */
    virtual
    std::tuple<Eigen::Vector<T, NumDof>, Eigen::Vector<T, NumDof>, Eigen::Vector<T, NumDof>>
    interpolate(TimePoint query_time) const = 0;

protected:
    std::array<TrajectoryPoint, Capacity> buffer_;
    mutable std::mutex buffer_mutex_;
};

// --- Derived Class Declaration and Implementation ---
template <std::size_t Capacity>
concept CubicBsplineValid = Capacity > 3;

template <typename T, std::size_t NumDof, std::size_t Capacity = 10>
requires CubicBsplineValid<Capacity>
class BsplineTrajectoryBuffer : public TrajectoryBuffer<T, NumDof, Capacity>
{

private:
    using Base = TrajectoryBuffer<T, NumDof, Capacity>;
    using TrajectoryPoint = typename Base::TrajectoryPoint;
    using TimePoint = typename Base::TimePoint;

public:
    explicit BsplineTrajectoryBuffer() = default;
    ~BsplineTrajectoryBuffer() override = default;

    /**
     * @brief Perform B-Spline interpolation algorithm with trajectory waypoints.
     *
     * @param query_time time of querying the target joint state.
     * @return TrajPointDataType the target data at time point `query_time`.
     *         Returns a default-constructed TrajPointDataType if interpolation fails.
     */
    std::tuple<Eigen::Vector<T, NumDof>, Eigen::Vector<T, NumDof>, Eigen::Vector<T, NumDof>>
    interpolate(TimePoint query_time) const override
    {
        std::lock_guard<std::mutex> lock(this->buffer_mutex_);

        constexpr std::size_t N = Capacity;

        T query_sec = std::chrono::duration<T>(query_time.time_since_epoch()).count();
        size_t seg_idx = 0;
        T t0 = 0.0, t1 = 0.0;
        bool found_segment = false;

        // Find the correct segment
        for (size_t i = 0; i + BSPLINE_DEGREE < N; ++i)
        {
            t0 = std::chrono::duration<T>(this->buffer_[i].timestamp.time_since_epoch()).count();
            t1 = std::chrono::duration<T>(this->buffer_[i + 1].timestamp.time_since_epoch()).count();
            if (query_sec >= t0 && query_sec <= t1) // Use <= for endpoint inclusion
            {
                seg_idx = i;
                found_segment = true;
                break;
            }
        }

        // Handle case where query_time is before the first point or after the last
        if (!found_segment)
        {
            if (query_sec < std::chrono::duration<T>(this->buffer_[0].timestamp.time_since_epoch()).count())
            {
                // Before start, return first point
                return std::make_tuple(this->buffer_[0].joint_pos, Eigen::Vector<T, NumDof>::Zero(), Eigen::Vector<T, NumDof>::Zero());
            }
            else if (query_sec > std::chrono::duration<T>(this->buffer_[N-1].timestamp.time_since_epoch()).count())
            {
                // After end, return last point
                return std::make_tuple(this->buffer_[N-1].joint_pos, Eigen::Vector<T, NumDof>::Zero(), Eigen::Vector<T, NumDof>::Zero());
            }
            // If somehow still not found within valid range (shouldn't happen with >= <= check)
            // return std::make_tuple(Eigen::Vector<T, NumDof>::Zero(), Eigen::Vector<T, NumDof>::Zero(), Eigen::Vector<T, NumDof>::Zero());
        }

        // Avoid division by zero if t0 == t1 (identical timestamps)
        // if (t0 == t1)
        // {
        //     return std::make_tuple(this->buffer_[seg_idx].joint_pos, Eigen::Vector<T, NumDof>::Zero(), Eigen::Vector<T, NumDof>::Zero()); // Return the state at that time
        // }

        T u = (query_sec - t0) / (t1 - t0);
        u = std::max(static_cast<T>(0.0), std::min(static_cast<T>(1.0), u)); // Clamp u to [0, 1]

        // Calculate B-Spline basis functions (cubic)
        Eigen::Vector<T, 4> B, dB, ddB;
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

        Eigen::Matrix<T, NumDof, COEFF_COUNT> P;
        for (size_t j = 0; j < COEFF_COUNT && (seg_idx + j) < N; ++j)
        {
            P.col(j) = this->buffer_[seg_idx + j].joint_pos;
        }

        Eigen::Vector<T, NumDof> joint_pos, joint_vel, joint_acc;
        joint_pos = P * B;
        joint_vel = P * dB / (t1 - t0);
        joint_acc = P * ddB / ((t1 - t0) * (t1 - t0));

        return std::make_tuple(joint_pos, joint_vel, joint_acc);
    }

private:
    static constexpr std::size_t BSPLINE_DEGREE = 3;
    static constexpr std::size_t COEFF_COUNT = BSPLINE_DEGREE + 1;

};