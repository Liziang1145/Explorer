#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"
#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"
#include "dummy_msg/dummy_receiver.hpp"
#include "dummy_msg/dummy_sender.hpp"
#include "dummy_msg/dummy_msg.h"

#include <thread>
TEST_CASE("comm channel udp") {
  asio::io_context io_context;
  CommChannel<ChannelMode::UDP, DummySender, DummyReceiver> channel(io_context, "127.0.0.1", 12345, "127.0.0.1",
                                                 12345);
  //   channel.bind_message_queue("dummy_msg", 0, mq);
  MsgQueue send_mq(RingBuffer<dummy_msg>{10});
  MsgQueue recv_mq(RingBuffer<dummy_msg>{10});
  channel.bind_message_queue("dummy_sender", ParserType::Sender, send_mq);
  channel.bind_message_queue("dummy_receiver", ParserType::Receiver, recv_mq);
  CHECK(channel.enable_sender() == true);
  CHECK(channel.enable_receiver() == true);

  std::thread t([&]() { io_context.run(); });

  send_mq.enqueue(dummy_msg{1});
  send_mq.enqueue(dummy_msg{1});
  send_mq.enqueue(dummy_msg{1});
  std::this_thread::sleep_for(std::chrono::milliseconds(10));
  CHECK(recv_mq.size() == 3);

  io_context.stop();
  t.join();

}

TEST_CASE("comm channel unix") {
  asio::io_context io_context;
  CommChannel<ChannelMode::Unix, DummySender, DummyReceiver> channel(io_context, "/tmp/socket1", "/tmp/socket1");
  //   channel.bind_message_queue("dummy_msg", 0, mq);
  MsgQueue send_mq(RingBuffer<dummy_msg>{10});
  MsgQueue recv_mq(RingBuffer<dummy_msg>{10});
  channel.bind_message_queue("dummy_sender", ParserType::Sender, send_mq);
  channel.bind_message_queue("dummy_receiver", ParserType::Receiver, recv_mq);
  CHECK(channel.enable_sender() == true);
  CHECK(channel.enable_receiver() == true);

  std::thread t([&]() { io_context.run(); });

  send_mq.enqueue(dummy_msg{1});
  send_mq.enqueue(dummy_msg{1});
  send_mq.enqueue(dummy_msg{1});
  std::this_thread::sleep_for(std::chrono::milliseconds(10));
  CHECK(recv_mq.size() == 3);

  io_context.stop();
  t.join();

}