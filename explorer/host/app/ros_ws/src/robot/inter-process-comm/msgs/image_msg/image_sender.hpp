#pragma once

#include "../common.hpp"
#include "../compress_utils.hpp"
#include "../CRC.h"
#include "image_msg.h"

struct ImageSender {
  using DataType                         = image_msg;
  static constexpr uint8_t parser_type   = ParserType::Sender;
  static constexpr uint16_t header       = 0xDCDC;
  static constexpr size_t length         = sizeof(image_msg)+4;
  static constexpr std::string_view name = "image_sender";

  static inline void Process(const DataType& in, std::span<std::byte>& out) {
    uint32_t tmp_32bits;
    memcpy(&out[0], &header, sizeof(uint16_t));
    memcpy(&out[2], &in.data, sizeof(image_msg));

    // CRC
    uint16_t crc = CRC::CalculateBits(out.data(), sizeof(image_msg)+2, CRC::CRC_16_KERMIT());
    memcpy(&out[sizeof(image_msg)+2], &crc, sizeof(uint16_t));
    
    return;
  }
};