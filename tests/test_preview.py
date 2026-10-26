# -*- coding: utf-8 -*-
"""HTML 預覽輸出：全部離線，吃 fixtures／samples。"""
import json
from pathlib import Path

from twcc.config import load_site
from twcc.parsers import parse_html
from twcc.preview import load_jsonl, render_html, render_preview

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


def _items(n=3):
    """從 PTT fixture parse 出真實結構的結果筆列（dict 形式）。"""
    html = (FIX / "ptt_search.html").read_text(encoding="utf-8")
    posts = parse_html("ptt", load_site("ptt"), html)
    return [p.model_dump() for p in posts[:n]]


def _item(site="ptt", title="t", text="x", url="https://e.com/a", **kw):
    d = {"site": site, "id": "i", "author": "user_1", "time": None,
         "title": title, "text": text, "url": url, "likes": None,
         "comments": None, "fetched_at": "2026-10-26T12:00:00+08:00"}
    d.update(kw)
    return d


def test_card_count_matches_items():
    items = _items(3)
    out = render_html(items, kw="AI Agent")
    assert out.count('<article class="card"') == len(items)


def test_escape_prevents_injected_code():
    evil = '<script>alert("x&y")</script>'
    out = render_html([_item(title=evil, text="<img src=x onerror=1>")], kw="<b>kw</b>")
    assert evil not in out                          # 原始 <script> 不存在
    assert "&lt;script&gt;" in out                  # 被 escape 成文字
    assert "&lt;b&gt;kw&lt;/b&gt;" in out           # 關鍵字也 escape
    assert "<img" not in out.split("<body>")[1]     # body 內沒有未轉義 img


def test_links_absolute_and_new_tab():
    out = render_html(_items(3))
    assert 'href="https://www.ptt.cc/bbs/' in out
    assert 'target="_blank" rel="noopener noreferrer"' in out


def test_summary_and_no_external_deps():
    items = _items(2)
    out = render_html(items, kw="RTX Spark")
    assert "RTX Spark" in out
    assert "ptt 2" in out                            # 各站筆數摘要
    # 單檔、零外部依賴：無 http(s) 資源引用（href 的站連結除外＝在卡片內）
    assert "<link" not in out and "<script src" not in out
    head = out.split('<div id="cards">')[0]
    assert 'href="http' not in head                  # 頁头不連外部資源


def test_render_preview_from_jsonl(tmp_path):
    src = tmp_path / "x.jsonl"
    src.write_text(
        json.dumps(_item(site="ptt", title="甲")) + "\n"
        + json.dumps(_item(site="dcard", title="乙", url="https://dcard.tw/f/b/p/1")) + "\n\n",
        encoding="utf-8")
    out = render_preview([src], out_path=tmp_path / "x.html", kw="測試")
    text = out.read_text(encoding="utf-8")
    assert out.exists()
    assert text.count('<article class="card"') == 2
    assert "測試" in text
    assert 'href="https://dcard.tw/f/b/p/1"' in text


def test_samples_render():
    """samples/ 假資料全部能進預覽（也間接驗證欄位齊全）。"""
    import glob
    paths = sorted(ROOT.glob("samples/*.jsonl"))
    items = []
    for p in paths:
        items.extend(load_jsonl(p))
    assert len(items) >= 10
    out = render_html(items, kw="AI")
    assert out.count('<article class="card"') == len(items)
