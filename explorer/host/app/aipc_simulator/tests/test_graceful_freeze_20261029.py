"""KR260 优雅停止的离线回归：只检查源码与数值模型，不连接机械臂。"""
import math
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SIDE = ROOT / "kr260-side"
PLANNER_H = (SIDE / "arm_planner.h").read_text(encoding="utf-8")
PLANNER_CPP = (SIDE / "arm_planner.cpp").read_text(encoding="utf-8")
RUNNER_CPP = (SIDE / "teleop_task_runner.cpp").read_text(encoding="utf-8")


def function_body(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError("函数大括号未闭合：" + signature)


def smooth_step(target, smooth, max_step):
    delta = max(-max_step, min(max_step, target - smooth))
    return smooth + delta


class GracefulFreezeSourceContract(unittest.TestCase):
    def test_public_dual_arm_freeze_interface_exists(self):
        self.assertIn("void freezeDualArmAtSmoothPosition();", PLANNER_H)

    def test_freeze_uses_same_lock_order_as_planner(self):
        body = function_body(PLANNER_CPP, "void ArmPlanner::freezeDualArmAtSmoothPosition()")
        left = body.index("left_arm_target_joint_pos_mtx_")
        right = body.index("right_arm_target_joint_pos_mtx_")
        self.assertLess(left, right)
        plan = function_body(PLANNER_CPP, "void ArmPlanner::threadPlan()")
        self.assertLess(plan.index("left_arm_target_joint_pos_mtx_"),
                        plan.index("right_arm_target_joint_pos_mtx_"))

    def test_freeze_copies_smooth_to_target_only_after_initialization(self):
        body = function_body(PLANNER_CPP, "void ArmPlanner::freezeDualArmAtSmoothPosition()")
        for side in ("left", "right"):
            self.assertIn(f"if ( this->{side}_arm_smooth_init_ )", body)
            self.assertIn(
                f"this->{side}_arm_target_joint_pos_ = this->{side}_arm_smooth_joint_pos_;",
                body,
            )
        self.assertNotIn("getLeftJointPosition", body)
        self.assertNotIn("getRightJointPosition", body)

    def test_single_arm_hold_is_atomic_and_has_no_unlocked_getter(self):
        for side in ("Left", "Right"):
            signature = f"void ArmPlanner::freeze{side}ArmAtSmoothPosition()"
            self.assertIn(f"void freeze{side}ArmAtSmoothPosition();", PLANNER_H)
            body = function_body(PLANNER_CPP, signature)
            lower = side.lower()
            self.assertIn(f"{lower}_arm_target_joint_pos_mtx_", body)
            self.assertIn(
                f"this->{lower}_arm_target_joint_pos_ = this->{lower}_arm_smooth_joint_pos_;",
                body,
            )
        process = function_body(RUNNER_CPP, "void TeleopTaskRunner::processTeleopSetpoint")
        self.assertIn("s.freezeAtSmooth", process)
        self.assertNotIn("getSmooth", process)
        self.assertNotIn("getLeftSmoothJointPosition", PLANNER_H + PLANNER_CPP)
        self.assertNotIn("getRightSmoothJointPosition", PLANNER_H + PLANNER_CPP)

    def test_runner_stop_freezes_instead_of_tracking_feedback(self):
        body = function_body(RUNNER_CPP, "void TeleopTaskRunner::stop()")
        self.assertIn("this->planner_->freezeDualArmAtSmoothPosition();", body)
        self.assertNotIn("setLeftArmTargetJointPosition", body)
        self.assertNotIn("setRightArmTargetJointPosition", body)
        self.assertNotIn("getLeftJointPosition", body)
        self.assertNotIn("getRightJointPosition", body)

    def test_stream_protection_and_shutdown_order_are_preserved(self):
        body = function_body(RUNNER_CPP, "void TeleopTaskRunner::stop()")
        freeze = body.index("freezeDualArmAtSmoothPosition")
        hold = body.index("std::chrono::milliseconds(300)")
        planner_stop = body.index("this->planner_->stop()")
        controller_stop = body.index("this->controller_->stop()")
        self.assertLess(freeze, hold)
        self.assertLess(hold, planner_stop)
        self.assertLess(planner_stop, controller_stop)


class GracefulFreezeNumericModel(unittest.TestCase):
    def test_feedback_target_reverses_but_smooth_freeze_does_not(self):
        feedback = math.radians(32.0)
        smooth = math.radians(40.0)
        distant_target = math.radians(80.0)
        max_step = 0.8 / 100.0  # 0.8 rad/s，100 Hz 离线示例

        old_next = smooth_step(feedback, smooth, max_step)
        new_next = smooth_step(smooth, smooth, max_step)

        self.assertLess(old_next, smooth)
        self.assertAlmostEqual(math.degrees(old_next - smooth), -0.458366, places=5)
        self.assertEqual(new_next, smooth)
        self.assertGreater(distant_target, smooth)  # 明确旧目标仍在更前方

    def test_repeated_freeze_is_stationary_for_every_joint(self):
        target = [math.radians(v) for v in (150, 100, -35, -50, -60, 30)]
        smooth = [math.radians(v) for v in (145, 96, -32, -46, -58, 27)]
        frozen = list(smooth)
        for _ in range(30):  # 300 ms / 10 ms
            smooth = [smooth_step(t, s, 0.008) for t, s in zip(frozen, smooth)]
        self.assertEqual(smooth, frozen)
        self.assertNotEqual(smooth, target)


if __name__ == "__main__":
    unittest.main()
