#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探路者只读延迟测量：实时杯子目标＋规划预检，不创建运动会话。

在 AIPC 运行：
  python3 measure_latency.py collect --trials 100 --out results
  python3 measure_latency.py summarize results/trials.csv --out results

collect 仅调用 /api/grasp_target_preview 与 /api/vla_motion_execute(stage=preview)。
它不调用 execute，不发送关节、夹爪或底盘运动命令。
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
import urllib.request
import urllib.error

CONSOLE = 'http://127.0.0.1:8092'
FIELDS = [
    'trial', 'wall_unix', 'success', 'error', 'label', 'confidence',
    'target_latency_ms', 'rgb_fetch_ms', 'depth_fetch_ms', 'model_prepare_ms',
    'yolo_inference_ms', 'coordinate_transform_ms', 'target_http_ms',
    'planning_http_ms', 'target_plus_planning_ms', 'planned_duration_s',
    'planning_nodes', 'target_x_m', 'target_y_m', 'target_z_m',
]
METRICS = ['target_latency_ms', 'rgb_fetch_ms', 'depth_fetch_ms', 'model_prepare_ms',
           'yolo_inference_ms', 'coordinate_transform_ms', 'target_http_ms',
           'planning_http_ms', 'target_plus_planning_ms', 'planned_duration_s']


def post(path, payload, timeout=90):
    began = time.perf_counter()
    request = urllib.request.Request(
        CONSOLE + path, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        try:
            detail = json.loads(detail).get('error', detail)
        except json.JSONDecodeError:
            pass
        raise ValueError(f'HTTP {exc.code}: {detail}') from None
    elapsed_ms = (time.perf_counter() - began) * 1000
    if not body.get('ok', False):
        raise ValueError(body.get('error', '接口返回失败'))
    return body, elapsed_ms


def percentile_nearest(sorted_values, probability):
    """最近秩百分位，定义写入 summary，避免不同软件口径含混。"""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(probability * len(sorted_values)))
    return sorted_values[rank - 1]


def summarize_values(values):
    values = sorted(float(v) for v in values
                    if isinstance(v, (int, float)) and math.isfinite(v))
    if not values:
        return None
    return {
        'count': len(values), 'unit': 'ms' if 'duration' not in 'ms' else 'ms',
        'p50': percentile_nearest(values, 0.50),
        'p95': percentile_nearest(values, 0.95),
        'p99': percentile_nearest(values, 0.99),
        'max': values[-1], 'mean': statistics.fmean(values), 'min': values[0],
    }


def summarize_file(input_path, out_dir):
    with open(input_path, encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    summary = {'source': str(input_path), 'total_trials': len(rows),
               'successful_trials': sum(row.get('success') == '1' for row in rows),
               'percentile_method': 'nearest-rank', 'metrics': {}}
    for name in METRICS:
        values = []
        for row in rows:
            try:
                value = float(row.get(name, ''))
                if math.isfinite(value):
                    values.append(value)
            except (TypeError, ValueError):
                pass
        result = summarize_values(values)
        if result:
            result['unit'] = 's' if name == 'planned_duration_s' else 'ms'
            summary['metrics'][name] = result
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out_dir/'metrics.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['metric', 'count', 'unit', 'p50', 'p95', 'p99', 'max', 'mean', 'min'])
        for name, result in summary['metrics'].items():
            writer.writerow([name, result['count'], result['unit'], result['p50'],
                             result['p95'], result['p99'], result['max'],
                             result['mean'], result['min']])
    return summary


def collect(trials, side, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir/'trials.csv'
    with output.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for trial in range(1, trials + 1):
            row = {name: '' for name in FIELDS}
            row.update(trial=trial, wall_unix=time.time(), success='0')
            target_began = time.perf_counter()
            try:
                target_process_started = time.perf_counter()
                command = ['/usr/bin/python3', '-c',
                    'import json,sys;sys.path.insert(0,"/home/apex");'
                    'from grasp_target_bridge import run;'
                    f'print(json.dumps(run({{"side":"{side}"}})))']
                completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
                target_http = (time.perf_counter()-target_process_started)*1000
                target = json.loads(completed.stdout.strip().splitlines()[-1])
                if completed.returncode or not target.get('ok'):
                    raise ValueError(target.get('error') or completed.stderr[-300:])
                timing = target.get('timing_ms', {})
                row.update(label=target.get('label', ''), confidence=target.get('confidence', ''),
                           target_latency_ms=timing.get('locate_total', ''),
                           rgb_fetch_ms=timing.get('rgb_fetch', ''),
                           depth_fetch_ms=timing.get('depth_fetch', ''),
                           model_prepare_ms=timing.get('model_prepare', ''),
                           yolo_inference_ms=timing.get('yolo_inference', ''),
                           coordinate_transform_ms=timing.get('coordinate_transform', ''),
                           target_http_ms=target_http)
                xyz = target['xyz']
                row.update(target_x_m=xyz[0], target_y_m=xyz[1], target_z_m=xyz[2])
                plan, planning_http = post('/api/vla_motion_execute',
                    {'side': side, 'xyz': xyz, 'stage': 'preview', 'collision_mode': 'exact',
                     'nearest_orientation': True})
                row.update(planning_http_ms=planning_http,
                           planned_duration_s=plan.get('duration_s', ''),
                           planning_nodes=plan.get('path_nodes_before_timing', ''),
                           target_plus_planning_ms=(time.perf_counter()-target_began)*1000,
                           success='1')
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
            writer.writerow(row)
            handle.flush()
            print(f"[{trial}/{trials}] {'OK' if row['success'] == '1' else 'FAIL'} "
                  f"target={row['target_latency_ms']} ms plan_http={row['planning_http_ms']} ms "
                  f"{row['error']}", flush=True)
    return summarize_file(output, out_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('collect', help='只读采集目标与规划延迟')
    run.add_argument('--trials', type=int, default=100)
    run.add_argument('--side', choices=['left', 'right'], default='left')
    run.add_argument('--out', type=Path, default=Path('results'))
    stat = sub.add_parser('summarize', help='重算已有 trials.csv')
    stat.add_argument('input', type=Path)
    stat.add_argument('--out', type=Path, default=Path('results'))
    args = parser.parse_args()
    if args.command == 'collect':
        if args.trials < 1:
            parser.error('--trials 必须大于 0')
        summary = collect(args.trials, args.side, args.out)
    else:
        summary = summarize_file(args.input, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
