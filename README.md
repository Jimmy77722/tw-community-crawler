# tw-community-crawler

台灣常用社群關鍵字抓取方法彙整——參考 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的專案寫法（平台模組化、設定集中），把「各站怎麼抓、結構長什麼樣、板塊怎麼辨識」定義成可重用的腳本。**受 MediaCrawler 啟發，未包含其程式碼。**

> ⚠️ 各站方法都是「某一天的實測定義」，網站一改版就可能作廢。所以腳本抓 0 筆時會回傳 `{'error':'EMPTY','probe':<頁面首兩行>}`，
> 讓你能立刻重探 DOM、修正腳本，而不是假裝流程永遠成立。

## 支援站點（免登入 5 站）

| 站點 | 參數 | 登入 | 搜尋入口 | 結果結構 | 板塊辨識 |
|---|---|---|---|---|---|
| PTT | `ptt` | 免登入 | pttweb.cc 全站搜尋（Google CSE） | `a[href*="ptt.cc/bbs/.../M."]` | ✅ 網址內含看板名 |
| Mobile01 | `m01` | 免登入 | `googlesearch.php?query=` | `a[href*="topicdetail"]`（`searchresult.php` 已 404） | ⚠️ 板號藏在 `?f=<板>&t=<文章>` |
| Dcard | `dcard` | 免登入可讀 | `/search?query=` | `<article>` 卡片：[看板,作者,時間,標題,摘要]（未登入時 `<a>` href 渲染不出，別用連結抓） | ✅ 卡片第一行＝看板；路徑 `/f/<板>/p/<ID>` |
| Reddit | `reddit` | 免登入可讀 | `/search/?q=&sort=new` | `<shreddit-post>` 屬性優先；掛零時後備抓 `a[href*="/comments/"]` | ✅ subreddit 藏在 `/r/<板>/comments` |
| 巴哈動畫瘋 | `ani` | 免登入 | `search.php?keyword=`（純 XHR，要多等） | 無 `<a>`/data 屬性，靠 innerText 行錨點「年份：」上一行＝作品名 | 無板塊（動畫站，關鍵字宜挑番名） |

> X（Twitter）、Threads、Instagram 需登入才能完整抓取，屬本機版另行維護的站點，
> 本公開版不提供登入站抓取教學。

## 快速開始

1. 安裝（含瀏覽器站的額外依賴）：
   ```bash
   pip install -e ".[browser]"
   ```
2. 只有 `method: browser` 的站（Dcard、ani）需要一顆帶遠端偵錯的 Chrome：
   ```bash
   chrome --remote-debugging-port=9222 --user-data-dir=<你的 profile>
   ```
3. 跑一把：
   ```bash
   tw-crawler ptt reddit --kw "AI Agent" --n 10
   tw-crawler all --kw "RTX Spark" --cdp http://127.0.0.1:9222
   ```
   環境變數：`CRAWLER_CDP_URL`（預設 `http://127.0.0.1:9222`）。

## 輸出

每站結果印在終端機；有結果時 `{site, count, items:[...]}`，
每筆 item 過 pydantic 驗證的統一欄位：`site id author time title text url likes comments fetched_at`
（time＝ISO 8601 台灣時區）。依 `site+id` 站內去重。
抓 0 筆時回 `{count:0, error:"EMPTY", probe:<首兩行DOM>}`——probe 就是給你重探結構用的。
結果另存 `output/<站>_<關鍵字>_<日期>.jsonl`（一行一筆；輸出目錄不進版控）。`samples/` 附輸出範例。

## 失效怎麼修（本專案的核心精神）

1. 看到 `EMPTY` → 加 `--save-html` 重跑，或直接開 `sites/<站>.yaml` 附的 `search_url`，看 DOM 換了什麼容器。
2. 只改對應站的 `sites/<站>.yaml`（網址樣板、method、選擇器、欄位對應），不動程式和其他站。
3. 修好後更新該站的實測備註。

## samples/

各站輸出的範例（每行一筆 JSON）。全部已去識別化：虛構帳號（user_1）、虛構內文、虛構連結，
不含任何真實帳號、貼文全文或個人資訊。

## 免責

僅供學習與研究使用；請遵守各平台服務條款，控制頻率、勿大規模抓取。

## License

MIT
