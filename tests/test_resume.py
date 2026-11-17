import json
import tempfile
import unittest
from pathlib import Path
from featurepipe.core import Client, BudgetExceeded, run

CASE = {'title': '测试', 'materials': [{'id': 's1', 'text': '虚构采访'}]}

class ResumeTests(unittest.TestCase):
    def test_budget_interruption_resume_and_no_duplicate_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'run'
            with self.assertRaises(BudgetExceeded):
                run(CASE, out, Client(mock=True, max_calls=2), rounds=1)
            self.assertEqual(json.loads((out/'usage.json').read_text())['calls'], 2)
            resumed = Client(mock=True)
            run(CASE, out, resumed, rounds=1, resume=True)
            uninterrupted = Client(mock=True)
            run(CASE, Path(tmp)/'baseline', uninterrupted, rounds=1)
            self.assertEqual(resumed.calls, uninterrupted.calls)
            self.assertEqual((out/'article.md').read_text(), (Path(tmp)/'baseline/article.md').read_text())
            calls = resumed.calls
            run(CASE, out, Client(mock=True), rounds=1, resume=True)
            self.assertEqual(json.loads((out/'usage.json').read_text())['calls'], calls)

    def test_changed_case_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            run(CASE, out, Client(mock=True), rounds=0)
            with self.assertRaisesRegex(ValueError, '不能复用'):
                run({**CASE, 'title':'变更'}, out, Client(mock=True), rounds=0, resume=True)

    def test_malformed_inspection_not_cached(self):
        class Broken(Client):
            def call(self, stage, data):
                return 'invalid' if stage=='inspect' else super().call(stage,data)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            with self.assertRaises(ValueError): run(CASE,out,Broken(mock=True),rounds=1)
            self.assertFalse((out/'r1-s1-inspection.json.checkpoint.json').exists())
            run(CASE,out,Client(mock=True),rounds=1,resume=True)
