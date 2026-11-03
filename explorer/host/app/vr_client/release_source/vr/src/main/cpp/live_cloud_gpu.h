#pragma once
#include <array>
#include <atomic>
#include <mutex>
#include <vector>
#include <cstring>
namespace livecloud {
  using Mat                   = std::array<float, 16>;
  static const char* vertex   = R"(#version 300 es
precision highp float;layout(location=0) in vec3 position;layout(location=1) in vec4 color;
uniform mat4 mvp;out vec3 rgb;out float alpha;
vec3 linearRGB(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
void main(){gl_Position=color.a>0.?mvp*vec4(position,1.):vec4(2.,2.,2.,1.);gl_PointSize=2.5;rgb=linearRGB(color.rgb);alpha=color.a;})";
  static const char* fragment = R"(#version 300 es
precision highp float;in vec3 rgb;in float alpha;uniform bool encodeSrgb;out vec4 frag;
vec3 srgb(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
void main(){frag=vec4(encodeSrgb?srgb(rgb):rgb,alpha);})";
  class Gpu {
    std::mutex mutex;
    std::atomic<long long> requested{0};
    long long current = 0;
    std::vector<uint8_t> pending;
    Mat nextMatrix{}, matrix{};
    bool dirty    = false;
    GLuint buffer = 0;
    size_t count  = 0;

  public:
    std::atomic<bool> visible{false};
    std::atomic<long long> stats[4]{};
    void reset(long long generation) {
      std::lock_guard<std::mutex> g(mutex);
      if (generation < requested) return;
      requested = generation;
      pending.clear();
      dirty   = false;
      visible = false;
    }
    bool offer(long long generation, std::vector<uint8_t> bytes, Mat transform) {
      std::lock_guard<std::mutex> g(mutex);
      if (generation != requested || bytes.size() > 1920000 || bytes.size() % 16) return false;
      pending    = std::move(bytes);
      nextMatrix = transform;
      dirty      = true;
      return true;
    }
    void tick() {
      std::vector<uint8_t> bytes;
      {
        std::lock_guard<std::mutex> g(mutex);
        if (current != requested) {
          if (buffer) glDeleteBuffers(1, &buffer);
          buffer   = 0;
          count    = 0;
          current  = requested;
          stats[0] = stats[1] = 0;
        }
        if (!dirty) return;
        bytes  = std::move(pending);
        matrix = nextMatrix;
        dirty  = false;
      }
      if (!buffer) glGenBuffers(1, &buffer);
      glBindBuffer(GL_ARRAY_BUFFER, buffer);
      glBufferData(GL_ARRAY_BUFFER, bytes.size(), bytes.empty() ? nullptr : bytes.data(), GL_DYNAMIC_DRAW);
      if (glGetError() != GL_NO_ERROR) {
        stats[3] = 1;
        count    = 0;
        return;
      }
      count    = bytes.size() / 16;
      stats[0] = count;
      stats[1] = bytes.size();
      stats[2]++;
    }
    void draw(GLuint program, const Mat& vp, bool encode) {
      if (current != requested || !visible || !count) return;
      Mat mvp{};
      for (int c = 0; c < 4; c++)
        for (int r = 0; r < 4; r++)
          for (int k = 0; k < 4; k++) mvp[c * 4 + r] += vp[k * 4 + r] * matrix[c * 4 + k];
      glEnable(GL_DEPTH_TEST);
      glDepthMask(GL_FALSE);
      glEnable(GL_BLEND);
      glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
      glUseProgram(program);
      glUniformMatrix4fv(glGetUniformLocation(program, "mvp"), 1, GL_FALSE, mvp.data());
      glUniform1i(glGetUniformLocation(program, "encodeSrgb"), encode);
      glBindBuffer(GL_ARRAY_BUFFER, buffer);
      glEnableVertexAttribArray(0);
      glEnableVertexAttribArray(1);
      glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 16, nullptr);
      glVertexAttribPointer(1, 4, GL_UNSIGNED_BYTE, GL_TRUE, 16, (void*)12);
      glDrawArrays(GL_POINTS, 0, count);
      glDepthMask(GL_TRUE);
    }
    void clear() {
      if (buffer) glDeleteBuffers(1, &buffer);
      buffer = 0;
      count  = 0;
    }
  };
}  // namespace livecloud
