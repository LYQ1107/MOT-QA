# MOT-QA Pilot research log

## Stage 1: inventory

2026-11-04T19:55:24.626671+08:00

User approved `/home/user/motqa_pilot` because `/data2` had only 499 MiB free. Raw datasets remain read only.

Plan: (1) bounded local discovery; (2) verify official sources, licenses and GT conventions; (3) inventory split/sequence/frame/GT and language coverage, with per-sequence background-motion estimates; (4) report findings and training-overlap question, then stop. No question generation, evaluated-model inference, tracker execution or training. Seed 42.

## Stage 1 result — 2026-11-04T20:20:26.124241+08:00

162 public-GT videos plus 7 MOT17 test videos inventoried; no frame-count or sampled-decode anomalies. All 373 GT/seqinfo files and 197 image-tree manifests match local release archives; DanceTrack complete archive checksums match publisher LFS. Complete LaMOT archive recovered from existing partial extraction: 7,556 annotation files verified against official Git blobs. All 4,472,553 relevant language frame/ID references match original GT.

Appearance resource risk: Dance val has 425 query combinations but only 40 positive and 12 single-ID-over-whole-clip entries. MOT17 deliberately assigns new IDs after leaving/re-entry, so future natural-person reappearance/unique-person questions need scope restrictions; no GT changed. Camera labels: 28 static/141 moving, including 5 explicit agent visual resolutions; thresholds unchanged. Keep the inventory and stop before Stage 2.

Failure and fix: an extra publisher-metadata request failed on HTTP308 under system Python3.10; added standard 308 redirect dispatch, retried direct, obtained official checksums. No proxy, dataset deletion, training or GPU work.

## Stage 2 start — 2026-11-04T20:44:15.555928+08:00

User authorized continuation while selecting public trackers; tracker training/tuning overlap remains unresolved. Continue GT-only construction under the existing provisional source restriction. Plan: normalize the 162 public-GT sequences; measure visibility and use provisional 0.25 for MOT17; derive region/gap/entry/overlap/crossing/screen-distance facts; aggregate original descriptions and measure time-specific uniqueness plus event/position references; quantify appearance shortfalls and stop at the Stage 2 report. No QA generation or model/tracker execution.

### Stage 2 reference time-display fix — 2026-11-04T20:57:23.885416+08:00

A concrete pre-QA audit found 0.1-second text rounding shifted 1,336 position anchors; 82 changed the named target, 2 rounded past the final frame, and 2 event references acquired a second same-type neighbor within the stated +/-1 second. Preserve the initial resources/protocol in results/stage2/revisions/initial_1decimal, then render event/position times to 3 decimals. Underlying GT, source windows, events and geometric/visibility thresholds do not change. Check every final displayed timestamp against the original frame and uniqueness rule. No QA or model inference has run.

## Stage 2 result — 2026-11-04T21:07:48.708299+08:00

Unified162 videos /2518 IDs /1294527 target GT rows;1268058 visible rows at provisional0.25. Eligible references: appearance484 (443 future3s), event352 (312), position2344 (2060). All162 array checks,90 original-source reference checks and30 crossing checks passed. Retain facts and stop.

Appearance hypothesis: label-level uniqueness does not establish visual uniqueness. Dance val resources cover21/273 IDs in7/25 videos, leaving252 IDs and18 videos uncovered. Extreme-duration inspection found generic MOT17 references and a SportsMOT color/ID mismatch. Source GT and descriptions unchanged; no automatic candidate removal or ID repair. Stage2 reports label-based candidates only, not approved QA references. VLM supplementation requires explicit user approval under original3.4 and has not run. Tracker train/tune overlap remains pending public-tracker selection.

## Stage 2 approved appearance supplement — 2026-11-04T13:25:23.128411+00:00

User approved original3.4 fallback. Plan: all273 Dance val IDs get disjoint GT crops; official Qwen3-VL-32B-Instruct BF16 proposes truthful appearance phrases; blind held-out same-video matching and fixed-anchor full-frame matching reject ambiguity; agent visually checks examples; report and stop. No source edits, QA, trackers or training. Frozen protocol SHA256 `e91cf48fa65f5d3c3f8fe3dea7c00dfc67a056a75e40af5fade32f7f0ba9749f`. Same-model verification is a consistency check, not independent human truth.

