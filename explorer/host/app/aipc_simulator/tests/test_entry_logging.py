# -*- coding: utf-8 -*-
"""入口逐帧诊断日志；全部离线，不访问控制台或执行器。"""
import csv
import pathlib
import tempfile
import unittest
from unittest import mock

import arm_console as app
from arm_entry import EntrySequence


class EntryLoggingTests(unittest.TestCase):
    def test_abort_log_separates_held_command_from_feedback(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(app, 'ENTRY_LOG_DIR', folder), \
                mock.patch.object(app, 'left_read', return_value=(True, [5, 1, -1, 0, 0, 0])), \
                mock.patch.object(app.SAFETY, 'stopped', False), \
                mock.patch.object(app, 'stop_all'):
            entry = EntrySequence([0] * 6, [0.5, 0.2, -0.2, 0, 0, 0], app.time.monotonic())
            sender = app.ControlSender()
            sender.entries['left'] = entry
            app.entry_log_start('left', entry)
            sender._entry_feedback('left', entry)
            with open(entry.log_path, newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['event'], 'start')
        self.assertEqual(rows[-1]['event'], 'abort')
        self.assertGreaterEqual(len(rows), 3)
        sample = rows[1]
        self.assertEqual(sample['cmd_J1_deg'], '0.0')
        self.assertEqual(sample['hold_ref_J1_deg'], '0.0')
        self.assertEqual(sample['feedback_J1_deg'], '5.0')
        self.assertIn('偏差 +5.000°', rows[-1]['note'])
        self.assertIn('指令 0.000°', rows[-1]['note'])


if __name__ == '__main__':
    unittest.main()
