"""Continue from saved editorial comments, without restarting sentence inspection."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from .client import BudgetExceeded, Client
from .config import load_env
from .evidence import quote_audit
from .paper_experiment import ADAPTER, RATES, Store, body_only, count, no_revision
from .spend import SpendGuard


def tagged_article(text):
    matches=re.findall(r'<正文>(.*?)</正文>',text,re.S)
    if len(matches)!=1 or not matches[0].strip():
        raise ValueError('请把唯一的完整正文放入<正文>与</正文>之间')
    return body_only(matches[0])


def object_result(text, expected_labels=None):
    obj=json.loads(text)
    if not isinstance(obj,dict):raise ValueError('评价结果必须是JSON对象')
    if not isinstance(obj.get('逐稿评价'),list) or not isinstance(obj.get('对照结论'),str):
        raise ValueError('评价结果必须含逐稿评价数组和对照结论文字')
    rows=obj['逐稿评价']
    labels=[]
    if not rows:raise ValueError('逐稿评价不得为空')
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('匿名编号'),str):raise ValueError('每份评价必须标明匿名编号')
        labels.append(row['匿名编号'])
        gates=row.get('硬门槛');scores=row.get('主观评价')
        if not isinstance(gates,list) or not gates or not isinstance(scores,list) or not scores:
            raise ValueError('每份评价必须有硬门槛及主观评价')
        for gate in gates:
            if not isinstance(gate,dict) or gate.get('状态') not in {'通过','失败','待核实'}:raise ValueError('硬门槛状态必须为通过、失败或待核实')
        for score in scores:
            value=score.get('评分') if isinstance(score,dict) else False
            if value is not None and (type(value) is not int or not 1<=value<=5):raise ValueError('评分必须为1至5的整数或null')
    if len(set(labels))!=len(labels):raise ValueError('匿名稿件评价重复')
    if expected_labels is not None and set(labels)!=set(expected_labels):raise ValueError('匿名稿件评价不完整或有多余编号')
    return obj


def run(args):
    load_env(args.env_file)
    folder=Path(args.run)
    config=json.loads((folder/'run-config.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    signature=hashlib.sha256(json.dumps(config,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if signature!=manifest['signature']:raise ValueError('原运行配置完整性校验失败')
    case=config['case'];p=config['registry']['versions']
    guard=SpendGuard(args.max_rmb,RATES)
    prompts={key:'' for key in ('revise','cleanup','draft','audit')}
    writer=Client(model=config['writer'],thinking=True,thinking_budget=4096,prompts=prompts,
                  output_limits={'revise':32768,'cleanup':16384,'draft':16384},timeout=600,
                  max_calls=3000,max_tokens=120000000,spend_guard=guard,protected_spend=min(5,args.max_rmb/5))
    reviewer=Client(model=config['reviewer'],thinking=True,thinking_budget=8192,prompts=prompts,
                    output_limits={'audit':16384},timeout=600,max_calls=30,max_tokens=2000000,spend_guard=guard)
    writer.preflight();reviewer.preflight()
    store=Store(folder,signature,True,{'writer':writer,'reviewer':reviewer})
    adjustment=folder/'中断费用保守预留.json'
    if not adjustment.exists():
        previous=json.loads((folder/'usage.json').read_text())['cost_estimate']
        # Store restores saved in-flight reservations as spent. Extra buffer covers a
        # reservation beginning after the last durable snapshot before termination.
        guard.spent+=args.interruption_buffer
        store.save(adjustment.name,{'已返回用量的估算费用':previous['spent_rmb_estimate'],
                                   '中断时在途预留转为已占用':previous.get('inflight_rmb_estimate',0),
                                   '额外中断安全预留':args.interruption_buffer,
                                   '说明':'未知请求不记为免费；这不是服务商实际账单。后续运行复用此调整，不重复加入。'})
        store.usage()
    store.save('续跑配置.json',{'累计人民币估算上限':args.max_rmb,'执行范围':'使用已有编辑意见顺序修订、五项清理、必要的字数修复及匿名评价；不补做尚未完成的逐句检查',
                              '论文完整五轮已完成':False,'预算基于原运行累计用量':'是','清理适配版本':2,
                              '清理输入':'仅正文，历史修订记录独立保存；说明最多150字，正文仅输出一份'})
    transcripts='\n\n'.join(f"[{m['id']}] {m.get('label','')}\n{m['text']}" for m in case['materials'])
    sources='[采访原文]\n'+transcripts
    pieces=json.loads((folder/'r1-sentences.json').read_text())
    comments=[]
    for file in sorted(folder.glob('r1-s*-senior.txt'),key=lambda f:int(re.search(r'-s(\d+)-',f.name).group(1))):
        index=int(re.search(r'-s(\d+)-',file.name).group(1))-1
        comments.append({'index':index,'sentence':pieces[index],'comment':file.read_text()})
    store.save('本轮采用的已有意见.json',comments)
    draft=(folder/'B-paper-D0.txt').read_text()
    applied=[];skipped=[];budget_stop=None
    try:
        try:
            for item in comments:
                if no_revision(item['comment']):
                    skipped.append({'index':item['index'],'reason':'无需修改'});continue
                occurrences=body_only(draft).count(item['sentence'])
                if occurrences!=1:
                    skipped.append({'index':item['index'],'reason':'原句已变化或不唯一','occurrences':occurrences});continue
                request=p['revision']+'\n[原始片段]\n'+item['sentence']+'\n[编辑意见]\n'+item['comment']+'\n[当前全文]\n'+draft
                messages=[{'role':'system','content':p['revision_role']+'\n'+ADAPTER+'\n'+sources},{'role':'user','content':request}]
                draft=store.call('writer','revise',messages,f'C-s{item["index"]+1}-revision.txt')
                applied.append(item['index'])
                store.save('C-当前修订正文.txt',body_only(draft))
                store.save('C-修订进度.json',{'已应用':applied,'已跳过':skipped,'当前字数':count(draft)})
            history=[{'role':'system','content':p['cleanup_role']+'\n'+ADAPTER+'\n'+sources},{'role':'user','content':'[稿件]\n'+body_only(draft)}]
            for index,prompt in enumerate(p['cleanup'],1):
                prompt+='\n程序正文边界适配：修改说明最多150字，只输出一份完整修订正文，不重复原稿，不输出修订记录或思考过程。把最终完整文章放入<正文>与</正文>之间；简要修改说明放在标签外。'
                messages=history+[{'role':'user','content':prompt}]
                raw=store.call('writer','cleanup',messages,f'C-cleanup-body-v2-{index}.txt',tagged_article)
                draft=tagged_article(raw)
                history=messages+[{'role':'assistant','content':raw}]
                store.save(f'C-清理{index}后正文.txt',draft)
            for attempt in range(2):
                if 4000<=count(draft)<=6000:break
                prompt=f'程序测得当前正文{count(draft)}个中文字符。请在严格忠于原始采访、不添加场景、心理、动作或引语的前提下，调整至4000—6000个中文字符。增加有原文依据的人物经历与差异，避免重复凑字数。保留已修正问题。把完整正文放在<正文>与</正文>之间。\n'+p['draft']+'\n[当前正文]\n'+body_only(draft)
                raw=store.call('writer','draft',[{'role':'system','content':p['writer_role']+'\n'+ADAPTER+'\n'+sources},{'role':'user','content':prompt}],f'C-length-repair-{attempt}.txt',tagged_article)
                draft=tagged_article(raw)
        except BudgetExceeded as exc:
            budget_stop=str(exc)
        draft=body_only(draft)
        store.save('C-修订稿.txt',draft)
        artifacts={'历史提示词初稿':body_only((folder/'A-legacy-drafting-prompt.txt').read_text()),
                   '论文提示词首次初稿':body_only((folder/'B-paper-D0-first.txt').read_text()),'已有意见修订稿':draft}
        metrics={key:quote_audit(value,case['materials']) for key,value in artifacts.items()}
        store.save('中文客观指标.json',metrics)
        ordered=sorted(artifacts,key=lambda key:hashlib.sha256(artifacts[key].encode()).hexdigest())
        labels={f'稿件{index+1}':key for index,key in enumerate(ordered)}
        store.save('匿名评价映射.json',labels)
        standards=json.loads(Path(args.criteria).read_text())
        reviews={label:{'正文':artifacts[key],'程序统计':metrics[key]} for label,key in labels.items()}
        prompt='''请依据下面的中文评价标准与采访文本，分别评价匿名稿件，再作对照。你不知道提示词版本，不要猜测。程序提供的引语匹配只是线索，不等于错引计数；不得拿它直接当成事实错误率。未提供已发表人工成稿，不评价与原人工文章的一致性。不要把模型审阅冒充人类盲评。事实、引语、人物归属、时间、隐私和篇幅逐项给通过、失败或待核实；每条判断举出正文原句与具体素材编号。仅凭文字好听不能判事实通过。三个主观维度可按标准给1至5分，每分必须给原文例证；无法判断填null。最后明确局限，不保证新版更好。
只输出JSON对象：{"逐稿评价":[{"匿名编号":"稿件1","硬门槛":[{"项目":"来源支持","状态":"待核实","理由":"具体理由","原句":"稿件连续原文","素材编号":["S1"]}],"主观评价":[{"维度":"叙事组织","评分":3,"理由":"理由和实际例子"}],"最重要的剩余问题":["具体问题"]}],"对照结论":"限于这次案例的比较","局限":"这是模型审阅，不是人类实验或普遍能力排名"}。
'''+sources+'\n[评价标准]\n'+json.dumps(standards,ensure_ascii=False)+'\n[匿名稿件]\n'+json.dumps(reviews,ensure_ascii=False)
        assessment=store.call('reviewer','audit',[{'role':'system','content':'你是独立的中文新闻编辑评审。以原始采访为事实边界，区分文本证据、推断、读感与待核实意见。'},{'role':'user','content':prompt}],'中文匿名对照评价.json',lambda text:object_result(text,labels))
        store.save('本轮结果.json',{'状态':'已完成预算内修订与评价' if budget_stop is None else '达到写作预算保护线，已保存稿件与评价',
                                 '预算停止原因':budget_stop,'累计人民币估算上限':args.max_rmb,'完整论文五轮已完成':False,
                                 '已有资深编辑意见数':len(comments),'已应用修改数':len(applied),'跳过意见':skipped,
                                 '修订稿中文字符数':count(draft),'修订稿字数达标':4000<=count(draft)<=6000,
                                 '比较边界':'历史与论文首次初稿是提示词对照；修订稿增加了有限编辑干预，不能把全部差异归因于提示词',
                                 '尚未实施':'剩余逐句检查、完整五轮、第六轮论文最终审阅、人类盲评',
                                 '模型评价属于审阅建议':'是','可直接发表':'未确认'})
        return folder
    finally:
        store.usage()
        store.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--env-file',default='.env')
    parser.add_argument('--criteria',default='evaluation/评价标准.json')
    parser.add_argument('--max-rmb',type=float,default=50)
    parser.add_argument('--interruption-buffer',type=float,default=3)
    args=parser.parse_args()
    if args.interruption_buffer<0:parser.error('安全预留不能为负数')
    try:print('本轮修订与评价已保存：'+str(run(args)),flush=True)
    except Exception as exc:parser.exit(1,f'续跑未完成：{type(exc).__name__}: {exc}\n')


if __name__=='__main__':main()
