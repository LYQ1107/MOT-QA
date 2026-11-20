"""Audit and package the review handoff; do not generate or approve any QA."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

from PIL import Image

ROOT=Path('/home/user/motqa_pilot')
OUT=ROOT/'results/review'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    generated=datetime.now().astimezone().isoformat()
    packet=json.loads((OUT/'reference_review_selection_locked.json').read_text())
    receipt=json.loads((OUT/'reference_review_receipt.json').read_text())
    browser=json.loads((OUT/'browser_check/browser_check_result.json').read_text())
    config=ROOT/'results/generation_config_locked.json'
    visibility=ROOT/'results/visibility_convention.json'
    assert sha(config)==packet['generation_config_sha256']
    assert json.loads(visibility.read_text())['status']=='LOCKED'
    assert browser['status']=='PASSED' and browser['test_choices_cleared']
    cases=packet['cases']
    assert len(cases)==154 and sum(r['review_scope']=='main' for r in cases)==137
    assert Counter(r['group'] for r in cases)=={
        'dance_flagged_vlm':8,'dance_original_refer':21,'sports_lamot_stratified':40,
        'mot17_lamot':68,'dance_agent_cleared_vlm':17}
    checked_images=set()
    checked_sources={}
    for c in cases:
        assert c['user_verdict'] is None
        assert round(float(c['t_ref_display'])*c['fps'])+1==c['reference_frame']
        assert abs(c['t_ref_s']-(c['reference_frame']-1)/c['fps'])<1e-9
        assert len({v['frame'] for v in c['other_target_views']} | {c['reference_frame']})==len(c['other_target_views'])+1
        paths=[c['full_frame']]+[v['path'] for v in c['other_target_views']]+[v['path'] for v in c['similar_people']]
        for value in paths:
            p=Path(value)
            with Image.open(p) as image:
                image.verify()
            checked_images.add(str(p))
        with Image.open(c['full_frame']) as image:
            assert image.size==(c['width'],c['height'])
        for p,digest in [(c['source_frame_path'],c['source_frame_sha256']),
                         (c['unified_gt_path'],c['unified_gt_sha256'])]+[
                         (x['source_frame_path'],x['source_frame_sha256']) for x in c['other_target_views']]:
            if p not in checked_sources:
                checked_sources[p]=sha(Path(p))
            assert checked_sources[p]==digest,p
    # Existing stage reports remain historical records, never rewrite their text.
    old_manifest=json.loads((ROOT/'results/report_collection_20261104/source_manifest.json').read_text())
    for report in old_manifest['reports']:
        assert sha(Path(report['source']))==report['sha256']

    sources=json.loads((OUT/'tracker_official_sources.json').read_text())
    def link(repo,path):
        d=sources[repo]
        return d['repository']+'/blob/'+d['revision']+'/'+path
    oc_author='https://github.com/noahcao/OC_SORT/issues/60#issuecomment-1319553251'
    dance_weights='https://huggingface.co/noahcao/dancetrack_models/tree/6487fc12a2fe13db44506592324cea83270f5812/bytetrack_models'
    sports_weights='https://drive.google.com/file/d/1wLJOZHwUbSBmjOfWw8n3fAPo3fvLyzUd/view'
    ch_weights='https://drive.google.com/file/d/1inCT7HeSJ08f27EfowABvjao0xYKtXz4/view'
    metadata=json.loads((ROOT/'sources/trackers/dancetrack_models_metadata.json').read_text())
    dance_ckpt=next(x for x in metadata['siblings'] if x['rfilename']=='bytetrack_models/bytetrack_model.pth.tar')
    tracker_text=f'''# MOT-QA Pilot：公开跟踪器候选的官方资料核查

核查时间：{generated}。本轮仅下载官方说明、代码配置与文件列表元数据；**没有下载任何跟踪权重、没有运行跟踪器**。
所有直连请求记录在`logs/downloads.md`与`logs/network_transfers.jsonl`，归档在`sources/trackers/`。
GitHub连接器读取文件元数据失败后，改用官方网页及不走代理的官方raw/API直连，没有改用第三方转存。

## 两个可选后端

| 后端 | 可确认的组件与适用范围 | 官方地址 | 许可 |
|---|---|---|---|
| OC-SORT | 纯运动关联，无独立ReID/关联网络权重；DanceTrack可用作者明确确认的train-only检测器；Sports可接下表train检测器，属于拟采用组合，未运行验证 | [官方仓库]({sources['ocsort']['repository']})、[训练/使用说明]({link('ocsort','docs/GET_STARTED.md')}) | [仓库MIT]({link('ocsort','LICENSE')})；底层YOLOX另有Apache-2.0说明 |
| ByteTrack | 置信度分层框关联，无独立ReID网络；DanceTrack及Sports用下表各自train-only检测器 | [官方仓库]({sources['bytetrack']['repository']})、[模型说明]({link('bytetrack','README.md')}) | [仓库MIT]({link('bytetrack','LICENSE')})；不同外部权重许可单列 |

这是两个跟踪算法后端，不把同一算法在不同数据集上的配置算成不同算法。以下“可用”表示官方文档能确认训练来源符合对应目标split限制，不表示已下载、实物复核或证明从未使用验证集选超参数。

## 逐权重核查

| 权重/组合 | 官方确认的训练来源 | 适用性与状态 |
|---|---|---|
| DanceTrack原发布 `bytetrack_models/bytetrack_model.pth.tar` | COCO预训练，再DanceTrack train；[官方训练说明]({link('dance','ByteTrack/README.md')})、[配置]({link('dance','ByteTrack/exps/example/dancetrack/yolox_x.py')})及[转换脚本]({link('dance','tools/convert_dance_to_coco.py')})只读train | **DanceTrack val文档级可用**；[官方HF模型地址]({dance_weights})。模型卡CC BY4.0；视频仍按DanceTrack非商业研究条件 |
| OC-SORT提供的DanceTrack检测器 `ocsort_dance_model.pth.tar`（历史命令亦名`bytetrack_dance_model.pth.tar`） | [维护者明确回复]({oc_author})确认只用DanceTrack train、未用val训练；[官方模型表]({link('ocsort','docs/MODEL_ZOO.md')})列val/test；不能仅凭test字样推断用了train+val | **DanceTrack val文档级可用**；使用[官方模型表的Drive文件夹](https://drive.google.com/drive/folders/1LnhZVJlpufUnWuObZASIN1KwfhuvT_a8)。重命名文件未下载，不能声称其SHA与上行相同；外部重命名权重未另见独立许可声明 |
| MixSort官方检测器 `yolox_x_sports_train.pth.tar`，用于ByteTrack或OC-SORT关联 | COCO→CrowdHuman train+val→SportsMOT train；[官方README]({link('mixsort','README.md')})区分train和mix流程，[检测器配置]({link('mixsort','exps/example/mot/yolox_x_sportsmot.py')})为train.json/name=train，转换脚本按split分别输出 | **SportsMOT val文档级可用**；[官方文件]({sports_weights})在README链接的官方Drive文件夹中列出。采用该检测器不加载MixFormer或其他ReID权重；[仓库MIT]({link('mixsort','LICENSE')})，外部checkpoint未单列权重许可 |
| `yolox_x_sports_mix.pth.tar` | 官方流程明确混合SportsMOT train+val | **SportsMOT val不可用**；[官方模型文件](https://drive.google.com/file/d/1lMUAp6pm7vx2KAfmr7grMgF6t5hRCz7l/view)，本轮仅查看目录元数据 |
| 原ByteTrack `bytetrack_ablation.pth.tar` | README为CrowdHuman + MOT17 half train；实际[转换脚本]({link('bytetrack','tools/convert_mot17_to_coco.py')})对0-based索引使用闭区间`0..N//2`，混合脚本读取train_half.json | **当前严格来源边界下不可用**：多包含本项目后半段首帧，见下表；不是“没有官方训练信息”，是有代码级边界冲突 |
| ByteTrack MOT17 test模型（如`bytetrack_x_mot17`） | 官方README明确含全部MOT17 train，另有CrowdHuman、Cityperson、ETHZ | **MOT17后半段不可用** |
| OpenMMLab ByteTrack half-train公开模型 | 官方模型表为CrowdHuman + MOT17-half-train；[其转换脚本](https://github.com/open-mmlab/mmdetection/blob/main/tools/dataset_converters/mot2coco.py#L152)同样以`N//2+1`切片 | **当前严格来源边界下不可用**，同一帧边界问题，不因换实现而自动通过 |
| MixSort `yolox_x_ch.pth.tar` | [官方训练配置]({link('mixsort','exps/example/mot/yolox_x_ch.py')})只读CrowdHuman mix.json；[混合脚本]({link('mixsort','tools/mix_crowdhuman.py')})为CrowdHuman train+val，README从COCO预训练后生成此checkpoint；官方Drive列出同名文件 | **不含任何MOT17训练帧的保守备选**；[官方文件]({ch_weights})，可接上述两种无训练关联器。但它没有MOT17前半段适配，不能冒充用户举例的“前半段消融权重”；若要求必须经过前半段适配，本轮尚无可确认完全符合当前边界的权重 |

Dance原发布checkpoint的发布者元数据：大小{dance_ckpt['size']} bytes，发布SHA256 `{dance_ckpt['lfs']['sha256']}`。
这里只读取官方LFS元数据，没有下载文件或宣称完成本地权重校验。Sports train/mix与CrowdHuman文件也只读官方目录元数据。

## MOT17边界冲突的直接计算

本项目锁定允许窗口为1-based `floor(N/2)+1..N`。ByteTrack官方转换器的train half为0-based `0..N//2`（包含末端），
即1-based `1..floor(N/2)+1`；因此每个序列有一帧交集。这是从官方代码及本项目窗口推得，不代表读取到了真实训练运行日志或权重内部数据。
在用户决定前不改本项目来源、GT、时间戳或窗口，不把“half train”文字说明直接当作无交集证明。

| MOT17序列 | 总帧数N | 项目后半段首帧 = 官方训练脚本包含的边界帧 |
|---|---:|---:|
'''
    metas=json.loads((ROOT/'results/stage2/sequence_metadata.json').read_text())
    overlap=[]
    for m in metas:
        if m['dataset']=='MOT17':
            frame=m['frames']//2+1
            tracker_text+=f"| {m['sequence']} | {m['frames']} | {frame} |\n"
            overlap.append(dict(sequence=m['sequence'],frames=m['frames'],potential_overlap_frame_1based=frame,
                                project_second_half_start=m['eligible_source_window_1based'][0]))
    tracker_text+='''
## 未获确认的组件与使用边界

- 完整MixSort的MixFormer、Deep-OC-SORT/BoT-SORT/StrongSORT等ReID权重，不能仅凭检测器train-only就认定整个管线可用。本轮没有取得每个此类公开权重的完整训练split依据，**未确认的权重一律不可用**，不作猜测。
- 未将公开val结果、test榜单名或第三方fork描述作为无训练重叠证明。官方论文/模型表的分数仅作资料，不当作本试点结果；上述后端均未安装或运行。
- 官方文档中的val评估、早停/选checkpoint及调参记录未必完整。这里确认的是公开训练来源；尚不能证明验证集完全没有用于超参数或checkpoint选择，不宣称试点测试对调参也完全未见。
- 两个可选后端都可在DanceTrack/SportsMOT采用已核实检测器。MOT17若坚持前半段适配，待解决边界问题；外部CrowdHuman-only是另列的保守备选，本轮不替用户选定或运行。

官方材料固定revision及本地档案见`results/review/tracker_official_sources.json`；额外README/API评论、HF/Drive元数据均保留原文件与下载记录。没有运行新实验，也没有为凑候选数把未知训练来源的权重写成可用。
'''
    (ROOT/'logs/tracker_candidates.md').write_text(tracker_text)
    write(OUT/'tracker_weight_audit.json',{
        'generated_at':generated,'tracker_backends':['OC-SORT','ByteTrack'],
        'downloaded_weights':0,'tracker_runs':0,
        'documented_target_split_eligible_weights':['DanceTrack original train detector','OC-SORT DanceTrack train detector','MixSort SportsMOT train YOLOX detector'],
        'mot17_half_adapted_status':'UNAVAILABLE_UNDER_CURRENT_LOCKED_BOUNDARY',
        'mot17_boundary_overlap_inference':overlap,
        'external_only_fallback':'MixSort yolox_x_ch.pth.tar; COCO pretraining + CrowdHuman train/val, no MOT17 adaptation',
        'unconfirmed_training_components':'unusable; no inference from detector provenance to additional ReID/association weights',
        'official_tuning_exclusion_proven':False,
        'report':str(ROOT/'logs/tracker_candidates.md'),
    })

    warnings_by_group={}
    for field in ['no_future_3s','less_than_two_same_frame_comparators','less_than_two_other_target_views','geometric_gate_not_met']:
        ids=set(receipt[field]);warnings_by_group[field]=dict(Counter(c['group'] for c in cases if c['review_id'] in ids))
    prep_report=f'''# MOT-QA Pilot：阶段二决定与阶段三前人工复核准备

完成时间：{generated}。项目根目录仍为`/home/user/motqa_pilot`，沿用用户已授权的独立项目。
本轮完成可见性锁定、补充约束落盘、离线人工复核页面及公开跟踪器资料核查，**尚未生成任何QA**。
按本次补充第4节，页面交付后停止，等用户上传`reference_review_result.json`。

## 已锁定的决定

- `results/visibility_convention.json`已改为LOCKED：MOT17 visibility≥0.25，Dance/Sports按GT存在；原因原文为“沿用任务预设，未依据 QA 结果调参”。旧字节及旧SHA在`results/review/history/`保存。
- 测试来源保持Dance val、Sports val、MOT17 train各序列后半段；时间显示三位小数。
- `results/generation_config_locked.json`记录框标45%/事件25%/外观15%/位置15%，外观不足转框标；原分辨率红框3px、几何和IoU门槛、归一化xyxy、after_frames、每身份最多3题。
- 各数据集O3/O4限制、Dance风险比例≤O3的20%、题型×数据集答案平衡与盲基线差5pp触发、MOT比例20%不足可降15%并转Sports、20题复核按8/5/4/3分层均已记录。
- 最终配置SHA256：`{sha(config)}`；可见性文件SHA256：`{sha(visibility)}`。新增模板和具体实现阈值仍须在真正生成QA前补充锁定，本轮没有伪称生成器已完成。

## 页面与名单

[可直接离线打开的复核页面](/home/user/motqa_pilot/results/review/reference_review.html)，约{receipt['html_bytes']/1048576:.2f}MiB，全部图片内嵌，无服务器或外部JS/CSS依赖。
原分辨率整帧画目标红框3px、其他GT人物灰框1px且无ID文字；另给同目标两个其他时刻裁剪和同帧相似者裁剪，支持点击放大。

| 复核组 | 条数 | 选择方式 |
|---|---:|---|
| Dance模型标疑 | 8 | 全部8条，原句和原验证时刻不改 |
| 原Refer-Dance | 21 | 全部21个身份，每身份一个原标注唯一时刻 |
| Sports LaMOT | 40 | seed42按视频分层、身份不重复，覆盖29/29个有候选视频 |
| MOT17 LaMOT | 68 | 全部68个身份，各选一条原始描述及一个时刻 |
| 主区合计 | **137** | 不因难例替换抽样或缩小分母 |
| 折叠补充区 | 17 | 此前智能体无明显疑点描述，为落实最终“只用用户通过”的要求也提供确认入口 |
| 页面总计 | **154** | 不同描述来源即使指向同一身份也分别复核 |

两张比较图按固定HSV颜色直方图70%＋梯度纹理30%的CPU余弦代理排序；没有运行ReID/视觉模型。
它只提供审阅近邻，不保证语义上最相似，页面也提醒检查整帧中的其他人。该代理不冒充未来题目难度字段要求的公开模型特征。
外观是否通过只由用户判断准确性和瞬时唯一性；备注不自动改写描述，未审核时刻不外推为连续可用区间。

## 不可凭空补齐的原始资源限制

- 1条Sports样本（`v_2QhNRucNC7E_c017`、ID20）在整段原GT只出现2帧，只能给1张不同于t_ref的目标图。保留所选身份，第二图显示缺失提示，不复制图片、不换成更容易的样本。
- 2条所选时刻的其他GT可见人物不足2名：Dance `dancetrack0004` ID3为0名，Sports `v_9MHDmAMxO5I_c006` ID0为1名，页面明确标注。
- 12条时刻在片尾不足3秒（Sports5、MOT17七条），仍按用户要求展示全部指定身份，明确标注该时刻不能直接出题；不从描述通过率分母去掉，也不偷偷换到未复核时刻。
- 17条所选时刻未满足框标的几何门槛，页面已提示审查可见细节；该门槛不是自动的外观语义判决。

详细分组：`{json.dumps(warnings_by_group,ensure_ascii=False)}`。
所有这些情况均不作为跳过人工复核或自动通过的理由。

## 保存、导出与审核门槛

页面每行“通过/不通过/不确定”及备注，默认均未选择；支持按数据集/状态/文字筛选、下一条未选择、浏览器自动保存及导入JSON继续。
顶部和底部均可导出`reference_review_result.json`，包含名单SHA、每行原文/时刻/来源及用户决定，未选择为null。
Sports全部40条决定完成后，以全部40条为分母（不通过/不确定仍在分母）；通过≥28条才保留其逐条通过的候选，否则整体不用Sports外观。
这不是将抽样通过外推到未审核的其他Sports描述。17条补充区若不审核，之后也不作为已通过资源。

已用隔离配置的Firefox136实际离线打开页面，验证：154行默认未选择、真实JSON下载、备注保留、重新打开后进度恢复、JSON导入往返、28/40与27/40门槛以及数据集筛选。
所有验证用选择已清空；测试导出仅存在`browser_check/exported_TEST_ONLY/`，绝非用户审核结果，不会进入候选生成。
截图及浏览器验证回执见`browser_check/`。审核名单SHA256：`{sha(OUT/'reference_review_selection_locked.json')}`。

## 跟踪器核查

[完整候选与逐权重依据](/home/user/motqa_pilot/logs/tracker_candidates.md)。候选后端为OC-SORT和ByteTrack，Dance train及Sports train检测器的官方来源有据。
不能把ByteTrack的MOT17 half-train模型直接标成严格无重叠：官方脚本实际多包含半段交界一帧，本项目当前后半段与其每序列交1帧，共7帧。
OpenMMLab公开实现也有同样切片边界；已列为当前窗口下不可用。另列COCO→CrowdHuman-only检测器作不含MOT17帧的保守备选，但不冒充前半段适配权重。
对未知额外ReID/关联权重不猜训练来源，标为不可用。未证明官方完全未用val选择超参数，故不宣称调参也完全无重叠。

## 完整性、修复与停止点

154行、137条主区分母均保留，核验{len(checked_images)}张派生JPEG可解码、原分辨率匹配、三位小数能还原锚帧、其他时刻帧不复用，所用原帧/NPZ摘要均与源记录一致。
13份阶段报告和4份旧样例附录均与上轮汇总清单的SHA一致；原GT、语言标注、旧报告和已生成资源未改写。
唯一应用户要求改动的旧约定是visibility状态，旧版本已保存；下载日志和研究日志正常追加。

初次渲染因OpenCV5不含HOGDescriptor停止，改用明确的NumPy梯度直方图；第二次因Sports AppleDouble侧文件计数停止，恢复阶段一排除`._`的规则；
第三次在上述仅2帧身份处停止，改为如实展示缺图，保留原样本。各失败日志/协议均在history，未改数据或跳过身份。
MOT17 O3配置最初误含删失缺席措辞，已在任何QA生成前按用户范围收紧，旧配置、原因和新旧SHA均留档；浏览器首个驱动沙箱不能读页面对象，改为内容上下文后通过，页面业务脚本未因此改变。

本轮CPU处理，无模型请求、无训练、无跟踪、无新权重下载；浏览器验证进程已关闭。
**到此停止，等待用户上传复核JSON；不开始阶段三题目生成或过滤。**
'''
    (ROOT/'results/stage3_preparation_report.md').write_text(prep_report)
    (OUT/'READ_ME_FIRST.txt').write_text(
        '打开 reference_review.html（全部图片已内嵌，可离线使用）。\n'
        '主区137条；另有折叠补充区17条。逐条判断原文是否准确且在t_ref唯一。\n'
        '选择通过/不通过/不确定，可写备注；无默认通过。可导出备份、导入继续。\n'
        '完成后点击页面底部导出 reference_review_result.json，上传回本对话。\n'
        'Sports全部40条决定后，以40为分母；通过至少28才保留其中逐条通过项。\n'
        '1个短轨迹无法提供第二张其他时刻图；2个指代帧分别只有0/1名其他可见人物，均如实标注。\n'
        '片尾不足3秒的12条仅供描述复核，不会直接拿不可用时刻出题。\n'
        '压缩包不含任何用户已作出的决定；目前全部未选择。\n')
    bundle=OUT/'reference_review_offline.zip'
    include={
        'reference_review.html':OUT/'reference_review.html',
        'READ_ME_FIRST.txt':OUT/'READ_ME_FIRST.txt',
        'reference_review_selection_locked.json':OUT/'reference_review_selection_locked.json',
        'reference_review_protocol_locked.json':OUT/'reference_review_protocol_locked.json',
        'generation_config_locked.json':config,
        'visibility_convention.json':visibility,
        'tracker_candidates.md':ROOT/'logs/tracker_candidates.md',
        'stage3_preparation_report.md':ROOT/'results/stage3_preparation_report.md',
    }
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        for name,path in include.items():z.write(path,name)
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
        assert z.read('reference_review.html')==(OUT/'reference_review.html').read_bytes()
    final=dict(finished_at=generated,status='WAITING_FOR_USER_REFERENCE_REVIEW',
               main_count=137,additional_count=17,qa_generated=0,model_calls=0,tracker_runs=0,
               jpeg_files_checked=len(checked_images),source_files_checked=len(checked_sources),
               unchanged_old_reports_and_appendices=17,
               generation_config_sha256=sha(config),visibility_sha256=sha(visibility),
               selection_sha256=sha(OUT/'reference_review_selection_locked.json'),
               html_sha256=sha(OUT/'reference_review.html'),html_bytes=(OUT/'reference_review.html').stat().st_size,
               zip_path=str(bundle),zip_bytes=bundle.stat().st_size,zip_sha256=sha(bundle),
               report=str(ROOT/'results/stage3_preparation_report.md'),
               tracker_report=str(ROOT/'logs/tracker_candidates.md'),
               browser_check=str(OUT/'browser_check/browser_check_result.json'),
               actual_user_review_received=False)
    write(OUT/'handoff_receipt.json',final)
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## Reference review handoff — {generated}\n\n'
            f'Prepared137 main +17 collapsed additional rows, all unreviewed. Sports seed42 sample covers29 videos. '
            f'One original2-frame ID has only1 other-time view;2 anchors have0/1 comparators;12 horizons<3s all explicitly flagged, no resampling/dropping. '
            f'All{len(checked_images)} derived JPEGs and source hashes checked; Firefox offline export/save/import and28/40 threshold passed; test choices cleared. '
            'Two documented tracker backends: OC-SORT/ByteTrack; Dance/Sports train detectors traced. Official MOT17 half-train conversion includes1 boundary frame beyond floor(N/2), so do not claim compatibility with current source window. '
            'PureCrowdHuman fallback separately documented, no tracker weights fetched/run. Stop for user JSON;0 QA/model/training calls.\n')
    readme=ROOT/'README.md'
    old=readme.read_text()
    old=old.replace('Current status: Stage 2 appearance supplementation complete and stopped before Stage 3.',
                    'Current status: Stage 2 decisions locked; pre-Stage 3 human reference review page ready. Waiting for user-exported reference_review_result.json before any QA generation.')
    old+='\n- [Human reference review page:137 main +17 additional](results/review/reference_review.html)\n- [Portable offline review ZIP](results/review/reference_review_offline.zip)\n- [Pre-Stage3 preparation report](results/stage3_preparation_report.md)\n- [Official tracker candidate audit](logs/tracker_candidates.md)\n'
    readme.write_text(old)
    print(json.dumps(final,ensure_ascii=False))


if __name__=='__main__':
    main()
