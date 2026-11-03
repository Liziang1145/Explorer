/**
 * @file utils.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Common utilities.
 * @version 0.1
 * @date 2025-08-10
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#pragma once

#include <time.h>
#include <functional>
#include <chrono>
#include <thread>

static inline void increaseTimeSpec(struct timespec* time, const struct timespec* increasement)
{
    time->tv_sec += increasement->tv_sec;
    time->tv_nsec += increasement->tv_nsec;

    if (time->tv_nsec >= 1000000000)
    {
        time->tv_sec++;
        time->tv_nsec -= 1000000000;
    }
};

// Template function to support different function signatures
template<typename Func>
static inline std::thread registerRealTimeLoop(Func function, unsigned int frequency, const bool* termination)
{
    if ( frequency == 0 )
        throw std::invalid_argument("loop frequency can't be zero");
    std::thread thread([&]()
    {
        struct timespec wakeup_time = {0,0};
        struct timespec cycletime = {0, 0}; // Initialize to zero
        
        // Convert frequency (Hz) to timespec
        double period_seconds = 1.0 / static_cast<double>(frequency);
        cycletime.tv_sec = static_cast<time_t>(period_seconds);
        cycletime.tv_nsec = static_cast<long>((period_seconds - cycletime.tv_sec) * 1e9);

        clock_gettime(CLOCK_MONOTONIC, &wakeup_time);

        while ( !*termination )
        {
            increaseTimeSpec(&wakeup_time, &cycletime);
            clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wakeup_time, NULL);

            function();
        }
    });
    return thread;
}

// Specialized version for functions with parameters
template<typename Func, typename... Args>
static inline std::thread registerRealTimeLoop(Func function, unsigned int frequency, const bool* termination, Args... args)
{
    if ( frequency == 0 )
        throw std::invalid_argument("loop frequency can't be zero");

    std::thread thread([&]()
    {
        struct timespec wakeup_time = {0,0};
        struct timespec cycletime = {0, 0}; // Initialize to zero
        
        // Convert frequency (Hz) to timespec
        double period_seconds = 1.0 / static_cast<double>(frequency);
        cycletime.tv_sec = static_cast<time_t>(period_seconds);
        cycletime.tv_nsec = static_cast<long>((period_seconds - cycletime.tv_sec) * 1e9);

        clock_gettime(CLOCK_MONOTONIC, &wakeup_time);

        while ( !*termination )
        {
            increaseTimeSpec(&wakeup_time, &cycletime);
            clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wakeup_time, NULL);

            function(args...);
        }
    });
    return thread;
}