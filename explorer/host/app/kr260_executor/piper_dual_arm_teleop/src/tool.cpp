/**
 * @file tool.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief Tool for AgileX Piper robotic manipulator.
 * @version 0.1
 * @date 2025-07-11
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <math.h>
#include <cstring>
#include <unistd.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <net/if.h>
#include <cstdint>

// Application name
const std::string APP_NAME = "tool";

// Piper 关节位置限幅（rad），与 arm_model.cpp 保持一致：
// J1 ±150°, J2 0~180°, J3 -170°~0°, J4 ±100°, J5 ±70°, J6 ±120°
const double JOINT_POS_LIMIT_LOW[6]  = {-2.618, 0,     -2.967, -1.745, -1.22, -2.0944};
const double JOINT_POS_LIMIT_HIGH[6] = { 2.618, M_PI,   0,      1.745,  1.22,  2.0944};

// Clamp joint positions into hardware limits. Returns true if any value was clamped.
bool clampJointPositions(std::vector<double>& positions)
{
    bool clamped = false;
    for (size_t i = 0; i < 6 && i < positions.size(); i++)
    {
        if (positions[i] < JOINT_POS_LIMIT_LOW[i])
        {
            std::cerr << "[限幅] 关节 " << (i + 1) << ": " << positions[i]
                      << " rad 低于下限 " << JOINT_POS_LIMIT_LOW[i]
                      << " rad，已钳制\n";
            positions[i] = JOINT_POS_LIMIT_LOW[i];
            clamped = true;
        }
        else if (positions[i] > JOINT_POS_LIMIT_HIGH[i])
        {
            std::cerr << "[限幅] 关节 " << (i + 1) << ": " << positions[i]
                      << " rad 高于上限 " << JOINT_POS_LIMIT_HIGH[i]
                      << " rad，已钳制\n";
            positions[i] = JOINT_POS_LIMIT_HIGH[i];
            clamped = true;
        }
    }
    return clamped;
}

// Enumeration for arm selection
enum class Arm
{
    LEFT,
    RIGHT,
    DUAL
};

// Command types
enum class CommandType
{
    ENABLE,
    DISABLE,
    SET_JOINT_POSITION,
    UNKNOWN
};

// Function Prototypes (placeholders)
void enableArm(Arm arm);
void disableArm(Arm arm);
void setJointPosition(Arm arm, const std::vector<double>& positions);

// Helper function to parse command
CommandType parseCommandType(const std::string& cmd);
Arm parseArm(const std::string& armStr);
bool isNumber(const std::string& s);

// Main command processing function
void processCommand(const std::vector<std::string>& args)
{
    if (args.size() < 2)
    {
        std::cerr << "Too few arguments.\n";
        return;
    }

    CommandType cmd = parseCommandType(args[0]);
    if (cmd == CommandType::UNKNOWN)
    {
        std::cerr << "Unknown command: " << args[0] << "\n";
        return;
    }

    if (args[1] != "left" && args[1] != "right" && args[1] != "dual")
    {
        std::cerr << "Invalid arm specified: " << args[1] << "\n";
        return;
    }

    Arm arm = parseArm(args[1]);

    switch (cmd)
    {
        case CommandType::ENABLE:
            enableArm(arm);
            break;
        case CommandType::DISABLE:
            disableArm(arm);
            break;
        case CommandType::SET_JOINT_POSITION:
            if (args.size() < 3 || args[2] != "all")
            {
                std::cerr << "Missing 'all' after arm type in set command.\n";
                return;
            }

            if (args.size() != 9)
            {
                std::cerr << "Expected 6 joint positions.\n";
                return;
            }

            {
                std::vector<double> positions;
                for (size_t i = 3; i < args.size(); ++i)
                {
                    if (!isNumber(args[i]))
                    {
                        std::cerr << "Invalid number: " << args[i] << "\n";
                        return;
                    }
                    positions.push_back(std::stod(args[i]));
                }

                setJointPosition(arm, positions);
            }
            break;
        default:
            std::cerr << "Unsupported command.\n";
    }
}

// Parse command type
CommandType parseCommandType(const std::string& cmd)
{
    if (cmd == "enable") return CommandType::ENABLE;
    if (cmd == "disable") return CommandType::DISABLE;
    if (cmd == "set") return CommandType::SET_JOINT_POSITION;
    return CommandType::UNKNOWN;
}

// Parse arm type
Arm parseArm(const std::string& armStr)
{
    if (armStr == "left") return Arm::LEFT;
    if (armStr == "right") return Arm::RIGHT;
    return Arm::DUAL;
}

// Check if string is a number
bool isNumber(const std::string& s)
{
    try
    {
        std::stod(s);
        return true;
    }
    catch (...)
    {
        return false;
    }
}

// Placeholder implementations

bool check(std::string if_name)
{
    struct stat st;
    std::string path = "/sys/class/net/";
    path += if_name;
    if (stat(path.c_str(), &st) != 0)
    {
        return false;
    }
    else
    {
        return true;
    }
}

int connect(Arm arm)
{
    std::string if_name = (arm == Arm::LEFT ? "can1" : "can2");
    if ( !check(if_name) )
    {
        return -1;
    }
    int s = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    struct sockaddr_can can_addr_ = {0};
    struct ifreq can_ifr_ = {0};
    strcpy(can_ifr_.ifr_name, if_name.c_str());
    ioctl(s, SIOCGIFINDEX, &can_ifr_);
    can_addr_.can_family = AF_CAN;
    can_addr_.can_ifindex = can_ifr_.ifr_ifindex;
    bind(s, (struct sockaddr *)&can_addr_, sizeof(can_addr_));
    return s;
}

void enableArm(Arm arm)
{
    int s = connect(arm);
    if ( s == -1 )
    {
        std::cerr << "CAN interface doesn't exist." << std::endl;
        return;
    }

    struct can_frame frame;
    for (int i=0 ; i<10 ; i++)
    {
        memset(&frame, 0, sizeof(frame));
        frame.can_id = 0x471;
        frame.can_dlc = 8;
        frame.data[0] = 7; // Select all the actuators.
        frame.data[1] = 0x02; // Enable
        write(s, &frame, sizeof(struct can_frame));
        sleep(0.05);
    }
}

void disableArm(Arm arm)
{
    int s = connect(arm);
    if ( s == -1 )
    {
        std::cerr << "CAN interface doesn't exist." << std::endl;
        return;
    }

    struct can_frame frame;
    for (int i=0 ; i<10 ; i++)
    {
        memset(&frame, 0, sizeof(frame));
        frame.can_id = 0x471;
        frame.can_dlc = 8;
        frame.data[0] = 7; // Select all the actuators.
        frame.data[1] = 0x01; // Disable
        write(s, &frame, sizeof(struct can_frame));
        sleep(0.05);
    }
}

void setJointPosition(Arm arm, const std::vector<double>& positions_in)
{
    /* 限幅保护：钳制到关节硬件限位内，超限打印警告后继续发送安全值 */
    std::vector<double> positions = positions_in;
    clampJointPositions(positions);

    int s = connect(arm);
    if ( s == -1 )
    {
        std::cerr << "CAN interface doesn't exist." << std::endl;
        return;
    }

    struct can_frame frame;
    for (int i=0 ; i<10 ; i++)
    {
        memset(&frame, 0, sizeof(frame));
        frame.can_id = 0x151;
        frame.can_dlc = 8;
        frame.data[0] = 0x01;   // CAN command mode.
        frame.data[1] = 1;      // Joint move mode.
        frame.data[2] = 100;    // Move rate.
        frame.data[3] = 0x00;   // Joint position control.
        write(s, &frame, sizeof(struct can_frame));
        sleep(0.05);
    }

    int32_t joint_pos_scaled;
    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x155;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(positions[0] * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(positions[1] * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(s, &frame, sizeof(struct can_frame));

    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x156;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(positions[2] * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(positions[3] * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(s, &frame, sizeof(struct can_frame));

    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x157;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(positions[4] * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(positions[5] * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(s, &frame, sizeof(struct can_frame));
}

// Entry point for command line usage
int main(int argc, char* argv[])
{
    if (argc < 2)
    {
        std::cerr << "Usage: " << APP_NAME << " <command> [arguments...]\n";
        return 1;
    }

    std::vector<std::string> args;
    for (int i = 1; i < argc; ++i)
    {
        args.push_back(argv[i]);
    }

    processCommand(args);

    return 0;
}
