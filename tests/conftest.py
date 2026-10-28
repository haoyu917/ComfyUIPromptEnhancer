import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def trust_test_api_hosts(monkeypatch):
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317,example.com,example.test,x")
    monkeypatch.setenv("BUFF_AI_API_KEY_ENV_VARS", "BUFF_AI_API_KEY")
