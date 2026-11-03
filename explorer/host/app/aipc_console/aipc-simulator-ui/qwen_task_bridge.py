# -*- coding: utf-8 -*-
"""千问任务解析、真实传统规划与人工确认执行。VLA 分支仅做任务预览。"""
import json
import math
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

HOST = os.environ.get('QWEN_BRIDGE_HOST', '0.0.0.0')
PORT = int(os.environ.get('QWEN_BRIDGE_PORT', '8102'))
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
CONSOLE_URL = os.environ.get('CONSOLE_URL', 'http://127.0.0.1:8092')
QWEN_MODEL = os.environ.get('QWEN_MODEL', 'qwen3.6:35b')
PLAN_TTL_S = 60.0

SYSTEM_PROMPT = '''你是机器人任务翻译器，只输出 JSON，不要解释。
只支持左臂抓取杯子。支持的任务字段为：
{"action":"pick","target":"cup","executor":"vla或planner","arm":"left","instruction":"Pick up the cup."}
用户指定 VLA、端到端或学习策略时 executor=vla；指定传统规划、RRT 或 TOPP-RA 时 executor=planner。
未指定执行方式时 executor=vla。
如果不是抓取动作，action=unsupported；如果不是杯子，target=other；如果不是左臂，arm=other。
unsupported/other 是明确的拒绝标记，后端会拒绝这些任务，不得改写成受支持任务。'''
TASK_SCHEMA = {
    'type': 'object',
    'properties': {
        'action': {'type': 'string', 'enum': ['pick', 'unsupported']},
        'target': {'type': 'string', 'enum': ['cup', 'other']},
        'executor': {'type': 'string', 'enum': ['vla', 'planner']},
        'arm': {'type': 'string', 'enum': ['left', 'other']},
        'instruction': {'type': 'string', 'enum': ['Pick up the cup.']},
    },
    'required': ['action', 'target', 'executor', 'arm', 'instruction'],
    'additionalProperties': False,
}

PLANS = {}
PLANS_LOCK = threading.RLock()


def validate_task(raw, requested_executor='auto'):
    if not isinstance(raw, dict):
        raise ValueError('千问返回的任务不是 JSON 对象')
    allowed = {'action', 'target', 'executor', 'arm', 'instruction'}
    if set(raw) != allowed:
        raise ValueError('任务字段不完整或包含额外字段')
    if raw.get('action') != 'pick' or raw.get('target') != 'cup':
        raise ValueError('当前仅支持抓取杯子')
    if raw.get('arm') != 'left':
        raise ValueError('当前仅支持左臂')
    executor = raw.get('executor')
    if executor not in ('vla', 'planner'):
        raise ValueError('executor 只能是 vla 或 planner')
    # 页面明确选择的分支是执行配置，不应要求用户在每句自然语言中重复。
    # 动作、物体和手臂仍必须由千问按支持范围解析，不能用分支覆盖任务语义。
    if requested_executor != 'auto':
        raw = {**raw, 'executor': requested_executor}
        executor = requested_executor
    if raw.get('instruction') != 'Pick up the cup.':
        raise ValueError('VLA 标准指令不符合数据集任务文本')
    return {'schema': 'aipc.task.v1', **raw, 'dry_run': True, 'requires_confirmation': True}


def preview_for(task):
    if task['executor'] == 'vla':
        stages = ['读取相机与左臂状态', 'SmolVLA 生成动作块', '安全检查后等待人工确认']
    else:
        stages = ['真实识别并精确预检', '移动到预抓点', '前进 6 cm 并闭爪', '抬升 2 cm']
    return {'branch': task['executor'], 'stages': stages, 'execution_sent': False}


