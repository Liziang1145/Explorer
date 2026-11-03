# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# import rospy
# import numpy as np
# import tf.transformations as tf_trans
# from nav_msgs.msg import Odometry
# from std_msgs.msg import Bool
# from threading import Lock
# import atexit

# # ================= 用户可修改的启用开关 =================
# ENABLE_ON_START = True   # 改 True 后启动，运动控制使能即生效
# # ======================================================

# class RobotTargetGenerator:
#     def __init__(self):
#         rospy.init_node('robot_target_generator')

#         # 最近收到的消息缓存
#         self.latest_board_world = None
#         self.latest_board_cam   = None
#         self.latest_odom        = None
#         self.lock = Lock()

#         # 发布者
#         self.target_pub = rospy.Publisher('/robot/targetOdom', Odometry, queue_size=1)
#         self.enable_pub = rospy.Publisher('/state/car_control_enable', Bool, queue_size=1, latch=True)

#         # 发布初始使能值
#         self.enable_pub.publish(Bool(data=ENABLE_ON_START))
#         rospy.loginfo(f"运动使能初始值: {ENABLE_ON_START}")

#         # 订阅者
#         rospy.Subscriber('/aprilTag/inWorld/targetOdom', Odometry, self.board_world_cb, queue_size=1)
#         rospy.Subscriber('/aprilTag/inCamera/targetOdom', Odometry, self.board_cam_cb, queue_size=1)
#         rospy.Subscriber('/filtered_odometry', Odometry, self.odom_cb, queue_size=1)

#         # 退出处理
#         atexit.register(self._shutdown_hook)
#         rospy.on_shutdown(self._shutdown_hook)

#         rospy.loginfo("节点启动，等待数据...")

#     def _shutdown_hook(self):
#         try:
#             self.enable_pub.publish(Bool(data=False))
#             rospy.loginfo("已发送使能信号: False (节点关闭)")
#         except:
#             pass

#     def board_world_cb(self, msg):
#         with self.lock:
#             self.latest_board_world = msg
#         self.try_compute_and_publish()

#     def board_cam_cb(self, msg):
#         with self.lock:
#             self.latest_board_cam = msg

#     def odom_cb(self, msg):
#         with self.lock:
#             self.latest_odom = msg

#     def try_compute_and_publish(self):
#         with self.lock:
#             if self.latest_board_world is None or self.latest_board_cam is None or self.latest_odom is None:
#                 return
#             board_world = self.latest_board_world
#             board_cam   = self.latest_board_cam
#             odom        = self.latest_odom

#         # 1. 提取 inCamera 的 pitch 角
#         try:
#             quat_cam = board_cam.pose.pose.orientation
#             q = [quat_cam.x, quat_cam.y, quat_cam.z, quat_cam.w]
#             # RPY, sxyz 顺序: roll, pitch, yaw
#             _, pitch_cam, _ = tf_trans.euler_from_quaternion(q, 'sxyz')
#         except Exception as e:
#             rospy.logerr("提取相机姿态失败: %s", e)
#             return

#         # 2. 提取 odom 的 yaw 角
#         try:
#             quat_odom = odom.pose.pose.orientation
#             q = [quat_odom.x, quat_odom.y, quat_odom.z, quat_odom.w]
#             _, _, yaw_odom = tf_trans.euler_from_quaternion(q, 'sxyz')
#         except Exception as e:
#             rospy.logerr("提取里程计姿态失败: %s", e)
#             return

#         # 3. 计算 omega = pitch_cam + yaw_odom
#         omega = -pitch_cam + yaw_odom

#         # 4. 目标法线方向（世界系 [1,0,0] 转 omega）
#         dir_x = np.cos(omega)
#         dir_y = np.sin(omega)
#         dir_z = 0.0
#         normal_dir = np.array([dir_x, dir_y, dir_z])

#         # 5. 目标位置：板世界坐标减去法线方向 × 0.3m
#         pos_board = np.array([board_world.pose.pose.position.x,
#                               board_world.pose.pose.position.y,
#                               board_world.pose.pose.position.z])
#         target_pos = pos_board - 0.3 * normal_dir

#         # 6. 目标姿态：roll=0, pitch=0, yaw=omega
#         quat_target = tf_trans.quaternion_from_euler(0.0, 0.0, omega)

#         # 7. 发布
#         out = Odometry()
#         out.header.stamp = rospy.Time.now()
#         out.header.frame_id = board_world.header.frame_id   # 世界坐标系
#         out.child_frame_id = "robot_target"
#         out.pose.pose.position.x = target_pos[0]
#         out.pose.pose.position.y = target_pos[1]
#         out.pose.pose.position.z = target_pos[2]
#         out.pose.pose.orientation.x = quat_target[0]
#         out.pose.pose.orientation.y = quat_target[1]
#         out.pose.pose.orientation.z = quat_target[2]
#         out.pose.pose.orientation.w = quat_target[3]

#         try:
#             self.target_pub.publish(out)
#         except Exception as e:
#             rospy.logerr("发布目标位姿失败: %s", e)


# if __name__ == '__main__':
#     node = None
#     try:
#         node = RobotTargetGenerator()
#         rospy.spin()
#     except rospy.ROSInterruptException:
#         pass
#     except Exception as e:
#         rospy.logerr("节点意外终止: %s", e)
#         if node:
#             node._shutdown_hook()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import numpy as np
import tf.transformations as tf_trans
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool
from threading import Lock
import atexit

# ================= 用户可修改的启用开关 =================
ENABLE_ON_START = True   # 改 True 后启动，运动控制使能即生效
# ======================================================

