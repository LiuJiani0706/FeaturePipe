import argparse, json
from .core import Client, run
from .config import load_env

def main():
    p=argparse.ArgumentParser(description="FeaturePipe independent reproduction")
    p.add_argument('--input',required=True); p.add_argument('--output',required=True)
    p.add_argument('--mock',action='store_true'); p.add_argument('--rounds',type=int,default=5)
    p.add_argument('--max-calls',type=int,default=250); p.add_argument('--max-tokens',type=int,default=500000)
    p.add_argument('--resume',action='store_true',help='从相同输入、模型和配置的输出目录继续；预算按累计用量计算')
    p.add_argument('--env-file',default='.env')
    p.add_argument('--evaluate',action='store_true',help='增加直接写作对照及同模型审阅；额外4次调用')
    p.add_argument('--min-chars',type=int,default=4000)
    p.add_argument('--max-chars',type=int,default=6000)
    args=p.parse_args()
    if not 0 <= args.rounds <= 10: p.error('rounds必须在0至10之间')
    if args.max_calls < 1 or args.max_tokens < 1: p.error('预算必须为正数')
    try:
        load_env(args.env_file)
        with open(args.input,encoding='utf-8') as f: case=json.load(f)
        path=run(case,args.output,Client(args.mock,args.max_calls,args.max_tokens),args.rounds,min_chars=args.min_chars,max_chars=args.max_chars,resume=args.resume,evaluate=args.evaluate,progress=lambda stage,name,calls: print(f'[{calls+1}] {stage} → {name}',flush=True))
    except Exception as e:
        p.exit(1,f'运行失败：{type(e).__name__}: {e}\n')
    print(f'已保存至 {path}；发布前需人工核查。')

if __name__=='__main__': main()
