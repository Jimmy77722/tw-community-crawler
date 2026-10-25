# -*- coding: utf-8 -*-
"""config 層離線測試：站點 yaml 載入、站名對應、全部 yaml 结构一致。"""
import pytest

from twcc.config import SITES_DIR, list_sites, load_site

EXPECTED_SITES = ["ani", "dcard", "m01", "ptt", "reddit"]


def test_list_sites():
    assert list_sites() == EXPECTED_SITES


def test_load_site_matches_filename():
    for name in list_sites():
        cfg = load_site(name)
        assert cfg["site"] == name


def test_load_site_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("twcc.config.SITES_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_site("nope")


def test_site_yaml_shape():
    """五站 yaml 都要有 method／search_url／extract.rule，method 限三种。"""
    for name in list_sites():
        cfg = load_site(name)
        assert cfg["method"] in ("api", "html", "browser"), name
        assert "{kw}" in cfg["search_url"], f"{name} search_url 要有 {{kw}} 樣板"
        assert cfg["extract"]["rule"] in ("link", "json", "text-rule"), name


def test_rate_limit_bounds():
    """rate_limit 若設定需為 [lo, hi] 兩個正數且 lo<=hi。"""
    for name in list_sites():
        rate = load_site(name).get("rate_limit")
        if rate is not None:
            assert len(rate) == 2 and 0 < rate[0] <= rate[1], name
