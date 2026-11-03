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
// teleop_setpoint v2 发送封装（格式见 teleop_setpoint_msg.h 头注释）。

#pragma once

#include <cstdint>
#include <cstring>
#include <span>
#include <string_view>

#include "../common.hpp"
#include "../CRC.h"
#include "teleop_setpoint_msg.h"

struct TeleopSetpointSender {
  using DataType                         = teleop_setpoint_msg;
  static constexpr uint8_t parser_type   = ParserType::Sender;
  static constexpr uint16_t header       = 0xFCFC;
  static constexpr size_t length         = 142;
  static constexpr std::string_view name = "teleop_setpoint_sender";

  static inline bool Process(std::span<std::byte>& out, const DataType& in) {
    memset(out.data(), 0, length);
    uint16_t hdr = header;
    uint8_t ver = 2;
    memcpy(&out[0], &hdr, sizeof(uint16_t));
    memcpy(&out[2], &ver, 1);
    memcpy(&out[3], &in.base_mode, 1);
    memcpy(&out[4], &in.left_mode, 1);
    memcpy(&out[5], &in.right_mode, 1);
    memcpy(&out[6], &in.enable_mask, sizeof(uint16_t));
    memcpy(&out[8], &in.seq, sizeof(uint32_t));
    memcpy(&out[12], &in.reference_revision, sizeof(uint32_t));
    memcpy(&out[16], &in.input_state, sizeof(uint32_t));
    memcpy(&out[20], &in.sample_time_ns, sizeof(uint64_t));
    memcpy(&out[28], in.left_target_pos.data(), sizeof(float)*3);
    memcpy(&out[40], in.left_target_quat.data(), sizeof(float)*4);
    memcpy(&out[56], in.right_target_pos.data(), sizeof(float)*3);
    memcpy(&out[68], in.right_target_quat.data(), sizeof(float)*4);
    memcpy(&out[84],  in.left_joint_target.data(),  sizeof(float)*6);
    memcpy(&out[108], in.right_joint_target.data(), sizeof(float)*6);
    memcpy(&out[132], &in.left_gripper, sizeof(float));
    memcpy(&out[136], &in.right_gripper, sizeof(float));
    uint16_t crc = CRC::Calculate(out.data(), 140, CRC::CRC_16_KERMIT());
    memcpy(&out[140], &crc, sizeof(uint16_t));
    return true;
  }
};
