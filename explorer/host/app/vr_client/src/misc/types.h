#pragma once

#include <Eigen/Dense>
#include <vector>
#include <iostream>
#include <array>

struct PointCloud
{
    std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> points_coord; // xyz size
    std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> points_color; // rgb alpha
    std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> points_norm;

    // allocate memory for point cloud
    PointCloud(int _size)
    {
        points_coord.reserve(_size);
        points_color.reserve(_size);
        points_norm.reserve(_size);
        points_coord.clear();
        points_color.clear();
        points_norm.clear();
    }

    ~PointCloud() = default;

    size_t size() const
    {
        if (points_coord.size() != points_color.size())
        {
            std::cerr << "inconsistent size" << std::endl;
        }
        return points_coord.size();
    }

    void *getPointBasePtr()
    {
        return reinterpret_cast<void *>(points_coord.data());
    }

    void *getColorBasePtr()
    {
        return reinterpret_cast<void *>(points_color.data());
    }

    void *getNormBasePtr()
    {
        return reinterpret_cast<void *>(points_norm.data());
    }

    // better not using this tho
    void pushPoint(const Eigen::Vector4f &point_coord, const Eigen::Vector4f &point_color, const Eigen::Vector3f &point_norm)
    {
        Eigen::Vector4f _norm(point_norm.x(), point_norm.y(), point_norm.z(), 0);
        points_coord.emplace_back(point_coord);
        points_color.emplace_back(point_color);
        points_norm.emplace_back(_norm);
        return;
    }
};

struct Mesh
{
    std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> vertexes;
    std::vector<Eigen::Vector4f, Eigen::aligned_allocator<Eigen::Vector4f>> normals; // normal of vertex
    std::vector<std::array<uint32_t, 3>> indexes;                                    // triangle representation

    Mesh(int _size)
    {
        vertexes.reserve(_size);
        normals.reserve(_size);
        indexes.reserve(_size);
        vertexes.clear();
        normals.clear();
        indexes.clear();
    }

    ~Mesh() = default;

    size_t size() const
    {
        if (vertexes.size() != normals.size())
        {
            std::cerr << "inconsistent size" << std::endl;
        }
        return vertexes.size();
    }

    size_t triangle_size() const
    {
        return indexes.size();
    }

    void *getVertexBasePtr()
    {
        return reinterpret_cast<void *>(vertexes.data());
    }

    void *getNormBasePtr()
    {
        return reinterpret_cast<void *>(normals.data());
    }

    void *getIndexBasePtr()
    {
        return reinterpret_cast<void *>(indexes.data());
    }

    void addVertex(const Eigen::Vector4f &vertex_coord, const Eigen::Vector3f &vertex_norm)
    {
        Eigen::Vector4f _norm(vertex_norm.x(), vertex_norm.y(), vertex_norm.z(), 0);
        vertexes.emplace_back(vertex_coord);
        normals.emplace_back(_norm);
        return;
    }

    void addTriangle(const std::array<uint32_t, 3> &triangle_index)
    {
        indexes.emplace_back(triangle_index);
        return;
    }
};