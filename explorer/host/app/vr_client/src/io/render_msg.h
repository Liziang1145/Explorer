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

#include "base_type.hpp"

struct render_msg {
  std::shared_ptr<AlignedVector<uint64_t>> points_resource;
  std::shared_ptr<AlignedVector<uint32_t>> colors_resource;
  std::shared_ptr<AlignedVector<uint32_t>> normals_resource;
  uint32_t size;
  uint32_t offset;
};