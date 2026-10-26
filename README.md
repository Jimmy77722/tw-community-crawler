# tw-community-crawler

台灣常用社群關鍵字抓取方法彙整——參考 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的專案寫法（平台模組化、設定集中），把「各站怎麼抓、結構長什麼樣、板塊怎麼辨識」定義成可重用的腳本。**受 MediaCrawler 啟發，未包含其程式碼。**

> **⚠️ 使用警語與免責**
> - 本專案只內建**免登入的公開頁面**：PTT、Dcard、Reddit、Mobile01、巴哈動畫瘋。
> - 需登入三站（X、IG、Threads）**預設關閉**：加 `--i-understand-login-risk` 才跑，風險自負（見下方站點表）。
> - X（Twitter）、IG、Threads 等需登入平台，使用條款大多**禁止未經授權的自動抓取**；用帳號 cookie 抓取可能導致**帳號被限制或停用**。要合規取得 X 資料，建議用 **X 官方 API**。
> - 請自行遵守各站**服務條款與 robots.txt**，並保持限速。
> - 抓到的資料可能含**個人資料**：遵守個資法，不得用來識別、追蹤或騷擾個人，也不得轉售。
> - 本專案按現狀提供（MIT），作者不對使用後果負責。

> ⚠️ 各站方法都是「某一天的實測定義」，網站一改版就可能作廢。所以腳本抓 0 筆時會回傳 `{'error':'EMPTY','probe':<頁面首兩行>}`，
> 讓你能立刻重探 DOM、修正腳本，而不是假裝流程永遠成立。

## 支援站點（免登入 5 站＋需登入 3 站）

| 站點 | 參數 | 登入 | 搜尋入口 | 結果結構 | 板塊辨識 |
|---|---|---|---|---|---|
| PTT | `ptt` | 免登入 | pttweb.cc 全站搜尋（Google CSE） | `a[href*="ptt.cc/bbs/.../M."]` | ✅ 網址內含看板名 |
| Mobile01 | `m01` | 免登入 | `googlesearch.php?query=` | `a[href*="topicdetail"]`（`searchresult.php` 已 404） | ⚠️ 板號藏在 `?f=<板>&t=<文章>` |
| Dcard | `dcard` | 免登入可讀 | `/search?query=` | `<article>` 卡片：[看板,作者,時間,標題,摘要]（未登入時 `<a>` href 渲染不出，別用連結抓） | ✅ 卡片第一行＝看板；路徑 `/f/<板>/p/<ID>` |
| Reddit | `reddit` | 免登入可讀 | `/search/?q=&sort=new` | `<shreddit-post>` 屬性優先；掛零時後備抓 `a[href*="/comments/"]` | ✅ subreddit 藏在 `/r/<板>/comments` |
| 巴哈動畫瘋 | `ani` | 免登入 | `search.php?keyword=`（純 XHR，要多等） | 無 `<a>`/data 屬性，靠 innerText 行錨點「年份：」上一行＝作品名 | 無板塊（動畫站，關鍵字宜挑番名） |
| X（Twitter） | `x` | **需登入・預設關閉・風險自負** | `x.com/search?q=&f=live`（你自己的已登入 Chrome） | `article` 卡片 innerText：[@帳號,顯示名,時間,推文…] | 推板無板塊 |
| Instagram | `ig` | **需登入・預設關閉・風險自負** | `/explore/tags/<標籤>/`（關鍵字挑單字標籤） | 網格卡片 innerText：[按讚,留言,時間,內文…] | 標籤頁 |
| Threads | `threads` | **需登入・預設關閉・風險自負** | `threads.com/search?q=` | `article` 卡片 innerText：[@帳號,顯示名,時間,貼文…] | 搜尋頁 |

> 需登入三站走 `--cdp` 接上**你自己已經登入的 Chrome**：程式不碰帳密、不寫登入流程、
> 不讀 cookie 檔。不加 `--i-understand-login-risk` 不會執行（印警語後結束）。
> 限速從嚴（至少 10 秒一次、`--n` 上限 50），遇驗證碼／登入牆／429 立刻停下不繞過。
> 作者欄預設雜湊成 `user_<hash8>`（`--keep-author` 保留原樣），不存頭像與個人頁網址。
> X 建議改用官方 API；若收到平台移除要求，作者會配合下架。

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