### Appearance model download launch correction — 2026-11-04T13:30:11.804527+00:00

The full-weight command accidentally omitted --download and repeated only configuration verification/speed probing. The dependent inference preflight stopped on absent download_complete.json, before GPU allocation or any inference. Correct the command flag, retain logs, and resume full checkpoint download. No protocol/acceptance changes.

### Appearance vLLM startup compatibility fix — 2026-11-04T13:49:21.663799+00:00

vLLM0.16 architecture inspection failed before model loading: device_id_to_physical_device_id casts CUDA_VISIBLE_DEVICES elements to int and rejects GPU UUID strings. Use registered physical indices instead, retaining CUDA UUID verification immediately before launch. Archive failed attempt logs. No prompt, seed, model, precision, image/context or acceptance-rule changes; zero generated outputs. Run targeted architecture-import/device-mapping regression, then resume all273 IDs.

### Post-hoc candidate visual audit expansion — 2026-11-04T14:19:04.220302+00:00

Locked30-case review includes9 auto-pass cases. Five have questionable attributes: waist drawstring attached to hoodie, baseball cap called bucket hat, uncertain feathered headpiece, yellow front logo called yellow brim, white neckwear called bow tie. Automatic figures25 remain unchanged. Since the entire accepted pool is small, additionally inspect the remaining16 auto-pass IDs. Keep the original30 selection, lock extra16 as explicitly post-hoc, record concerns and emit an agent-cleared subset separately. No new model calls, description rewriting or threshold tuning.

## Stage 2 appearance supplement result — 2026-11-04T14:28:46.769854+00:00

All273 IDs processed; 272 valid phrases, 32 held-out global unique, 25 fixed-anchor automatic candidates. Original coverage21 IDs; automatic new coverage15, mixed-source auto union36/273. Locked visual sample30 plus explicitly post-hoc16 extra cases reviewed; all25 automatic candidates reviewed, 8 flagged, 17 have no obvious agent-identified issue; 10 newly covered IDs in the latter subset. Keep automatic results and agent-cleared subset separate, no source/GT repair or acceptance tuning. Same-model check repeats accessory/color errors and can falsely reject targets; do not treat it as independent human validation. Own model service terminated; stop before Stage3.

## Stage 2 appearance supplement result — 2026-11-04T14:32:33.393050+00:00

All273 IDs processed; 272 valid phrases, 32 held-out global unique, 25 fixed-anchor automatic candidates. Original coverage21 IDs; automatic new coverage15, mixed-source auto union36/273. Locked visual sample30 plus explicitly post-hoc16 extra cases reviewed; all25 automatic candidates reviewed, 8 flagged, 17 have no obvious agent-identified issue; 10 newly covered IDs in the latter subset. Keep automatic results and agent-cleared subset separate, no source/GT repair or acceptance tuning. Same-model check repeats accessory/color errors and can falsely reject targets; do not treat it as independent human validation. Own model service terminated; stop before Stage3.

## Read-only report consolidation — 2026-11-04T22:49:54+08:00

User requested all reports. Collected TOC-Bench and MOT-QA Pilot: 13 stage reports (12 current, one superseded stage5 implementation) plus four sample/interaction appendices. Rendered a consolidated HTML with current conclusions and original text; archived unchanged source bytes and five existing figures. Verified every archived report/appendix hash against its source and all internal report links. Source reports, frozen protocols, labels and prediction files unchanged. No inference, training, tracking or QA construction. Outputs: results/report_collection_20261104/all_reports_summary.html and results/all_reports_20261104.zip.

## Stage 2 decisions and pre-Stage 3 review preparation — 2026-11-04T23:07:46.563889+08:00

