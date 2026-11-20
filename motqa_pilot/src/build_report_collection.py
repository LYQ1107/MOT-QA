"""Collect unchanged research reports and render a self-contained reading copy."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
import re
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from markdown_it import MarkdownIt


ROOT = Path('/home/user/motqa_pilot')
TOC = Path('/data2/user/toc_phase0')
OUT = ROOT / 'results/report_collection_20261104'
ZIP = ROOT / 'results/all_reports_20261104.zip'

# The stage-five first implementation is retained for provenance, not scoring.
SPECS = [
    ('toc1', TOC, 'stage1_report.md', 'TOC 阶段一：环境与数据准备', 'current',
     '独立安装 vLLM 与 MASA，统一模型可用，保留下载来源与依赖版本。'),
    ('toc2', TOC, 'stage2_report.md', 'TOC 阶段二：官方协议复现', 'current',
     '623/2323＝26.82%，通过复现；解析失败291题全部计错。'),
    ('toc3', TOC, 'stage3_report.md', 'TOC 阶段三：轨迹与规则基线', 'current',
     '749题、689视频；预登记可表达324题；初始R/D规则71/134。'),
    ('toc3v1', TOC, 'stage3_improvement_report.md', 'TOC 阶段三改进：冻结 v1', 'current',
     '按视频锁定开发/测试；memo50、top5、gap0.5秒；测试未因本轮改进涨分。'),
    ('toc4', TOC, 'stage4_main_report.md', 'TOC 阶段四：官方格式主实验', 'current',
     '测试可表达251题，A89、B88、D88；真实轨迹未检出收益。'),
    ('toc5', TOC, 'stage5_report.md', 'TOC 阶段五：推理模板与表示梯度（最终修正版）', 'current',
     '推理模板B80对A58，但B对D不显著，表示梯度不单调。'),
    ('toc5old', TOC, 'stage5_report_initial_implementation.md', 'TOC 阶段五：约束实现初稿（已替代）', 'superseded',
     '保留历史失败与修复过程；不能与最终版约束解码结果混合。'),
    ('toc6', TOC, 'stage6_report.md', 'TOC 阶段六：工具调用与合成 LoRA', 'current',
     '原T1调用被格式拒绝；LoRA使R/D29→40/101，未达到45/101。'),
    ('toc7info', TOC, 'stage7_track_information_report.md', 'TOC 阶段七：轨迹信息量事后诊断', 'current',
     '同覆盖子集R/D规则与多数盲基线均51/75；尚无超出先验的可靠证据。'),
    ('toc7', TOC, 'stage7_report.md', 'TOC 阶段七：接口修复与决定性对照', 'current',
     '修复T1为98/251，占位同为98，打乱94；未检出真实轨迹特异收益。'),
    ('mot1', ROOT, 'stage1_report.md', 'MOT-QA 阶段一：数据与语言资源盘点', 'current',
     '169个唯一视频，其中162个有GT；登记身份语义与临时来源限制。'),
    ('mot2', ROOT, 'stage2_report.md', 'MOT-QA 阶段二：GT 事实与指代资源', 'current',
     '2518个GT ID；外观484时段、事件352条、位置2344时段；尚未生成QA。'),
    ('mot2appearance', ROOT, 'stage2_appearance_report.md', 'MOT-QA 阶段二补充：DanceTrack 外观描述', 'current',
     '273个ID全部处理；25自动候选中17条审阅未见明显问题、8条标疑。'),
]

APPENDICES = [
    ('examples4', 'stage4_AB_examples.md', '阶段四：A/B 成败对照样例'),
    ('examples5', 'stage5_reasoning_RD_examples.md', '阶段五：R/D 推理样例'),
    ('examples6', 'stage6_RD_interactions.md', '阶段六：R/D 完整交互'),
    ('examples7', 'stage7_RD_interactions.md', '阶段七：R/D 完整交互与事实核查'),
]

MD = MarkdownIt('commonmark', {'html': False}).enable('table')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_table(path: Path, header_prefix: str) -> str:
    """Copy a table verbatim so dimension scores keep their original denominators."""
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header_prefix))
    end = start + 1
    while end < len(lines) and lines[end].startswith('|'):
        end += 1
    return '\n'.join(lines[start:end])


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    records = []
    source_bytes = {}
    for ident, root, filename, title, status, note in SPECS:
        source = root / 'results' / filename
        data = source.read_bytes()
        group = 'toc_bench' if root == TOC else 'motqa_pilot'
        archive = f'original_reports/{group}/{filename}'
        record = dict(id=ident, title=title, project=group, kind='report',
                      status=status, note=note, source=str(source),
                      archive_path=archive, bytes=len(data), sha256=sha(data),
                      source_mtime=datetime.fromtimestamp(
                          source.stat().st_mtime, ZoneInfo('Asia/Shanghai')).isoformat())
        records.append(record)
        source_bytes[str(source)] = data
    for ident, filename, title in APPENDICES:
        source = TOC / 'results' / filename
        data = source.read_bytes()
        records.append(dict(id=ident, title=title, project='toc_bench', kind='appendix',
                            status='reference', note='原报告所引的完整样例附录。',
                            source=str(source), archive_path=f'appendices/{filename}',
                            bytes=len(data), sha256=sha(data),
                            source_mtime=datetime.fromtimestamp(
                                source.stat().st_mtime, ZoneInfo('Asia/Shanghai')).isoformat()))
        source_bytes[str(source)] = data
    link_targets = {r['source']: '#' + r['id'] for r in records}
    assets = {}

    def render(text: str, source: Path | None = None) -> str:
        tokens = MD.parse(text)
        for block in tokens:
            for token in block.children or []:
                key = 'src' if token.type == 'image' else 'href' if token.type == 'link_open' else None
                if not key:
                    continue
                target = token.attrGet(key)
                if not target or target.startswith(('#', 'https:', 'http:', 'data:', 'mailto:')):
                    continue
                raw, _, anchor = target.partition('#')
                path = Path(raw)
                if not path.is_absolute():
                    path = (source.parent if source else ROOT) / path
                path = path.resolve()
                if key == 'src' and path.is_file():
                    content = path.read_bytes()
                    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                    token.attrSet('src', 'data:' + mime + ';base64,' + base64.b64encode(content).decode())
                    assets[str(path)] = content
                elif str(path) in link_targets:
                    token.attrSet(key, link_targets[str(path)])
                else:
                    token.attrSet(key, str(path) + ('#' + anchor if anchor else ''))
        return MD.renderer.render(tokens, MD.options, {})

    overview = '''
## 最新结论

**TOC-Bench：官方基线已复现，但截至阶段七，尚未检出模型利用真实 v1 轨迹内容的可靠收益。**
阶段二为623/2323（26.82%），接近论文27.0%。阶段四真实轨迹B与无证据A基本持平；
阶段五的模板内涨分未通过真实/打乱对照；阶段七修复调用后，T1与占位工具输出同为98/251。
“规则或路由高于模型”这一早期观察，需要结合类别先验重新解释。

**轨迹信息量诊断收紧了早期判断。** R/D规则在其覆盖的75道测试题上为51/75，开发集多数类盲基线也为51/75；
消失前是否贴边与真实类别的Fisher检验p=.2589。Count规则低于多数盲基线；X-Order只有9道覆盖题，证据不足。
目前没有可靠证据表明冻结规则从v1轨迹读出的事件信息超出类别先验；这不证明原始轨迹里不存在其他可用信息。

**MOT-QA Pilot：完成数据盘点、GT事实/指代资源以及外观补充，尚未生成QA。**
162个有GT视频已统一；DanceTrack val的273个ID完成外观描述流程，25条自动通过候选经智能体逐条视觉审阅后，
17条未见明显疑点、8条需用户复核。17条相对旧资源新增10个ID；旧资源与这些候选的混合并集为31/273个ID、9/25视频。
不同来源的验证强度不同，不能称为31个独立人工认证身份，更不能直接作为题数。

## 阅读与版本说明

- 本汇总收录两个项目的**13份阶段报告（12份当前报告、1份被替代历史稿）**，另附4份完整样例/交互附录。
- 阶段五以`stage5_report.md`最终技术修正版为准；`stage5_report_initial_implementation.md`只保留历史实现记录。
- 原报告按完成当时的状态原文保留，可能写有“下一阶段尚未运行”；当前进度以本页最新结论和较晚阶段报告为准。
- 汇总只读取现有结果，没有运行新推理、训练、跟踪或改动任何冻结配置、切分、标签及原报告。
- 表中严格主结果与计数约束诊断分开；未检出差异不等于证明等效。完整逐题原始输出见原报告引用的本地文件。

## TOC-Bench：范围与冻结协议

阶段二复现范围为1951个视频、2323题。后续重点实验为749题、689个视频，按视频以seed42划分：
开发138视频/147题，测试551视频/602题。预登记可表达清单共324题，开发73、测试251；
测试可表达251题包含Count81、R/D101、X-Order30、Order19、次要ReID20。主要四维共231题。
这些范围不能混用分母，阶段二26.82%也不能直接与后续251题的分数比较。

冻结v1采用MASA-GroundingDINO统一模型、5fps、score0.2、memo50；删除持续<0.6秒且均分<0.3的轨迹，
按置信度×观测时长保留top5。规则间断阈值0.5秒，边缘阈值0.05。跟踪配置只按开发集选择，之后保持不变。
阶段四起官方32帧采样、相同时间戳与65536上下文统一；主结果用测试集，全集含参与调参的开发集，仅作附带。
任何真值metadata均未作为跟踪输入或模型证据。

## TOC-Bench：阶段脉络

| 阶段 | 主要产出与结果 | 当前解释 |
|---|---|---|
| [一：环境](#toc1) | vLLM与MASA分开环境安装；统一MASA权重可用 | 环境和下载准备完成 |
| [二：复现](#toc2) | 623/2323＝26.82%；无解码失败；291条解析失败计错 | 通过27.0%±3pp验收；2个30帧视频按官方分支处理 |
| [三：初始轨迹](#toc3) | 749题、899视频—短语对；主体标签对照746/749；规则R/D71/134＝52.99% | 标签匹配不是双目标完整抽取准确率；早期规则优势尚未排除先验 |
| [三：限时改进](#toc3v1) | 开发主要可表达29→30/70；测试80→76/231 | 保持开发集选定方案，测试没有涨分；主要产出为冻结与压缩 |
| [四：官方格式](#toc4) | A89、B88、C90、D88 /251；路由112/251 | B−A为−0.40pp，p=1；未检出真实轨迹收益 |
| [五：推理/表示](#toc5) | 推理A58、B80、D72 /251；B-events83/251 | H6成立，但B−D不显著；表示精简没有单调改善 |
| [六：工具/LoRA](#toc6) | T0不调用；原T1的1801次调用均被格式拒绝；LoRA R/D29→40/101 | 原工具结果不能回答成功取到事实后能否利用；H11未达45/101 |
| [七：信息诊断](#toc7info) | R/D覆盖子集规则51/75＝多数盲基线；Count规则18/81<32/81 | 规则/路由优势不足以证明超出类别先验的信息 |
| [七：接口修复](#toc7) | T1 98、占位98、打乱94、T-none73 /251 | 修复改善相对同模板基线，但未检出真实工具事实的特异收益 |

## TOC-Bench：同一测试可表达251题的关键分数

所有分数均为严格解析；规则弃答计错。不同模板的消息、预算等不同，下面用于并列定位，不能把跨模板差值直接解释为单一机制的因果效应。

| 模板/条件 | 总体（251题） | R/D（101题） | 说明 |
|---|---:|---:|---|
| 官方 A | 89/251＝35.46% | 39/101＝38.61% | 无证据，带统一时间戳 |
| 官方 B | 88/251＝35.06% | 37/101＝36.63% | 真实多轨迹 |
| 官方 C | 90/251＝35.86% | 38/101＝37.62% | 占位提示 |
| 官方 D | 88/251＝35.06% | 36/101＝35.64% | 锁定打乱轨迹 |
| 官方 B-main | 85/251＝33.86% | 34/101＝33.66% | 主体轨迹 |
| 官方 B-events | 87/251＝34.66% | 36/101＝35.64% | 主体事件事实 |
| 简短推理 A | 58/251＝23.11% | 31/101＝30.69% | 同模板无证据 |
| 简短推理 B | 80/251＝31.87% | 30/101＝29.70% | 模板内涨分主要来自Count |
| 简短推理 D | 72/251＝28.69% | 25/101＝24.75% | B对D优势未显著 |
| 简短推理 B-main | 56/251＝22.31% | 15/101＝14.85% | 表示梯度不单调 |
| 简短推理 B-events | 83/251＝33.07% | 29/101＝28.71% | 微调前 |
| LoRA后 B-events | 83/251＝33.07% | 40/101＝39.60% | 总正确数未变，R/D提升不显著 |
| 工具 T-none | 73/251＝29.08% | 22/101＝21.78% | 同系统与答题模板，无工具 |
| 工具 T0 | 66/251＝26.29% | 18/101＝17.82% | 零样本，未调用工具 |
| 工具 T1（修复后） | 98/251＝39.04% | 46/101＝45.54% | 使用原5个开发集示范 |
| 工具 T-ph | 98/251＝39.04% | 50/101＝49.50% | 返回占位符 |
| 工具 T-sh | 94/251＝37.45% | 46/101＝45.54% | 返回打乱事实 |
| 冻结规则 | 79/251＝31.47% | 51/101＝50.50% | 未覆盖题计错 |
| 路由（官方A回退） | 112/251＝44.62% | 63/101＝62.38% | 规则覆盖用规则，否则用A |
| 开发集多数类盲基线 | 126/251＝50.20% | 68/101＝67.33% | 使用开发集类别先验，未按测试标签选类 |

## TOC-Bench：关键检验与诊断

各项沿用各阶段预登记的exact双侧McNemar、题级配对bootstrap1000次、seed42。这里汇集既有检验，不新增显著性筛选；事后诊断与预登记主检验分开。

| 检验 | 差值 | p值 | 95%CI（pp） | 解释 |
|---|---:|---:|---|---|
| 阶段四 官方B−A，251题 | −0.40pp | 1 | [−5.98,+4.79] | 主实验无可检出收益 |
| H6 推理B−A，251题 | +8.76pp | .00535486 | [+3.18,+14.74] | 预登记成立；22个净增中21来自Count |
| 阶段五 推理B−D，251题 | +3.19pp | .2559 | [−1.20,+8.37] | 真实轨迹特异性证据不足 |
| H11 LoRA−微调前，R/D101题 | +10.89pp | .135156 | [−1.98,+22.77] | 40/101，未达45/101；总体仍83/251 |
| H12 修复T1−T-none，251题 | +9.96pp | .0114563 | [+2.79,+16.74] | 预登记成立 |
| 修复T1−T-ph，251题 | 0.00pp | 1 | [−6.37,+7.18] | 纠正41题、损失41题，净收益0 |
| 修复T1−T-sh，251题 | +1.59pp | .707981 | [−4.39,+7.57] | 无可检出真实事实优势 |
| 修复T1−多数盲基线，251题 | −11.16pp | .00841699 | [−18.73,−3.98] | 低于开发集先验基线 |
| 修复T1−T-none，测试全部602题 | +0.50pp | .893497 | [−4.32,+5.32] | 子集上的提升未扩展到全部测试题 |

H7表示梯度在R/D上不单调：推理B30→B-main15→B-events29 /101。H8的B-events未达到规则51/101：官方36、推理29。
H9/H10原工具实验未支持，但当时接口没有成功送达事实。修复后602题的合法执行为567/567，
76.91%题发起调用；全部是events，track与look均为0，因此没有实际测到裁剪图工具收益。

计数需区分格式与推断：官方数值提示把2、3、4写为示例，未明确禁止0/1，解析器却拒绝0/1。
阶段四测试可表达Count的guided A为30/81、B为33/81、D同为33/81；恒答“2”为32/81。
因此严格涨分或高于25%均不足以单独证明利用了事件事实。完整合法率、修正版guided结果见阶段四至七原文。

ReID的23题发布标签为13个“同一”、10个“不同”，模型22题预测“同一”。按发布标签12/23＝52.17%；
若反事实假定全部“同一”，则22/23＝95.65%，可在数值上解释论文95.7%，但不能证明论文确实采用该标注。
23题及全部100条repair_log均未见ReID修复记录。原标签保持原样，ReID仍为次要维度。

## MOT-QA Pilot：已完成内容与资源规模

| 阶段 | 范围与结果 | 限制/状态 |
|---|---|---|
| [一：数据盘点](#mot1) | 169唯一视频、134083帧；162有GT，7个MOT17 test无公开GT | MOT17检测器目录已去重；原始数据只读 |
| 一：身份语义 | Dance完全遮挡后同ID；Sports片内唯一ID；MOT17出画再入可能新ID | 不能把GT轨迹ID直接当作跨出画的真人身份 |
| 一：临时来源 | Dance val25、Sports val45、MOT17 train7段后半，共77原视频 | 公开跟踪器及检测/ReID模块的训练/调参重叠仍待核对 |
| [二：统一GT](#mot2) | 162视频、2518个GT ID、1294527行有效GT、1268058行可见 | MOT17 visibility≥0.25仍登记为待阶段二审阅的临时约定 |
| 二：指代资源 | 外观484连续时段；事件352条；位置2344连续时段 | 留未来≥3秒分别443/312/2060；不是独立QA数 |
| 二：原外观覆盖 | Dance val21/273个ID、7/25视频 | 仅标注层面的唯一性，不等于视觉准确 |
| [二补充：强视觉模型](#mot2appearance) | Qwen3-VL-32B对273个ID处理，272合法描述、32全视频图库唯一、25自动候选 | 同模型独立帧匹配是自一致性检查，仍会重复确认属性错误 |
| 二补充：全部25候选审阅 | 17条未见明显疑点、8条标疑；17条新增10个ID | 17条不是用户最终人工确认；不把25条全部当作通过资源 |
| 二补充：混合并集 | 原21加审阅后17，去重31/273个ID、9/25视频 | 混合验证强度；新增每ID只验证一个时刻，不外推连续区间 |

162个有GT视频由Dance65、Sports90、MOT17 train7组成。77段临时来源中的事件/位置资源由公开GT推导；
边缘与间断是操作性事件定义，并非独立人工语义标注。MOT17可见率字段与Dance/Sports恒1字段已区别处理。
初版时间保留一位小数造成82条位置指代换目标及2条超片尾，已统一三位小数并核验全部资源，初版留档。

外观补充采用3张生成裁剪、2张不同帧校验裁剪，再做固定时刻整帧匹配。
全视频所有ID图册唯一的门槛比原任务“某个t_ref唯一”更保守，每ID仅检查一个固定时刻；
因此覆盖不足不能推断未通过者在任何时刻都无法指认。全部25自动候选均已审阅；
问题包括帽型/帽标、发型/发饰、衣物归属与内搭颜色误述。自动候选保留不改，17条另存，8条保留标疑。

当前仅得到数据、事实与指代候选，尚未生成目标900候选/600定稿QA，尚未运行试点跟踪器或正式评测。
当前主要未决项是描述真实准确与瞬时唯一性、身份语义适用范围、跟踪器训练/调参数据重叠。
这些是已有报告列出的后续事项，本次汇总没有推进到阶段三。

## 资源、失败记录与结果可信度

- TOC阶段二1951视频全部完成manifest大小与SHA核对，零解码失败；2323题无缺失/重复。
- TOC阶段四4196条有效预测、阶段五最终矩阵12588条、阶段六2783条新增预测、阶段七2532条新增预测。
  阶段五矩阵含4196条复用，另有历史失败实现输出；**不能相加当作互不重叠的独立题数或有效预测数**。
- 冻结后的全量MASA跟踪约4.00小时；轨迹文本P95约2069、最大3784 token，完整B输入最大24760，低于65536上下文。
- 阶段四推理含启动/停止约68.67分钟；阶段五从预登记到最终修正/清理约5.54小时；阶段六约3.37小时（合成LoRA训练35.67分钟）；阶段七交付约1.88小时。
  各项计时边界不同、部分任务并行，不拼成总墙钟耗时。
- MOT-QA盘点与GT资源计算使用CPU；外观补充下载18.29分钟，服务启动至清理24.24分钟，共577请求，无截断。
- 历史中的服务启动兼容、工具闭合标签、guided实现与时间显示问题均已保留失败记录，修复后的结果与旧实现分开。
- 两项目最后阶段的本任务模型服务均已结束并核验释放显存。本次汇总无需GPU。

## 原始对比表（从当前报告逐字摘取）

以下表格直接取自原文件，保留各维度分子与分母，便于逐项核对；阶段五采用最终修正版。
'''

    extracts = [
        ('阶段二：与论文表2比较', TOC / 'results/stage2_report.md', '| 指标 | 正确/总数 |'),
        ('阶段五：官方格式六条件', TOC / 'results/stage5_report.md', '| 条件 | Count |'),
        ('阶段五：简短推理六条件', None, None),
        ('阶段六：LoRA前后', TOC / 'results/stage6_report.md', '| Before B-events |'),
        ('阶段七：工具修复主表', TOC / 'results/stage7_report.md', '| 条件 | Count |'),
        ('MOT-QA：外观补充覆盖', ROOT / 'results/stage2_appearance_report.md', '| 指标 | 结果 |'),
    ]
    excerpt_html = []
    for title, source, prefix in extracts:
        if source is None:
            source = TOC / 'results/stage5_report.md'
            content = source.read_text().split('## 3.2 主表：简短推理模板，测试可表达251题', 1)[1]
            lines = content.splitlines()
            start = next(i for i, line in enumerate(lines) if line.startswith('| 条件 |'))
            table = []
            for line in lines[start:]:
                if not line.startswith('|'):
                    break
                table.append(line)
            table_text = '\n'.join(table)
        elif prefix == '| Before B-events |':
            content = source.read_text().split('## 可学性：纯合成LoRA前后', 1)[1]
            table_text = '\n'.join(line for line in content.split('## 测试全部602题', 1)[0].splitlines()
                                   if line.startswith('|'))
        else:
            table_text = first_table(source, prefix)
        excerpt_html.append('<h3>' + html.escape(title) + '</h3><div class="table-wrap">' + render(table_text, source) + '</div>')

    index_rows = []
    report_sections = []
    for record in records:
        ident, title = record['id'], record['title']
        superseded = record['status'] == 'superseded'
        badge = '已替代·历史稿' if superseded else '样例附录' if record['kind'] == 'appendix' else '当前报告'
        index_rows.append('<tr><td><a href="#' + ident + '">' + html.escape(title) +
                          '</a></td><td>' + badge + '</td><td>' + html.escape(record['note']) + '</td></tr>')
        warning = ('<p class="notice">本稿已由最终修正版替代。历史guided实现结果不纳入最新主结论。</p>' if superseded else '')
        body = render(source_bytes[record['source']].decode('utf-8'), Path(record['source']))
        report_sections.append(
            '<details class="source-report' + (' superseded' if superseded else '') + '" id="' + ident + '">'
            '<summary>' + html.escape(title) + ' <span class="badge">' + badge + '</span></summary>'
            '<div class="report-body">' + warning + '<p class="source-meta">原文件：<a href="' +
            html.escape(record['source'], quote=True) + '">' + html.escape(record['source']) + '</a><br>SHA256：<code>' +
            record['sha256'] + '</code></p>' + body + '</div></details>')

    title = 'TOC-Bench 与 MOT-QA Pilot 全部报告汇总'
    document = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + title + '''</title>
<style>
:root{color-scheme:light;--ink:#182735;--muted:#526472;--line:#d7e0e7;--accent:#165c70}
*{box-sizing:border-box}body{margin:0;background:#f2f5f7;color:var(--ink);font:16px/1.8 system-ui,-apple-system,"Noto Sans CJK SC",sans-serif}
main{max-width:1280px;margin:24px auto;padding:32px 42px;background:white;border:1px solid var(--line);border-radius:12px}
h1{font-size:29px;line-height:1.4}h2{font-size:23px;margin-top:36px;padding-top:12px;border-top:1px solid var(--line)}h3{font-size:19px;margin-top:25px}
a{color:var(--accent);text-underline-offset:3px}p,ul,ol{margin:14px 0}li{margin:5px 0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0}th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}th{background:#edf4f6}tbody tr:nth-child(even){background:#f9fbfc}
.table-wrap{overflow-x:auto}pre{overflow-x:auto;background:#f3f6f8;padding:14px;line-height:1.5}code{font:13px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}
.meta,.source-meta{font-size:13px;color:var(--muted);overflow-wrap:anywhere}.notice{padding:13px 18px;background:#fff4d9;border-left:4px solid #b27912}
.toolbar{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}button,.toolbar a{padding:8px 12px;background:#edf4f6;border:1px solid var(--line);border-radius:5px;color:var(--ink);font:inherit;cursor:pointer}
.source-report{border:1px solid var(--line);border-radius:7px;margin:14px 0;scroll-margin-top:16px}.source-report>summary{padding:14px 18px;cursor:pointer;background:#f6f9fb;font-weight:600}.report-body{padding:12px 22px 25px;overflow-x:auto}.report-body h1{font-size:25px}.badge{font-size:12px;color:var(--muted);font-weight:normal}.superseded>summary{background:#fff5df}img{max-width:100%;height:auto}blockquote{margin:14px 0;padding-left:16px;border-left:3px solid var(--line);color:var(--muted)}
@media(max-width:760px){main{margin:0;border:0;padding:20px 16px;border-radius:0}h1{font-size:24px}table{display:block;overflow-x:auto}th,td{min-width:90px}.report-body{padding:10px}}
@media print{body{background:white}main{border:0;padding:0;margin:0;max-width:none}.toolbar{display:none}.source-report{break-before:page}summary{font-size:20px}.report-body{padding:0}a{color:inherit}table{font-size:10px}h2,h3{break-after:avoid}}
</style></head><body><main id="top"><h1>''' + title + '''</h1>
<p class="meta">汇总生成：''' + html.escape(generated) + '''（北京时间） · 13份报告 + 4份样例附录 · 仅整合已有结果</p>
<div class="toolbar"><a href="#report-index">报告目录</a><a href="#originals">完整原文</a><button id="expand">展开全部原文</button><button id="collapse">收起全部原文</button><button id="print">打印当前展开内容 / 保存PDF</button></div>
''' + render(overview) + '\n'.join(excerpt_html) + '''
<h2 id="report-index">报告目录与版本</h2><p>点击目录项可展开对应原文。标为“已替代”的阶段五旧稿只用于追溯；样例附录不另计为阶段报告。</p>
<table><thead><tr><th>报告</th><th>状态</th><th>关键内容</th></tr></thead><tbody>''' + ''.join(index_rows) + '''</tbody></table>
<h2 id="originals">完整原文与样例附录</h2>
<p>原文以完成时状态保留，附图已嵌入本HTML。指向其他本地JSON、预测、图册或目录的链接仍指向原项目位置；离开服务器后可能不可用。压缩包收录原始报告与4份附录，不包含视频、模型、完整逐题预测或外观图册。</p>
''' + '\n'.join(report_sections) + '''
<p class="meta">原始报告逐字节保存，路径、大小与SHA256见source_manifest.json。该清单用于确定本次汇总所对应的报告版本；较晚的实证结论优先于早期解释。</p>
<p><a href="#top">返回顶部</a></p></main>
<script>
function reveal(){const id=decodeURIComponent(location.hash.slice(1));const node=document.getElementById(id);if(node&&node.tagName==='DETAILS'){node.open=true;requestAnimationFrame(()=>node.scrollIntoView());}}
addEventListener('hashchange',reveal);reveal();
document.getElementById('expand').onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=true);
document.getElementById('collapse').onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=false);
document.getElementById('print').onclick=()=>window.print();
</script></body></html>'''
    html_path = OUT / 'all_reports_summary.html'
    html_path.write_text(document)
    summary_data = {
        'generated_at': generated,
        'scope': 'Two conversation projects; existing results only',
        'report_count': len(SPECS), 'current_report_count': 12,
        'superseded_report_count': 1, 'appendix_count': len(APPENDICES),
        'key_results': {
            'toc_official_reproduction': {'correct': 623, 'n': 2323, 'accuracy_percent': 26.82},
            'toc_test_trackable_n': 251,
            'toc_official_A': 89, 'toc_official_B': 88,
            'toc_T1_fixed': 98, 'toc_Tph': 98, 'toc_Tsh': 94,
            'toc_majority': 126, 'toc_route_A': 112,
            'mot_public_gt_videos': 162, 'mot_gt_track_ids': 2518,
            'mot_dance_val_gt_ids': 273, 'mot_appearance_auto_candidates': 25,
            'mot_appearance_agent_clear': 17, 'mot_appearance_flagged': 8,
            'mot_appearance_mixed_union_ids': 31,
            'mot_qa_generated': 0,
        },
        'interpretation': [
            'No detectable true-trajectory-content benefit through TOC stage7; not proof of raw-trajectory impossibility.',
            'Earlier route gains do not establish information beyond class priors.',
            'MOT-QA stage2 resources are candidates, not finalized QA or independent human-certified identities.',
        ],
    }
    (OUT / 'summary_data.json').write_text(json.dumps(summary_data, ensure_ascii=False, indent=2) + '\n')

    # Preserve original bytes and include only figures already in these reports.
    for record in records:
        target = OUT / record['archive_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_bytes[record['source']])
    asset_records = []
    for source, data in sorted(assets.items()):
        path = Path(source)
        group_root = TOC if path.is_relative_to(TOC) else ROOT
        group = 'toc_bench' if group_root == TOC else 'motqa_pilot'
        archive = Path('figures') / group / path.relative_to(group_root)
        target = OUT / archive
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        asset_records.append(dict(source=source, archive_path=str(archive), bytes=len(data), sha256=sha(data)))
    manifest = dict(generated_at=generated, report_count=len(SPECS),
                    current_report_count=12, superseded_report_count=1,
                    appendix_count=len(APPENDICES), reports=records, figures=asset_records,
                    generated_html=dict(path=html_path.name, sha256=sha(html_path.read_bytes())),
                    exclusions=['raw video', 'model weights', 'full prediction data', 'external local evidence files'])
    (OUT / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'bundle_notes.txt').write_text(
        '全部研究报告汇总\n\n打开 all_reports_summary.html 阅读总览和可展开原文。\n'
        '13份阶段报告：12份当前报告，1份阶段五历史稿；另含4份完整样例附录。\n'
        '原报告以原字节复制，见original_reports；阶段五初稿已被最终修正版替代。\n'
        '本HTML内嵌了原报告所用图片，图片原文件另见figures。\n'
        '报告引用的其他原始预测、JSON、视频、外观审阅图册仍在服务器原项目路径，不包含于本压缩包。\n'
        '本次不做任何新实验，也不修改历史结论原文；最新阶段七结论在汇总中说明。\n')
    with zipfile.ZipFile(ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(OUT))

    # Check packaging, not experiment logic: every source is unchanged and present.
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        for record in records:
            assert sha(Path(record['source']).read_bytes()) == record['sha256']
            assert sha(archive.read(record['archive_path'])) == record['sha256']
    assert sum(r['kind'] == 'report' for r in records) == 13
    assert document.count('<details class="source-report') == 17
    assert 'stage5_report_initial_implementation.md' in document
    print(json.dumps(dict(html=str(html_path), html_bytes=html_path.stat().st_size,
                          zip=str(ZIP), zip_bytes=ZIP.stat().st_size,
                          reports=13, appendices=4, figures=len(assets),
                          verification='All original report/appendix bytes unchanged and archived.'),
                     ensure_ascii=False))


if __name__ == '__main__':
    build()
