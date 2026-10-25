# -*- coding: utf-8 -*-
"""各 method 的 parse 層：輸入原始 HTML／JSON／瀏覽器文字，輸出 Post 列表。
離線可測（tests/ 用 fixtures 打這層），網路層不摻進來。"""
from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Iterable

from selectolax.lexbor import LexborHTMLParser

from .schema import TZ_TAIPEI, Post, now_iso


def _iso(epoch_value) -> str | None:
    """epoch 秒 → ISO 8601（Asia/Taipei）。"""
    if epoch_value is None:
        return None
    try:
        return dt.datetime.fromtimestamp(float(epoch_value), TZ_TAIPEI).isoformat(timespec="seconds")
    except (ValueError, TypeError, OSError):
        return None


def parse_html(site: str, cfg: dict, html: str) -> list[Post]:
    """rule=link：從 <a href> 列表挑連結，正则抽 id／看板。PTT、Mobile01 走這。"""
    ex = cfg["extract"]
    assert ex["rule"] == "link", f"{site} 的 extract.rule 應為 link"
    parser = LexborHTMLParser(html)
    seen: set[str] = set()
    posts: list[Post] = []
    id_re = re.compile(ex.get("id_regex") or "x^")
    url_re = re.compile(ex.get("url_regex") or "$^")
    board_re = re.compile(ex.get("board_regex") or "(?!)")
    for a in parser.css(ex["container"]):
        href = a.attributes.get("href") or ""
        want = ex.get("link_filter", "")
        if want and want not in href:
            continue
        m_id = id_re.search(href)
        if not m_id:
            continue
        m_url = url_re.search(href)
        if m_url:
            url = m_url.group(1)
        elif href.startswith("http"):
            url = href
        else:
            # 相對 href 用 base_url 組絕對網址（不用登入也不怕 cookie）
            base = ex.get("base_url")
            if base:
                url = base.rstrip("/") + ("/" + href.lstrip("/"))
            else:
                url = href
        title = (a.text(strip=True) or "").strip()
        if not title:
            continue
        m_board = board_re.search(href)
        board = m_board.group(1) if m_board else None
        post_id = m_id.group(1)
        if post_id in seen:
            continue
        seen.add(post_id)
        posts.append(Post(
            site=site, id=post_id, title=title, url=url,
            author=board,           # link 規則的 board 借 author 欄顯示（PTT 看板／M01 板號）
            time=None, text=None,
            fetched_at=now_iso(),
        ))
        if len(posts) >= cfg.get("max_items", 20):
            break
    return posts


def _dig(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def parse_json(site: str, cfg: dict, data: dict) -> list[Post]:
    """rule=json：沿 items_path 取陣列，fields 對位。Reddit 走這。"""
    ex = cfg["extract"]
    assert ex["rule"] == "json"
    items = _dig(data, ex["items_path"]) or []
    posts: list[Post] = []
    prefix = ex.get("id_prefix", "")
    for it in items:
        f = ex["fields"]
        title = _dig(it, f["title"]) or ""
        url = _dig(it, f.get("url", "url")) or ""
        if f.get("url_base") and url.startswith("/"):
            url = f["url_base"].rstrip("/") + url
        pid = str(_dig(it, f["id"]) or "")
        if not title or not pid:
            continue
        posts.append(Post(
            site=site, id=prefix + pid,
            author=_dig(it, f.get("author", "author")),
            time=_iso(_dig(it, ex.get("time_field", "created_utc"))),
            title=str(title), text=(_dig(it, f.get("text", "text")) or None),
            url=url,
            likes=(int(_dig(it, f["likes"])) if f.get("likes") and _dig(it, f["likes"]) is not None else None),
            comments=(int(_dig(it, f["comments"])) if f.get("comments") and _dig(it, f["comments"]) is not None else None),
            fetched_at=now_iso(),
        ))
        if len(posts) >= cfg.get("max_items", 20):
            break
    return posts


def parse_text_rule(site: str, cfg: dict, texts: list[str]) -> list[Post]:
    """rule=text-rule：站點無 href／無属性（Dcard 無登入態、ani 純渲染）時的後備。
    texts = 每container的 innerText 切行后的 list。由 crawl_browser 負責餵。"""
    ex = cfg["extract"]
    assert ex["rule"] == "text-rule"
    posts: list[Post] = []
    pat = ex.get("row_pattern")
    anchor = ex.get("anchor_line")
    for block in texts:
        lines = [ln for ln in (x.strip() for x in block.splitlines()) if ln]
        if pat:
            m = re.search(pat, "\n".join(lines), re.S)
            if m:
                f = ex["fields"]
                board = m.group(f.get("board", 1))
                author = m.group(f.get("author", 2))
                rest = m.group(4) if f.get("title") == "$rest-first" else m.group(f.get("title", 4))
                rest_lines = rest.splitlines() or [""]
                title = rest_lines[0].strip() or "(無標題)"
                text = " ".join(rest_lines[1:]).strip() or None
                pid = f"{site}-" + re.sub(r"\W+", "", title)[:24]
                posts.append(Post(site=site, id=pid, author=author, title=title,
                                  text=text, url=f"https://www.dcard.tw", fetched_at=now_iso()))
        elif anchor:
            are = re.compile(anchor)
            for i, ln in enumerate(lines):
                if are.search(ln) and i > 0:
                    title = lines[i - 1]
                    pid = f"{site}-" + re.sub(r"\W+", "", title)[:24]
                    posts.append(Post(site=site, id=pid, author=None, title=title,
                                      text=ln, url="https://ani.gamer.com.tw", fetched_at=now_iso()))
                    break
        if len(posts) >= cfg.get("max_items", 20):
            break
    # 站內去重（同 id 保留第一筆）
    uniq: dict[str, Post] = {}
    for p in posts:
        uniq.setdefault(p.id, p)
    return list(uniq.values())