Hypothesis: box references can reduce appearance ambiguity without inventing person descriptions. User locked MOT17 visibility>=0.25, source windows and 3-decimal timestamps; old visibility file archived. Plan: lock revised generation constraints, prepare 137 requested phrase review rows plus a collapsed 17-row prior-agent-clear section; use existing GT and deterministic CPU image descriptors only for review-frame selection and nearest distractor display. Audit official tracker training splits without weights or execution. Stop once the offline review page is delivered; wait for user-uploaded reference_review_result.json before QA generation. No benchmark labels/results used for tuning.

### Pre-review preparation corrections — 2026-11-04T23:16:09.388755+08:00

Initial frame renderer stopped because installed OpenCV5 omits HOGDescriptor. Preserve failed protocol/log; compute the same declared category of unsigned gradient-cell appearance proxy directly in NumPy, then re-render without any model. No selection was locked or labels assigned. Also remove unintended censored-absence wording from MOT17 O3 policy before any QA; archive old config and record both hashes. New config hash b75ddac560bb71629e37120f97f0c5e23c4b8dddb052e9605d2d750a8fd85166.

### Review source-frame enumeration fix

Second build stopped at image-count assertion: SportsMOT contains AppleDouble ._*.jpg sidecars. Restore the Stage1 inventory enumeration rule (exclude ._ sidecars) and verify numeric frame IDs1..N. Source pixels/GT and selection criteria unchanged; no incorrect Sports frame was rendered, no final review list emitted. Keep failed log and prior protocol.

### Review short-track input limitation

The third build found one selected SportsMOT identity (v_2QhNRucNC7E_c017 ID20) exists in only two frames in the entire original GT. Two distinct other-time images are impossible for this row. Keep the original seed42 sample and denominator40; show its single other-time crop and an explicit missing-image placeholder, not a duplicated view or replacement identity. All other153 identities have at least3 visible frames. No QA or user decisions exist. Preserve failed protocol/log.

## Reference review handoff — 2026-11-04T23:32:35.692464+08:00

Prepared137 main +17 collapsed additional rows, all unreviewed. Sports seed42 sample covers29 videos. One original2-frame ID has only1 other-time view;2 anchors only1 comparator;12 horizons<3s all explicitly flagged, no resampling/dropping. All766 derived JPEGs and source hashes checked; Firefox offline export/save/import and28/40 threshold passed; test choices cleared. Two documented tracker backends: OC-SORT/ByteTrack; Dance/Sports train detectors traced. Official MOT17 half-train conversion includes1 boundary frame beyond floor(N/2), so do not claim compatibility with current source window. PureCrowdHuman fallback separately documented, no tracker weights fetched/run. Stop for user JSON;0 QA/model/training calls.

### Handoff wording correction

The two same-frame comparator shortages are0(Dance0004 ID3) and1(Sportsv_9MHDmAMxO5I_c006 ID0), not1 each. Corrected preparation report/readme and repackedZIP, retaining prior report and hashes. Actual locked selection, page/images, source facts and browser validation unchanged.

## Review opening failure: compact offline delivery — 2026-11-04T23:51:56.595735+08:00

User could not open original review due to an internal visualization error. Prior Firefox standalone validation did not establish in-app compatibility. Exact app failure not reproduced; original document48MiB is an avoidable delivery burden. Archive original HTML/ZIP, preserve locked selection and every image byte, generate <256KiB HTML loading5rows per page plus local images. Keep packet ID, full154-row export schema and selection hash unchanged; existing exported reviews remain importable. Validate actual extracted ZIP opening, paging, full-result export and import in a system browser. No QA, model or tracker work.

### Compact review delivery verified

The app browser explicitly returned: Remote file URLs cannot be opened in the local browser. This does not establish the exact cause of the prior visualization engine error. Verified the actual ZIP after extraction to a path with spaces/Chinese in Firefox136: original154 metadata equal,5 rows/page,25 first-page JPEGs loaded at original dimensions, changes persist across pages/reopen, real export contains all154 even when filtered, legacyJSON import works,28/40 gate preserved. Test choices cleared and browser closed. Entry122669bytes,766 image files byte-identical. Updated opening instructions and delivery receipt; review list/config/QA status unchanged.

