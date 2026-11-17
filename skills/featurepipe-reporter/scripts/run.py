#!/usr/bin/env python3
"""Relocatable entry point. Local tools by default; paid mode needs an explicit budget."""
import argparse
import json
import math
from pathlib import Path
import runpy
import sys


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts' / 'runtime'))


def outside_skill(value):
    path = Path(value).expanduser().resolve()
    if path == SKILL or SKILL in path.parents:
        raise argparse.ArgumentTypeError('输出必须位于技能目录之外，避免私有材料进入技能包')
    return str(path)


def budget(value):
    try:
        amount = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError('预算必须是有限正数') from None
    if not math.isfinite(amount) or amount <= 0:
        raise argparse.ArgumentTypeError('预算必须是有限正数')
    return amount


def invoke(module=None, script=None, arguments=()):
    old = sys.argv
    try:
        sys.argv = [module or str(script), *map(str, arguments)]
        if module:
            runpy.run_module(module, run_name='__main__')
        else:
            runpy.run_path(str(script), run_name='__main__')
    finally:
        sys.argv = old


def main():
    parser = argparse.ArgumentParser(description='FeaturePipe 采访写作：本地工具与显式预算的论文实验')
    commands = parser.add_subparsers(dest='command', required=True)
    prompts = commands.add_parser('prompts', help='按阶段读取中文提示词')
    prompts.add_argument('--stage', help='省略时列出可选阶段')
    importer = commands.add_parser('import', help='导入明确选择的 DOCX 正文')
    importer.add_argument('--file', action='append', required=True)
    importer.add_argument('--title', required=True)
    importer.add_argument('--output', type=outside_skill, required=True)
    importer.add_argument('--alias-map')
    inspect = commands.add_parser('inspect', help='离线检查引语字面出处，不验证全部事实')
    inspect.add_argument('--input', required=True)
    inspect.add_argument('--article', required=True)
    inspect.add_argument('--output', type=outside_skill, required=True)
    demo = commands.add_parser('demo', help='固定虚构响应的离线演示，不调用 API')
    demo.add_argument('--output', type=outside_skill, required=True)
    paper = commands.add_parser('paper', help='收费接口论文实验，含初稿提示词对照')
    paper.add_argument('--input', required=True)
    paper.add_argument('--output', type=outside_skill, required=True)
    paper.add_argument('--env-file', required=True)
    paper.add_argument('--max-rmb', type=budget, required=True)
    paper.add_argument('--rounds', type=int, choices=range(1, 6), default=1)
    paper.add_argument('--workers', type=int, choices=range(1, 17), default=4)
    paper.add_argument('--writer', default='deepseek-ai/DeepSeek-V4-Pro')
    paper.add_argument('--reviewer', default='zai-org/GLM-5.3')
    paper.add_argument('--max-calls', type=int, default=3000)
    paper.add_argument('--max-tokens', type=int, default=120000000)
    paper.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.command == 'prompts':
        data = json.loads((SKILL / 'references' / 'prompt-versions.json').read_text(encoding='utf-8'))['versions']
        if not args.stage:
            print('\n'.join(data))
        elif args.stage not in data:
            parser.error('不存在的提示词阶段：' + args.stage)
        else:
            value = data[args.stage]
            print('\n\n'.join(value) if isinstance(value, list) else value)
    elif args.command == 'import':
        argv = ['--title', args.title, '--output', args.output]
        for item in args.file:
            argv.extend(['--file', item])
        if args.alias_map:
            argv.extend(['--alias-map', args.alias_map])
        invoke(script=SKILL / 'scripts' / 'helpers' / 'import_interviews.py', arguments=argv)
    elif args.command == 'inspect':
        from featurepipe.evidence import quote_audit
        from featurepipe.paper_experiment import body_only
        case = json.loads(Path(args.input).read_text(encoding='utf-8'))
        materials = case.get('materials')
        if not isinstance(materials, list) or not materials:
            parser.error('输入必须包含非空 materials 数组')
        ids = set()
        for item in materials:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip() or not isinstance(item.get('text'), str) or not item['text'].strip() or item['id'] in ids:
                parser.error('来源必须有唯一非空 id 和非空 text')
            ids.add(item['id'])
        result = quote_audit(body_only(Path(args.article).read_text(encoding='utf-8')), materials)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with output.open('x', encoding='utf-8') as handle:
            output.chmod(0o600)
            json.dump(result, handle, ensure_ascii=False, indent=2)
        print('已保存引语检查；字面匹配不证明说话人归属或全文真实：' + str(output))
    elif args.command == 'demo':
        invoke(module='featurepipe', arguments=[
            '--input', SKILL / 'assets' / 'mock-case.json', '--output', args.output,
            '--mock', '--rounds', '1', '--env-file', SKILL / 'assets' / 'no-env',
        ])
    elif args.command == 'paper':
        if args.max_calls < 1 or args.max_tokens < 1:
            parser.error('调用与 token 估算上限必须为正数')
        # Do not inherit an unrelated working directory's .env or silently use old task budgets.
        if not Path(args.env_file).is_file():
            parser.error('指定的本地配置文件不存在')
        argv = ['--input', args.input, '--output', args.output, '--env-file', args.env_file,
                '--prompts', SKILL / 'references' / 'prompt-versions.json',
                '--max-rmb', args.max_rmb, '--rounds', args.rounds, '--workers', args.workers,
                '--writer', args.writer, '--reviewer', args.reviewer,
                '--max-calls', args.max_calls, '--max-tokens', args.max_tokens]
        if args.resume:
            argv.append('--resume')
        invoke(module='featurepipe.paper_experiment', arguments=argv)


if __name__ == '__main__':
    main()
