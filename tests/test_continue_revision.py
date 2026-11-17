import json
import unittest

from featurepipe.continue_revision import object_result, tagged_article


class ContinuationTests(unittest.TestCase):
    def test_cleanup_keeps_only_tagged_body(self):
        text='修改说明：删除了无依据场景。\n<正文>标题\n完整正文。</正文>\n这句话不是正文。'
        self.assertEqual(tagged_article(text),'标题\n完整正文。')
        with self.assertRaises(ValueError):tagged_article('这里只有说明，没有完整文章。')
        with self.assertRaises(ValueError):tagged_article('<正文>一</正文><正文>二</正文>')

    def test_review_requires_actual_comparison(self):
        with self.assertRaises(ValueError):object_result('{}')
        with self.assertRaises(ValueError):object_result('{"逐稿评价":[],"对照结论":"没有实际评价"}')
        row={'匿名编号':'稿件1','硬门槛':[{'项目':'来源支持','状态':'待核实'}],'主观评价':[{'维度':'叙事组织','评分':3}]}
        value={'逐稿评价':[row],'对照结论':'仅作格式测试'}
        self.assertEqual(object_result(json.dumps(value),{'稿件1'}),value)
        with self.assertRaises(ValueError):object_result(json.dumps(value),{'稿件1','稿件2'})
        row['主观评价'][0]['评分']=True
        with self.assertRaises(ValueError):object_result(json.dumps(value))
