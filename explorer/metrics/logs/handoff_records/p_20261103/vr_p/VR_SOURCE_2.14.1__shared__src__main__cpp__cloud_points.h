#pragma once
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <deque>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <limits>

namespace cloud {
  using Mat = std::array<float, 16>;
  struct Meta {
    std::string id;
    std::array<float, 6> bounds;
    std::array<int, 3> cell{};
  };
  inline bool sphere(const std::array<float, 6>& b, const std::array<float, 3>& p, float radius) {
    double d = 0;
    for (int k = 0; k < 3; k++) {
      double v = std::max(double(b[k] - p[k]), std::max(0., double(p[k] - b[k + 3])));
      d += v * v;
    }
    return d <= radius * radius;
  }
  inline bool visible(const std::array<float, 6>& b, const Mat& m) {
    for (int p = 0; p < 6; p++) {
      int r   = p / 2;
      float s = p & 1 ? -1.f : 1.f, d = m[15] + s * m[12 + r];
      for (int k = 0; k < 3; k++) {
        float c = m[k * 4 + 3] + s * m[k * 4 + r];
        d += c * b[k + (c >= 0 ? 3 : 0)];
      }
      if (d < 0) return false;
    }
    return true;
  }
  inline std::vector<uint8_t> packedPoints(const uint8_t* raw, size_t size) {
    if (!raw || !size || size % 15 || size > 15000000) throw std::runtime_error("15-byte cloud point length");
    std::vector<uint8_t> result(size / 15 * 16);
    for (size_t i = 0; i < size / 15; i++) {
      for (int k = 0; k < 3; k++) {
        float f;
        std::memcpy(&f, raw + i * 15 + k * 4, 4);
        if (!std::isfinite(f) || std::abs(f) > 1000000) throw std::runtime_error("Cloud position invalid");
      }
      std::memcpy(result.data() + i * 16, raw + i * 15, 15);
      result[i * 16 + 15] = 255;
    }
    return result;
  }
  static const char* vertex   = R"(#version 300 es
precision highp float;
layout(location=0) in vec3 position;layout(location=1) in vec4 color;
uniform mat4 mvp;uniform vec3 head;uniform bool coarse;uniform bool fineReady;uniform float pointSize;uniform float nearRadius;uniform bool progressive;uniform highp usampler3D readyCells;uniform ivec3 gridOrigin;uniform ivec3 gridSize;uniform float tileMeters;
out vec3 rgb;
vec3 linearRGB(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
void main(){float d=distance(position,head);ivec3 cell=ivec3(floor(position/tileMeters))-gridOrigin;
 bool inGrid=all(greaterThanEqual(cell,ivec3(0)))&&all(lessThan(cell,gridSize));bool cellReady=progressive&&inGrid&&texelFetch(readyCells,cell,0).r>0u;
 bool draw=coarse?(d>nearRadius||(progressive?!cellReady:!fineReady)):(d<=nearRadius&&(progressive||fineReady));
gl_Position=draw?mvp*vec4(position,1.):vec4(2.,2.,2.,1.);gl_PointSize=pointSize;rgb=linearRGB(color.rgb);}
)";
  static const char* fragment = R"(#version 300 es
precision highp float;in vec3 rgb;uniform bool encodeSrgb;out vec4 frag;
vec3 srgb(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
void main(){frag=vec4(encodeSrgb?srgb(rgb):rgb,1.);}
)";

  class Gpu {
    struct Item {
      long long gen;
      std::string id;
      std::vector<uint8_t> data;
      bool coarse;
    };
    struct Tile {
      GLuint buffer = 0;
      size_t bytes  = 0;
      bool coarse   = false;
    };
    std::mutex mutex, statusMutex;
    std::deque<Item> pending;
    size_t queued = 0;
    std::vector<Meta> nextMetas, metas;
    std::map<std::string, std::array<float, 6>> metaById;
    std::set<std::string> keep;
    std::map<std::string, Tile> tiles;
    std::set<std::string> published, accepted;
    long long publishedGeneration = 0;
    std::atomic<long long> requested{0};
    long long current = 0;
    bool resetPending = false, keepKnown = false;
    Item uploading{};
    GLuint uploadingBuffer = 0;
    size_t offset = 0, bytes = 0;
    const size_t budget;
    float nearRadius = 3, requestedRadius = 3, tileMeters = 1, nextTileMeters = 1;
    std::vector<int> nextCells;
    bool gridDirty = false, occupancyDirty = true, progressive = false;
    std::array<int, 3> gridOrigin{}, gridSize{};
    GLuint occupancy = 0;
    size_t volume    = 0;
    std::array<float, 3> lastHead{};
    void publish() {
      std::lock_guard<std::mutex> queueLock(mutex);
      std::lock_guard<std::mutex> lock(statusMutex);
      if (current != requested) return;
      publishedGeneration = current;
      published.clear();
      accepted.clear();
      for (const auto& e : tiles) {
        published.insert(e.first);
        accepted.insert(e.first);
      }
      for (const auto& e : pending) accepted.insert(e.id);
      if (uploadingBuffer) accepted.insert(uploading.id);
    }
    void remove(std::map<std::string, Tile>::iterator it) {
      bytes -= it->second.bytes;
      glDeleteBuffers(1, &it->second.buffer);
      tiles.erase(it);
      occupancyDirty = true;
    }

