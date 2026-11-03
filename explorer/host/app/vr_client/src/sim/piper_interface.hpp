/**
 * @file piper_interface.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic manipulator CAN control interface implementation.
 * @version 0.1
 * @date 2025-08-10
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <cstdint>
#include <cstring>
#include <functional>
#include <vector>
#include <array>
#include <map>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <poll.h>
#include <fcntl.h>

#include "log.hpp"

/**
 * @brief Class for controlling and communicating with the Piper robotic arm via CAN protocol.
 */
template <typename T>
class PiperInterface 
{
public:
    // Function pointer type for receiving CAN frames
    using CanReceiveCallback = std::function<bool(struct can_frame&)>;

    // Control modes
    enum ControlMode : uint8_t 
    {
        STANDBY_MODE = 0x00,
        CAN_CONTROL_MODE = 0x01,
        ETHERNET_CONTROL_MODE = 0x03,
        WIFI_CONTROL_MODE = 0x04,
        OFFLINE_TRAJECTORY_MODE = 0x07
    };

    // MOVE modes
    enum MoveMode : uint8_t 
    {
        MOVE_P = 0x00,  // Point-to-point (Cartesian)
        MOVE_J = 0x01,  // Joint interpolation
        MOVE_L = 0x02,  // Linear in Cartesian
        MOVE_C = 0x03,  // Circular
        MOVE_M = 0x04   // Custom trajectory
    };

    // Arm installation orientation
    enum InstallationPose : uint8_t 
    {
        INVALID_POSE = 0x00,
        HORIZONTAL = 0x01,
        SIDE_LEFT = 0x02,
        SIDE_RIGHT = 0x03
    };

    // Mechanical states
    enum MechanicalState : uint8_t 
    {
        NORMAL = 0x00,
        EMERGENCY_STOP = 0x01,
        NO_SOLUTION = 0x02,
        SINGULARITY = 0x03,
        TARGET_ANGLE_LIMIT_EXCEEDED = 0x04,
        JOINT_COMM_ERROR = 0x05,
        BRAKE_NOT_RELEASED = 0x06,
        COLLISION_DETECTED = 0x07,
        TEACHING_OVER_SPEED = 0x08,
        JOINT_STATUS_ABNORMAL = 0x09,
        OTHER_ERROR = 0x0A,
        TEACHING_RECORD = 0x0B,
        TEACHING_EXECUTE = 0x0C,
        TEACHING_PAUSE = 0x0D,
        MAIN_CONTROLLER_NTC_OVER_TEMP = 0x0E,
        RELEASE_RESISTOR_NTC_OVER_TEMP = 0x0F
    };

    // Constructor
    explicit PiperInterface(const std::string& can_interface = "can0") 
        : can_interface_(can_interface), can_socket_(-1), listening_(false)
    {
    }

    ~PiperInterface() = default;
    /**
     * @brief Initialize CAN interface using SocketCAN.
     * @return true if successful.
     */
    bool initCan()
    {
        struct stat st;
        std::string can_file_path = "/sys/class/net/" + this->can_interface_;
        if (stat(can_file_path.c_str(), &st) != 0)
        {
            LOG_ERROR("CAN interface {} does not exist", this->can_interface_);
            return false;
        }
        struct ifreq ifr;
        struct sockaddr_can addr;

        // Create socket
        can_socket_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
        if (can_socket_ < 0) 
        {
            LOG_ERROR("Failed to create CAN socket");
            return false;
        }

        // Set up address
        std::strcpy(ifr.ifr_name, can_interface_.c_str());
        if (ioctl(can_socket_, SIOCGIFINDEX, &ifr) < 0) 
        {
            LOG_ERROR("Failed to get CAN interface index");
            close(can_socket_);
            can_socket_ = -1;
            return false;
        }

        addr.can_family = AF_CAN;
        addr.can_ifindex = ifr.ifr_ifindex;

        // Bind socket
        if (bind(can_socket_, (struct sockaddr*)&addr, sizeof(addr)) < 0) 
        {
            LOG_ERROR("Failed to bind CAN socket");
            close(can_socket_);
            can_socket_ = -1;
            return false;
        }

        // Set socket to non-blocking
        int flags = fcntl(can_socket_, F_GETFL, 0);
        fcntl(can_socket_, F_SETFL, flags | O_NONBLOCK);

        LOG_INFO("Successfully initialized CAN interface: {}", can_interface_);
        return true;
    }

    void listen()
    {
        listening_ = true;
        listen_thread_ = std::thread([this](){while(listening_){queryState();processExceptions();}});
    }

    void stop()
    {
        disableAllMotors(20);
        listening_ = false;
        listen_thread_.join();
        if (can_socket_ >= 0) 
        {
            close(can_socket_);
            can_socket_ = -1;
        }
    }
private:
    std::string can_interface_;
    int can_socket_;

