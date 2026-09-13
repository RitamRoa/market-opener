"""
NSE and BSE Public Corporate Announcements Client.
Zero API keys — retrieves real-time public corporate filings directly from exchange feeds.
Handles cookie warming, browser header emulation, and graceful fallbacks.
"""

import requests
import logging
from typing import List, Dict, Any, Tuple, Optional
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


def get_all_exchange_announcements(target_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Combines announcements from NSE and BSE for the specified research date.
    If target_date is provided and not today, queries dated announcements for that exact date.
    If target_date is today or None, queries live announcement feeds.
    """
    if target_date:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if target_date != today_str:
            items, _ = get_historical_exchange_announcements(target_date)
            return items

    items = fetch_nse_announcements()
    if len(items) < 5:
        bse_items = fetch_bse_announcements()
        items.extend(bse_items)
    return items



def fetch_nse_announcements_for_date(target_date: str) -> List[Dict[str, Any]]:
    """
    Fetches corporate announcements from the official NSE public portal for target_date (YYYY-MM-DD).
    """
    announcements = []
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        nse_date_str = dt.strftime("%d-%m-%Y")

        session.get("https://www.nseindia.com", timeout=6)
        url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={nse_date_str}&to_date={nse_date_str}"
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
                        "published_at": item.get("an_dt", f"{target_date} 12:00:00"),
                        "is_primary": True
                    })
            logger.info(f"Retrieved {len(announcements)} historical announcements from NSE for {target_date}.")
        else:
            logger.warning(f"NSE historical endpoint returned status {res.status_code} for {target_date}")
    except Exception as e:
        logger.warning(f"NSE historical announcement fetch failed for {target_date}: {e}")

    return announcements


def fetch_bse_announcements_for_date(target_date: str, max_pages: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches corporate announcements from BSE public portal for target_date (YYYY-MM-DD).
    """
    announcements = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bseindia.com/"
    }

    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        bse_date_str = dt.strftime("%Y%m%d")

        for page in range(1, max_pages + 1):
            url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno={page}&strCat=-1&strPrevDate={bse_date_str}&strScrip=&strSearch=P&strToDate={bse_date_str}&strType=C"
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code != 200:
                break
            data = res.json()
            table = data.get("Table", [])
            if not table:
                break

            for item in table:
                scrip_cd = item.get("SCRIP_CD", "")
                company_name = item.get("SLONGNAME", "") or item.get("NEWSSUB", "")
                title = item.get("NEWSSUB", "BSE Announcement")
                summary = item.get("HEADLINE", "") or title
                announcements.append({
                    "source": "BSE Announcements",
                    "symbol": None,
                    "raw_symbol": str(scrip_cd),
                    "company_name": company_name,
                    "category": item.get("CATEGORYNAME", "Announcement"),
                    "title": f"{company_name}: {title}",
                    "summary": summary,
                    "url": f"https://www.bseindia.com/corporates/anndet_new.aspx?newsid={item.get('NEWSID', '')}",
                    "published_at": item.get("NEWS_DT", f"{target_date}T12:00:00"),
                    "is_primary": True
                })

        logger.info(f"Retrieved {len(announcements)} historical announcements from BSE for {target_date}.")
    except Exception as e:
        logger.warning(f"BSE historical announcement fetch failed for {target_date}: {e}")

    return announcements


def get_historical_exchange_announcements(target_date: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Combines historical announcements from NSE and BSE for target_date with fallback guarantees.
    Returns (announcements, counts_per_source).
    """
    counts = {"NSE Corporate Announcements": 0, "BSE Announcements": 0}
    items = []

    nse_items = fetch_nse_announcements_for_date(target_date)
    counts["NSE Corporate Announcements"] = len(nse_items)
    items.extend(nse_items)

    bse_items = fetch_bse_announcements_for_date(target_date)
    counts["BSE Announcements"] = len(bse_items)
    items.extend(bse_items)

    return items, counts