## Clarify downstream operations and complete-QA review — 2026-11-05T14:51:50.278205+08:00

User asks where later reasoning types are. Record explanatory O1–O7/composition templates, GT computation descriptions and separate20-item complete-QA review workflow. No templates are bound to real videos/answers; not candidate QA. Existing generation gate and locked config unchanged, actual QA count0. Current page remains reference validation only; later review must show complete questions/options/GT evidence and answers.

## 中文审阅版本 — 2026-11-05T15:04:42.959410+08:00

按用户要求，154条描述（81种英文原文）逐条忠实翻译为中文，中文优先展示，英文原文折叠保留；来源、指代时刻、提示改为中文，支持中英文搜索。保留原描述中的笼统和疑似错误细节，不依据图片改写。生成独立中文ZIP，旧英文页面和交接记录留存历史。锁定名单、配置、766张图片及JSON导出字段未变。从实际解压包用Firefox136检查：154条译文、原文一致性、图片加载、分页、保存、全量导出、旧JSON导入及Sports70%门槛均通过，测试选择已清除。仍等待用户人工复核JSON；本次没有生成QA或进行模型/跟踪推理。

## 中文下载入口漏同步修复 — 2026-11-05T16:20:10.880348+08:00

用户截图显示人物描述仍为英文。检查发现中文HTML/独立zh包已更新，但此前browser/offline两个常用ZIP入口仍含旧英文页面，交付遗漏属实；无法确定用户实际打开了哪一个本地副本。保留旧包于history，统一四个当前ZIP为中文v2，并使包内原英文文件名入口也显示中文；增加唯一v2下载文件名和可见版本标题。从实际v2 ZIP解压后用Firefox验证全部154条译文、第一条中文描述、图片、分页、保存、导入导出及原门槛通过；所有当前ZIP及网页入口同步检查通过，测试选择清除。锁定名单、配置、原文和图片未改，仍等待用户复核JSON，无QA生成或模型推理。

## 单ID绑定与语义歧义说明 — 2026-11-05T20:05:50.443073+08:00

用户指出MOT17第70条“在街上行走的人”符合多人。读取锁定条目确认红框仅来自LaMOT绑定的gt_id26，并非模型或人工确认的唯一语言匹配；此类泛化描述按单人指代标准应不通过。把页面红框说明和图注改为“原标注指定人物，不代表描述唯一”；明确多人符合时选择不通过。原拟多人物分组界面不能解决描述本身的歧义，本轮改为解释来源绑定，未生成多目标QA或推断全体语义匹配集合，未替用户写入通过/不通过决定。154条锁定名单、时刻、原文、图片及通过标准保持不变，中文包各入口同步重建并通过内容完整性检查。

## 人工复核导入与用户批量补充 — 2026-11-05T20:19:13.383225+08:00

原始上传JSON完整留存：20261105_reference_review_result_4b0bb0e65491.json，SHA256 4b0bb0e654910673b8fe6467c4d463f381212e88783017eb255f727d0ff2a778。名单、原文、时刻与锁定包一致。原文件54通过/40不通过/2不确定/58未选择。用户补充“剩下的我没有写的也都是同样的问题”，据此将58未选择项记为多人歧义不通过；Sports第62/64/68条原勾通过但备注明确多人符合，按用户备注和单人唯一性标准整理为不通过；原勾选未被抹去，所有更改另存逐条依据。最终51通过/101不通过/2不确定。MOT17的68条均不通过，本包无MOT20。Sports29/40=72.5%，达到70%门槛，只允许逐条通过项。51条人工通过中4条Sports固定时刻后不足3秒，保留通过决定但不能用于正式出题；当前可用外观指代47条（Dance22/Sports25）。不唯一描述不从单个绑定ID外推成多人集合，外观缺口按既定规则转框标指代。锁定配置、名单、源数据不变；本轮仅整理人工反馈，尚未生成QA或调用模型/跟踪器。

## 完整题预审启动 — 2026-11-05T20:55:33.126588+08:00