## HTML 預覽

```bash
tw-crawler ptt reddit --kw "AI Agent" --n 10 --html    # 抓完直接產 <站>_<關鍵字>_<時間>.html
tw-crawler preview output/ptt_AI.jsonl --out 預覽.html  # 既有 jsonl 隨時轉 html
```

- 單一 html 檔、CSS/JS 全內嵌、不連外部 CDN，離線雙擊就能開。
- 上方摘要（關鍵字、各站筆數、抓取時間），下方每篇一張卡片：站名、標題、時間、
  內文前 150 字、原文連結（新分頁開）。
- 站名篩選與關鍵字搜尋是純前端 JS，資料內嵌在頁面裡。
- 所有文字經 HTML escape：抓回來的內容不會在頁面上變成可執行的程式碼。
- 範例見 `samples/preview_example.html`。

## 禮貌爬取

- 限速：每次請求（含開瀏覽器頁面前）同站隨機等 2–5 秒；站點可在 yaml 用 `rate_limit: [lo, hi]` 覆寫。
- 單次上限：結果筆數取 `--n` 與站點 `max_items` 中較嚴者。
- 遇到 429、403、「暫時限制」或驗證頁：該站立即禮貌停止並回報 `RATE_LIMIT`，不重試硬闖（只有瞬時傳輸錯誤才指數退避）。
- 不做 UA 偽裝、不隱藏 webdriver；UA 是誠實可辨識的字串：`tw-community-crawler/<版本> (+repo 網址)`，方便站方辨識與聯絡。

## 失效怎麼修（本專案的核心精神）

1. 看到 `EMPTY` → 加 `--save-html` 重跑，或直接開 `sites/<站>.yaml` 附的 `search_url`，看 DOM 換了什麼容器。
2. 只改對應站的 `sites/<站>.yaml`（網址樣板、method、選擇器、欄位對應），不動程式和其他站。
3. 修好後更新該站的實測備註。

## 測試（離線）

```bash
pip install -e ".[dev]"
python -m pytest -q
```

- 測試全部離線：parse／http／crawler 三層吃 `tests/fixtures/` 樣板，不打任何真實站點，也不開瀏覽器。
- Reddit `search.json` 對本機 IP 常 403，故用 fixture 離線驗證欄位對應（`data.*` 路徑、`id_prefix`、epoch→台北時間）。
- GitHub Actions（`.github/workflows/ci.yml`）同樣只跑離線測試，Python 3.10／3.13 雙版本矩陣。

## samples/

各站輸出的範例（每行一筆 JSON）。全部已去識別化：虛構帳號（user_1）、虛構內文、虛構連結，
不含任何真實帳號、貼文全文或個人資訊。

## 外掛開發

本專案不靠 Python plugin 註冊表：**一站一支 `sites/<站>.yaml`**（method／search_url／extract 規則）。
新增站点＝加 yaml＋fixtures＋假樣本，主程式不動。細節見 `docs/plugins.md`。

## 常見問題

- **抓到 0 筆（`EMPTY`）**：網站改版了。結果會附 `probe`（頁面首兩行）；加 `--save-html`
  重跑對照 DOM，只修該站 yaml 的選擇器／規則，不動程式。
- **403（Mobile01、Reddit 常見）**：站方擋資料中心 IP 或防爬。腳本會禮貌停止並回報
  `RATE_LIMIT`，**不重試硬闖**；換住宅 IP／时段再跑，Reddit 亦可先用 fixtures 驗證欄位。
- **429**：短時間請求太密。拉大 `rate_limit`、減 `--n`、避開尖峰；同站两次請求間必等 2–5 秒。

## 免責

僅供學習與研究使用；詳情見開頭警語與 `docs/plugins.md`。

## License

MIT
