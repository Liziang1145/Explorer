# IPC
An easy-to-use inter process communication library.  

Compiles with C++ 20.  

### Features
- [x] Support both Udp socket and Unix domain communication.
- [x] Dynamic Message Queue binding.
- [x] Flexibly support multiple protocols on one channel.
- [x] easy to implement a custom message type.

### Usage
Switch communication method by template parameter `ChannelMode`.
```cpp
#include "comm_channel.hpp"

CommChannel<ChannelMode::UDP,...> channel("127.0.0.1", 12345,"127.0.0.1", 12345);

CommChannel<ChannelMode::Unix,...> channel("/tmp/test", "/tmp/test");
```
Choose arbitrary protocols by feeding template parameters.
```cpp
CommChannel<ChannelMode::UDP, DummySender, DummyReceiver, ...> channel;
```
Bind a message queue to a protocol. Note that the name has to match the name of the protocol.
```cpp
MsgQueue send_mq(RingBuffer<dummy_msg>{10});

channel.bind_message_queue("dummy_sender", ParserType::Sender, send_mq);
```

### What else to Know
This repo is built on [Asio](https://github.com/chriskohlhoff/asio.git) and my implementation of inter-thread communication library [ITC](https://github.com/geniusdo/inter-thread-comm.git).