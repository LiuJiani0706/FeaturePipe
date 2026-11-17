"""Check credentials without logging their contents or sending interview material."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from featurepipe.client import Client
from featurepipe.config import load_env

load_env()
client = Client(max_calls=1, max_tokens=15000, retries=0)
try:
    text = client.call("summary", {"title": "连接测试", "materials": [{"id": "T1", "text": "这是虚构的接口测试，不含个人信息。只需简短确认收到。"}]})
    print(json.dumps({"success": True, "model": client.model, "reply": text, "records": client.records}, ensure_ascii=False, indent=2))
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
    sys.exit(1)
