# Inter-Thread Communication

## 1. Task 

Your own task class should be inherited from `TaskBase` class.  
Implement your own `task()` function and optional `start()` and `stop()` functions.

## 2. Message Queue

You can use `MsgQueue` as the inter-thread communication channel.  
A `MsgQueue` can be initialized as `IMsgQueue* msgQueue = new MsgQueueImpl<std::shared_ptr<FullbodyState>>(100);`, where the base class `IMsgQueue` is usued as the common interface, and `MsgQueueImpl` is the actual implementation.   

Inside the `MsgQueue`, a wait-free ring-buffer is implemented as an alternative to the `boost::spsc_queue`.


## 3. Message Binding

You can bind a `MsgQueue` to a `Task` by using the `bind_msg_queue(const std::string &name, IMsgQueue *msg_queue)` function, and then you can quiry a message queue by using the ` IMsgQueue *quiry_msg_queue(const std::string &name)` function.

```c++
// Create a task
Schedule::CommTask task{};

// Create a message queue
IMsgQueue* msgQueue = new MsgQueueImpl<std::shared_ptr<FullbodyState>>(100);

// Bind the message queue to the task
task->bind_msg_queue("fullbody_state", msgQueue);

// Start the task
task->start();
```

## 4. Polymorphism

Currently the message queue binding is acheived through **Runtime Polymorphism**.  

A **Static Plymorphism** implementation is planned for the future.