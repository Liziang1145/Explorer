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

#include <Eigen/Dense>
#include <utility>
#include <type_traits>
#include <concepts>
#include "base_type.hpp"


struct FullbodyCmd
{
    // mask explanation
    // enable: 1
    // disable: 0
    // Control Enable | base control | left hand control | right hand control | base vel valid | left hand vel valid | right hand vel valid | padding
    uint8_t header = 0xFB;        // 0XFB
    uint8_t mask;                 //
    uint32_t cnt;                 // packet count
    uint64_t time;                // timestamp unit: ns
    float base_x, base_y, base_z; // global position of baselink in FLU coordinate
    uint32_t left_hand_pos;       // position of left hand relative to base in FLU coordinate   10-bit compressed
    uint32_t right_hand_pos;      // position of right hand relative to base in FLU coordinate  10-bit compressed

    // uint64_t rotation_upper; // containing 3 quaternion:
    // uint64_t rotation_lower; // rotation of head, right hand and left hand

    float base_quat[4]; // quaternion of head
    float left_hand_quat[4];  // quaternion of left hand
    float right_hand_quat[4]; // quaternion of right hand

    uint32_t base_vel;   // relative velocity of base in FLU coordinate                         10-bit compressed
    uint32_t base_omega; // relative angular velocity of base in FLU coordinate                 10-bit compressed

    uint32_t left_hand_vel;    // relative velocity of left hand in FLU coordinate              10-bit compressed
    uint32_t right_hand_vel;   // relative velocity of right hand in FLU coordinate             10-bit compressed
    uint32_t left_hand_omega;  // relative angular velocity of left hand in FLU coordinate      10-bit compressed
    uint32_t right_hand_omega; // relative angular velocity of right hand in FLU coordinate     10-bit compressed
    uint16_t left_gripper_ctrl; // left gripper control
    uint16_t right_gripper_ctrl; // right gripper control
    uint16_t crc_bits;         // 16-bit KERMIT CRC

    //112bytes
};


//! This struct is just for clarification, Do not use this in coding
// struct FullbodyCmd
// {
//     // mask explanation
//     // enable: 1
//     // disable: 0
//     // Control Enable | base control | left hand control | right hand control | base vel valid | left hand vel valid | right hand vel valid | padding
//     uint8_t header = 0xFB;        // 0XFB
//     uint8_t mask;                 //
//     uint32_t cnt;                 // packet count
//     uint64_t time;                // timestamp unit: ns
//     float base_x, base_y, base_z; // global position of baselink in FLU coordinate
//     uint32_t left_hand_pos;       // position of left hand relative to base in FLU coordinate   10-bit compressed
//     uint32_t right_hand_pos;      // position of right hand relative to base in FLU coordinate  10-bit compressed

//     uint64_t rotation_upper; // containing 3 quaternion:
//     uint64_t rotation_lower; // rotation of head, right hand and left hand

//     uint32_t base_vel;   // relative velocity of base in FLU coordinate                         10-bit compressed
//     uint32_t base_omega; // relative angular velocity of base in FLU coordinate                 10-bit compressed

//     uint32_t left_hand_vel;    // relative velocity of left hand in FLU coordinate              10-bit compressed
//     uint32_t right_hand_vel;   // relative velocity of right hand in FLU coordinate             10-bit compressed
//     uint32_t left_hand_omega;  // relative angular velocity of left hand in FLU coordinate      10-bit compressed
//     uint32_t right_hand_omega; // relative angular velocity of right hand in FLU coordinate     10-bit compressed

//     uint32_t grip;     // left hand and right hand
//     uint16_t crc_bits; // 16-bit KERMIT CRC

//     // Total 76 Bytes
// };

struct FullbodyState
{
    // mask explanation
    // enable: 1
    // disable: 0
    // Control Enable | base control | left hand control | right hand control | base vel valid | left hand vel valid | right hand vel valid | padding
    uint8_t mask;                   //
    uint32_t cnt;                   // packet count
    uint64_t time;                  // timestamp unit: ns
    Eigen::Vector3f base_pos;       // global position of baselink in FLU coordinate
    Eigen::Vector3f left_hand_pos;  // position of left hand relative to base in FLU coordinate
    Eigen::Vector3f right_hand_pos; // position of right hand relative to base in FLU coordinate

    Eigen::Quaternionf base_quat;       //
    Eigen::Quaternionf left_hand_quat;  //
    Eigen::Quaternionf right_hand_quat; //

    Eigen::Vector3f base_lin_vel; // relative velocity of base in FLU coordinate
    Eigen::Vector3f base_ang_vel; // relative angular velocity of base in FLU coordinate

