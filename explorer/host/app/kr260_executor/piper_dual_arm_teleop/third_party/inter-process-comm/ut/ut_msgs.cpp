#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"
#include "itc/backend/RingBuf.hpp"
#include "comm_channel.hpp"

#include "dummy_msg/dummy_receiver.hpp"
#include "dummy_msg/dummy_sender.hpp"
#include "dummy_msg/dummy_msg.h"

#include "whole_body_msg/whole_body_receiver.hpp"
#include "whole_body_msg/whole_body_sender.hpp"
#include "whole_body_msg/whole_body_msg.h"

TEST_CASE("test whole_body_msg") {
  asio::io_context io_context;
  CommChannel<ChannelMode::UDP, WholeBodySender, WholeBodyReceiver> channel(io_context, "127.0.0.1", 12345, "127.0.0.1", 12345);
}
