#pragma once

#include <vector>
#include <string>
#include <memory>
#include <iostream>
#include <tuple>
#include <algorithm>


#include <Eigen/Eigen>

#include <Eigen/Core>
#include <Eigen/Dense>
#include <Eigen/Geometry>


#include <ros/ros.h>
#include <nav_msgs/Odometry.h>
#include <tf/transform_datatypes.h>
#include <std_msgs/Bool.h>

#include "configParser.hpp"


#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"
#include "whole_body_msg/whole_body_receiver.hpp"
#include "whole_body_msg/whole_body_msg.h"


namespace WHU_ROBOT{

	template <ChannelMode Mode = ChannelMode::UDP>
	class CarCmd2ROSHandler{
	public:
		explicit CarCmd2ROSHandler(const param_t& _param, const ros::NodeHandle& _nh);

		~CarCmd2ROSHandler(){}

		void init(void);
		void stop(void);

		void exec(void);
	private:
		ros::NodeHandle nh;
		param_t param;
		ros::Publisher target_odom_pub;
		ros::Publisher state_sync_pub;
		ros::Publisher state_car_enable_pub;

		asio::io_context io_context;
		std::thread t;
		CommChannel<Mode, WholeBodyReceiver> channel;
		MsgQueue recv_mq;

		asio::executor_work_guard<asio::io_context::executor_type> work_guard = 
			asio::make_work_guard(io_context);

		void cmdPublish(const Eigen::Vector3f& position,
                               const Eigen::Quaternionf& orientation);

		auto decodePacket(const whole_body_msg& packet) -> std::tuple<Eigen::Vector3f, Eigen::Quaternionf>{
			    // Copy the first three floats into a Vector3f
			Eigen::Vector3f pos;
			pos << packet.base_pos[0],
				packet.base_pos[1],
				packet.base_pos[2];

			// Copy all four floats into a Quaternionf (w, x, y, z)
			Eigen::Quaternionf quat{};
			quat.x() = packet.base_quat[0];  // x
			quat.y() = packet.base_quat[1];  // y
			quat.z() = packet.base_quat[2];  // z
			quat.w() = packet.base_quat[3];   // w
			

			maskParser(packet.mask);

			return { pos, quat };
		}
		
		void maskParser(const uint16_t& mask);
	};

	template<>
	inline CarCmd2ROSHandler<ChannelMode::UDP>::CarCmd2ROSHandler(const param_t& _param, 
							const ros::NodeHandle& _nh):
		nh{_nh},
		param{_param},
		io_context{},
		channel(io_context, param.car_cmd_local_ip, param.car_cmd_local_port, 
			param.car_cmd_remote_ip, param.car_cmd_remote_port),
		recv_mq(RingBuffer<whole_body_msg>{10})
	{
		std::cout<<"CarCmd2ROSHandler constructing UDP"<<std::endl;
		target_odom_pub = nh.advertise<nav_msgs::Odometry>(param.target_odom_topic, 10);
		state_sync_pub = nh.advertise<std_msgs::Bool>(param.state_msg_sync_enable, 10);
		state_car_enable_pub = nh.advertise<std_msgs::Bool>(param.state_msg_car_control_enable, 10);
	}

	template<>
	inline CarCmd2ROSHandler<ChannelMode::Unix>::CarCmd2ROSHandler(const param_t& _param, 
							const ros::NodeHandle& _nh):
		nh{_nh},
		param{_param},
		io_context{},
		channel(io_context, param.cmd_unix_channel, "/tmp/cmd_unix_channel_remote"),
		recv_mq(RingBuffer<whole_body_msg>{10})
	{
		std::cout<<"CarCmd2ROSHandler constructing Unix"<<std::endl;
		target_odom_pub = nh.advertise<nav_msgs::Odometry>(param.target_odom_topic, 10);
		state_sync_pub = nh.advertise<std_msgs::Bool>(param.state_msg_sync_enable, 10);
		state_car_enable_pub = nh.advertise<std_msgs::Bool>(param.state_msg_car_control_enable, 10);
	}

