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

#include <utility>
#include <type_traits>
#include <concepts>

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto EncodeFloating(const ScalarType fp, const ScalarType maxAbs = 1.0) {
  using UnsignedType  = std::conditional_t<(Bits > 32), uint64_t, uint32_t>;
  UnsignedType fp_enc = static_cast<UnsignedType>((fp + maxAbs) / (2.0 * maxAbs) * ((UnsignedType(1) << Bits) - 1) + 0.5);
  return fp_enc;
}

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto DecodeFloating(const uint32_t fp_enc, const ScalarType maxAbs = 1.0) {
  constexpr uint32_t maxInt = (uint32_t(1) << Bits) - 1;
  ScalarType fp             = static_cast<ScalarType>(fp_enc & maxInt) / maxInt * (2.0 * maxAbs) - maxAbs;
  return fp;
}

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto Encode2D(const ScalarType x, const ScalarType y, const ScalarType maxAbs = 1.0) {
  using UnsignedType  = std::conditional_t<(Bits * 2 > 32), uint64_t, uint32_t>;
  auto x_enc          = EncodeFloating<ScalarType, Bits>(x, maxAbs);
  auto y_enc          = EncodeFloating<ScalarType, Bits>(y, maxAbs);
  UnsignedType fp_enc = y_enc | (x_enc << Bits);
  return fp_enc;
}

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto Encode3D(const ScalarType x, const ScalarType y, const ScalarType z,
                                                             const ScalarType maxAbs = 1.0) {
  using UnsignedType  = std::conditional_t<(Bits * 3 > 32), uint64_t, uint32_t>;
  auto x_enc          = EncodeFloating<ScalarType, Bits>(x, maxAbs);
  auto y_enc          = EncodeFloating<ScalarType, Bits>(y, maxAbs);
  auto z_enc          = EncodeFloating<ScalarType, Bits>(z, maxAbs);
  UnsignedType fp_enc = z_enc | (y_enc << Bits) | (x_enc << (2 * Bits));
  return fp_enc;
}

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto Decode2D(const std::conditional_t<(Bits * 2 > 32), uint64_t, uint32_t> fp_enc,
                                                             const ScalarType maxAbs = 1.0) {
  ScalarType x = DecodeFloating<ScalarType, Bits>(fp_enc >> (1 * Bits), maxAbs);
  ScalarType y = DecodeFloating<ScalarType, Bits>(fp_enc, maxAbs);
  return std::make_tuple(x, y);
}

template <typename ScalarType, int Bits>
requires(Bits > 0 && Bits <= 21) static inline auto Decode3D(const std::conditional_t<(Bits * 3 > 32), uint64_t, uint32_t> fp_enc,
                                                             const ScalarType maxAbs = 1.0) {
  ScalarType x = DecodeFloating<ScalarType, Bits>(fp_enc >> (2 * Bits), maxAbs);
  ScalarType y = DecodeFloating<ScalarType, Bits>(fp_enc >> (1 * Bits), maxAbs);
  ScalarType z = DecodeFloating<ScalarType, Bits>(fp_enc, maxAbs);
  return std::make_tuple(x, y, z);
}

template <typename ScalarType, size_t N>
requires(std::is_arithmetic_v<ScalarType>&& N > 0) static inline size_t maxAbsIndex(const ScalarType* arr) {
  size_t maxIdx        = 0;
  ScalarType maxAbsVal = std::abs(arr[0]);
  for (size_t i = 1; i < N; ++i) {
    ScalarType absVal = std::abs(arr[i]);
    if (absVal > maxAbsVal) {
      maxAbsVal = absVal;
      maxIdx    = i;
    }
  }
  return maxIdx;
}

template <typename ScalarType>
static inline auto EncodeQuaternion(const ScalarType* data) {
  constexpr ScalarType maxAbs = 0.70710678118;
  size_t idx                  = maxAbsIndex<ScalarType, 4>(data);
  std::array<ScalarType, 3> rest_data;
  ScalarType sign = data[idx] >= 0 ? 1.0 : -1.0;
  for (size_t i = 0, j = 0; i < 4; ++i) {
    if (i == idx) continue;
    rest_data[j++] = sign * data[i];
  }
  auto result = Encode3D<ScalarType, 10>(rest_data[0], rest_data[1], rest_data[2], maxAbs);
  return ((static_cast<uint32_t>(idx) & uint32_t(3)) << 30) | result;
}

template <typename ScalarType>
static inline auto DecodeQuaternion(const uint32_t data, ScalarType* quat) -> void {
  constexpr ScalarType maxAbs = 0.70710678118;
  std::array<ScalarType, 3> recv_data;
  size_t idx                                         = data >> 30;
  std::tie(recv_data[0], recv_data[1], recv_data[2]) = Decode3D<ScalarType, 10>(data, maxAbs);
  ScalarType maxFp = sqrt(1 - recv_data[0] * recv_data[0] - recv_data[1] * recv_data[1] - recv_data[2] * recv_data[2]);
  maxFp            = maxFp >= 1.0 ? 1.0 : maxFp;
  for (size_t i = 0, j = 0; i < 4; ++i) {
    if (i == idx) {
      quat[i] = maxFp;
    } else {
      quat[i] = recv_data[j++];
    }
  }
  return;
}
