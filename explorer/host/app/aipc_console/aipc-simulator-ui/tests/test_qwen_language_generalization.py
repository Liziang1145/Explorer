# -*- coding: utf-8 -*-
"""真实千问多说法解析回归：只调用 interpret，不生成计划、不连接执行接口。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BRIDGE = 'http://127.0.0.1:8102'
REPORT = Path('/home/apex/outputs/qwen_language_generalization.json')
POSITIVE = [
    '用传统规划把杯子抓起来',
    '请通过 RRT 和 TOPP-RA 抓取杯子。',
    '麻烦你让左臂拿起桌上的杯子',
    '能不能用传统规划帮我拿一下水杯？',
    '用规划器拾取杯子，不要走学习策略。',
    'Pick up the cup with the planner.',
    'Use RRT to grasp the cup, please.',
    '用传统方式抓那个杯子就行',
    '左臂执行杯子抓取任务，走传统规划分支',
    '请规划一条轨迹，把杯子拿起来',
]
NEGATIVE = [
    '用传统规划把瓶子抓起来',
    '用传统规划让右臂抓杯子',
    '用传统规划把杯子放下',
    '用传统规划把木块抓起来',
]


def interpret(text):
    request = Request(BRIDGE + '/api/task/interpret',
        data=json.dumps({'text': text, 'executor': 'planner'}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=280) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def save_report(results):
    previous = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    by_input = {item['input']: item for item in previous.get('cases', [])}
    by_input.update({item['input']: item for item in results})
    ordered = [by_input[text] for text in POSITIVE + NEGATIVE if text in by_input]
    report = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'interpret_only', 'plan_generation_called': False, 'execution_sent': False,
        'passed': sum(item['passed'] for item in ordered), 'total': len(ordered),
        'all_passed': len(ordered) == len(POSITIVE + NEGATIVE) and all(item['passed'] for item in ordered),
        'cases': ordered,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int, default=4)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    cases = [(text, True) for text in POSITIVE] + [(text, False) for text in NEGATIVE]
    if args.fresh and REPORT.exists():
        REPORT.unlink()
    results = []
    for text, supported in cases[args.start:args.start + args.limit]:
        status, payload = interpret(text)
        task = payload.get('task', {})
        normalized = (task.get('action') == 'pick' and task.get('target') == 'cup' and
                      task.get('arm') == 'left' and task.get('executor') == 'planner' and
                      task.get('instruction') == 'Pick up the cup.')
        passed = status == 200 and normalized if supported else status == 422 and not normalized
        results.append({'input': text, 'expected': 'accept_cup_pick' if supported else 'reject',
                        'passed': passed, 'http_status': status, 'task': task or None,
                        'error': payload.get('error'), 'elapsed_s': payload.get('elapsed_s'),
                        'execution_sent': False})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
        save_report(results)
    report = save_report(results)
    print(json.dumps({'report': str(REPORT), 'passed': report['passed'],
                      'total': report['total'], 'all_passed': report['all_passed']},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