def interpret(text, executor='auto', timeout=280):
    if not text or len(text) > 200:
        raise ValueError('指令长度必须为 1～200 个字符')
    if executor not in ('auto', 'vla', 'planner'):
        raise ValueError('未知执行分支')
    # 当前是单任务受控演示：明确超出范围的常见词直接拒绝，避免结构化
    # 输出约束与不支持语义冲突时长时间推理。任何模糊输入默认不放行。
    if any(term in text for term in ('右臂', '右手', '放下', '松开', '瓶子', '木块')):
        raise ValueError('当前仅支持左臂抓取杯子，不支持该动作、目标或手臂')
    body = json.dumps({
        'model': QWEN_MODEL, 'stream': False, 'format': TASK_SCHEMA,
        'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                     {'role': 'user', 'content': text}],
        'options': {'temperature': 0},
    }).encode('utf-8')
    started = time.monotonic()
    request = Request(OLLAMA_URL + '/api/chat', data=body,
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    content = payload.get('message', {}).get('content', '')
    try:
        raw_task = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError('未生成受支持的任务；当前仅支持左臂抓取杯子') from None
    task = validate_task(raw_task, executor)
    return {'ok': True, 'task': task, 'preview': preview_for(task), 'model': QWEN_MODEL,
            'elapsed_s': round(time.monotonic() - started, 2),
            'note': '仅完成任务解析与分支预览，未向控制台或机械臂发送执行指令。'}


def console_request(path, data=None, timeout=120):
    body = None if data is None else json.dumps(data).encode('utf-8')
    request = Request(CONSOLE_URL + path, data=body,
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not payload.get('ok', True):
        raise ValueError(payload.get('error') or '控制台请求失败')
    return payload


def safety_now():
    state = console_request('/api/safety', timeout=10)
    if state.get('stopped') or state.get('pending'):
        raise ValueError('软件停止已锁定或正在停止，不能计划或执行')
    epoch = state.get('epoch')
    if epoch is None:
        raise ValueError('控制台没有提供安全代次')
    return epoch


def public_plan(plan):
    return {key: value for key, value in plan.items() if not key.startswith('_')}


def update_plan(plan_id, **changes):
    with PLANS_LOCK:
        plan = PLANS.get(plan_id)
        if plan is not None:
            plan.update(changes, updated_at=time.time())


def create_plan(text, executor='planner'):
    parsed = interpret(text, executor)
    task = parsed['task']
    if task['executor'] != 'planner':
        raise ValueError('真实计划生成当前仅支持传统规划分支')
    with PLANS_LOCK:
        if any(p.get('state') in ('accepted', 'running') for p in PLANS.values()):
            raise ValueError('已有确认后的任务正在执行，不能生成新计划')
    epoch = safety_now()
    target = console_request('/api/grasp_target_preview', {'side': 'left'}, timeout=55)
    xyz = target.get('xyz')
    if not isinstance(xyz, list) or len(xyz) != 3 or not all(math.isfinite(v) for v in xyz):
        raise ValueError('实时目标接口没有返回有效预抓 J5 坐标')
    preview = console_request('/api/vla_motion_execute', {
        'stage': 'preview', 'side': 'left', 'xyz': xyz,
        'collision_mode': 'exact', 'pregrasp': True,
    }, timeout=180)
    if preview.get('execution_allowed') is False:
        raise ValueError('预抓轨迹超过网页执行速度或时长上限')
    now = time.time()
    plan_id = uuid.uuid4().hex
    plan = {
        'ok': True, 'plan_id': plan_id, 'state': 'awaiting_confirmation',
        'task': task, 'side': 'left', 'xyz': xyz,
        'target_label': target.get('label'), 'confidence': target.get('confidence'),
        'created_at': now, 'updated_at': now, 'expires_at': now + PLAN_TTL_S,
        'safety_epoch': epoch, 'current_stage': 'pregrasp_preview',
        'stages': ['移动到预抓点', '水平向前 6 cm，到位前闭爪', '保持闭爪并抬升 2 cm'],
        'duration_s': preview.get('duration_s'),
        'minimum_mesh_clearance_cm': preview.get('minimum_mesh_clearance_cm'),
        'max_joint_velocity_rad_s': preview.get('max_joint_velocity_rad_s'),
        'confirm_required': True, 'execution_sent': False,
        'message': '真实目标与预抓轨迹预检已完成；60 秒内需要人工确认。',
    }
    with PLANS_LOCK:
        PLANS[plan_id] = plan
    return public_plan(plan)


def get_plan(plan_id):
    with PLANS_LOCK:
        plan = PLANS.get(plan_id)
        if plan is None:
            raise ValueError('计划不存在')
        if plan['state'] == 'awaiting_confirmation' and time.time() > plan['expires_at']:
            plan.update(state='expired', message='计划已过期，请重新识别和预检', updated_at=time.time())
        return public_plan(plan)


def cancel_plan(plan_id):
    with PLANS_LOCK:
        plan = PLANS.get(plan_id)
        if plan is None:
            raise ValueError('计划不存在')
        if plan['state'] != 'awaiting_confirmation':
            raise ValueError('计划已确认或已结束，不能通过取消接口停止；需要停止时请使用全局停止')
        plan.update(state='cancelled', message='人工取消，未发送执行指令', updated_at=time.time())
        return public_plan(plan)


def check_epoch(epoch):
    if safety_now() != epoch:
        raise ValueError('安全代次已变化，旧任务已中止')


def execute_motion(xyz, epoch, pregrasp=False):
    options = {'side': 'left', 'xyz': xyz, 'collision_mode': 'exact',
               'safety_epoch': epoch}
    if pregrasp:
        options['pregrasp'] = True
    else:
        options['nearest_orientation'] = True
    checked = console_request('/api/vla_motion_execute', {'stage': 'preview', **options}, timeout=180)
    if checked.get('execution_allowed') is False:
        raise ValueError('轨迹超过执行速度或时长上限')
    check_epoch(epoch)
    accepted = console_request('/api/vla_motion_execute', {'stage': 'execute', **options}, timeout=180)
    if not accepted.get('move_seq'):
        raise ValueError('执行接口没有返回动作号')
    return accepted


def wait_motion(seq, epoch, close_gripper_at=None):
    started = time.monotonic()
    closed = False
    while True:
        check_epoch(epoch)
        status = console_request('/api/status', timeout=10)
        result = status.get('control', {}).get('move_result', {}).get('left', {})
        elapsed = time.monotonic() - started
        if close_gripper_at is not None and not closed and elapsed >= close_gripper_at:
            console_request('/api/intent', {'intent': 'gripper', 'side': 'left',
                                            'open': 0.0, 'safety_epoch': epoch}, timeout=10)
            closed = True
        if result.get('seq') == seq and result.get('state') == 'done':
            return
        if result.get('seq') == seq and result.get('state') in ('failed', 'cancelled'):
            raise ValueError(result.get('message') or '运动未成功完成')
        if elapsed > 75:
            raise ValueError('等待机械臂真实到位超时')
        time.sleep(0.25)


def run_confirmed_plan(plan_id):
    try:
        plan = get_plan(plan_id)
        epoch = plan['safety_epoch']
        base = plan['xyz']
        grasp = [base[0], base[1] + 0.06, base[2]]
        lift = [grasp[0], grasp[1], grasp[2] + 0.02]
        update_plan(plan_id, state='running', current_stage='pregrasp',
                    execution_sent=True, message='正在移动到预抓点')
        accepted = execute_motion(base, epoch, pregrasp=True)
        wait_motion(accepted['move_seq'], epoch)
        update_plan(plan_id, current_stage='approach_and_close', message='正在向前 6 cm，末段闭合夹爪')
        accepted = execute_motion(grasp, epoch)
        wait_motion(accepted['move_seq'], epoch,
                    close_gripper_at=float(accepted['duration_s']) * 0.75)
        console_request('/api/intent', {'intent': 'gripper', 'side': 'left',
                                        'open': 0.0, 'safety_epoch': epoch}, timeout=10)
        time.sleep(1.2)
        check_epoch(epoch)
        update_plan(plan_id, current_stage='lift', message='夹爪保持闭合，正在抬升 2 cm')
        accepted = execute_motion(lift, epoch)
        wait_motion(accepted['move_seq'], epoch)
        update_plan(plan_id, state='done', current_stage='done',
                    message='预抓、闭爪和抬升三段均已真实到位')
    except Exception as exc:
        update_plan(plan_id, state='failed', current_stage='failed',
                    message='任务中止：' + str(exc))


def confirm_plan(plan_id, confirmation, start_worker=True):
    if confirmation != '确认执行':
        raise ValueError('必须提供明确的人工确认文本')
    with PLANS_LOCK:
        plan = PLANS.get(plan_id)
        if plan is None:
            raise ValueError('计划不存在')
        if plan['state'] != 'awaiting_confirmation':
            raise ValueError('计划已确认、过期或取消，不能重复执行')
        if time.time() > plan['expires_at']:
            plan.update(state='expired', message='计划已过期', updated_at=time.time())
            raise ValueError('计划已超过 60 秒，请重新生成')
        epoch = plan['safety_epoch']
        plan.update(state='accepted', message='人工确认已收到，准备执行', updated_at=time.time())
    try:
        check_epoch(epoch)
    except Exception:
        update_plan(plan_id, state='failed', message='确认时安全检查未通过')
        raise
    if start_worker:
        threading.Thread(target=run_confirmed_plan, args=(plan_id,), daemon=True).start()
    return get_plan(plan_id)


class Handler(BaseHTTPRequestHandler):
    def _origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.hostname == self.headers.get('Host', '').split(':')[0] and parsed.port in (8091, 8102)

    def _reply(self, data, status=200):
        if not self._origin_ok():
            status, data = 403, {'ok': False, 'error': '来源不受信任'}
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if self.headers.get('Origin') and self._origin_ok():
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_OPTIONS(self):
        if not self._origin_ok():
            return self._reply({'ok': False, 'error': '来源不受信任'}, 403)
        self.send_response(204)
        if self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            return self._reply({'ok': True, 'model': QWEN_MODEL,
                                'mode': 'planner_confirmation_required',
                                'active_plans': sum(p.get('state') in ('accepted', 'running')
                                                    for p in PLANS.values())})
        if parsed.path == '/api/task/plan/status':
            try:
                return self._reply({'ok': True, 'plan': get_plan(parse_qs(parsed.query).get('plan_id', [''])[0])})
            except ValueError as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 404)
        self._reply({'ok': False, 'error': 'not found'}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 4096:
                raise ValueError('请求体大小无效')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('请求必须为 JSON 对象')
            if self.path == '/api/task/interpret':
                return self._reply(interpret(str(data.get('text', '')).strip(),
                                             data.get('executor', 'auto')))
            if self.path == '/api/task/plan':
                return self._reply(create_plan(str(data.get('text', '')).strip(),
                                               data.get('executor', 'planner')))
            if self.path == '/api/task/plan/confirm':
                return self._reply({'ok': True, 'plan': confirm_plan(
                    str(data.get('plan_id', '')), data.get('confirmation'))}, 202)
            if self.path == '/api/task/plan/cancel':
                return self._reply({'ok': True, 'plan': cancel_plan(str(data.get('plan_id', '')))})
            return self._reply({'ok': False, 'error': 'not found'}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self._reply({'ok': False, 'error': str(exc), 'execution_sent': False}, 422)
        except Exception as exc:
            self._reply({'ok': False, 'error': '任务服务失败：' + str(exc)}, 502)

    def log_message(self, fmt, *args):
        print('qwen-task-bridge: ' + fmt % args, flush=True)


if __name__ == '__main__':
    print(f'Qwen task bridge on {HOST}:{PORT}; model={QWEN_MODEL}; confirmation required', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
