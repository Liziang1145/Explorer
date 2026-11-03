(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const API = '/api/v1/core-metrics';
  let state = null, selected = '', recordsKey = '', records = [], loading = false;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const number = n => typeof n === 'number' && Number.isFinite(n) ? n.toFixed(2) : '—';
  const legacyNumber = value => value === '' || value === null || value === undefined ? '—' : number(Number(value));
  async function api(path, body) {
    const response = await fetch(API + path, {
      method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-Hub-Client': 'console'},
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function notice(message, isError = false) {
    $('vla-notice').textContent = message;
    $('vla-notice').classList.toggle('error', isError);
  }
  function row(cells) {
    const tr = el('tr', '');
    for (const value of cells) tr.append(el('td', String(value)));
    return tr;
  }
  function selectedTask() {
    return (state?.history || []).find(task => task.id === selected) || null;
  }
  function render() {
    if (!state) return;
    const running = state.running;
    $('vla-start').disabled = !!running;
    $('vla-stop').disabled = !running;
    $('vla-state').textContent = running
      ? `运行中 ${running.trials_done} / ${running.trials_requested}`
      : '空闲 · 不发送运动指令';
    const choices = $('vla-select'), previous = selected || choices.value;
    choices.replaceChildren();
    for (const task of state.history) {
      const option = el('option', `${new Date(task.created * 1000).toLocaleString('zh-CN')} · ${task.name} · ${task.trials_done || 0} 次`);
      option.value = task.id;
      choices.append(option);
    }
    selected = state.history.some(task => task.id === previous) ? previous : state.history[0]?.id || '';
    choices.value = selected;
    const task = selectedTask();
    $('vla-delete').disabled = !task || task.status === 'running' || running?.id === task.id;
    if (!task) {
      $('vla-meta').textContent = '尚无测量轮次';
      $('vla-kpis').replaceChildren();
      $('vla-stages').replaceChildren();
      $('vla-samples').textContent = '暂无原始记录';
      return;
    }
    const type = task.legacy ? '历史 CPU 基线（未测自然语言）' : '新 GPU 只读 VLA 链路';
    $('vla-meta').textContent = `${type} · ${task.status} · ${task.device} · ${task.measurement_boundary}`;
    const cards = [
      ['完成预检', `${task.successful_trials || 0} / ${task.trials_done || 0}`, '失败样本也留库'],
      ['任务输入', task.legacy ? '无自然语言' : '本地千问', task.legacy ? '仅视觉与规划' : task.instruction],
      ['视觉推理', task.device || '—', task.vision_model || '—'],
      ['原始数据库', 'vla', '独立新增 5 GB 循环保留']
    ];
    $('vla-kpis').replaceChildren(...cards.map(([title, value, detail]) => {
      const card = el('article', '', 'cm-kpi');
      card.append(el('small', title), el('strong', value), el('p', detail));
      return card;
    }));
    const stages = task.legacy ? [
      ['YOLO predict() · CPU', 'yolo_inference_ms'],
      ['三维坐标变换', 'coordinate_transform_ms'],
      ['目标定位总计算', 'target_latency_ms'],
      ['独立目标进程 HTTP', 'target_http_ms'],
      ['只读规划预检', 'planning_http_ms'],
      ['目标进程＋规划预检', 'target_plus_planning_ms']
    ] : [
      ['本地千问解析', 'natural_language_ms'],
      ['等待新 GPU 检测帧', 'vision_wait_ms'],
      ['GPU YOLO predict() · 嵌套于等待段', 'gpu_inference_ms'],
      ['GPU 进程处理 · 嵌套于等待段', 'gpu_processing_ms'],
      ['深度帧获取与同步', 'depth_fetch_ms'],
      ['深度反投影＋预抓点', 'geometry_ms'],
      ['只读轨迹预检', 'planning_preview_ms'],
      ['原话请求→本轮返回（含失败）', 'total_ms'],
      ['原话请求→预检成功（仅成功样本）', 'total_success_ms']
    ];
    $('vla-stages').replaceChildren(...stages.map(([label, key]) => {
      const d = task.summary?.[key] || {};
      return row([label, d.n ?? d.count ?? 0, ...['mean', 'p50', 'p95', 'p99', 'max'].map(field => number(d[field]))]);
    }));
    $('vla-export').href = `${API}/export?project=vla&task_id=${encodeURIComponent(task.id)}`;
    $('vla-report').href = `${API}/report?id=${encodeURIComponent(task.id)}`;
    const key = `${task.id}:${task.trials_done}`;
    if (key !== recordsKey) {
      recordsKey = key;
      loadRecords(task.id);
    }
  }
  async function loadRecords(id) {
    try {
      const data = await api(`/vla/records?id=${encodeURIComponent(id)}`);
      if (selected !== id) return;
      records = data.items || [];
      const host = $('vla-samples');
      if (!records.length) { host.textContent = '等待原始记录入库'; return; }
      const wrap = el('div', '', 'cm-table-wrap'), table = el('table', ''), head = el('thead', ''), body = el('tbody', '');
      head.append(row(['序号', '结果', 'GPU', '总耗时 / ms', '规划 / ms', '失败原因']));
      for (const record of records.slice(-100).reverse()) {
        const sample = record.payload?.sample || {};
        const legacy = record.kind === 'vla_legacy_trial';
        const tr = row([sample.trial || '—', legacy ? (sample.success === '1' ? '通过' : '失败') : (sample.success ? '通过' : '失败'),
          legacy ? 'CPU' : sample.gpu_verified ? 'ROCm' : '未到达GPU',
          legacy ? legacyNumber(sample.target_plus_planning_ms) : number(sample.timings_ms?.total_ms),
          legacy ? legacyNumber(sample.planning_http_ms) : number(sample.timings_ms?.planning_preview_ms),
          (sample.error || '').slice(0, 120)]);
        tr.classList.add('cm-click');
        tr.tabIndex = 0;
        const show = () => { $('raw-detail').textContent = JSON.stringify(record, null, 2); $('raw-dialog').showModal(); };
        tr.onclick = show;
        tr.onkeydown = event => { if (event.key === 'Enter') show(); };
        body.append(tr);
      }
      table.append(head, body); wrap.append(table); host.replaceChildren(wrap);
    } catch (error) { notice('读取逐次记录失败：' + error.message, true); }
  }
  async function refresh() {
    if (loading || document.hidden) return;
    loading = true;
    try { state = await api('/vla/status'); render(); }
    catch (error) { notice('VLA 测量服务暂不可用：' + error.message, true); }
    finally { loading = false; }
  }
  $('vla-form').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    try {
      const result = await api('/vla/start', {
        instruction: form.elements.instruction.value,
        trials: Number(form.elements.trials.value)
      });
      selected = result.task_id;
      recordsKey = '';
      notice('只读测量已开始；不会发送机械臂或底盘动作。');
      await refresh();
    } catch (error) { notice(error.message, true); }
  };
  $('vla-stop').onclick = async () => {
    try { await api('/vla/stop', {}); notice('正在结束本轮只读测量…'); await refresh(); }
    catch (error) { notice(error.message, true); }
  };
  $('vla-delete').onclick = () => {
    const task = selectedTask();
    if (!task || task.status === 'running' || state.running?.id === task.id) return;
    $('vla-delete-task-name').textContent = `${task.name} · ${new Date(task.created * 1000).toLocaleString('zh-CN')} · ${task.id}`;
    $('vla-delete-confirm').value = '';
    $('vla-delete-error').textContent = '';
    $('vla-delete-dialog').showModal();
    $('vla-delete-confirm').focus();
  };
  $('vla-delete-cancel').onclick = () => $('vla-delete-dialog').close();
  $('vla-delete-form').onsubmit = async event => {
    event.preventDefault();
    const task = selectedTask();
    if (!task) return;
    if ($('vla-delete-confirm').value.trim() !== '删除') {
      $('vla-delete-error').textContent = '请输入“删除”确认';
      return;
    }
    const button = $('vla-delete-submit');
    button.disabled = true;
    try {
      const result = await api('/round/delete', {id: task.id, confirm: task.id});
      $('vla-delete-dialog').close();
      selected = '';
      recordsKey = '';
      records = [];
      notice(`已删除本轮结果与 ${result.deleted_records} 条专属原始记录；其他轮次和共享监测保留。`);
      await refresh();
    } catch (error) {
      $('vla-delete-error').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  $('vla-refresh').onclick = refresh;
  $('vla-select').onchange = () => { selected = $('vla-select').value; recordsKey = ''; render(); };
  for (const tab of document.querySelectorAll('[data-tab]')) {
    if (tab.dataset.tab === 'vla') tab.addEventListener('click', refresh);
  }
  setInterval(() => { if (document.querySelector('[data-tab="vla"]')?.classList.contains('selected')) refresh(); }, 3000);
})();
