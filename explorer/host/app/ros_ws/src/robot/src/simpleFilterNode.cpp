// odometry_filter_node.cpp
// A ROS node that subscribes to /Odometry (nav_msgs/Odometry) at ~20Hz,
// applies a simple exponential moving average filter to reduce noise,
// and publishes the filtered data to /filtered_odometry.

#include <ros/ros.h>
#include <nav_msgs/Odometry.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>

#include <Eigen/Geometry>
#include <deque>

geometry_msgs::Quaternion eigenToMsg(const Eigen::Quaterniond& q) {
  geometry_msgs::Quaternion q_msg;
  q_msg.x = q.x();
  q_msg.y = q.y();
  q_msg.z = q.z();
  q_msg.w = q.w();
  return q_msg;
}

Eigen::Quaterniond convertFRDToFLU(const Eigen::Quaterniond& q_FRD) {
    // FRD → FLU 相当于绕 X 轴旋转 180°
    // Eigen::Quaterniond q_rot = Eigen::AngleAxisd(M_PI, Eigen::Vector3d::UnitX());
    Eigen::Quaterniond q_rot(Eigen::AngleAxisd(M_PI, Eigen::Vector3d::UnitX()));


    // 应用右乘（因为我们是在变更body坐标系定义）
    Eigen::Quaterniond q_FLU = q_FRD * q_rot;

    return q_FLU.normalized();
}


class OdometryFilterNode {
public:
  OdometryFilterNode(ros::NodeHandle& nh)
  : nh_(nh), alpha_(0.1), initialized_(false)
  {
    // Get filter parameter alpha (0 < alpha < 1), close to 1 means weaker filter and faster response
    nh_.param("/robot/param/filter_alpha", alpha_, alpha_);
    alpha_ = std::min(std::max(alpha_, 0.0), 1.0);

    // Subscriber to raw odometry
    sub_ = nh_.subscribe("/Odometry", 10, &OdometryFilterNode::odomCallback, this);
    
    // Publisher for filtered odometry
    pub_ = nh_.advertise<nav_msgs::Odometry>("/filtered_odometry", 10);

    ROS_INFO("Odometry filter node initialized with alpha = %.3f", alpha_);
  }

private:
void odomCallback(const nav_msgs::Odometry::ConstPtr& msg) {
  nav_msgs::Odometry filtered;
  filtered.header = msg->header;
  filtered.child_frame_id = msg->child_frame_id;

  // 1. 姿态转换并加入缓冲区
  Eigen::Quaterniond q_input(msg->pose.pose.orientation.w,
                             msg->pose.pose.orientation.x,
                             msg->pose.pose.orientation.y,
                             msg->pose.pose.orientation.z);
  Eigen::Quaterniond q_flu = convertFRDToFLU(q_input);
  orient_buffer_.push_back(q_flu);
  if (orient_buffer_.size() > window_size_) orient_buffer_.pop_front();

  // 2. 平均四元数（加权再归一化）
  Eigen::Quaterniond q_sum(0, 0, 0, 0);
  for (const auto& q : orient_buffer_) {
      if (q_sum.dot(q) < 0)
          q_sum.coeffs() -= q.coeffs();
      else
          q_sum.coeffs() += q.coeffs();
  }
  Eigen::Quaterniond q_filtered = q_sum.normalized();

  // 3. 平均位置
  pos_buffer_.push_back(msg->pose.pose.position);
  if (pos_buffer_.size() > window_size_) pos_buffer_.pop_front();

  geometry_msgs::Point filtered_pos;
  filtered_pos.x = filtered_pos.y = filtered_pos.z = 0;
  for (const auto& p : pos_buffer_) {
      filtered_pos.x += p.x;
      filtered_pos.y += p.y;
      filtered_pos.z += p.z;
  }
  double N = static_cast<double>(pos_buffer_.size());
  filtered_pos.x /= N;
  filtered_pos.y /= N;
  filtered_pos.z /= N;

  // 4. 填充结果并发布
  filtered.pose.pose.position = filtered_pos;
  filtered.pose.pose.orientation = eigenToMsg(q_filtered);
  filtered.twist = msg->twist;
  filtered.pose.covariance = msg->pose.covariance;
  filtered.twist.covariance = msg->twist.covariance;

  pub_.publish(filtered);
}


  ros::NodeHandle nh_;
  ros::Subscriber sub_;
  ros::Publisher pub_;

  double alpha_;
  bool initialized_{};
  geometry_msgs::Point prev_pos_;
  geometry_msgs::Quaternion prev_orient_;

  std::deque<geometry_msgs::Point> pos_buffer_;
  std::deque<Eigen::Quaterniond> orient_buffer_;
  size_t window_size_ = 20;  // 可调窗口大小
};

int main(int argc, char** argv) {
  ros::init(argc, argv, "odometry_filter_node");
  ros::NodeHandle nh;

  OdometryFilterNode node(nh);
  ros::spin();

  return 0;
}
