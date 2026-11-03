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
#include <algorithm>
#include <atomic>
#include <numeric>
#include <limits>
#include <mortonLUT.hpp>
#include <tbb/parallel_for_each.h>
#include <tbb/parallel_sort.h>
#include <tbb/enumerable_thread_specific.h>

static inline AlignedVector<uint64_t> IntervalDownsample(const AlignedVector<uint64_t> &raw_points, const int interval = 20, const bool parallel = true)
{
    AlignedVector<uint64_t> result;
    size_t sample_size = raw_points.size() / interval;

    if (parallel == true)
    {
        result.resize(sample_size);
        tbb::parallel_for_each(result.begin(), result.end(),
                               [&](uint64_t &point)
                               {
                                   size_t idx = &point - &result[0];
                                   point = raw_points[idx * interval];
                               });
    }
    else
    {
        result.reserve(sample_size);
        for (size_t i = 0; i < sample_size; i++)
        {
            result.emplace_back(raw_points[i * interval]);
        }
    }

    return result;
}

// Input points must be sorted!!!!!!!!!!!!!!!!!!!!!!!!!!!!
static inline AlignedVector<uint64_t> VoxelGridDownsample(const AlignedVector<uint64_t> &raw_points, const int box_width = 5)
{
    using namespace mortonnd;
    constexpr MortonNDLutDecoder_3D_64 decoder;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    const uint64_t bit_mask = 0xffffffffffffffffULL << (box_width * 3);
    AlignedVector<uint64_t> result;
    std::vector<uint32_t> duplicates;
    std::vector<uint64_t> index;
    duplicates.reserve(32768);
    index.reserve(32768);
    uint64_t sum = 0;
    uint32_t cnt = 1;
    index.emplace_back(0);
    for (size_t i = 1; i < raw_points.size(); i++)
    {
        if ((raw_points[i] & bit_mask) == (raw_points[i - 1] & bit_mask))
            cnt++;
        else
        {
            duplicates.emplace_back(cnt);
            sum += cnt;
            index.emplace_back(sum);
            cnt = 1;
        }
    }
    duplicates.emplace_back(cnt);
    result.resize(duplicates.size());
    tbb::parallel_for(tbb::blocked_range<size_t>(0, duplicates.size()),
                      [&](const tbb::blocked_range<size_t> &range)
                      {
                          for (size_t dup_idx = range.begin(); dup_idx < range.end(); ++dup_idx)
                          {
                              uint64_t x = 0, y = 0, z = 0;
                              const uint32_t dup_cnt = duplicates[dup_idx];
                              const uint64_t raw_idx = index[dup_idx];
                              for (uint32_t i = 0; i < dup_cnt; ++i)
                              {
                                  auto [dx, dy, dz] = decoder.Decode(raw_points[raw_idx + i]);
                                  x += dx;
                                  y += dy;
                                  z += dz;
                              }
                              x /= dup_cnt;
                              y /= dup_cnt;
                              z /= dup_cnt;
                              result[dup_idx] = encoder.Encode(x, y, z);
                          }
                      });
    return result;
}

