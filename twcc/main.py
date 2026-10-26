# -*- coding: utf-8 -*-
"""tw-crawler CLI：站名用選項指定、關鍵字 quote 編碼、輸出 jsonl（一行一筆）。
用法例：tw-crawler ptt --kw "AI Agent" --n 20 --out output/
      tw-crawler all --kw "RTX Spark" --probe
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import sys
import os
for _p in ("pydantic", "yaml", "httpx", "tenacity", "selectolax"):
    try:
        __import__(_p)
    except ImportError:
        print(f"[tw-crawler] 缺依賴 {_p}，先： pip install -e .", file=sys.stderr)
        raise SystemExit(2)

from .config import list_sites, load_site
from .crawler import crawl_site, anonymize_items

DEFAULT_CDP = os.environ.get("CRAWLER_CDP_URL", "http://127.0.0.1:9222")

LOGIN_WARNING = (
    "⚠️ 登入風險宣告：X／IG／Threads 需登入才能抓，本專案不碰你的帳密與 cookie"
    "（只用你自己已登入的瀏覽器分頁）。\n"
    "   平台條款大多禁止未經授權的自動抓取，可能導致帳號被限制或停用；抓到 0 筆"
    "（登入牆改版）請 sites/<站>.yaml 隨 DOM 調整。X 建議改用官方 API。\n"
    "   已預設從嚴：每站至少 10 秒抓一次、單次上限 50 筆、作者名稱雜湊藏名。"
)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tw-crawler",
        description="台灣常用社群關鍵字抓取（免登入 5 站；抓 0 筆會附 probe 供重探）")
    ap.add_argument("sites", nargs="+", choices=[*list_sites(), "all"],
                    help="站點（可多選，或 all＝全部）")
    ap.add_argument("--kw", required=True, help="關鍵字（內部自動 quote 編碼）")
    ap.add_argument("--n", type=int, default=10, help="單站上限筆數（預設 10）")
    ap.add_argument("--out", default="output", help="輸出目錄（預設 output/）")
    ap.add_argument("--cdp", default=DEFAULT_CDP,
                    help="Playwright connect_over_cdp 位址（method:browser 的站才需要）")
    ap.add_argument("--probe", action="store_true",
                    help="只開目標頁印 DOM 首兩行，不抽欄位")
    ap.add_argument("--save-html", action="store_true",
                    help="除錯：原回傳內容存 output/<站>_raw.html")
    ap.add_argument("--html", action="store_true",
                    help="抓完從同一批結果產出 output/<站>_<關鍵字>_<時間>.html 預覽")
    ap.add_argument("--i-understand-login-risk", action="store_true",
                    help="表明你懂 X/IG/Threads 需登入且風險自負（這三站不加不跑）")
    ap.add_argument("--keep-author", action="store_true",
                    help="登入站保留作者原樣（預設雜湊成 user_<hash8>）")
    ap.add_argument("--jsonl", action="store_true", default=True,
                    help="結果寫 <站>_關鍵詞_日付.jsonl（預設開）")
    return ap


def _preview_args(argv: list[str]) -> int:
    """子指令：tw-crawler preview <jsonl檔> [更多 jsonl...] [--out 檔.html] [--kw 字]"""
    ap = argparse.ArgumentParser(prog="tw-crawler preview",
                                 description="把既有 jsonl 轉成單一 html 預覽檔")
    ap.add_argument("jsonl", nargs="+", help="既有的 .jsonl 檔（可多個）")
    ap.add_argument("--out", default=None, help="輸出 html 路徑（預設同檔名 .html）")
    ap.add_argument("--kw", default="", help="摘要顯示的關鍵字")
    args = ap.parse_args(argv)
    from .preview import render_preview
    out = render_preview(args.jsonl, out_path=args.out, kw=args.kw)
    print(f"→ 預覽 {out}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "preview":
        return _preview_args(argv[1:])
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sites = list_sites() if "all" in args.sites else sorted(set(args.sites))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")

    # --probe：只探 DOM，不抽欄位
    if args.probe:
        for site in sites:
            cfg = load_site(site)
            url = cfg["search_url"].format(kw=urllib.parse.quote(args.kw), n=args.n)
            print(f"[probe:{site}] {url}")
        return 0

    failures = []
    login_gated = [s for s in sites if load_site(s).get("login_required")]
    if login_gated and not args.i_understand_login_risk:
        print(LOGIN_WARNING)
        print(f"→ 未加 --i-understand-login-risk，跳過需登入站點："
              f"{'、'.join(login_gated)}")
        sites = [s for s in sites if s not in login_gated]
        if not sites:
            return 0
    elif login_gated:
        print(LOGIN_WARNING)
    for site in sites:
        print(f"== [{site}] {time.strftime('%H:%M:%S')}")
        result = crawl_site(site, args.kw, args.n, out_dir, args.cdp, args.probe,
                         save_html=args.save_html,
                         keep_author=args.keep_author)
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
        if result.get("error") in ("EMPTY", "RATE_LIMIT", "ERROR"):
            failures.append((site, result.get("error"), result.get("reason", "")))
        elif result["count"] and args.jsonl:
            fn = out_dir / f"{site}_{urllib.parse.quote(args.kw)[:24]}_{day}.jsonl"
            with fn.open("w", encoding="utf-8") as f:
                for item in result["items"]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"→ 存 {fn}（{result['count']} 筆）")
        if args.html and result["count"]:
            from .preview import render_html
            stamp = time.strftime("%Y%m%d_%H%M%S")
            html_fn = out_dir / f"{site}_{urllib.parse.quote(args.kw)[:24]}_{stamp}.html"
            html_fn.write_text(render_html(result["items"], kw=args.kw), encoding="utf-8")
            print(f"→ 預覽 {html_fn}")
    if failures:
        print("\n失敗站點：", "; ".join(f"{s}:{e}（{r}）" for s, e, r in failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
