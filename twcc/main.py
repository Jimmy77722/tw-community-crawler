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

from .config import list_sites
from .crawler import crawl_site

DEFAULT_CDP = os.environ.get("CRAWLER_CDP_URL", "http://127.0.0.1:9222")


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
    ap.add_argument("--jsonl", action="store_true", default=True,
                    help="結果寫 <站>_關鍵詞_日付.jsonl（預設開）")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sites = list_sites() if "all" in args.sites else sorted(set(args.sites))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")

    # --probe：只探 DOM，不抽欄位
    if args.probe:
        from .config import load_site
        for site in sites:
            cfg = load_site(site)
            url = cfg["search_url"].format(kw=urllib.parse.quote(args.kw), n=args.n)
            print(f"[probe:{site}] {url}")
        return 0

    failures = []
    for site in sites:
        print(f"== [{site}] {time.strftime('%H:%M:%S')}")
        result = crawl_site(site, args.kw, args.n, out_dir, args.cdp, args.probe,
                         save_html=args.save_html)
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
        if result.get("error") in ("EMPTY", "RATE_LIMIT", "ERROR"):
            failures.append((site, result.get("error"), result.get("reason", "")))
        elif result["count"] and args.jsonl:
            fn = out_dir / f"{site}_{urllib.parse.quote(args.kw)[:24]}_{day}.jsonl"
            with fn.open("w", encoding="utf-8") as f:
                for item in result["items"]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"→ 存 {fn}（{result['count']} 筆）")
    if failures:
        print("\n失敗站點：", "; ".join(f"{s}:{e}（{r}）" for s, e, r in failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
