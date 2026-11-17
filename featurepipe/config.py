"""Local configuration. Never execute .env content as shell code."""

import os
from pathlib import Path


def load_env(path=".env"):
    path = Path(path)
    if not path.is_file():
        return
    allowed = {"DEEPSEEK_API_KEY", "FEATUREPIPE_API_KEY", "FEATUREPIPE_BASE_URL", "FEATUREPIPE_MODEL"}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or name not in allowed:
            raise ValueError(f".env 第 {number} 行包含不支持的配置项")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f".env 第 {number} 行引号不完整")
            value = value[1:-1]
        # Existing environment takes precedence; no interpolation or execution.
        if value:
            os.environ.setdefault(name, value)
