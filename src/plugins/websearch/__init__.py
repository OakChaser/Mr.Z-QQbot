import os
import re
import asyncio
import urllib.parse
import httpx
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg

DDG_URL = "https://html.duckduckgo.com/html/"
BING_URL = "https://www.bing.com/search"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# 每个搜索后端单次查询的超时（秒），防止被墙的平台的慢超时拖垮整体
SEARCH_PER_TIMEOUT = 6


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


async def bing_search(query: str, max_results: int = 5) -> list[dict]:
    """用 Bing 网页搜索（当前网络下 DuckDuckGo 被封时的零配置后备）。返回 [{source,title,url,snippet}]。"""
    params = {"q": query, "setlang": "zh-CN", "cc": "CN"}
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": UA}, follow_redirects=True) as client:
            resp = await client.get(BING_URL, params=params)
            html = resp.text
    except Exception as e:
        logger.error(f"bing search http error: {e}")
        return []
    results = []
    for block in re.split(r'<li class="b_algo"', html)[1:]:
        # 标题：块内第一个正文非空的外部链接（排除 bing/microsoft 自身域名）
        title = url = None
        for m in re.finditer(r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.S):
            t = _strip_tags(m.group(2))
            if t and "bing.com" not in m.group(1) and "microsoft.com" not in m.group(1):
                title, url = t, m.group(1)
                break
        if not title:
            continue
        # 摘要：b_caption 块内的文本
        cm = re.search(r'class="b_caption"[^>]*>(.*?)</div>', block, re.S)
        snippet = _strip_tags(cm.group(1)) if cm else ""
        results.append({"source": "bing", "title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


async def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """用 DuckDuckGo HTML 接口做免费搜索，返回 [{title, url, snippet}]"""
    data = {"q": query, "kl": "cn-zh"}
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA}, follow_redirects=True) as client:
            resp = await client.post(DDG_URL, data=data)
            html = resp.text
    except Exception as e:
        logger.error(f"web search http error: {e}")
        return []

    results = []
    # 结果标题 + 链接
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL
    ):
        url = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not title:
            continue
        if "uddg=" in url:
            url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
        results.append({"title": title, "url": url, "snippet": ""})

    # 摘要（snippet 有时在 <a class="result__snippet"> 里）
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
    )
    for i, s in enumerate(snippets):
        if i < len(results):
            results[i]["snippet"] = re.sub(r"<[^>]+>", "", s).strip()

    return results[:max_results]


# 所有可用后端：名字 -> 函数。新增平台在此注册即可。
SEARCH_BACKENDS = {
    "bing": bing_search,
    "ddg": ddg_search,
}


async def _safe_search(name: str, fn, query: str, max_results: int) -> list[dict]:
    """带超时与容错的单次后端查询，失败/超时返回空列表，不影响其他平台。"""
    try:
        res = await asyncio.wait_for(fn(query, max_results), timeout=SEARCH_PER_TIMEOUT)
    except Exception as e:
        logger.error(f"{name} search failed: {e}")
        return []
    out = []
    for r in res or []:
        r = dict(r)
        r.setdefault("source", name)
        out.append(r)
    return out


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """并发查询多个搜索平台，合并全部结果（按 url 去重），每个结果带 source 标记。

    启用的平台由环境变量 WEB_SEARCH_BACKEND 控制（逗号分隔，默认 bing,ddg）。
    所有平台同时发起，整体耗时 ≈ 最慢一个平台的耗时（单个平台超时上限 SEARCH_PER_TIMEOUT）。
    """
    enabled = [b.strip().lower() for b in os.getenv("WEB_SEARCH_BACKEND", "bing,ddg").split(",") if b.strip()]
    tasks = []
    for name in enabled:
        fn = SEARCH_BACKENDS.get(name)
        if fn:
            tasks.append(_safe_search(name, fn, query, max_results))
    if not tasks:
        tasks = [_safe_search("bing", bing_search, query, max_results)]

    gathered = await asyncio.gather(*tasks)
    merged = []
    seen = set()
    for res_list in gathered:
        for r in res_list or []:
            u = r.get("url", "")
            if u in seen:
                continue
            seen.add(u)
            merged.append(r)
    return merged[: max_results * 2]


search_cmd = on_command("search", aliases={"web"}, priority=1, block=True)


@search_cmd.handle()
async def do_search(event: MessageEvent, args: MessageSegment = CommandArg()):
    query = args.extract_plain_text().strip()
    if not query:
        await search_cmd.finish("搜啥？把关键词跟在 /search 后面。")

    logger.info(f"web search cmd: {query}")
    results = await web_search(query)
    if not results:
        await search_cmd.finish("没搜到东西，换个关键词试试。")

    lines = []
    for i, r in enumerate(results, 1):
        snippet = r.get("snippet", "")
        src = r.get("source", "")
        line = f"{i}. [{src}] {r['title']}"
        if snippet:
            line += f"\n   {snippet}"
        line += f"\n   {r['url']}"
        lines.append(line)

    text = "搜索结果：\n" + "\n\n".join(lines)
    await search_cmd.finish(text[:1500])
