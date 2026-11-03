/**
 * @file main.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Main program of hardware control.
 * @version 0.1
 * @date 2025-07-08
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <log.hpp>
#include <termination.h>
#include <arm_model.h>
#include <arm_hardware_interface.h>
#include <arm_planner.h>
#include <teleop_task_runner.h>

int main(int argv, char** argc)
{
    /* Create log file. */
    initLogger(PROJECT_PATH"/logs", "deploy");
    /* Initialize program stop flag as false. */
    TerminationHandler::stop_requested.store(false);
    /* Register SIGINT handler. */
    TerminationHandler::setup();
    /* Create simulation interface. */
    auto interface = std::make_shared<ArmHardwareInterface>();
    if ( interface->start("can1", "can2") != true)
    {
        LOG_ERROR("CAN interface initialization failed. Exiting...");
        return -1;
    }
    /* Create task runner. */
    TeleopTaskRunner runner(interface, 20, 200);
    runner.initialize();
    /* Blocking runner. */
    runner.run();
    /* Stop task runner.
     * Terminate interface, controller and planner. */
    runner.stop();
    interface->stop();
    /* Flush log data into file. */
    spdlog::drop_all();

    return 0;
}