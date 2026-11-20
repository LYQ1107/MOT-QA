# MOT-QA Pilot 阶段二报告

生成时间：@@NOW@@。用户授权先继续、后续选公开跟踪器；训练/调参重叠仍待具体跟踪器确定后核对，本轮沿用 DanceTrack val、SportsMOT val、MOT17 train 后半段的临时来源范围。

基础 GT 事实与指代资源已计算完，**停在阶段二，不生成候选 QA**。主要问题是外观资源集中于少量视频和身份，且人工语言标注的单目标指定未必构成视觉唯一性。按附件3.4停下汇报，没有调用模型补描述。

统一了 **162个有GT视频、2,518个GT轨迹ID、1,294,527条有效行人标注**。DanceTrack/SportsMOT保留ID=0；MOT17固定FRCNN副本，过滤flag=0和非class=1行。每序列一个NPZ，轴为`[track,frame,xywh]`，显式提供GT ID与原帧号；原始框另存，缺失框为NaN，presence/visibility/visible分别保留。MOT17官方1-based坐标转为0-based，DanceTrack/SportsMOT保持发布框的坐标；无裁框、插值或ID重标。时间为`(frame-1)/fps`，后半段保留原视频秒数。

数据位于 `/home/user/motqa_pilot/data/stage2/unified/`；路径与数组说明见 [sequence_metadata.json](/home/user/motqa_pilot/results/stage2/sequence_metadata.json)，逐轨迹索引见 [track_index.jsonl](/home/user/motqa_pilot/results/stage2/track_index.jsonl)。

可见性先按附件默认阈值0.25测算，约定状态为 **PROVISIONAL_PENDING_STAGE2_REVIEW**，待本次汇报确认后锁定。DanceTrack/SportsMOT第九列恒1，不作为实测可见率，按GT框是否存在判断；MOT17按visibility≥0.25。

@@DATA_TABLE@@

MOT17阈值分布如下，分母112,297为有效行人GT行。阈值0也包含visibility=0的完全不可见标注。

@@VIS_TABLE@@

MOT17有10,485行visibility=0，29,601行visibility=1。建议沿用0.25，保持任务预设；没有依据QA分数调参，也未声称已校准为真实可见面积精度。完整分布见 [visibility_distribution.json](/home/user/motqa_pilot/results/stage2/visibility_distribution.json)。[约定文件](/home/user/motqa_pilot/results/visibility_convention.json) SHA256：`@@VIS_SHA@@`。

事件按以下口径计算：框中心x三等分，距两条分界线≤5%画面宽度记为模糊；连续不可见帧数/fps严格大于1秒才记间断，最后可见框距任意边缘小于2%相应宽/高记离开，否则记遮挡；下一可见帧记重现。视频片尾持续不可见超过1秒记终端消失；第一帧已在边缘的首现单列左删失，不用作观察到进入过程的事件指代。

IoU≥0.1连续至少3帧构成重叠片段；紧邻前/后帧中两人均可见、非零横向中心差变号才记交叉。缺失端点或中心并列标unknown，不算成没有交叉。画面移动距离只累加相邻可见帧中心位移并除以画面对角线，缺失间隔不连直线。保留机位标签，moving视频中的数值仅表示画面内运动。离开/遮挡是附件定义的**操作性边缘判据**，不是独立人工语义事件标注。

全部162段的统计如下。首现贴边数量包含第1帧，删失数单列；终端消失包含在离开/遮挡中，不再与其相加。

@@EVENT_TABLE@@

临时候选来源77段的统计如下。MOT17只纳入全部证据都在后半段的事件，不把半段起点视为真实首次入场。

@@ELIGIBLE_TABLE@@

逐序列进入、离开、遮挡、重现、重叠、交叉和删失数均见 [sequence_events.csv](/home/user/motqa_pilot/results/stage2/sequence_events.csv)；所有点事件和双人重叠证据分别见 [point_events.jsonl](/home/user/motqa_pilot/results/stage2/point_events.jsonl)、[overlap_events.jsonl](/home/user/motqa_pilot/results/stage2/overlap_events.jsonl)。

MOT17出画再入会使用新ID，因此不能仅据原ID终止判断真人不再回来，也不能直接跨全片把所有不同ID当作不同真人。其位置、关系、交互事实可在原ID有效关联范围内使用。DanceTrack明确保证完全遮挡后同ID，对所有出画再入的保证仍未明确；SportsMOT要求运动员片段内唯一ID。本轮没有跨ID拼接真实身份，适用范围保存在 [identity_applicability.json](/home/user/motqa_pilot/results/stage2/identity_applicability.json)。

三类指代只从临时来源窗口生成：外观先按视频和规范化文本合并所有原始标注的逐帧目标，再与可见GT相交，恰好一个ID才算自动唯一；事件要求同类事件在±1秒内唯一；位置使用leftmost/rightmost，与第二名中心差≥5%宽度且至少两人可见。未来3秒列只表示仍有≥3秒视频时间，未断言已经能构造某道题。

@@REF_TABLE@@

外观自动唯一性如下。组通过率分母是窗口内确有标注可见目标的描述组；帧通过率分母是有标注可见目标的`(视频,文本,帧)`，不是全部视频帧。**这些指标不是视觉准确率。**

@@APP_TABLE@@

