#pragma once

#include <Eigen/Eigen>
#include <span>

#include <iostream>
#include <Eigen/Core>
#include <Eigen/Dense>
#include <Eigen/StdVector>

#include "configParser.hpp"
#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"


#include "nav_state_msg/nav_state_msg.h"
#include "nav_state_msg/nav_state_sender.hpp"
#include "nav_state_msg/nav_state_receiver.hpp"

#include "whole_body_msg/whole_body_msg.h"
#include "whole_body_msg/whole_body_sender.hpp"
#include "whole_body_msg/whole_body_receiver.hpp"



namespace WHU_ROBOT {

	template <ChannelMode Mode = ChannelMode::UDP>
	class MergeHandler {
		public:
			explicit MergeHandler(const param_t& _param);

			~MergeHandler(){}

			void init(void);
			void stop(void);

			void exec(void);

		private:
			param_t param;
			asio::io_context io_context;
			std::thread t;
			CommChannel<ChannelMode::UDP, NavStateSender, WholeBodyReceiver> remote_channel;
			CommChannel<Mode, NavStateReceiver> local_channel_odom_rcv;
			CommChannel<Mode, WholeBodySender> local_channel_carcmd_snd;

			CommChannel<ChannelMode::Unix, WholeBodySender,NavStateReceiver> local_channel_arm;


			MsgQueue recv_mq_remote;
			MsgQueue send_mq_remote;
			MsgQueue recv_mq_local_odom;
			MsgQueue send_mq_local_carcmd;

			MsgQueue recv_mq_local_arm;
			MsgQueue send_mq_local_arm;

			nav_state_msg stateMerge(nav_state_msg& msg_from_odom, nav_state_msg& msg_from_arm){
				nav_state_msg rtn = msg_from_arm;

				rtn.mask |= msg_from_odom.mask;
				rtn.base_pos = msg_from_odom.base_pos;
				rtn.base_quat = msg_from_odom.base_quat;

				return rtn;
			}
	};

	template<>
	inline MergeHandler<ChannelMode::Unix>::MergeHandler(const param_t& _param):
		param{_param},
		io_context{},
		remote_channel(io_context, param.merge_local_ip, param.merge_local_port, 
			param.merge_remote_ip, param.merge_remote_port),
		local_channel_odom_rcv(io_context, param.odom_unix_channel, "/tmp/odom_unix_channel_remote"),
		local_channel_carcmd_snd(io_context, "/tmp/cmd_unix_channel_local", param.cmd_unix_channel),
		local_channel_arm(io_context, param.arm_unix_channel_station, param.arm_unix_channel_solve),
		recv_mq_remote(RingBuffer<whole_body_msg>{10}),
		send_mq_remote(RingBuffer<nav_state_msg>{10}),
		recv_mq_local_odom(RingBuffer<nav_state_msg>{10}),
		send_mq_local_carcmd(RingBuffer<whole_body_msg>{10}),
		recv_mq_local_arm(RingBuffer<nav_state_msg>{10}),
		send_mq_local_arm(RingBuffer<whole_body_msg>{10})
	{
		std::cout<<"MergeHandler constructing"<<std::endl;
	}

	template<>
	inline MergeHandler<ChannelMode::UDP>::MergeHandler(const param_t& _param):
		param{_param},
		io_context{},
		remote_channel(io_context, param.merge_local_ip, param.merge_local_port, 
			param.merge_remote_ip, param.merge_remote_port),
		local_channel_odom_rcv(io_context, param.odom_remote_ip, param.odom_remote_port, 
			param.odom_local_ip, param.odom_local_port),
		local_channel_carcmd_snd(io_context, param.car_cmd_remote_ip, param.car_cmd_remote_port, 
			param.car_cmd_local_ip, param.car_cmd_local_port),
		local_channel_arm(io_context, param.arm_unix_channel_station, param.arm_unix_channel_solve),
		recv_mq_remote(RingBuffer<whole_body_msg>{10}),
		send_mq_remote(RingBuffer<nav_state_msg>{10}),
		recv_mq_local_odom(RingBuffer<nav_state_msg>{10}),
		send_mq_local_carcmd(RingBuffer<whole_body_msg>{10}),
		recv_mq_local_arm(RingBuffer<nav_state_msg>{10}),
		send_mq_local_arm(RingBuffer<whole_body_msg>{10})
	{
		std::cout<<"MergeHandler constructing"<<std::endl;
	}

