import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from featurepipe.client import APIError, BudgetExceeded, Client
from featurepipe.config import load_env
from featurepipe.core import parse_audit, run


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"FEATUREPIPE_API_KEY":"test-secret", "FEATUREPIPE_BASE_URL":"https://api.siliconflow.cn/v1", "FEATUREPIPE_MODEL":"deepseek-ai/DeepSeek-V4-Flash"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_provider_request_and_usage(self):
        response={"model":"test-version", "choices":[{"finish_reason":"stop","message":{"content":'{"issues":[]}'}}],"usage":{"total_tokens":19}}
        fake = unittest.mock.MagicMock()
        fake.open.return_value.__enter__.return_value = io.StringIO(json.dumps(response))
        with patch("featurepipe.client.urllib.request.build_opener",return_value=fake):
            client=Client()
            client.call("inspect",{"sentence":"测试"})
        req=fake.open.call_args.args[0]
        body=json.loads(req.data)
        self.assertEqual(req.full_url,"https://api.siliconflow.cn/v1/chat/completions")
        self.assertFalse(body["enable_thinking"])
        self.assertEqual(body["response_format"],{"type":"json_object"})
        self.assertEqual(client.records[0]["usage"]["total_tokens"],19)

    def test_truncation_is_not_success(self):
        response={"choices":[{"finish_reason":"length","message":{"content":"半篇文章"}}],"usage":{"total_tokens":30}}
        with patch.object(Client,"_post",return_value=response):
            c=Client()
            with self.assertRaises(APIError): c.call("draft",{})
        self.assertEqual(c.records[0]["usage"]["total_tokens"],30)
        self.assertEqual(c.records[0]["status"],"invalid_response")

    def test_length_retry_instructions_precede_material(self):
        response={"choices":[{"finish_reason":"stop","message":{"content":"正文"}}]}
        with patch.object(Client,"_post",return_value=response) as post:
            Client().call("draft",{"length_target":{"min_chinese_chars":400,"max_chinese_chars":600},"length_feedback":907})
        prompt=post.call_args.args[0]['messages'][1]['content']
        self.assertTrue(prompt.startswith('正文篇幅目标：400至600'))
        self.assertIn('上一稿实测907个中文字符，请删减',prompt)

    def test_unauthorized_does_not_retry_or_leak(self):
        with patch.object(Client,"_post",side_effect=urllib.error.HTTPError("https://api.siliconflow.cn",401,"secret-from-server",{},None)) as post:
            c=Client()
            with self.assertRaises(APIError) as caught: c.call("summary",{})
        self.assertEqual(post.call_count,1)
        self.assertNotIn("secret-from-server",str(caught.exception))
        self.assertEqual(c.calls,1)

    def test_retries_count_toward_budget(self):
        with patch.object(Client,"_post",side_effect=urllib.error.HTTPError("https://api.siliconflow.cn",429,"rate limit",{},None)), patch("featurepipe.client.time.sleep"):
            c=Client(max_calls=1)
            with self.assertRaises(BudgetExceeded): c.call("summary",{})
        self.assertEqual(c.calls,1)
        self.assertEqual(c.records[0]["http_status"],429)

    def test_env_is_data_and_does_not_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'.env'
            p.write_text('FEATUREPIPE_MODEL=other\nDEEPSEEK_API_KEY="$(do-not-execute)"\n')
            load_env(p)
        self.assertEqual(os.environ['FEATUREPIPE_MODEL'],'deepseek-ai/DeepSeek-V4-Flash')
        self.assertEqual(os.environ['DEEPSEEK_API_KEY'],'$(do-not-execute)')

    def test_evaluation_outputs_and_source_validation(self):
        case={"title":"测试","materials":[{"id":"S1","text":"虚构素材"}]}
        with tempfile.TemporaryDirectory() as tmp:
            out=run(case,Path(tmp)/'out',Client(mock=True),rounds=1,evaluate=True)
            self.assertTrue((out/'00-baseline.md').exists())
            self.assertTrue((out/'evaluation-final.json').exists())
            self.assertEqual(json.loads((out/'report.json').read_text())['evaluation'],'same-model-review-not-independent')
        with self.assertRaises(ValueError):
            parse_audit(json.dumps({"findings":[{"sentence":"x","problem":"x","evidence":"x","source_ids":["missing"]}],"assessment":"x"}),case['materials'])
