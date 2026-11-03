/**
 * @file termination.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief Ctrl-C termination handler.
 * @version 0.1
 * @date 2025-07-08
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __TERMINATION_H__
#define __TERMINATION_H__

#include <csignal>
#include <atomic>

class TerminationHandler
{
public:
    inline static std::atomic<bool> stop_requested;

    static void signalHandler(int signal)
    {
        if (signal == SIGINT)
        {
            stop_requested.store(true, std::memory_order_release);
        }
    }

    static void setup()
    {
        std::signal(SIGINT, signalHandler);  // Simple and portable
        // For more advanced handling, use sigaction with SA_RESTART
    }
};

#endif // __TERMINATION_H__