合计484个外观连续唯一时段、352个事件指代、2,344个位置连续唯一时段。外观包括250个`(视频,文本,目标ID)`单位，实际仅149个不同`(视频,目标ID)`。同一人多个描述、多个时间点不能当作新增身份。原文、GT证据、时间范围与来源SHA均见 [reference_resources.jsonl](/home/user/motqa_pilot/results/stage2/reference_resources.jsonl)。

外观唯一时段中位长度：DanceTrack 1.475秒、SportsMOT 3.2秒、MOT17约0.429秒；短于1秒分别53/118、57/223、105/143。本轮只报告时长，没有添加最短时长过滤。来源和指代汇总见 [dataset_summary.json](/home/user/motqa_pilot/results/stage2/dataset_summary.json)。

DanceTrack val的273个GT身份中，仅21个有标注意义的唯一描述，**252个未覆盖，18/25个视频完全没有唯一外观资源**。没有唯一资源的视频为：@@MISSING_VIDEOS@@。7个有自动唯一资源的视频也不是视觉质量通过名单。逐身份缺口见 [appearance_gaps.json](/home/user/motqa_pilot/results/stage2/appearance_gaps.json) 和 [逐序列覆盖表](/home/user/motqa_pilot/results/stage2/appearance_coverage_by_sequence.csv)。

原目标要求约900候选/600定稿、外观约50%；当前不能证明能得到450/300道可靠外观题。443个留足未来3秒的外观时段不等于443道独立合格题，也不能据此断言绝对做不了450题：重复使用身份、可构造操作、混淆选项和后续过滤损耗尚未评估，不能提前编造QA容量或答案盲基线。

智能体查看了每个数据集最短/最长唯一时段的6帧；这是极端时长选择，**不能用于估计整体描述错误率**。观察如下，原始描述及GT均未修改，也没有据此悄悄删除自动候选。

- DanceTrack短例仅0.05秒，目标高度重叠，白色T恤难以核实；长例的蓝裤子较能区分，但深色外层/浅色内搭措辞仍需核查。
- SportsMOT长例 `v_cC2mHWqMcjk_c007` 第318帧，原句为“The player in the left-side team wearing white clothes.”，原始JSON指定ID10，其原始GT框指向绿色上衣运动员，存在颜色/ID映射疑点。未猜测偏移、未修正ID。短例right-side team player属于空间/群体指代，非纯个体外观。
- MOT17两例都是泛化的person/man walking描述，画面中多人，JSON指定一个ID不能证明自然语言能唯一指认。故自动单目标指定不足以直接进入正式题库。

@@IMAGES@@

完整记录见 [visual_review_notes.json](/home/user/motqa_pilot/results/stage2/visual_review_notes.json)。以下是SportsMOT疑点实图，红框为原JSON指定的原始GT身份：

![SportsMOT颜色与目标映射疑点](/home/user/motqa_pilot/results/stage2/reference_review/SportsMOT_long.jpg)

还修正了实际发生的时间显示错误：初版保留一位小数，1,336条位置指代落到相邻帧，其中82条改变目标、2条超出片尾，另2条事件在显示时间±1秒内不再唯一。现统一三位小数，2,344个位置时间全部还原原锚帧，352个事件逐一核对锚帧与显示时间唯一性，全部通过。GT、事件阈值、锚帧和资源数量未改。初版文件留在 `results/stage2/revisions/initial_1decimal/`，原因见research_log及 [初版审计](/home/user/motqa_pilot/results/stage2/time_display_audit_initial.json)，定向回归见 [time_display_regression.json](/home/user/motqa_pilot/results/stage2/time_display_regression.json)。[指代模板](/home/user/motqa_pilot/results/stage2/reference_templates.json)已保存。

数值核验包括全部162个NPZ的presence/visible行数、时间轴和哈希；种子42分层抽取90个指代，从原始GT与原始描述JSON独立重算；另30个交叉逐帧核对IoU与前后交换。全部通过，阶段一快照也未改变，见 [source_audit.json](/home/user/motqa_pilot/results/stage2/source_audit.json)。这些检查验证计算与标注一致，不能替代语言本身的准确性和唯一性检查。

主计算耗时@@COMPUTE_SECONDS@@秒，另计来源核验、视觉查看与报告时间；最多4个CPU工作线程，无GPU、无新下载、无删除。未启动预计超过6小时的操作。阶段二协议SHA256为 `@@PROTOCOL_SHA@@`；完整阈值在 [protocol.json](/home/user/motqa_pilot/results/stage2/protocol.json)，数据与结果摘要在receipt和快照中。

建议沿用可见性0.25；外观资源缺口需要下一步决定。附件3.4的备选是用强视觉语言模型为GT裁剪补描述，再做同视频唯一性与视觉核查，保留确实无法外观区分的身份。可以先针对DanceTrack val的273个ID，其中252个目前无自动唯一资源。生成描述不能替代人工GT轨迹或生成答案，SportsMOT/MOT17已有描述疑点也需在使用前核查。

原附件明确写“备选方案（需用户同意后执行）”，本轮没有该项授权，模型调用数为0。请用户选择是否授权补描述，或先收窄到可核验的现有指代资源。**已停下，不进入阶段三；未生成候选QA、答案或训练集，未运行模型评测、训练或跟踪器。**
