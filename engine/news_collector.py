"""
News Collector for Indian Financial Markets.
Collects public news from Google News RSS, Economic Times, Moneycontrol, Mint, and Business Standard.
Zero API keys — fully compliant, multi-threaded RSS and public web feed parser.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
from engine.db import cache_news

logger = logging.getLogger(__name__)

FEED_REGISTRY = [
    {
        "source": "Google News (Indian Equities)",
        "url": "https://news.google.com/rss/search?q=NSE+BSE+stocks+results+order+announcement+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Corporate Action)",
        "url": "https://news.google.com/rss/search?q=Nifty+stocks+earnings+acquisition+SEBI+contract+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    },
    {
        "source": "Moneycontrol Business",
        "url": "https://www.moneycontrol.com/rss/business.xml",
    },
    {
        "source": "Moneycontrol Top News",
        "url": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    },
    {
        "source": "Livemint Markets",
        "url": "https://www.livemint.com/rss/markets",
    },
    {
        "source": "Business Standard Markets",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
    },
    {
        "source": "Google News (Policy & Capex)",
        "url": "https://news.google.com/rss/search?q=Cabinet+approves+procurement+tender+infrastructure+PLI+defence+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Commodities & Energy)",
        "url": "https://news.google.com/rss/search?q=crude+oil+Brent+petrol+diesel+OMC+refiners+copper+steel+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Energy Infrastructure & OPEC)",
        "url": "https://news.google.com/rss/search?q=(Middle+East+OR+Iran+OR+crude+oil+OR+Brent+OR+OPEC+OR+Trump+OR+tariff+OR+Strait+of+Hormuz)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Green Energy, BESS & Infra)",
        "url": "https://news.google.com/rss/search?q=(battery+storage+OR+BESS+OR+HiTHIUM+OR+Advait+OR+shipyard+OR+highway+OR+appointed+date)+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Capital Markets & Block Deals)",
        "url": "https://news.google.com/rss/search?q=(block+deal+OR+stake+sale+OR+PE+exit+OR+Lenskart+OR+promoter+holding)+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "source": "Google News (Industry Dispatches)",
        "url": "https://news.google.com/rss/search?q=toll+revenue+auto+sales+power+demand+cement+dispatches+telecom+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    }
]


def clean_html_text(raw_html: str) -> str:
    """Strips HTML tags and normalizes whitespace."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ")
    return " ".join(text.split())


def parse_single_feed(feed_meta: Dict[str, str], timeout: int = 8) -> List[Dict[str, Any]]:
    """Fetches and parses a single RSS feed safely."""
    items = []
    source_name = feed_meta["source"]
    feed_url = feed_meta["url"]

    try:
        # Fetch with requests to ensure custom User-Agent and timeout control
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        res = requests.get(feed_url, headers=headers, timeout=timeout)
        if res.status_code == 200:
            parsed = feedparser.parse(res.content)
            for entry in parsed.entries:
                title = clean_html_text(entry.get("title", ""))
                link = entry.get("link", "")
                summary = clean_html_text(entry.get("summary", "") or entry.get("description", ""))
                published = entry.get("published", "") or entry.get("updated", datetime.utcnow().isoformat())

                source_title = ""
                if isinstance(entry.get("source"), dict):
                    source_title = entry.get("source", {}).get("title", "")
                elif hasattr(entry, "source") and hasattr(entry.source, "title"):
                    source_title = getattr(entry.source, "title", "")

                effective_source = source_title if source_title else source_name

                item = {
                    "source": effective_source,
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published_at": published,
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "is_primary": False
                }
                items.append(item)
                cache_news(item)
        else:
            logger.debug(f"Feed {source_name} returned HTTP {res.status_code}")
    except Exception as e:
        logger.debug(f"Error reading feed {source_name}: {e}")

    return items


def collect_market_news(target_date: Optional[str] = None, max_workers: int = 6) -> List[Dict[str, Any]]:
    """
    Fetches financial news, media, and regulatory sources for the specified research date.
    If target_date is provided, queries dated search feeds across major Indian financial publications.
    If target_date is today, combines dated search results with live feeds for maximum coverage.
    If target_date is None, queries standard live feeds.
    """
    if target_date:
        items, _ = collect_historical_market_news(target_date, max_workers=max_workers)
        today_str = datetime.now().strftime("%Y-%m-%d")
        if target_date == today_str:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(parse_single_feed, feed) for feed in FEED_REGISTRY]
                for future in as_completed(futures):
                    try:
                        items.extend(future.result())
                    except Exception as e:
                        logger.debug(f"Thread execution error in feed fetcher: {e}")
        # Deduplicate items by url / title
        seen = set()
        unique_items = []
        for it in items:
            k = (it.get("url") or it.get("title", "")).strip().lower()
            if k not in seen:
                seen.add(k)
                unique_items.append(it)
        logger.info(f"Collected total of {len(unique_items)} deduplicated news articles for {target_date}.")
        return unique_items

    all_news = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(parse_single_feed, feed) for feed in FEED_REGISTRY]
        for future in as_completed(futures):
            try:
                items = future.result()
                all_news.extend(items)
            except Exception as e:
                logger.debug(f"Thread execution error in feed fetcher: {e}")

    logger.info(f"Collected total of {len(all_news)} raw news articles from public feeds.")
    return all_news


