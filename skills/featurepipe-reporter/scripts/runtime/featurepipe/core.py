import hashlib, json, re
from pathlib import Path

from .client import Client, BudgetExceeded
from .prompts import SYSTEM, TASKS

def sentences(text):
    return [x.strip() for x in re.findall(r'[^。！？!?\n]+(?:[。！？!?]+[”’」』）)\"]*)?|[。！？!?]+[”’」』）)\"]*',text) if x.strip()]

def parse_issues(text):
    text=re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    obj=json.loads(text)
    if not isinstance(obj,dict) or not isinstance(obj.get('issues'),list): raise ValueError('检查结果必须含issues数组')
    for issue in obj['issues']:
        if not isinstance(issue,dict) or not all(isinstance(issue.get(k),str) for k in ('problem','evidence')): raise ValueError('问题缺少problem/evidence')
    return obj['issues']

def run(case, output, client, rounds=5, min_chars=4000, max_chars=6000, resume=False, evaluate=False, progress=None):
    if not isinstance(case,dict): raise ValueError('输入必须是JSON对象')
    if not isinstance(case.get('title'),str) or not case['title'].strip(): raise ValueError('缺少标题')
    sources=case.get('materials')
    if not isinstance(sources,list) or not sources: raise ValueError('materials必须是非空数组')
    ids=[]
    for source in sources:
        if not isinstance(source,dict) or not all(isinstance(source.get(k),str) and source[k].strip() for k in ('id','text')): raise ValueError('素材必须包含id/text')
        ids.append(source['id'])
    if len(set(ids)) != len(ids): raise ValueError('素材ID重复')
    if not 0 <= rounds <= 10 or not 0 <= min_chars <= max_chars: raise ValueError('无效的轮次或字数范围')
    client.preflight()
    out=Path(output)
    identity={'case':case,'rounds':rounds,'min_chars':min_chars,'max_chars':max_chars,
              'mock':client.mock,'model':client.model,
              'base_url':client.base,'prompts':TASKS,'system':SYSTEM,'checkpoint_version':3,'evaluate':evaluate}
    signature=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if resume:
        manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('signature') != signature: raise ValueError('输入、模型或配置变化，不能复用检查点')
        if (out/'usage.json').exists():
            previous=json.loads((out/'usage.json').read_text(encoding='utf-8'))
            client.calls=previous['calls']; client.tokens=previous['reserved_tokens']; client.records=previous['records']
    else:
        out.mkdir(parents=True,exist_ok=False)
        (out/'manifest.json').write_text(json.dumps({'signature':signature,'version':1}),encoding='utf-8')
    context={'title':case['title'],'materials':sources}
    def save(name,value):
        temp=out/(name+'.tmp')
        temp.write_text(value,encoding='utf-8'); temp.replace(out/name)
    def save_usage():
        save('usage.json',json.dumps({'calls':client.calls,'reserved_tokens':client.tokens,'records':client.records,'actual_total_tokens':sum((r.get('usage') or {}).get('total_tokens',0) for r in client.records)},ensure_ascii=False,indent=2))
    def call(stage,data,name):
        fingerprint=hashlib.sha256(json.dumps({'stage':stage,'data':data},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        checkpoint=out/(name+'.checkpoint.json')
        if resume and checkpoint.exists():
            cached=json.loads(checkpoint.read_text(encoding='utf-8'))
            if cached['fingerprint'] != fingerprint: raise ValueError('检查点上下文不匹配：'+name)
            return cached['result']
        try:
            if progress: progress(stage,name,client.calls)
            result=client.call(stage,data)
            # Keep malformed structured responses for diagnosis; never cache them as completed.
            if stage in {'inspect','audit'}: save(name+'.response.txt',result)
            if stage=='inspect': parse_issues(result)
            if stage=='audit': parse_audit(result,sources)
            save(name,result)
            save(name+'.checkpoint.json',json.dumps({'fingerprint':fingerprint,'result':result},ensure_ascii=False))
            return result
        finally:
            save_usage()
    try:
        save('prompt-snapshot.json',json.dumps({'system':SYSTEM,'tasks':TASKS},ensure_ascii=False,indent=2))
        save('run-config.json',json.dumps({'model':client.model,'base_url':client.base,'rounds':rounds,'min_chars':min_chars,'max_chars':max_chars,'evaluate':evaluate,'mock':client.mock,'max_calls':client.max_calls,'max_reserved_tokens':client.max_tokens},ensure_ascii=False,indent=2))
        target={'min_chinese_chars':min_chars,'max_chinese_chars':max_chars}
        if evaluate:
            baseline=call('baseline',{**context,'length_target':target},'00-baseline.md')
        summary=call('summary',context,'01-summary.md')
        strategy=call('strategy',{**context,'summary':summary},'02-strategy.md')
        outline=call('outline',{**context,'summary':summary,'strategy':strategy},'03-outline.md')
        outline=call('outline_review',{**context,'outline':outline},'04-outline-reviewed.md')
        draft=''
        for attempt in range(2):
            draft=call('draft',{**context,'outline':outline,'length_target':target,'previous_draft':draft,'length_feedback':len(re.findall(r'[\u4e00-\u9fff]',draft))},f'05-draft-{attempt}.md')
            if min_chars <= len(re.findall(r'[\u4e00-\u9fff]',draft)) <= max_chars: break
        length_ok=min_chars <= len(re.findall(r'[\u4e00-\u9fff]',draft)) <= max_chars
        initial_draft=draft
        round_stats=[]
        for r in range(rounds):
            issues=[]
            for i,sentence in enumerate(sentences(draft)):
                raw=call('inspect',{**context,'article':draft,'sentence':sentence},f'r{r+1}-s{i+1}-inspection.json')
                issues.extend({**issue,'sentence_index':i,'sentence':sentence} for issue in parse_issues(raw))
            round_stats.append({'round':r+1,'sentences':len(sentences(draft)),'flagged_issues':len(issues)})
            save(f'r{r+1}-issues.json',json.dumps(issues,ensure_ascii=False,indent=2))
            for i,issue in enumerate(issues):
                suggestion=call('suggest',{**context,'article':draft,'issue':issue},f'r{r+1}-issue{i+1}-suggestion.md')
                draft=call('revise',{**context,'article':draft,'suggestion':suggestion},f'r{r+1}-issue{i+1}-revision.md')
            draft=call('polish',{**context,'article':draft},f'r{r+1}-polished.md')
        save('article.md',draft)
        if evaluate:
            for label,article in [('baseline',baseline),('initial',initial_draft),('final',draft)]:
                call('audit',{**context,'article':article},f'evaluation-{label}.json')
        save('report.json',json.dumps({'mock':client.mock,'initial_length_ok':length_ok,'final_chinese_chars':len(re.findall(r'[\u4e00-\u9fff]',draft)),'rounds':rounds,'publication_ready':False,'model':client.model,'base_url':client.base,'evaluation':('same-model-review-not-independent' if evaluate else None),'round_stats':round_stats,'final_length_ok':min_chars <= len(re.findall(r'[\u4e00-\u9fff]',draft)) <= max_chars},ensure_ascii=False,indent=2))
        return out
    finally:
        save('usage.json',json.dumps({'calls':client.calls,'reserved_tokens':client.tokens,'records':client.records,'actual_total_tokens':sum((r.get('usage') or {}).get('total_tokens',0) for r in client.records)},ensure_ascii=False,indent=2))


def parse_audit(text, sources):
    obj=json.loads(text)
    if not isinstance(obj,dict) or not isinstance(obj.get('findings'),list) or not isinstance(obj.get('assessment'),str):
        raise ValueError('审阅结果必须含findings数组和assessment文字')
    known={s['id'] for s in sources}
    for finding in obj['findings']:
        if not isinstance(finding,dict) or not all(isinstance(finding.get(k),str) for k in ('sentence','problem','evidence')):
            raise ValueError('审阅问题缺少原句、问题或证据')
        ids=finding.get('source_ids')
        if not isinstance(ids,list) or not all(isinstance(x,str) and x in known for x in ids):
            raise ValueError('审阅引用不存在的素材ID')
    return obj
