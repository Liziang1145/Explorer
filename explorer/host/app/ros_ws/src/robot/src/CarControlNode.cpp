#include <ros/ros.h>
#include "CarROSHandler.hpp"
#include "configParser.hpp"
#include "simpleCtrl.hpp"

int main(int argc, char** argv)
{
	std::cout << "WHU Robot CarControl Node Starting..." << std::endl;

    ros::init(argc, argv, "WHUrobot_carcontrol_node");
    ros::NodeHandle nh;

    std::string config_file = "/workspace/src/robot/config/control_config.yaml";
    WHU_ROBOT::ctl_param_t params(config_file);

    auto controller_ptr = std::make_unique<WHU_ROBOT::SimpleCtrl>(params);
    WHU_ROBOT::CarROSHandler carROS_handler(params, nh, std::move(controller_ptr));


    ros::Rate rate(100.0);

    while (ros::ok())
    {
	carROS_handler.exec();
	ros::spinOnce();
	rate.sleep();
    }


    return 0;
}