#pragma once
#include "colored_scene_data.h"
#include <atomic>
#include <memory>
#include <mutex>

namespace tlzscene {
  // GL methods run only in the XR render context. submit() is a bounded, latest-only
  // handoff from the loader thread. Existing geometry remains visible until commit.
  class Gpu {
    struct Tile {
      GLuint vbo = 0, ebo = 0;
      GLsizei vertices = 0, indices = 0;
      std::array<float, 6> bounds;
    };
    std::mutex mutex;
    std::unique_ptr<Geometry> pending, upload;
    std::vector<Tile> resident, building;
    size_t part = 0, offset = 0, residentBytes = 0;
    static void dispose(std::vector<Tile>& tiles) {
      for (auto& t : tiles) {
        glDeleteBuffers(1, &t.vbo);
        glDeleteBuffers(1, &t.ebo);
      }
      tiles.clear();
    }

  public:
    std::atomic<uint64_t> revision{0};
    std::atomic<int64_t> stats[8]{};  // chunks, triangles, source vertices, GPU bytes, upload done/total, visible chunks, error
    std::array<float, 6> bounds{};
    void submit(Geometry&& data) {
      std::lock_guard<std::mutex> lock(mutex);
      pending = std::make_unique<Geometry>(std::move(data));
    }
    void tick() {
      std::unique_ptr<Geometry> next;
      {
        std::lock_guard<std::mutex> lock(mutex);
        next = std::move(pending);
      }
      if (next) {
        dispose(building);
        upload.reset();
        part = offset = 0;
        stats[7]      = 0;
        stats[4]      = 0;
        stats[5]      = next->bytes;
        if (residentBytes + next->bytes > MaxGpuBytes) {
          stats[7] = 1;
          stats[5] = 0;
          return;
        }
        upload = std::move(next);
      }
      if (!upload) return;
      size_t budget = 2 * 1024 * 1024;  // bounded host-to-GPU traffic per XR frame
      while (budget && part < upload->chunks.size()) {
        auto& source = upload->chunks[part];
        size_t vb = source.vertices.size() * 4, ib = source.indices.size() * 4;
        if (part == building.size()) {
          Tile tile;
          tile.bounds   = source.bounds;
          tile.vertices = source.vertices.size() / 6;
          tile.indices  = source.indices.size();
          glGenBuffers(1, &tile.vbo);
          glBindBuffer(GL_ARRAY_BUFFER, tile.vbo);
          glBufferData(GL_ARRAY_BUFFER, vb, nullptr, GL_STATIC_DRAW);
          glGenBuffers(1, &tile.ebo);
          glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, tile.ebo);
          glBufferData(GL_ELEMENT_ARRAY_BUFFER, ib, nullptr, GL_STATIC_DRAW);
          if (glGetError() != GL_NO_ERROR) {
            glDeleteBuffers(1, &tile.vbo);
            glDeleteBuffers(1, &tile.ebo);
            dispose(building);
            upload.reset();
            stats[7] = 2;
            stats[5] = 0;
            return;
          }
          building.push_back(tile);
        }
        const auto& tile = building.back();
        bool vertex      = offset < vb;
        size_t at        = vertex ? offset : offset - vb;
        size_t count     = std::min(budget, (vertex ? vb : ib) - at);
        GLenum target    = vertex ? GL_ARRAY_BUFFER : GL_ELEMENT_ARRAY_BUFFER;
        glBindBuffer(target, vertex ? tile.vbo : tile.ebo);
        const uint8_t* data = vertex ? (const uint8_t*)source.vertices.data() : (const uint8_t*)source.indices.data();
        glBufferSubData(target, at, count, data + at);
        if (glGetError() != GL_NO_ERROR) {
          dispose(building);
          upload.reset();
          stats[7] = 2;
          stats[5] = 0;
          return;
        }
        offset += count;
        budget -= count;
        stats[4].fetch_add(count);
        if (offset == vb + ib) {
          offset = 0;
          part++;
          std::vector<float>().swap(source.vertices);
          std::vector<uint32_t>().swap(source.indices);
        }
      }
      if (part == upload->chunks.size()) {
        dispose(resident);
        resident = std::move(building);
        building.clear();
        residentBytes = upload->bytes;
        bounds        = upload->bounds;
        stats[0]      = resident.size();
        stats[1]      = upload->triangles;
        stats[2]      = upload->vertices;
        stats[3]      = residentBytes;
        upload.reset();
        revision.fetch_add(1);
      }
      glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
    }
    void draw(GLuint program, const std::array<float, 16>& mvp, bool encodeSrgb, bool points) {
      GLboolean cull = glIsEnabled(GL_CULL_FACE);
      glDisable(GL_CULL_FACE);
      glEnable(GL_DEPTH_TEST);
      glDepthMask(GL_TRUE);
      glDisable(GL_BLEND);
      glUseProgram(program);
      glUniformMatrix4fv(glGetUniformLocation(program, "mvp"), 1, GL_FALSE, mvp.data());
      glUniform1i(glGetUniformLocation(program, "encodeSrgb"), encodeSrgb);
      glEnableVertexAttribArray(0);
      glEnableVertexAttribArray(1);
      int visibleChunks = 0;
      for (const auto& tile : resident) {
        if (!visible(tile.bounds, mvp)) continue;
        visibleChunks++;
        glBindBuffer(GL_ARRAY_BUFFER, tile.vbo);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, nullptr);
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, (void*)12);
        if (points)
          glDrawArrays(GL_POINTS, 0, tile.vertices);
        else {
          glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, tile.ebo);
          glDrawElements(GL_TRIANGLES, tile.indices, GL_UNSIGNED_INT, nullptr);
        }
      }
      stats[6] = visibleChunks;
      glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
      if (cull) glEnable(GL_CULL_FACE);
    }
    void clear() {
      dispose(resident);
      dispose(building);
      upload.reset();
      std::lock_guard<std::mutex> lock(mutex);
      pending.reset();
    }
  };
}  // namespace tlzscene