def search_company_news(company_name: str, symbol: str, days: int = 3) -> List[Dict[str, Any]]:
    """
    Zero API key company-specific news search via Google News RSS.
    Searches for: "{company_name}" OR "{symbol}" NSE BSE
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "")
    query = f'("{company_name}" OR "{clean_sym}") (NSE OR BSE OR order OR results OR share price) when:{days}d'
    encoded_query = urllib.parse.quote(query)
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed_meta = {
        "source": f"Google News Search ({clean_sym})",
        "url": feed_url
    }
    return parse_single_feed(feed_meta)


def build_historical_feed_registry(target_date: str) -> List[Dict[str, str]]:
    """Constructs dated public news search feeds for target_date (YYYY-MM-DD)."""
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    prev_day = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    queries = [
        ("The Economic Times", f"site:economictimes.indiatimes.com after:{prev_day} before:{next_day}"),
        ("Moneycontrol", f"site:moneycontrol.com after:{prev_day} before:{next_day}"),
        ("Business Standard", f"site:business-standard.com after:{prev_day} before:{next_day}"),
        ("Livemint", f"site:livemint.com after:{prev_day} before:{next_day}"),
        ("Reuters", f"site:reuters.com (India OR Nifty OR Sensex OR stocks) after:{prev_day} before:{next_day}"),
        ("CNBC-TV18", f"site:cnbctv18.com after:{prev_day} before:{next_day}"),
        ("Press Information Bureau", f"site:pib.gov.in (Cabinet OR Ministry OR approved OR scheme) after:{prev_day} before:{next_day}"),
        ("SEBI / Regulators", f"site:sebi.gov.in after:{prev_day} before:{next_day}"),
        ("Google News (Corporate Actions)", f"Nifty stocks earnings acquisition contract India after:{prev_day} before:{next_day}"),
        ("Google News (Orders & Disclosures)", f"NSE BSE stocks results order announcement India after:{prev_day} before:{next_day}"),
        ("Google News (Energy & Windfall Tax)", f"(windfall tax OR petroleum OR crude OR refiners OR MRPL OR ONGC) India after:{prev_day} before:{next_day}"),
        ("Google News (Global Geopolitics & Macro)", f"(Middle East OR Iran OR Israel OR Red Sea OR Strait of Hormuz OR Trump OR tariff OR crude oil OR Brent OR OPEC) after:{prev_day} before:{next_day}"),
        ("Google News (Green Energy, BESS & Power)", f"(battery storage OR BESS OR HiTHIUM OR Advait OR solar OR wind OR Petronet OR biogas) India after:{prev_day} before:{next_day}"),
        ("Google News (Infra, Highways & Tolls)", f"(appointed date OR concession OR highway OR GR Infra OR UPEIDA OR toll) India after:{prev_day} before:{next_day}"),
        ("Google News (Defence & Shipbuilding)", f"(shipbuilding OR shipyard OR Mazagon OR Mazagaon OR defence MoU OR navy) India after:{prev_day} before:{next_day}"),
        ("Google News (Capital Markets & Block Deals)", f"(block deal OR stake sale OR PE exit OR Lenskart OR promoter sale OR QIP) India after:{prev_day} before:{next_day}"),
    ]

    registry = []
    for name, q in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        registry.append({
            "source": name,
            "url": url
        })
    return registry


def collect_historical_market_news(target_date: str, max_workers: int = 6) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Fetches dated public financial news, media, and regulatory sources for target_date.
    Returns (all_news_items, counts_by_source).
    """
    registry = build_historical_feed_registry(target_date)
    all_news = []
    source_counts = {feed["source"]: 0 for feed in registry}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(parse_single_feed, feed): feed["source"] for feed in registry}
        for future in as_completed(future_to_source):
            src = future_to_source[future]
            try:
                items = future.result()
                source_counts[src] = len(items)
                all_news.extend(items)
            except Exception as e:
                logger.warning(f"Historical news fetcher failed for source '{src}': {e}")

    logger.info(f"Collected total of {len(all_news)} raw historical news articles for {target_date}.")
    return all_news, source_counts
