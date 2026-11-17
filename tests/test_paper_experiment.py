from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from featurepipe.client import BudgetExceeded, Client
from featurepipe.paper_experiment import Store, body_only, no_revision, parse_split
from featurepipe.spend import SpendGuard
from unittest.mock import patch


class PaperTests(unittest.TestCase):
    def test_no_revision_requires_only_sentinel(self):
        self.assertTrue(no_revision(' **无需修改。** '))
        self.assertTrue(no_revision('"no revision needed"'))
        self.assertFalse(no_revision('无需修改，但请增加一个场景。'))

    def test_split_is_in_order_and_covers_body(self):
        draft='甲说今天可以出门。乙说准备先完成作业。丙想先去吃饭。'
        pieces=['甲说今天可以出门。','乙说准备先完成作业。','丙想先去吃饭。']
        self.assertEqual(parse_split(json.dumps({'sentences':pieces}),draft),pieces)
        with self.assertRaises(ValueError):parse_split(json.dumps({'sentences':pieces[::-1]}),draft)
        with self.assertRaises(ValueError):parse_split(json.dumps({'sentences':pieces[:1]}),draft)
        with self.assertRaises(ValueError):parse_split(json.dumps({'sentences':['甲说今天特别开心。']}),draft)

    def test_revision_records_do_not_count_as_article(self):
        self.assertEqual(body_only('完整正文。\n\n--- 修订记录 ---\n版本一：修改了句子'), '完整正文。')
        self.assertEqual(body_only('正文提到了修订记录，但没有分隔线。'),'正文提到了修订记录，但没有分隔线。')

    def test_parallel_calls_cannot_overrun_budget(self):
        client=Client(mock=True,max_calls=3,max_tokens=100000)
        def one(_):
            try:client.call('summary',{});return True
            except BudgetExceeded:return False
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(one,range(12)))
        self.assertEqual(sum(results),3)
        self.assertEqual(len(client.records),3)
        self.assertEqual(client.calls,3)

    def test_cache_and_both_client_budgets_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            clients={'writer':Client(mock=True),'reviewer':Client(mock=True)}
            store=Store(Path(tmp)/'run','signature',False,clients)
            messages=[{'role':'user','content':'采访素材'}]
            store.call('writer','summary',messages,'summary.txt')
            store.call('reviewer','summary',messages,'review.txt')
            with self.assertRaisesRegex(ValueError,'进程占用'):
                Store(Path(tmp)/'run','signature',True,{'writer':Client(mock=True),'reviewer':Client(mock=True)})
            store.close()
            resumed={'writer':Client(mock=True),'reviewer':Client(mock=True)}
            again=Store(Path(tmp)/'run','signature',True,resumed)
            again.call('writer','summary',messages,'summary.txt')
            self.assertEqual(resumed['writer'].calls,1)
            self.assertEqual(resumed['reviewer'].calls,1)
            with self.assertRaises(ValueError):again.call('writer','summary',[{'role':'user','content':'不同素材'}],'summary.txt')
            again.close()

    def test_money_reservation_is_durable_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard=SpendGuard(1,{'M':{'input':10,'output':20,'cached_input':1}})
            client=Client(model='M',spend_guard=guard)
            store=Store(Path(tmp)/'run','signature',False,{'writer':client})
            def response(body):
                saved=json.loads((store.path/'usage.json').read_text())
                self.assertEqual(saved['clients']['writer']['calls'],1)
                self.assertGreater(saved['cost_estimate']['inflight_rmb_estimate'],0)
                return {'choices':[{'finish_reason':'stop','message':{'content':'已收到'}}],'usage':{'prompt_tokens':10,'completion_tokens':1}}
            with patch.object(client,'preflight'),patch.object(client,'_post',side_effect=response):
                store.call('writer','summary',[{'role':'user','content':'测试'}],'summary.txt')
            saved=json.loads((store.path/'usage.json').read_text())
            self.assertEqual(saved['cost_estimate']['inflight_rmb_estimate'],0)
            store.close()


if __name__=='__main__':unittest.main()
