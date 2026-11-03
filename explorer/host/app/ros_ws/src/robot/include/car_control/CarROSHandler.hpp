#pragma once

#include <ros/ros.h>
#include <nav_msgs/Odometry.h>
#include <yhs_can_msgs/ctrl_cmd.h>
#include <std_msgs/Bool.h>

#include "CarControlBase.hpp"
#include "configParser.hpp"

namespace WHU_ROBOT{

	class CarROSHandler{
	public:
		explicit CarROSHandler(const ctl_param_t& _param, const ros::NodeHandle& _nh, 
				std::unique_ptr<CarControllerBase> _controller_ptr):
			nh{_nh},
			param{_param},
			controller_ptr{std::move(_controller_ptr)}
		{
			odom_sub = nh.subscribe<nav_msgs::Odometry>(param.odom_topic, 10, 
				&CarROSHandler::odomCallback, this);
			target_odom_sub = nh.subscribe<nav_msgs::Odometry>(param.target_odom_topic, 10, 
				&CarROSHandler::targetOdomCallback, this);
			ctrl_pub = nh.advertise<yhs_can_msgs::ctrl_cmd>(param.ctrl_topic, 10);
			state_msg_control_enable_sub = nh.subscribe<std_msgs::Bool>(param.state_msg_car_control_enable,
				 10, &CarROSHandler::stateControlEnableCallback, this);
		}

		~CarROSHandler(){}

		void exec(void);
	private:
		ros::NodeHandle nh;
		ctl_param_t param;
		ros::Subscriber odom_sub;
		ros::Subscriber target_odom_sub;
		ros::Publisher ctrl_pub;

		ros::Subscriber state_msg_control_enable_sub;

		bool if_enable_control = 0;

		std::unique_ptr<CarControllerBase> controller_ptr;

		void odomCallback(const nav_msgs::OdometryConstPtr& msg);
		void targetOdomCallback(const nav_msgs::OdometryConstPtr& msg);
		void ctrlPublish(const CarState& cmd);

		void stateControlEnableCallback(const std_msgs::Bool::ConstPtr& msg);
	};


	inline void CarROSHandler::stateControlEnableCallback(const std_msgs::Bool::ConstPtr& msg){
		if(msg->data){
			if_enable_control = 1;
		} else {
			if_enable_control = 0;
		}
	}


	inline void CarROSHandler::exec(void){
		CarState cmd;
		cmd = controller_ptr->computeControlOnce();
		ctrlPublish(cmd);
		// ROS_INFO("exec once");
	}


	inline void CarROSHandler::ctrlPublish(const CarState& cmd){
		yhs_can_msgs::ctrl_cmd msg;
		msg.ctrl_cmd_gear = cmd.mode;
		msg.ctrl_cmd_x_linear = cmd.base_lin_vel.x();
		msg.ctrl_cmd_z_angular = cmd.base_ang_vel.z();
		msg.ctrl_cmd_y_linear = cmd.base_lin_vel.y();

		ctrl_pub.publish(msg);
	}


