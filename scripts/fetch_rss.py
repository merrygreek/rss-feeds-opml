"""
RSS Aggregator — GitHub Actions 版
并发抓取 49 个 RSS/Atom feed，输出 docs/feeds.json
"""

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

try:
    import aiohttp
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    import aiohttp

# ── Feed 列表 ────────────────────────────────────────────────
FEEDS = [
    # AI & LLM
    {"id": "simonwillison",   "category": "AI & LLM",       "title": "Simon Willison",       "url": "https://simonwillison.net/atom/everything/",                         "home": "https://simonwillison.net/"},
    {"id": "openai",          "category": "AI & LLM",       "title": "OpenAI News",          "url": "https://openai.com/news/rss.xml",                                    "home": "https://openai.com/news/"},
    {"id": "arxiv-ai",        "category": "AI & LLM",       "title": "arXiv cs.AI",          "url": "https://arxiv.org/rss/cs.AI",                                       "home": "https://arxiv.org/list/cs.AI/recent"},
    {"id": "arxiv-lg",        "category": "AI & LLM",       "title": "arXiv cs.LG",          "url": "https://arxiv.org/rss/cs.LG",                                       "home": "https://arxiv.org/list/cs.LG/recent"},
    {"id": "google-research", "category": "AI & LLM",       "title": "Google Research Blog", "url": "https://research.google/blog/rss/",                                  "home": "https://research.google/blog/"},
    {"id": "deepmind",        "category": "AI & LLM",       "title": "DeepMind Blog",        "url": "https://deepmind.google/blog/rss.xml",                               "home": "https://deepmind.google/blog/"},
    {"id": "lilianweng",      "category": "AI & LLM",       "title": "Lilian Weng",          "url": "https://lilianweng.github.io/lil-log/feed.xml",                      "home": "https://lilianweng.github.io/"},
    {"id": "gwern",           "category": "AI & LLM",       "title": "Gwern",                "url": "https://www.gwern.net/feed",                                         "home": "https://www.gwern.net/"},
    {"id": "garymarcus",      "category": "AI & LLM",       "title": "Gary Marcus",          "url": "https://garymarcus.substack.com/feed",                               "home": "https://garymarcus.substack.com/"},
    {"id": "minimaxir",       "category": "AI & LLM",       "title": "Max Woolf",            "url": "https://minimaxir.com/index.xml",                                    "home": "https://minimaxir.com/"},
    {"id": "thesequence",     "category": "AI & LLM",       "title": "The Sequence",         "url": "https://thesequence.substack.com/feed",                              "home": "https://thesequence.substack.com/"},
    # Tech Blogs
    {"id": "jeffgeerling",    "category": "Tech Blogs",     "title": "Jeff Geerling",        "url": "https://www.jeffgeerling.com/blog.xml",                              "home": "https://www.jeffgeerling.com/"},
    {"id": "seangoedecke",    "category": "Tech Blogs",     "title": "Sean Goedecke",        "url": "https://www.seangoedecke.com/rss.xml",                               "home": "https://www.seangoedecke.com/"},
    {"id": "krebsonsecurity", "category": "Tech Blogs",     "title": "Krebs on Security",    "url": "https://krebsonsecurity.com/feed/",                                  "home": "https://krebsonsecurity.com/"},
    {"id": "daringfireball",  "category": "Tech Blogs",     "title": "Daring Fireball",      "url": "https://daringfireball.net/feeds/main",                              "home": "https://daringfireball.net/"},
    {"id": "ericmigi",        "category": "Tech Blogs",     "title": "Eric Migicovsky",      "url": "https://ericmigi.com/rss.xml",                                       "home": "https://ericmigi.com/"},
    {"id": "antirez",         "category": "Tech Blogs",     "title": "antirez",              "url": "http://antirez.com/rss",                                             "home": "http://antirez.com/"},
    {"id": "idiallo",         "category": "Tech Blogs",     "title": "Ibrahim Diallo",       "url": "https://idiallo.com/feed.rss",                                       "home": "https://idiallo.com/"},
    {"id": "maurycyz",        "category": "Tech Blogs",     "title": "Maurycy",              "url": "https://maurycyz.com/index.xml",                                     "home": "https://maurycyz.com/"},
    {"id": "pluralistic",     "category": "Tech Blogs",     "title": "Pluralistic",          "url": "https://pluralistic.net/feed/",                                      "home": "https://pluralistic.net/"},
    {"id": "shkspr",          "category": "Tech Blogs",     "title": "Terence Eden",         "url": "https://shkspr.mobi/blog/feed/",                                     "home": "https://shkspr.mobi/blog/"},
    {"id": "lcamtuf",         "category": "Tech Blogs",     "title": "Lcamtuf",              "url": "https://lcamtuf.substack.com/feed",                                  "home": "https://lcamtuf.substack.com/"},
    {"id": "mitchellh",       "category": "Tech Blogs",     "title": "Mitchell Hashimoto",   "url": "https://mitchellh.com/feed.xml",                                     "home": "https://mitchellh.com/"},
    {"id": "dynomight",       "category": "Tech Blogs",     "title": "Dynomight",            "url": "https://dynomight.net/feed.xml",                                     "home": "https://dynomight.net/"},
    {"id": "xeiaso",          "category": "Tech Blogs",     "title": "Xe Iaso",              "url": "https://xeiaso.net/blog.rss",                                        "home": "https://xeiaso.net/"},
    {"id": "oldnewthing",     "category": "Tech Blogs",     "title": "The Old New Thing",    "url": "https://devblogs.microsoft.com/oldnewthing/feed",                    "home": "https://devblogs.microsoft.com/oldnewthing/"},
    {"id": "righto",          "category": "Tech Blogs",     "title": "Ken Shirriff",         "url": "https://www.righto.com/feeds/posts/default",                         "home": "https://www.righto.com/"},
    {"id": "arminronacher",   "category": "Tech Blogs",     "title": "Armin Ronacher",       "url": "https://lucumr.pocoo.org/feed.atom",                                 "home": "https://lucumr.pocoo.org/"},
    {"id": "skyfall",         "category": "Tech Blogs",     "title": "Skyfall",              "url": "https://skyfall.dev/rss.xml",                                        "home": "https://skyfall.dev/"},
    {"id": "rachelbythebay",  "category": "Tech Blogs",     "title": "Rachel by the Bay",    "url": "https://rachelbythebay.com/w/atom.xml",                              "home": "https://rachelbythebay.com/"},
    {"id": "danabramov",      "category": "Tech Blogs",     "title": "Dan Abramov",          "url": "https://overreacted.io/rss.xml",                                     "home": "https://overreacted.io/"},
    {"id": "johndcook",       "category": "Tech Blogs",     "title": "John D. Cook",         "url": "https://www.johndcook.com/blog/feed/",                               "home": "https://www.johndcook.com/"},
    {"id": "matklad",         "category": "Tech Blogs",     "title": "Matklad",              "url": "https://matklad.github.io/feed.xml",                                 "home": "https://matklad.github.io/"},
    {"id": "elibendersky",    "category": "Tech Blogs",     "title": "Eli Bendersky",        "url": "https://eli.thegreenplace.net/feeds/all.atom.xml",                   "home": "https://eli.thegreenplace.net/"},
    {"id": "fabiensanglard",  "category": "Tech Blogs",     "title": "Fabien Sanglard",      "url": "https://fabiensanglard.net/rss.xml",                                 "home": "https://fabiensanglard.net/"},
    {"id": "miguelgrinberg",  "category": "Tech Blogs",     "title": "Miguel Grinberg",      "url": "https://blog.miguelgrinberg.com/feed",                               "home": "https://blog.miguelgrinberg.com/"},
    {"id": "troyhunt",        "category": "Tech Blogs",     "title": "Troy Hunt",            "url": "https://www.troyhunt.com/rss/",                                      "home": "https://www.troyhunt.com/"},
    {"id": "anildash",        "category": "Tech Blogs",     "title": "Anil Dash",            "url": "https://anildash.com/feed.xml",                                      "home": "https://anildash.com/"},
    {"id": "computerrip",     "category": "Tech Blogs",     "title": "Computer Rip",         "url": "https://computer.rip/rss.xml",                                       "home": "https://computer.rip/"},
    {"id": "tedunangst",      "category": "Tech Blogs",     "title": "Ted Unangst",          "url": "https://www.tedunangst.com/flak/rss",                                "home": "https://www.tedunangst.com/"},
    {"id": "paulgraham",      "category": "Tech Blogs",     "title": "Paul Graham Essays",   "url": "http://www.aaronsw.com/2002/feeds/pgessays.rss",                     "home": "http://paulgraham.com/"},
    {"id": "steveblank",      "category": "Tech Blogs",     "title": "Steve Blank",          "url": "https://steveblank.com/feed/",                                       "home": "https://steveblank.com/"},
    # Startup & News
    {"id": "hackernews",      "category": "Startup & News", "title": "Hacker News",          "url": "https://news.ycombinator.com/rss",                                   "home": "https://news.ycombinator.com/"},
    {"id": "techmeme",        "category": "Startup & News", "title": "Techmeme",             "url": "https://www.techmeme.com/feed.xml",                                  "home": "https://www.techmeme.com/"},
    {"id": "techcrunch",      "category": "Startup & News", "title": "TechCrunch",           "url": "https://techcrunch.com/feed/",                                       "home": "https://techcrunch.com/"},
    {"id": "techcrunch-ai",   "category": "Startup & News", "title": "TechCrunch AI",        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",      "home": "https://techcrunch.com/category/artificial-intelligence/"},
    {"id": "techcrunch-fund", "category": "Startup & News", "title": "TechCrunch Funding",   "url": "https://techcrunch.com/tag/funding/feed/",                           "home": "https://techcrunch.com/tag/funding/"},
    {"id": "venturebeat",     "category": "Startup & News", "title": "VentureBeat",          "url": "https://venturebeat.com/feed/",                                      "home": "https://venturebeat.com/"},
    {"id": "venturebeat-ai",  "category": "Startup & News", "title": "VentureBeat AI",       "url": "https://venturebeat.com/category/ai/feed/",                          "home": "https://venturebeat.com/category/ai/"},
    # 中文
    {"id": "ruanyifeng",      "category": "中文",            "title": "阮一峰的网络日志",       "url": "https://www.ruanyifeng.com/blog/atom.xml",                           "home": "https://www.ruanyifeng.com/blog/"},
    {"id": "bestblogs",       "category": "中文",            "title": "BestBlogs.dev AI 90+", "url": "https://www.bestblogs.dev/zh/feeds/rss?category=ai&minScore=90",    "home": "https://www.bestblogs.dev/"},
]

TIMEOUT  = aiohttp.ClientTimeout(total=10)
MAX_CONN = 20   # 最大并发连接数
MAX_ITEMS = 10  # 每个 feed 最多保留条目数

HEADERS = {
    "User-Agent": "RSSBot/1.0 (github.com/merrygreek/rss-feeds-opml)",
    "Accept": "application/rss+xml, application/atom+xml, text/xml, */*",
}

# ── XML 解析 ─────────────────────────────────────────────────
def strip_tags(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()

def parse_xml(xml_text: str) -> list[dict]:
    items = []
    try:
        # 清理命名空间前缀，简化解析
        xml_clean = re.sub(r' xmlns[^"]*"[^"]*"', "", xml_text)
        xml_clean = re.sub(r"<(\w+):(\w+)", r"<\1_\2", xml_clean)
        xml_clean = re.sub(r"</(\w+):(\w+)>", r"</\1_\2>", xml_clean)

        root = ET.fromstring(xml_clean)
        is_atom = root.tag.lower() in ("feed", "{http://www.w3.org/2005/atom}feed")

        if is_atom:
            entries = root.findall(".//entry") or root.findall(".//{http://www.w3.org/2005/atom}entry")
        else:
            entries = root.findall(".//item")

        for entry in entries:
            def t(tag):
                el = entry.find(tag)
                return strip_tags(el.text or "").strip() if el is not None and el.text else ""

            if is_atom:
                title = t("title")
                link_el = entry.find("link[@rel='alternate']") or entry.find("link")
                link = link_el.get("href", "") if link_el is not None else ""
                date = t("updated") or t("published")
                summary = t("summary") or t("content")
            else:
                title = t("title")
                link = t("link")
                date = t("pubDate") or t("dc_date")
                summary = t("description")

            # 标准化日期
            try:
                date_iso = datetime.fromisoformat(date.replace("Z", "+00:00")).isoformat()
            except Exception:
                try:
                    from email.utils import parsedate_to_datetime
                    date_iso = parsedate_to_datetime(date).isoformat()
                except Exception:
                    date_iso = None

            items.append({
                "title": title[:200] or "(no title)",
                "link": link,
                "date": date_iso,
                "summary": summary[:300],
            })

    except Exception as e:
        pass  # XML 解析失败时返回空列表

    return items

# ── 异步抓取单个 feed ────────────────────────────────────────
async def fetch_feed(session: aiohttp.ClientSession, feed: dict) -> dict:
    base = {"id": feed["id"], "category": feed["category"],
            "title": feed["title"], "home": feed["home"], "url": feed["url"]}
    try:
        async with session.get(feed["url"], headers=HEADERS, timeout=TIMEOUT,
                               allow_redirects=True, ssl=False) as resp:
            if resp.status != 200:
                return {**base, "status": "error", "error": f"HTTP {resp.status}", "items": []}
            xml_text = await resp.text(errors="replace")
            items = parse_xml(xml_text)[:MAX_ITEMS]
            print(f"  ✓ {feed['title']:<30} {len(items)} items")
            return {**base, "status": "ok", "fetchedAt": datetime.now(timezone.utc).isoformat(), "items": items}
    except asyncio.TimeoutError:
        print(f"  ✗ {feed['title']:<30} TIMEOUT")
        return {**base, "status": "error", "error": "timeout", "items": []}
    except Exception as e:
        print(f"  ✗ {feed['title']:<30} {e}")
        return {**base, "status": "error", "error": str(e), "items": []}

# ── 批量并发抓取 ─────────────────────────────────────────────
async def fetch_all() -> list[dict]:
    conn = aiohttp.TCPConnector(limit=MAX_CONN, ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [fetch_feed(session, f) for f in FEEDS]
        results = await asyncio.gather(*tasks)
    return list(results)

# ── 主函数 ───────────────────────────────────────────────────
async def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting RSS fetch ({len(FEEDS)} feeds)...")
    results = await fetch_all()

    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count
    print(f"\nDone: {ok_count} OK, {fail_count} failed")

    # 按 category 分组
    grouped: dict[str, list] = {}
    for r in results:
        cat = r["category"]
        grouped.setdefault(cat, []).append(r)

    # 全量扁平列表（按时间倒序）
    all_items = []
    for r in results:
        for item in r.get("items", []):
            all_items.append({
                **item,
                "feedId": r["id"],
                "feedTitle": r["title"],
                "category": r["category"],
                "feedHome": r["home"],
            })
    all_items.sort(key=lambda x: x.get("date") or "", reverse=True)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "totalFeeds": len(results),
        "successCount": ok_count,
        "failedCount": fail_count,
        "failed": [r["id"] for r in results if r["status"] == "error"],
        "grouped": grouped,
        "allItems": all_items[:500],  # 最多 500 条最新文章
    }

    out_path = Path(__file__).parent.parent / "docs" / "feeds.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written → {out_path} ({out_path.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    asyncio.run(main())
