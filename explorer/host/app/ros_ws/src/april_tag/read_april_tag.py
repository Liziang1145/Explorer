#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import cv2
import numpy as np
import apriltag
import tf.transformations as tf_trans
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry

class AprilTagBoardPoseEstimator:
    def __init__(self):
        rospy.init_node('april_tag_board_pose')

        # ---------- 参数（标定板规格）----------
        self.tag_family = rospy.get_param('~tag_family', 'tag36h11')
        self.tag_size = rospy.get_param('~tag_size', 0.022)        # 单个标签边长，单位米 (2.2 cm)
        self.tag_spacing = rospy.get_param('~tag_spacing', 0.0066) # 标签边缘间距 (0.66 cm)
        self.rows = rospy.get_param('~rows', 6)                    # 标定板上标签行数
        self.cols = rospy.get_param('~cols', 6)                    # 标签列数

        # 计算标定板的整体尺寸
        self.board_width = self.cols * self.tag_size + (self.cols - 1) * self.tag_spacing
        self.board_height = self.rows * self.tag_size + (self.rows - 1) * self.tag_spacing

        # 预计算每个标签四角在其自身坐标系下的偏移（顺序与 apriltag 库一致）
        # apriltag 返回的角点顺序：[左下, 右下, 右上, 左上]
        hs = self.tag_size / 2.0
        self.corner_offsets = np.array([
            [-hs,  hs, 0.0],  # 左下
            [ hs,  hs, 0.0],  # 右下
            [ hs, -hs, 0.0],  # 右上
            [-hs, -hs, 0.0]   # 左上
        ], dtype=np.float32)

        # ---------- 相机数据 ----------
        self.camera_matrix = None
        self.dist_coeffs = None
        self.cam_frame_id = "camera_color_optical_frame"  # 默认坐标系名称

        # ---------- 工具 ----------
        self.bridge = CvBridge()
        self.detector = apriltag.Detector(
            apriltag.DetectorOptions(families=self.tag_family)
        )

        # ---------- 订阅与发布 ----------
        self.image_sub = rospy.Subscriber(
            '/camera/color/image_raw', Image, self.image_callback, queue_size=1
        )
        self.info_sub = rospy.Subscriber(
            '/camera/color/camera_info', CameraInfo, self.info_callback, queue_size=1
        )
        self.odom_pub = rospy.Publisher(
            '/aprilTag/inCamera/targetOdom', Odometry, queue_size=10
        )

        rospy.loginfo("AprilTag 标定板位姿估计节点已启动，等待图像...")

    def info_callback(self, msg):
        """保存相机内参及畸变系数"""
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.K).reshape(3, 3)
            self.dist_coeffs = np.array(msg.D) if msg.D else np.zeros(5)
            self.cam_frame_id = msg.header.frame_id
            rospy.loginfo("相机内参已获取。")

    def image_callback(self, img_msg):
        """图像回调：检测AprilTag，估计标定板位姿并发布"""
        if self.camera_matrix is None:
            rospy.logwarn_throttle(10, "等待相机内参...")
            return

        try:
            # 转换为灰度图（apriltag 需要灰度图）
            cv_image = self.bridge.imgmsg_to_cv2(img_msg, desired_encoding='mono8')
        except Exception as e:
            rospy.logerr("图像转换失败: %s", e)
            return

        # 检测所有标签
        detections = self.detector.detect(cv_image)

        if not detections:
            return  # 没有检测到标签，不发布消息

        # 收集 3D‑2D 对应点
        object_points = []  # 3D 点在标定板坐标系下
        image_points = []   # 2D 像素坐标

        for det in detections:
            tag_id = det.tag_id
            # 假设标签 ID 按行主序排列（0 ~ 35）
            row = tag_id // self.cols
            col = tag_id % self.cols
            if row >= self.rows or col >= self.cols:
                rospy.logdebug("忽略不在标定板上的标签 ID: %d", tag_id)
                continue

            # 标签中心在标定板坐标系下的坐标（原点位于标定板几何中心）
            x_center = -self.board_width / 2.0 + self.tag_size / 2.0 + col * (self.tag_size + self.tag_spacing)
            y_center = -self.board_height / 2.0 + self.tag_size / 2.0 + row * (self.tag_size + self.tag_spacing)
            z_center = 0.0  # 所有点共面

            # 生成该标签四角的 3D 坐标（顺序与 det.corners 一致）
            obj_corners = self.corner_offsets + np.array([x_center, y_center, z_center])
            object_points.extend(obj_corners.tolist())

            # 2D 图像点（det.corners 已与 3D 点顺序匹配）
            image_points.extend(det.corners)

        if len(object_points) < 4:
            rospy.logwarn_throttle(10, "有效点数不足 (需 >=4)，当前: %d", len(object_points))
            return

        obj_pts = np.array(object_points, dtype=np.float32)
        img_pts = np.array(image_points, dtype=np.float32)

        # 位姿求解（标定板坐标系 -> 相机坐标系）
        success, rvec, tvec = cv2.solvePnP(
            obj_pts, img_pts,
            self.camera_matrix, self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not success:
            rospy.logwarn("solvePnP 未收敛")
            return

        # 转换为旋转矩阵并构建 4×4 变换矩阵
        R, _ = cv2.Rodrigues(rvec)
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = tvec.flatten()
        quat = tf_trans.quaternion_from_matrix(T)  # [x, y, z, w]

        # 构建 Odometry 消息
        odom = Odometry()
        odom.header.stamp = img_msg.header.stamp
        odom.header.frame_id = self.cam_frame_id
        odom.child_frame_id = "calibration_board_center"
        odom.pose.pose.position.x = tvec[0, 0]
        odom.pose.pose.position.y = tvec[1, 0]
        odom.pose.pose.position.z = tvec[2, 0]
        odom.pose.pose.orientation.x = quat[0]
        odom.pose.pose.orientation.y = quat[1]
        odom.pose.pose.orientation.z = quat[2]
        odom.pose.pose.orientation.w = quat[3]
        # 协方差留空（默认全零）

        self.odom_pub.publish(odom)

if __name__ == '__main__':
    try:
        node = AprilTagBoardPoseEstimator()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass