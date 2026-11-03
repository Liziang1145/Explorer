#define M_PI 3.14159265358979323846
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <vector>
#include <mutex>
namespace Eigen { template<class T,int N> struct Vector { T a[N]{}; T& operator()(int i){return a[i];} T operator()(int i)const{return a[i];} }; }
namespace ArmModel { constexpr int num_dof_=6; }
struct can_frame { uint32_t can_id; uint8_t can_dlc; uint8_t data[8]; };
std::vector<can_frame> captured;
int write(int,const void* p,size_t n){captured.push_back(*static_cast<const can_frame*>(p));return int(n);}
constexpr int MOVE_MODE_JOINT=1;
class ArmHardwareInterface {public:
 int left_can_socket_=0,right_can_socket_=1; std::mutex left_joints_mutex_,right_joints_mutex_;
 void setLeftJointControl(const Eigen::Vector<double,6>&,const Eigen::Vector<double,6>&,const Eigen::Vector<double,6>&);
 void setRightJointControl(const Eigen::Vector<double,6>&,const Eigen::Vector<double,6>&,const Eigen::Vector<double,6>&);
 void setJointPositionMode(int)const;
 void setActuatorPosition(int,const Eigen::Vector<double,6>&)const;
};
void ArmHardwareInterface::setLeftJointControl(
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque)
{
    std::lock_guard<std::mutex> lock(this->left_joints_mutex_);
    if ( this->left_can_socket_ == -1 ) return;   // left arm offline
    /* 限位安全余量（同右臂，2026-10-16）：指令内收约 3°，防止贴限位触发驱动器保护锁存 */
    static const double MARGIN = 0.05;
    Eigen::Vector<double,ArmModel::num_dof_> hw_joint_pos = joint_pos;
    // 下限使用官方机械范围；上限保留 0.05 rad 安全余量。
    static const double LO[6] = {-2.618, 0.0, -2.967, -1.745, -1.22, -2.0944};
    static const double HI[6] = { 2.618, M_PI-MARGIN,  0.0-MARGIN,  1.745-MARGIN,  1.22-MARGIN,  2.0944-MARGIN};
    for ( int i=0 ; i<6 ; i++ )
        hw_joint_pos(i) = std::clamp(hw_joint_pos(i), LO[i], HI[i]);
    // setActuatorControl(this->left_can_socket_, joint_pos, joint_vel, joint_feedforward_torque);
    setJointPositionMode(this->left_can_socket_);
    setActuatorPosition(this->left_can_socket_, hw_joint_pos);
}

void ArmHardwareInterface::setRightJointControl(
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque)
{
    std::lock_guard<std::mutex> lock(this->right_joints_mutex_);
    if ( this->right_can_socket_ == -1 ) return;   // right arm offline
    /* J1 符号适配（2026-10-15 真机验证）：右臂固件 J1 正方向与 URDF 模型相反，
     * 在硬件边界取反，模型内部保持自洽。注意 tool.cpp 直发原始 CAN，
     * 其 J1 方向与此处相反属预期。 */
    Eigen::Vector<double,ArmModel::num_dof_> hw_joint_pos = joint_pos;
    hw_joint_pos(0) = -hw_joint_pos(0);
    /* 限位安全余量（2026-10-16 抓包定位）：目标位姿把 J6 压到限位边界 -120°
     * 持续发力会触发驱动器限位保护锁存（状态字节 0xA4，全臂拒动只能断电重启）。
     * 指令统一内收 3°，永不贴边。J2/J3 单侧限位同理内收。 */
    static const double MARGIN = 0.05;  // rad ≈ 2.9°
    // 下限使用官方机械范围；上限保留 0.05 rad 安全余量。
    static const double LO[6] = {-2.618, 0.0, -2.967, -1.745, -1.22, -2.0944};
    static const double HI[6] = { 2.618, M_PI-MARGIN,  0.0-MARGIN,  1.745-MARGIN,  1.22-MARGIN,  2.0944-MARGIN};
    for ( int i=0 ; i<6 ; i++ )
        hw_joint_pos(i) = std::clamp(hw_joint_pos(i), LO[i], HI[i]);
    // setActuatorControl(this->right_can_socket_, joint_pos, joint_vel, joint_feedforward_torque);
    setJointPositionMode(this->right_can_socket_);
    setActuatorPosition(this->right_can_socket_, hw_joint_pos);
}

void ArmHardwareInterface::setJointPositionMode(const int can_socket) const
{
    struct can_frame frame;
    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x151;
    frame.can_dlc = 8;
    frame.data[0] = 0x01;   // CAN command mode.
    frame.data[1] = MOVE_MODE_JOINT; // Joint move mode.
    frame.data[2] = 100;    // Move rate.
    frame.data[3] = 0x00;   // Joint position control.
    write(can_socket, &frame, sizeof(struct can_frame));
}

void ArmHardwareInterface::setActuatorPosition(const int can_socket, const Eigen::Vector<double,6>& joint_pos) const
{
    struct can_frame frame;
    int32_t joint_pos_scaled;
    
    /* Set default joint position control mode. */
    setJointPositionMode(can_socket);

    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x155;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(joint_pos(0) * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(joint_pos(1) * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(can_socket, &frame, sizeof(struct can_frame));

    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x156;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(joint_pos(2) * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(joint_pos(3) * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(can_socket, &frame, sizeof(struct can_frame));

    memset(&frame, 0, sizeof(frame));
    frame.can_id = 0x157;
    frame.can_dlc = 8;
    joint_pos_scaled = static_cast<int32_t>(joint_pos(4) * 180.0 / M_PI * 1000.0);
    frame.data[0] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[1] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[2] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[3] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    joint_pos_scaled = static_cast<int32_t>(joint_pos(5) * 180.0 / M_PI * 1000.0);
    frame.data[4] = static_cast<uint8_t>(joint_pos_scaled >> 24);
    frame.data[5] = static_cast<uint8_t>(joint_pos_scaled >> 16);
    frame.data[6] = static_cast<uint8_t>(joint_pos_scaled >> 8);
    frame.data[7] = static_cast<uint8_t>(joint_pos_scaled & 0xFF);
    write(can_socket, &frame, sizeof(struct can_frame));
}

int main(){ ArmHardwareInterface a; Eigen::Vector<double,6> v,z; unsigned rng=0x26110201;
 for(int n=0;n<64;n++){ for(int j=0;j<6;j++){rng=rng*1664525u+1013904223u; v(j)=n==0?0.0:n==1?-10.0:n==2?10.0:(int32_t(rng)/2147483648.0)*4.0;}
 captured.clear(); if(n&1)a.setRightJointControl(v,z,z);else a.setLeftJointControl(v,z,z);
 if(captured.size()!=5)return 2;
 for(auto &f:captured){std::printf("%d %03x ",n,f.can_id);for(int j=0;j<8;j++)std::printf("%02x",f.data[j]);std::printf("\n");}
 }
}