template <int PatternVoxel>
constexpr std::array<std::array<int, 3>, PatternVoxel> GetPattern()
{
    using ReturnType = std::array<std::array<int, 3>, PatternVoxel>;
    static_assert(PatternVoxel == 32 || PatternVoxel == 27 || PatternVoxel == 19 || PatternVoxel == 8, "PatternVoxel must be 32, 27, 19 or 8");

    if constexpr (PatternVoxel == 8)
    {
        return ReturnType{{{0, 0, 0},
                           {1, 0, 0},
                           {0, 1, 0},
                           {1, 1, 0},
                           {0, 0, 1},
                           {1, 0, 1},
                           {0, 1, 1},
                           {1, 1, 1}}};
    }
    else if constexpr (PatternVoxel == 19)
    {
        return ReturnType{{{1, 0, 0},
                           {0, 1, 0},
                           {1, 1, 0},
                           {2, 1, 0},
                           {1, 2, 0},
                           {0, 0, 1},
                           {1, 0, 1},
                           {0, 1, 1},
                           {1, 1, 1},
                           {2, 1, 1},
                           {1, 2, 1},
                           {0, 2, 1},
                           {2, 0, 1},
                           {2, 2, 1},
                           {1, 0, 2},
                           {0, 1, 2},
                           {1, 1, 2},
                           {2, 1, 2},
                           {1, 2, 2}}};
    }
    else if constexpr (PatternVoxel == 27)
    {
        return ReturnType{{{0, 0, 0},
                           {1, 0, 0},
                           {0, 1, 0},
                           {1, 1, 0},
                           {2, 1, 0},
                           {1, 2, 0},
                           {0, 2, 0},
                           {2, 0, 0},
                           {2, 2, 0},
                           {0, 0, 1},
                           {1, 0, 1},
                           {0, 1, 1},
                           {1, 1, 1},
                           {2, 1, 1},
                           {1, 2, 1},
                           {0, 2, 1},
                           {2, 0, 1},
                           {2, 2, 1},
                           {0, 0, 2},
                           {1, 0, 2},
                           {0, 1, 2},
                           {1, 1, 2},
                           {2, 1, 2},
                           {1, 2, 2},
                           {0, 2, 2},
                           {2, 0, 2},
                           {2, 2, 2}}};
    }
    else if constexpr (PatternVoxel == 32)
    {
        return ReturnType{{{1, 1, 0},
                           {1, 2, 0},
                           {2, 1, 0},
                           {2, 2, 0},
                           {1, 0, 1},
                           {0, 1, 1},
                           {1, 1, 1},
                           {1, 2, 1},
                           {2, 1, 1},
                           {0, 2, 1},
                           {2, 0, 1},
                           {2, 2, 1},
                           {1, 3, 1},
                           {3, 1, 1},
                           {3, 2, 1},
                           {2, 3, 1},
                           {1, 0, 2},
                           {0, 1, 2},
                           {1, 1, 2},
                           {1, 2, 2},
                           {2, 1, 2},
                           {0, 2, 2},
                           {2, 0, 2},
                           {2, 2, 2},
                           {1, 3, 2},
                           {3, 1, 2},
                           {3, 2, 2},
                           {2, 3, 2},
                           {1, 1, 3},
                           {1, 2, 3},
                           {2, 1, 3},
                           {2, 2, 3}}};
    }
    else
    {
        return ReturnType{};
    }
}

template <int PatternVoxel>
static inline auto PatternOffsets(const Eigen::Vector3f &center, const uint32_t size)
{
    using namespace mortonnd;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    constexpr int coord_offset = 1 << 20;
    const uint32_t coord_x = std::floor(center.x() * 100) + coord_offset;
    const uint32_t coord_y = std::floor(center.y() * 100) + coord_offset;
    const uint32_t coord_z = std::floor(center.z() * 100) + coord_offset;
    const uint32_t width = 1 << (size - 1);
    const uint64_t block_offset = (1ULL << ((size - 1) * 3)) - 1;
    uint32_t corner_x, corner_y, corner_z;
    if constexpr (PatternVoxel == 8)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 1) * width : coord_x / width * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 1) * width : coord_y / width * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 1) * width : coord_z / width * width;
    }
    else if constexpr (PatternVoxel == 19 || PatternVoxel == 27)
    {
        corner_x = (coord_x / width - 1) * width;
        corner_y = (coord_y / width - 1) * width;
        corner_z = (coord_z / width - 1) * width;
    }
    else if constexpr (PatternVoxel == 32)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 2) * width : (coord_x / width - 1) * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 2) * width : (coord_y / width - 1) * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 2) * width : (coord_z / width - 1) * width;
    }
    std::array<uint64_t, PatternVoxel> start_pts;
    auto patterns = GetPattern<PatternVoxel>();
    for (size_t i = 0; i < patterns.size(); ++i)
    {
        const auto &pattern = patterns[i];
        uint64_t start_pt = encoder.Encode(corner_x + pattern[0] * width, corner_y + pattern[1] * width, corner_z + pattern[2] * width);
        start_pts[i] = start_pt;
    }
    std::sort(start_pts.begin(), start_pts.end());
    return start_pts;
}


//TODO: 目前是返回周围点，包含了复制构造，修改使其只返回周围点的个数而不复制