    Eigen::Vector3f left_hand_lin_vel;  // relative velocity of left hand in FLU coordinate
    Eigen::Vector3f right_hand_lin_vel; // relative velocity of right hand in FLU coordinate
    Eigen::Vector3f left_hand_ang_vel;  // relative angular velocity of left hand in FLU coordinate
    Eigen::Vector3f right_hand_ang_vel; // relative angular velocity of right hand in FLU coordinate
    float left_input, right_input;      // left hand and right hand
};

struct MapInfo
{
    std::shared_ptr<AlignedVector<uint64_t>> points_resource;
    std::shared_ptr<AlignedVector<uint32_t>> colors_resource;
    std::shared_ptr<AlignedVector<uint32_t>> normals_resource;

    size_t size;
    size_t offset; // carry some extra infomation
};

struct PoseInfo
{
    Eigen::Vector4f position;
    Eigen::Quaternionf orientation;
};

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto EncodeFloating(const ScalarType fp, const ScalarType maxAbs = 1.0)
{
    using UnsignedType = std::conditional_t<(Bits > 32), uint64_t, uint32_t>;
    UnsignedType fp_enc = static_cast<UnsignedType>((fp + maxAbs) / (2.0 * maxAbs) * ((UnsignedType(1) << Bits) - 1) + 0.5);
    return fp_enc;
}

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto DecodeFloating(const uint32_t fp_enc, const ScalarType maxAbs = 1.0)
{
    constexpr uint32_t maxInt = (uint32_t(1) << Bits) - 1;
    ScalarType fp = static_cast<ScalarType>(fp_enc & maxInt) / maxInt * (2.0 * maxAbs) - maxAbs;
    return fp;
}

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto Encode2D(const ScalarType x, const ScalarType y, const ScalarType maxAbs = 1.0)
{
    using UnsignedType = std::conditional_t<(Bits * 2 > 32), uint64_t, uint32_t>;
    auto x_enc = EncodeFloating<ScalarType, Bits>(x, maxAbs);
    auto y_enc = EncodeFloating<ScalarType, Bits>(y, maxAbs);
    UnsignedType fp_enc = y_enc | (x_enc << Bits);
    return fp_enc;
}

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto Encode3D(const ScalarType x, const ScalarType y, const ScalarType z, const ScalarType maxAbs = 1.0)
{
    using UnsignedType = std::conditional_t<(Bits * 3 > 32), uint64_t, uint32_t>;
    auto x_enc = EncodeFloating<ScalarType, Bits>(x, maxAbs);
    auto y_enc = EncodeFloating<ScalarType, Bits>(y, maxAbs);
    auto z_enc = EncodeFloating<ScalarType, Bits>(z, maxAbs);
    UnsignedType fp_enc = z_enc | (y_enc << Bits) | (x_enc << (2 * Bits));
    return fp_enc;
}

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto Decode2D(const std::conditional_t<(Bits * 2 > 32), uint64_t, uint32_t> fp_enc, const ScalarType maxAbs = 1.0)
{
    ScalarType x = DecodeFloating<ScalarType, Bits>(fp_enc >> (1 * Bits), maxAbs);
    ScalarType y = DecodeFloating<ScalarType, Bits>(fp_enc, maxAbs);
    return std::make_tuple(x, y);
}

template <typename ScalarType, int Bits>
    requires(Bits > 0 && Bits <= 21)
static inline auto Decode3D(const std::conditional_t<(Bits * 3 > 32), uint64_t, uint32_t> fp_enc, const ScalarType maxAbs = 1.0)
{
    ScalarType x = DecodeFloating<ScalarType, Bits>(fp_enc >> (2 * Bits), maxAbs);
    ScalarType y = DecodeFloating<ScalarType, Bits>(fp_enc >> (1 * Bits), maxAbs);
    ScalarType z = DecodeFloating<ScalarType, Bits>(fp_enc, maxAbs);
    return std::make_tuple(x, y, z);
}

// template <typename ScalarType>
// static inline auto EncodeQuaternion(const Eigen::Quaternion<ScalarType> &q)
// {
//     auto copy_q = q;
//     Eigen::Index index;
//     copy_q.coeffs().cwiseAbs().maxCoeff(&index);
//     if (copy_q.coeffs()(index) < 0)
//         copy_q.coeffs() *= -1;

//     for (int i = 0; i < 4; i++)
//     {
//         if (i == index)
//             continue;
        
        
//     }
// }

