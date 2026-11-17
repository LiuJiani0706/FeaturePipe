"""Import explicitly selected DOCX interviews; never import a finished article automatically."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NS='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def docx_text(path):
    with ZipFile(path) as archive:
        tree=ET.fromstring(archive.read('word/document.xml'))
        media=sum(name.startswith('word/media/') for name in archive.namelist())
    def content(node):
        if node.tag in {NS+'del',NS+'moveFrom'}:return ''
        if node.tag==NS+'t':return node.text or ''
        if node.tag==NS+'br':return '\n'
        if node.tag==NS+'tab':return '\t'
        return ''.join(content(child) for child in node)
    body=tree.find(NS+'body')
    if body is None:raise ValueError('DOCX缺少正文')
    def paragraphs(node):
        if node.tag in {NS+'del',NS+'moveFrom'}:return
        if node.tag==NS+'p':
            yield content(node)
            return
        for child in node:yield from paragraphs(child)
    return '\n'.join(paragraphs(body)),media


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',action='append',required=True,help='明确选择的采访DOCX，可重复使用；不要选择已发表正文')
    parser.add_argument('--title',required=True)
    parser.add_argument('--output',default='runs/private-inputs/case.json')
    parser.add_argument('--alias-map',help='可选JSON对象，明确指定真名到化名的替换')
    args=parser.parse_args()
    aliases=json.loads(Path(args.alias_map).read_text(encoding='utf-8')) if args.alias_map else {}
    if not isinstance(aliases,dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in aliases.items()):
        parser.error('化名映射必须是非空字符串到非空字符串的对象')
    materials=[];manifest=[]
    if len({str(Path(value).resolve()) for value in args.file})!=len(args.file):parser.error('采访文件重复')
    for index,value in enumerate(args.file,1):
        path=Path(value)
        if path.name.startswith('~$') or path.suffix.lower()!='.docx':parser.error('仅支持明确选择的非临时DOCX采访文件')
        text,media=docx_text(path);label=path.stem
        for old,new in aliases.items():text=text.replace(old,new);label=label.replace(old,new)
        if not text.strip():parser.error('采访正文为空：'+path.name)
        materials.append({'id':f'S{index}','label':label,'text':text})
        manifest.append({'id':f'S{index}','source_path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'embedded_media_not_imported':media})
    output=Path(args.output)
    if output.exists():parser.error('输出文件已存在，请选择新文件名')
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    output.write_text(json.dumps({'title':args.title,'materials':materials,'input_scope':'DOCX正文文字，内嵌图像未输入模型'},ensure_ascii=False,indent=2),encoding='utf-8')
    output.chmod(0o600)
    provenance=output.with_name(output.stem+'-source-manifest.json')
    provenance.write_text(json.dumps({'sources':manifest,'alias_replacement_applied':bool(aliases)},ensure_ascii=False,indent=2),encoding='utf-8');provenance.chmod(0o600)
    print(f'已导入{len(materials)}份采访；原文件未修改。输出：{output}')


if __name__=='__main__':main()
