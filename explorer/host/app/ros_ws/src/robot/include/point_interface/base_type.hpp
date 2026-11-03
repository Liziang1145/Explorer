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

#include <Eigen/Dense>
#include <zpp_bits.h>
#include <atomic>
#include <aligned_allocator.hpp>
#include <shared_mutex>
#include <mutex>
#include <iostream>
#include <span>
#include <cassert>
#include <thread>
#include <array>
#include <mortonLUT.hpp>

template <typename ScalarType>
struct BasePoint;

struct CompressedPoint;

template <typename PointType, int PacketSize>
class PointPacket;

template <typename PointType>
class PointPoll;

template <typename ScalarType>
class PointBuffer;

template <typename Derived>
struct PointCloudAdaptor;

using BasePointf = BasePoint<float>;

template <typename T, size_t Alignment = 64>
using AlignedVector = std::vector<T, AlignedAllocator<T, Alignment>>;

template <typename ScalarType>
struct BasePoint
{
    // Default copy construct
    using Scalar = ScalarType;

    Eigen::Matrix<ScalarType, 4, 1> _pos = Eigen::Matrix<ScalarType, 4, 1>::Zero();
    Eigen::Matrix<ScalarType, 4, 1> _color = Eigen::Matrix<ScalarType, 4, 1>::Zero();
    Eigen::Matrix<ScalarType, 4, 1> _normal = Eigen::Matrix<ScalarType, 4, 1>::Zero();

        // ----- 可写 Block 版本 -----
    Eigen::Block<Eigen::Matrix<ScalarType,4,1>,3,1> xyz() {
      return _pos.template segment<3>(0);
    }
    Eigen::Block<Eigen::Matrix<ScalarType,4,1>,3,1> rgb() {
      return _color.template segment<3>(0);
    }
    Eigen::Block<Eigen::Matrix<ScalarType,4,1>,3,1> normal() {
      return _normal.template segment<3>(0);
    }

    // ----- 只读（const）Block 版本 -----
    Eigen::Block<const Eigen::Matrix<ScalarType,4,1>,3,1> xyz() const {
      return _pos.template segment<3>(0);
    }
    Eigen::Block<const Eigen::Matrix<ScalarType,4,1>,3,1> rgb() const {
      return _color.template segment<3>(0);
    }
    Eigen::Block<const Eigen::Matrix<ScalarType,4,1>,3,1> normal() const {
      return _normal.template segment<3>(0);
    }

    // Eigen::Matrix<ScalarType, 3, 1> &xyz() { return _pos.vec(); }
    // const Eigen::Matrix<ScalarType, 3, 1> &xyz() const { return _pos.vec(); }

    // Eigen::Matrix<ScalarType, 3, 1> &rgb() { return _color.vec(); }
    // const Eigen::Matrix<ScalarType, 3, 1> &rgb() const { return _color.vec(); }

    // Eigen::Matrix<ScalarType, 3, 1> &normal() { return _normal.vec(); }
    // const Eigen::Matrix<ScalarType, 3, 1> &normal() const { return _normal.vec(); }

    constexpr static size_t sized()
    {
        return 3 * 4 * sizeof(Scalar);
    }

    constexpr static auto serialize(auto &archive, auto &self)
    {
        return archive(self._pos[0], self._pos[1], self._pos[2], self._pos[3],
                       self._color[0], self._color[1], self._color[2], self._color[3],
                       self._normal[0], self._normal[1], self._normal[2], self._normal[3]);
    }
};

struct CompressedPoint
{
    using Scalar = uint64_t;
    uint32_t normal;      // 24 bit normal
    uint32_t color;       // 32 bit RGBA
    uint64_t morton_code; // 64bit

    CompressedPoint(uint64_t morton_code = 0, uint32_t color = 0, uint32_t normal = 0) : normal(normal), color(color), morton_code(morton_code) {}

    CompressedPoint(const Eigen::Vector4f &pt, uint32_t rgba32=0, uint32_t normal24 = 0): 
        normal{normal24},
        color{rgba32}
    {
        this->morton_code = CompressedPoint::encode_morton(pt);
        // this->color = 0;
        // this->normal = 0;
    }

    constexpr static uint32_t color_bit_mask = 0x00FFFFFF;

    constexpr static size_t sized()
    {
        return 16;
    }

