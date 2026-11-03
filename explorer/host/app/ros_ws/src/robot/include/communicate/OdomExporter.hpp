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

#include "configParser.hpp"

#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"
#include "nav_state_msg/nav_state_sender.hpp"
#include "nav_state_msg/nav_state_msg.h"


namespace WHU_ROBOT{

template <ChannelMode Mode = ChannelMode::UDP>
class OdomExporter {
public:
	explicit OdomExporter(const param_t& _param);

	void init(void);
	void stop(void);

	void addOdom(const uint64_t& time, const Eigen::Vector3f& base_pos, const Eigen::Quaternionf& base_quat);

	void pushSyncSignal(void);

private:

	/*-----------------------------consts-----------------------------------------*/

	/*-----------------------------functions-----------------------------------------*/
	/*-----------------------------objs-----------------------------------------*/

	param_t param;

	asio::io_context io_context;
	std::thread t;
	CommChannel<Mode, NavStateSender> channel;
	MsgQueue send_mq;

	size_t sync_cnt = 0;

	size_t popSyncSignal(void);
};

template<ChannelMode Mode>
inline 	void OdomExporter<Mode>::pushSyncSignal(void){
	sync_cnt++;
	std::cout<<"\033[32mOdomExporter: get sync request\033[0m"<<std::endl;
}

template<ChannelMode Mode>
inline size_t OdomExporter<Mode>::popSyncSignal(void){
	return sync_cnt>0 ? sync_cnt-- : 0;
}

template<ChannelMode Mode>
inline void OdomExporter<Mode>::addOdom(const uint64_t& time, 
	const Eigen::Vector3f& base_pos, const Eigen::Quaternionf& base_quat)
{
	static constexpr uint16_t MASK_ODOM_SYNC_ANSWER = 0b0000'0000'0100'0000;

	static uint32_t __cnt = 0;

	nav_state_msg data{};

	if(popSyncSignal()){
		std::cout<<"\033[33m" << "sync send back" << "\033[0m" << std::endl;
		data.mask = MASK_ODOM_SYNC_ANSWER;
	} else {
		data.mask = 0;
	}
	data.cnt = __cnt++;
	data.time = time;

	data.base_pos[0] = base_pos.x();
	data.base_pos[1] = base_pos.y();
	data.base_pos[2] = base_pos.z();
	data.base_pos[3] = 0.0f;
		
	data.base_quat[0] = base_quat.x();
	data.base_quat[1] = base_quat.y();
	data.base_quat[2] = base_quat.z();
	data.base_quat[3] = base_quat.w();

	send_mq.enqueue(std::move(data));

}
 

template<>
inline OdomExporter<ChannelMode::UDP>::OdomExporter(const param_t& _param):
	param{_param},
	io_context{},
	channel(io_context, param.odom_local_ip, param.odom_local_port, 
		param.odom_remote_ip, param.odom_remote_port),
	send_mq(RingBuffer<nav_state_msg>{10})
{
	std::cout<<"OdomExporter constructing"<<std::endl;
}


template<>
inline OdomExporter<ChannelMode::Unix>::OdomExporter(const param_t& _param):
	param{_param},
	io_context{},
	channel(io_context, "/tmp/odom_unix_channel_local", param.odom_unix_channel),
	send_mq(RingBuffer<nav_state_msg>{10})
{
	std::cout<<"OdomExporter constructing"<<std::endl;
}

template<ChannelMode Mode>
inline void OdomExporter<Mode>::init(void){
	std::cout << "OdomExporter Starting..." << std::endl;
	if(param.enable_odom_trans){
		std::cout << "odom_trans enabled" << std::endl;

 		channel.bind_message_queue("nav_state_sender", ParserType::Sender, send_mq);
		
  		while(!channel.enable_sender()){std::cout<<
			"OdomExporter: waiting enable_sender"<<std::endl;}
		
		std::cout << "odom transmit Starting..." << std::endl;
		
  		t = std::thread([this]() { io_context.run(); });

	} else {
		std::cout << "odom_trans not enable" << std::endl;
	}
	std::cout << "OdomExporter Started" << std::endl;
}

template<ChannelMode Mode>
inline void OdomExporter<Mode>::stop(void){
	if(param.enable_odom_trans){
	std::cout << "OdomExporter Stopping..." << std::endl;
	io_context.stop();
		// while(!t.joinable()) {std::cout<<"CarCmd2ROSHandler: waiting thread joinable"<<std::endl;}
		t.join();
	std::cout << "OdomExporter Stopped" << std::endl;
	}
}


} // namespace WHU_ROBOT