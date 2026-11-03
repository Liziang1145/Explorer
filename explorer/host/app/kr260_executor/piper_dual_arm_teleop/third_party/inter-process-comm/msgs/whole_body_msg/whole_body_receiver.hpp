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

#pragma once

#include "../common.hpp"
#include "../compress_utils.hpp"
#include "../CRC.h"
#include "whole_body_msg.h"

struct WholeBodyReceiver {
  using DataType                         = whole_body_msg;
  static constexpr uint8_t parser_type   = ParserType::Receiver;
  static constexpr uint16_t header       = 0xFBFB;
  static constexpr size_t length         = 78;
  static constexpr std::string_view name = "whole_body_receiver";

  static inline bool Process(const std::span<std::byte>& in, DataType& out) {
    // crc check
    {
      uint16_t crc = CRC::CalculateBits(in.data(), 76, CRC::CRC_16_KERMIT());
      uint16_t crc_in;
      memcpy(&crc_in, &in[76], sizeof(uint16_t));
      if (crc != crc_in) return false;
    }

    memcpy(&out.mask, &in[2], sizeof(uint16_t));
    memcpy(&out.cnt, &in[4], sizeof(uint32_t));
    memcpy(&out.time, &in[8], sizeof(uint64_t));
    uint32_t tmp_32bits;
    // base pos
    memcpy(out.base_pos.data(), &in[16], sizeof(float) * 3);
    // left hand pos
    memcpy(&tmp_32bits, &in[28], sizeof(uint32_t));
    std::tie(out.left_hand_pos[0], out.left_hand_pos[1], out.left_hand_pos[2]) = Decode3D<float, 10>(tmp_32bits, 2.0);
    // right hand pos
    memcpy(&tmp_32bits, &in[32], sizeof(uint32_t));
    std::tie(out.right_hand_pos[0], out.right_hand_pos[1], out.right_hand_pos[2]) = Decode3D<float, 10>(tmp_32bits, 2.0);
    // base quaternion
    memcpy(&tmp_32bits, &in[36], sizeof(uint32_t));
    DecodeQuaternion<float>(tmp_32bits, out.base_quat.data());
    // left hand quaternion
    memcpy(&tmp_32bits, &in[40], sizeof(uint32_t));
    DecodeQuaternion<float>(tmp_32bits, out.left_hand_quat.data());
    // right hand quaternion
    memcpy(&tmp_32bits, &in[44], sizeof(uint32_t));
    DecodeQuaternion<float>(tmp_32bits, out.right_hand_quat.data());
    // base linear velocity
    memcpy(&tmp_32bits, &in[48], sizeof(uint32_t));
    std::tie(out.base_lin_vel[0], out.base_lin_vel[1], out.base_lin_vel[2]) = Decode3D<float, 10>(tmp_32bits, 3.0);
    // base angular velocity
    memcpy(&tmp_32bits, &in[52], sizeof(uint32_t));
    std::tie(out.base_ang_vel[0], out.base_ang_vel[1], out.base_ang_vel[2]) = Decode3D<float, 10>(tmp_32bits, 3.14);
    // left hand linear velocity
    memcpy(&tmp_32bits, &in[56], sizeof(uint32_t));
    std::tie(out.left_hand_lin_vel[0], out.left_hand_lin_vel[1], out.left_hand_lin_vel[2]) = Decode3D<float, 10>(tmp_32bits, 5.0);
    // right hand linear velocity
    memcpy(&tmp_32bits, &in[60], sizeof(uint32_t));
    std::tie(out.right_hand_lin_vel[0], out.right_hand_lin_vel[1], out.right_hand_lin_vel[2]) = Decode3D<float, 10>(tmp_32bits, 5.0);
    // left hand angular velocity
    memcpy(&tmp_32bits, &in[64], sizeof(uint32_t));
    std::tie(out.left_hand_ang_vel[0], out.left_hand_ang_vel[1], out.left_hand_ang_vel[2]) = Decode3D<float, 10>(tmp_32bits, 6.28);
    // right hand angular velocity
    memcpy(&tmp_32bits, &in[68], sizeof(uint32_t));
    std::tie(out.right_hand_ang_vel[0], out.right_hand_ang_vel[1], out.right_hand_ang_vel[2]) = Decode3D<float, 10>(tmp_32bits, 6.28);
    // grip gorce
    memcpy(&tmp_32bits, &in[72], sizeof(uint32_t));
    std::tie(out.left_grip, out.right_grip) = Decode2D<float, 16>(tmp_32bits);

    return true;
  }
};