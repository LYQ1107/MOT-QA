"""Review handoff, full900 change ledger and preserved-source receipt."""
from collections import Counter
import json

import generate_candidates_round2 as g
import readability_v3 as v
from render_readability_v3_review import REASONS


def table(headers, rows):
    return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join(
        '| '+' | '.join(str(x).replace('|', '/') for x in row)+' |\n' for row in rows)


def main():
    audit = json.loads((v.D/'raw_gt_and_readability_audit.json').read_text())
    browser = json.loads((v.D/'browser_check/browser_check_result.json').read_text())
    assert audit['status'] == browser['status'] == 'PASSED'
    stats = json.loads((v.D/'summary.json').read_text())
    scan = json.loads((v.D/'all900_before_revision_audit.json').read_text())
    review = json.loads((v.D/'review_receipt.json').read_text())
    qs = g.rows(g.ROOT/'data/candidates_readability_v3.jsonl')
    old = {q['qa_id']: q for q in g.rows(v.D/'before_revision/candidates_round2_original.jsonl')}
    byslot = {q['previous_slot_qa_id']: q for q in qs}
    scanned = {q['qa_id']: q for q in scan['checks']}
    ledger = []
    for oldid, prior in old.items():
        q = byslot[oldid]
        reasons = scanned[oldid]['after_reference_repair']['issues']
        ledger.append({
            'old_qa_id': oldid, 'new_qa_id': q['qa_id'],
            'action': 'replaced' if q['replaces_qa_id'] else 'same_source_facts',
            'same_question_text': q['question'] == prior['question'],
            'reference_changed': [[p.get(k) for k in ['role','type','target_id','frame','text','text_zh','box_xyxy_normalized']] for p in q['reference']['persons']] != [[p.get(k) for k in ['role','type','target_id','frame','text','text_zh','box_xyxy_normalized']] for p in prior['reference']['persons']],
            'old': {'dataset': prior['dataset'], 'sequence': prior['sequence'],
                    'operation': prior['operation_name'], 'template': prior['template_id'],
                    'question_zh': prior['question_zh'], 'semantic_answer': prior['semantic_answer']},
            'new': {'dataset': q['dataset'], 'sequence': q['sequence'],
                    'operation': q['operation_name'], 'template': q['template_id'],
                    'question_zh': q['question_zh'], 'semantic_answer': q['semantic_answer']},
            'original_scan_reasons': reasons,
            'reason_zh': [REASONS.get(x, x) for x in reasons],
            'preserved_unmodified_reviewed_question': bool(q.get('preserve_reviewed_question'))})
    g.putrows(v.D/'all900_change_ledger.jsonl', ledger)
    changes = ['# 可辨认性修订v3：全部900题逐题记录\n',
               '旧题、原人审决定与旧20示例保留。以下对应编号是版本槽位；替换题可能换视频、人物或子模板。\n']
    for item in ledger:
        if item['action'] == 'replaced' or item['old']['question_zh'] != item['new']['question_zh']:
            changes += [f'\n## {item["old_qa_id"]} → {item["new_qa_id"]}\n',
                        f'处理：{item["action"]}；原因：'+('；'.join(item['reason_zh']) or '为满足全库配额、原有答案平衡和本轮明确的事件定义，联合重选或修订。')+'\n',
                        f'旧：{item["old"]["dataset"]}/{item["old"]["sequence"]}；{item["old"]["question_zh"]}\n',
                        f'新：{item["new"]["dataset"]}/{item["new"]["sequence"]}；{item["new"]["question_zh"]}\n']
    (v.D/'question_changes_zh.md').write_text('\n'.join(changes))
    families = Counter(q['template_id'] for q in qs)
    exclusion = {'recorded_at': v.now(), 'candidate_sha256': v.sha(g.ROOT/'data/candidates_readability_v3.jsonl'),
                 'rule': 'All held_out wordings and all composition questions are forbidden in future training.',
                 'held_out_qa_ids': [q['qa_id'] for q in qs if q['paraphrase_split'] == 'held_out'],
                 'composition_qa_ids': [q['qa_id'] for q in qs if q['split_role'] == 'held_out_composition'],
                 'additional_held_out_template': str(v.D/'o7_time_template_addendum_locked.json')}
    g.dump(g.ROOT/'results/training_exclusion_manifest_readability_v3.json', exclusion)
    now = v.now()
    root = str(v.D)
    report = [
        '# MOT-QA Pilot：人工反馈后的可辨认性修订v3\n',
        f'完成时间：{now}。本次完成900候选修订、原始GT重算、配额/盲基线检查及12题中文补审包；正式过滤、定稿与阶段五推理尚未开始。\n',
        '## 修订结果\n',
        f'原900题逐题检查：{scan["dispositions"].get("eligible_with_recorded_revision",0)}题可直接保留或修订，{scan["dispositions"].get("replace",0)}题因规则或明确人审疑点需要替换。为同时满足原有操作/来源/答案平衡，最终保留{stats["retained_original_facts"]}题的原素材事实，替换{stats["replaced_original_questions"]}题；两种数目含义不同。原“0225、0229、0777”均替换，映射见逐题记录。\n',
        f'{stats["unchanged_reviewed_preserved"]}道人审通过题的题面、参考图文、选项与答案完整保留；原人工决定均未改写。其余改动没有自动获得人工通过。补审12题是有目的的诊断覆盖，不用于估计全库通过率。\n',
        table(['操作','候选数'], [(op, stats['operations'][op]) for op in g.CFG['candidate_operation_targets']]),
        table(['数据集','候选数'], stats['datasets'].items()),
        table(['指代方式','候选数'], stats['references'].items()),
        f'格式：{stats["formats"]}；身份挑战{stats["identity_challenge"]}/900；二选一{stats["binary"]}/900；人物裁剪图选项{stats["image_options"]}/900；有效身份混淆干扰项{stats["confusion_options"]}/{stats["choice_n"]}。使用{stats["videos"]}视频，每视频最多{stats["max_per_video"]}题，每主身份最多{stats["max_primary_reuse"]}题。\n',
        f'外观指代仍只取用户通过的描述；本轮联合质量与配额选择得到{stats["references"].get("appearance",0)}题，低于15%的部分由框标补齐，没有新增描述。事件指代仍为{stats["references"].get("event",0)}题，位置指代{stats["references"].get("position",0)}题。\n',
        '## 具体规则与边界\n',
        '原可见性定义及超过1秒的事件定义保持不变。事件题在中英文中明确这个定义；本轮选材要求关键间断至少2秒、消失前/重现后稳定可见至少0.6秒，并要求实际32帧里至少2张处在间断内且有前后可见状态。没有发生类题排除问题区间及既定2秒延伸内实际存在重现（含短间断）的例子，避免原0229的歧义。\n',
        '事件指代要求至少1秒可见上下文，参考框宽至少32像素且至少画面2%；在同一个可见段内找更清楚的参考帧，找不到就换题。原16×48、画内比例、遮盖、IoU等门槛仍适用。中文补齐左右边缘信息。代理条件不能证明人眼一定清楚，因此保留人工判断。\n',
        '视频输入统一为：从最早参考帧前1秒，到问题终点后2秒，裁剪到原授权来源窗口；在该片段内按floor(i*N/32)均匀采32帧。窗口只由题面参考/问题时刻确定，不读答案事件来选关键帧。保留原视频秒数，参考图及3倍裁剪仍放在32帧之后。后续A/G/G-ph/G-sh使用完全相同的片段、帧与时间戳；执行代码必须读取video_input字段。\n',
        f'输入片段长度分布（秒）：{stats["input_window_duration_s"]}；采样间隔分布（秒）：{stats["input_sampling_interval_s"]}。数值时间题的间隔均≤1秒，对应既定±0.5秒容差；本轮没有按模型输出修改任何配置。\n',
        '## O7模板补充与平衡\n',
        f'保留原“重现后在哪个区域”{families["return_region"]}题；另有同属O7的“何时重现”{families["premise_return_time"]}题（三时间段加没有发生）。原因是长间断且稳定重现的Sports素材无中间区域正例，仅靠区域模板无法满足原有条件答案平衡。新模板在生成前另行锁定，5种英文改写、其中2种仅用于测试，真假总量仍各55题；各数据集内真假/正例类别平衡要求继续检查，没有接收放宽的诊断解。\n',
        '初次修订的900题GT答案全部通过，但O6的来源语义盲基线比全局高7pp，未达5pp要求，故归档未交付。最终版本通过原口径复检，O6约束处理图片、时间档、计数子类在来源间的集中问题，并在图片/文字选项中分别均衡答案位置；未修改指标或门槛。\n',
        table(['操作','选择题数','全局多数字母','仅来源字母','语义多数','仅来源语义'], [
            (op, b['multiple_choice_n'], f'{b["majority_letter"]:.2%}', f'{b["dataset_only_letter"]:.2%}',
             f'{b["semantic_majority"]:.2%}', f'{b["semantic_dataset_only"]:.2%}')
            for op, b in stats['blind_baselines'].items()]),
        '连续时间和精确人数作答没有四选一均匀随机基线；O7真假各半带来的50%语义多数按原约定明确报告。\n',
        '## 核验与补审交付\n',
        f'900题从原始GT独立重算通过；新采样、事件资格、来源身份范围、原硬门槛、全库配额和盲基线均通过。补查发现原裁剪选项题是在基础资格检查之后生成，旧900中14题遗漏了交错未知状态检查；这次统一补上，原人工勾选仍保留。自动核验不等于人工可辨认性认证。\n',
        f'实际解压最终ZIP，在Firefox {browser.get("browser_version")}检查全部12页：中文题面、{browser["images_loaded"]}张图片、每题实际32帧、原片播放、GT片段、保存、全12题导出与导入均通过。测试选择清除，浏览器已关闭。\n',
        f'- [中文补审12题ZIP]({review["zip"]})\n',
        f'- [本地补审入口]({review["page"]})\n',
        f'- [修订版900候选]({g.ROOT}/data/candidates_readability_v3.jsonl)\n',
        f'- [全部900题修改台账]({root}/all900_change_ledger.jsonl)\n',
        f'- [中文逐题差异]({root}/question_changes_zh.md)\n',
        f'- [规则锁定]({v.LOCK})；[O7补充模板]({root}/o7_time_template_addendum_locked.json)\n',
        f'- [原始GT与可辨认性检查]({root}/raw_gt_and_readability_audit.json)\n',
        f'完整解压ZIP，打开“打开中文补审12题.html”，导出`{review["export_filename"]}`。这12题需要用户对可辨认性作判断；收到结果后再推进过滤。\n',
        '本轮只有已有公共视觉特征的CPU补算，没有问答模型推理、跟踪、权重下载或训练；原始GT、visibility、v2配置、原900题和旧20示例按原文件保留。阶段五标准保持锁定，正式规模未扩增。\n',
    ]
    path = g.ROOT/'results/stage3_readability_v3_report.md'
    path.write_text('\n'.join(report))
    receipt = {'recorded_at': now, 'status': 'REVISION_COMPLETE_WAIT_USER_READABILITY_REVIEW12',
               'report': str(path), 'report_sha256': v.sha(path),
               'candidate_file': str(g.ROOT/'data/candidates_readability_v3.jsonl'),
               'candidate_sha256': v.sha(g.ROOT/'data/candidates_readability_v3.jsonl'),
               'rules_sha256': v.sha(v.LOCK), 'review_zip_sha256': review['zip_sha256'],
               'review_zip': review['zip'], 'manual_review_required': 12,
               'original_human_choices_preserved': True,
               'filtering_executed': False, 'stage5_executed': False,
               'preserved_source_files': json.loads(v.LOCK.read_text())['preserved_source_files']}
    for p, digest in receipt['preserved_source_files'].items():
        assert v.sha(p) == digest, p
    g.dump(v.D/'delivery_receipt.json', receipt)
    g.dump(g.ROOT/'results/current_candidate_revision.json', receipt)
    readme = g.ROOT/'README.md'
    text = readme.read_text()
    lead = ('当前最新版本为可辨认性修订v3：900道候选已完成原始GT和全库质量/平衡核验，等待中文12题补审。'
            '原900题和人审决定保留；正式过滤与阶段五尚未开始。\n\n'
            '- [最新修订报告](results/stage3_readability_v3_report.md)\n'
            '- [中文补审12题ZIP](results/motqa_readability_v3_review12_zh.zip)\n'
            '- [修订版900题](data/candidates_readability_v3.jsonl)\n\n')
    readme.write_text(text.replace('# MOT-QA Pilot\n\n', '# MOT-QA Pilot\n\n'+lead, 1))
    with (g.ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## 可辨认性修订v3交付 — {now}\n\n'
                f'原900扫描{scan["dispositions"]}；最终保留原素材事实{stats["retained_original_facts"]}、'
                f'替换{stats["replaced_original_questions"]}，为联合配额和平衡所需，原文件均留存。'
                f'保留{stats["unchanged_reviewed_preserved"]}道人审题图文选项答案不变；原三疑点均替换。'
                f'900原始GT答案、可辨认性代理、原硬门槛和所有盲基线复检通过。'
                f'新32帧输入窗口仅由题面时刻确定，原视频时间戳不变，所有后续条件共用。'
                f'O7区域{families["return_region"]}/时间档{families["premise_return_time"]}，真假55/55。'
                '实际ZIP中文12页、全部图片/32帧、视频播放、保存和真实导出导入通过；测试决定已清除并关闭浏览器。'
                '交付后等待用户可辨认性补审，不启动过滤、问答模型、跟踪、训练或正式扩增。\n')
    print(path)
    print(json.dumps({k: stats[k] for k in ['retained_original_facts', 'replaced_original_questions',
          'references', 'formats', 'identity_challenge', 'confusion_options', 'image_options']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
