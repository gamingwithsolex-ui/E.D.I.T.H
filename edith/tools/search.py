import os
import requests
import webbrowser
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
    WEB_SEARCH = True
except ImportError:
    WEB_SEARCH = False

def _wikipedia_search(query, sentences=5):
    """Fetch a clean Wikipedia summary via the public REST API."""
    wiki_headers = {
        "User-Agent": "EDITH-AI/1.0 (Personal assistant; python-requests) contact/local"
    }
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        }
        r = requests.get(search_url, params=params, headers=wiki_headers, timeout=6)
        if r.status_code != 200:
            return ""
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return ""
        title = results[0]["title"]

        extract_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json",
            "exsentences": sentences,
        }
        r2 = requests.get(search_url, params=extract_params, headers=wiki_headers, timeout=6)
        pages = r2.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract:
                return f"[Wikipedia — {title}]\n{extract}"
    except Exception:
        pass
    return ""

def _scrape_page(url, max_chars=800):
    """Scrape and return clean text from a URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Edith/1.0)"}
        r = requests.get(url, headers=headers, timeout=6)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
    except Exception:
        return ""

def _ddg_search(query, max_results=5, deep=False):
    """DuckDuckGo text search, optionally scraping top result."""
    if not WEB_SEARCH:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                body = r.get("body", "")[:300]
                entry = {"title": r.get("title", ""), "body": body, "url": r.get("href", "")}
                results.append(entry)
        if deep and results and results[0]["url"]:
            scraped = _scrape_page(results[0]["url"])
            if scraped:
                results[0]["body"] = scraped
    except Exception:
        pass
    return results

def _ddg_news(query, max_results=4):
    """Fetch latest news from DuckDuckGo."""
    if not WEB_SEARCH:
        return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.news(query, max_results=max_results))
    except Exception:
        return []

def search_web(query, deep=False):
    """Multi-source search: Wikipedia + DuckDuckGo + optional news."""
    parts = []
    wiki = _wikipedia_search(query)
    if wiki:
        parts.append(wiki)

    ddg = _ddg_search(query, max_results=5, deep=deep)
    if ddg:
        lines = []
        for r in ddg:
            lines.append(f"- {r['title']}: {r['body']}")
        parts.append("[Web Results]\n" + "\n".join(lines))

    news_kws = ["news", "latest", "today", "current", "recent", "update", "2024", "2025", "2026"]
    if any(k in query.lower() for k in news_kws):
        news = _ddg_news(query)
        if news:
            lines = [f"- [{n.get('date','')[:10]}] {n.get('title','')}: {n.get('body','')[:200]}" for n in news]
            parts.append("[News]\n" + "\n".join(lines))

    if parts:
        return "\n\n".join(parts)
    return "No results found for: " + query

def deep_search(query):
    return search_web(query, deep=True)

def open_website(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
