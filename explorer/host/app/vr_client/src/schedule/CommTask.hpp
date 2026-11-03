#pragma once

#include "TaskBase.hpp"

#include "ipc/comm_channel.hpp"
#include "ipc/itc/MsgQueue.hpp"
#include "ipc/msgs/whole_body_msg/whole_body_sender.hpp"
#include "ipc/msgs/cloud_msg/cloud_receiver.hpp"
#include "ipc/msgs/nav_state_msg/nav_state_receiver.hpp"

namespace Schedule {

  class CommTask : public TaskBase {
  public:
    // std::vector<std::byte>>>;
  protected:
    void task() override {
      auto work_guard = asio::make_work_guard(io_context);
      CommChannel<ChannelMode::UDP, WholeBodySender, NavStateReceiver> channel(io_context, "192.168.1.105", 12345, "192.168.1.5", 54321);
      // CommChannel<ChannelMode::UDP, WholeBodySender, NavStateReceiver> channel(io_context, "127.0.0.1", 12345, "127.0.0.1", 54321);
      // CommChannel<ChannelMode::UDP, WholeBodySender, NavStateReceiver> channel(io_context, "192.168.2.105", 12345, "192.168.1.5", 54321);
      // CommChannel<ChannelMode::UDP, WholeBodySender, NavStateReceiver> channel(io_context, "192.168.1.105", 12345, "192.168.1.108", 54321);

        // CommChannel<ChannelMode::UDP, WholeBodySender> channel(io_context, "127.0.0.1", 12345, "127.0.0.1", 54321);

      auto cmd_msg_queue = quiry_msg_queue("whole_body_ctrl_cmd");
      channel.bind_message_queue("whole_body_sender", ParserType::Sender, *cmd_msg_queue);
      auto nav_msg_queue = quiry_msg_queue("nav_state_msg");
      channel.bind_message_queue("nav_state_receiver", ParserType::Receiver, *nav_msg_queue);
      channel.enable_sender();
      channel.enable_receiver();

      CommChannel<ChannelMode::UDP, CloudReceiver> map_channel(io_context, "192.168.1.105", 5000, "192.168.1.5", 12345);
      // CommChannel<ChannelMode::UDP, CloudReceiver> map_channel(io_context, "192.168.1.180", 5000, "192.168.1.54", 5001);
      // CommChannel<ChannelMode::UDP, CloudReceiver> map_channel(io_context, "127.0.0.1", 5000, "127.0.0.1", 12345);
      // CommChannel<ChannelMode::UDP, CloudReceiver> map_channel(io_context, "192.168.2.105", 5000, "192.168.1.5", 12345);
      // CommChannel<ChannelMode::UDP, CloudReceiver> map_channel(io_context, "192.168.1.105", 5000, "192.168.1.108", 12345);
      auto map_msg_queue = quiry_msg_queue("cloud_msg");
      map_channel.bind_message_queue("cloud_receiver", ParserType::Receiver, *map_msg_queue);
      map_channel.enable_receiver();

      CommChannel<ChannelMode::UDP, CloudReceiver> cam_channel(io_context, "192.168.1.105", 6666, "192.168.1.5", 13579);
      // CommChannel<ChannelMode::UDP, CloudReceiver> cam_channel(io_context, "127.0.0.1", 8423, "127.0.0.1", 12365);
      auto cam_msg_queue = quiry_msg_queue("cam_msg");
      cam_channel.bind_message_queue("cloud_receiver", ParserType::Receiver, *cam_msg_queue);
      cam_channel.enable_receiver();
      io_context.run();
    }

  private:
    asio::io_context io_context;
  };

};  // namespace Schedule