    static uint64_t encode_morton(const Eigen::Vector4f &pt, const float voxel_size = 0.01)
    {
        using namespace mortonnd;
        constexpr int coord_offset = 1 << 20; // 1 << 20 = 1048576
        constexpr MortonNDLutEncoder_3D_64 encoder;
        const float inv_size = 1.0 / voxel_size;
        return static_cast<uint64_t>(encoder.Encode(floor_f(pt[0] * inv_size) + coord_offset, floor_f(pt[1] * inv_size) + coord_offset, floor_f(pt[2] * inv_size) + coord_offset));
    }

    static auto decode_morton(uint64_t morton_code, const float voxel_size = 0.01)
    {
        using namespace mortonnd;
        constexpr int coord_offset = 1 << 20; // 1 << 20 = 1048576
        constexpr MortonNDLutDecoder_3D_64 decoder;
        auto result = decoder.Decode(morton_code);
        Eigen::Vector4f pt = Eigen::Vector4f(static_cast<float>(static_cast<int32_t>(std::get<0>(result)) - coord_offset) * voxel_size,
                                             static_cast<float>(static_cast<int32_t>(std::get<1>(result)) - coord_offset) * voxel_size,
                                             static_cast<float>(static_cast<int32_t>(std::get<2>(result)) - coord_offset) * voxel_size,
                                             1.);
        return pt;
    }

    constexpr static auto serialize(auto &archive, auto &self)
    {
        return archive(self.normal, self.color, self.morton_code);
    }

    constexpr static int32_t floor_f(float x)
    {
        return static_cast<int32_t>(x + 32768.) - 32768;
    }
};

template <typename PointType, int PacketSize>
class PointPacket
{
    friend class PointPoll<PointType>;

public:
    using Scalar = typename PointType::Scalar;
    using Point = PointType;
    static constexpr int SerializedSize = Point::sized();
    static constexpr int MaxPointNum = (PacketSize - 8) / (64 / std::gcd(64, SerializedSize) * SerializedSize) * (64 / std::gcd(64, SerializedSize) * SerializedSize) / SerializedSize;
    static constexpr int TotalByte = SerializedSize * MaxPointNum + 12; // 8+4byte size to indicate the size of vector
    static constexpr uint16_t HEADER = 0xD0FD;

    PointPacket(PointType *pointer)
    {
        _points = std::span<Point>(pointer, MaxPointNum);
    }

    ~PointPacket() = default;

    void SetAttribute(const uint16_t id, const uint16_t length)
    {
        this->id = id;
        this->length = length;
    }

    uint16_t size() const
    {
        return length;
    }

    constexpr static auto serialize(auto &archive, auto &self)
    {
        auto result = archive(self.header, self.id, self.length, self.checksum, self._points);

        if constexpr (std::remove_cvref_t<decltype(archive)>::kind() == zpp::bits::kind::in)
        {
            if (self.header != HEADER)
            {
                throw std::runtime_error("Protocol error: Invalid header. Expected header: " + std::to_string(HEADER) + ", but got: " + std::to_string(self.header));
            }
        }
        return result;
    }

private:
    uint16_t header = HEADER;
    uint16_t id = 0;
    uint16_t length = 0;
    uint16_t checksum; // no crc now
    std::span<Point> _points;
};

template <typename PointType>
class PointPoll
{
    friend PointBuffer<typename PointType::Scalar>;

private:
    using Scalar = typename PointType::Scalar;
    using Point = PointType;
    using PacketPoll = std::vector<std::span<std::byte>>;
    using PacketPollPtr = std::shared_ptr<PacketPoll>;
    std::vector<Point, AlignedAllocator<Point>> _points;
    std::atomic<size_t> emptyPtrOffset = 0;
    std::atomic<size_t> pointNum = 0;
    std::atomic<size_t> copyCnt = 1;
    mutable std::shared_mutex rw_mutex;

public:
    std::vector<std::byte> internal_buffer;

    PointPoll()
    {
        _points.reserve(1024);
    };

    PointPoll(const size_t _size)
    {
        _points.reserve(_size);
    };

    ~PointPoll() = default;

    // thread-safe function
    size_t size() const
    {
        std::shared_lock lock(rw_mutex);
        return pointNum.load();
    }

    void AddPoint(const Point &point)
    {
        pointNum.fetch_add(1);
        emptyPtrOffset.fetch_add(1);
        {
            std::unique_lock lock(rw_mutex);
            _points.emplace_back(point);
        }
    }