    bool listening_;
    std::thread listen_thread_;

    // Feedback data structures
    struct 
    {
        uint8_t control_mode = 0;
        uint8_t mechanical_state = 0;
        uint8_t move_mode = 0;
        uint8_t teaching_state = 0;
        uint8_t motion_state = 0;
        uint8_t trajectory_index = 0;
        uint16_t fault_code = 0;
        // Fault bits from byte 6 and 7
        struct 
        {
            bool joint_comm_error[6] = {false};
            bool joint_angle_limit_exceeded[6] = {false};
        } fault_bits;
    } state;

    struct 
    {
        T travel_mm = 0.0;
        T torque_nm = 0.0;
        uint8_t status = 0;
        // Status bits
        struct 
        {
            bool voltage_low = false;
            bool motor_over_temp = false;
            bool driver_over_current = false;
            bool driver_over_temp = false;
            bool sensor_error = false;
            bool driver_error = false;
            bool enabled = false;
            bool zeroed = false;
        } bits;
    } gripper;

    T joint_angles[6] = {0};
    T cartesian_pos[6] = {0};  // x, y, z, rx, ry, rz

    // Joint driver feedback (high speed)
    struct JointDriverHS 
    {
        T speed_rad_per_sec = 0.0;  // 0.001 rad/s
        T current_a = 0.0;          // 0.001 A
        T position_rad = 0.0;       // rad
    };
    JointDriverHS joint_driver_hs[6];

    // Joint driver feedback (low speed)
    struct JointDriverLS 
    {
        T voltage_v = 0.0;          // 0.1 V
        T driver_temp_c = 0.0;      // 1°C
        int8_t motor_temp_c = 0;
        T bus_current_a = 0.0;      // 0.001 A
        uint8_t driver_status = 0;
        // Status bits
        struct 
        {
            bool voltage_low = false;
            bool motor_over_temp = false;
            bool driver_over_current = false;
            bool driver_over_temp = false;
            bool collision_protection = false;
            bool driver_error = false;
            bool enabled = false;
            bool stall_protection = false;
        } bits;
    };
    JointDriverLS joint_driver_ls[6];

public:
    /**
     * @brief Enable all joint motors.
     * @return true if command sent successfully.
     */
    bool enableAllMotors(std::size_t trials) 
    {
        auto enable_all_motors = [this]()
        {
            struct can_frame frame;
            frame.can_id = 0x471;
            frame.can_dlc = 8;
            std::memset(frame.data, 0, 8);
            frame.data[0] = 0x07;  // All joints
            frame.data[1] = 0x02;  // Enable
            return sendCanFrame(frame);
        };
        bool arm_enabled = false;
        LOG_INFO("start to enable actuators on interface {}", can_interface_);
        for ( std::size_t i=0 ; i<trials ; i++ )
        {
            enable_all_motors();
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            std::array<bool, 6> enable_status;
            for ( std::size_t j=0 ; j<6 ; j++ )
            {
                enable_status[j] = isJointEnabled(j);
            }
            if ( std::all_of(enable_status.begin(), enable_status.end(), [&](const bool& val){return val==true;}) )
            {
                arm_enabled = true;
                LOG_INFO("interface {} actuators are all enabled.", can_interface_);
                break;
            }
            else
            {
                LOG_WARN("interface {} actuator enable status:[1]{},[2]{},[3]{},[4]{},[5]{},[6]{}",
                    can_interface_,
                    enable_status[0], enable_status[1], enable_status[2],
                    enable_status[3], enable_status[4], enable_status[5]);
            }
        }
        return arm_enabled;
    }

    /**
     * @brief Disable all joint motors.
     * @return true if command sent successfully.
     */
    bool disableAllMotors(std::size_t trials) 
    {
        auto disable_all_motors = [this]()
        {
            struct can_frame frame;
            frame.can_id = 0x471;
            frame.can_dlc = 8;
            std::memset(frame.data, 0, 8);
            frame.data[0] = 0x07;  // All joints
            frame.data[1] = 0x01;  // Disable
            return sendCanFrame(frame);
        };
        bool arm_disabled = false;
        LOG_INFO("start to disable actuators on interface {}", can_interface_);
        for ( std::size_t i=0 ; i<trials ; i++ )
        {
            disable_all_motors();
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            std::array<bool, 6> disable_status;
            for ( std::size_t j=0 ; j<6 ; j++ )
            {
                disable_status[j] = !isJointEnabled(j);
            }
            if ( std::all_of(disable_status.begin(), disable_status.end(), [&](const bool& val){return val==true;}) )
            {
                arm_disabled = true;
                LOG_INFO("interface {} actuators are all disabled.", can_interface_);
                break;
            }
            else
            {
                LOG_WARN("interface {} actuator disable status:[1]{},[2]{},[3]{},[4]{},[5]{},[6]{}",
                    can_interface_,
                    disable_status[0], disable_status[1], disable_status[2],
                    disable_status[3], disable_status[4], disable_status[5]);
            }
        }
        return arm_disabled;
    }

    /**
     * @brief Enter CAN control mode.
     * @return true if command sent successfully.
     */
    bool enterCANControlMode() 
    {
        struct can_frame frame;
        frame.can_id = 0x151;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = CAN_CONTROL_MODE;
        return sendCanFrame(frame);
    }

    /**
     * @brief Set control mode and motion parameters.
     * 
     * @param move_mode Motion type (MOVE_J, MOVE_P, etc.).
     * @param enable_mit_mode Whether to enable MIT control mode.
     * @param mode Control mode.
     * @param speed_percentage Speed percentage (0-100).
     * @param dwell_time Dwell time for offline trajectory (0-254 seconds, 255 to terminate).
     * @param installation Installation pose.
     * @return true if command sent successfully.
     */
    bool setControlMode(MoveMode move_mode, bool enable_mit_mode = false, ControlMode mode = ControlMode::CAN_CONTROL_MODE, uint8_t speed_percentage = 100,
                        uint8_t dwell_time = 0, InstallationPose installation = HORIZONTAL) 
    {
        if (speed_percentage > 100) speed_percentage = 100;
        struct can_frame frame;
        frame.can_id = 0x151;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = static_cast<uint8_t>(mode);
        frame.data[1] = static_cast<uint8_t>(move_mode);
        frame.data[2] = speed_percentage;
        frame.data[3] = enable_mit_mode ? 0xAD : 0x00;
        frame.data[4] = dwell_time;
        frame.data[5] = static_cast<uint8_t>(installation);
        return sendCanFrame(frame);
    }

    /**
     * @brief Set target Cartesian position (X, Y, Z) and orientation (RX, RY, RZ).
     * Units: mm (0.001mm), degrees (0.001°).
     */
    bool setCartesianTarget(T x_mm, T y_mm, T z_mm,
                            T rx_deg, T ry_deg, T rz_deg) 
    {
        auto sendSegment = [this](canid_t id, int32_t val_high, int32_t val_low) 
        {
            struct can_frame frame;
            frame.can_id = id;
            frame.can_dlc = 8;
            std::memset(frame.data, 0, 8);
            frame.data[0] = (val_high >> 24) & 0xFF;
            frame.data[1] = (val_high >> 16) & 0xFF;
            frame.data[2] = (val_high >> 8) & 0xFF;
            frame.data[3] = val_high & 0xFF;
            frame.data[4] = (val_low >> 24) & 0xFF;
            frame.data[5] = (val_low >> 16) & 0xFF;
            frame.data[6] = (val_low >> 8) & 0xFF;
            frame.data[7] = val_low & 0xFF;
            return sendCanFrame(frame);
        };

        int32_t x = static_cast<int32_t>(x_mm * 1000);
        int32_t y = static_cast<int32_t>(y_mm * 1000);
        int32_t z = static_cast<int32_t>(z_mm * 1000);
        int32_t rx = static_cast<int32_t>(rx_deg * 1000);
        int32_t ry = static_cast<int32_t>(ry_deg * 1000);
        int32_t rz = static_cast<int32_t>(rz_deg * 1000);

        if (!sendSegment(0x152, x, y)) return false;
        if (!sendSegment(0x153, z, rx)) return false;
        if (!sendSegment(0x154, ry, rz)) return false;

        return true;
    }

    /**
     * @brief Set target joint angles (J1-J6) in degrees.
     * Units: radian.
     */
    bool setJointPosition(std::array<T, 6> joint_pos) 
    {
        auto sendSegment = [this](canid_t id, int32_t val1, int32_t val2) 
        {
            struct can_frame frame;
            frame.can_id = id;
            frame.can_dlc = 8;
            std::memset(frame.data, 0, 8);
            frame.data[0] = (val1 >> 24) & 0xFF;
            frame.data[1] = (val1 >> 16) & 0xFF;
            frame.data[2] = (val1 >> 8) & 0xFF;
            frame.data[3] = val1 & 0xFF;
            frame.data[4] = (val2 >> 24) & 0xFF;
            frame.data[5] = (val2 >> 16) & 0xFF;
            frame.data[6] = (val2 >> 8) & 0xFF;
            frame.data[7] = val2 & 0xFF;
            return sendCanFrame(frame);
        };

        int32_t j1 = static_cast<int32_t>(joint_pos[0] * 180.0 / M_PI * 1000);
        int32_t j2 = static_cast<int32_t>(joint_pos[1] * 180.0 / M_PI * 1000);
        int32_t j3 = static_cast<int32_t>(joint_pos[2] * 180.0 / M_PI * 1000);
        int32_t j4 = static_cast<int32_t>(joint_pos[3] * 180.0 / M_PI * 1000);
        int32_t j5 = static_cast<int32_t>(joint_pos[4] * 180.0 / M_PI * 1000);
        int32_t j6 = static_cast<int32_t>(joint_pos[5] * 180.0 / M_PI * 1000);

        if (!sendSegment(0x155, j1, j2)) return false;
        if (!sendSegment(0x156, j3, j4)) return false;
        if (!sendSegment(0x157, j5, j6)) return false;

        return true;
    }

