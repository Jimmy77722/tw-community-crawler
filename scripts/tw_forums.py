"""
台灣常用社群 8 站 keyword 抓取器（Playwright over CDP，接一顆已登入的 Chrome）
支援站點：reddit dcard ani ptt m01 x threads ig（含 all）
Each site's method was verified on 2026-10-25; sites update, so treat methods as
provisional — every fetcher returns {'error':'EMPTY','probe':<首兩行DOM>} on zero
results, so you can re-probe the live DOM and patch this file instead of trusting
a fixed flow.
用法：
  python tw_forums.py [站點...] [--kw "關鍵字"] [--n 3]
  例：python tw_forums.py ptt dcard --kw "AI Agent" --n 5
前提：先開一顆帶 --remote-debugging-port 的 Chrome（各站登入態存在該 profile），
  並 set CRAWLER_CDP_URL=http://127.0.0.1:<port>（預設 9222）。
各站方法與板塊辨識（2026-10-25 實測）見 README.md。
"""
import sys, os, json, asyncio
from playwright.async_api import async_playwright

# ==========================================
# Config（集中設定，改這裡就好）
# ==========================================
CDP_URL = os.environ.get("CRAWLER_CDP_URL", "http://127.0.0.1:9222")
OUT_DIR = os.environ.get("CRAWLER_OUT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"))

KW_DEFAULT = "RTX Spark"  # 可自行指定關鍵字

