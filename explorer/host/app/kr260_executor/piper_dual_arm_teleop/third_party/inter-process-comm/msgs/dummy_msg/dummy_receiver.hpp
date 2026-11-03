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
#include "dummy_msg.h"

struct DummyReceiver {
  using DataType                         = dummy_msg;
  static constexpr uint8_t parser_type   = ParserType::Receiver;
  static constexpr uint16_t header       = 0x00;
  static constexpr size_t length         = 6;
  static constexpr std::string_view name = "dummy_receiver";

  static constexpr bool Process(const std::span<std::byte>& in, DataType& out) {
    // Dummy Process
    return true;
  }
};