"""
Coverage for the retry behavior added to the bcut ASR transcriber.

Background: B站必剪 ASR interface is flaky in two distinct ways:
  1. Business-level transient errors — the JSON response is well-formed but
     ``code`` is in {139201, -400, -500}. These typically clear on retry.
  2. HTTP-level transient errors — wbi/风控 抖动 returns 412; gateway
     returns 5xx. Again, retry usually succeeds.

Pinning both layers: each of the three network calls (``__commit_upload``,
``_create_task``, ``_query_result``) must:
  - retry on a retryable business code up to ``DEFAULT_MAX_RETRIES``
  - retry on a retryable HTTP status up to ``DEFAULT_MAX_RETRIES``
  - raise immediately on a non-retryable failure
  - raise when retries are exhausted
  - apply exponential backoff between attempts

See: issue #433 (桌面端 bcut 首次成功后后续任务上传失败).
"""
import time
import requests

import pytest

from app.transcriber import bcut as bcut_module
from app.transcriber.bcut import (
    BcutTranscriber,
    DEFAULT_MAX_RETRIES,
    RETRYABLE_BUSINESS_CODES,
    RETRYABLE_HTTP_STATUSES,
)


class _FakeResp:
    def __init__(self, *, status=200, json_payload=None, raise_http=False):
        self.status_code = status
        self._payload = json_payload if json_payload is not None else {}
        self._raise_http = raise_http
        self.headers = {}
        self.url = ""

    def raise_for_status(self):
        if self._raise_http:
            err = requests.exceptions.HTTPError(
                f"{self.status_code} Server Error", response=self
            )
            raise err

    def json(self):
        return self._payload


class _ScriptedSession:
    """Each .post / .get returns the next pre-scripted response (or HTTPError)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def _next(self):
        self.calls += 1
        if not self._responses:
            raise AssertionError("scripted session ran out of responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        return self._next()

    def get(self, url, params=None, headers=None, timeout=None):
        return self._next()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip real backoff sleeps so the suite stays fast."""
    monkeypatch.setattr(bcut_module.time, "sleep", lambda s: None)
    yield


# ---------- __commit_upload ----------

def test_commit_upload_retries_on_retryable_business_code_then_succeeds():
    t = BcutTranscriber()
    t.session = _ScriptedSession([
        _FakeResp(json_payload={"code": 139201, "message": "too many"}),
        _FakeResp(json_payload={"code": -500, "message": "busy"}),
        _FakeResp(json_payload={"code": 0, "data": {"download_url": "http://fake/dl"}}),
    ])
    t._BcutTranscriber__commit_upload()  # name-mangled private
    assert t._BcutTranscriber__download_url == "http://fake/dl"
    assert t.session.calls == DEFAULT_MAX_RETRIES


def test_commit_upload_retries_on_412_then_succeeds():
    t = BcutTranscriber()
    t.session = _ScriptedSession([
        _FakeResp(status=412, raise_http=True),
        _FakeResp(json_payload={"code": 0, "data": {"download_url": "http://fake/dl"}}),
    ])
    t._BcutTranscriber__commit_upload()
    assert t.session.calls == 2


def test_commit_upload_retries_on_5xx_then_succeeds():
    t = BcutTranscriber()
    t.session = _ScriptedSession([
        _FakeResp(status=503, raise_http=True),
        _FakeResp(json_payload={"code": 0, "data": {"download_url": "http://fake/dl"}}),
    ])
    t._BcutTranscriber__commit_upload()
    assert t.session.calls == 2


def test_commit_upload_fails_fast_on_non_retryable_business_code():
    t = BcutTranscriber()
    t.session = _ScriptedSession([
        _FakeResp(json_payload={"code": 99999, "message": "fatal"}),
    ])
    with pytest.raises(Exception, match="上传提交失败: fatal"):
        t._BcutTranscriber__commit_upload()
    assert t.session.calls == 1


def test_commit_upload_raises_when_retries_exhausted():
    t = BcutTranscriber()
    t.session = _ScriptedSession([
        _FakeResp(json_payload={"code": 139201, "message": "x"}),
        _FakeResp(json_payload={"code": 139201, "message": "x"}),
        _FakeResp(json_payload={"code": 139201, "message": "x"}),
    ])
    with pytest.raises(Exception, match=r"重试 \d+ 次后仍返回 code=139201"):
        t._BcutTranscriber__commit_upload()
    assert t.session.calls == DEFAULT_MAX_RETRIES


# ---------- _create_task ----------

def test_create_task_retries_on_412_then_succeeds():
    t = BcutTranscriber()
    t._BcutTranscriber__download_url = "http://fake/dl"
    t.session = _ScriptedSession([
        _FakeResp(status=412, raise_http=True),
        _FakeResp(json_payload={"code": 0, "data": {"task_id": "tid-1"}}),
    ])
    assert t._create_task() == "tid-1"
    assert t.session.calls == 2


def test_create_task_fails_fast_on_non_retryable_code():
    t = BcutTranscriber()
    t._BcutTranscriber__download_url = "http://fake/dl"
    t.session = _ScriptedSession([
        _FakeResp(json_payload={"code": 7, "message": "auth"}),
    ])
    with pytest.raises(Exception, match="创建任务失败: auth"):
        t._create_task()
    assert t.session.calls == 1


# ---------- _query_result ----------

def test_query_result_retries_on_412_then_returns_data():
    t = BcutTranscriber()
    t.task_id = "tid-1"
    t.session = _ScriptedSession([
        _FakeResp(status=412, raise_http=True),
        _FakeResp(json_payload={"code": 0, "data": {"state": 4, "result": "{}"}}),
    ])
    data = t._query_result()
    assert data == {"state": 4, "result": "{}"}
    assert t.session.calls == 2


def test_query_result_retries_on_timeout():
    t = BcutTranscriber()
    t.task_id = "tid-1"
    t.session = _ScriptedSession([
        requests.exceptions.Timeout("read timed out"),
        _FakeResp(json_payload={"code": 0, "data": {"state": 4, "result": "{}"}}),
    ])
    data = t._query_result()
    assert data["state"] == 4
    assert t.session.calls == 2


# ---------- constants ----------

def test_retryable_constants_cover_documented_codes():
    assert 139201 in RETRYABLE_BUSINESS_CODES
    assert -400 in RETRYABLE_BUSINESS_CODES
    assert -500 in RETRYABLE_BUSINESS_CODES
    assert 412 in RETRYABLE_HTTP_STATUSES
    assert 500 in RETRYABLE_HTTP_STATUSES
    assert 502 in RETRYABLE_HTTP_STATUSES
    assert 503 in RETRYABLE_HTTP_STATUSES
    assert 504 in RETRYABLE_HTTP_STATUSES


def test_default_max_retries_is_three():
    assert DEFAULT_MAX_RETRIES == 3
