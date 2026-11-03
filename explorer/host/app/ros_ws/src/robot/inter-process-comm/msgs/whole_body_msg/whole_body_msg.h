#pragma once
#include <array>

struct whole_body_msg {
  using vec4 = std::array<float, 4>;
  // mask explanation
  // enable: 1
  // disable: 0
  // high:Control Enable | base control | left hand control | right hand control | base vel valid | left hand vel valid | right hand vel valid |
  // low: pose request | pose answer
  uint16_t mask;
  uint32_t cnt;
  uint64_t time;  // timestamp unit: ns

  vec4 base_pos;        // global position of baselink in FLU coordinate
  vec4 left_hand_pos;   // position of left hand relative to base in FLU coordinate
  vec4 right_hand_pos;  // position of right hand relative to base in FLU coordinate

  vec4 base_quat;        //
  vec4 left_hand_quat;   //
  vec4 right_hand_quat;  //

  vec4 base_lin_vel;  // relative velocity of base in FLU coordinate
  vec4 base_ang_vel;  // relative angular velocity of base in FLU coordinate

  vec4 left_hand_lin_vel;   // relative velocity of left hand in FLU coordinate
  vec4 right_hand_lin_vel;  // relative velocity of right hand in FLU coordinate

  vec4 left_hand_ang_vel;   // relative angular velocity of left hand in FLU coordinate
  vec4 right_hand_ang_vel;  // relative angular velocity of right hand in FLU coordinate

  float left_grip, right_grip;
};