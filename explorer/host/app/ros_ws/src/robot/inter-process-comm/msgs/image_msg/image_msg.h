#pragma once
#include <array>

constexpr int IMG_WIDTH = 640;
constexpr int IMG_HEIGHT = 480;
constexpr int IMG_CHANNELS = 3; // RGB
constexpr int IMG_SIZE = IMG_WIDTH * IMG_HEIGHT * IMG_CHANNELS;

struct image_msg {
	using ImagePixType = uint8_t;
	using ImageData = ImagePixType[IMG_HEIGHT][IMG_WIDTH][IMG_CHANNELS];
	
	ImageData data;
};