template <int PatternVoxel>
static inline size_t RangeSearchCnt(const AlignedVector<uint64_t> &raw_points, 
                                     const uint64_t &center, 
                                     const uint32_t size)
{
    using namespace mortonnd;
    constexpr MortonNDLutDecoder_3D_64 decoder;
    
    // 解码中心点坐标
    auto [coord_x, coord_y, coord_z] = decoder.Decode(center);
    const uint32_t width = 1 << (size - 1);
    
    // 计算空间块角点
    uint32_t corner_x, corner_y, corner_z;
    if constexpr (PatternVoxel == 8) {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 1) * width : coord_x / width * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 1) * width : coord_y / width * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 1) * width : coord_z / width * width;
    } else if constexpr (PatternVoxel == 19 || PatternVoxel == 27) {
        corner_x = (coord_x / width - 1) * width;
        corner_y = (coord_y / width - 1) * width;
        corner_z = (coord_z / width - 1) * width;
    } else if constexpr (PatternVoxel == 32) {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 2) * width : (coord_x / width - 1) * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 2) * width : (coord_y / width - 1) * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 2) * width : (coord_z / width - 1) * width;
    }

    // 获取模式并生成起始点
    auto patterns = GetPattern<PatternVoxel>();
    std::array<uint64_t, PatternVoxel> start_pts;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    for (size_t i = 0; i < patterns.size(); ++i) {
        const auto &pattern = patterns[i];
        start_pts[i] = encoder.Encode(
            corner_x + pattern[0] * width,
            corner_y + pattern[1] * width,
            corner_z + pattern[2] * width
        );
    }
    
    // 排序起始点
    std::sort(start_pts.begin(), start_pts.end());
    
    // 计算块偏移量（块大小-1）
    const uint64_t block_offset = (1ULL << ((size - 1) * 3)) - 1;
    
    size_t count = 0;
    for (const auto &start_pt : start_pts) {
        uint64_t end_pt = start_pt + block_offset;
        auto it_start = std::lower_bound(raw_points.begin(), raw_points.end(), start_pt);
        auto it_end = std::upper_bound(raw_points.begin(), raw_points.end(), end_pt);
        count += std::distance(it_start, it_end);
    }
    
    return count;
}

template <int PatternVoxel>
static inline size_t RangeSearchCnt(const AlignedVector<uint64_t> &raw_points, 
                                   const Eigen::Vector3f &center, 
                                   const uint32_t size)
{
    using namespace mortonnd;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    
    // 坐标转换：浮点数坐标 -> 整数坐标
    constexpr int coord_offset = 1 << 20;
    const uint32_t coord_x = std::floor(center.x() * 100) + coord_offset;
    const uint32_t coord_y = std::floor(center.y() * 100) + coord_offset;
    const uint32_t coord_z = std::floor(center.z() * 100) + coord_offset;
    
    const uint32_t width = 1 << (size - 1);
    const uint64_t block_offset = (1ULL << ((size - 1) * 3)) - 1;
    
    // 计算空间块角点
    uint32_t corner_x, corner_y, corner_z;
    if constexpr (PatternVoxel == 8) {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 1) * width : coord_x / width * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 1) * width : coord_y / width * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 1) * width : coord_z / width * width;
    } else if constexpr (PatternVoxel == 19 || PatternVoxel == 27) {
        corner_x = (coord_x / width - 1) * width;
        corner_y = (coord_y / width - 1) * width;
        corner_z = (coord_z / width - 1) * width;
    } else if constexpr (PatternVoxel == 32) {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 2) * width : (coord_x / width - 1) * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 2) * width : (coord_y / width - 1) * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 2) * width : (coord_z / width - 1) * width;
    }

    // 生成模式起始点
    auto patterns = GetPattern<PatternVoxel>();
    std::array<uint64_t, PatternVoxel> start_pts;
    for (size_t i = 0; i < patterns.size(); ++i) {
        const auto &pattern = patterns[i];
        start_pts[i] = encoder.Encode(
            corner_x + pattern[0] * width,
            corner_y + pattern[1] * width,
            corner_z + pattern[2] * width
        );
    }
    
    // 排序起始点
    std::sort(start_pts.begin(), start_pts.end());
    
    // 计数器代替结果向量
    size_t count = 0;
    
    // 遍历所有模式块并计数
    for (const auto &start_pt : start_pts) {
        uint64_t end_pt = start_pt + block_offset;
        auto it_start = std::lower_bound(raw_points.begin(), raw_points.end(), start_pt);
        auto it_end = std::upper_bound(raw_points.begin(), raw_points.end(), end_pt);
        count += std::distance(it_start, it_end);
    }
    
    return count;
}


