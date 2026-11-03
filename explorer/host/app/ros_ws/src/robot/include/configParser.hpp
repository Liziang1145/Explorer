#pragma once

#include <yaml-cpp/yaml.h>
#include <string>

namespace WHU_ROBOT {

class param_t {
public:
	std::string cloud_topic;
	std::string odom_topic;

	std::string cloud_export_path;
	
	std::string remote_ip;
	int remote_port;
	std::string local_ip;
	int local_port;

	bool enable_bin_save;
	bool enable_pcd_trans;

	std::string odom_remote_ip;
	int odom_remote_port;
	std::string odom_local_ip;
	int odom_local_port;

	bool enable_odom_trans;

	std::string car_cmd_remote_ip;
	int car_cmd_remote_port;
	std::string car_cmd_local_ip;
	int car_cmd_local_port;
	std::string target_odom_topic;
	bool enable_cmd2ROS;

	std::string odom_unix_channel;
	std::string cmd_unix_channel;

	std::string merge_remote_ip;
	int merge_remote_port;
	std::string merge_local_ip;
	int merge_local_port;

	std::string state_msg_sync_enable;
	std::string state_msg_car_control_enable;

	std::string image_remote_ip;
	int image_remote_port;
	std::string image_local_ip;
	int image_local_port;

	std::string arm_unix_channel_station;
	std::string arm_unix_channel_solve;

	std::string arm_remote_ip;
	int arm_remote_port;
	std::string arm_local_ip;
	int arm_local_port;

	param_t(const std::string& filename){
		try {
			YAML::Node config = YAML::LoadFile(filename);
			cloud_topic = config["cloud_topic"].as<std::string>();
			odom_topic = config["odom_topic"].as<std::string>();
			cloud_export_path = config["cloud_export_path"].as<std::string>();
			remote_ip = config["remote_ip"].as<std::string>();
			remote_port = config["remote_port"].as<int>();
			local_ip = config["local_ip"].as<std::string>();
			local_port = config["local_port"].as<int>();
			enable_bin_save = config["enable_bin_save"].as<bool>();
			enable_pcd_trans = config["enable_pcd_trans"].as<bool>();

			odom_remote_ip = config["odom_remote_ip"].as<std::string>();
			odom_remote_port = config["odom_remote_port"].as<int>();
			odom_local_ip = config["odom_local_ip"].as<std::string>();
			odom_local_port = config["odom_local_port"].as<int>();
			enable_odom_trans = config["enable_odom_trans"].as<bool>();


			car_cmd_remote_ip = config["car_cmd_remote_ip"].as<std::string>();
			car_cmd_remote_port = config["car_cmd_remote_port"].as<int>();
			car_cmd_local_ip = config["car_cmd_local_ip"].as<std::string>();
			car_cmd_local_port = config["car_cmd_local_port"].as<int>();
			target_odom_topic = config["target_odom_topic"].as<std::string>();
			enable_cmd2ROS = config["enable_cmd2ROS"].as<bool>();

			odom_unix_channel = config["odom_unix_channel"].as<std::string>();
			cmd_unix_channel = config["cmd_unix_channel"].as<std::string>();


			merge_remote_ip = config["merge_remote_ip"].as<std::string>();
			merge_remote_port = config["merge_remote_port"].as<int>();
			merge_local_ip = config["merge_local_ip"].as<std::string>();
			merge_local_port = config["merge_local_port"].as<int>();


			state_msg_sync_enable = config["state_msg_sync_enable"].as<std::string>();
			state_msg_car_control_enable = config["state_msg_car_control_enable"].as<std::string>();

			image_remote_ip = config["image_remote_ip"].as<std::string>();
			image_remote_port = config["image_remote_port"].as<int>();
			image_local_ip = config["image_local_ip"].as<std::string>();
			image_local_port = config["image_local_port"].as<int>();

			arm_unix_channel_station = config["arm_unix_channel_station"].as<std::string>();
			arm_unix_channel_solve = config["arm_unix_channel_solve"].as<std::string>();

			arm_remote_ip = config["arm_remote_ip"].as<std::string>();
			arm_remote_port = config["arm_remote_port"].as<int>();
			arm_local_ip = config["arm_local_ip"].as<std::string>();
			arm_local_port = config["arm_local_port"].as<int>();



		} catch (const YAML::Exception& e) {
			throw std::runtime_error("Error parsing configuration file: " + std::string(e.what()));
		}
	}
};

class ctl_param_t {
public:
	std::string odom_topic;
	std::string target_odom_topic;
	std::string ctrl_topic;

	float delta_distance;
	float delta_yaw;
	float brake_distance;

	float p_vx;
	float p_vy;
	float p_wz;

	float d_vx;
	float d_vy;
	float d_wz;

	float max_v;
	float max_w;

	std::string state_msg_car_control_enable;

	ctl_param_t(const std::string& filename){
		try {
			YAML::Node config = YAML::LoadFile(filename);

			odom_topic = config["odom_topic"].as<std::string>();
			target_odom_topic = config["target_odom_topic"].as<std::string>();
			ctrl_topic = config["ctrl_topic"].as<std::string>();

			delta_distance = config["delta_distance"].as<float>();
			delta_yaw = config["delta_yaw"].as<float>();
			brake_distance = config["brake_distance"].as<float>();

			p_vx = config["p_vx"].as<float>();
			p_vy = config["p_vy"].as<float>();
			p_wz = config["p_wz"].as<float>();

			d_vx = config["d_vx"].as<float>();
			d_vy = config["d_vy"].as<float>();
			d_wz = config["d_wz"].as<float>();

			max_v = config["max_v"].as<float>();
			max_w = config["max_w"].as<float>();

			state_msg_car_control_enable = config["state_msg_car_control_enable"].as<std::string>();


		} catch (const YAML::Exception& e) {
			throw std::runtime_error("Error parsing configuration file: " + std::string(e.what()));
		}
	}
};

}//namespace WHU_robot