用户要求现在审阅完整题。先生成20道有真实GT依据的设计预审题，8框标/5事件/4外观/3位置，覆盖O1–O7及两种组合；明确标为预审，不冒充从已完成900题抽样。只用人工通过外观；不运行模型/跟踪器。完整阶段三的视觉特征相似度与全批平衡仍待后续。

首轮在第3题MOT17左右关系处停止：现有位置/事件参考帧未提供同时满足几何门槛且后续交错的目标组合。保留失败日志与协议；从现有GT交错事件之前3.5秒增加框标参考帧候选，不改种子、题型、几何门槛或源GT。

完整题预审实现修正：MOT17有25个合法交错片段，但严格框标门槛下的候选在后续左右间距不足5%。静态“谁在左侧”模板被实现额外限制为必须交错；原任务的身份干扰允许重叠或交错。改为要求参考后有真实重叠，并保持5%问点间距和所有框标门槛；扩充MOT重叠前参考帧候选。不改原GT、种子、题型配额或已锁定用户规则。此前两次均未输出最终题库。

预审候选扩展遇到左删失重叠事件（before_frame=None）并停止。它没有有效的“重叠前”证据帧，恢复阶段二既定规则：不作为此类框标锚点；未知事件不当作负例。无最终题库输出。

首版20题已经完整生成，但身份混淆选项覆盖率45%，未达到原定70%。保留首版题目/协议/日志，按原任务允许的重采样，优先选择有真实重叠对象且错误跟踪会产生不同答案的题。不改GT、答案计算、几何门槛或70%标准。

## 完整推理题中文预审交付 — 2026-11-05T21:13:34.891029+08:00

生成20道真实GT推理设计预审题，框标8/事件5/外观4/位置3；Dance8/Sports8/MOT17四题。覆盖O1–O7与O5+O2、O6+O4组合，O1占10%，虚假前提占10%，每个显式目标身份最多复用3题。首版干扰覆盖45%未达要求，保留旧版后按原规则重采样，最终19/20=95%；未改几何门槛、原GT或用户锁定配置。20题答案全部从原始GT文本独立重算通过。制作40个10fpsMP4（原片/GT核验各20）及精确源关键帧；正式框标图保留原分辨率、3px红框、无其他框和ID。实际ZIP解压后在Firefox136验证中文问题、两人指代图、视频实际播放并解码、分页保存、全20题导出/导入，测试选择清除且浏览器进程关闭。本批明确为设计预审，未冒充从已完成900题随机抽取。小批语义答案分布已另存，不能据此报模型分数；全批平衡、公开视觉特征appearance_similarity、过滤和正式阶段三验收尚未完成。停止等待用户上传question_review_result.json，不运行模型/训练/跟踪器，不进入正式过滤阶段。

## 完整题人工复核：移动镜头位移歧义 — 2026-11-05T22:39:22.055552+08:00

用户上传20题复核：17通过、0不通过、3不确定、0未选择。原始JSON按字节留存，名单/问题/哈希核对通过。用户明确三条不确定均因相机运动，核对为第4(Dance0019)、5(MOT17-11)、17(SportsG-v...)，全部O5累计位移比较且camera_motion=moving。原题虽限定画面内，GT计算仍是框中心的图像路径，不能代表人物实际走过的路程；数值重算通过不足以证明题面适合人工/模型推理。保留17条通过和3条不确定，不把不确定改成失败或通过。补充原因另存；17条进入已通过设计池，3条暂缓。记录生成前补充规则：主池累计图像路径比较只允许明确固定机位，移动/未知机位不纳入；O5优先换成首次出现/重现先后比较。其他移动机位题仍按原画面位置/事件含义保留，不移除整类视频，不修改锁定基础配置、原题、GT或答案。尚未生成替换3题与900题整批，无模型/跟踪器运行。

## 三题重现先后替换补审交付 — 2026-11-05T22:57:56.729962+08:00