	inline void CarROSHandler::odomCallback(const nav_msgs::OdometryConstPtr& msg){

		static uint32_t __cnt = 0;

			// 1. 从 ROS 消息头提取时间戳（单位：秒 + 纳秒），转换为 uint64_t 纳秒
		uint64_t sec  = static_cast<uint64_t>(msg->header.stamp.sec);
		uint64_t nsec = static_cast<uint64_t>(msg->header.stamp.nsec);
		uint64_t time_ns = sec * 1000000000ull + nsec;

		// 2. 提取基础坐标（base_pos）
		Eigen::Vector3f _base_pos;
		_base_pos.x() = static_cast<float>(msg->pose.pose.position.x);
		_base_pos.y() = static_cast<float>(msg->pose.pose.position.y);
		_base_pos.z() = static_cast<float>(msg->pose.pose.position.z);

		// 3. 提取基础朝向（base_quat）：ROS 中 quaternion 为 (x, y, z, w)，
		//    Eigen::Quaternionf 构造时参数顺序为 (w, x, y, z)
		const auto& q = msg->pose.pose.orientation;
		Eigen::Quaternionf _base_quat(
			static_cast<float>(q.w),
			static_cast<float>(q.x),
			static_cast<float>(q.y),
			static_cast<float>(q.z)
		);

		CarState _odomState;

		_odomState.mode = 2;
		_odomState.cnt = __cnt++;
		_odomState.time = time_ns;
		_odomState.base_pos = _base_pos;
		_odomState.base_quat = _base_quat;

		_odomState.base_lin_vel.setZero();
		_odomState.base_ang_vel.setZero();


		controller_ptr->feedCurrent(_odomState);


		// ROS_INFO("Received Odometry");
		// ROS_INFO("  time (ns): %llu", static_cast<unsigned long long>(time_ns));
		// ROS_INFO("  position: [x=%.3f, y=%.3f, z=%.3f]",
		// 	base_pos.x(), base_pos.y(), base_pos.z());
		// ROS_INFO("  orientation (quat): [w=%.3f, x=%.3f, y=%.3f, z=%.3f]",
		// 	base_quat.w(), base_quat.x(), base_quat.y(), base_quat.z());
	}


	inline void CarROSHandler::targetOdomCallback(const nav_msgs::OdometryConstPtr& msg){

		static constexpr uint8_t MASK_ENABLE_CNT = 0b0000'0010;
		static constexpr uint8_t MASK_ENABLE_CONTROL = 0b1000'0000;

		static uint32_t __cnt = 0;

			// 1. 从 ROS 消息头提取时间戳（单位：秒 + 纳秒），转换为 uint64_t 纳秒
		uint64_t sec  = static_cast<uint64_t>(msg->header.stamp.sec);
		uint64_t nsec = static_cast<uint64_t>(msg->header.stamp.nsec);
		uint64_t time_ns = sec * 1000000000ull + nsec;

		// 2. 提取基础坐标（base_pos）
		Eigen::Vector3f _base_pos;
		_base_pos.x() = static_cast<float>(msg->pose.pose.position.x);
		_base_pos.y() = static_cast<float>(msg->pose.pose.position.y);
		_base_pos.z() = static_cast<float>(msg->pose.pose.position.z);

		// 3. 提取基础朝向（base_quat）：ROS 中 quaternion 为 (x, y, z, w)，
		//    Eigen::Quaternionf 构造时参数顺序为 (w, x, y, z)
		const auto& q = msg->pose.pose.orientation;
		Eigen::Quaternionf _base_quat(
			static_cast<float>(q.w),
			static_cast<float>(q.x),
			static_cast<float>(q.y),
			static_cast<float>(q.z)
		);

		CarState _odomState;

		_odomState.mode = MASK_ENABLE_CNT;

		if(if_enable_control){
			_odomState.mode |= MASK_ENABLE_CONTROL;
		}

		_odomState.cnt = __cnt++;
		_odomState.time = time_ns;
		_odomState.base_pos = _base_pos;
		_odomState.base_quat = _base_quat;

		_odomState.base_lin_vel.setZero();
		_odomState.base_ang_vel.setZero();


		controller_ptr->feedTarget(_odomState);


		// ROS_INFO("Received target");
		// ROS_INFO("  time (ns): %llu", static_cast<unsigned long long>(time_ns));
		// ROS_INFO("  position: [x=%.3f, y=%.3f, z=%.3f]",
		// 	base_pos.x(), base_pos.y(), base_pos.z());
		// ROS_INFO("  orientation (quat): [w=%.3f, x=%.3f, y=%.3f, z=%.3f]",
		// 	base_quat.w(), base_quat.x(), base_quat.y(), base_quat.z());
	}

};//namespace WHU_ROBOT
