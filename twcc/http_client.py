# -*- coding: utf-8 -*-
"""誠實禮貌的 HTTP 層：隨機限速、tenacity 指數退避、429/403/驗證頁就停。"""
from __future__ import annotations

import random
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 誠實可辨識的 UA（不做指紋偽裝）
UA = "tw-community-crawler/0.2 (+https://github.com/Jimmy77722/tw-community-crawler)"

# 站域名單次呼叫间的限速狀態
_last_call: dict[str, float] = {}
# 遇到限速/封鎖就停止該站：這些情況不重試硬闖
STOP_MARKERS = (" temporarily blocked", "are you a robot", "captcha", "暫時限制")


class RateLimited(RuntimeError):
    """429/403/驗證頁：該站暫停，不重試硬闖。"""

    def __init__(self, site: str, status: int, hint: str = ""):
        super().__init__(f"[{site}] HTTP {status}{'：' + hint if hint else ''}")
        self.site, self.status = site, status


def _sleep_gap(site: str, lo: float, hi: float) -> None:
    """每次請求前隨機等 lo~hi 秒（同站相對於上次呼叫）。"""
    last = _last_call.get(site, 0.0)
    gap = random.uniform(lo, hi)
    wait = max(0.0, last + gap - time.monotonic())
    time.sleep(wait)


def polite_gap(site: str, rate: tuple[float, float]) -> None:
    """瀏覽器路徑用的禮貌等待：先等限速間隔，再登記本次呼叫時間。"""
    _sleep_gap(site, *rate)
    _last_call[site] = time.monotonic()


@retry(
    retry=retry_if_exception_type((httpx.TransportError,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _do_get(url: str, headers: dict, timeout: float) -> httpx.Response:
    return httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)


DEFAULT_RATE = (2.0, 5.0)  # 預設禮貌限速：每次請求間隔 2–5 秒隨機，sites yaml 可用 rate_limit 覆寫


def polite_get(site: str, url: str, headers: dict | None = None,
               rate: tuple[float, float] = DEFAULT_RATE, timeout: float = 20.0) -> httpx.Response:
    """唯一進出口：限速 → 請求（瞬時錯誤退避重試）→ 限速/驗證頁丟 RateLimited。"""
    _sleep_gap(site, *rate)
    h = {"User-Agent": UA, "Accept-Language": "zh-TW", "Accept": "*/*"}
    if headers:
        h.update(headers)
    _last_call[site] = time.monotonic()
    resp = _do_get(url, h, timeout)
    low = resp.text.lower() if len(resp.text) < 200_000 else resp.text[:5000].lower()
    if resp.status_code == 429:
        raise RateLimited(site, 429, "請求太頻繁")
    if resp.status_code == 403:
        raise RateLimited(site, 403, "被擋（可能需登入或驗證）")
    if resp.status_code == 200 and any(m in low for m in STOP_MARKERS):
        raise RateLimited(site, 200, "驗證頁／暫時限制")
    return resp