用户询问是否还有需要审计的题目。针对此前第4/5/17题移动镜头累计位移歧义，生成3道O5重现先后比较替换题，保留原槽位与replaces_qa_id映射，旧3条不确定记录和已通过17条均不改。新题分别来自DanceTrack0014、MOT17-10-FRCNN和SportsMOT v_ITo3sCnpw_k_c012；Sports外观指代严格复用用户通过的原描述/身份/时刻，不生成新外观描述。移动相机不再用于推断人物路程。

从原始GT文本独立重算三题可见间断和首次重现顺序均通过。核验发现MOT17的visibility<0.25区间含部分可见帧，故在交付前把泛称“消失”修正为“可见性间断/重新清晰可见”，页面明确25%既定约定；未改可见性阈值、事件时刻或锁定配置，最初措辞版本另存history。Dance/MOT仅使用同ID内部遮挡间断，Sports不询问消失原因。合并17+3后显式目标身份最多复用3题，混淆选项覆盖85%。

交付中文3题ZIP（12834080字节），含6个原片/GT核验MP4及精确源帧。实际解压ZIP在Firefox136以file路径验证中文、多人物指代、视频播放并解码、分页保存、全3题真实JSON导出和重新导入，测试选择已清空并关闭浏览器。新导出名为question_review_replacement_result.json。更新README和当前状态，历史状态另存。仍等待用户对新3题的人工决定；没有将自动核验当成人工通过。约900候选整批、全量平衡、公开视觉特征和正式过滤未完成；无模型、跟踪器或训练运行。停止等待补审，不推进后续阶段。

## 三题全部通过与题型/方法讨论 — 2026-11-05T23:06:13.398218+08:00

用户明确表示“这三个都通过了”。以原话和精确题目哈希另存对话确认，不伪造上传的JSON；17条原通过题与3条时间顺序替换题合并为20个已通过设计槽位。原3条距离题的不确定记录、原17题文件、替换题原始文件、锁定生成配置和可见性约定均未改。题型数量为O1=2/O2=3/O3=2/O4=3/O5=3/O6=3/O7=2/组合=2。用户要求先讨论所有题型与主动工具调用相较脚本的意义，本轮仅登记确认和核对清单，不启动900题生成、模型推理或跟踪。现有全部答案从轨迹定义可确定性计算；后续若主张大模型主动调用收益，必须比较相同预测轨迹后端下的脚本问答、离线轨迹输入与主动查询，不能把可用脚本算答案本身宣称为大模型独占能力。

## 第二轮硬规则与正式候选生成启动 — 2026-11-05T23:37:55.994864+08:00

用户授权修订规则、新增O8/数值/改写、约900候选和后续GT检查；20个人工通过样例按字节保留且不计正式题库。先读现有GT生成/审核代码，锁定round2规则及阶段五判断标准，再生成20个对应修订版本并逐题记差异，最后生成约900候选和统计/GT核验。MOT17的7视频×20题上限140低于180，采用用户已允许15%=135题，其余45转Sports，目标Dance360/Sports405/MOT135。身份复用按新指令仅计主目标。O7前提真假各半与旧的四选一语义均匀要求有直接冲突，依新要求执行并明报50%多数基线；不靠洗牌掩盖。阶段三后停下，不自动启动过滤或阶段五。公共视觉特征仅用于难度与候选外观排序，不运行跟踪器。

第二轮生成真实序列检查遇到已有重叠事件的after_frame=None（边界删失），排序键不能比较None与整数。保留失败日志，排序使用frame/after_frame/frame_start中已有值；交错有效性判定和未知事件不作负例的规则保持不变，再跑同一序列。尚未输出正式候选。

对应样例重生成发现原第10题所在的Dance/event/O3候选池没有同时满足边界+2秒否定延伸的“否”例。不得为保留旧答案截断窗口；对应版本优先选同类合法否例，缺失时允许改成真实的重现正例，记录答案与片段变化。MOT17事件指代没有通过20%和5%双重余量的最近距离分段例，第13题同属O6的候选改用首次交错时段并保留严格几何/时间门槛；明确子类改变。数值样例采用第4/5时间和第7/11人数，共4/20；第17仍为O5但用三人重现先后选择，避免把不存在的Sports外观数值候选当作已生成。原20题不改。

