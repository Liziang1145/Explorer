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
#include "cloud_msg.h"
#include <memory>

struct CloudReceiver {
  using DataType                         = std::shared_ptr<std::vector<std::byte>>;
  static constexpr uint8_t parser_type   = ParserType::Receiver;
  static constexpr uint16_t header       = 0xD0FD;
  static constexpr size_t length         = 1356;
  static constexpr std::string_view name = "cloud_receiver";

  static inline bool Process(const std::span<std::byte>& in, DataType& out) {
    out = std::make_shared<std::vector<std::byte>>();
    out->resize(length);
    memcpy(out->data(), in.data(), length);
    return true;
  }
};