# ---------- 各站抓取 ----------
async def reddit(pg, kw, n):
    await pg.goto(f"https://www.reddit.com/search/?q={kw.replace(' ','%20')}&sort=new", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(5000)
    for _ in range(3):
        await pg.mouse.wheel(0, 2200); await pg.wait_for_timeout(1500)
    items = await pg.evaluate("""(n) => {
        const posts=[...document.querySelectorAll('shreddit-post')];
        if (posts.length) return posts.slice(0,n).map(p => ({
            title:(p.getAttribute('post-title')||'').trim(), sub:(p.getAttribute('subreddit-prefixed-name')||'').trim(),
            date:(p.getAttribute('created-timestamp')||'').slice(0,10), link:location.origin+(p.getAttribute('permalink')||'')}));
        // 後備：新搜尋頁以連結清單呈現結果 —— 抓 r/<sub>/comments/ 模式
        const seen=new Set(), out=[];
        for (const a of document.querySelectorAll('a[href*="/comments/"]')) {
            const t=(a.innerText||'').trim().split(String.fromCharCode(10))[0];
            if (t.length>8 && !seen.has(a.href)) { seen.add(a.href);
                const sm=(a.getAttribute('href')||'').match(/\/r\/([A-Za-z0-9_]+)\/comments/);
                out.push({title:t.slice(0,90), sub: sm?('r/'+sm[1]):'', date:'', link:a.href}); }
            if (out.length>=n) break;
        }
        return out;
    }""", n)
    return items

async def dcard(pg, kw, n):
    await pg.goto(f"https://www.dcard.tw/search?query={kw.replace(' ','%20')}", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(6000)
    return await pg.evaluate("""(n) => {
        const NL=String.fromCharCode(10);
        const out=[];
        for (const a of document.querySelectorAll('article')) {
            const lines=(a.innerText||'').split(NL).map(x=>x.trim()).filter(Boolean);
            // 卡片結構：[看板, 作者/學校, 時間, 標題, 摘要...]
            if (lines.length>=4) {
                const link=(a.querySelector('a[href*="/p/"]')||{}).href || '';
                out.push({board: lines[0], title: lines[3].slice(0,80), snippet: (lines[4]||'').slice(0,60), link});
            }
            if (out.length>=n) break;
        }
        return out;
    }""", n)

async def ani(pg, kw, n):
    await pg.goto(f"https://ani.gamer.com.tw/search.php?keyword={kw.replace(' ','%20')}", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(7000)  # XHR 渲染，需多等
    return await pg.evaluate("""(n) => {
        const NL=String.fromCharCode(10);
        const lines=((document.body&&document.body.innerText)||'').split(NL).map(x=>x.trim()).filter(x=>x && x!=='remove_red_eye' && x!=='雙語');
        const out=[]; 
        for (let i=0;i<lines.length-1;i++){
            if (/^年份：/.test(lines[i+1])) {   // 標題的下一行是「年份：」=> 這行是作品名
                let eps='', j=i+2;
                if (j<lines.length && /^共\d+集$/.test(lines[j])) { eps=lines[j]; j++; }
                out.push({title: lines[i].slice(0,50), year: lines[i+1].replace('年份：',''), episodes: eps});
            }
            if (out.length>=n) break;
        }
        return out;
    }""", n)

async def ptt(pg, kw, n):
    await pg.goto(f"https://www.pttweb.cc/ptt-search", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(3000)
    try:
        await pg.fill('input#gsc-i-id1', kw)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(7000)
    except Exception:
        pass
    return await pg.evaluate("""(n) => {
        const links=[...document.querySelectorAll('a')].filter(a=>/ptt\.cc\/bbs\/.+\/(M|G)\./.test(a.href||''));
        const seen=new Set(),out=[];
        for (const a of links){const t=(a.innerText||'').trim().replace(/\s*[-–]?\s*批踢踢實業坊\s*$/,''); const board=(a.href.match(/\/bbs\/([A-Za-z0-9_-]+)\//)||[])[1]||''; if(t.length>6&&!seen.has(a.href)){seen.add(a.href);out.push({title:t.slice(0,80),board,link:a.href});}}
        return out.slice(0,n);
    }""", n)

async def m01(pg, kw, n):
    await pg.goto(f"https://www.mobile01.com/googlesearch.php?query={kw.replace(' ','%20')}", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(6000)
    return await pg.evaluate("""(n) => {
        const as=[...document.querySelectorAll('a')].filter(a=>/topicdetail|\/topic\/\d+/.test(a.href||'')&&(a.innerText||'').trim().length>8);
        const seen=new Set(),out=[];
        for (const a of as){const t=(a.innerText||'').trim().split(String.fromCharCode(10))[0]; if(!seen.has(t)){seen.add(t);out.push({title:t.slice(0,90),link:a.href});}}
        return out.slice(0,n);
    }""", n)

async def x(pg, kw, n):
    await pg.goto(f"https://x.com/search?f=live&q={kw.replace(' ','%20')}", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(6000)
    for _ in range(2):
        await pg.mouse.wheel(0, 1800); await pg.wait_for_timeout(1500)
    return await pg.evaluate("""(n) => {
        const NL=String.fromCharCode(10);
        const out=[];
        for (const art of document.querySelectorAll('article')) {
            const link=(art.querySelector('a[href*="/status/"]')||{}).href||'';
            const lines=(art.innerText||'').split(NL).map(x=>x.trim()).filter(Boolean);
            if (lines.length>=4) out.push({user: lines[0], handle: lines[1], time: lines[2], text: lines.slice(3,6).join(' ').slice(0,160), link});
            if (out.length>=n) break;
        }
        return out;
    }""", n)

async def threads(pg, kw, n):
    await pg.goto(f"https://www.threads.com/search?q={kw.replace(' ','%20')}&serp_type=default", wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(9000)
    for _ in range(2):
        await pg.mouse.wheel(0, 1500); await pg.wait_for_timeout(1500)
    return await pg.evaluate("""(n) => {
        const NL=String.fromCharCode(10);
        const seen=new Set(), out=[];
        // 搜尋頁無 article：post 連結 /@USER/post/ID，往內層找承載文字的卡片
        for (const a of document.querySelectorAll('a[href^="/@"]')) {
            const href=a.getAttribute('href')||'';
            const m=href.match(/^\/@([A-Za-z0-9._]+)\/post\/([A-Za-z0-9_-]+)$/);
            if (!m || seen.has(href)) continue;
            let box=a, lines=[];
            for (let i=0;i<8&&box;i++){
                const L=(box.innerText||'').split(NL).map(x=>x.trim()).filter(Boolean);
                if (L.length>=4){ lines=L; break; }
                box=box.parentElement;
            }
            if (lines.length<3) continue;
            seen.add(href);
            const text=lines.filter(l=>l.length>6&&!/^\d/.test(l)&&!/說讚|追蹤|其他|・/.test(l)).join(' ').slice(0,150);
            out.push({user: m[1], text: text||lines.slice(0,3).join(' '), link:'https://www.threads.com'+href});
            if (out.length>=n) break;
        }
        return out;
    }""", n)

async def ig(pg, kw, n):
    # IG 無關鍵字全文搜尋：單字走 hashtag 頁，多字（含空白）走首頁 feed
    url = ("https://www.instagram.com/explore/tags/" + kw.replace(" ", "").lower() + "/") if " " not in kw else "https://www.instagram.com/"
    await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    await pg.wait_for_timeout(6000)
    for _ in range(3):
        await pg.mouse.wheel(0, 1800); await pg.wait_for_timeout(1500)
    return await pg.evaluate("""(n) => {
        const NL=String.fromCharCode(10);
        const out=[];
        for (const art of document.querySelectorAll('article')) {
            const a=art.querySelector('a[href*="/p/"],a[href*="/reel/"]');
            if (!a) continue;
            const lines=(art.innerText||'').split(NL).map(x=>x.trim()).filter(Boolean);
            const img=art.querySelector('img[alt]');
            const alt=(img&&img.alt&&img.alt.length>3)?img.alt.slice(0,120):'';
            out.push({user: lines[0]||'', caption: (lines.find(l=>l.length>15||alt)||'').slice(0,150), link: a.href});
            if (out.length>=n) break;
        }
        return out;
    }""", n)

SITE_FN = {"reddit": reddit, "dcard": dcard, "ani": ani, "ptt": ptt, "m01": m01, "x": x, "threads": threads, "ig": ig}
SITE_PAT = {"reddit": "reddit.com", "dcard": "dcard.tw", "ani": "ani.gamer", "ptt": "ptt.cc", "m01": "mobile01", "x": "x.com", "threads": "threads.com", "ig": "instagram.com"}

async def main():
    args = [a for a in sys.argv[1:]]
    kw = KW_DEFAULT
    n = 3
    out = None
    for a in args:
        if a.startswith("--kw"): kw = args[args.index(a)+1]
        if a.startswith("--n"): n = int(args[args.index(a)+1])
    sites = [a for a in args if a in SITE_FN] or ["all"]
    if "all" in sites: sites = list(SITE_FN)
    if out is None:
        from datetime import date
        out = os.path.join(OUT_DIR, f"forums_{kw.replace(' ','')}_{date.today().isoformat()}.jsonl")
    os.makedirs(OUT_DIR, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = b.contexts[0]
        all_res = {}
        for s in sites:
            pg = next((q for q in ctx.pages if SITE_PAT[s] in q.url), None) or await ctx.new_page()
            try:
                items = await SITE_FN[s](pg, kw, n)
                if items:
                    all_res[s] = {"count": len(items), "items": items}
                else:
                    t = (await pg.evaluate("() => ((document.body&&document.body.innerText)||'').slice(0,120)"))
                    all_res[s] = {"count": 0, "error": "EMPTY", "probe": t.replace("\n", " / ")[:100], "url": pg.url[:80]}
            except Exception as e:
                all_res[s] = {"error": str(e)[:100]}
            print(f"[{s}] ->", json.dumps(all_res[s], ensure_ascii=False)[:260], flush=True)
            await asyncio.sleep(3)
        with open(out, "w", encoding="utf-8") as f:
            f.write(json.dumps({"kw": kw, "date": str(__import__("datetime").date.today()), "results": all_res}, ensure_ascii=False, indent=1))
        print("SAVED:", out)
        await b.close()

asyncio.run(main())