	template<ChannelMode Mode>
	inline void CarCmd2ROSHandler<Mode>::exec(void){
		whole_body_msg recv_data;
		// std::cout << "DEBUG:---------------------"<<recv_mq.size()<<std::endl;
		if(!recv_mq.empty()){
			recv_mq.dequeue(recv_data);
			ROS_INFO("-----------------------------get command data----------------------------------");
			auto [_position, _orientation] = decodePacket(recv_data);
			cmdPublish(_position, _orientation);
		}
	}

	template<ChannelMode Mode>
	inline void CarCmd2ROSHandler<Mode>::init(void){

 		channel.bind_message_queue("whole_body_receiver", ParserType::Receiver, recv_mq);
		
  		while(!channel.enable_receiver()){std::cout<<
			"CarCmd2ROSHandler: waiting enable_receiver"<<std::endl;}

  		t = std::thread([this]() { io_context.run(); });


		ROS_INFO("CarCmd2ROS start");
	}

	template<ChannelMode Mode>
	inline void CarCmd2ROSHandler<Mode>::stop(void){
		std::cout << "CarCmd2ROSHandler Stopping..." << std::endl;
		io_context.stop();
		// while(!t.joinable()) {std::cout<<"CarCmd2ROSHandler: waiting thread joinable"<<std::endl;}
		t.join();
		std::cout << "CarCmd2ROSHandler Stopped" << std::endl;

	}

	template<ChannelMode Mode>
	inline void CarCmd2ROSHandler<Mode>::cmdPublish(const Eigen::Vector3f& position,
		const Eigen::Quaternionf& orientation)
	{
		nav_msgs::Odometry odom_msg;

		// 设置时间戳和坐标系
		odom_msg.header.stamp = ros::Time::now();
		odom_msg.header.frame_id = "odom";
		odom_msg.child_frame_id = "base_link";

		// 设置位置
		odom_msg.pose.pose.position.x = position.x();
		odom_msg.pose.pose.position.y = position.y();
		odom_msg.pose.pose.position.z = position.z();

		// Eigen::Quaternionf 转 geometry_msgs::Quaternion
		geometry_msgs::Quaternion q_msg;
		q_msg.x = orientation.x();
		q_msg.y = orientation.y();
		q_msg.z = orientation.z();
		q_msg.w = orientation.w();
		odom_msg.pose.pose.orientation = q_msg;

		target_odom_pub.publish(odom_msg);
	}

	template<ChannelMode Mode>
	inline void CarCmd2ROSHandler<Mode>::maskParser(const uint16_t& mask){
		static constexpr uint16_t MASK_CAR_ENABLE = 0b0100'0000'0000'0000;//base control
		static constexpr uint16_t MASK_SYNC_ENABLE = 0b0000'0000'1000'0000;//pose request
		
		//--debug
		std::cout << "mask = 0x"
		<< std::hex << std::uppercase << std::setw(4) << std::setfill('0')
		<< mask
		<< std::dec    // 恢复为十进制输出格式
		<< std::endl;
		//--debug

		std_msgs::Bool msg_sync;
		std_msgs::Bool msg_car_enable;

		if (mask & MASK_CAR_ENABLE) {
			msg_car_enable.data = true;
			state_car_enable_pub.publish(msg_car_enable);
		} else {
			msg_car_enable.data = false;
			state_car_enable_pub.publish(msg_car_enable);
		}

		if (mask & MASK_SYNC_ENABLE) {
			msg_sync.data = true;
			state_sync_pub.publish(msg_sync);
		} else {
			msg_sync.data = false;
			state_sync_pub.publish(msg_sync);
		}

		if((mask & MASK_SYNC_ENABLE) && (mask & MASK_CAR_ENABLE)){
			std::cout<<"Warning: MASK_CAR_ENABLE should be disabled when set MASK_SYNC_ENABLE"<<std::endl;
		}
	}


};//namespace WHU_ROBOT

