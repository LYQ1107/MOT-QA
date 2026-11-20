"""Manual notes after reading all 18 selected question/output/tool exchanges."""
from stage6_common import ROOT,read,write,sha,now


def main():
    notes={
        ('T1','061682ce31ac'):('缺乏事件支持；解释读错事实','工具只有5.6秒首次出现、20.2秒最后可见，没有消失或重现。模型把5.6秒同时当成消失和重现；最终A虽正确，不能由返回的事件列表支持。'),
        ('T1','128d74ab4e21'):('缺乏事件支持','20.8秒是首次出现，不是被记录的重现。返回没有消失前位置或可见间断，不能据此判断离开还是遮挡；最终A正确不等于工具推理成立。'),
        ('T1','1299999226de'):('一致（按冻结规则解释）','28.4秒消失、28.8秒重现和非贴边标志都准确引用；映射到A完全遮挡，与冻结规则对这些事实的解释一致。'),
        ('T1','0893a25082de'):('选项映射不符；事件时间有误','13.4秒消失确实存在，但19.8秒是last seen，第二次消失在20.0秒。两次消失均明确非贴边，模型却说两次都离开并选B，与冻结规则解释相反。'),
        ('T1','093589b84207'):('选项映射不符','6.0、16.4、20.2、25.2秒消失及非贴边事实引用准确；34.8秒却只是last seen。模型明确说away from the edge却选B离开，而A才是完全遮挡。'),
        ('T1','09ecc5ba1b9b'):('未给合法类别答案','14.4和15.0秒重现确实存在，但列表还有其他重现。问题是A/B的R/D判断，最终给Answer: 2，发生题型混淆；措辞与计数示范相同，严格解析失败。'),
        ('T-ph','061682ce31ac'):('无法核验：没有工具事实','唯一返回是[tool output omitted]。模型给出1.255/1.916秒和A，时刻不来自工具；虽答对，不能归因于工具事实。未检查这些时刻是否来自32帧。'),
        ('T-ph','093589b84207'):('无法核验：没有工具事实','返回仅为占位符；27.283/28.384秒及非贴边判断没有工具依据。最终A正确不能证明引用了轨迹。'),
        ('T-ph','09ecc5ba1b9b'):('无法核验：没有工具事实','返回仅为占位符；模型给出0.0/1.033秒及完全遮挡解释，没有工具事件支持；最终B正确。'),
        ('T-ph','0893a25082de'):('无法核验：没有工具事实','只有占位符，最终直接Answer: B，没有可核查的事件引用，答案错误。'),
        ('T-ph','13357e2b139e'):('无法核验：没有工具事实','只有占位符，最终直接Answer: B，没有可核查的事件引用，答案错误。'),
        ('T-ph','13b4b9c339ff'):('无法核验：没有工具事实','只有占位符，却声称11.0秒重现；该时刻没有工具依据。最终B错误；未据此判断画面本身是否提供该时刻。'),
        ('T-sh','093589b84207'):('与打乱事实一致','7.2和34.4秒消失、非贴边均与实际收到的打乱列表一致，A也符合冻结规则解释。但输入事实已打乱，标签答对不能证明真实轨迹被利用。'),
        ('T-sh','1299999226de'):('没有相关消失事件，结论缺乏支持','打乱列表只有首次出现0.0秒、最后可见33.4秒，没有被记录的间断。模型据此声称持续可见、不离开，再选A完全遮挡；没有消失前/重现事件来支持该类别。'),
        ('T-sh','13b4b9c339ff'):('边缘及时间顺序均读错','实际返回28.2秒消失且yes(left)，13.6秒是更早的首次出现，之后没有重现。模型改说away并把13.6秒当作28.2秒之后的重现；A虽答对，解释与工具事实不符。'),
        ('T-sh','061682ce31ac'):('选项映射不符','准确引用10.0、14.8、21.2、23.2、29.6秒等非贴边消失，但把away映射为B离开，与冻结规则解释相反；真实标签A。'),
        ('T-sh','0893a25082de'):('时刻一致，判断依据超出返回事实','13.4秒消失、26.4秒重现引用准确；工具标志非贴边。模型自行用重现间隔太长排除完全遮挡并选B，这个时间阈值不在冻结规则中，最终判断不符合其解释。'),
        ('T-sh','09ecc5ba1b9b'):('未给合法类别答案','15.6和28.4秒重现是真实返回的两项，但打乱列表共有5次重现。R/D题最终给Answer: 2，题型混淆并解析失败；不是有效类别推断。')}
    index=read(ROOT/'results/stage7_RD_interactions.json');records=[]
    assert set(notes)=={(r['condition'],r['qa_id']) for r in index['records']}
    for row in index['records']:
        assert sha(row['record_path'])==row['record_sha256']
        status,note=notes[row['condition'],row['qa_id']]
        records.append(dict(condition=row['condition'],qa_id=row['qa_id'],correct=row['correct'],
            facts_consistency=status,note=note,record_path=row['record_path'],record_sha256=row['record_sha256']))
    summary=('真实T1的六个固定样例中，一例准确使用时间和边缘事实并与冻结规则映射一致；两例虽然标签正确，却没有对应消失事件支持；两例非贴边事实被映射成离开；一例把R/D问题回答成计数。'
        '占位对照没有工具事实，却仍生成具体时刻并能答对部分题；不能把这些解释计为轨迹引用。打乱对照可见准确引用错误时间轴、读反边缘标志、时间倒置和题型混淆。'
        '这些是固定小样本的定性描述，不外推为总体忠实性比例。非贴边到完全遮挡的判断只按冻结规则代理解释，不等于验证真实视频中的物理遮挡。')
    write(ROOT/'results/stage7_RD_manual_review.json',dict(created_at=now(),posthoc=True,model_requests=0,
        selection=index['selection'],reviewed=len(records),scope='Question/options, every actual tool reply and final output of all18 fixed examples; no look was used, no new video or model inference.',
        summary=summary,records=records))
    print('Manually reviewed all',len(records),'fixed interactions; no predictions changed')


if __name__=='__main__':main()
