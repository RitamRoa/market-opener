"""
NSE and BSE Public Corporate Announcements Client.
Zero API keys — retrieves real-time public corporate filings directly from exchange feeds.
Handles cookie warming, browser header emulation, and graceful fallbacks.
"""

import requests
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Origin": "https://www.nseindia.com"
}


def fetch_nse_announcements() -> List[Dict[str, Any]]:
    """
    Fetches latest corporate announcements from the official NSE public portal.
    Initializes session cookies by visiting the homepage first.
    """
    announcements = []
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Step 1: Warm up session cookies
        session.get("https://www.nseindia.com", timeout=6)

        # Step 2: Fetch equity corporate announcements
        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        res = session.get(url, timeout=8)

        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                for item in data:
                    sym = item.get("symbol", "").strip()
                    if not sym:
                        continue
                    canonical_sym = f"{sym}.NS"
                    announcements.append({
                        "source": "NSE Corporate Announcements",
                        "symbol": canonical_sym,
                        "raw_symbol": sym,
                        "company_name": item.get("sm_name", ""),
                        "category": item.get("desc", "Corporate Announcement"),
                        "title": f"{item.get('sm_name', sym)}: {item.get('desc', 'Announcement')}",
                        "summary": item.get("attchmntText", "") or item.get("desc", ""),
                        "url": item.get("attchmntFile", "https://www.nseindia.com"),
                        "published_at": item.get("an_dt", datetime.utcnow().strftime("%d-%b-%Y %H:%M:%S")),
                        "is_primary": True
                    })
            logger.info(f"Retrieved {len(announcements)} announcements from NSE.")
        else:
            logger.warning(f"NSE announcement endpoint returned status {res.status_code}")
    except Exception as e:
        logger.warning(f"NSE announcement fetch encountered error: {e}")

    return announcements


def fetch_bse_announcements() -> List[Dict[str, Any]]:
    """
    Fallback fetcher for BSE public corporate announcements.
    """
    announcements = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bseindia.com/"
    }

    try:
        url = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate=&strScrip=&strSearch=P&strToDate=&strType=C"
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            table = data.get("Table", [])
            for item in table:
                scrip_cd = item.get("SCRIP_CD", "")
                company_name = item.get("SLONGNAME", "") or item.get("NEWSSUB", "")
                title = item.get("NEWSSUB", "BSE Announcement")
                summary = item.get("HEADLINE", "") or title
                announcements.append({
                    "source": "BSE Announcements",
                    "symbol": None, # Will be resolved by entity mapper
                    "raw_symbol": str(scrip_cd),
                    "company_name": company_name,
                    "category": item.get("CATEGORYNAME", "Announcement"),
                    "title": f"{company_name}: {title}",
                    "summary": summary,
                    "url": f"https://www.bseindia.com/corporates/anndet_new.aspx?newsid={item.get('NEWSID', '')}",
                    "published_at": item.get("NEWS_DT", datetime.utcnow().isoformat()),
                    "is_primary": True
                })
    except Exception as e:
        logger.debug(f"BSE announcements fetch skipped/failed: {e}")

    return announcements


def get_all_exchange_announcements() -> List[Dict[str, Any]]:
    """
    Combines announcements from NSE and BSE with fallback guarantees.
    """
    items = fetch_nse_announcements()
    if len(items) < 5:
        bse_items = fetch_bse_announcements()
        items.extend(bse_items)
    return items
