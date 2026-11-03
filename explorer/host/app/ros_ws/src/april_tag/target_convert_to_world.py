#!/usr/bin/env python3
"""
ROS Noetic node: transforms AprilTag target odometry from camera frame to world frame.
Subscribes:
  /filtered_odometry               – robot odometry in world frame
  /aprilTag/inCamera/targetOdom    – target odometry in camera frame
Publishes:
  /aprilTag/inWorld/targetOdom     – target odometry in world frame

Coordinate conventions (all right-handed):
  World frame      : fixed ENU (map)
  Robot frame      : x forward, y left, z up
  Camera frame     : z forward (robot's x), x right (robot's -y), y down (robot's -z)
  Camera <-> Robot : rigidly attached, extrinsic transform (camera origin & orientation in robot frame)

No tf library is used – all frame names come from the incoming messages.
"""

import math
import threading
import numpy as np
import rospy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Quaternion, Pose

# ==============================================================================
# Camera extrinsics (USER MODIFIABLE)
#   camera_translation  : camera origin coordinates in the ROBOT frame [x, y, z]
#   camera_rotation_euler: rotation from CAMERA to ROBOT frame,
#                          Euler angles (roll, pitch, yaw) in radians,
#                          fixed-axis rotation order 'sxyz' (roll->pitch->yaw)
# ------------------------------------------------------------------------------
# Default values for the camera mounted on the robot:
#   camera_translation   = [0.0, 0.0, 0.0]
#   camera_rotation_euler = [-1.5708, 0.0, -1.5708]   # roll=-90°, pitch=0°, yaw=-90°
#
# Verification:
#   The required camera->robot rotation matrix is:
#       [[ 0,  0,  1],
#        [-1,  0,  0],
#        [ 0, -1,  0]]
#   The user-suggested [-1.5708, 1.5708, 0.0] yields:
#       [[ 0, -1,  0],
#        [ 0,  0,  1],
#        [-1,  0,  0]]    <-- does NOT match
#   The correct Euler triple for this fixed-axis XYZ sequence is:
#       roll: -1.5708, pitch: 0.0, yaw: -1.5708
#   This script uses the mathematically correct default above.
#   If you need a different camera orientation, modify the two arrays below.
# ==============================================================================
camera_translation = [0.0, 0.0, 0.0]               # x, y, z of camera origin in robot frame
camera_rotation_euler = [-1.5708, 0.0, -1.5708]    # roll, pitch, yaw [radians]
euler_sequence = 'sxyz'                             # fixed-axis rotation order

