# -*- coding: utf-8 -*-
"""需登入三站（x／ig／threads）離線測試：yaml 從嚴參數、text-rule fixtures、
作者雜湊去識別化、CLI 預設關閉警語。全部手寫假資料，不碰網路、不開瀏覽器。"""
import json

import pytest

from twcc import crawler
from twcc.config import load_site
from twcc.crawler import anonymize_items, crawl_site
from twcc.parsers import parse_text_rule
from twcc import main as twcc_main

FIX = __import__("pathlib").Path(__file__).parent / "fixtures"
LOGIN_SITES = ["x", "ig", "threads"]


def _blocks(name):
    data = json.loads((FIX / f"{name}_blocks.json").read_text(encoding="utf-8"))
    return data["blocks"]


# ---------- yaml 從嚴參數 ----------

@pytest.mark.parametrize("site", LOGIN_SITES)
def test_login_site_yaml_policy(site):
    cfg = load_site(site)
    assert cfg["method"] == "browser", "需登入站只走使用者自己的已登入瀏覽器"
    assert cfg.get("login_required") is True
    lo, hi = cfg["rate_limit"]
    assert lo >= 10, "登入站限速至少 10 秒"
    assert cfg.get("max_items") == 50, "--n 上限 50"


# ---------- fixtures text-rule 解析 ----------

@pytest.mark.parametrize("site", LOGIN_SITES)
def test_login_fixtures_parse(site):
    cfg = load_site(site)
    posts = parse_text_rule(site, cfg, _blocks(site))
    assert posts, f"{site} fixtures 應解析出筆數"
    for p in posts:
        assert p.site == site
        assert p.title and p.url.startswith("https://"), "假連結也要絕對網址"


# ---------- 去識別化 ----------

def test_anonymize_hashes_author():
    items = [{"site": "x", "author": "真實帳號aaa"},
             {"site": "x", "author": "真實帳號aaa"},
             {"site": "x", "author": None}]
    out = anonymize_items(items)
    assert out[0]["author"].startswith("user_") and len(out[0]["author"]) == 13
    assert out[0]["author"] == out[1]["author"]      # 同作者同雜湊
    assert out[2]["author"] is None                  # 無作者不硬造
    assert "真實" not in json.dumps(out, ensure_ascii=False)


def test_crawl_site_login_anonymizes_by_default(monkeypatch):
    cfg = load_site("x")
    posts = parse_text_rule("x", cfg, _blocks("x"))

    def fake_browser(site, cfg_, kw, cdp_url, n):
        return posts, {"url": "https://x.com/search"}
    monkeypatch.setattr(crawler, "_crawl_browser_sync", fake_browser)

    res = crawl_site("x", "AI", 50, out_dir="ignore", cdp_url="")
    assert res["count"] == len(posts)
    for it in res["items"]:
        assert it["author"] is None or it["author"].startswith("user_")

    res2 = crawl_site("x", "AI", 50, out_dir="ignore", cdp_url="",
                      keep_author=True)
    assert any(not str(it["author"]).startswith("user_")
               for it in res2["items"] if it["author"])


# ---------- CLI 預設關閉 ----------

def test_cli_blocks_login_sites_without_flag(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("未加 --i-understand-login-risk 不應抓取")
    monkeypatch.setattr(twcc_main, "crawl_site", boom)
    rc = twcc_main.main(["x", "--kw", "AI"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "--i-understand-login-risk" in out       # 印警語後結束
    assert "⚠️" in out


def test_cli_login_sites_print_warning_each_run(monkeypatch, capsys, tmp_path):
    seen = {"n": 0}

    def fake(site, kw, n, out_dir, cdp, probe, **k):
        seen["n"] += 1
        return {"site": site, "count": 0, "items": [], "error": "EMPTY"}
    monkeypatch.setattr(twcc_main, "crawl_site", fake)
    rc = twcc_main.main(["x", "threads", "--kw", "AI",
                         "--i-understand-login-risk", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and seen["n"] == 2
    assert out.count("⚠️ 登入風險宣告") == 1          # 每次執行開頭印一次警語
