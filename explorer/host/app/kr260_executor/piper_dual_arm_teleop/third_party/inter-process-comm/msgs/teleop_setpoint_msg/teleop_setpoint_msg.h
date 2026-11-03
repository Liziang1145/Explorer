// teleop_setpoint_msg —— AIPC→KR260 本地链路 v2 控制报文（适配《探路者全链路通信协议规范 v2.0》）
//
// 设计说明：
// - 规范 v2.0 的 CONTROL_SETPOINT（CBOR+64B头+WebRTC）止于 AIPC（车端 A）。
//   AIPC→KR260 属车内本地链路，本报文是其语义子集：字段含义、单位、模式编号与规范对齐，
//   传输仍为 UDP+固定二进制（KR260 侧无 CBOR 依赖）。
// - 与旧 whole_body_msg（0xFBFB, 78B）通过 2 字节帧头区分，可共存过渡。
// - 坐标系：目标位姿使用已登记的遥操作参考系（标定后 = 车体系/底座系），
//   不再含头显系原始量；scaleRightHandPose 的 1.1 缩放与 head_position_ 偏置
//   由 AIPC 按规范第 6 节「只应用一次」完成，KR260 不再重复缩放。
//
// 线格式（小端，固定偏移，memcpy 编解码；禁止直接 puts 结构体）：
//   [0]   u16  header = 0xFCFC
//   [2]   u8   version = 2
//   [3]   u8   base_mode   : 0 保持 / 1 位姿目标 / 2 速度目标（KR260 暂不执行，仅透传记录）
//   [4]   u8   left_mode   : 0 保持 / 1 末端位姿 / 2 关节位置
//   [5]   u8   right_mode  : 同左
//   [6]   u16  enable_mask : bit0 总使能 bit1 底盘 bit2 左臂 bit3 右臂 bit4 左夹爪 bit5 右夹爪
//   [8]   u32  seq             : 同一源递增；seq<=last_seen 的帧丢弃
//   [12]  u32  reference_revision : 遥操作标定版本；与本地配置不一致时拒绝并记录
//   [16]  u32  input_state   : bit0 头显跟踪有效 bit1 左手有效 bit2 右手有效 bit3 按住控制 bit4 应用前台
//   [20]  u64  sample_time_ns: 输入采样时间（AIPC 单调时钟），供命令年龄/TTL 估计
//   [28]  f32[7] left_target  : pos xyz + quat xyzw（left_mode=1 时有效）
//   [56]  f32[7] right_target
//   [84]  f32[6] left_joint_target  : rad（left_mode=2 时有效）
//   [108] f32[6] right_joint_target
//   [132] f32 left_gripper  : 归一化开口 [0,1]，1=全开（enable_mask bit4 置位才执行）
//   [136] f32 right_gripper : 同上（bit5）
//   [140] u16 crc16_kermit  : 覆盖字节 [0,140)
// 总长 142 字节。

#pragma once
#include <array>
#include <cstdint>

struct teleop_setpoint_msg {
  using vec3 = std::array<float, 3>;
  using quat = std::array<float, 4>;
  using joints = std::array<float, 6>;

  uint8_t base_mode = 0, left_mode = 0, right_mode = 0;
  uint16_t enable_mask = 0;
  uint32_t seq = 0;
  uint32_t reference_revision = 0;
  uint32_t input_state = 0;
  uint64_t sample_time_ns = 0;

  vec3 left_target_pos{0,0,0};
  quat left_target_quat{0,0,0,1};
  vec3 right_target_pos{0,0,0};
  quat right_target_quat{0,0,0,1};
  joints left_joint_target{0,0,0,0,0,0};
  joints right_joint_target{0,0,0,0,0,0};
  float left_gripper = 1.0f;   // 归一化开口，默认全开
  float right_gripper = 1.0f;
};
