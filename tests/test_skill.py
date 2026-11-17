"""Skill behavior at its portable CLI boundary; no paid API calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'featurepipe-reporter'


class SkillTests(unittest.TestCase):
    def call(self, runner, *args, cwd):
        env = dict(os.environ, FEATUREPIPE_API_KEY='', DEEPSEEK_API_KEY='',
                   FEATUREPIPE_BASE_URL='https://invalid.local', PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable, str(runner), *map(str, args)],
                              cwd=cwd, env=env, text=True, capture_output=True, timeout=30)

    def test_portable_archive_and_offline_demo(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            bundle = work / 'skill.zip'
            with ZipFile(bundle, 'w') as archive:
                for file in SKILL.rglob('*'):
                    if file.is_file() and '__pycache__' not in file.parts:
                        archive.write(file, 'featurepipe-reporter/' + file.relative_to(SKILL).as_posix())
            with ZipFile(bundle) as archive:
                archive.extractall(work / 'unpacked')
            runner = work / 'unpacked' / 'featurepipe-reporter' / 'scripts' / 'run.py'
            prompt = self.call(runner, 'prompts', '--stage', 'summary', cwd=work)
            self.assertEqual(prompt.returncode, 0, prompt.stderr)
            self.assertIn('采访', prompt.stdout)
            result = self.call(runner, 'demo', '--output', work / 'demo', cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((work / 'demo' / 'article.md').is_file())

    def test_paid_mode_requires_new_explicit_finite_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = SKILL / 'scripts' / 'run.py'
            arguments = ['paper', '--input', 'missing.json', '--output', Path(folder) / 'run',
                         '--env-file', 'missing.env']
            for extra in [[], ['--max-rmb', 'nan'], ['--max-rmb', '-1'], ['--max-rmb', 'inf']]:
                with self.subTest(extra=extra):
                    result = self.call(runner, *arguments, *extra, cwd=folder)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('max-rmb', result.stderr)
                    self.assertFalse((Path(folder) / 'run').exists())

    def test_outputs_cannot_enter_shareable_skill(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.call(SKILL / 'scripts' / 'run.py', 'demo', '--output',
                               SKILL / 'assets' / 'private-result', cwd=folder)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('技能目录之外', result.stderr)
            self.assertFalse((SKILL / 'assets' / 'private-result').exists())

    def test_import_aliases_and_provenance_stay_outside_skill(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            doc = work / '示例真名.docx'
            with ZipFile(doc, 'w') as archive:
                archive.writestr('word/document.xml',
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    '<w:body><w:p><w:r><w:t>示例真名说：我只借过一次。</w:t></w:r></w:p>'
                    '</w:body></w:document>')
            aliases = work / 'aliases.json'
            aliases.write_text(json.dumps({'示例真名': '化名甲'}), encoding='utf-8')
            case = work / 'case.json'
            result = self.call(SKILL / 'scripts' / 'run.py', 'import', '--file', doc,
                               '--title', '虚构测试', '--alias-map', aliases,
                               '--output', case, cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(case.read_text(encoding='utf-8'))
            self.assertNotIn('示例真名', case.read_text(encoding='utf-8'))
            self.assertEqual(data['materials'][0]['label'], '化名甲')
            self.assertTrue((work / 'case-source-manifest.json').exists())
            article = work / 'article.txt'
            article.write_text('化名甲说：“我只借过一次。”\n--- 修订记录 ---\n“这是日志”', encoding='utf-8')
            result = self.call(SKILL / 'scripts' / 'run.py', 'inspect', '--input', case,
                               '--article', article, '--output', work / 'audit.json', cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads((work / 'audit.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['marked_quotes'], 1)
            self.assertEqual(audit['quotes'][0]['exact_source_ids'], ['S1'])


if __name__ == '__main__':
    unittest.main()
