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
#include "nav_state_msg.h"

struct NavStateSender {
  using DataType                         = nav_state_msg;
  static constexpr uint8_t parser_type   = ParserType::Sender;
  static constexpr uint16_t header       = 0xDCDC;
  static constexpr size_t length         = 54;
  static constexpr std::string_view name = "nav_state_sender";

  static inline void Process(const DataType& in, std::span<std::byte>& out) {
    constexpr float m_PI = 3.14159265358979323846f;
    uint32_t tmp_32bits;
    memcpy(&out[0], &header, sizeof(uint16_t));
    memcpy(&out[2], &in.mask, sizeof(uint16_t));

    memcpy(&out[4], &in.cnt, sizeof(uint32_t));
    memcpy(&out[8], &in.time, sizeof(uint64_t));
    // base pos
    memcpy(&out[16], in.base_pos.data(), sizeof(float) * 3);
    tmp_32bits = EncodeQuaternion<float>(in.base_quat.data());
    memcpy(&out[28], &tmp_32bits, sizeof(uint32_t));
    // left joints
    tmp_32bits = Encode3D<float, 10>(in.left_joints[0], in.left_joints[1], in.left_joints[2], m_PI);
    memcpy(&out[32], &tmp_32bits, sizeof(uint32_t));
    tmp_32bits = Encode3D<float, 10>(in.left_joints[3], in.left_joints[4], in.left_joints[5], m_PI);
    memcpy(&out[36], &tmp_32bits, sizeof(uint32_t));
    // right joints
    tmp_32bits = Encode3D<float, 10>(in.right_joints[0], in.right_joints[1], in.right_joints[2], m_PI);
    memcpy(&out[40], &tmp_32bits, sizeof(uint32_t));
    tmp_32bits = Encode3D<float, 10>(in.right_joints[3], in.right_joints[4], in.right_joints[5], m_PI);
    memcpy(&out[44], &tmp_32bits, sizeof(uint32_t));
    // force feedback
    tmp_32bits = Encode2D<float, 16>(in.left_force, in.right_force);
    memcpy(&out[48], &tmp_32bits, sizeof(uint32_t));
    // CRC
    uint16_t crc = CRC::CalculateBits(out.data(), 52, CRC::CRC_16_KERMIT());
    memcpy(&out[52], &crc, sizeof(uint16_t));
    // total 54 bytes
    return;
  }
};