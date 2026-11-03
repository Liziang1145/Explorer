#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import cv2
import numpy as np
import tf.transformations as tf_trans
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry
from threading import Lock

class AprilTagBoardVisualizer:
    def __init__(self):
        rospy.init_node('april_board_visualizer')

        # ---------- 标定板尺寸（必须与检测节点一致）----------
        self.tag_size = rospy.get_param('~tag_size', 0.022)        # m
        self.tag_spacing = rospy.get_param('~tag_spacing', 0.0066) # m
        self.rows = rospy.get_param('~rows', 6)
        self.cols = rospy.get_param('~cols', 6)

        # 计算整板的宽高
        self.board_w = self.cols * self.tag_size + (self.cols - 1) * self.tag_spacing
        self.board_h = self.rows * self.tag_size + (self.rows - 1) * self.tag_spacing

        # 定义标定板在自身坐标系中的角点（Z=0 平面）
        # 原点位于几何中心，顺序：左上、右上、右下、左下（闭合）
        hw = self.board_w / 2.0
        hh = self.board_h / 2.0
        self.board_corners_3d = np.array([
            [-hw,  hh, 0.0],  # 左上
            [ hw,  hh, 0.0],  # 右上
            [ hw, -hh, 0.0],  # 右下
            [-hw, -hh, 0.0]   # 左下
        ], dtype=np.float32)

        # 用于绘制坐标轴的 3D 点（原点 + X/Y/Z 轴末端，单位米）
        self.axis_length = rospy.get_param('~axis_length', 0.03)  # 3 cm
        self.axis_3d = np.array([
            [0.0, 0.0, 0.0],                        # 原点
            [self.axis_length, 0.0, 0.0],           # X 轴（红）
            [0.0, self.axis_length, 0.0],           # Y 轴（绿）
            [0.0, 0.0, self.axis_length]            # Z 轴（蓝）
        ], dtype=np.float32)

        # ---------- 存储最新消息 ----------
        self.latest_image = None
        self.latest_camera_info = None
        self.latest_odom = None
        self.lock = Lock()

        # ---------- 工具 ----------
        self.bridge = CvBridge()

        # ---------- 订阅 ----------
        self.image_sub = rospy.Subscriber(
            '/camera/color/image_raw', Image, self.image_cb, queue_size=1)
        self.info_sub = rospy.Subscriber(
            '/camera/color/camera_info', CameraInfo, self.info_cb, queue_size=1)
        self.odom_sub = rospy.Subscriber(
            '/aprilTag/inCamera/targetOdom', Odometry, self.odom_cb, queue_size=1)

        # ---------- 发布 ----------
        self.image_pub = rospy.Publisher(
            '/aprilTag/inCamera/image_annotated', Image, queue_size=1)

        # 定时处理（以固定频率合成）
        self.process_timer = rospy.Timer(rospy.Duration(0.03), self.process_and_publish)

        rospy.loginfo("AprilTag 标定板可视化节点已启动，等待数据...")

    def image_cb(self, msg):
        with self.lock:
            self.latest_image = msg

    def info_cb(self, msg):
        with self.lock:
            self.latest_camera_info = msg

    def odom_cb(self, msg):
        with self.lock:
            self.latest_odom = msg

    def process_and_publish(self, event):
        with self.lock:
            if self.latest_image is None or self.latest_camera_info is None or self.latest_odom is None:
                return
            img_msg = self.latest_image
            cam_info = self.latest_camera_info
            odom = self.latest_odom

        try:
            # 将图像转换为 OpenCV 彩色格式（BGR）
            cv_img = self.bridge.imgmsg_to_cv2(img_msg, desired_encoding='bgr8')
        except Exception as e:
            rospy.logerr("图像转换失败: %s", e)
            return

        # 提取相机矩阵
        K = np.array(cam_info.K).reshape(3,3)
        if cam_info.D:
            dist = np.array(cam_info.D)
        else:
            dist = np.zeros(5)

        # 提取位姿
        pos = odom.pose.pose.position
        ori = odom.pose.pose.orientation
        tvec = np.array([pos.x, pos.y, pos.z])
        quat = [ori.x, ori.y, ori.z, ori.w]
        # 从四元数获得旋转矩阵（板子 -> 相机）
        R = tf_trans.quaternion_matrix(quat)[:3, :3]

        # 将标定板角点投影到图像
        img_pts = self.project_points(self.board_corners_3d, R, tvec, K, dist)
        if img_pts is not None:
            # 绘制填充半透明边框
            overlay = cv_img.copy()
            cv2.polylines(overlay, [img_pts.astype(np.int32)], isClosed=True,
                          color=(0, 255, 0), thickness=2)
            cv_img = cv2.addWeighted(overlay, 0.6, cv_img, 0.4, 0)

        # 投影坐标轴
        axis_pts = self.project_points(self.axis_3d, R, tvec, K, dist)
        if axis_pts is not None:
            origin = tuple(axis_pts[0].astype(int))
            x_end = tuple(axis_pts[1].astype(int))
            y_end = tuple(axis_pts[2].astype(int))
            z_end = tuple(axis_pts[3].astype(int))
            cv2.line(cv_img, origin, x_end, (0, 0, 255), 2)  # 红 X
            cv2.line(cv_img, origin, y_end, (0, 255, 0), 2)  # 绿 Y
            cv2.line(cv_img, origin, z_end, (255, 0, 0), 2)  # 蓝 Z

        # 添加文字信息（位姿数值）
        text_lines = [
            f"Pos: [{pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f}] m",
            f"Ori (xyzw): [{ori.x:.3f}, {ori.y:.3f}, {ori.z:.3f}, {ori.w:.3f}]",
            f"Board: {self.cols}x{self.rows} tags"
        ]
        y0, dy = 30, 25
        for i, line in enumerate(text_lines):
            cv2.putText(cv_img, line, (10, y0 + i*dy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(cv_img, line, (10, y0 + i*dy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)  # 黑色描边

        # 发布标注后的图像
        try:
            out_msg = self.bridge.cv2_to_imgmsg(cv_img, encoding='bgr8')
            out_msg.header = img_msg.header
            self.image_pub.publish(out_msg)
        except Exception as e:
            rospy.logerr("图像发布失败: %s", e)

    def project_points(self, object_points, R, tvec, K, dist):
        """将3D点从标定板坐标系投影到图像平面，返回Nx2数组或None"""
        # 变换到相机坐标系: P_cam = R * P_board + tvec
        # 注意：object_points 形状为 (N,3)，R为(3,3)，tvec为(3,)
        cam_pts = (R @ object_points.T).T + tvec.reshape(1,3)
        # 过滤掉在相机后方的点（Z <= 0）
        if np.any(cam_pts[:, 2] <= 0):
            return None
        # 投影
        img_pts, _ = cv2.projectPoints(
            cam_pts.reshape(-1,1,3),
            np.zeros(3), np.zeros(3),  # 已经变换，无需外参
            K, dist
        )
        return img_pts.reshape(-1,2)


if __name__ == '__main__':
    try:
        node = AprilTagBoardVisualizer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass