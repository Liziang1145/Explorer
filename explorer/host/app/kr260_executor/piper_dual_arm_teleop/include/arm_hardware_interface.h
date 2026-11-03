/**
 * @file arm_hardware_interface.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm communication and packet parser.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ARM_HARDWARE_INTERFACE_H__
#define __ARM_HARDWARE_INTERFACE_H__

#include <thread>
#include <mutex>
#include <atomic>
#include <array>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <Eigen/Core>
#include <arm_model.h>
#include <arm_interface.h>

class ArmHardwareInterface final : public ArmInterface
{
public:
    ArmHardwareInterface();
    ~ArmHardwareInterface() = default;
    bool start(const char* left_arm_can_name, const char* right_arm_can_name);
    void stop();
    void setLeftJointControl(
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque) override;
    void setLeftGripperControl(const double& position, const double& torque) override;
    void setLeftMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation) override;
    void setRightJointControl(
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque) override;
    void setRightGripperControl(const double& position, const double& torque) override;
    void setRightMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation) override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointPosition() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointVelocity() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointAcceleration() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getLeftJointTorque() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointPosition() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointVelocity() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointAcceleration() override;
    const Eigen::Vector<double,ArmModel::num_dof_>& getRightJointTorque() override;

private:
    enum ArmControlMode
    {
        MODE_STANDBY = 0,
        MODE_CAN,
        MODE_TEACH,
        MODE_ETHERNET,
        MODE_WIFI,
        MODE_REMOTE,
        MODE_DUAL_TEACH,
        MODE_OFFLINE_TRAJECTORY
    };

    enum ArmStatus
    {
        STATUS_NORMAL,
        STATUS_EMERGENCY_STOP,
        STATUS_NO_SOLUTION,
        STATUS_SINGULAR,
        STATUS_OVER_POSITION_LIMIT,
        STATUS_JOINT_COMMUNICATION_ERROR,
        STATUS_JOINT_BRAKE_UNRELEASED,
        STATUS_SELF_COLLISION,
        STATUS_TEACH_OVERSPEED,
        STATUS_JOINT_EXCEPTION,
        STATUS_OTHER_EXCEPTION,
        STATUS_TEACH_RECORD,
        STATUS_TEACH_EXECUTE,
        STATUS_TEACH_SUSPEND,
        STATUS_NTC_OVER_TEMPERATURE,
        STATUS_RELEASE_RES_OVER_TEMPERATURE
    };

    enum MoveMode
    {
        MOVE_MODE_POSITION = 0,
        MOVE_MODE_JOINT,
        MOVE_MODE_LINEAR,
        MOVE_MODE_CIRCULAR,
        MOVE_MODE_MIT
    };

    enum TeachStatus
    {
        TEACH_STATE_OFF = 0,
        TEACH_STATE_START,
        TEACH_STATE_END,
        TEACH_STATE_EXECUTE,
        TEACH_STATE_SUSPEND,
        TEACH_STATE_RESUME,
        TEACH_STATE_TERMINATE,
        TEACH_STATE_TRAJ_BEGIN
    };

    enum MotionStatus
    {
        MOTION_REACH = 0,
        MOTION_NOT_REACH
    };

    enum ActuatorStatus
    {
        ACTUATOR_STATUS_LOW_VOLTAGE = 1<<0,
        ACTUATOR_STATUS_MOTOR_OVER_TEMPERATURE = 1<<1,
        ACTUATOR_STATUS_OVER_CURRENT = 1<<2,
        ACTUATOR_STATUS_OVER_TEMPERATURE = 1<<3,
        ACTUATOR_STATUS_COLLISION_PROTECT = 1<<4,
        ACTUATOR_STATUS_ERROR = 1<<5,
        ACTUATOR_STATUS_DISABLED = 1<<6,
        ACTUATOR_STATUS_LOCKED_ROTOR = 1<<7
    };

    /* runing flag */
    bool running_;

    /* which arm is physically connected (single-arm fallback) */
    bool left_arm_online_ = true;
    bool right_arm_online_ = true;

    /* CAN socket id */
    int left_can_socket_;
    int right_can_socket_;

    /* thread for CAN polling receiption */
    std::thread read_thread_;

    /* CAN socket mutex */
    std::mutex left_arm_can_mtx_;
    std::mutex right_arm_can_mtx_;
    
    std::mutex left_joints_mutex_;
    std::mutex right_joints_mutex_;

    std::array<float,ArmModel::num_dof_> left_arm_actuator_voltage_;
    std::array<int16_t,ArmModel::num_dof_> left_arm_actuator_temperature_;
    std::array<int8_t,ArmModel::num_dof_> left_arm_motor_temperature_;
    std::array<uint8_t,ArmModel::num_dof_> left_arm_actuator_status_;

    std::array<float,ArmModel::num_dof_> right_arm_actuator_voltage_;
    std::array<int16_t,ArmModel::num_dof_> right_arm_actuator_temperature_;
    std::array<int8_t,ArmModel::num_dof_> right_arm_motor_temperature_;
    std::array<uint8_t,ArmModel::num_dof_> right_arm_actuator_status_;

    Eigen::Vector<double, ArmModel::num_dof_> left_actual_joint_pos_;
    Eigen::Vector<double, ArmModel::num_dof_> left_actual_joint_vel_;
    Eigen::Vector<double, ArmModel::num_dof_> left_actual_joint_acc_;
    Eigen::Vector<double, ArmModel::num_dof_> left_actual_joint_torq_;

    Eigen::Vector<double, ArmModel::num_dof_> right_actual_joint_pos_;
    Eigen::Vector<double, ArmModel::num_dof_> right_actual_joint_vel_;
    Eigen::Vector<double, ArmModel::num_dof_> right_actual_joint_acc_;
    Eigen::Vector<double, ArmModel::num_dof_> right_actual_joint_torq_;

    void parseCanFrame(const int can_socket, struct can_frame* can_frame);

    /**
     * @brief Send MIT protocol command to piper manipulator.
     * 
     * @param actuator_id from 0 to 5.
     * @param position position without joint limit bound. unit: rad.
     * @param velocity velocity without joint velocity bound. unit: rad/s.
     * @param kp 
     * @param kd 
     * @param torque 
     */
    void sendControlMessage(
        const int can_socket,
        const uint8_t actuator_id,
        const int16_t position,
        const int16_t velocity,
        const int16_t kp,
        const int16_t kd,
        const int8_t torque) const;
    void setMITMode(const int can_socket) const;
    void setJointPositionMode(const int can_socket) const;
    void setEndEffectorPoseMode(const int can_socket) const;
    void enableActuators(const int can_socket) const;
    void disableActuators(const int can_socket) const;
    void setActuatorControl(
        const int can_socket,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
        const Eigen::Vector<double,ArmModel::num_dof_>& joint_torque) const;
    void setActuatorPosition(const int can_socket, const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos) const;
    void setEndEffectorPose(const int can_socket, const Eigen::Vector3d& pos, const Eigen::Quaterniond& orientation) const;
    void setGripperCurrentAsZero(const int can_socket) const;
    void setGripperControl(const int can_socket, const double position, const double torque) const;
    void threadCanReceive();
    /* C12：按臂独立排空 CAN 接收队列（poll 之后调用，内部按 FIONREAD 批量读并校验帧长）。 */
    void drainCan(int socket_fd, std::mutex& mtx);
    // void threadCanTransmit();
};

#endif // __ARM_HARDWARE_INTERFACE_H__