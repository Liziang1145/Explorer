import time
import unittest
from unittest.mock import patch
import qwen_task_bridge as bridge


class QwenTaskBridgeTests(unittest.TestCase):
    def setUp(self):
        bridge.PLANS.clear()

    def valid(self, executor='vla'):
        return {'action': 'pick', 'target': 'cup', 'executor': executor,
                'arm': 'left', 'instruction': 'Pick up the cup.'}

    def awaiting_plan(self):
        now = time.time()
        return {'plan_id': 'test-plan', 'state': 'awaiting_confirmation',
                'xyz': [0.0, 0.3, 0.1], 'safety_epoch': 7,
                'created_at': now, 'updated_at': now, 'expires_at': now + 60,
                'task': self.valid('planner')}

    def test_vla_task_is_dry_run_and_requires_confirmation(self):
        task = validate = bridge.validate_task(self.valid())
        self.assertEqual(validate['schema'], 'aipc.task.v1')
        self.assertTrue(validate['dry_run'])
        self.assertTrue(validate['requires_confirmation'])
        self.assertFalse(bridge.preview_for(task)['execution_sent'])

    def test_planner_branch(self):
        task = bridge.validate_task(self.valid('planner'), 'planner')
        self.assertIn('真实识别并精确预检', bridge.preview_for(task)['stages'])

    def test_rejects_other_object(self):
        raw = self.valid()
        raw['target'] = 'bottle'
        with self.assertRaises(ValueError):
            bridge.validate_task(raw)

    def test_rejects_extra_action_field(self):
        raw = self.valid()
        raw['execute'] = True
        with self.assertRaises(ValueError):
            bridge.validate_task(raw)

    def test_rejects_wrong_task_text(self):
        raw = self.valid()
        raw['instruction'] = 'Pick up the cup'
        with self.assertRaises(ValueError):
            bridge.validate_task(raw)

    def test_explicit_branch_selection_does_not_require_repetition(self):
        task = bridge.validate_task(self.valid(), 'planner')
        self.assertEqual(task['executor'], 'planner')
        self.assertEqual(task['target'], 'cup')

    @patch('qwen_task_bridge.execute_motion')
    def test_plan_generation_never_executes(self, execute):
        parsed = {'task': self.valid('planner')}
        target = {'xyz': [0.0, 0.3, 0.1], 'label': 'cup', 'confidence': 0.9}
        preview = {'execution_allowed': True, 'duration_s': 4.0}
        with patch('qwen_task_bridge.interpret', return_value=parsed), \
             patch('qwen_task_bridge.safety_now', return_value=7), \
             patch('qwen_task_bridge.console_request', side_effect=[target, preview]):
            plan = bridge.create_plan('用传统规划抓杯子')
        self.assertEqual(plan['state'], 'awaiting_confirmation')
        self.assertTrue(plan['confirm_required'])
        self.assertFalse(plan['execution_sent'])
        execute.assert_not_called()

    @patch('qwen_task_bridge.run_confirmed_plan')
    @patch('qwen_task_bridge.safety_now', return_value=7)
    def test_execution_requires_exact_confirmation(self, safety, worker):
        plan = self.awaiting_plan()
        bridge.PLANS[plan['plan_id']] = plan
        with self.assertRaises(ValueError):
            bridge.confirm_plan(plan['plan_id'], '是的')
        self.assertEqual(plan['state'], 'awaiting_confirmation')
        worker.assert_not_called()
        accepted = bridge.confirm_plan(plan['plan_id'], '确认执行', start_worker=False)
        self.assertEqual(accepted['state'], 'accepted')
        with self.assertRaises(ValueError):
            bridge.confirm_plan(plan['plan_id'], '确认执行', start_worker=False)

    @patch('qwen_task_bridge.safety_now', return_value=8)
    def test_safety_epoch_change_rejects_confirmation(self, safety):
        plan = self.awaiting_plan()
        bridge.PLANS[plan['plan_id']] = plan
        with self.assertRaises(ValueError):
            bridge.confirm_plan(plan['plan_id'], '确认执行', start_worker=False)
        self.assertEqual(bridge.PLANS[plan['plan_id']]['state'], 'failed')

    def test_expired_plan_cannot_be_confirmed(self):
        plan = self.awaiting_plan()
        plan['expires_at'] = time.time() - 1
        bridge.PLANS[plan['plan_id']] = plan
        with self.assertRaises(ValueError):
            bridge.confirm_plan(plan['plan_id'], '确认执行', start_worker=False)
        self.assertEqual(plan['state'], 'expired')


if __name__ == '__main__':
    unittest.main()
