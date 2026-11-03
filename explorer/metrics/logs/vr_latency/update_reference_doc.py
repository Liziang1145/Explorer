from pathlib import Path
from copy import deepcopy
import json, math, statistics, hashlib
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.shared import Twips

BASE = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/25298/Desktop/探路者_竞赛技术文档V1.5.docx')
OUT = Path('C:/Users/25298/Desktop/FPGA/01_文档/探路者_竞赛技术文档V1.5_数据更新参考稿.docx')
vr = json.loads((BASE/'vr-cleaning-20261103-193754.json').read_text(encoding='utf-8'))
vla = json.loads((BASE/'vla-215-reference.json').read_text(encoding='utf-8'))
doc = Document(SOURCE)
changes = []

def setp(p, text):
    before = p.text
    props = next((deepcopy(r._r.rPr) for r in p.runs if r._r.rPr is not None), None)
    p.clear()
    run = p.add_run(text)
    if props is not None:
        if run._r.rPr is not None: run._r.remove(run._r.rPr)
        run._r.insert(0, props)
    changes.append({'before': before, 'after': text})
    return p

def findp(prefix):
    found = [p for p in doc.paragraphs if p.text.startswith(prefix)]
    assert len(found) == 1, (prefix, len(found))
    return found[0]

def replacep(prefix, text):
    return setp(findp(prefix), text)

def cell(table, row, col, text):
    c = doc.tables[table].cell(row, col)
    p = c.paragraphs[0]
    for extra in c.paragraphs[1:]: c._tc.remove(extra._p)
    return setp(p, text)

def comment(p, text):
    if not p.runs: p.add_run(' ')
    doc.add_comment(p.runs, text, author='数据核对', initials='核')

def after(p, text):
    e = OxmlElement('w:p')
    if p._p.pPr is not None: e.append(deepcopy(p._p.pPr))
    p._p.addnext(e)
    return setp(Paragraph(e, p._parent), text)

def stats(values):
    v = sorted(values); n = len(v)
    return [str(n), f'{statistics.fmean(v):.2f}', *[f'{v[math.ceil(n*q)-1]:.2f}' for q in [.5,.95,.99]], f'{v[-1]:.2f}']

full = [r for r in vr['response_records'] if r['full_ms'] is not None and vr['full']['bounds_ms'][0] <= r['full_ms'] <= vr['full']['bounds_ms'][1]]
partial = [r for r in vr['response_records'] if r['post_aipc_ms'] is not None and vr['partial']['bounds_ms'][0] <= r['post_aipc_ms'] <= vr['partial']['bounds_ms'][1]]
assert len(full) == 54 and len(partial) == 62
assert len(vla['rows']) == 215 and len(vla['batch_counts']) == 11

# Abstract: preserve the architecture text and replace only measured claims.
p = findp('“探路者”面向')
old = '在 12 组有效动作样本中，VR 控制采样至编码器反馈代理延迟 P50 为 146.40 ms；20 组自然语言至 GPU 定位及只读预检全部完成，总耗时 P50 为 3874.06 ms；'
new = 'VR 控制采样至编码器反馈代理测量汇总 4 批次、56 组完整响应；按 3×IQR 规则剔除 2 个统计离群值后，54 组样本的 P50 为 148.08 ms、P95 为 175.46 ms、P99 为 191.81 ms，原始记录保留。11 批次共 215 次自然语言至 GPU 定位及只读预检全部完成，总耗时 P50 为 4001.88 ms；'
assert old in p.text
setp(p, p.text.replace(old,new))
comment(p, '数据更新参考稿：VR采用2026-11-02至11-03四批次记录；清洗结果属于统计离群值敏感性分析，不代表两个慢响应已被证实为测量错误。VLA为11批次215次只读预检，不是完整抓取成功率。')