class RobotTargetGenerator:
    def __init__(self):
        rospy.init_node('robot_target_generator')

        # 最近收到的消息缓存
        self.latest_board_world = None
        self.latest_board_cam   = None
        self.latest_odom        = None
        self.lock = Lock()

        # 平滑历史缓冲区
        self.pos_x_history = []
        self.pos_y_history = []
        self.pos_z_history = []
        self.yaw_history   = []
        self.window_size   = 10

        # 发布者
        self.target_pub = rospy.Publisher('/robot/targetOdom', Odometry, queue_size=1)
        self.enable_pub = rospy.Publisher('/state/car_control_enable', Bool, queue_size=1, latch=True)

        # 发布初始使能值
        self.enable_pub.publish(Bool(data=ENABLE_ON_START))
        rospy.loginfo(f"运动使能初始值: {ENABLE_ON_START}")

        # 订阅者
        rospy.Subscriber('/aprilTag/inWorld/targetOdom', Odometry, self.board_world_cb, queue_size=1)
        rospy.Subscriber('/aprilTag/inCamera/targetOdom', Odometry, self.board_cam_cb, queue_size=1)
        rospy.Subscriber('/filtered_odometry', Odometry, self.odom_cb, queue_size=1)

        # 退出处理
        atexit.register(self._shutdown_hook)
        rospy.on_shutdown(self._shutdown_hook)

        rospy.loginfo("节点启动，等待数据...")

    def _shutdown_hook(self):
        try:
            self.enable_pub.publish(Bool(data=False))
            rospy.loginfo("已发送使能信号: False (节点关闭)")
        except:
            pass

    def board_world_cb(self, msg):
        with self.lock:
            self.latest_board_world = msg
        self.try_compute_and_publish()

    def board_cam_cb(self, msg):
        with self.lock:
            self.latest_board_cam = msg

    def odom_cb(self, msg):
        with self.lock:
            self.latest_odom = msg

    def try_compute_and_publish(self):
        with self.lock:
            if self.latest_board_world is None or self.latest_board_cam is None or self.latest_odom is None:
                return
            board_world = self.latest_board_world
            board_cam   = self.latest_board_cam
            odom        = self.latest_odom

        # 1. 提取 inCamera 的 pitch 角
        try:
            quat_cam = board_cam.pose.pose.orientation
            q = [quat_cam.x, quat_cam.y, quat_cam.z, quat_cam.w]
            _, pitch_cam, _ = tf_trans.euler_from_quaternion(q, 'sxyz')
        except Exception as e:
            rospy.logerr("提取相机姿态失败: %s", e)
            return

        # 2. 提取 odom 的 yaw 角
        try:
            quat_odom = odom.pose.pose.orientation
            q = [quat_odom.x, quat_odom.y, quat_odom.z, quat_odom.w]
            _, _, yaw_odom = tf_trans.euler_from_quaternion(q, 'sxyz')
        except Exception as e:
            rospy.logerr("提取里程计姿态失败: %s", e)
            return

        # 3. 计算 omega = -pitch_cam + yaw_odom
        omega = -pitch_cam + yaw_odom

        # 4. 目标法线方向（世界系 [1,0,0] 转 omega）
        dir_x = np.cos(omega)
        dir_y = np.sin(omega)
        dir_z = 0.0
        normal_dir = np.array([dir_x, dir_y, dir_z])

        # 5. 目标位置：板世界坐标减去法线方向 × 0.3m
        pos_board = np.array([board_world.pose.pose.position.x,
                              board_world.pose.pose.position.y,
                              board_world.pose.pose.position.z])
        target_pos = pos_board - 0.3 * normal_dir

        # ---- 平滑处理 ----
        self.pos_x_history.append(target_pos[0])
        self.pos_y_history.append(target_pos[1])
        self.pos_z_history.append(target_pos[2])
        self.yaw_history.append(omega)

        # 保持窗口大小
        if len(self.pos_x_history) > self.window_size:
            self.pos_x_history.pop(0)
            self.pos_y_history.pop(0)
            self.pos_z_history.pop(0)
            self.yaw_history.pop(0)

        # 计算平均值（窗口内数据不足时用当前已有数据平均）
        smooth_x   = np.mean(self.pos_x_history)
        smooth_y   = np.mean(self.pos_y_history)
        smooth_z   = np.mean(self.pos_z_history)
        smooth_yaw = np.mean(self.yaw_history)

        # 6. 目标姿态：roll=0, pitch=0, yaw=平滑后的yaw
        quat_target = tf_trans.quaternion_from_euler(0.0, 0.0, smooth_yaw)

        # 7. 发布
        out = Odometry()
        out.header.stamp = rospy.Time.now()
        out.header.frame_id = board_world.header.frame_id   # 世界坐标系
        out.child_frame_id = "robot_target"
        out.pose.pose.position.x = smooth_x
        out.pose.pose.position.y = smooth_y
        out.pose.pose.position.z = smooth_z
        out.pose.pose.orientation.x = quat_target[0]
        out.pose.pose.orientation.y = quat_target[1]
        out.pose.pose.orientation.z = quat_target[2]
        out.pose.pose.orientation.w = quat_target[3]

        try:
            self.target_pub.publish(out)
        except Exception as e:
            rospy.logerr("发布目标位姿失败: %s", e)


if __name__ == '__main__':
    node = None
    try:
        node = RobotTargetGenerator()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr("节点意外终止: %s", e)
        if node:
            node._shutdown_hook()