template <int PatternVoxel>
static inline AlignedVector<uint64_t> RangeSearch(const AlignedVector<uint64_t> &raw_points, const uint64_t &center, const uint32_t size)
{
    using namespace mortonnd;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    constexpr MortonNDLutDecoder_3D_64 decoder;
    AlignedVector<uint64_t> result;
    result.reserve(32768);
    constexpr int coord_offset = 1 << 20;
    auto [coord_x, coord_y, coord_z] = decoder.Decode(center);
    const uint32_t width = 1 << (size - 1);
    const uint64_t block_offset = (1ULL << ((size - 1) * 3)) - 1;
    uint32_t corner_x, corner_y, corner_z;
    if constexpr (PatternVoxel == 8)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 1) * width : coord_x / width * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 1) * width : coord_y / width * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 1) * width : coord_z / width * width;
    }
    else if constexpr (PatternVoxel == 19 || PatternVoxel == 27)
    {
        corner_x = (coord_x / width - 1) * width;
        corner_y = (coord_y / width - 1) * width;
        corner_z = (coord_z / width - 1) * width;
    }
    else if constexpr (PatternVoxel == 32)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 2) * width : (coord_x / width - 1) * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 2) * width : (coord_y / width - 1) * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 2) * width : (coord_z / width - 1) * width;
    }
    std::array<uint64_t, PatternVoxel> start_pts;
    auto patterns = GetPattern<PatternVoxel>();
    for (size_t i = 0; i < patterns.size(); ++i)
    {
        const auto &pattern = patterns[i];
        uint64_t start_pt = encoder.Encode(corner_x + pattern[0] * width, corner_y + pattern[1] * width, corner_z + pattern[2] * width);
        start_pts[i] = start_pt;
    }
    std::sort(start_pts.begin(), start_pts.end());
    // TODO: parallelize this
    for (const auto &start_pt : start_pts)
    {
        uint64_t end_pt = start_pt + block_offset;
        auto it_start = std::lower_bound(raw_points.begin(), raw_points.end(), start_pt);
        auto it_end = std::upper_bound(raw_points.begin(), raw_points.end(), end_pt);
        std::copy(it_start, it_end, std::back_inserter(result));
    }
    return result;
}

template <int PatternVoxel>
static inline AlignedVector<uint64_t> RangeSearch(const AlignedVector<uint64_t> &raw_points, const Eigen::Vector3f &center, const uint32_t size)
{
    using namespace mortonnd;
    constexpr MortonNDLutEncoder_3D_64 encoder;
    AlignedVector<uint64_t> result;
    result.reserve(32768);
    constexpr int coord_offset = 1 << 20;
    const uint32_t coord_x = std::floor(center.x() * 100) + coord_offset;
    const uint32_t coord_y = std::floor(center.y() * 100) + coord_offset;
    const uint32_t coord_z = std::floor(center.z() * 100) + coord_offset;
    const uint32_t width = 1 << (size - 1);
    const uint64_t block_offset = (1ULL << ((size - 1) * 3)) - 1;
    uint32_t corner_x, corner_y, corner_z;
    if constexpr (PatternVoxel == 8)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 1) * width : coord_x / width * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 1) * width : coord_y / width * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 1) * width : coord_z / width * width;
    }
    else if constexpr (PatternVoxel == 19 || PatternVoxel == 27)
    {
        corner_x = (coord_x / width - 1) * width;
        corner_y = (coord_y / width - 1) * width;
        corner_z = (coord_z / width - 1) * width;
    }
    else if constexpr (PatternVoxel == 32)
    {
        corner_x = (coord_x % width) < (width >> 1) ? (coord_x / width - 2) * width : (coord_x / width - 1) * width;
        corner_y = (coord_y % width) < (width >> 1) ? (coord_y / width - 2) * width : (coord_y / width - 1) * width;
        corner_z = (coord_z % width) < (width >> 1) ? (coord_z / width - 2) * width : (coord_z / width - 1) * width;
    }
    std::array<uint64_t, PatternVoxel> start_pts;
    auto patterns = GetPattern<PatternVoxel>();
    for (size_t i = 0; i < patterns.size(); ++i)
    {
        const auto &pattern = patterns[i];
        uint64_t start_pt = encoder.Encode(corner_x + pattern[0] * width, corner_y + pattern[1] * width, corner_z + pattern[2] * width);
        start_pts[i] = start_pt;
    }
    std::sort(start_pts.begin(), start_pts.end());
    // TODO: parallelize this
    for (const auto &start_pt : start_pts)
    {
        uint64_t end_pt = start_pt + block_offset;
        auto it_start = std::lower_bound(raw_points.begin(), raw_points.end(), start_pt);
        auto it_end = std::upper_bound(raw_points.begin(), raw_points.end(), end_pt);
        std::copy(it_start, it_end, std::back_inserter(result));
    }
    return result;
}

// better using current ground point as the center here
auto Terrain(const AlignedVector<uint64_t> &raw_points, const Eigen::Vector3f &center, const uint32_t resolution)
{
    using namespace mortonnd;
    constexpr MortonNDLutDecoder_3D_64 decoder;
    constexpr uint32_t range_factor = 7;
    constexpr float z_tolerance = 0.5;
    auto points = RangeSearch<8>(raw_points, center, range_factor);
    points = VoxelGridDownsample(points, resolution);

    const uint32_t grid_bit_width = range_factor - resolution + 2;
    const uint32_t grid_size = 1 << (grid_bit_width - 1);
    const uint32_t grid_bit_mask = grid_size - 1;
    std::vector<uint32_t> grid(grid_size * grid_size, 0);
    for (const auto pt : points)
    {
        auto [x, y, z] = decoder.Decode(pt);

        uint32_t grid_x = x & grid_bit_mask;
        uint32_t grid_y = y & grid_bit_mask;
        uint32_t &cell = grid[grid_x + grid_y * grid_size];
        cell = (z > cell) ? z : cell;
    }
    return grid;
}

