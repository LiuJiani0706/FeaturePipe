"""Build a self-contained Skill from public source; never read credentials or runs."""
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile


AUTHORED = {
    'SKILL.md', 'agents/openai.yaml', 'scripts/run.py',
    'references/paper-protocol.md', 'references/configuration.md', 'references/attribution.md',
}


def public_skill_files(skill):
    manifest = json.loads((skill / 'runtime-manifest.json').read_text(encoding='utf-8'))
    return AUTHORED | {'runtime-manifest.json'} | {item['target'] for item in manifest['files']}


def main():
    root = Path(__file__).resolve().parents[1]
    skill = root / 'skills' / 'featurepipe-reporter'
    copies = {
        'scripts/import_interviews.py': 'scripts/helpers/import_interviews.py',
        'prompt_sets/paper-and-legacy-zh.json': 'references/prompt-versions.json',
        'evaluation/评价标准.json': 'references/评价标准.json',
        'evaluation/论文访谈评价指南中文版.txt': 'references/论文访谈评价指南中文版.txt',
        'examples/case.json': 'assets/mock-case.json',
        'examples/borrow-room.json': 'assets/interview-example.json',
        'LICENSE': 'LICENSE',
    }
    for path in sorted((root / 'featurepipe').glob('*.py')):
        copies[path.relative_to(root).as_posix()] = 'scripts/runtime/featurepipe/' + path.name
    entries = []
    for source, target in copies.items():
        content = (root / source).read_bytes()
        path = skill / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        entries.append({'source': source, 'target': target, 'sha256': hashlib.sha256(content).hexdigest()})
    (skill / 'runtime-manifest.json').write_text(json.dumps({
        'origin': 'featurepipe independent reproduction', 'files': entries,
        'contains_private_inputs': False,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Remove generated interpreter caches from the distributed working copy too.
    for cache in skill.rglob('__pycache__'):
        shutil.rmtree(cache)
    output = root / 'release' / 'featurepipe-reporter.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for relative in sorted(public_skill_files(skill)):
            archive.write(skill / relative, 'featurepipe-reporter/' + relative)
    print('已生成独立 Skill：' + str(output))


if __name__ == '__main__':
    main()
