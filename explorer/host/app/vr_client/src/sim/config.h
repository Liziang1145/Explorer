/**
 * @file config.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief Project configuration header file
 * @version 0.1
 * @date 2025-08-07
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __CONFIG_H__
#define __CONFIG_H__

#define CONFIG_CLIENT_IPV4_ADDRESS "192.168.1.5"
#define CONFIG_CLIENT_PORT 12345
#define CONFIG_CLIENT_MSG_QUEUE "/workspace/tmp/arm_station"
#define CONFIG_SERVER_IPV4_ADDRESS "192.168.1.108"
#define CONFIG_SERVER_PORT 54321
#define CONFIG_SERVER_MSG_QUEUE "/workspace/tmp/arm_solve"
#define CONFIG_LEFT_ARM_BASE_X      0.238
#define CONFIG_LEFT_ARM_BASE_Y      0.197
#define CONFIG_LEFT_ARM_BASE_Z      0.42
#define CONFIG_LEFT_ARM_BASE_ROLL   0.0
#define CONFIG_LEFT_ARM_BASE_PITCH  0.0
#define CONFIG_LEFT_ARM_BASE_YAW    0.0
#define CONFIG_RIGHT_ARM_BASE_X     0.238
#define CONFIG_RIGHT_ARM_BASE_Y     -0.197
#define CONFIG_RIGHT_ARM_BASE_Z     0.42
#define CONFIG_RIGHT_ARM_BASE_ROLL  0.0
#define CONFIG_RIGHT_ARM_BASE_PITCH 0.0
#define CONFIG_RIGHT_ARM_BASE_YAW   0.0
#define CONFIG_WAYPOINT_AMOUNT 10
#define CONFIG_PLANNER_FREQUENCY 20
#define CONFIG_CONTROLLER_FREQUENCY 200
#define CONFIG_TRAJECTORY_DECAY_COEF 3.0
#endif // __CONFIG_H__