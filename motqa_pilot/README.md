# MOT-QA Pilot

当前最新版本为可辨认性修订v3：900道候选已完成原始GT和全库质量/平衡核验，等待中文12题补审。原900题和人审决定保留；正式过滤与阶段五尚未开始。

- [最新修订报告](results/stage3_readability_v3_report.md)
- [中文补审12题ZIP](results/motqa_readability_v3_review12_zh.zip)
- [修订版900题](data/candidates_readability_v3.jsonl)

Project root: `/home/user/motqa_pilot` (user approved storage relocation).

Current status:Stage3 round2 has generated900 formal candidates, excluding the20 user-approved design examples. O1/O2/O3/O4/O5/O6/O7/O8/composition counts are60/90/100/105/100/100/110/135/100. All900 answers plus20 corresponding rule-revision examples pass original-GT recomputation, including marked identity-confusion options. The old20 examples remain unchanged. Filtering, final pilot release and Stage5 GT-model checks have not run; stop here for the Stage3 report.

最新人工抽查已收到：原JSON为18通过、2不确定；对话额外指出0.440秒事件指代困难。0225、0229、0777三题在审阅旁表中暂缓，0777原勾选通过仍保留。当前17题无额外异议；其余880题未经这次逐题人工审阅。GT重算通过不代表事件与指代在视觉上均清楚。修订建议另存，候选、答案、GT及锁定配置未改，尚未生成替换题或启动过滤。

- [本次人审结果与时间事件疑点诊断](results/stage3_round2/manual_review_diagnosis/review_findings_zh.md)
- [原始决定与三题暂缓依据](results/stage3_round2/manual_review_diagnosis/review_dispositions.json)

- [当前阶段三报告：900道正式候选](results/stage3_round2_report.md)
- [900道候选数据](data/candidates.jsonl)
- [20道对应规则差异：无需重审旧题](results/precheck_rule_diff.md)
- [正式候选抽查20题中文ZIP](results/motqa_round2_formal_sample20_zh.zip)
- [阶段五判断标准：推理前已锁定](results/stage5_criteria_locked.json)
- [阶段三交付与哈希记录](results/stage3_round2/delivery_receipt.json)

- [已完成审阅：3题重现先后补审（中文版，约12MiB）](results/motqa_temporal_replacement_review_3_zh_v2.zip)
- [3题补审页面](results/question_review_replacements/打开3题补审.html)
- [3题补审交付与验证记录](results/question_review_replacements/delivery_receipt.json)
- [3题原始GT答案独立核验](results/question_review_replacements/raw_gt_answer_audit.json)

- [当前20个已通过设计槽位](data/question_review_user_passed_20.jsonl)
- [替换3题对话确认记录](results/question_review_replacements/user_chat_approval.json)

- [完整题人工复核导入与3条相机运动问题](results/question_review/user_question_review_import_summary.json)
- [复核结果：保留原决定并补充相机运动原因](results/question_review/question_review_result_with_camera_notes.json)
- [相机运动题型补充规则](results/question_review/camera_motion_design_addendum_v1.json)
- [已通过的17条设计](data/question_review_user_passed_17.jsonl)
- [待替换的3条设计](data/question_review_camera_revision_3.jsonl)

- [下载：完整推理题中文预审20题（含视频，完整解压）](results/motqa_complete_question_review_20_zh_v1.zip)
- [完整题审阅页面](results/question_review/打开完整题审阅.html)
- [20题原始GT答案核验](results/question_review/raw_gt_answer_audit.json)
- [完整题审阅交付记录](results/question_review/delivery_receipt.json)

原20题完整题包已完成人工审阅，结果 `question_review_result.json` 已导入。新的3题已由用户在对话中全部确认通过，原17题无需重复。两轮均可查看原片、GT核验片段和精确源帧。

- [整理后的完整人工复核结果](results/review/reference_review_result_final.json)
- [原始上传、补充决定与可用池统计](results/review/user_review_import_summary.json)
- [逐条修改依据](results/review/reference_review_adjudication_changes.json)

- [Stage 2 appearance supplement report](results/stage2_appearance_report.md)
- [All25 automatic candidates and agent review](results/stage2_appearance/visual_review/all_auto_candidates.html)
- [Stage 2 report](results/stage2_report.md)
- [Stage 1 report](results/stage1_report.md)
- [Sequence inventory](results/sequence_inventory.csv)
- [Language mappings](results/language_descriptions.jsonl)
- [Licenses](logs/licenses.md)
- [Downloads](logs/downloads.md)
- [Original request](task_request.txt)

Raw datasets are referenced read only; all derived files remain in this project. Provisional sources and unresolved tracker training overlap are documented in the report.

Reports from both conversation projects: [consolidated report](results/report_collection_20261104/all_reports_summary.html), [original reports and sample appendices ZIP](results/all_reports_20261104.zip). Includes 13 stage reports (one superseded historical version) and 4 sample appendices; no new experiments.

- [中文审阅 v2：主区137条、补充17条](results/review/reference_review_zh_v2.html)
- [下载中文审阅 v2 包（完整解压后打开）](results/review/reference_review_zh_v2.zip)
- [Portable offline review ZIP](results/review/reference_review_offline.zip)
- [Pre-Stage3 preparation report](results/stage3_preparation_report.md)
- [Official tracker candidate audit](logs/tracker_candidates.md)

外观描述审阅 v2 为已完成的前一轮审阅，154条原描述与对应人工结论仍留存。原20题完整问题也已审阅。替换3题也已由用户确认通过，当前没有待审设计题。
