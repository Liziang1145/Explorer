#include <ros/ros.h>
#include "configParser.hpp"
#include "MergeHandler.hpp"
#include "comm_channel.hpp"

int main(int argc, char** argv)
{


		std::cout << "WHU Robot MergeHandler Node Starting..." << std::endl;

		ros::init(argc, argv, "WHUrobot_MergeNode");
		ros::NodeHandle nh;

		std::string config_file = "/workspace/src/robot/config/config.yaml";
		WHU_ROBOT::param_t params(config_file);

		WHU_ROBOT::MergeHandler<ChannelMode::Unix> merge_handler(params);
		merge_handler.init();

		ros::Rate rate(100.0);

		while(ros::ok()){
			ros::spinOnce();
			merge_handler.exec();
			rate.sleep();
		}

		merge_handler.stop();

	std::cout<<"CommunicateNode END" <<std::endl;
	return 0;

}