"""Import supplied research prompts into an ignored, private experiment registry."""
import hashlib
import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


def plain(text):
    for _ in range(8):
        text = re.sub(r'\\(?:textit|textbf|texttt|emph)\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:begin|end)\{enumerate\}', '', text)
    text = text.replace(r'\item', '\n- ').replace(r'\_', '_').replace(r'\&', '&')
    return re.sub(r'[ \t]+', ' ', re.sub(r'\s*\n\s*', '\n', text)).strip()


def extract(tex, legacy):
    blocks = re.findall(r'\\begin\{quote\}\\small(.*?)\\end\{quote\}', tex, re.S)
    quoted = lambda i: [plain(x) for x in re.findall(r"``(.*?)''", blocks[i], re.S)]
    if len(blocks) != 16 or len(quoted(15)) != 5:
        raise ValueError('附录结构发生变化，请检查模板提取位置')
    start = legacy.index('你是一位经验丰富的资深新闻记者，刚刚完成了一项关于')
    end = legacy.index('你是一位经验丰富的资深编辑', start)
    return {
        'writer_role': quoted(0)[0], 'summary': quoted(1)[0],
        'meta': quoted(2)[0], 'meta_retry': quoted(2)[1], 'outline': quoted(3)[0],
        'outline_inspect': quoted(4)[0], 'outline_repair': quoted(5)[0],
        'draft': quoted(6)[0], 'split': quoted(7)[0], 'editor_role': quoted(8)[0],
        'dimensions': plain(blocks[10]), 'senior': quoted(11)[0],
        'revision_role': quoted(12)[0], 'revision': quoted(13)[0],
        'cleanup_role': quoted(14)[0], 'cleanup': quoted(15),
        'legacy_draft': legacy[start:end].strip(),
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--appendix',required=True,help='论文附录LaTeX文件')
    parser.add_argument('--legacy',required=True,help='历史中文提示词DOCX文件')
    parser.add_argument('--output',default='runs/private-inputs/prompt-versions.json')
    args=parser.parse_args()
    appendix=Path(args.appendix)
    old=Path(args.legacy)
    with ZipFile(old) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    legacy='\n'.join(''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in tree.findall('.//w:p',ns))
    obj={'versions':extract(appendix.read_text(),legacy),
         'provenance':{'paper_path':str(appendix),'paper_sha256':hashlib.sha256(appendix.read_bytes()).hexdigest(),'legacy_path':str(old),'legacy_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
          'paper_language':'published appendix English translation of Chinese runtime prompts; not recovered original Chinese strings',
          'legacy_scope':'one complete drafting turn from historical working prompt document; topic placeholder substituted at runtime',
          'transformations':['LaTeX formatting removed; text and enumeration preserved','runtime placeholders filled from private inputs','segmentation output serialized as JSON for parsing','Chinese output instruction added as an explicit runtime adapter']}}
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');out.chmod(0o600)
    print('已提取论文附录模板、5项清理提示及旧版写作提示；保存至Git忽略的实验输入目录。')


if __name__=='__main__':main()
