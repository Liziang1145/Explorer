#pragma once
// Runtime-owned GLB geometry, flattened into the official grip coordinate frame.
// Textures/animations are deliberately replaced by our static matte material.
#define CGLTF_IMPLEMENTATION
#include "third_party/cgltf.h"
#include <algorithm>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <vector>

namespace tlzcontroller {
  struct Mesh {
    // position, normal, linear base colour (three floats each).
    std::vector<float> vertices;
    float bounds[6] = {-.025f, -.025f, -.06f, .025f, .025f, .06f};
    int source      = 0;  // 0: built-in fallback; 1: XR_FB_render_model
  };
  inline void triangle(Mesh& m, const float* a, const float* b, const float* c, const float* color, const float* normals = nullptr) {
    float u[3], v[3];
    for (int k = 0; k < 3; k++) {
      u[k] = b[k] - a[k];
      v[k] = c[k] - a[k];
    }
    float n[3] = {u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]};
    float l    = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (l < 1e-10f) return;
    for (float& x : n) x /= l;
    const float* p[3] = {a, b, c};
    for (int j = 0; j < 3; j++)
      for (int k = 0; k < 9; k++) m.vertices.push_back(k < 3 ? p[j][k] : k < 6 ? (normals ? normals[j * 3 + k - 3] : n[k - 3]) : color[k - 6]);
  }
  inline Mesh fallback() {
    Mesh m;
    const int faces[36] = {0, 2, 1, 1, 2, 3, 4, 5, 6, 5, 7, 6, 0, 1, 4, 1, 5, 4, 2, 6, 3, 3, 6, 7, 0, 4, 2, 2, 4, 6, 1, 3, 5, 3, 7, 5};
    float p[8][3];
    for (int i = 0; i < 8; i++)
      for (int k = 0; k < 3; k++) p[i][k] = m.bounds[k + ((i & (1 << k)) ? 3 : 0)];
    for (int i = 0; i < 36; i += 3) {
      const float bright[3] = {.68f, .72f, .76f}, dark[3] = {.10f, .13f, .17f};
      triangle(m, p[faces[i]], p[faces[i + 1]], p[faces[i + 2]], i < 12 ? bright : dark);
    }
    return m;
  }
  inline Mesh load(const std::vector<uint8_t>& glb) {
    if (glb.size() < 20 || glb.size() > 16 * 1024 * 1024) throw std::runtime_error("GLB size");
    cgltf_options options{};
    options.type    = cgltf_file_type_glb;
    cgltf_data* raw = nullptr;
    if (cgltf_parse(&options, glb.data(), glb.size(), &raw) != cgltf_result_success) throw std::runtime_error("GLB parse");
    std::unique_ptr<cgltf_data, decltype(&cgltf_free)> data(raw, cgltf_free);
    // Never open files/URLs from a GLB. Only its embedded binary buffer is allowed.
    if (raw->buffers_count != 1 || raw->buffers[0].uri || !raw->bin || raw->nodes_count > 4096 || raw->scenes_count == 0)
      throw std::runtime_error("GLB embedded scene required");
    if (cgltf_load_buffers(&options, raw, nullptr) != cgltf_result_success || cgltf_validate(raw) != cgltf_result_success)
      throw std::runtime_error("GLB validation");
    const cgltf_scene* scene = raw->scene ? raw->scene : &raw->scenes[0];
    Mesh m;
    m.source = 1;
    for (int k = 0; k < 3; k++) {
      m.bounds[k]     = 100;
      m.bounds[k + 3] = -100;
    }
    for (size_t ni = 0; ni < raw->nodes_count; ni++) {
      const cgltf_node* node = &raw->nodes[ni];
      if (!node->mesh) continue;
      const cgltf_node* root = node;
      unsigned depth         = 0;
      while (root->parent) {
        if (++depth > 64) throw std::runtime_error("GLB hierarchy");
        root = root->parent;
      }
      bool inScene = false;
      for (size_t j = 0; j < scene->nodes_count; j++) inScene |= scene->nodes[j] == root;
      if (!inScene) continue;
      if (node->skin) throw std::runtime_error("Skinned controller unsupported");
      float t[16];
      cgltf_node_transform_world(node, t);
      for (float x : t)
        if (!std::isfinite(x)) throw std::runtime_error("GLB transform");
      for (size_t pi = 0; pi < node->mesh->primitives_count; pi++) {
        const auto& p = node->mesh->primitives[pi];
        if (p.type != cgltf_primitive_type_triangles || p.has_draco_mesh_compression || p.targets_count)
          throw std::runtime_error("Unsupported controller primitive");
        const cgltf_accessor* positions = nullptr;
        const cgltf_accessor* normal    = nullptr;
        for (size_t ai = 0; ai < p.attributes_count; ai++) {
          if (p.attributes[ai].type == cgltf_attribute_type_position) positions = p.attributes[ai].data;
          if (p.attributes[ai].type == cgltf_attribute_type_normal) normal = p.attributes[ai].data;
        }
        if (!positions || positions->type != cgltf_type_vec3 || positions->is_sparse
            || (normal && (normal->type != cgltf_type_vec3 || normal->is_sparse || normal->count != positions->count)))
          throw std::runtime_error("Controller positions/normals");
        size_t count = p.indices ? p.indices->count : positions->count;
        if (count % 3 || count > 300000 || m.vertices.size() / 9 + count > 300000
            || (p.indices && (p.indices->type != cgltf_type_scalar || p.indices->is_sparse)))
          throw std::runtime_error("Controller triangle budget");
        float color[3] = {.72f, .75f, .78f};
        if (p.material && p.material->has_pbr_metallic_roughness)
          for (int k = 0; k < 3; k++) {
            float value = p.material->pbr_metallic_roughness.base_color_factor[k];
            if (!std::isfinite(value)) throw std::runtime_error("Controller material color");
            color[k] = std::clamp(value, .04f, .85f);
          }
        // Inverse transpose of the node's linear transform, up to scalar determinant.
        const float co[9] = {t[5] * t[10] - t[9] * t[6], t[9] * t[2] - t[1] * t[10], t[1] * t[6] - t[5] * t[2],
                             t[8] * t[6] - t[4] * t[10], t[0] * t[10] - t[8] * t[2], t[4] * t[2] - t[0] * t[6],
                             t[4] * t[9] - t[8] * t[5],  t[8] * t[1] - t[0] * t[9],  t[0] * t[5] - t[4] * t[1]};
        float determinant = t[0] * co[0] + t[4] * co[1] + t[8] * co[2];
        if (std::abs(determinant) < 1e-10f) throw std::runtime_error("Singular controller node");
        for (size_t i = 0; i < count; i += 3) {
          float xyz[3][3], norm[9];
          for (int j = 0; j < 3; j++) {
            size_t ix = p.indices ? cgltf_accessor_read_index(p.indices, i + j) : i + j;
            float v[3], n[3];
            if (ix >= positions->count || !cgltf_accessor_read_float(positions, ix, v, 3)) throw std::runtime_error("Controller index");
            for (int k = 0; k < 3; k++) {
              xyz[j][k] = t[k] * v[0] + t[4 + k] * v[1] + t[8 + k] * v[2] + t[12 + k];
              if (!std::isfinite(xyz[j][k]) || std::abs(xyz[j][k]) > 1) throw std::runtime_error("Controller bounds");
            }
            if (normal) {
              if (!cgltf_accessor_read_float(normal, ix, n, 3)) throw std::runtime_error("Controller normal");
              float length = 0;
              for (int k = 0; k < 3; k++) {
                norm[j * 3 + k] = (co[k * 3] * n[0] + co[k * 3 + 1] * n[1] + co[k * 3 + 2] * n[2]) / determinant;
                length += norm[j * 3 + k] * norm[j * 3 + k];
              }
              if (!std::isfinite(length) || length < 1e-12f) throw std::runtime_error("Controller normal length");
              for (int k = 0; k < 3; k++) norm[j * 3 + k] /= std::sqrt(length);
            }
          }
          size_t before = m.vertices.size();
          triangle(m, xyz[0], xyz[1], xyz[2], color, normal ? norm : nullptr);
          if (m.vertices.size() != before)
            for (auto& v : xyz)
              for (int k = 0; k < 3; k++) {
                m.bounds[k]     = std::min(m.bounds[k], v[k]);
                m.bounds[k + 3] = std::max(m.bounds[k + 3], v[k]);
              }
        }
      }
    }
    if (m.vertices.empty()) throw std::runtime_error("Empty controller mesh");
    for (int k = 0; k < 3; k++)
      if (m.bounds[k + 3] - m.bounds[k] < .001f || m.bounds[k + 3] - m.bounds[k] > .5f) throw std::runtime_error("Controller physical scale");
    return m;
  }
}  // namespace tlzcontroller