    bool setJointMitControl(const std::array<T, 6>& joint_pos, const std::array<T, 6>& joint_vel, const std::array<T, 6>& joint_torq)
    {
        auto sendSegment = [this](int id, T pos, T vel, T torq, T kp, T kd) -> bool
        {
            int16_t pos_enc = floating2int16(pos, -12.5, 12.5, 16);
            int16_t vel_enc = floating2int16(vel, -45.0, 45.0, 12);
            int16_t kp_enc = floating2int16(kp, 0.0, 500.0, 12);
            int16_t kd_enc = floating2int16(kd, -5, 5.0, 12);
            int8_t torq_enc = floating2int8(torq, -18.0, 18.0, 8);

            struct can_frame frame;
            uint8_t crc = 0;
            memset(&frame, 0, sizeof(frame));
            frame.can_id = 0x15A + id;
            frame.can_dlc = 8;
            frame.data[0] = (pos_enc >> 8);
            frame.data[1] = (pos_enc & 0xFF);
            frame.data[2] = (vel_enc >> 4);
            frame.data[3] = (((vel_enc & 0x0F) << 4)|kp_enc >> 8);
            frame.data[4] = (kp_enc & 0xFF);
            frame.data[5] = (kd_enc >> 4);
            frame.data[6] = (((kd_enc & 0x0F) << 4)|(torq_enc >> 4));
            crc = (frame.data[0]^frame.data[1]^frame.data[2]^frame.data[3]^frame.data[4]^frame.data[5]^frame.data[6]) & 0x0F;
            frame.data[7] = ((torq_enc << 4) | crc);
            return sendCanFrame(frame);
        };

        for ( int i=0 ; i<6 ; i++ )
        {
            if ( !sendSegment(i, joint_pos(i), joint_vel(i), joint_torq(i), 10.0, 0.8) ) return false;
        }

        return true;
    }

    /**
     * @brief Set arc motion point (start, mid, end).
     * @param point_type 0x01=start, 0x02=mid, 0x03=end
     */
    bool setArcPoint(uint8_t point_type) 
    {
        if (point_type < 0x01 || point_type > 0x03) return false;
        struct can_frame frame;
        frame.can_id = 0x158;
        frame.can_dlc = 1;
        frame.data[0] = point_type;
        return sendCanFrame(frame);
    }

    /**
     * @brief Emergency stop.
     * @return true if command sent.
     */
    bool emergencyStop() 
    {
        struct can_frame frame;
        frame.can_id = 0x150;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = 0x01;  // Emergency stop
        return sendCanFrame(frame);
    }

    /**
     * @brief Resume from emergency stop.
     * @return true if command sent.
     */
    bool resumeFromEmergencyStop() 
    {
        struct can_frame frame;
        frame.can_id = 0x150;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = 0x02;  // Resume
        return sendCanFrame(frame);
    }

    /**
     * @brief Set gripper position and torque.
     * @param travel_mm Gripper travel in mm (0 = closed).
     * @param torque_nm Torque limit in Nm.
     * @param enable Enable gripper.
     * @param clear_error Clear error.
     * @param set_zero Set current position as zero.
     */
    bool setGripper(T travel_mm, T torque_nm = 0.5f,
                    bool enable = true, bool clear_error = false, bool set_zero = false) 
    {
        struct can_frame frame;
        frame.can_id = 0x159;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);

        int32_t travel = static_cast<int32_t>(travel_mm * 1000);
        int16_t torque = static_cast<int16_t>(torque_nm * 1000);

        frame.data[0] = (travel >> 24) & 0xFF;
        frame.data[1] = (travel >> 16) & 0xFF;
        frame.data[2] = (travel >> 8) & 0xFF;
        frame.data[3] = travel & 0xFF;
        frame.data[4] = (torque >> 8) & 0xFF;
        frame.data[5] = torque & 0xFF;

        frame.data[6] = 0;
        if (enable) frame.data[6] |= 0x01;
        if (clear_error) frame.data[6] |= 0x02;

        if (set_zero) 
        {
            frame.data[7] = 0xAE;  // Set zero
            frame.data[6] = 0x00;  // Must be disabled when setting zero
        } 
        else 
        {
            frame.data[7] = 0x00;
        }