900题联合配额首次不可行，保留求解器失败与仅诊断的弹性LP（不接受放宽数据集）。诊断指向MOT17容量和O6供给。发现区间题的3+4秒实现前提错误套用到单时刻题，使MOT17-09完全未供给、-10仅18题上限。新增只读GT生成的合法3/5秒单时刻候选，保留每题实际要求；同时补齐原任务已有O6“交错次数”子类。以上不降低用户的几何、比较、间断、视频/主身份上限，也不接受弹性LP的违约解。原池与失败日志留存。

首轮900候选的920答案/几何/时间核验全部通过，但语义盲基线复检发现整数舍入在分数据集汇总后累积：O3/O5的语义多数比例为38.33%/43.33%，O4数据集条件语义多数比全局高5.71pp。字母均衡不能掩盖这些问题。保留首轮候选/核验/统计，增加合并后的严格语义上限，并让小样本时间/计数子类各数据集共享一个众数类别，以原门槛重新采样；不修改GT、答案、题型数量、seed或验收标准。

干扰项核对发现O3替换身份时必须对应题目指定的间断起点，不能用另一个人的任意重现事件作答案。修正反事实干扰项推导：仅匹配±1秒内的同类间断，找不到则为“没有发生”，若与正确答案相同就不计身份干扰；O2/O5选人/组合位置的双角色互换加明确方法字段。此为生成逻辑修复，仍按>=70%选择题有效干扰项标准重新选题。修订样例第17选合法普通“未发生”例，展示2秒否定观察余量。

增强后的原始GT核验：919/920通过，唯一失败为MOT17-02的一个O7反事实干扰项。被错跟的ID17间断跨越半段验证起点，阶段二事件表因删失未记录，不能把它当“从未重现”；完整原GT表明其返回区域与正确答案相同。保留失败记录，把该删失反事实标为不可用，题干/正确答案不变；从已选900的检查点重做选项来源和覆盖率，再独立核验，不降低70%标准。

## 第二轮阶段三交付 — 2026-11-06T01:01:57.678430+08:00

正式候选900，O1–O8/组合为60/90/100/105/100/100/110/135/100；Dance360/Sports405/MOT135，76视频、405主身份，每视频≤20/主身份≤3。旧20题按字节保留且排除统计；对应修订20题统计为{"numeric": 4, "identity_challenge": 19, "ordinary_never": 1}，规则差异已落盘。身份挑战715/900；数值180/900；二选一150/900；图片选项45/900；外观106，不足29转框标（框434/事件225/位置135）。O7真假55/55；普通Never40/790。原始GT独立重算920题答案、主身份挑战标记、参考裁剪与已标身份反事实干扰项全过；有效选择题干扰项504/720=70%，未降低阈值。语义与字母来源盲基线复检均无超限。实际解压中文抽查ZIP，Firefox20页图片/视频播放/导入导出均通过，测试选择清除。仅运行已授权的公共视觉特征，无跟踪器、问答模型、训练或过滤。最终配置、改写、阶段五标准和未来训练排除项已保存及哈希；停止等待阶段三确认，不提前做阶段四、阶段五或正式规模扩增。

## 正式候选20题人工结果与时间事件疑点 — 1ce539a8cef6

2026-11-06T19:43:22.739321+08:00。用户原JSON18通过/2不确定；原样归档，17题无额外异议，0225/0229不确定及对话提及0777单列暂缓。原GT核对：0225关键缺框1.8秒，计划32帧中仅2张缺框状态；0229有0.25/0.40秒短间断但被>1秒事件定义排除，题面未限定口径却答“没有发生”；0777事件前仅0.44秒可观察，参考框18px。源帧已查看；GT可重算不等于人工可辨认。225事件指代中9题事件早于1秒、58题参考框宽<2%，仅描述性定位，不当作新增阈值或自动失败。保留原人审决定、候选、答案、GT和锁定配置；修订建议另存未应用；无过滤、模型、跟踪或训练。