  public:
    static constexpr size_t Budget = 96 * 1024 * 1024, QueueBudget = 16 * 1024 * 1024;
    explicit Gpu(size_t limit = Budget) : budget(limit) {}
    std::atomic<long long> stats[8]{};
    void configure(long long generation, std::vector<Meta> descriptors) {
      std::lock_guard<std::mutex> lock(mutex);
      if (generation > 0 && requested > 0 && generation < requested) return;
      requested    = generation;
      nextMetas    = std::move(descriptors);
      resetPending = true;
      pending.clear();
      queued = 0;
      keep.clear();
      keepKnown = false;
      nextCells.clear();
      gridDirty = true;
      std::lock_guard<std::mutex> state(statusMutex);
      published.clear();
      accepted.clear();
      publishedGeneration = 0;
    }
    bool offer(long long gen, std::string id, const uint8_t* raw, size_t size, bool coarse) {
      if (gen != requested) return false;
      {
        std::lock_guard<std::mutex> lock(mutex);
        if (queued + size / 15 * 16 > QueueBudget) return false;
      }
      auto data = packedPoints(raw, size);
      return offerPacked(gen, std::move(id), std::move(data), coarse);
    }
    bool offerPacked(long long gen, std::string id, std::vector<uint8_t> data, bool coarse) {
      std::lock_guard<std::mutex> lock(mutex);
      if (gen != requested || queued + data.size() > QueueBudget) return false;
      std::lock_guard<std::mutex> state(statusMutex);
      if (accepted.count(id)) return true;
      accepted.insert(id);
      queued += data.size();
      pending.push_back({gen, std::move(id), std::move(data), coarse});
      return true;
    }
    void retain(long long gen, std::set<std::string> ids) {
      std::lock_guard<std::mutex> lock(mutex);
      if (gen == requested) {
        keep      = std::move(ids);
        keepKnown = true;
      }
    }
    std::set<std::string> resident(long long gen) {
      std::lock_guard<std::mutex> lock(statusMutex);
      return gen == requested && gen == publishedGeneration ? published : std::set<std::string>{};
    }
    std::set<std::string> queuedIds(long long gen) {
      std::lock_guard<std::mutex> lock(statusMutex);
      return gen == requested ? accepted : std::set<std::string>{};
    }
    void policy(long long gen, float radius) {
      std::lock_guard<std::mutex> lock(mutex);
      if (gen == requested && std::isfinite(radius) && radius >= .5f && radius <= 10) requestedRadius = radius;
    }
    void grid(long long gen, float meters, std::vector<int> cells) {
      std::lock_guard<std::mutex> lock(mutex);
      if (gen == requested && std::isfinite(meters) && meters > 0 && meters <= 1000) {
        nextCells      = std::move(cells);
        nextTileMeters = meters;
        gridDirty      = true;
      }
    }
    void rebuildGrid() {
      progressive = false;
      volume      = 0;
      if (nextCells.size() != metas.size() * 3 || metas.empty()) return;
      tileMeters = nextTileMeters;
      gridOrigin = {INT32_MAX, INT32_MAX, INT32_MAX};
      std::array<int, 3> hi{INT32_MIN, INT32_MIN, INT32_MIN};
      for (size_t i = 0; i < metas.size(); i++)
        for (int k = 0; k < 3; k++) {
          int c = nextCells[i * 3 + k];
          if (c < -1000000 || c > 1000000) return;
          metas[i].cell[k] = c;
          gridOrigin[k]    = std::min(gridOrigin[k], c);
          hi[k]            = std::max(hi[k], c);
        }
      size_t count = 1;
      for (int k = 0; k < 3; k++) {
        gridSize[k] = hi[k] - gridOrigin[k] + 1;
        if (gridSize[k] <= 0 || gridSize[k] > 512) return;
        count *= gridSize[k];
        if (count > 262144) return;
      }
      volume         = count;
      progressive    = true;
      occupancyDirty = true;
    }
    size_t cellIndex(const std::array<int, 3>& c) {
      return (size_t(c[2] - gridOrigin[2]) * gridSize[1] + c[1] - gridOrigin[1]) * gridSize[0] + c[0] - gridOrigin[0];
    }
    void uploadOccupancy() {
      if (!progressive || !occupancyDirty) return;
      std::vector<int> required(volume), ready(volume);
      std::vector<uint8_t> bits(volume);
      for (const auto& m : metas) {
        size_t i = cellIndex(m.cell);
        required[i]++;
        if (tiles.count(m.id)) ready[i]++;
      }
      for (size_t i = 0; i < volume; i++) bits[i] = required[i] > 0 && required[i] == ready[i] ? 1 : 0;
      if (!occupancy) glGenTextures(1, &occupancy);
      glActiveTexture(GL_TEXTURE6);
      glBindTexture(GL_TEXTURE_3D, occupancy);
      glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
      glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
      glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
      glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
      glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE);
      glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
      glTexImage3D(GL_TEXTURE_3D, 0, GL_R8UI, gridSize[0], gridSize[1], gridSize[2], 0, GL_RED_INTEGER, GL_UNSIGNED_BYTE, bits.data());
      glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
      occupancyDirty = false;
    }
    void tick() {
      std::set<std::string> retained;
      bool known;
      {
        std::lock_guard<std::mutex> lock(mutex);
        if (resetPending) {
          clearGl();
          current = requested;
          metas   = std::move(nextMetas);
          metaById.clear();
          for (auto& m : metas) metaById[m.id] = m.bounds;
          resetPending = false;
          stats[6]     = 0;
        }
        nearRadius = requestedRadius;
        if (gridDirty) {
          rebuildGrid();
          gridDirty = false;
        }
        retained = keep;
        known    = keepKnown;
        if (uploadingBuffer && !uploading.coarse && known && !retained.count(uploading.id)) {
          glDeleteBuffers(1, &uploadingBuffer);
          uploadingBuffer = 0;
          uploading.data.clear();
          offset = 0;
        }
        if (uploadingBuffer && uploading.gen != current) {
          glDeleteBuffers(1, &uploadingBuffer);
          uploadingBuffer = 0;
          uploading.data.clear();
        }
        while (!uploadingBuffer && !pending.empty()) {
          Item next = std::move(pending.front());
          pending.pop_front();
          queued -= next.data.size();
          if (next.gen != current || (!next.coarse && known && !retained.count(next.id))) continue;
          if (tiles.count(next.id)) continue;
          bool incomingNear = next.coarse || (metaById.count(next.id) && sphere(metaById[next.id], lastHead, nearRadius));
          auto distance     = [&](const std::string& id) {
            auto it = metaById.find(id);
            if (it == metaById.end()) return 1e30f;
            float sum = 0;
            for (int k = 0; k < 3; k++) {
              float d = (it->second[k] + it->second[k + 3]) * .5f - lastHead[k];
              sum += d * d;
            }
            return sum;
          };
          while (bytes + next.data.size() > budget) {
            auto victim    = tiles.end();
            float farthest = incomingNear ? -1.f : distance(next.id);
            for (auto it = tiles.begin(); it != tiles.end(); ++it) {
              if (it->second.coarse || (metaById.count(it->first) && sphere(metaById[it->first], lastHead, nearRadius))) continue;
              float d = distance(it->first);
              if (d > farthest) {
                farthest = d;
                victim   = it;
              }
            }
            if (victim == tiles.end()) break;
            remove(victim);
          }
          if (bytes + next.data.size() > budget) {
            stats[6] = incomingNear ? 1 : 3;
            continue;
          }
          uploading = std::move(next);
          offset    = 0;
          glGenBuffers(1, &uploadingBuffer);
          glBindBuffer(GL_ARRAY_BUFFER, uploadingBuffer);
          glBufferData(GL_ARRAY_BUFFER, uploading.data.size(), nullptr, GL_STATIC_DRAW);
        }
        stats[2] = queued;
      }
      bool changed = false;
      if (known)
        for (auto it = tiles.begin(); it != tiles.end();) {
          if (!it->second.coarse && !retained.count(it->first)) {
            auto old = it++;
            remove(old);
            changed        = true;
            occupancyDirty = true;
          } else
            ++it;
        }
      if (uploadingBuffer) {
        size_t n = std::min(size_t(2 * 1024 * 1024), uploading.data.size() - offset);
        glBindBuffer(GL_ARRAY_BUFFER, uploadingBuffer);
        glBufferSubData(GL_ARRAY_BUFFER, offset, n, uploading.data.data() + offset);
        if (glGetError() != GL_NO_ERROR) {
          glDeleteBuffers(1, &uploadingBuffer);
          uploadingBuffer = 0;
          uploading.data.clear();
          stats[6] = 2;
        } else {
          offset += n;
          if (offset == uploading.data.size()) {
            tiles[uploading.id] = {uploadingBuffer, uploading.data.size(), uploading.coarse};
            bytes += uploading.data.size();
            uploadingBuffer = 0;
            uploading.data.clear();
            changed        = true;
            occupancyDirty = true;
          }
        }
      }
      stats[0] = tiles.size();
      stats[1] = bytes;
      publish();
      uploadOccupancy();
    }
    void draw(GLuint program, const Mat& mvp, std::array<float, 3> head, bool encodeSrgb) {
      if (current != requested) return;
      lastHead   = head;
      bool ready = tiles.count("coarse") > 0 && !metas.empty();
      int needed = 0, have = 0;
      for (const auto& m : metas)
        if (sphere(m.bounds, head, nearRadius)) {
          needed++;
          if (tiles.count(m.id))
            have++;
          else
            ready = false;
        }
      stats[3] = have;
      stats[4] = needed;
      stats[5] = ready;
      if (ready && stats[6] == 1) stats[6] = 0;
      glEnable(GL_DEPTH_TEST);
      glDepthMask(GL_TRUE);
      glDisable(GL_BLEND);
      glUseProgram(program);
      glUniformMatrix4fv(glGetUniformLocation(program, "mvp"), 1, GL_FALSE, mvp.data());
      glUniform3fv(glGetUniformLocation(program, "head"), 1, head.data());
      glUniform1i(glGetUniformLocation(program, "fineReady"), ready);
      glUniform1f(glGetUniformLocation(program, "nearRadius"), nearRadius);
      glUniform1f(glGetUniformLocation(program, "tileMeters"), tileMeters);
      glUniform1i(glGetUniformLocation(program, "progressive"), progressive);
      glUniform3i(glGetUniformLocation(program, "gridOrigin"), gridOrigin[0], gridOrigin[1], gridOrigin[2]);
      glUniform3i(glGetUniformLocation(program, "gridSize"), gridSize[0], gridSize[1], gridSize[2]);
      glActiveTexture(GL_TEXTURE6);
      glBindTexture(GL_TEXTURE_3D, occupancy);
      glUniform1i(glGetUniformLocation(program, "readyCells"), 6);
      glUniform1i(glGetUniformLocation(program, "encodeSrgb"), encodeSrgb);
      glUniform1f(glGetUniformLocation(program, "pointSize"), 2.5f);
      glEnableVertexAttribArray(0);
      glEnableVertexAttribArray(1);
      long long points = 0;
      for (const auto& e : tiles) {
        if (!e.second.coarse) {
          if (!progressive && !ready) continue;
          auto m = metaById.find(e.first);
          if (m == metaById.end() || !sphere(m->second, head, nearRadius) || !visible(m->second, mvp)) continue;
        }
        glBindBuffer(GL_ARRAY_BUFFER, e.second.buffer);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 16, nullptr);
        glVertexAttribPointer(1, 4, GL_UNSIGNED_BYTE, GL_TRUE, 16, (void*)12);
        glUniform1i(glGetUniformLocation(program, "coarse"), e.second.coarse);
        glDrawArrays(GL_POINTS, 0, e.second.bytes / 16);
        points += e.second.bytes / 16;
      }
      stats[7] = points;
    }
    void clearGl() {
      for (auto& e : tiles) glDeleteBuffers(1, &e.second.buffer);
      tiles.clear();
      if (occupancy) glDeleteTextures(1, &occupancy);
      occupancy      = 0;
      progressive    = false;
      occupancyDirty = true;
      if (uploadingBuffer) glDeleteBuffers(1, &uploadingBuffer);
      uploadingBuffer = 0;
      uploading.data.clear();
      bytes = 0;
      for (auto& s : stats) s = 0;
    }
  };
}  // namespace cloud