        return sendCanFrame(frame);
    }

    /**
     * @brief Set collision sensitivity for each joint (0-8, 0=off).
     */
    bool setCollisionLevel(uint8_t j1, uint8_t j2, uint8_t j3,
                           uint8_t j4, uint8_t j5, uint8_t j6) 
    {
        struct can_frame frame;
        frame.can_id = 0x47A;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = j1 > 8 ? 8 : j1;
        frame.data[1] = j2 > 8 ? 8 : j2;
        frame.data[2] = j3 > 8 ? 8 : j3;
        frame.data[3] = j4 > 8 ? 8 : j4;
        frame.data[4] = j5 > 8 ? 8 : j5;
        frame.data[5] = j6 > 8 ? 8 : j6;
        return sendCanFrame(frame);
    }

    /**
     * @brief Set zero position for a specific joint.
     * @param joint_id 1-6
     * @return true if command sent.
     */
    bool setJointZero(uint8_t joint_id) 
    {
        if (joint_id < 1 || joint_id > 6) return false;
        struct can_frame frame;
        frame.can_id = 0x475;
        frame.can_dlc = 8;
        std::memset(frame.data, 0, 8);
        frame.data[0] = joint_id;
        frame.data[1] = 0xAE;  // Set zero
        return sendCanFrame(frame);
    }

    /**
     * @brief Query current robot state by processing all received CAN frames.
     * @return true if frames were processed.
     */
    bool queryState() 
    {
        struct can_frame frame;
        bool received = false;
        
        while (receiveCanFrame(frame)) 
        {
            received = true;
            switch (frame.can_id) 
            {
                case 0x2A1: parseStateFeedback(frame); break;
                case 0x2A2: parseCartesianPos1(frame); break;
                case 0x2A3: parseCartesianPos2(frame); break;
                case 0x2A4: parseCartesianPos3(frame); break;
                case 0x2A5: parseJointAngles12(frame); break;
                case 0x2A6: parseJointAngles34(frame); break;
                case 0x2A7: parseJointAngles56(frame); break;
                case 0x2A8: parseGripperFeedback(frame); break;
                case 0x473: parseJointLimitFeedback(frame); break;
                case 0x476: parseSetResponse(frame); break;
                case 0x478: parseEndEffectorParamFeedback(frame); break;
                case 0x47B: parseCollisionLevelResponse(frame); break;
                case 0x47C: parseJointAccelLimitFeedback(frame); break;
                case 0x47E: parseGripperTeachParamFeedback(frame); break;
                
                // High speed joint driver feedback (0x251-0x256)
                case 0x251: case 0x252: case 0x253: 
                case 0x254: case 0x255: case 0x256:
                    parseJointDriverHS(frame);
                    break;
                    
                // Low speed joint driver feedback (0x261-0x266)
                case 0x261: case 0x262: case 0x263: 
                case 0x264: case 0x265: case 0x266:
                    parseJointDriverLS(frame);
                    break;
                default:
                    // Handle ID offset cases (0x2Bx, 0x2Cx, etc.)
                    if ((frame.can_id >= 0x2B1 && frame.can_id <= 0x2B8) || 
                        (frame.can_id >= 0x2C1 && frame.can_id <= 0x2C8)) 
                    {
                        canid_t base_id = frame.can_id - (frame.can_id >= 0x2B1 ? 0x10 : 0x20);
                        switch (base_id) 
                        {
                            case 0x2A1: parseStateFeedback(frame); break;
                            case 0x2A2: parseCartesianPos1(frame); break;
                            case 0x2A3: parseCartesianPos2(frame); break;
                            case 0x2A4: parseCartesianPos3(frame); break;
                            case 0x2A5: parseJointAngles12(frame); break;
                            case 0x2A6: parseJointAngles34(frame); break;
                            case 0x2A7: parseJointAngles56(frame); break;
                            case 0x2A8: parseGripperFeedback(frame); break;
                        }
                    }
                    break;
            }
        }
        return received;
    }

    // Getters for feedback data
    ControlMode getControlMode() const 
    { 
        return static_cast<ControlMode>(state.control_mode); 
    }
    
    MechanicalState getMechanicalState() const 
    { 
        return static_cast<MechanicalState>(state.mechanical_state); 
    }
    
    MoveMode getMoveMode() const 
    { 
        return static_cast<MoveMode>(state.move_mode); 
    }
    
    T getGripperTravel() const 
    { 
        return gripper.travel_mm; 
    }
    
    T getJointAngle(int idx) const 
    {
        if (idx < 0 || idx > 5) return 0.0;
        return joint_angles[idx];
    }

    T getJointFeedbackAngle(int idx) const
    {
        if (idx < 0 || idx > 5) return 0.0;
        return joint_driver_hs[idx].position_rad;
    }
    
    T getCartesianPosition(int idx) const 
    {
        if (idx < 0 || idx > 5) return 0.0;
        return cartesian_pos[idx];
    }

    // Fault bit accessors
    bool isJointCommError(int idx) const 
    {
        if (idx < 0 || idx > 5) return false;
        return state.fault_bits.joint_comm_error[idx];
    }
    
    bool isJointAngleLimitExceeded(int idx) const 
    {
        if (idx < 0 || idx > 5) return false;
        return state.fault_bits.joint_angle_limit_exceeded[idx];
    }

    bool isJointVoltageLow(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.voltage_low;
    }

    bool isJointOverTemp(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.motor_over_temp;
    }

    bool isJointDriverOverCurrent(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.driver_over_current;
    }

    bool isJointDriverOverTemp(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.driver_over_temp;
    }

    bool isJointInCollisionProtection(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.collision_protection;
    }

    bool isJointDriverError(int idx) const
    {
        if (idx < 0 || idx > 5) return false;
        return joint_driver_ls[idx].bits.driver_error;
    }

    bool isJointEnabled(int idx) const
    {
        return joint_driver_ls[idx].bits.enabled;
    }

    bool isJointInStallProtection(int idx) const
    {
        return joint_driver_ls[idx].bits.stall_protection;
    }

    // Gripper status accessors
    bool isGripperVoltageLow() const 
    { 
        return gripper.bits.voltage_low; 
    }
    
    bool isGripperMotorOverTemp() const 
    { 
        return gripper.bits.motor_over_temp; 
    }
    
    bool isGripperDriverOverCurrent() const 
    { 
        return gripper.bits.driver_over_current; 
    }
    
    bool isGripperDriverOverTemp() const 
    { 
        return gripper.bits.driver_over_temp; 
    }
    
    bool isGripperSensorError() const 
    { 
        return gripper.bits.sensor_error; 
    }
    
    bool isGripperDriverError() const 
    { 
        return gripper.bits.driver_error; 
    }
    
    bool isGripperEnabled() const 
    { 
        return gripper.bits.enabled; 
    }
    
    bool isGripperZeroed() const 
    { 
        return gripper.bits.zeroed; 
    }