# Summary indicators and unsupported claims.
cell(0,1,1,'输入至编码器运动反馈代理时延：P50、P95、P99、样本量')
cell(0,1,3,'N=54（4批次，剔除2个统计离群值）；P50 148.08 ms，P95 175.46 ms，P99 191.81 ms。')
cell(0,2,1,'典型操作任务功能验证')
comment(doc.tables[0].cell(2,1).paragraphs[0], '夹石头、叠杯子和叠毛巾的演示能支持功能验证；若要称为任务成功率，需要补充各任务的成功次数、总次数及失败判据。')
cell(0,3,3,'工作区内完成率93%（待核实）')
comment(doc.tables[0].cell(3,3).paragraphs[0], '保留原稿93%供作者核实；本次未取得它对应的完整抓取实机记录。请补成功次数/总次数、工作区和目标条件、成功判据及任务ID；不能用215次只读预检推导。')
cell(0,4,1,'自然语言请求至只读预检返回耗时、预检完成率')
cell(0,4,3,'N=215（11批次）；P50 4001.88 ms，P95 4435.58 ms，P99 4621.64 ms；只读预检完成率100%（215/215）。')
comment(doc.tables[0].cell(7,3).paragraphs[0], '3秒内收到的反馈帧数支持恢复后接口有数据，不等同于故障恢复耗时。若本行作为恢复时间指标，仍需补故障发生至恢复有效反馈的计时记录。')
comment(doc.tables[0].cell(8,3).paragraphs[0], '原稿资源比例予以保留；请绑定资源报告、工程和位流哈希，尤其核对是否对应2.2.4新增PL机械臂命令引擎版本，不能直接跨位流沿用2026-10-28实现报告。')

# VR methodology, complete and partial samples, and source linkage.
replacep('测试条件：任务为“VR双臂响应测试-实际”', '测试条件：汇总 2026-11-02 至 2026-11-03 的 4 批次 VR 双臂响应记录，软件测量版本为 software-v2-trace-fix。记录按任务 ID 区分，批次时长以实际起止时间为准；响应关联采用动作前静止至少 0.5 s 的条件。')
p=replacep('样本与统计：完整链路样本 N=12', '样本与统计：4 批次共 56 组完整 VR 起点响应及 64 组 AIPC 起点响应。对两种测量边界分别采用合并样本的一次性 3×IQR 筛查，排除同两个响应后分别保留 N=54 和 N=62；后者包含前者，另有 8 组缺少有效 VR 起点。四分位数采用线性插值，P50／P95／P99 采用最近秩法。')
comment(p, '原始→保留的完整样本数：11月2日23:57，12→12；11月3日18:27，23→22；19:04，3→3；19:19，18→17。完整链路筛查范围为9.19～274.82 ms；被排除值420.53和291.85 ms。仅为统计离群筛查，原始记录未删除。')
replacep('证据：VR到编码器反馈_报告.md', '证据：07_实验记录/VR时延清洗_20261103/vr-cleaning-20261103-193754.json；含 4 个任务 ID、逐次响应、原始／清洗汇总、筛查阈值及排除清单。原单批次报告继续保留为历史记录。')
replacep('表3.3 VR 控制采样至编码器运动反馈代理延迟', '表3.3 四批次 VR 编码器运动反馈代理延迟（统计离群值剔除后）')
for ri,rows,key in [(1,full,'full_ms'),(2,partial,'post_aipc_ms')]:
    for ci,text in enumerate(stats([r[key] for r in rows]),1): cell(8,ri,ci,text)
p=replacep('完整链路 P50 为 146.40 ms', '清洗后完整链路 N=54，均值 140.63 ms，P50 为 148.08 ms、P95 为 175.46 ms、P99 与最大值均为 191.81 ms。AIPC 起点部分链路 N=62，P50 为 140.34 ms、P95 为 168.14 ms、P99 为 185.67 ms。反馈阈值、连续确认帧数及反馈周期共同定义代理终点；当前样本量下，完整链路 P99 等于保留样本最大值。')
p2=after(p, '原始完整链路 N=56，P50／P95／P99 分别为 148.11／191.81／420.53 ms。统计筛查排除 420.53 ms 与 291.85 ms 两个响应；它们尚未被证实为测量错误，清洗结果仅作为离群值敏感性分析，不能替代原始尾延迟。原始记录、异常候选及筛查规则均保留。')
comment(p2, '建议正式提交同时保留原始与清洗结果。不要将“统计离群”改写成“无效数据”或把清洗后P99作为未经筛选的最坏响应保证。')
replacep('表3.4 同一轮关联响应的分段统计', '表3.4 清洗后54组完整链路响应的分段统计（单位 ms）')
keys=['vr_to_aipc','aipc_queue','ik','send_wait','network','board_to_can','can_to_feedback']
for ri,key in enumerate(keys,1):
    for ci,text in enumerate(stats([r['segments_ms'][key] for r in full]),1): cell(9,ri,ci,text)
