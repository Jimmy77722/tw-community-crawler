# -*- coding: utf-8 -*-
"""統一輸出 schema：每站每筆結果都要過這個模型（pydantic 驗證）。"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, field_validator

TZ_TAIPEI = dt.timezone(dt.timedelta(hours=8), name="Asia/Taipei")


class Post(BaseModel):
    site: str
    id: str
    author: Optional[str] = None
    time: Optional[str] = None          # ISO 8601（Asia/Taipei）
    title: str
    text: Optional[str] = None
    url: str
    likes: Optional[int] = None
    comments: Optional[int] = None
    fetched_at: str                     # 抓取代当下時間（ISO 8601）

    @field_validator("time")
    @classmethod
    def _time_iso_taipei(cls, v):
        if v in (None, ""):
            return None
        try:
            parsed = dt.datetime.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"time 需為 ISO 8601：{v!r}（{e}）")
        return parsed.astimezone(TZ_TAIPEI).isoformat()

    @field_validator("url")
    @classmethod
    def _url_absolute(cls, v):
        if v.startswith("//"):
            return "https:" + v
        assert v.startswith("http"), f"url 需為絕對網址：{v!r}"
        return v

    def key(self):
        """站內去重鍵：site + id。"""
        return (self.site, self.id)


def now_iso() -> str:
    return dt.datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
