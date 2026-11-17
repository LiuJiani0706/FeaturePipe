"""Export a Chinese reading report from completed local experiment artifacts."""
import argparse
import json
from pathlib import Path
import hashlib
from datetime import datetime, timedelta, timezone


def reported_cost(usage):
    rates=usage['cost_estimate']['rates_per_million_tokens']
    total=0.0
    for client in usage['clients'].values():
        for record in client['records']:
            item=record.get('usage')
            rate=rates.get(record.get('model'))
            if not item or not rate:continue
            prompt=item.get('prompt_tokens',0);completion=item.get('completion_tokens',0)
            hit=item.get('prompt_cache_hit_tokens',(item.get('prompt_tokens_details') or {}).get('cached_tokens',0))
            hit=max(0,min(prompt,hit if isinstance(hit,int) else 0))
            total+=((prompt-hit)*rate['input']+hit*rate['cached_input']+completion*rate['output'])/1000000
    return total


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    args=parser.parse_args();root=Path(args.run)
    load=lambda name:json.loads((root/name).read_text(encoding='utf-8'))
    result=load('本轮结果.json');usage=load('usage.json');metrics=load('中文客观指标.json');mapping=load('匿名评价映射.json');assessment=load('中文匿名对照评价.json')
    known=reported_cost(usage);conservative=usage['cost_estimate']['spent_rmb_estimate']
    labels={key:value for key,value in mapping.items()}
    lines=['真实采访提示词对照与定点修订结果','',
           '本次使用五份真实采访的正文文本；未向模型提供已发表成稿。DOCX内嵌照片未输入模型，结论只针对本次文本输入。',
           '当前论文提示词是英文附录的中文回译，不是找回当时的中文原始字符串。',
           '历史初稿与论文首次初稿使用相同前序上下文、素材和生成配置；修订稿增加了编辑干预，不能将其全部变化归因于提示词。','',
           '执行结果',result['状态'],
           f"已有编辑汇总{result['已有资深编辑意见数']}份，实际应用{result['已应用修改数']}条；完整论文五轮未完成。",
           '用户要求当前审查到此、进入下一步；因此未补齐剩余逐句审查。已做顺序修订、清理及预算内评价。','',
           '篇幅与引号片段检测']
    for label,values in metrics.items():
        lines.append(f"{label}：{values['chinese_chars']}个中文字符；引号片段{values['marked_quotes']}处；允许句末标点变化后仍无法逐字匹配原文{values['unmatched_after_end_punctuation_adjustment']}处。")
    lines.extend(['这些数字不是事实错误数：引号也可用于概念或合法编辑。子串存在也不证明说话人正确。','', '费用记录',
                  f"两模型累计估算预算：{usage['cost_estimate']['maximum_rmb_estimate']:.2f}元。",
                  f"已返回usage部分，按公开价格估算约{known:.4f}元；包含未知请求和中断安全预留后的保守累计记录约{conservative:.4f}元。",
                  f"供应商已返回用量合计{usage['actual_total_tokens']} token；这不包含无法取得用量的中断请求。",
                  '估算不是实际扣费账单；安全预留不能称为已确认消费。','', '匿名模型评价'])
    for item in assessment['逐稿评价']:
        anonymous=item['匿名编号'];lines.extend(['',labels.get(anonymous,anonymous)+'（'+anonymous+'）'])
        for gate in item.get('硬门槛',[]):
            lines.append(gate.get('项目','项目')+'：'+gate.get('状态','待核实')+'。'+gate.get('理由',''))
        for score in item.get('主观评价',[]):
            value=score.get('评分');lines.append(score.get('维度','维度')+'：'+('未评价' if value is None else str(value)+'/5')+'。'+score.get('理由',''))
        for finding in item.get('最重要的剩余问题',[]):lines.append('待处理：'+str(finding))
    lines.extend(['','对照结论',assessment['对照结论'],'', '限制',
                  '这是一个案例、一次采样，且没有人类盲评。评分来自模型，不是论文原用户研究结果。',
                  '没有发现问题不等于文章已核实；本文不据模型分数宣称可直接发表。',
                  '初稿篇幅不同、中文回译、平台和接口适配，以及后续修订步骤均需在解读时考虑。'])
    (root/'结果说明中文版.txt').write_text('\n'.join(lines),encoding='utf-8')
    saved=[]
    for path in sorted(root.glob('C-*.txt')):
        if '.raw.' in path.name:continue
        saved.append({'文件':path.name,'保存时间':datetime.fromtimestamp(path.stat().st_mtime,timezone(timedelta(hours=8))).isoformat(),
                      '内容SHA256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (root/'实际保存记录.json').write_text(json.dumps({'说明':'这是文件实际保存时间；模型自行生成的修订记录时间戳不作为实际执行时间。','记录':saved},ensure_ascii=False,indent=2),encoding='utf-8')
    print('已导出：'+str(root/'结果说明中文版.txt'))


if __name__=='__main__':main()
