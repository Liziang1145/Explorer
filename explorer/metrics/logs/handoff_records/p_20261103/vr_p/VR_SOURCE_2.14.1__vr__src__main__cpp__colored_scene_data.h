#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <map>
#include <stdexcept>
#include <unordered_map>
#include <vector>

namespace tlzscene {
  constexpr size_t MaxGpuBytes = 64 * 1024 * 1024, MaxAssetBytes = 48 * 1024 * 1024;
  struct Chunk {
    std::array<int, 3> cell{};
    std::vector<float> vertices;  // display Y-up xyz + linear RGB, 24-byte vertex
    std::vector<uint32_t> indices;
    std::array<float, 6> bounds{};
    size_t bytes() const { return vertices.size() * 4 + indices.size() * 4; }
  };
  struct Geometry {
    std::vector<Chunk> chunks;
    std::array<float, 6> bounds{};
    size_t bytes = 0, vertices = 0, triangles = 0;
  };
  inline uint32_t u32(const uint8_t* p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
  inline float f32(const uint8_t* p) {
    uint32_t bits = u32(p);
    float f;
    std::memcpy(&f, &bits, 4);
    return f;
  }
  inline float linear(uint8_t c) {
    float f = c / 255.f;
    return f <= .04045f ? f / 12.92f : std::pow((f + .055f) / 1.055f, 2.4f);
  }
  inline Geometry decode(const uint8_t* positions, size_t pb, const uint8_t* colors, size_t cb, const uint8_t* indices, size_t ib, size_t n,
                         size_t faces) {
    if (!positions || !colors || !indices || !n || n > 1000000 || !faces || faces > 2000000 || pb != n * 12 || cb != n * 3 || ib != faces * 12)
      throw std::runtime_error("Scene buffer lengths/counts");
    Geometry out;
    out.vertices  = n;
    out.triangles = faces;
    std::vector<std::array<float, 3>> xyz(n);
    out.bounds = {INFINITY, INFINITY, INFINITY, -INFINITY, -INFINITY, -INFINITY};
    for (size_t i = 0; i < n; i++)
      for (int k = 0; k < 3; k++) {
        float v = f32(positions + i * 12 + k * 4);
        if (!std::isfinite(v) || std::abs(v) > 1000000) throw std::runtime_error("Scene coordinate range");
        xyz[i][k]         = v;
        out.bounds[k]     = std::min(out.bounds[k], v);
        out.bounds[k + 3] = std::max(out.bounds[k + 3], v);
      }
    float lut[256];
    for (int i = 0; i < 256; i++) lut[i] = linear(i);
    std::map<std::array<int, 3>, size_t> cells;
    std::vector<std::unordered_map<uint32_t, uint32_t>> remaps;
    for (size_t t = 0; t < faces; t++) {
      uint32_t ix[3];
      for (int j = 0; j < 3; j++) {
        ix[j] = u32(indices + t * 12 + j * 4);
        if (ix[j] >= n) throw std::runtime_error("Scene uint32 index range");
      }
      std::array<int, 3> cell;
      for (int k = 0; k < 3; k++) cell[k] = (int)std::floor((xyz[ix[0]][k] + xyz[ix[1]][k] + xyz[ix[2]][k]) / 6.f);  // 2m cells
      auto found = cells.find(cell);
      size_t ci;
      if (found == cells.end()) {
        if (cells.size() >= 512) throw std::runtime_error("Scene chunk budget");
        ci          = out.chunks.size();
        cells[cell] = ci;
        out.chunks.emplace_back();
        remaps.emplace_back();
        out.chunks.back().cell   = cell;
        out.chunks.back().bounds = {INFINITY, INFINITY, INFINITY, -INFINITY, -INFINITY, -INFINITY};
      } else
        ci = found->second;
      auto& chunk = out.chunks[ci];
      auto& remap = remaps[ci];
      for (uint32_t vertex : ix) {
        auto it = remap.find(vertex);
        uint32_t local;
        if (it == remap.end()) {
          local         = (uint32_t)(chunk.vertices.size() / 6);
          remap[vertex] = local;
          for (int k = 0; k < 3; k++) {
            float v = xyz[vertex][k];
            chunk.vertices.push_back(v);
            chunk.bounds[k]     = std::min(chunk.bounds[k], v);
            chunk.bounds[k + 3] = std::max(chunk.bounds[k + 3], v);
          }
          for (int k = 0; k < 3; k++) chunk.vertices.push_back(lut[colors[vertex * 3 + k]]);
          out.bytes += 24;
        } else
          local = it->second;
        chunk.indices.push_back(local);
        out.bytes += 4;
      }
      if (out.bytes > MaxAssetBytes) throw std::runtime_error("Scene decoded memory budget");
    }
    return out;
  }
  // Conservative six-plane AABB test in local display coordinates. Never clips a
  // triangle at a cell boundary: bounds include all referenced vertices.
  inline bool visible(const std::array<float, 6>& b, const std::array<float, 16>& m) {
    for (int plane = 0; plane < 6; plane++) {
      int row        = plane / 2;
      float sign     = (plane & 1) ? -1.f : 1.f;
      float distance = m[15] + sign * m[12 + row];
      for (int k = 0; k < 3; k++) {
        float coefficient = m[k * 4 + 3] + sign * m[k * 4 + row];
        distance += coefficient * b[k + (coefficient >= 0 ? 3 : 0)];
      }
      if (distance < 0) return false;
    }
    return true;
  }
}  // namespace tlzscene
