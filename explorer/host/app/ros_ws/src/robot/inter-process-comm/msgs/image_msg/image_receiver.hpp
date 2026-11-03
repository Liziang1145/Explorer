#pragma once

#include "../common.hpp"
#include "../compress_utils.hpp"
#include "../CRC.h"
#include "image_msg.h"

struct ImageReceiver {
	using DataType                         = image_msg;
	static constexpr uint8_t parser_type   = ParserType::Receiver;
	static constexpr uint16_t header       = 0xDCDC;
	static constexpr size_t length         = sizeof(image_msg)+4;
	static constexpr std::string_view name = "image_receiver";
      
	static inline bool Process(const std::span<std::byte>& in, DataType& out) {
	  // crc check
	  {
	    uint16_t crc = CRC::CalculateBits(in.data(), sizeof(image_msg)+2, CRC::CRC_16_KERMIT());
	    uint16_t crc_in;
	    memcpy(&crc_in, &in[sizeof(image_msg)+2], sizeof(uint16_t));
	    if (crc != crc_in) return false;
	  }
      
	  memcpy(&out.data, &in[2], sizeof(image_msg));
	  
	  return true;
	}
      };