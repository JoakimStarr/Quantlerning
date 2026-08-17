"""联网搜索：Tavily API 封装，供 AI 追问按需检索外部实时信息。

仅当用户在 AI 面板开启「联网搜索」时使用；结果以 system 上下文注入，
并明确标注来源为外部网页（区别于本站 quantlab 数据），回答需带 Markdown 链接引用。
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tavily.com/search"
_MAX_RESULTS = 5
_MAX_CONTENT_CHARS = 600


class WebSearchNotConfiguredError(Exception):
    """未配置 Tavily API key。"""


class WebSearchError(Exception):
    """Tavily 调用失败。"""


async def web_search(query: str, api_key: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """按 query 检索网络信息，返回 [{title, url, content}, ...]。

    未配置 key 抛 WebSearchNotConfiguredError；调用失败抛 WebSearchError。
    """
    if not api_key:
        raise WebSearchNotConfiguredError(
            "联网搜索未配置：请在「设置」页填写 Tavily API Key。"
        )
    if not query.strip():
        return []

    payload = {
        "query": query.strip(),
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=20) as client:
            resp = await client.post(SEARCH_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                raise WebSearchError(
                    f"联网搜索失败（HTTP {resp.status_code}）：{resp.text[:200]}"
                )
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("联网搜索网络错误: %s", e)
        raise WebSearchError(f"联网搜索连接失败: {e.__class__.__name__}") from e
    except ValueError:
        raise WebSearchError("联网搜索返回非预期格式") from None

    results: list[dict] = []
    for r in data.get("results") or []:
        content = (r.get("content") or "").strip()
        if not content:
            continue
        results.append(
            {
                "title": (r.get("title") or "").strip() or "（无标题）",
                "url": (r.get("url") or "").strip(),
                "content": content[:_MAX_CONTENT_CHARS],
            }
        )
    return results


def build_search_context(results: list[dict]) -> str:
    """把检索结果组装成 system 上下文文本。

    明确标注「外部网页、非本站数据」，并要求引用时给出链接——保证真实性纪律。
    """
    if not results:
        return ""
    lines = [
        "以下是「联网搜索」返回的实时网络信息（来源为外部网页，"
        "非本站 quantlab 数据，仅供回答参考，引用时请给出链接）："
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}（{r['url']}）：{r['content']}")
    lines.append(
        "请结合课程知识回答用户问题：若网络信息与课程知识冲突，请明确指出差异；"
        "引用外部信息时用 Markdown 链接标注来源（如 [来源标题](URL)）；"
        "不要把网络信息说成本站 quantlab 数据。"
    )
    return "\n".join(lines)
