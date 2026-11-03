#pragma once

#include "TaskBase.hpp"
#include "base_type.hpp"

#include <atomic>
#include <chrono>
#include "render_msg.h"
#include "pose_msg.h"
#include "algo.hpp"

namespace Schedule {

  class MappingTask : public TaskBase {
  public:
  protected:
    double now_seconds() {
      using namespace std::chrono;
      auto now = steady_clock::now();
      auto dur = now.time_since_epoch();
      return duration_cast<duration<double>>(dur).count();
    }
    void task() override {
      auto pose_msg_queue  = quiry_msg_queue("pose_msg");
      auto cloud_msg_queue = quiry_msg_queue("cloud_msg");
      auto cam_msg_queue   = quiry_msg_queue("cam_msg");
      auto map_info_queue  = quiry_msg_queue("map_info");
      auto cam_info_queue  = quiry_msg_queue("cam_info");

      PointPoll<CompressedPoint> compressPoll;
      PointPoll<CompressedPoint> receivePoll;
      PointPoll<CompressedPoint> camReceivePoll;
      PointPoll<CompressedPoint> camPoll;
      bool init = false;
      // std::shared_ptr<MapInfo> m_info[2]={std::make_shared<MapInfo>(),std::make_shared<MapInfo>()};

      // PoseInfo pose_info, last_pose_info;
      pose_msg current_pose, last_pose;
      int packet_cnt            = 0;
      int cam_packet_cnt        = 0;
      uint8_t update_lidar_flag = 0;
      uint8_t update_cam_flag   = 0;
      while (1) {
        std::shared_ptr<std::vector<std::byte>> cloud_msg;
        std::shared_ptr<std::vector<std::byte>> cam_msg;
        if (cloud_msg_queue->dequeue(cloud_msg)) {
          packet_cnt++;
          receivePoll.DecodePacket<PointPacket<CompressedPoint, 1400>>(*cloud_msg);
          if (packet_cnt > 300) {
            packet_cnt = 0;

            // sort self
            receivePoll.sort();
            // delete dead points
            compressPoll.reduce_life();
            // merge
            compressPoll.merge(receivePoll);
            // clear
            receivePoll.clear();
            if (!init) {
              init              = true;
              update_lidar_flag = true;
              last_time         = now_seconds();
            }

            if ((now_seconds() - last_time >= 3) && init) {
              update_lidar_flag = true;
              last_time         = now_seconds();
            }
            // if (compressPoll.size() < 1000000)
            // {

            //     update_lidar_flag = true;
            // }

            std::cout << "compressPoll.size() " << compressPoll.size() << std::endl;
            // add time update
            //  update_lidar_flag = true;
          }
        }

        if (cam_msg_queue->dequeue(cam_msg)) {
          cam_packet_cnt++;
          camReceivePoll.DecodePacket<PointPacket<CompressedPoint, 1400>>(*cam_msg);
          if (cam_packet_cnt > 300) {
            // sort self
            camReceivePoll.sort();
            // delete dead points
            camPoll.reduce_life();
            // merge
            camPoll.merge(camReceivePoll);
            // clear
            camReceivePoll.clear();

            cam_packet_cnt  = 0;
            update_cam_flag = true;
          }
        }

        if (pose_msg_queue->dequeue(current_pose)) {
          Eigen::Vector4f currPose(current_pose.position.data());
          Eigen::Vector4f lastPose(last_pose.position.data());
          auto distance = (currPose.head<3>() - lastPose.head<3>()).norm();
          if (distance > 1) {
            update_lidar_flag = true;
          }
          last_pose = current_pose;
        }

        if (update_lidar_flag) {
          std::shared_ptr<render_msg> m_info = std::make_shared<render_msg>();
          active_buffer                      = (active_buffer + 1) % 2;
          // Eigen::Vector3f currPos = pose_info.position.head<3>();
          Eigen::Vector3f currPos = Eigen::Vector3f(current_pose.position[0], current_pose.position[1], current_pose.position[2]);

          // mark invisible points
          compressPoll.RangeMarkInvisible<8>(PatternOffsets<8>(currPos, 8), 8);

          // extract some surrounding points.
          auto blockPts = compressPoll.RangeExtract<8>(PatternOffsets<8>(currPos, 12), 12);

          m_info->size            = 0;
          m_info->points_resource = std::make_shared<AlignedVector<uint64_t>>();
          m_info->colors_resource = std::make_shared<AlignedVector<uint32_t>>();

          m_info->points_resource->reserve(blockPts.size());
          m_info->colors_resource->reserve(blockPts.size());
          for (const auto pt : blockPts) {
            m_info->points_resource->emplace_back(pt.morton_code);
            m_info->colors_resource->emplace_back(pt.color);
          }
          m_info->offset = static_cast<uint32_t>(blockPts.size());
          m_info->size += static_cast<uint32_t>(blockPts.size());

          // downsampled pt
          auto FullPts        = compressPoll.ExtractMember<uint64_t>(&CompressedPoint::morton_code);
          auto DownsampledPts = VoxelGridDownsample(FullPts, 6);

          m_info->points_resource->reserve(blockPts.size() + DownsampledPts.size());
          m_info->colors_resource->reserve(blockPts.size() + DownsampledPts.size());
          for (const auto pt : DownsampledPts) {
            m_info->points_resource->emplace_back(pt);
            m_info->colors_resource->emplace_back(0xFFFFFFFF);
          }
          m_info->size += static_cast<uint32_t>(DownsampledPts.size());

          // add camera

          // std::cout<<"size "<<m_info->size<<std::endl;
          // std::cout<<"offset "<<m_info->offset<<std::endl;
          // std::cout<<"pt size "<<m_info->points_resource->size()<<std::endl;
          // std::cout<<"colorr size "<<m_info->colors_resource->size()<<std::endl;

          map_info_queue->enqueue(m_info);
          update_lidar_flag = false;
          // last_pose_info = pose_info;
        }

        if (update_cam_flag) {
          std::shared_ptr<render_msg> m_info = std::make_shared<render_msg>();
          m_info->size                       = 0;
          m_info->points_resource            = std::make_shared<AlignedVector<uint64_t>>();
          m_info->colors_resource            = std::make_shared<AlignedVector<uint32_t>>();
          m_info->points_resource->reserve(camPoll.size());
          m_info->colors_resource->reserve(camPoll.size());
          auto ContigPts = camPoll.GetRawData();
          for (const auto pt : ContigPts) {
            m_info->points_resource->emplace_back(pt.morton_code);
            m_info->colors_resource->emplace_back(pt.color);
          }
          m_info->offset = 0;
          m_info->size   = static_cast<uint32_t>(camPoll.size());
          cam_info_queue->enqueue(m_info);
          update_cam_flag = false;
        }

        // currently update cam will not reset

        std::this_thread::sleep_for(std::chrono::milliseconds(1));
        timer_counter++;
      }
    }

  private:
    uint32_t active_buffer = 0;
    uint64_t timer_counter = 0;
    double last_time;
  };
};  // namespace Schedule