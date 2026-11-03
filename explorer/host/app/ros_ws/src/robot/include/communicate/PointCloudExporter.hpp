// PointCloudExporter.hpp
#pragma once

#include <pcl/point_types.h>
#include <pcl/point_cloud.h>
#include <vector>
#include <string>
#include <memory>
#include <iostream>
#include <tuple>
#include <algorithm>

#include "base_type.hpp"
#include "configParser.hpp"

#include <Eigen/Eigen>

#include <Eigen/Core>
#include <Eigen/Dense>
#include <pcl/io/pcd_io.h>
#include <pcl/filters/voxel_grid.h>
#include <pcl/keypoints/uniform_sampling.h>
#include <pcl/common/concatenate.h>
#include <eigen_conversions/eigen_msg.h>


#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"
#include "cloud_msg/cloud_sender.hpp"
#include "cloud_msg/cloud_msg.h"

#include "algo.hpp"

static constexpr size_t PACKET_MTU = 1400; // 可调整
using _PacketType = PointPacket<CompressedPoint, PACKET_MTU>;
using _SenderType = cloud_msg;
using _PollType = PointPoll<CompressedPoint>;

static constexpr size_t __pack_size = _PacketType::TotalByte;

namespace WHU_ROBOT{


class PointCloudExporter {
public:

	explicit PointCloudExporter(const param_t& _param, size_t initial_pool_size = 1024);

	void init(void);
	void stop(void);

	void addPoints(const pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr& _cloud);

	bool saveToBinaryFile(const std::string &filename, size_t num_threads);

private:

	/*-----------------------------consts-----------------------------------------*/
	// static constexpr float filter_resolution = 0.05f; 
	// static constexpr uint8_t filter_type = 0;//type 0 none; type 1 VoxelGrid; type 2 UniformSampling
	// static constexpr size_t transmit_poll_cnt_limit = 10; // transmit_poll到达此次数后发送
	// static constexpr size_t pcd_sample_cnt_limit = 1; 
	static constexpr size_t transmit_frame_cnt_limit = 10; //每多少帧雷达点云压一次传输包
	static constexpr uint32_t neighbor_range = 3;//range_meter = 2^neighbor_range * 0.01
	static constexpr size_t neighbor_limit_cnt = 10;

	static constexpr uint8_t process_type = 1;//1-查表，发增量	2-全局动态点云

	/*-----------------------------functions-----------------------------------------*/
	uint32_t intensityToHeatmapRGBA(const float& _intensity);
	// pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr cloudFilter(const 
	// 	pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr& cloud, float resolution = filter_resolution);
	bool pointAvailable(_PollType& current_global_poll, const Eigen::Vector3f& point);
	// void transmitCloud(void);
	void transmitCloud(_PollType& transmit_poll);
	/*-----------------------------objs-----------------------------------------*/
	param_t param;

	const size_t initial_pool_size_; // 初始池大小


	_PollType global_point_poll_;
	// std::shared_ptr<PointPoll<CompressedPoint>> transmit_poll_ptr_;
	// TaskBase* transmit_task_ptr_ = nullptr; // 传输任务
	// IMsgQueue* transmit_poll_msg_queue_ptr_ = nullptr; // 传输任务的消息队列

	// bool enable_bin_save_; 
	// bool enable_pcd_trans_; 

	// size_t transmit_poll_cnt_ = 0;// transmit_poll使用计数

