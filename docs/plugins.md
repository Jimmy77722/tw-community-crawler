# 外掛開發（站點定義）

本專案的「外掛」不是 Python plugin 註冊表，而是**站點定義檔**：
每支援一個站，就在 `sites/<站>.yaml` 描述它的搜尋網址與抽取規則；主程式不動。

新增一站的步驟：

1. 開 `sites/<新站>.yaml`，填：
   - `method`：`api`（httpx 直取 HTML/JSON）或 `browser`（需要帶 CDP 的 Chrome）。
   - `search_url`：含 `{kw}`（自動 quote 編碼）與 `{n}` 的網址樣板。
   - `extract.rule`：三種之一——
     - `link`：结果是一串 `<a href>`（PTT、Mobile01）。配 `container` 選擇器、
       `link_filter`、`id_regex`、`url_regex`、`board_regex`（板塊辨識）。
     - `json`：结果是 JSON API（Reddit）。`list_path`／`fields` 都是點點路徑
       （Reddit 注意 `data.` 前綴）。
     - `text-rule`：無穩定選擇器，靠 innerText 行模式（Dcard 卡片、ani 锚點行）。
   - 可選 `rate_limit: [lo, hi]` 覆寫預設隨機限速 2–5 秒。
2. 依序跑 `tw-crawler <新站> --kw <字> --save-html`，看是否抓到；抓 0 筆就照
   `EMPTY` 的 probe 輸出調整 yaml。
3. 在 `tests/fixtures/` 放一份該站的離線樣板，加對應 parser 測試。
4. `samples/sample_<站>.jsonl` 放兩筆**假資料**（作者 user_1、假內文、假連結）。

## 警語與免責（與 README 相同）

- 本專案只內建**免登入的公開頁面**：PTT、Dcard、Reddit、Mobile01、巴哈動畫瘋。
- X（Twitter）、IG、Threads 等**需要登入**的平台，使用條款大多禁止未經授權的
  自動抓取；使用帳號 cookie 抓取可能導致**帳號被限制或停用**。
- 如果要合規取得 X 的資料，建議使用 **X 官方 API**。
- 使用者要自行遵守各站的**服務條款與 robots.txt**，並保持限速。
- 抓取的資料可能含有**個人資料**：使用時要遵守個資法，不得用來識別、追蹤或
  騷擾個人，也不得轉售。
- 本專案按現狀提供（MIT），作者不對使用後果負責。
