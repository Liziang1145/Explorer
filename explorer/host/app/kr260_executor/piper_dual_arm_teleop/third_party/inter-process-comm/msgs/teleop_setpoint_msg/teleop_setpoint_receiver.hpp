// Copyright 2025 Chuangye Liu <chuangyeliu0206@gmail.com>
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// teleop_setpoint v2 接收解析（格式见 teleop_setpoint_msg.h 头注释）。
// 注意：CRC 覆盖完整负载 [0,140)，与旧 whole_body 的「前 76 位」怪癖无关。

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <span>

#include "../common.hpp"
#include "../CRC.h"
#include "teleop_setpoint_msg.h"

struct TeleopSetpointReceiver {
  using DataType                         = teleop_setpoint_msg;
  static constexpr uint8_t parser_type   = ParserType::Receiver;
  static constexpr uint16_t header       = 0xFCFC;
  static constexpr size_t length         = 142;
  static constexpr std::string_view name = "teleop_setpoint_receiver";

  static inline bool Process(const std::span<std::byte>& in, DataType& out) {
    // CRC-16/KERMIT 覆盖 [0,140)，即全部字节减去末尾 CRC 自身
    uint16_t crc = CRC::Calculate(in.data(), 140, CRC::CRC_16_KERMIT());
    uint16_t crc_in;
    memcpy(&crc_in, &in[140], sizeof(uint16_t));
    if (crc != crc_in) return false;

    uint8_t version;
    memcpy(&version, &in[2], 1);
    if (version != 2) return false;

    memcpy(&out.base_mode,   &in[3], 1);
    memcpy(&out.left_mode,   &in[4], 1);
    memcpy(&out.right_mode,  &in[5], 1);
    memcpy(&out.enable_mask, &in[6], sizeof(uint16_t));
    memcpy(&out.seq,         &in[8], sizeof(uint32_t));
    memcpy(&out.reference_revision, &in[12], sizeof(uint32_t));
    memcpy(&out.input_state, &in[16], sizeof(uint32_t));
    memcpy(&out.sample_time_ns, &in[20], sizeof(uint64_t));

    memcpy(out.left_target_pos.data(),  &in[28], sizeof(float)*3);
    memcpy(out.left_target_quat.data(), &in[40], sizeof(float)*4);
    memcpy(out.right_target_pos.data(), &in[56], sizeof(float)*3);
    memcpy(out.right_target_quat.data(),&in[68], sizeof(float)*4);
    memcpy(out.left_joint_target.data(),  &in[84],  sizeof(float)*6);
    memcpy(out.right_joint_target.data(), &in[108], sizeof(float)*6);
    memcpy(&out.left_gripper,  &in[132], sizeof(float));
    memcpy(&out.right_gripper, &in[136], sizeof(float));

    // 基本合法性：拒绝 NaN/Inf（规范 5.4）与零四元数
    auto finite4 = [](const float* p, int n){ for(int i=0;i<n;i++) if(!std::isfinite(p[i])) return false; return true; };
    if ( !finite4(out.left_target_pos.data(),3) || !finite4(out.left_target_quat.data(),4) ) return false;
    if ( !finite4(out.right_target_pos.data(),3) || !finite4(out.right_target_quat.data(),4) ) return false;
    if ( !finite4(out.left_joint_target.data(),6) || !finite4(out.right_joint_target.data(),6) ) return false;
    if ( !std::isfinite(out.left_gripper) || !std::isfinite(out.right_gripper) ) return false;
    auto quatOk = [](const DataType::quat& q){
      float n = q[0]*q[0]+q[1]*q[1]+q[2]*q[2]+q[3]*q[3];
      return n > 0.5f && n < 2.0f;   // 范数偏差容差宽于规范 1e-3，归一化在使用处做
    };
    if ( !quatOk(out.left_target_quat) || !quatOk(out.right_target_quat) ) return false;

    return true;
  }
};