template <typename T>
static inline auto sort_index(const T &v)
{
    std::vector<uint32_t> idx(v.size());
    std::iota(idx.begin(), idx.end(), 0);
    tbb::parallel_sort(idx.begin(), idx.end(), [&v](uint32_t i1, uint32_t i2)
                       { return v[i1] < v[i2]; });
    return idx;
}

template <typename T>
static inline auto reorder(const T &v, const std::vector<uint32_t> &index)
{
    T result(index.size());
    tbb::parallel_for(size_t(0), index.size(), [&](size_t i)
                      { result[i] = v[index[i]]; });
    return result;
}

// alpha max plus beta min  about 10% error
constexpr uint32_t fast_hypot(const uint32_t x, const uint32_t y)
{
    int32_t mask = -(x < y);
    uint32_t max = (x & ~mask) | (y & mask);
    uint32_t min = (y & ~mask) | (x & mask);
    uint32_t alpha = 0.9604f * max + 0.3978f * min;
    mask = -(alpha < max);
    return (alpha & ~mask) | (max & mask);
}

constexpr uint32_t fast_hypot(const uint32_t x, const uint32_t y, const uint32_t z)
{
    int32_t mask = -(x < y);
    uint32_t max = (x & ~mask) | (y & mask);
    uint32_t min = (y & ~mask) | (x & mask);
    mask = -(max < z);
    max = (max & ~mask) | (z & mask);
    mask = -(z < min);
    min = (min & ~mask) | (z & mask);
    uint32_t mid = x + y + z - max - min;
    uint32_t alpha = 0.9398f * max + 0.3893f * mid + 0.2987f * min;
    mask = -(alpha < max);
    return (alpha & ~mask) | (max & mask);
}

static inline uint32_t morton_norm(const uint64_t p)
{
    using namespace mortonnd;
    static constexpr MortonNDLutDecoder_3D_64 decoder;
    auto [x, y, z] = decoder.Decode(p);
    return fast_hypot(x, y, z);
}

static inline auto EstimateNormal(const AlignedVector<uint64_t> &raw_points, const Eigen::Vector3f &p, const float radius)
{

    using namespace mortonnd;
    constexpr MortonNDLutDecoder_3D_64 decoder;
    constexpr int coord_offset = 1 << 20;
    const uint32_t intRad = std::log2(radius * 100) + 1;
    AlignedVector<Eigen::Vector3f> normals(raw_points.size());
    tbb::parallel_for_each(raw_points.begin(), raw_points.end(),
                           [&](const uint64_t &_p) -> void
                           {
                               size_t idx = &_p - &raw_points[0];
                               const auto points = RangeSearch<8>(raw_points, _p, intRad);
                               if (points.size() < 10)
                                   return;
                               auto [coord_x, coord_y, coord_z] = decoder.Decode(_p);
                               int32_t cnt = 0;
                               Eigen::Vector4d sum_pts = Eigen::Vector4d::Zero();
                               Eigen::Matrix4d sum_cross = Eigen::Matrix4d::Zero();
                               for (const auto pt : points)
                               {
                                   auto [x, y, z] = decoder.Decode(pt);

                                   if (fast_hypot(abs(static_cast<int>(coord_x - x)), abs(static_cast<int>(coord_y - y)), abs(static_cast<int>(coord_z - z))) > uint32_t(radius * 100))
                                       continue;

                                   sum_pts += Eigen::Vector4d(static_cast<int32_t>(x) - coord_offset, static_cast<int32_t>(y) - coord_offset, static_cast<int32_t>(z) - coord_offset, 0) * 0.01;
                                   sum_cross += sum_pts * sum_pts.transpose();
                                   cnt++;
                               }
                               const Eigen::Vector4d mean = sum_pts / cnt;
                               const Eigen::Matrix4d cov = (sum_cross - mean * sum_pts.transpose()) / cnt;

                               Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> eig;
                               eig.computeDirect(cov.block<3, 3>(0, 0));
                               normals[idx] = eig.eigenvalues().col(0).normalized().cast<float>();
                           });

    return normals;
}