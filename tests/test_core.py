import json, tempfile, unittest
from pathlib import Path
from featurepipe.core import Client, BudgetExceeded, run, parse_issues, sentences
class Tests(unittest.TestCase):
    def test_demo(self):
        case={'title':'测试','materials':[{'id':'s1','text':'虚构素材'}]}
        with tempfile.TemporaryDirectory() as t:
            out=run(case,Path(t)/'out',Client(mock=True),rounds=1)
            self.assertTrue((out/'article.md').exists())
            self.assertEqual(json.loads((out/'report.json').read_text())['publication_ready'],False)
    def test_budget(self):
        c=Client(mock=True,max_calls=0)
        with self.assertRaises(BudgetExceeded): c.call('summary',{})
        self.assertEqual(c.calls,0)
    def test_parse_fail_closed(self):
        with self.assertRaises(ValueError): parse_issues('{"issues":[{}]}')
    def test_sentences(self): self.assertEqual(sentences('你好。再见！'),['你好。','再见！'])
    def test_sentence_keeps_closing_quote(self):
        self.assertEqual(sentences('“后面再说。”林禾说。'), ['“后面再说。”','林禾说。'])
        self.assertEqual(sentences('真的吗？！\n“是的！”'), ['真的吗？！','“是的！”'])
if __name__=='__main__': unittest.main()
