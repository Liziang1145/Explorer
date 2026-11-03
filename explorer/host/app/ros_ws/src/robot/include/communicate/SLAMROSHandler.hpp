#pragma once

#define PCL_NO_PRECOMPILE


#include <ros/ros.h>
#include <Eigen/Eigen>

#include <Eigen/Core>
#include <Eigen/Dense>
#include <Eigen/StdVector>
#include <sensor_msgs/PointCloud2.h>
#include <nav_msgs/Odometry.h>
#include <pcl_conversions/pcl_conversions.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <std_msgs/Bool.h>

#include "configParser.hpp"
#include "PointCloudExporter.hpp"
#include "OdomExporter.hpp"

#include "comm_channel.hpp"


#include <chrono>

namespace WHU_ROBOT {

class SLAMROSHandler {
public:
	SLAMROSHandler(const param_t& _param, const ros::NodeHandle& _nh): 
		nh{_nh}, 
		param{_param},
		odom_exporter{param},
		cloud_exporter{param}
	{
		std::cout<<"SLAMROSHandler constructing"<<std::endl;
		cloud_sub = nh.subscribe<sensor_msgs::PointCloud2>(param.cloud_topic, 10, &SLAMROSHandler::cloudCallback, this);
		odom_sub = nh.subscribe<nav_msgs::Odometry>(param.odom_topic, 10, &SLAMROSHandler::odomCallback, this);

		state_msg_sync_sub = nh.subscribe<std_msgs::Bool>(param.state_msg_sync_enable, 10,
			 &SLAMROSHandler::stateOdomSyncCallback, this);
	}

	~SLAMROSHandler() {
		
	}

	void init(void);
	void stop(void);

private:
	ros::NodeHandle nh;
	param_t param;
	ros::Subscriber cloud_sub;
	ros::Subscriber odom_sub;

	PointCloudExporter cloud_exporter;
	OdomExporter<ChannelMode::Unix> odom_exporter;

	ros::Subscriber state_msg_sync_sub;

	void cloudCallback(const sensor_msgs::PointCloud2ConstPtr& msg);
	void odomCallback(const nav_msgs::OdometryConstPtr& msg);
	void stateOdomSyncCallback(const std_msgs::Bool::ConstPtr& msg);
};

inline void SLAMROSHandler::stateOdomSyncCallback(const std_msgs::Bool::ConstPtr& msg){
	if(msg->data) odom_exporter.pushSyncSignal();
}

inline void SLAMROSHandler::init(void){
	cloud_exporter.init();
	odom_exporter.init();
}

inline void SLAMROSHandler::stop(void){
	cloud_exporter.stop();
	odom_exporter.stop();
	ROS_INFO("Saving point cloud data to binary file: %s", param.cloud_export_path.c_str());
	cloud_exporter.saveToBinaryFile(param.cloud_export_path,4);
}

inline void SLAMROSHandler::cloudCallback(const sensor_msgs::PointCloud2ConstPtr& msg){
	pcl::PointCloud<pcl::PointXYZINormal>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZINormal>);


	pcl::fromROSMsg(*msg, *cloud);

	ROS_INFO("Received point cloud with %zu points", cloud->size());
	
	auto t0 = std::chrono::steady_clock::now();

	cloud_exporter.addPoints(cloud);
	
	auto t1 = std::chrono::steady_clock::now();
	ROS_INFO("Added points to exporter in %.3f ms", std::chrono::duration<double, std::milli>(t1 - t0).count());
}

inline void SLAMROSHandler::odomCallback(const nav_msgs::OdometryConstPtr& msg){
if(param.enable_odom_trans){
		// 1. 从 ROS 消息头提取时间戳（单位：秒 + 纳秒），转换为 uint64_t 纳秒
	uint64_t sec  = static_cast<uint64_t>(msg->header.stamp.sec);
	uint64_t nsec = static_cast<uint64_t>(msg->header.stamp.nsec);
	uint64_t time_ns = sec * 1000000000ull + nsec;

	// 2. 提取基础坐标（base_pos）
	Eigen::Vector3f base_pos;
	base_pos.x() = static_cast<float>(msg->pose.pose.position.x);
	base_pos.y() = static_cast<float>(msg->pose.pose.position.y);
	base_pos.z() = static_cast<float>(msg->pose.pose.position.z);

	// 3. 提取基础朝向（base_quat）：ROS 中 quaternion 为 (x, y, z, w)，
	//    Eigen::Quaternionf 构造时参数顺序为 (w, x, y, z)
	const auto& q = msg->pose.pose.orientation;
	Eigen::Quaternionf base_quat(
		static_cast<float>(q.w),
		static_cast<float>(q.x),
		static_cast<float>(q.y),
		static_cast<float>(q.z)
	);

	// 4. 调用 OdomExporter，将提取到的 time、position、quaternion 传入
	odom_exporter.addOdom(time_ns, base_pos, base_quat);

	ROS_INFO("Received Odometry:");
	ROS_INFO("  time (ns): %llu", static_cast<unsigned long long>(time_ns));
	ROS_INFO("  position: [x=%.3f, y=%.3f, z=%.3f]",
		base_pos.x(), base_pos.y(), base_pos.z());
	ROS_INFO("  orientation (quat): [w=%.3f, x=%.3f, y=%.3f, z=%.3f]",
		base_quat.w(), base_quat.x(), base_quat.y(), base_quat.z());
}
}

}// namespace WHU_ROBOT