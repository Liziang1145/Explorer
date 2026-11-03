#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"

#include "compress_utils.hpp"

TEST_CASE("test encode/decode ") {
  std::array<float, 4> quat1 = {0.8533,0.1525,0.2091,0.4526};
  uint32_t result = EncodeQuaternion<float>(quat1.data());
  std::array<float, 4> quat2;
  DecodeQuaternion<float>(result, quat2.data());
  std::cout<<quat2[0]<<" "<<quat2[1]<<" "<<quat2[2]<<" "<<quat2[3]<<std::endl;

}
