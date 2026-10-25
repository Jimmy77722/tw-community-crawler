# -*- coding: utf-8 -*-
"""抓取調度：依 site yaml 的 method 分派 api / html / browser。
優先序：官方 JSON → 純 HTML → 瀏覽器（Playwright）。回傳 (posts, meta)。"""
from __future__ import annotations

import asyncio
import json as jsonlib
import logging
import urllib.parse

from .config import load_site
from .http_client import RateLimited, polite_get
from .parsers import parse_html, parse_json, parse_text_rule
from .schema import now_iso

log = logging.getLogger("twcc")


def _save_raw(out_dir, site: str, text: str):
    """除錯用：把原回傳內容存到 output/<site>_raw.html，方便重探 DOM。"""
    from pathlib import Path
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir).joinpath(f"{site}_raw.html").write_text(text, encoding="utf-8")

# 只有 method:browser 的站才需要 Playwright；lazy import，public 版裝 playwright 才跑得動
def _crawl_browser_sync(site: str, cfg: dict, kw: str, cdp_url: str, n: int):
    from playwright.sync_api import sync_playwright  # lazy

    url = cfg["search_url"].format(kw=urllib.parse.quote(kw), n=n)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()          # 自己開的分頁
        try:
            page.goto(url, wait_until="domcontentloaded")
            wait_sel = cfg.get("wait_selector")
            try:
                if wait_sel:
                    page.wait_for_selector(wait_sel, timeout=15_000)
                else:
                    page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception as e:
                log.warning("[%s] 等待內容逾時：%s", site, type(e).__name__)
            settle = cfg.get("settle_ms")
            if settle:
                # Google CSE 等遲遲渲染的結果：再等 settle 毫秒
                page.wait_for_timeout(int(settle))
            container = cfg["extract"].get("container", "li")
            if cfg["extract"]["rule"] == "link":
                # 渲染後 DOM 已就緒（wait_selector 過）：直接吃渲染後的 HTML，重用 link 規則
                html = page.content()
                meta = {"url": page.url}
                posts = parse_html(site, cfg, html)
                if not posts:
                    two = page.evaluate("() => document.documentElement.outerHTML.split('\\n').slice(0,2)")
                    meta["probe"] = "\n".join(two)[:1200]
                return posts, meta
            blocks = page.eval_on_selector_all(
                container, "els => els.map(e => e.innerText)")
            posts = parse_text_rule(site, cfg, blocks)
            meta = {"url": page.url}
            if not posts:
                two = page.evaluate("() => document.documentElement.outerHTML.split('\\n').slice(0,2)")
                meta["probe"] = "\n".join(two)[:1200]
            return posts, meta
        finally:
            page.close()               # 只關自己開的分頁，不關使用者的瀏覽器


def crawl_site(site: str, kw: str, n: int, out_dir, cdp_url: str,
               probe: bool = False, save_html: bool = False):
    """回傳 dict：{'site','count','items':[...]}；抓 0 筆含 probe 供重探。"""
    cfg = load_site(site)
    url = cfg["search_url"].format(kw=urllib.parse.quote(kw), n=n)
    posts, meta = [], {"url": url}
    try:
        if cfg["method"] == "api":
            resp = polite_get(site, url)
            if save_html:
                _save_raw(out_dir, site, resp.text)
            data = jsonlib.loads(resp.text)
            posts = parse_json(site, cfg, data)
        elif cfg["method"] == "html":
            resp = polite_get(site, url)
            if save_html:
                _save_raw(out_dir, site, resp.text)
            posts = parse_html(site, cfg, resp.text)
        elif cfg["method"] == "browser":
            posts, meta = _crawl_browser_sync(site, cfg, kw, cdp_url, n)
        else:
            raise ValueError(f"{site}: 未知 method {cfg['method']}")
    except RateLimited as e:
        # 禮貌停止該站：記錄後回報，不重試硬闖
        log.warning("[%s] 禮貌停止：%s", site, e)
        return {"site": site, "count": 0, "items": [], "error": "RATE_LIMIT",
                "reason": str(e), "url": url}
    except Exception as e:
        log.error("[%s] 抓取失敗：%s: %s", site, type(e).__name__, e)
        return {"site": site, "count": 0, "items": [], "error": type(e).__name__,
                "reason": str(e)[:160], "url": url}

    # 站內去重（依 site+id）
    seen, uniq = set(), []
    for p in posts:
        if p.key() in seen:
            continue
        seen.add(p.key())
        uniq.append(p)
    items = [p.model_dump() for p in uniq]
    result = {"site": site, "count": len(items), "items": items,
              "fetched_at": now_iso(), **meta}
    if not items:
        log.warning("[%s] 抓到 0 筆——可能改版，附上 probe 重探 DOM", site)
        result["error"] = "EMPTY"
        result["probe"] = meta.get("probe", "")
    return result