template <typename ScalarType>
static inline auto EncodeQuaternions(const Eigen::Quaternion<ScalarType> &q1,
                                     const Eigen::Quaternion<ScalarType> &q2 = Eigen::Quaternion<ScalarType>::Identity(),
                                     const Eigen::Quaternion<ScalarType> &q3 = Eigen::Quaternion<ScalarType>::Identity())
{
    auto encodeQuat = [](const Eigen::Quaternion<ScalarType> &_q) -> uint64_t
    {
        using namespace std;
        uint8_t mark = 3;
        auto q = _q;
        Eigen::Index index;
        q.coeffs().cwiseAbs().maxCoeff(&index);
        if (q.coeffs()(index) < 0)
            q.coeffs() *= -1;
        q.normalize();
        ScalarType min = abs(q.w());
        ScalarType fp1, fp2, fp3;
        fp1 = q.x();
        fp2 = q.y();
        fp3 = q.z();
        if (abs(q.x()) < min)
        {
            min = abs(q.x());
            mark = 0;
            fp1 = q.y();
            fp2 = q.z();
            fp3 = q.w();
        }
        if (abs(q.y()) < min)
        {
            min = abs(q.y());
            mark = 1;
            fp1 = q.x();
            fp2 = q.z();
            fp3 = q.w();
        }
        if (abs(q.z()) < min)
        {
            min = abs(q.z());
            mark = 2;
            fp1 = q.x();
            fp2 = q.y();
            fp3 = q.w();
        }
        if (min > q.coeffs()(mark))
        {
            mark += 4;
        }

        auto fp1_enc = EncodeFloating<ScalarType, 13>(fp1);
        auto fp2_enc = EncodeFloating<ScalarType, 13>(fp2);
        auto fp3_enc = EncodeFloating<ScalarType, 13>(fp3);

        uint64_t result = uint64_t(0);

        result |= (uint64_t(mark) << 61);
        result |= (uint64_t(fp1_enc) << 48);
        result |= (uint64_t(fp2_enc) << 35);
        result |= (uint64_t(fp3_enc) << 22);
        return result;
    };

    auto q1_enc = encodeQuat(q1);
    auto q2_enc = encodeQuat(q2);
    auto q3_enc = encodeQuat(q3);

    uint64_t upper_bits = q1_enc | (q2_enc >> 42);
    uint64_t lower_bits = (q2_enc << 22) | (q3_enc >> 20);

    return std::make_pair(upper_bits, lower_bits);
}

template <typename ScalarType>
static inline auto DecodeQuaternions(const uint64_t upper_bits, const uint64_t lower_bits)
{
    auto decodeQuat = [](const uint64_t bin) -> Eigen::Quaternion<ScalarType>
    {
        uint8_t mark = (bin >> 61) & 0x7;
        ScalarType fp1, fp2, fp3;
        fp1 = DecodeFloating<ScalarType, 13>((bin >> 48) & 0x1FFF);
        fp2 = DecodeFloating<ScalarType, 13>((bin >> 35) & 0x1FFF);
        fp3 = DecodeFloating<ScalarType, 13>((bin >> 22) & 0x1FFF);
        ScalarType fp4_double = 1.0 - fp1 * fp1 - fp2 * fp2 - fp3 * fp3;
        ScalarType fp4 = fp4_double <= 0 ? 0 : sqrt(fp4_double);
        Eigen::Quaternion<ScalarType> result;
        if ((mark & 0x03) == 0)
        {
            result.x() = fp4;
            result.y() = fp1;
            result.z() = fp2;
            result.w() = fp3;
        }
        else if ((mark & 0x03) == 1)
        {
            result.x() = fp1;
            result.y() = fp4;
            result.z() = fp2;
            result.w() = fp3;
        }
        else if ((mark & 0x03) == 2)
        {
            result.x() = fp1;
            result.y() = fp2;
            result.z() = fp4;
            result.w() = fp3;
        }
        else if ((mark & 0x03) == 3)
        {
            result.x() = fp1;
            result.y() = fp2;
            result.z() = fp3;
            result.w() = fp4;
        }
        else if ((mark & 0x03) == 4)
        {
            result.x() = -fp4;
            result.y() = fp1;
            result.z() = fp2;
            result.w() = fp3;
        }
        else if ((mark & 0x03) == 5)
        {
            result.x() = fp1;
            result.y() = -fp4;
            result.z() = fp2;
            result.w() = fp3;
        }
        else if ((mark & 0x03) == 6)
        {
            result.x() = fp1;
            result.y() = fp2;
            result.z() = -fp4;
            result.w() = fp3;
        }
        else
        {
            result.x() = fp1;
            result.y() = fp2;
            result.z() = fp3;
            result.w() = -fp4;
        }
        return result;
    };

    auto q1 = decodeQuat(upper_bits);
    auto q2 = decodeQuat((upper_bits << 42) | (lower_bits >> 22));
    auto q3 = decodeQuat(lower_bits << 20);

    return std::make_tuple(q1, q2, q3);
}