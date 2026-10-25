# tw-community-crawler 🕷️

台灣常用社群 8 站關鍵字抓取方法彙整 —— 參考 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的專案寫法（平台模組化、設定集中），把「各站怎麼抓、結構長什麼样、板塊怎麼辨識」定義成可重用的腳本。

> ⚠️ 各站方法都是「某一天的實測定義」，網站一改版就可能作廢。所以腳本抓 0 筆時會回傳 `{'error':'EMPTY','probe':<頁面首兩行>}`，
> 讓你能立刻重探 DOM、修正腳本，而不是假裝流程永遠成立。

## 支援站點

| 站點 | 參數 | 登入 | 搜尋入口 | 結果結構 | 板塊辨識 |
|---|---|---|---|---|---|
| PTT | `ptt` | 免登入 | pttweb.cc 全站搜尋（Google CSE） | `a[href*="ptt.cc/bbs/.../M."]` | ✅ 網址內含看板名 |
| Mobile01 | `m01` | 免登入 | `googlesearch.php?query=` | `a[href*="topicdetail"]`（`searchresult.php` 已 404） | ⚠️ 板號藏在 `?f=<板>&t=<文章>` |
| Dcard | `dcard` | 免登入可讀 | `/search?query=` | `<article>` 卡片：[看板,作者,時間,標題,摘要]（未登入時 `<a>` href 渲染不出，別用連結抓） | ✅ 卡片第一行＝看板；路徑 `/f/<板>/p/<ID>` |
| Reddit | `reddit` | 免登入可讀 | `/search/?q=&sort=new` | `<shreddit-post>` 屬性優先；掛零時後備抓 `a[href*="/comments/"]` | ✅ subreddit 藏在 `/r/<板>/comments` |
| 巴哈動畫瘋 | `ani` | 免登入 | `search.php?keyword=`（純 XHR，要多等） | 無 `<a>`/data 屬性，靠 innerText 行錨點「年份：」上一行＝作品名 | 無板塊（動畫站，關鍵字宜挑番名） |
| X (Twitter) | `x` | **需登入** | `x.com/search?f=live&q=` | `<article>`（user/handle/時間/內文/status 連結） | 無 |
| Threads | `threads` | **需登入** | 首頁搜尋框 → `/search?q=&serp_type=default` | **無 `<article>`**：post 連結 `/@user/post/ID`，往內層祖先找文字卡片 | 無 |
| Instagram | `ig` | **需登入** | 單字→`/explore/tags/<字>/`；多字→首頁 feed（IG 無全文搜尋） | `<article>`＋`a[href*="/p/"]`，文案從 `img[alt]` 或行文字取 | 無 |

## 快速開始

1. 開一顆帶遠端偵錯的 Chrome，並在裡面把 X / Threads / IG 登入態留著：
   ```bash
   chrome --remote-debugging-port=9222 --user-data-dir=<你的 profile>
   ```
2. 安裝依賴：
   ```bash
   pip install playwright
   ```
3. 跑一把：
   ```bash
   python scripts/tw_forums.py ptt dcard --kw "AI Agent" --n 5
   python scripts/tw_forums.py all --kw "RTX Spark"          # 全部 8 站
   ```
   環境變數：`CRAWLER_CDP_URL`（預設 `http://127.0.0.1:9222`）、`CRAWLER_OUT_DIR`（輸出目錄，預設專案內 `output/`）。

## 輸出

每站一列 JSON：有結果時 `{count, items:[{title/board/user/link...}]}`；
抓 0 筆時 `{count:0, error:"EMPTY", probe:<首兩行DOM>, url}` —— probe 就是給你重探結構用的。
結果另存 `output/forums_<關鍵字>_<日期>.jsonl`。`samples/` 內附 2026-10-25 實測範例。

## 失效怎么修（本專案的核心精神）

1. 看到 `EMPTY` → 用瀏覽器開同一個 URL，看結果 DOM 换了什麼容器。
2. 只改對應站點函數的 selector/等待時間，不動其他站。
3. 修好後更新函數 docstring 的「最後驗證日期」。

## 免責

僅供學習與研究使用；請遵守各平台服務條款，控制頻率、勿大規模抓取。

## License

MIT