	asio::io_context io_context;
	std::thread t;
	CommChannel<ChannelMode::UDP, CloudSender> channel;
	MsgQueue send_mq;
};


inline  PointCloudExporter::PointCloudExporter(const param_t& _param, size_t initial_pool_size):
	param{_param},
	initial_pool_size_{initial_pool_size},
	global_point_poll_{initial_pool_size_},
	io_context{},
	channel(io_context, param.local_ip, param.local_port, 
		param.remote_ip, param.remote_port),
	send_mq(RingBuffer<_SenderType>{50})
{
	std::cout<<"PointCloudExporter constructing"<<std::endl;

	if(CloudSender::length != __pack_size){
		std::cout<<"\033[31m点云传输包大小与协议不匹配！\033[0m"<<std::endl;
	}
}



// inline void PointCloudExporter::transmitCloud(void){
// 	std::cout << "cloud transmiting " << std::endl;
// 	if(transmit_task_ptr_){
// 		auto packets_ptr = transmit_poll_ptr_->EncodePackets<_PacketType>(0, transmit_poll_ptr_->size(), 4);
// 		for(auto& pkt : *packets_ptr){
// 			std::shared_ptr<_SenderType> sender_ptr = std::make_shared<_SenderType>(pkt);
// 			if(transmit_poll_msg_queue_ptr_){
// 				transmit_poll_msg_queue_ptr_->enqueue(&sender_ptr);
// 			} else {
// 				std::cerr << "Error: transmit_poll_msg_queue_ptr_ is null!" << std::endl;
// 			}
// 		}	
// 	}
// 	std::cout << "cloud transmitted " << std::endl;
// }

// inline PointCloudExporter::PointCloudExporter(size_t initial_pool_size): point_poll_{initial_pool_size}
// {
// 	initial_pool_size_ = initial_pool_size;
// 	transmit_poll_ptr_ = std::make_shared<PointPoll<CompressedPoint>>(initial_pool_size);
// }

// inline PointCloudExporter::PointCloudExporter(TaskBase& transmit_task ,bool enable_pcd_trans,bool enable_bin_save, size_t initial_pool_size):
// 	transmit_task_ptr_{&transmit_task},
// 	enable_bin_save_{enable_bin_save},
// 	enable_pcd_trans_{enable_pcd_trans},
// 	point_poll_{initial_pool_size}
// {
// 	initial_pool_size_ = initial_pool_size;
// 	transmit_poll_ptr_ = std::make_shared<PointPoll<CompressedPoint>>(initial_pool_size);

// }




inline void PointCloudExporter::init(void){
	std::cout << "PointCloudExporter Starting..." << std::endl;

	if(param.enable_pcd_trans){

		std::cout << "pcd_trans enabled" << std::endl;
		// transmit_poll_msg_queue_ptr_ = new MsgQueueImpl<std::shared_ptr<_SenderType>>(1024);
		// if(transmit_poll_msg_queue_ptr_ != nullptr){
		// 	transmit_task_ptr_->bind_msg_queue(std::string("PoindCloudPacket"), transmit_poll_msg_queue_ptr_);
		// } else{
		// 	std::cout << "transmit_poll_msg_queue_ptr_ nullptr" << std::endl;
		// }

		// std::cout << "transmit_task Starting..." << std::endl;
		// transmit_task_ptr_->start();

		channel.bind_message_queue("cloud_sender", ParserType::Sender, send_mq);

		while(!channel.enable_sender()){std::cout<<
			"PointCloudExporter: waiting enable_sender"<<std::endl;}

		std::cout << "cloud transmit Starting..." << std::endl;

		t = std::thread([this]() { io_context.run(); });

	} else {
		std::cout << "pcd_trans not enable" << std::endl;
	}
	std::cout << "PointCloudExporter Started" << std::endl;
}

inline void PointCloudExporter::stop(void){
	if(param.enable_pcd_trans){
	std::cout << "PointCloudExporter Stopping..." << std::endl;
		io_context.stop();
		t.join();
	std::cout << "PointCloudExporter Stopped" << std::endl;
	}
}


/**	
*	TODO，需求: 
* 	1, 取消采样模式，将所有帧全部压入，每次发送前进行下采样
	2, 下采样不使用PCL库而是直接对pack处理，主要是去重
	3, 通过algo.hpp，遍历点获取其周围点，周围点多于一定数量视为无效点
	4, 只发送增量
	
	例如编码精度1cm，近邻范围5cm，10帧一次发送，分为全局poll和发送poll
	将10帧所有点全部压入->1cm精度意义下的去重->计算纯增量点送入发送poll
	->遍历发送poll,若增量点在全局poll的5cm范围内有大量点则从发送poll去除
	->发送
	问题：
	5cm有大量点的话，是否还存入全局poll；
	复制与内存分配耗时问题
*/	
inline void PointCloudExporter::addPoints(const pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr& cloud)
{
	constexpr int PatternVoxel = 8;

// std::cout<<"DEBUG: CALL FROM addPoints"<<std::endl;
	if(param.enable_bin_save || param.enable_pcd_trans){
		if constexpr(process_type == 1){
			static size_t transmit_frame_cnt = 0;
			transmit_frame_cnt++;

			static _PollType transmit_poll{initial_pool_size_};

			size_t __cnt = 0;

			auto raw_points = global_point_poll_.ExtractMember<uint64_t>(&CompressedPoint::morton_code);
			std::sort(raw_points.begin(), raw_points.end());

			for (const auto& pt : cloud->points) {
				if (!std::isfinite(pt.x)) continue;

				size_t neighborPointCount = RangeSearchCnt<PatternVoxel>(raw_points, 
					Eigen::Vector3f{pt.x, pt.y, pt.z}, 
					neighbor_range);

				if(neighborPointCount <= neighbor_limit_cnt){
					CompressedPoint base_pt{Eigen::Vector4f( pt.x, pt.y, pt.z, pt.intensity ), 
						intensityToHeatmapRGBA( pt.intensity)};

					global_point_poll_.AddPoint(base_pt);
					transmit_poll.AddPoint(base_pt);

					__cnt++;
				}
			}
			std::cout<<"PointCloudExporter: get available point num: " << __cnt <<std::endl;

			if(transmit_frame_cnt >= transmit_frame_cnt_limit){
				transmitCloud(transmit_poll);
				transmit_poll.clear();
				transmit_frame_cnt = 0;
			}
		} else if constexpr (process_type == 2){

			constexpr uint32_t __mask = 0xA0'00'00'00;

			static size_t transmit_frame_cnt = 0;
			transmit_frame_cnt++;

			static _PollType transmit_poll{initial_pool_size_};

			size_t __cnt = 0;

			// auto raw_points = global_point_poll_.ExtractMember<uint64_t>(&CompressedPoint::morton_code);
			// std::sort(raw_points.begin(), raw_points.end());

			for (const auto& pt : cloud->points) {
				if (!std::isfinite(pt.x)) continue;

				// size_t neighborPointCount = RangeSearchCnt<PatternVoxel>(raw_points, 
				// 	Eigen::Vector3f{pt.x, pt.y, pt.z}, 
				// 	neighbor_range);

				// if(neighborPointCount <= neighbor_limit_cnt){
					CompressedPoint base_pt{Eigen::Vector4f( pt.x, pt.y, pt.z, pt.intensity ), 
						intensityToHeatmapRGBA( pt.intensity),__mask};

					// global_point_poll_.AddPoint(base_pt);
					transmit_poll.AddPoint(base_pt);

					__cnt++;
				// }
			}
			std::cout<<"PointCloudExporter: get available point num: " << __cnt <<std::endl;

			if(transmit_frame_cnt >= transmit_frame_cnt_limit){
				transmitCloud(transmit_poll);
				transmit_poll.clear();
				transmit_frame_cnt = 0;
			}
		}
	}
	
}


inline void PointCloudExporter::transmitCloud(_PollType& transmit_poll){
	if(param.enable_pcd_trans){
		std::cout << "cloud transmiting " << std::endl;
		auto packets_ptr = transmit_poll.EncodePackets<_PacketType>(0, transmit_poll.size(), 4);

		for(auto& pkt : *packets_ptr){
			
			send_mq.enqueue(std::move(pkt));
			
		}	
		

		std::cout << "cloud transmit enqueueed " << std::endl;
	}
}


inline uint32_t PointCloudExporter::intensityToHeatmapRGBA(const float& _intensity) {
	// 将 intensity 限定到 [0, 255]
	float intensity = std::max(0.0f, std::min(255.0f, _intensity));

	int r, g, b;
	if (intensity < 128.0f) {
		r = 0;
		g = static_cast<int>(255.0f * intensity / 128.0f);
		b = 255;
	} else {
		float scaled = (intensity - 128.0f) / 127.0f;
		r = static_cast<int>(255.0f * scaled);
		g = 255;
		b = static_cast<int>(255.0f - 255.0f * scaled);
	}

	const uint8_t alpha = 255;  // 不透明
	// 按 0xRRGGBBAA 打包（大端意义上的 RGBA）
	return
		(static_cast<uint32_t>(r) << 24) |
		(static_cast<uint32_t>(g) << 16) |
		(static_cast<uint32_t>(b) <<  8) |
		static_cast<uint32_t>(alpha);
}

inline bool PointCloudExporter::saveToBinaryFile(const std::string &filename, size_t num_threads)
{
	if(param.enable_bin_save){

	std::vector<std::byte> buffer;
	auto out = zpp::bits::out(buffer,zpp::bits::endian::big{});
	out(global_point_poll_).or_throw();

	// Step 2: 打开二进制文件准备写入
	std::ofstream file(filename, std::ios::out | std::ios::binary);
	if (!file.is_open())
	{
		std::cerr << "Failed to open file: " << filename << std::endl;
		return false;
	}


		file.write(
		reinterpret_cast<const char *>(buffer.data()),
		static_cast<std::streamsize>(buffer.size())
	);

	// 4. 检查写入状态
	if (!file.good()) {
		std::cerr << "Error writing to file: " << filename << std::endl;
		file.close();
		return false;
	}

	file.close();
	}
	return true;
}


// inline pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr
// PointCloudExporter::cloudFilter(const pcl::PointCloud<pcl::PointXYZINormal>::ConstPtr& cloud,	float resolution)
// {

// 	if constexpr(filter_type == 0){//none
// 		return cloud;
// 	} else if constexpr(filter_type == 1){//VoxelGrid
// 		pcl::VoxelGrid<pcl::PointXYZINormal> voxel_grid;
// 		voxel_grid.setInputCloud(cloud);
// 		voxel_grid.setLeafSize(resolution, resolution, resolution);

// 		pcl::PointCloud<pcl::PointXYZINormal>::Ptr filtered_cloud(new pcl::PointCloud<pcl::PointXYZINormal>);
// 		voxel_grid.filter(*filtered_cloud);
// 		return filtered_cloud;
// 	} else if constexpr(filter_type == 2){//UniformSampling
// 		pcl::UniformSampling<pcl::PointXYZINormal> uniform_sampling;
// 		uniform_sampling.setInputCloud(cloud);
// 		uniform_sampling.setRadiusSearch(resolution);

// 		pcl::PointCloud<pcl::PointXYZINormal>::Ptr filtered_cloud(new pcl::PointCloud<pcl::PointXYZINormal>);
// 		uniform_sampling.filter(*filtered_cloud);
// 		return filtered_cloud;
// 	} else {
// 		std::cerr << "Invalid filter type. Using VoxelGrid by default." << std::endl;
// 		return cloud;
// 	}
// }


};//namespace WHU_robot