# ------------------------------------------------------------------------------
# Compute camera->robot rotation matrix from Euler angles
# ------------------------------------------------------------------------------
def euler_to_mat(roll, pitch, yaw, seq='sxyz'):
    """Fixed-axis Euler rotation matrix (R = R_z(yaw)*R_y(pitch)*R_x(roll))."""
    cr = math.cos(roll); sr = math.sin(roll)
    cp = math.cos(pitch); sp = math.sin(pitch)
    cy = math.cos(yaw); sy = math.sin(yaw)

    if seq == 'sxyz':
        R = np.array([
            [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
            [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
            [-sp,   cp*sr,            cp*cr]
        ])
        return R
    else:
        raise ValueError("Only fixed-axis 'sxyz' Euler sequence is supported.")

# Expected camera->robot rotation matrix (derived from axis mapping)
R_expected = np.array([
    [ 0.0,  0.0,  1.0],
    [-1.0,  0.0,  0.0],
    [ 0.0, -1.0,  0.0]
])

R_user = euler_to_mat(*camera_rotation_euler, euler_sequence)

if np.allclose(R_user, R_expected, atol=1e-4):
    rospy.loginfo("Camera->robot rotation verified ✓")
else:
    rospy.logwarn("WARNING: camera_rotation_euler does NOT produce the expected camera->robot matrix!")
    rospy.logwarn("Expected rotation:\n%s", R_expected)
    rospy.logwarn("Current rotation:\n%s", R_user)
    rospy.logwarn("For the described axis mapping, use: roll=-1.5708, pitch=0.0, yaw=-1.5708")

# 4x4 homogeneous transform from camera to robot (T_R_C)
T_R_C = np.eye(4)
T_R_C[:3, :3] = R_user
T_R_C[:3, 3] = np.array(camera_translation)

# ==============================================================================
# Utility functions (No tf)
# ==============================================================================
def quaternion_to_rot(q):
    """Convert quaternion [x, y, z, w] to 3x3 rotation matrix."""
    qx, qy, qz, qw = q
    R = np.array([
        [1 - 2*qy**2 - 2*qz**2, 2*qx*qy - 2*qz*qw, 2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw, 1 - 2*qx**2 - 2*qz**2, 2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw, 2*qy*qz + 2*qx*qw, 1 - 2*qx**2 - 2*qy**2]
    ])
    return R

def rot_to_quaternion(R):
    """Convert 3x3 rotation matrix to quaternion [x, y, z, w]."""
    m00, m01, m02 = R[0,0], R[0,1], R[0,2]
    m10, m11, m12 = R[1,0], R[1,1], R[1,2]
    m20, m21, m22 = R[2,0], R[2,1], R[2,2]
    tr = m00 + m11 + m22
    if tr > 0:
        s = 0.5 / math.sqrt(tr + 1.0)
        qw = 0.25 / s
        qx = (m21 - m12) * s
        qy = (m02 - m20) * s
        qz = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
    return np.array([qx, qy, qz, qw])

def odom_to_matrix(odom_msg):
    """
    Convert Odometry message to 4x4 homogeneous matrix.
    Interprets pose as transformation from child to header frame:
        P_header = T * P_child
    """
    p = odom_msg.pose.pose.position
    q = odom_msg.pose.pose.orientation
    pos = np.array([p.x, p.y, p.z])
    quat = np.array([q.x, q.y, q.z, q.w])
    R = quaternion_to_rot(quat)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = pos
    return T

def matrix_to_odom(T, world_frame_id, child_frame_id):
    """Convert a 4x4 world->child matrix to an Odometry message."""
    odom = Odometry()
    odom.header.frame_id = world_frame_id
    odom.child_frame_id = child_frame_id
    pos = Point()
    pos.x, pos.y, pos.z = T[0, 3], T[1, 3], T[2, 3]
    quat = rot_to_quaternion(T[:3, :3])
    odom.pose.pose = Pose(pos, Quaternion(*quat))
    return odom

# ==============================================================================
# Node
# ==============================================================================
class TargetWorldPublisher:
    def __init__(self):
        rospy.init_node('target_world_publisher')

        # Subscribers (asynchronous, no time synchronization)
        self.sub_robot = rospy.Subscriber(
            '/filtered_odometry', Odometry, self.robot_cb, queue_size=1)
        self.sub_target_cam = rospy.Subscriber(
            '/aprilTag/inCamera/targetOdom', Odometry, self.target_cam_cb, queue_size=1)

        # Publisher
        self.pub_target_world = rospy.Publisher(
            '/aprilTag/inWorld/targetOdom', Odometry, queue_size=1)

        self.lock = threading.Lock()
        self.latest_robot_odom = None
        self.latest_target_cam = None

        self.T_R_C = T_R_C   # fixed camera->robot transform

        # Publish periodically (10 Hz)
        self.timer = rospy.Timer(rospy.Duration(0.1), self.timer_cb)

    def robot_cb(self, msg):
        with self.lock:
            self.latest_robot_odom = msg

    def target_cam_cb(self, msg):
        with self.lock:
            self.latest_target_cam = msg

    def timer_cb(self, event):
        with self.lock:
            robot = self.latest_robot_odom
            target_cam = self.latest_target_cam

        if robot is None or target_cam is None:
            return

        # Build transforms from incoming messages
        T_W_R = odom_to_matrix(robot)           # world <- robot
        T_C_A = odom_to_matrix(target_cam)      # camera <- target

        # Compose: world <- robot <- camera <- target
        T_W_A = T_W_R @ self.T_R_C @ T_C_A

        # Output odometry message
        world_odom = matrix_to_odom(
            T_W_A,
            world_frame_id=robot.header.frame_id,       # preserve world frame name
            child_frame_id=target_cam.child_frame_id    # target frame name
        )
        world_odom.header.stamp = target_cam.header.stamp   # use target observation time
        self.pub_target_world.publish(world_odom)

if __name__ == '__main__':
    node = TargetWorldPublisher()
    rospy.spin()