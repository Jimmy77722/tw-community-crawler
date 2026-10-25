# -*- coding: utf-8 -*-
"""schema 層離線測試：統一欄位驗證、時區、絕對網址。"""
import pytest
from pydantic import ValidationError

from twcc.schema import Post, now_iso


def make_post(**over):
    base = dict(site="ptt", id="M.1", title="標題", url="https://ptt.cc/x",
                fetched_at="2026-10-25T00:00:00+08:00")
    base.update(over)
    return Post(**base)


def test_fetched_at_required():
    from pydantic import BaseModel
    with pytest.raises(ValidationError):
        Post(site="ptt", id="M.1", title="t", url="https://ptt.cc/x")


def test_minimal_post():
    p = make_post()
    assert p.author is None and p.time is None and p.text is None
    assert p.likes is None and p.comments is None


def test_url_protocol_relative_made_absolute():
    p = make_post(url="//www.reddit.com/r/x")
    assert p.url == "https://www.reddit.com/r/x"


def test_url_must_be_absolute():
    with pytest.raises(ValidationError):
        make_post(url="/relative/path")


def test_time_normalized_to_taipei():
    p = make_post(time="2026-01-01T02:00:00+00:00")
    assert p.time == "2026-01-01T10:00:00+08:00"


def test_time_rejects_garbage():
    with pytest.raises(ValidationError):
        make_post(time="not-a-date")


def test_time_none_allowed():
    assert make_post(time=None).time is None
    assert make_post(time="").time is None


def test_key_is_site_plus_id():
    assert make_post().key() == ("ptt", "M.1")


def test_now_iso_has_taipei_offset():
    assert now_iso().endswith("+08:00")