replacep('分段按可关联事件分别统计', '表3.4 的七个阶段统一采用表3.3中保留的 54 组完整链路样本，未混入仅具备 AIPC 起点的 8 组部分响应，也不同于独立输入流的逐帧传输统计。各阶段分位数不能相加得到总时延分位数。CAN 发送采用时序关联，板端至 CAN 对应 PS 执行桥接；本指标为编码器运动反馈代理，不代表外部物理运动起点或 PL 硬件执行时延。')

# VLA: recompute every stage from the same 215 records.
replacep('测试条件：2026-11-03，本地千问', '测试条件：2026-11-03，汇总 11 批次自然语言只读预检。逐次记录的语言模型为 qwen3.8-flash-next-iq3_s，视觉模型为 AMD ROCm GPU YOLO26m-seg；接口调用限于语言解析、RGB-D 目标定位与轨迹预检，测量不包含机械臂运动执行。')
replacep('样本与统计：N=20，20 次完成只读预检', '样本与统计：N=215（11批次），215/215 次请求完成只读预检，完成率100%；按任务 ID＋试验序号核对无重复。全部阶段以215条逐次记录重新统计，采用最近秩法，保留均值与P50／P95／P99／最大值。')
replacep('证据：GPU只读VLA_报告.md', '证据：07_实验记录/VR时延清洗_20261103/vla-215-reference.json；含11批次任务ID、215条原始样本及分阶段汇总。原GPU只读VLA_报告.md及20次记录作为历史单批次证据保留。')
replacep('表3.5 自然语言至 GPU 定位与只读轨迹预检延迟', '表3.5 自然语言至 GPU 定位与只读轨迹预检延迟（11批次、215次）')
vkeys=['natural_language_ms','vision_wait_ms','gpu_inference_ms','gpu_processing_ms','depth_fetch_ms','geometry_ms','planning_preview_ms','total_ms']
for ri,key in enumerate(vkeys,1):
    values=[r['timings_ms'][key] for r in vla['rows']]
    for ci,text in enumerate(stats(values),1): cell(10,ri,ci,text)
p=replacep('总耗时 P50 为 3874.06 ms', '11批次215次请求的总耗时均值为4006.97 ms，P50为4001.88 ms，P95为4435.58 ms，P99为4621.64 ms，最大值为4722.66 ms；GPU predict() P50为20.01 ms，独立轨迹预检阶段P50为3225.71 ms。GPU推理嵌套在等待新检测帧区间内，总耗时按逐次请求直接统计，不由各阶段分位数相加。215/215次均完成只读预检；该完成率不代表完整抓取成功率，运动执行仍需单独验收。')
comment(p,'本次将原20次单批次表完整替换为215次汇总，未仅修改N。不要将4001.88 ms标为“纯规划算法耗时”；它包含自然语言解析、等待检测、定位和预检。')

# Reconcile resource-data status without asserting a newly verified bitstream.
p=findp('实现结果为 WNS +0.100 ns')
setp(p,p.text.replace('资源占用、板级测频和控制周期抖动按最终位流补充板级测量。','表1.1所列资源比例仍需绑定对应的资源报告和位流哈希；板级测频与控制周期抖动另行实测。'))
p=findp('同一 final_timing.rpt 的 TNS')
setp(p,p.text.replace('板级测频、资源占用、片外收发和恢复耗时见3.2.2 的分项状态。','资源比例按表1.1列示并待绑定同批报告；板级测频、片外收发和恢复耗时须按实际部署位流分别核验。'))

