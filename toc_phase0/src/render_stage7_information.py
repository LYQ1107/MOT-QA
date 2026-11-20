"""Human-readable tables for the completed post-hoc information diagnostic."""
from stage6_common import ROOT,read

LABELS={'event_count':'Count','reappear_or_disappear':'R/D','cross_object_order':'X-Order'}
CLASSES={'fully_hidden':'完全遮挡','leaves_frame':'离开画面'}


def main():
    data=read(ROOT/'results/stage7_track_information_diagnostics.json')
    lines=['# 阶段七：轨迹信息量事后诊断','',
        '结论：按冻结v1规则及本次指定的指标，测试集尚无可靠证据表明其读出的事件信息超出开发集多数类别先验。R/D与盲基线同为51/75，边缘关联不显著；Count低于多数基线；X-Order有方向性的7/9对5/9，但样本仅9题、配对p=.5。此结论不证明原始轨迹中不存在任何更复杂的可用信息。','',
        '全部结果为事后诊断，不重新跟踪、不运行模型、不调整规则。主要盲基线只用开发集同维度/题型多数类别：R/D为完全遮挡，Count为2，X-Order为B；测试比较绝不按测试覆盖子集的多数类拟合答案。开发集已参与v1调参，仅作描述。','',
        f'![测试集规则混淆矩阵]({ROOT}/results/stage7/figures/test_rule_confusions.png)','','| 范围 | 维度 | 覆盖/总数 | 规则正确 | 平衡准确率 | kappa | 盲基线正确 | 差值pp [95%CI] | exact McNemar p |',
        '|---|---|---:|---:|---:|---:|---:|---|---:|']
    for scope,ds in data['covered_rule_diagnostics'].items():
        for dim,r in ds.items():
            m=r['frozen_rule'];b=r['majority_blind'];p=r['rule_minus_development_majority']
            if p:
                cells=[scope,LABELS[dim],f"{r['covered']}/{r['total']}",str(m['correct']),f"{100*m['balanced_accuracy']:.2f}%",f"{m['kappa']:.4f}" if m['kappa'] is not None else '—',str(b['correct']),f"{p['effect_pp']:+.2f} [{p['ci95_pp'][0]:+.2f}, {p['ci95_pp'][1]:+.2f}]",f"{p['mcnemar_exact_two_sided_p']:.6g}"]
            else:cells=[scope,LABELS[dim],f"{r['covered']}/{r['total']}"]+['—']*6
            lines.append('| '+' | '.join(cells)+' |')
    lines += ['','空覆盖子集不计算指标；不补题、不当作0分。平衡准确率按各真实类别的召回平均；Count的0/1预测作为错误完整保留，不能只在合法输出上计分。kappa考虑所有预测类别的边际分布。配对bootstrap1000次、seed42，exact McNemar双侧；事后p未作多重比较校正。']
    for scope,ds in data['covered_rule_diagnostics'].items():
        for dim,r in ds.items():
            lines += ['',f'## {scope} / {LABELS[dim]}','']
            if not r['covered']:
                lines += ['规则覆盖0题，混淆矩阵、平衡准确率、kappa和配对检验均不可计算。开发集覆盖子集多数类也无法估计；测试X-Order的主要盲基线固定采用全部37道开发题的多数选项B（22/37）。']
                continue
            if dim=='reappear_or_disappear':
                table=r['edge_table']['counts']
                lines += ['采用冻结规则实际选中的第一个间断；Before题排除终止间断。表中的边缘特征由消失前最后一帧框中心与画面边缘距离≤0.05计算，并核对其推导答案与已保存规则预测逐题一致。','',
                    '| 消失前是否贴边 | 真值：完全遮挡 | 真值：离开画面 |','|---|---:|---:|',
                    f'| 否 | {table[0][0]} | {table[0][1]} |',f'| 是 | {table[1][0]} | {table[1][1]} |','',
                    f"Fisher双侧p={r['fisher_exact_two_sided_p']:.6g}，odds ratio不可估计（无贴边样本）。开发集两种标签都存在，但贴边行为0次，无法据此学习有区分度的边缘关系。" if scope=='dev' else f"Fisher双侧p={r['fisher_exact_two_sided_p']:.6g}，odds ratio={r['fisher_odds_ratio']:.3f}。8个贴边事件中4个真值为离开；边缘判定给多数基线新增4个正确，也失去4个正确，净收益0。"]
            m=r['frozen_rule'];columns=m['prediction_columns']
            lines += ['','规则混淆矩阵（行为真值，列为规则预测）：','',
                '| 真值 \\ 预测 | '+' | '.join(CLASSES.get(c,c) for c in columns)+' |',
                '|---|'+'---:|'*len(columns)]
            for y in m['truth_rows']:
                lines.append('| '+CLASSES.get(y,y)+' | '+' | '.join(str(m['confusion_matrix'][y][c]) for c in columns)+' |')
            if r.get('covered_dev_majority_blind'):
                extra=r['rule_minus_covered_dev_majority']
                lines += ['',f"改用开发集规则覆盖题的多数类时，选中类别仍相同，配对差值{extra['effect_pp']:+.2f}pp，p={extra['mcnemar_exact_two_sided_p']:.6g}。"]
    lines += ['','## R/D分类别召回率','',
        'A/B为阶段四官方裸答案格式；B-events同时列出官方格式和阶段五推理格式，以便与阶段六LoRA的同提示词结果比较。每类独立分母，解析失败计错；LoRA未评测开发集，不补跑。测试全部R/D101题均在可表达子集中。','',
        '| 范围 | 模型 | 完全遮挡召回 | 离开画面召回 | 平衡准确率 |','|---|---|---:|---:|---:|']
    for scope,models in data['RD_model_class_recalls'].items():
        for name,r in models.items():
            if 'per_class_recall' not in r:cells=[scope,name,'N/A','N/A','N/A']
            else:
                cells=[scope,name]
                for c in ('fully_hidden','leaves_frame'):
                    cells.append(f"{r['confusion_matrix'][c][c]}/{r['true_distribution'][c]} ({100*r['per_class_recall'][c]:.2f}%)")
                cells.append(f"{100*r['balanced_accuracy']:.2f}%")
            lines.append('| '+' | '.join(cells)+' |')
    lines += ['','微调前推理B-events的完全遮挡/离开召回为5/68、24/33，微调后为23/68、17/33。总体正确数由29升至40，主要表现为对多数类完全遮挡召回提高，同时少数类离开召回下降；平衡准确率仅由40.04%升至42.67%。该变化不足以证明获得了超出类别先验的时间推理能力。','',
        '## R/D路由增益分解','','| 测试子集 | 题数 | 官方A正确 | 冻结规则正确 | 多数盲基线正确 | 路由正确 |','|---|---:|---:|---:|---:|---:|']
    for part,r in data['RD_routing_prior_decomposition']['test'].items():
        lines.append('| '+part+' | '+' | '.join(str(r[k]) for k in ['n','official_A','frozen_rule','majority_blind','route'])+' |')
    lines += ['','在规则覆盖的75题上，固定选完全遮挡与冻结规则同得51题，均比官方A的27题多24题；规则不覆盖的26题上，多数盲基线17题、A12题。因此R/D路由63题相对A39题的增益，可以在本样本上由类别先验替代实现，并不需要这条边缘特征；这是事后解释，不是对全部原始轨迹信息量为零的证明。','',
        f'[完整统计、逐题边缘事实与来源哈希]({ROOT}/results/stage7_track_information_diagnostics.json)；[开发多数类别锁定文件]({ROOT}/results/stage7_majority_baselines_locked.json)。']
    (ROOT/'results/stage7_track_information_report.md').write_text('\n'.join(lines)+'\n')
    print('Rendered post-hoc information report; no model inference or parameter changes')


if __name__=='__main__':main()
