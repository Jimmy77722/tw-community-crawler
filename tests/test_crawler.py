# -*- coding: utf-8 -*-
"""crawler 層離線測試：yaml 分派、去重與上限、RateLimited 禮貌停止、EMPTY＋probe。
stub 掉 HTTP 與瀏覽器分派，不碰網路。"""
import json
from pathlib import Path

import httpx
import pytest

from twcc import crawler
from twcc.http_client import RateLimited
from twcc.crawler import crawl_site

FIX = Path(__file__).parent / "fixtures"


class FakeResp:
    def __init__(self, text):
        self.text = text


@pytest.fixture()
def fake_polite_get(monkeypatch):
    """stub polite_get：記錄呼叫、回腳本內容。"""
    calls = []
    state = {"script": [FakeResp("{}")]}

    def fake(site, url, headers=None, rate=None, timeout=20.0):
        calls.append((site, url, headers, rate))
        r = state["script"].pop(0) if len(state["script"]) > 1 else state["script"][0]
        if isinstance(r, Exception):
            raise r
        return FakeResp(r)

    monkeypatch.setattr(crawler, "polite_get", fake)
    return calls, state


# ---------- api 分派（Reddit search.json fixture） ----------

def test_crawl_site_reddit_api(fake_polite_get):
    calls, state = fake_polite_get
    data = (FIX / "reddit_search.json").read_text(encoding="utf-8")
    state["script"] = [data]
    result = crawl_site("reddit", "RTX Spark", 10, out_dir="ignore", cdp_url="")
    assert result["site"] == "reddit"
    assert result["count"] == 3
    ids = [it["id"] for it in result["items"]]
    assert ids == ["t3_abc123", "t3_def456", "t3_ghi789"]
    # 統一 schema 欄位齊全
    for it in result["items"]:
        assert set(it) >= {"site", "id", "author", "time", "title", "text",
                           "url", "likes", "comments", "fetched_at"}


def test_crawl_site_n_caps_items(fake_polite_get):
    _, state = fake_polite_get
    state["script"] = [(FIX / "reddit_search.json").read_text(encoding="utf-8")]
    result = crawl_site("reddit", "kw", 2, out_dir="ignore", cdp_url="")
    assert result["count"] == 2                 # --n 較嚴時以其為準


# ---------- RateLimited → 禮貌停止 ----------

def test_crawl_site_rate_limited_result(fake_polite_get):
    _, state = fake_polite_get
    state["script"] = [RateLimited("reddit", 403, "被擋")]
    result = crawl_site("reddit", "kw", 10, out_dir="ignore", cdp_url="")
    assert result == {"site": "reddit", "count": 0, "items": [],
                      "error": "RATE_LIMIT", "reason": "[reddit] HTTP 403：被擋",
                      "url": result["url"]}
    assert "search.json" in result["url"]


def test_crawl_site_empty_has_probe(fake_polite_get):
    _, state = fake_polite_get
    state["script"] = ['{"data": {"children": []}}']
    result = crawl_site("reddit", "kw", 10, out_dir="ignore", cdp_url="")
    assert result["count"] == 0
    assert result["error"] == "EMPTY"
    assert "probe" in result


# ---------- html 分派（fixture HTML 餵 parse_html） ----------

def test_crawl_site_html_dispatch(monkeypatch):
    """用 ptt 的 link 規則直接驗 html 分派路徑（method 覆寫成 html）。"""
    html = (FIX / "ptt_search.html").read_text(encoding="utf-8")

    def fake(site, url, headers=None, rate=None, timeout=20.0):
        return FakeResp(html)

    monkeypatch.setattr(crawler, "polite_get", fake)
    monkeypatch.setattr(crawler, "load_site", lambda name: {
        "site": "ptt", "method": "html",
        "search_url": "https://ptt.cc/q/{kw}", "max_items": 20,
        "extract": {"rule": "link", "container": "a", "link_filter": "/bbs/",
                    "id_regex": r"/bbs/\w+/(M\.\d+)",
                    "board_regex": r"/bbs/(\w+)/"},
    })
    result = crawl_site("ptt", "AI", 10, out_dir="ignore", cdp_url="")
    assert result["count"] == 3
    titles = [it["title"] for it in result["items"]]
    assert any("本地" in t for t in titles)


# ---------- save-html 除錯輸出 ----------

def test_save_raw_writes_file(tmp_path, fake_polite_get):
    _, state = fake_polite_get
    state["script"] = [(FIX / "reddit_search.json").read_text(encoding="utf-8")]
    crawl_site("reddit", "kw", 10, out_dir=str(tmp_path), cdp_url="", save_html=True)
    raw = tmp_path / "reddit_raw.html"
    assert raw.exists()
    assert "children" in raw.read_text(encoding="utf-8")