# Appendix B and D: evidence lineage and remaining work.
cell(17,2,1,'CPU基线yolo26m-seg.pt；215次GPU预检的语言模型qwen3.8-flash-next-iq3_s、视觉模型YOLO26m-seg；SmolVLA分支单独归档')
cell(17,2,2,'待绑定215次实验的权重哈希、输入规格、精度与后端版本；SmolVLA检查点哈希单独记录')
cell(17,3,2,'待绑定位流哈希及资源报告，核对新PL驱动与2026-10-28实现报告是否同版；补板级时钟、Linux内核和CAN配置')
cell(18,1,1,'07_实验记录/VR时延清洗_20261103/vr-cleaning-20261103-193754.json')
cell(18,1,2,'核对4个任务ID及逐次响应；原始完整56组、部分64组；统一3×IQR筛查后54／62组，最近秩法重算')
cell(18,2,1,'07_实验记录/VR时延清洗_20261103/vla-215-reference.json')
cell(18,2,2,'核对11个任务ID＋试验序号；215条无重复只读预检记录；按逐次请求重算总耗时及各阶段分位数')
cell(20,7,1,'2026-11-02至11-03；4批次；software-v2-trace-fix')
cell(20,7,2,'VR时延清洗_20261103/vr-cleaning-20261103-193754.json；含4个任务ID；旧单批次报告保留')
cell(20,7,3,'表3.3～3.4：原始完整56／部分64组；筛查后54／62组；分段表统一取54组完整响应')
cell(20,7,4,'原始响应＋清洗规则与排除清单；统计离群不等于已证实测量错误')
cell(20,14,1,'2026-11-03；11批次，215条')
cell(20,14,2,'VR时延清洗_20261103/vla-215-reference.json；含11个任务ID与逐次sample')
cell(20,14,3,'表3.5：215/215只读预检；语言模型qwen3.8-flash-next-iq3_s；全阶段及总耗时按215条重算')
cell(20,14,4,'215条逐次记录核验无重复；不包含运动执行；原20次单批次证据继续保留')
p=findp('证据包包含正式交付元数据')
setp(p, '证据包包含正式交付元数据、VR四批次原始响应与离群筛查明细、VLA 11批次215条逐次预检样本、TCP任务及逐秒窗口、历史通信与接口区间记录、19条导航历史和对应地图状态。新增数据文件位于07_实验记录/VR时延清洗_20261103；VR、VLA及其他链路按各自任务ID、测量边界、版本和证据编号索引，历史快照不视为当前在线状态。')
cell(21,2,2,'将表1.1资源比例绑定同批位流的LUT／FF／BRAM／DSP报告，补板级时钟、I/O与CDC说明，验证实际PL通路和端口局部恢复。')
cell(21,9,2,'在VR四批次原始56组、筛查后54组完整响应基础上继续扩样，覆盖不同关节与媒体并发；导航覆盖直线、转弯、窄通道和停止恢复。')

# Make changed numeric tables readable and repeat their headers across pages.
for ti,widths in [(9,[1640,650,1182,1182,1182,1182,1182]),(10,[2230,720,1050,1050,1050,1050,1052])]:
    table=doc.tables[ti]
    table.autofit=False
    for column,width in zip(table.columns,widths): column.width=Twips(width)
    for row in table.rows:
        for c,width in zip(row.cells,widths): c.width=Twips(width)
for ti in [0,8,9,10,17,18,20,21]:
    table=doc.tables[ti]
    header=table.rows[0]._tr.get_or_add_trPr()
    if header.find(qn('w:tblHeader')) is None: header.append(OxmlElement('w:tblHeader'))
    for row in table.rows:
        pr=row._tr.get_or_add_trPr()
        for h in list(pr.findall(qn('w:trHeight'))):
            if h.get(qn('w:hRule'))=='exact': h.set(qn('w:hRule'),'atLeast')

doc.core_properties.comments='数据更新参考稿；统计截止2026-11-03 19:37:54 +08:00。仅更新已核验VR/VLA统计与相关索引，保留原稿其他实测声明并用批注提示待核实项。'
OUT.parent.mkdir(parents=True,exist_ok=True)
doc.save(OUT)
(BASE/'V1.5_数据更新修改清单.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
reopened=Document(OUT)
assert len(reopened.tables)==22
assert len(reopened.inline_shapes)==len(Document(SOURCE).inline_shapes)
assert reopened.tables[8].cell(1,1).text=='54'
assert reopened.tables[10].cell(8,1).text=='215'
assert reopened.tables[10].cell(8,5).text=='4621.64'
print('OUTPUT',OUT)
print('EDITS',len(changes),'COMMENTS',len(reopened.comments),'IMAGES',len(reopened.inline_shapes))
print('SOURCE_SHA256',hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print('VR_SEGMENTS')
for row in reopened.tables[9].rows: print(' | '.join(c.text for c in row.cells))
