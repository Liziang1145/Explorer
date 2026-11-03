/**
 * @file arm_planner.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Robotic arm trajectory planner.
 * @version 0.1
 * @date 2025-08-08
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#pragma once

#include <vector>
#include <tuple>
#include <chrono>
#include <concepts>
#include <Eigen/Core>
#include <config.h>


class ArmPlanner
{
public:
    using TimePoint = std::chrono::steady_clock::time_point;
    using Duration = std::chrono::steady_clock::duration;

    template<typename T, std::size_t NumDof, std::size_t WayPointAmount>
    static std::tuple<std::vector<TimePoint>, Eigen::Matrix<T, NumDof, WayPointAmount>>
    plan(const TimePoint& start_time, const double min_duration, const Eigen::Vector<T, NumDof>& start, const Eigen::Vector<T, NumDof>& end);
};

class LinearArmPlanner : ArmPlanner
{
private:
    using TimePoint = ArmPlanner::TimePoint;
    using Duration = ArmPlanner::Duration;
public:

    template<typename T, std::size_t NumDof, std::size_t WayPointAmount>
    static std::tuple<std::array<TimePoint, WayPointAmount>, Eigen::Matrix<T, NumDof, WayPointAmount>>
    plan(const TimePoint& start_time, const double min_duration, const Eigen::Vector<T, NumDof>& start, const Eigen::Vector<T, NumDof>& end)
    {
        Eigen::Matrix<T, NumDof, WayPointAmount> trajectory;
        std::array<TimePoint, WayPointAmount> time_point;
        double duration = min_duration + CONFIG_TRAJECTORY_DECAY_COEF * (end - start).squaredNorm();
        double interval = duration / (WayPointAmount - 1);
        Duration step_duration = std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(interval));
        Eigen::Vector<T, NumDof> step_position = (end - start) / static_cast<T>(WayPointAmount - 1);
        for (std::size_t i = 0; i < WayPointAmount; ++i)
        {
            trajectory.col(i) = (start + step_position * i);
            time_point[i] = (start_time + step_duration * i);
        }
        return std::make_tuple(time_point, trajectory);
    }
};