	template<ChannelMode Mode>
	inline void MergeHandler<Mode>::init(void){
		std::cout << "MergeHandler Starting..." << std::endl;

		remote_channel.bind_message_queue("nav_state_sender", ParserType::Sender, send_mq_remote);
		remote_channel.bind_message_queue("whole_body_receiver", ParserType::Receiver, recv_mq_remote);
		local_channel_odom_rcv.bind_message_queue("nav_state_receiver", ParserType::Receiver, 
				recv_mq_local_odom);
		local_channel_carcmd_snd.bind_message_queue("whole_body_sender", ParserType::Sender, 
				send_mq_local_carcmd);
		local_channel_arm.bind_message_queue("nav_state_receiver", ParserType::Receiver, recv_mq_local_arm);
		local_channel_arm.bind_message_queue("whole_body_sender", ParserType::Sender, send_mq_local_arm);

		while(!remote_channel.enable_receiver()){std::cout<<"1"<<std::endl;}
		while(!remote_channel.enable_sender()){std::cout<<"2"<<std::endl;}
		while(!local_channel_odom_rcv.enable_receiver()){std::cout<<"3"<<std::endl;}
		while(!local_channel_carcmd_snd.enable_sender()){std::cout<<"4"<<std::endl;}
		while(!local_channel_arm.enable_receiver()){std::cout<<"5"<<std::endl;}
		while(!local_channel_arm.enable_sender()){std::cout<<"6"<<std::endl;}

		t = std::thread([this]() { io_context.run(); });
		
		std::cout << "MergeHandler Start" << std::endl;
	}

	template<ChannelMode Mode>
	inline void MergeHandler<Mode>::stop(void){
		std::cout << "MergeHandler Stopping..." << std::endl;

		io_context.stop();
		t.join();

		std::cout << "MergeHandler Stopped" << std::endl;
	}

	template<ChannelMode Mode>
	inline void MergeHandler<Mode>::exec(void){
		// std::cout << "DEBUG:---------------------"<<recv_mq.size()<<std::endl;

		static nav_state_msg recv_odom{};
		static nav_state_msg recv_arm{};
		 whole_body_msg recv_remote_data;
		 nav_state_msg merged_msg;

		static bool get_local_odom = 0;
		static bool get_local_arm = 1;
		
		if(!recv_mq_local_odom.empty()){
			if(recv_mq_local_odom.dequeue(recv_odom))
			{
				std::cout<<"get odom data"<<std::endl;
				get_local_odom = 1;
			} else {std::cout<<"wrong odom data"<<std::endl;}
		}

		if(!recv_mq_local_arm.empty()){
			if(recv_mq_local_arm.dequeue(recv_arm)){
				std::cout<<"get arm data"<<std::endl;
				get_local_arm = 1;
			}else {std::cout<<"wrong arm data"<<std::endl;}
		}

		if(get_local_odom && get_local_arm){
			merged_msg = stateMerge(recv_odom,recv_arm);
			send_mq_remote.enqueue(merged_msg);
		}

		if(!recv_mq_remote.empty()){
			
			recv_mq_remote.dequeue(recv_remote_data);
			std::cout<<"get command data"<<std::endl;
			
			send_mq_local_carcmd.enqueue(recv_remote_data);
			send_mq_local_arm.enqueue(recv_remote_data);
		}

	}

}//namespace WHU_ROBOT
