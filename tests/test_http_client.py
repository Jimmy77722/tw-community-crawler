# -*- coding: utf-8 -*-
"""HTTP 層離線測試：限速、退避重試、403／驗證頁禮貌停止。
只 stub httpx.get 與 time.sleep，不碰網路、不真等。"""
import time

import httpx
import pytest

from twcc import http_client
from twcc.http_client import RateLimited, polite_gap, polite_get


def make_resp(status=200, text="ok"):
    req = httpx.Request("GET", "https://example.test/")
    return httpx.Response(status, text=text, request=req)


@pytest.fixture()
def slept(monkeypatch):
    """把 time.sleep（time 是模組級單例）變記錄器：限速與退避都不真等。"""
    log = []
    monkeypatch.setattr(time, "sleep", lambda s: log.append(s))
    return log


class FakeGet:
    """依腳本回 Response 或拋例外；.n 記呼叫次數（驗重試次數），.calls 記 headers。"""

    def __init__(self, monkeypatch, *script):
        self.script = list(script)
        self.calls = []
        self.n = 0
        monkeypatch.setattr(http_client.httpx, "get", self)

    def __call__(self, url, headers=None, follow_redirects=False, timeout=None):
        self.n += 1
        self.calls.append((url, headers))
        r = self.script[min(self.n - 1, len(self.script) - 1)]
        if isinstance(r, Exception):
            raise r
        return r


# ---------- 限速 ----------

def test_first_call_no_sleep(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp())
    polite_get("ptt", "https://example.test/1")
    assert slept and max(slept) == 0.0    # 該站首次呼叫：實際零等待


def test_second_call_waits_full_gap(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp())
    polite_get("m01", "https://example.test/1", rate=(2.0, 2.0))
    polite_get("m01", "https://example.test/2", rate=(2.0, 2.0))
    waits = [s for s in slept if s > 0]        # 首次呼叫必定 sleep(0)，只看真等待
    assert len(waits) == 1 and 1.99 <= waits[0] <= 2.01


def test_rate_state_is_per_site(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp())
    polite_get("ptt", "https://example.test/a", rate=(2.0, 2.0))
    polite_get("m01", "https://example.test/b", rate=(2.0, 2.0))
    assert all(s == 0 for s in slept)          # 不同站不共用限速狀態：兩站首次都零等待


def test_polite_gap_registers_site():
    polite_gap("dcard", (0.0, 0.0))
    assert http_client._last_call.get("dcard") is not None


# ---------- 禮貌停止（Reddit 403 走這條） ----------

def test_403_stops_without_retry(slept, monkeypatch):
    g = FakeGet(monkeypatch, make_resp(403, "Forbidden"))
    with pytest.raises(RateLimited) as ei:
        polite_get("reddit", "https://www.reddit.com/search.json?q=x")
    assert ei.value.status == 403
    assert g.n == 1                         # 不重試硬闖


def test_429_stops(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp(429, "Too Many Requests"))
    with pytest.raises(RateLimited) as ei:
        polite_get("ptt", "https://example.test/")
    assert ei.value.status == 429


def test_captcha_page_200_also_stops(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp(200, "This is a CAPTCHA. unblock it"))
    with pytest.raises(RateLimited) as ei:
        polite_get("reddit", "https://example.test/")
    assert ei.value.status == 200


def test_genuine_200_passes(slept, monkeypatch):
    FakeGet(monkeypatch, make_resp(200, "hello"))
    resp = polite_get("reddit", "https://example.test/")
    assert resp.text == "hello"


def test_ua_is_honest(slept, monkeypatch):
    g = FakeGet(monkeypatch, make_resp())
    polite_get("reddit", "https://example.test/")
    ua = g.calls[0][1]["User-Agent"]
    assert ua == http_client.UA
    assert "tw-community-crawler/" in ua and "github.com" in ua


# ---------- 只有瞬時傳輸錯誤才退避重試 ----------

def test_transport_error_retries_three_times(slept, monkeypatch):
    boom = httpx.ConnectError("boom")
    g = FakeGet(monkeypatch, boom, boom, boom, make_resp(200, "ok"))
    with pytest.raises(httpx.ConnectError):
        polite_get("reddit", "https://example.test/")
    assert g.n == 3                         # stop_after_attempt(3)


def test_transport_error_then_success(slept, monkeypatch):
    boom = httpx.ConnectError("boom")
    g = FakeGet(monkeypatch, boom, make_resp(200, "ok"))
    resp = polite_get("reddit", "https://example.test/")
    assert resp.text == "ok"
    assert g.n == 2
