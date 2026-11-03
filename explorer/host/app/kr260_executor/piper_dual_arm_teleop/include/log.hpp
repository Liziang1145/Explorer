#pragma once

#ifndef __LOG_HPP__
#define __LOG_HPP__

#include <sstream>
#include <iomanip>
#include <ctime>
#include <chrono>
#include <string>
#include <filesystem>
#include <spdlog/spdlog.h>
#include <spdlog/async.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/sinks/basic_file_sink.h>

#define LOG_CRITICAL(...) spdlog::critical(__VA_ARGS__)
#define LOG_ERROR(...) spdlog::error(__VA_ARGS__)
#define LOG_WARN(...) spdlog::warn(__VA_ARGS__)
#define LOG_INFO(...) spdlog::info(__VA_ARGS__)
#define LOG_DEBUG(...) spdlog::debug(__VA_ARGS__)
#define LOG_TRACE(...) spdlog::trace(__VA_ARGS__)

/**
 * @brief Initialize a console and file logger with the given log directory and title.
 * 
 * @param log_dir 
 * @param log_title 
 */
inline void initLogger(std::filesystem::path log_dir, std::string log_title)
{
    /**
     * @brief Utility function to get the current time formatted as "YYYY-mm-dd_HH-MM-SS"
     * 
     * @return std::string 
     */
    auto getCurrentTimeForLog = []()
    {
        auto t = std::time(nullptr);
        auto tm = *std::localtime(&t);

        std::ostringstream oss;
        oss << std::put_time(&tm, "%Y-%m-%d_%H:%M:%S");
        return oss.str();
    };

    std::filesystem::path log_file_name = log_dir / (log_title + '_' + getCurrentTimeForLog() + ".log");

    // Initialize spdlog with an asynchronous logger
    spdlog::init_thread_pool(8192, 1); // Queue size, 1 worker thread

    // Create sinks for console and file
    auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
    auto file_sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(log_file_name, true);

    // Set log levels for each sink
    console_sink->set_level(spdlog::level::info);
    file_sink->set_level(spdlog::level::debug);

    // Create a logger that writes to both console and file
    std::vector<spdlog::sink_ptr> sinks {console_sink, file_sink};
    auto logger = std::make_shared<spdlog::async_logger>("multi_sink", sinks.begin(), sinks.end(), spdlog::thread_pool(), spdlog::async_overflow_policy::block);

    // Register logger
    spdlog::set_default_logger(logger);

    // Set log format (same for both console and file)
    spdlog::set_pattern("[%Y-%m-%d %H:%M:%S.%f] [%^%l%$] %v");

    // Set the global log level to the lowest level of the sinks
    spdlog::set_level(spdlog::level::debug); // Set to 'debug' level to ensure all messages are processed
}
#endif // __LOG_HPP__