private:
    void processExceptions()
    {
        for ( int i=0 ; i<6 ; i++ )
        {
            if ( isJointCommError(i) )
                LOG_ERROR("interface {} joint {} communication error.", can_interface_, i);
            if ( isJointAngleLimitExceeded(i) )
                LOG_ERROR("interface {} joint {} exceeds limit.", can_interface_, i);
            if ( isJointVoltageLow(i) )
                LOG_ERROR("interface {} joint {} voltage low.", can_interface_, i);
            if ( isJointOverTemp(i) )
                LOG_ERROR("interface {} joint {} over temperature.", can_interface_, i);
            if ( isJointDriverOverCurrent(i) )
                LOG_ERROR("interface {} joint {} driver over current.", can_interface_, i);
            if ( isJointDriverOverTemp(i) )
                LOG_ERROR("interface {} joint {} driver over temperature.", can_interface_, i);
            if ( isJointInCollisionProtection(i) )
                LOG_ERROR("interface {} joint {} is in collision protection.", can_interface_, i);
            if ( isJointInStallProtection(i) )
                LOG_ERROR("interface {} joint {} is in stall protection.", can_interface_, i);
            if ( isGripperVoltageLow() )
                LOG_ERROR("interface {} gripper voltage low.", can_interface_, i);
            if ( isGripperMotorOverTemp() )
                LOG_ERROR("interface {} gripper motor over temperature.", can_interface_, i);
            if ( isGripperDriverOverCurrent() )
                LOG_ERROR("interface {} gripper driver over current.", can_interface_, i);
            if ( isGripperDriverOverTemp() )
                LOG_ERROR("interface {} gripper driver over temperature.", can_interface_, i);
            if ( isGripperSensorError() )
                LOG_ERROR("interface {} gripper sensor error.", can_interface_, i);
            if ( isGripperDriverError() )
                LOG_ERROR("interface {} gripper driver error.", can_interface_, i);
        }
    }

    /**
     * @brief Send a CAN frame using SocketCAN.
     * @param frame The CAN frame to send.
     * @return true if successful.
     */
    bool sendCanFrame(const struct can_frame& frame) 
    {
        if (can_socket_ < 0) 
        {
            LOG_ERROR("CAN socket not initialized");
            return false;
        }

        ssize_t bytes_sent = write(can_socket_, &frame, sizeof(struct can_frame));
        if (bytes_sent != sizeof(struct can_frame)) 
        {
            LOG_ERROR("Failed to send CAN frame, bytes_sent={}", bytes_sent);
            return false;
        }

        return true;
    }

    /**
     * @brief Receive a CAN frame using SocketCAN.
     * @param frame Reference to store received frame.
     * @return true if frame received, false otherwise.
     */
    bool receiveCanFrame(struct can_frame& frame) 
    {
        if (can_socket_ < 0) 
        {
            return false;
        }

        ssize_t bytes_read = read(can_socket_, &frame, sizeof(struct can_frame));
        
        if (bytes_read <= 0) 
        {
            return false;  // No data or error
        }

        return true;
    }

    // Complete parser implementations
    void parseStateFeedback(const struct can_frame& frame) 
    {
        state.control_mode = frame.data[0];
        state.mechanical_state = frame.data[1];
        state.move_mode = frame.data[2];
        state.teaching_state = frame.data[3];
        state.motion_state = frame.data[4];
        state.trajectory_index = frame.data[5];
        state.fault_code = (frame.data[7] << 8) | frame.data[6];

        // Parse fault bits from byte 6 and 7
        uint8_t byte6 = frame.data[6];
        uint8_t byte7 = frame.data[7];
        
        state.fault_bits.joint_comm_error[0] = (byte7 >> 0) & 0x01;
        state.fault_bits.joint_comm_error[1] = (byte7 >> 1) & 0x01;
        state.fault_bits.joint_comm_error[2] = (byte7 >> 2) & 0x01;
        state.fault_bits.joint_comm_error[3] = (byte7 >> 3) & 0x01;
        state.fault_bits.joint_comm_error[4] = (byte7 >> 4) & 0x01;
        state.fault_bits.joint_comm_error[5] = (byte7 >> 5) & 0x01;

        state.fault_bits.joint_angle_limit_exceeded[0] = (byte6 >> 0) & 0x01;
        state.fault_bits.joint_angle_limit_exceeded[1] = (byte6 >> 1) & 0x01;
        state.fault_bits.joint_angle_limit_exceeded[2] = (byte6 >> 2) & 0x01;
        state.fault_bits.joint_angle_limit_exceeded[3] = (byte6 >> 3) & 0x01;
        state.fault_bits.joint_angle_limit_exceeded[4] = (byte6 >> 4) & 0x01;
        state.fault_bits.joint_angle_limit_exceeded[5] = (byte6 >> 5) & 0x01;
    }

    void parseCartesianPos1(const struct can_frame& frame) 
    {
        int32_t x = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t y = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        cartesian_pos[0] = x / 1000.0;  // mm
        cartesian_pos[1] = y / 1000.0;
    }

    void parseCartesianPos2(const struct can_frame& frame) 
    {
        int32_t z = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t rx = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        cartesian_pos[2] = z / 1000.0;
        cartesian_pos[3] = rx / 1000.0;  // degrees
    }

    void parseCartesianPos3(const struct can_frame& frame) 
    {
        int32_t ry = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t rz = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        cartesian_pos[4] = ry / 1000.0;
        cartesian_pos[5] = rz / 1000.0;
    }

    void parseJointAngles12(const struct can_frame& frame) 
    {
        int32_t j1 = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t j2 = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        joint_angles[0] = j1 / 1000.0;
        joint_angles[1] = j2 / 1000.0;
    }

    void parseJointAngles34(const struct can_frame& frame) 
    {
        int32_t j3 = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t j4 = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        joint_angles[2] = j3 / 1000.0;
        joint_angles[3] = j4 / 1000.0;
    }

    void parseJointAngles56(const struct can_frame& frame) 
    {
        int32_t j5 = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int32_t j6 = (frame.data[4] << 24) | (frame.data[5] << 16) | (frame.data[6] << 8) | frame.data[7];
        joint_angles[4] = j5 / 1000.0;
        joint_angles[5] = j6 / 1000.0;
    }

    void parseGripperFeedback(const struct can_frame& frame) 
    {
        int32_t travel = (frame.data[0] << 24) | (frame.data[1] << 16) | (frame.data[2] << 8) | frame.data[3];
        int16_t torque = (frame.data[4] << 8) | frame.data[5];
        gripper.travel_mm = travel / 1000.0;
        gripper.torque_nm = torque / 1000.0;
        gripper.status = frame.data[6];

        // Parse status bits
        uint8_t status = frame.data[6];
        gripper.bits.voltage_low = (status >> 0) & 0x01;
        gripper.bits.motor_over_temp = (status >> 1) & 0x01;
        gripper.bits.driver_over_current = (status >> 2) & 0x01;
        gripper.bits.driver_over_temp = (status >> 3) & 0x01;
        gripper.bits.sensor_error = (status >> 4) & 0x01;
        gripper.bits.driver_error = (status >> 5) & 0x01;
        gripper.bits.enabled = (status >> 6) & 0x01;
        gripper.bits.zeroed = (status >> 7) & 0x01;
    }

    void parseJointLimitFeedback(const struct can_frame& frame) 
    {
        uint8_t joint_id = frame.data[0];
        if (joint_id < 1 || joint_id > 6) return;
        
        int16_t max_angle = (frame.data[1] << 8) | frame.data[2];
        int16_t min_angle = (frame.data[3] << 8) | frame.data[4];
        uint16_t max_speed = (frame.data[5] << 8) | frame.data[6];
        
        // Values are in 0.1° and 0.01rad/s
        // Store or process as needed
        (void)max_angle; (void)min_angle; (void)max_speed;
    }

    void parseSetResponse(const struct can_frame& frame) 
    {
        uint8_t cmd = frame.data[0];
        if (cmd == 0x75 && frame.data[1] == 0x01) 
        {
            // Joint zero set success
        }
        // Handle trajectory point responses, etc.
        (void)frame;
    }

    void parseEndEffectorParamFeedback(const struct can_frame& frame) 
    {
        uint16_t max_linear_speed = (frame.data[0] << 8) | frame.data[1];  // 0.001 m/s
        uint16_t max_angular_speed = (frame.data[2] << 8) | frame.data[3]; // 0.001 rad/s
        uint16_t max_linear_accel = (frame.data[4] << 8) | frame.data[5];  // 0.001 m/s^2
        uint16_t max_angular_accel = (frame.data[6] << 8) | frame.data[7]; // 0.001 rad/s^2
        
        (void)max_linear_speed; (void)max_angular_speed;
        (void)max_linear_accel; (void)max_angular_accel;
    }

    void parseCollisionLevelResponse(const struct can_frame& frame) 
    {
        // Update local copy if needed
        for (int i = 0; i < 6; i++) 
        {
            (void)frame.data[i]; // collision level for joint i+1
        }
    }

    void parseJointAccelLimitFeedback(const struct can_frame& frame) 
    {
        uint8_t joint_id = frame.data[0];
        if (joint_id < 1 || joint_id > 6) return;
        
        uint16_t max_accel = (frame.data[1] << 8) | frame.data[2];  // 0.001 rad/s^2
        
        (void)max_accel;
    }

    void parseGripperTeachParamFeedback(const struct can_frame& frame) 
    {
        uint8_t travel_scale = frame.data[0];   // 100-200%
        uint8_t max_travel = frame.data[1];     // mm
        uint8_t friction = frame.data[2];       // 1-10
        
        (void)travel_scale; (void)max_travel; (void)friction;
    }

    void parseJointDriverHS(const struct can_frame& frame) 
    {
        canid_t id = frame.can_id;
        if (id < 0x251 || id > 0x256) return;
        int joint_idx = id - 0x251;  // 0-5

        int16_t speed_raw = (frame.data[0] << 8) | frame.data[1];
        uint16_t current_raw = (frame.data[2] << 8) | frame.data[3];
        int32_t pos_raw = (frame.data[4] << 24) | (frame.data[5] << 16) | 
                         (frame.data[6] << 8) | frame.data[7];

        joint_driver_hs[joint_idx].speed_rad_per_sec = speed_raw / 1000.0;
        joint_driver_hs[joint_idx].current_a = current_raw / 1000.0;
        joint_driver_hs[joint_idx].position_rad = static_cast<T>(pos_raw) / 1000.0;
    }

    void parseJointDriverLS(const struct can_frame& frame) 
    {
        canid_t id = frame.can_id;
        if (id < 0x261 || id > 0x266) return;
        int joint_idx = id - 0x261;  // 0-5

        uint16_t voltage_raw = (frame.data[0] << 8) | frame.data[1];
        int16_t driver_temp_raw = (frame.data[2] << 8) | frame.data[3];
        int8_t motor_temp_raw = frame.data[4];
        uint16_t bus_current_raw = (frame.data[6] << 8) | frame.data[7];
        uint8_t status = frame.data[5];

        joint_driver_ls[joint_idx].voltage_v = voltage_raw / 10.0;
        joint_driver_ls[joint_idx].driver_temp_c = driver_temp_raw / 1.0;
        joint_driver_ls[joint_idx].motor_temp_c = motor_temp_raw;
        joint_driver_ls[joint_idx].bus_current_a = bus_current_raw / 1000.0;
        joint_driver_ls[joint_idx].driver_status = status;

        // Parse status bits
        auto& bits = joint_driver_ls[joint_idx].bits;
        bits.voltage_low = (status >> 0) & 0x01;
        bits.motor_over_temp = (status >> 1) & 0x01;
        bits.driver_over_current = (status >> 2) & 0x01;
        bits.driver_over_temp = (status >> 3) & 0x01;
        bits.collision_protection = (status >> 4) & 0x01;
        bits.driver_error = (status >> 5) & 0x01;
        bits.enabled = !((status >> 6) & 0x01);  // Inverted: 0=enabled, 1=disabled
        bits.stall_protection = (status >> 7) & 0x01;
    }

    int16_t floating2int16(T x, T min, T max, uint8_t bits)
    {
        return static_cast<int16_t>((x-min)*(static_cast<T>((1<<bits)-1)/(max-min))); 
    };

    int8_t floating2int8(T x, T min, T max, uint8_t bits)
    {
        return static_cast<int8_t>((x-min)*(static_cast<T>((1<<bits)-1)/(max-min))); 
    };
};