#pragma once

#include <vector>
#include <memory>
#include <concepts>
#include <stdexcept>

template<typename T>
    requires std::copyable<T> && std::default_initializable<T>
class TransmitBuffer {
public:
    TransmitBuffer(const TransmitBuffer&) = delete;
    TransmitBuffer& operator=(const TransmitBuffer&) = delete;

    explicit TransmitBuffer(size_t buffer_size = 2)
        : buffer_size_(buffer_size),
          buffer_(buffer_size),  // 默认构造出 buffer_size 个 nullptr 的 shared_ptr<T>
          current_id(0)
    {
        if (buffer_size_ == 0) {
            throw std::invalid_argument("TransmitBuffer: buffer_size must be >= 1");
        }
    }

    ~TransmitBuffer() = default;

    // 将 data 包装为 shared_ptr<T> 写入当前索引，返回该 shared_ptr<T>
    std::shared_ptr<T> push_T_rtn_shared(const T& data) {
        // 在当前位置创建一个新的 shared_ptr<T>
        buffer_.at(current_id) = std::make_shared<T>(data);
        auto ptr = buffer_.at(current_id);

        // 环形移动到下一个位置
        current_id = (current_id + 1) % buffer_size_;
        return ptr;
    }

private:
    size_t buffer_size_;
    std::vector<std::shared_ptr<T>> buffer_;
    size_t current_id;
};
