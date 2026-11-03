cmake_minimum_required(VERSION 3.14)
project(robot)

SET(CMAKE_BUILD_TYPE "Release")


set(CMAKE_CONFIGURATION_TYPES "Debug;Release")
if (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")
endif()


set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fexceptions" )
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=gnu++20 -pthread -fexceptions")
add_definitions(-DEIGEN_DONT_ALIGN_STATICALLY)

set(BOOST_ROOT "/usr/local/boost_1_88_0")
set(BOOST_INCLUDEDIR "${BOOST_ROOT}/include")
set(BOOST_LIBRARYDIR "${BOOST_ROOT}/lib")

find_package(Boost 1.88.0 REQUIRED)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  nav_msgs
  pcl_ros
  pcl_conversions
  roscpp
  rospy
  sensor_msgs
  std_msgs
  tf
  message_generation
  eigen_conversions
  yhs_can_msgs
)

find_package(Eigen3 3.4 REQUIRED)
find_package(PCL 1.8 REQUIRED)
# find_package(PCL REQUIRED COMPONENTS common io filters)
find_package(yaml-cpp REQUIRED)
find_package(TBB REQUIRED)

message(Eigen: ${EIGEN3_INCLUDE_DIR})

catkin_package()


include_directories(
  ${catkin_INCLUDE_DIRS}
  ${EIGEN3_INCLUDE_DIRS}
  ${PCL_INCLUDE_DIRS}
  ${TBB_INCLUDE_DIRS}
  /usr/include
  include
  include/point_interface
  # include/net_interface
  include/communicate
  include/car_control
  include/boost
  inter-process-comm
  inter-process-comm/msgs
)

add_definitions(${PCL_DEFINITIONS})


add_executable(WHUrobot_communicate_node src/CommunicateNode.cpp)

add_executable(WHUrobot_carcontrol_node src/CarControlNode.cpp)

add_executable(WHUrobot_merge_node src/MergeNode.cpp)

add_executable(WHUrobot_filter_node src/simpleFilterNode.cpp)


target_link_libraries(WHUrobot_communicate_node
  ${catkin_LIBRARIES} Eigen3::Eigen ${PCL_LIBRARIES} ${YAML_CPP_LIBRARIES} TBB::tbb
)

target_link_libraries(WHUrobot_carcontrol_node
  ${catkin_LIBRARIES} Eigen3::Eigen ${YAML_CPP_LIBRARIES} TBB::tbb
)


target_link_libraries(WHUrobot_merge_node
  ${catkin_LIBRARIES} Eigen3::Eigen ${YAML_CPP_LIBRARIES} TBB::tbb
)


target_link_libraries(WHUrobot_filter_node
  ${catkin_LIBRARIES} Eigen3::Eigen ${YAML_CPP_LIBRARIES} TBB::tbb
)