    template <typename MemberType, size_t Alignment = 64>
    AlignedVector<MemberType, Alignment> ExtractMember(MemberType PointType::*member_ptr)
    {
        // std::unique_lock lock(rw_mutex);
        AlignedVector<MemberType, Alignment> result;
        result.reserve(this->size());
        for (const auto pt : _points)
        {
            result.emplace_back(pt.*member_ptr);
        }
        return result;
    }

    void clear()
    {
        std::unique_lock lock(rw_mutex);
        _points.clear();
        emptyPtrOffset = 0;
        pointNum = 0;
        copyCnt = 1;
    }

    // thread-safe function
    // Do not call this mannually, it's supposed to be called when receiving udp packets
    // It is highly not recommended to call this function with AddPoint()
    template <typename Packet>
        requires std::is_same<typename Packet::Scalar, Scalar>::value
    size_t DecodePacket(const std::vector<std::byte> &buffer)
    {
        size_t offset = emptyPtrOffset.fetch_add(Packet::MaxPointNum, std::memory_order_seq_cst);
        std::unique_lock<std::shared_mutex> lock(rw_mutex);
        if (_points.capacity() < pointNum.load() + 3 * copyCnt.load() * Packet::MaxPointNum)
        {
            size_t expected_size = (_points.capacity() + copyCnt.load() * Packet::MaxPointNum) * 3;
            _points.reserve(expected_size);
        }
        lock.unlock();

        copyCnt.fetch_add(1);
        // memcpy(_points.data() + offset, packet._points.data(), Packet::TotalByte);
        Packet packet(_points.data() + offset);
        zpp::bits::in{buffer, zpp::bits::size4b{}, zpp::bits::endian::little{}}(packet).or_throw();
        pointNum.fetch_add(packet.size());
        copyCnt.fetch_sub(1);
        return packet.size();
    }

    // automatically allocate threads
    template <typename Packet>
        requires std::is_same<typename Packet::Scalar, Scalar>::value
    const PacketPollPtr EncodePackets(const size_t startIndex, const size_t size, size_t NumOfThreads = 1)
    {
        std::mutex _mutex;
        assert(startIndex + size <= _points.size());
        size_t packetNum = size / Packet::MaxPointNum + 1;
        PacketPollPtr EncodedBuffer = std::make_shared<PacketPoll>();
        internal_buffer.reserve(Packet::TotalByte * packetNum * 2);
        internal_buffer.clear();
        std::vector<std::thread> thread_pool;
        std::vector<std::vector<int>> thread_packet_num(NumOfThreads);
        for (size_t i = 0; i < packetNum; i++)
        {
            thread_packet_num[i % NumOfThreads].push_back(i);
        }

        auto encodeTask = [&](const size_t thread_id)
        {
            auto packet_index = thread_packet_num[thread_id];
            for (size_t j = 0; j < packet_index.size(); j++)
            {
                Packet packet(_points.data() + startIndex + packet_index[j] * Packet::MaxPointNum);
                packet.SetAttribute(0, Packet::MaxPointNum);
                std::span<std::byte> currentView = std::span<std::byte>(this->internal_buffer.data() + packet_index[j] * Packet::TotalByte, Packet::TotalByte);
                auto out = zpp::bits::out(currentView, zpp::bits::size4b{}, zpp::bits::endian::little{});
                out(packet).or_throw();
                {
                    std::unique_lock<std::mutex> lock(_mutex);
                    EncodedBuffer->emplace_back(currentView);
                }
            }
        };

        for (size_t i = 0; i < NumOfThreads; i++)
        {
            thread_pool.emplace_back(encodeTask, i);
        }

        for (size_t i = 0; i < NumOfThreads; i++)
        {
            thread_pool[i].join();
        }
        return EncodedBuffer;
    }

    // should not be called by users
    constexpr static auto serialize(auto &archive, auto &self)
    {
        std::unique_lock lock(self.rw_mutex);
        self._points.resize(self.pointNum.load());
        size_t _emptyPtrOffset = self.emptyPtrOffset.load();
        size_t _pointNum = self.pointNum.load();
        size_t _copyCnt = self.copyCnt.load();
        auto result = archive(self._points, _emptyPtrOffset, _pointNum, _copyCnt);
        if constexpr (std::remove_cvref_t<decltype(archive)>::kind() == zpp::bits::kind::in)
        {
            self.emptyPtrOffset.store(_emptyPtrOffset);
            self.pointNum.store(_pointNum);
            self.copyCnt.store(_copyCnt);
        }
        return result;
    }
};
