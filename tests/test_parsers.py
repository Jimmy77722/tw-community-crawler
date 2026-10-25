# -*- coding: utf-8 -*-
"""parser 層離線測試：全部吃 tests/fixtures 的樣板，不碰網路。"""
import json
from pathlib import Path

import pytest

from twcc.config import load_site
from twcc.parsers import parse_html, parse_json, parse_text_rule

FIX = Path(__file__).parent / "fixtures"


# ---------- rule=link（PTT／Mobile01 渲染後 HTML） ----------

@pytest.fixture()
def ptt_html():
    return (FIX / "ptt_search.html").read_text(encoding="utf-8")


def test_parse_html_ptt_basic(ptt_html):
    cfg = load_site("ptt")
    posts = parse_html("ptt", cfg, ptt_html)
    ids = {p.id for p in posts}
    # PTT 文章 ID 規則只取 M.<digits>；fixture 三篇不重複文章＋一重複連結（去重）＝ 3 筆
    assert len(posts) == 3
    assert "M.1762000000" in ids
    assert "M.1762000001" in ids          # 重複連結只留第一筆
    assert "M.1762000002" in ids


def test_parse_html_ptt_fields(ptt_html):
    cfg = load_site("ptt")
    posts = parse_html("ptt", cfg, ptt_html)
    p = next(p for p in posts if p.id == "M.1762000000")
    assert p.title == "[心得] 本地 LLM 上手記錄"
    assert p.url.startswith("https://www.ptt.cc/bbs/AI/")
    assert p.author == "AI"                      # board 借 author 欄
    assert p.site == "ptt"


def test_parse_html_link_filter_and_titles(ptt_html):
    cfg = load_site("ptt")
    posts = parse_html("ptt", cfg, ptt_html)
    # 廣告連結（無 /bbs/）與空標題連結都被擋掉
    assert all("/bbs/" in p.url for p in posts)
    assert all(p.title for p in posts)


def test_parse_html_m01_relative_url_base(ptt_html):
    """相對 href 用 base_url 組絕對網址（M01 規則）。"""
    cfg = {
        "extract": {
            "rule": "link", "container": "a", "link_filter": "topicdetail",
            "id_regex": r"[?&]t=(\d+)", "board_regex": r"[?&]f=(\d+)",
            "base_url": "https://www.mobile01.com",
        },
        "max_items": 20,
    }
    html = '<html><body><a href="/topicdetail.php?f=329&t=9000001">M01 相對連結</a></body></html>'
    posts = parse_html("m01", cfg, html)
    assert len(posts) == 1
    assert posts[0].url == "https://www.mobile01.com/topicdetail.php?f=329&t=9000001"
    assert posts[0].id == "9000001"
    assert posts[0].author == "329"


# ---------- rule=json（Reddit search.json fixture） ----------

@pytest.fixture()
def reddit_data():
    return json.loads((FIX / "reddit_search.json").read_text(encoding="utf-8"))


def test_parse_json_reddit_count(reddit_data):
    cfg = load_site("reddit")
    posts = parse_json("reddit", cfg, reddit_data)
    assert len(posts) == 3


def test_parse_json_reddit_fields(reddit_data):
    cfg = load_site("reddit")
    posts = parse_json("reddit", cfg, reddit_data)
    p = posts[0]
    assert p.id == "t3_abc123"                   # id_prefix 生效
    assert p.url == "https://www.reddit.com/r/LocalLLaMA/comments/abc123/rtx_spark/"
    assert p.likes == 42 and p.comments == 7
    assert p.time == "2025-11-01T20:26:40+08:00"  # created_utc → 台北 ISO


def test_parse_json_reddit_optional_fields(reddit_data):
    """author/ups/num_comments 為 null 時不炸、留 None。"""
    cfg = load_site("reddit")
    posts = parse_json("reddit", cfg, reddit_data)
    p = posts[2]
    assert p.author is None and p.text is None
    assert p.likes is None and p.comments is None


def test_parse_json_respects_max_items(reddit_data):
    cfg = load_site("reddit")
    cfg["max_items"] = 2
    assert len(parse_json("reddit", cfg, reddit_data)) == 2


# ---------- rule=text-rule（Dcard／ani 瀏覽器文字行） ----------

def test_parse_text_rule_dcard_rows():
    cfg = load_site("dcard")
    texts = [
        "programming\nada\n2026-10-25\nRTX Spark 討論\n摘要第二行",
        "ai\nbob\n2026-10-24\n本地模型心得",
    ]
    posts = parse_text_rule("dcard", cfg, texts)
    assert len(posts) == 2
    assert posts[0].author == "ada"
    assert posts[0].title == "RTX Spark 討論"
    assert posts[0].text == "摘要第二行"


def test_parse_text_rule_dcard_bad_rows_skipped():
    cfg = load_site("dcard")
    posts = parse_text_rule("dcard", cfg, ["只有兩行\n撐不起row_pattern"])
    assert posts == []


def test_parse_text_rule_ani_anchor():
    cfg = load_site("ani")
    texts = ["片名A\n番名B\n2025年\n更多", "只有名字\n沒有年份行"]
    posts = parse_text_rule("ani", cfg, texts)
    assert len(posts) == 1
    assert posts[0].title == "番名B"             # 錨點（年份行）的上一行