## 人工反馈修订v3启动与全量扫描修复 — 2026-11-06T20:15:40.203414+08:00

用户“继续吧”授权900候选修订与中文补审。先阅读原生成、选择、资产与GT审核代码，另锁定v3规则：保留原>1秒事件定义，候选可辨认间断≥2秒、前后稳定可见≥0.6秒；统一按题面参考与问题时刻取片段后均匀32帧，缺失状态≥2帧且有前后可见状态；事件指代需1秒可见上下文及更清楚的参考帧。原GT、visibility、v2配置和旧20示例保留。第一轮扫描在固定人审题0240处停止：可选裁剪题在原流程的基础硬规则检查之后生成，故遗漏了全体交错未知状态检查；原始GT答案可重算不等于该完整性检查通过。最小修复是对原900与可选题统一调用既有hard_eligibility后再决定保留，不放宽规则或伪造用户不通过；保留失败日志和扫描结果，按原锁定v3重新扫描。

## 可辨认性v3：O7供给冲突与模板补充

初次900题选择不可行，诊断LP只用于定位冲突，未接受其放宽解。原因是要求长间断和稳定重现后，SportsMOT正例没有中间区域；DanceTrack原池左侧正例仅2个实际重现事实。保持真假各半和条件答案平衡，先锁定同属O7的“何时重现/没有发生”三时间档加否定选项模板，再从同一合格GT池生成候选。仍用原>1秒事件定义、候选≥2秒及相同采样检查，900总量、各操作/数据集配额不改。此前不含明确左右方向的事件指代中文已纳入修订，不把翻译有变化的条目冒充原样人工通过。

### v3首次答案核验通过，O6来源盲基线待重平衡

补充O7时间档模板后成功选900；原始GT答案、新可辨认性与硬配额均通过。O6按数据集语义多数22%，全局15%，差7pp超出5pp门槛，因此不交付该版；归档候选与失败统计。调整选择中的O6子类/来源集中约束，并在图片选项和文字选项各自均衡答案字母，使实际按原口径计算的盲基线达标；不改指标、阈值、GT或题目定义。复用已算公共视觉特征，从选题检查点继续。

### 中文补审页面换行转义修复

真实ZIP浏览器检查在初始翻页进度处失败，随后脚本编译明确报未转义换行。原因是Python普通三引号模板把JavaScript事实说明的换行转义解释成了字符串内换行。保留失败HTML/ZIP和日志，将中文HTML/JS模板独立存为源文件，直接读取，修复转义后从相同素材重新打包并重跑实际ZIP浏览器检查。候选900、答案、抽样12题、GT和冻结规则均未改。

## 可辨认性修订v3交付 — 2026-11-06T20:42:45.443884+08:00

原900扫描{'eligible_with_recorded_revision': 722, 'replace': 178}；最终保留原素材事实647、替换253，为联合配额和平衡所需，原文件均留存。保留9道人审题图文选项答案不变；原三疑点均替换。900原始GT答案、可辨认性代理、原硬门槛和所有盲基线复检通过。新32帧输入窗口仅由题面时刻确定，原视频时间戳不变，所有后续条件共用。O7区域62/时间档48，真假55/55。实际ZIP中文12页、全部图片/32帧、视频播放、保存和真实导出导入通过；测试决定已清除并关闭浏览器。交付后等待用户可辨认性补审，不启动过滤、问答模型、跟踪、训练或正式扩增。

## 当前题型盘点与O5覆盖边界 — 2026-11-07

用户要求详细展示主要题型。只读取v3的900候选及报告，无新生成、过滤或模型运行。核对当前O4全部为交错对象去重；O6细分为交错时间32、交错次数20、交错对象裁剪选人45、画面内最近距离3。O7区域62/时间档48，真假55/55。O5的70道数值题比较两人的首次重现时刻；另30道三人选最早题中20道仅一人有合格重现、10道无人重现，未构成充分的三人时序排序测试。该覆盖限制在用户说明中明确披露，当前候选、答案和锁定规则保持不变。
