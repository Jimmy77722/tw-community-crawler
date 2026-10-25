# -*- coding: utf-8 -*-
"""站點設定載入：sites/<站名>.yaml → dict。DOM 失效時只改 yaml，不改程式。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"


def load_site(name: str) -> dict:
    path = SITES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"找不到站點設定：{path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert cfg.get("site") == name, f"{path} 的 site 欄位應對應檔名"
    return cfg


def list_sites() -> list[str]:
    return sorted(p.stem for p in SITES_DIR.glob("*.yaml"))
