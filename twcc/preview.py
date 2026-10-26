# -*- coding: utf-8 -*-
"""HTML 預覽輸出：把抓到的結果（或既有 jsonl）轉成單一 html 檔。

- 單一檔案、零外部依賴（CSS/JS 內嵌），離線可開。
- 所有文字一律 html.escape；連結用新分頁開。
- 站名篩選＋關鍵字搜尋是純前端 JS，資料內嵌在頁面裡。

外掛介面（本專案的「外掛」＝站點定義）：
每個站一個 sites/<站>.yaml（method／search_url／extract 規則），
解析器只認三種 rule：link／json／text-rule（見 twcc/parsers.py）。
新增一站＝加一支 yaml＋（必要時）samples 假資料，不改主程式。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

TEXT_SNIPPET = 150       # 卡片摘要截斷長度

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tw-crawler 預覽 __TITLE__</title>
<style>
:root { color-scheme: light dark; }
body { font-family: system-ui, "Microsoft JhengHei", sans-serif;
       margin: 0; padding: 1.2rem; max-width: 880px; margin-inline: auto; }
h1 { font-size: 1.2rem; margin: 0 0 .4rem; }
.summary { font-size: .9rem; opacity: .85; margin-bottom: .6rem; }
.summary span { margin-right: .9rem; }
.controls { position: sticky; top: 0; background: Canvas; padding: .5rem 0;
            display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
            border-bottom: 1px solid rgba(128,128,128,.3); }
.controls input { flex: 1 1 12rem; padding: .35rem .5rem; }
.chip { border: 1px solid rgba(128,128,128,.5); border-radius: 999px;
        padding: .15rem .6rem; cursor: pointer; font-size: .85rem; user-select: none; }
.chip.off { opacity: .35; text-decoration: line-through; }
.card { border: 1px solid rgba(128,128,128,.35); border-radius: .5rem;
        padding: .7rem .8rem; margin: .6rem 0; }
.card .meta { font-size: .8rem; opacity: .75; display: flex; flex-wrap: wrap; gap: .6rem; }
.card h2 { font-size: 1rem; margin: .3rem 0; }
.card .snippet { font-size: .9rem; white-space: pre-line; }
.badge { font-size: .75rem; border: 1px solid currentColor; border-radius: .3rem;
         padding: 0 .35rem; }
a { text-decoration: none; }
.hidden { display: none; }
#count { font-size: .85rem; opacity: .7; margin-top: .5rem; }
</style>
</head>
<body>
<h1>tw-crawler 預覽</h1>
<div class="summary">__SUMMARY__</div>
<div class="controls">
  <input id="q" type="search" placeholder="關鍵字搜尋（標題＋內文）" data-default-site="全部">
  <span id="chips"></span>
</div>
<div id="count"></div>
<div id="cards">__CARDS__</div>
<script>
(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var chipsBox = document.getElementById('chips');
  var q = document.getElementById('q');
  var all = '全部';
  var site = all;
  var sites = {};
  cards.forEach(function (c) { sites[c.dataset.site] = (sites[c.dataset.site] || 0) + 1; });
  function chip(label) {
    var el = document.createElement('span');
    el.className = 'chip'; el.textContent = label; el.dataset.site = label;
    el.addEventListener('click', function () {
      site = label;
      Array.prototype.forEach.call(chipsBox.children, function (ch) {
        ch.classList.toggle('off', ch.dataset.site !== label);
      });
      apply();
    });
    chipsBox.appendChild(el);
  }
  chip(all);
  Object.keys(sites).sort().forEach(function (s) { chip(s + '（' + sites[s] + '）'); });
  function apply() {
    var kw = q.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {
      var okSite = site === all || c.dataset.site === site;
      var okKw = !kw || c.dataset.hay.indexOf(kw) !== -1;
      var show = okSite && okKw;
      c.classList.toggle('hidden', !show);
      if (show) shown++;
    });
    document.getElementById('count').textContent =
      '顯示 ' + shown + ' / ' + cards.length + ' 筆';
  }
  q.addEventListener('input', apply);
  apply();
})();
</script>
</body>
</html>
"""


def _esc(v) -> str:
    return html.escape(str(v), quote=True)


def load_jsonl(path) -> list[dict]:
    """讀 jsonl：空白行跳過，坏行（非 JSON）跳過；其餘照統一 schema 收下。"""
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("site") and obj.get("url"):
            items.append(obj)
    return items


def _card(item: dict) -> str:
    site = _esc(item.get("site", ""))
    title = _esc(item.get("title") or "(無標題)")
    text = (item.get("text") or "")[:TEXT_SNIPPET]
    meta = [f'<span class="badge">{site}</span>']
    if item.get("author"):
        meta.append(f"作者:{_esc(item['author'])}")
    if item.get("time"):
        meta.append(f"時間:{_esc(item['time'])}")
    if isinstance(item.get("likes"), int):
        meta.append(f"讚:{item['likes']}")
    if isinstance(item.get("comments"), int):
        meta.append(f"留言:{item['comments']}")
    hay = _esc(" ".join(str(item.get(k) or "") for k in ("site", "title", "text", "author")).lower())
    url = _esc(item.get("url", ""))
    return (f'<article class="card" data-site="{site}" data-hay="{hay}">'
            f'<div class="meta">{" ".join(meta)}</div>'
            f'<h2><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>'
            f'<div class="snippet">{_esc(text)}</div></article>')


def render_html(items: list[dict], *, kw: str = "", title_suffix: str = "") -> str:
    """結果筆列表（已驗證 dict）→ 完整 HTML 字串。全部文字經 escape。"""
    import datetime as dt
    per_site: dict[str, int] = {}
    dates = set()
    for it in items:
        per_site[it.get("site", "?")] = per_site.get(it.get("site", "?"), 0) + 1
        if it.get("fetched_at"):
            dates.add(str(it["fetched_at"])[:10])
    gen = dt.datetime.now(dt.timezone(dt.timedelta(hours=8), name="Asia/Taipei"))
    parts = []
    if kw:
        parts.append(f"關鍵字:<b>{_esc(kw)}</b>")
    parts.append("筆數:" + _esc(
        ", ".join(f"{s} {n}" for s, n in sorted(per_site.items())) or "（空）"))
    if dates:
        parts.append("抓取日:" + _esc(", ".join(sorted(dates))))
    parts.append(f"產生時間:{_esc(gen.isoformat(timespec='seconds'))}")
    summary = "".join(f"<span>{p}</span>" for p in parts)
    cards = "\n".join(_card(it) for it in items)
    suffix = f" {title_suffix}" if title_suffix else ""
    return (_TEMPLATE.replace("__TITLE__", _esc(f"{kw}{suffix}").strip() or "結果")
                   .replace("__SUMMARY__", summary)
                   .replace("__CARDS__", cards))


def render_preview(jsonl_paths, out_path: Path | None = None, kw: str = "") -> Path:
    """一個或多個 jsonl → 單一 html。回傳寫出路径。"""
    if isinstance(jsonl_paths, (str, Path)):
        jsonl_paths = [jsonl_paths]
    items = []
    for p in jsonl_paths:
        items.extend(load_jsonl(p))
    out = Path(out_path) if out_path else Path(jsonl_paths[0]).with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(items, kw=kw), encoding="utf-8")
    return out
