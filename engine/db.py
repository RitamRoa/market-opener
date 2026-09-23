"""
Database & Caching Module for Local Indian Stock Market Intelligence Engine.
Stores and caches news, filings, price data, events, and opportunity scores in SQLite.
Guarantees zero repeated downloading and persists complete historical track records.
"""

import sqlite3
import json
import os
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "market_intelligence.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Creates a thread-safe connection to the SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the database schema if not already created."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # News & Filings Cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                summary TEXT,
                source TEXT,
                published_at TEXT,
                retrieved_at TEXT,
                symbol TEXT,
                cluster_id TEXT,
                is_noise INTEGER DEFAULT 0
            )
        """)

        # Price & yfinance Cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_cache (
                symbol TEXT,
                data_type TEXT, -- 'history', 'info', 'financials'
                payload TEXT,
                retrieved_at TEXT,
                PRIMARY KEY (symbol, data_type)
            )
        """)

        # Detected Corporate Events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_cache (
                event_id TEXT PRIMARY KEY,
                symbol TEXT,
                company_name TEXT,
                title TEXT,
                event_type TEXT,
                sentiment TEXT, -- POSITIVE, NEGATIVE, MIXED, NEUTRAL
                event_date TEXT,
                retrieved_at TEXT,
                sources TEXT, -- JSON array of sources
                materiality_score REAL,
                is_deduplicated INTEGER DEFAULT 1
            )
        """)

        # Deep Stock Analysis & Opportunity Scores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                symbol TEXT,
                analysis_date TEXT,
                opportunity_score REAL,
                priced_in_score REAL,
                confidence_score REAL,
                bull_case TEXT,
                bear_case TEXT,
                full_payload TEXT,
                PRIMARY KEY (symbol, analysis_date)
            )
        """)

        # FNA Events (Sharekhan-style fundamental intelligence memory)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fna_events (
                event_id TEXT PRIMARY KEY,
                company_name TEXT,
                symbol TEXT,
                event_type TEXT,
                headline TEXT,
                what_happened TEXT,
                why_it_matters TEXT,
                fundamental_direction TEXT,
                key_financial_implication TEXT,
                time_horizon TEXT,
                order_value_cr REAL,
                relative_revenue_pct REAL,
                materiality_score REAL,
                sources TEXT,
                event_date TEXT,
                created_at TEXT
            )
        """)

        # FNA Reports Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fna_reports (
                report_id TEXT PRIMARY KEY,
                report_date TEXT,
                item_count INTEGER,
                report_text TEXT,
                report_json TEXT,
                created_at TEXT
            )
        """)

        # Surfaced Events Store (for cross-day deduplication across runs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fna_surfaced_events (
                fingerprint TEXT PRIMARY KEY,
                company_key TEXT,
                company_name TEXT,
                symbol TEXT,
                event_type TEXT,
                headline TEXT,
                what_happened TEXT,
                order_value_cr REAL,
                surfaced_date TEXT,
                content_tokens TEXT,
                created_at TEXT
            )
        """)

        conn.commit()


# --- Cache Helper Functions ---

def cache_news(news_item: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    """Inserts a news item if not already cached. Returns True if new."""
    url = news_item.get("url", "")
    url_hash = hashlib.md5((news_item.get("title", "") + url).encode("utf-8")).hexdigest()
    retrieved_at = datetime.utcnow().isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM news_cache WHERE url_hash = ?", (url_hash,))
        if cursor.fetchone():
            return False  # Already exists

        cursor.execute("""
            INSERT INTO news_cache (url_hash, url, title, summary, source, published_at, retrieved_at, symbol, cluster_id, is_noise)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url_hash,
            url,
            news_item.get("title", ""),
            news_item.get("summary", ""),
            news_item.get("source", ""),
            news_item.get("published_at", retrieved_at),
            retrieved_at,
            news_item.get("symbol", None),
            news_item.get("cluster_id", None),
            1 if news_item.get("is_noise", False) else 0
        ))
        conn.commit()
    return True


def get_cached_news_by_date(target_date: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Retrieves all cached news articles and exchange announcements for target_date (YYYY-MM-DD).
    Matches ISO format, RFC formats (e.g. '18 Sep 2026', '18-Sep-2026').
    """
    items = []
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_str = dt.strftime("%d %b %Y")
        day_dash = dt.strftime("%d-%b-%Y")
    except Exception:
        day_str = target_date
        day_dash = target_date

    patterns = [f"{target_date}%", f"%{day_str}%", f"%{day_dash}%"]
    seen_hashes = set()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for p in patterns:
            cursor.execute("""
                SELECT url_hash, url, title, summary, source, published_at, symbol 
                FROM news_cache 
                WHERE published_at LIKE ?
            """, (p,))
            for row in cursor.fetchall():
                h = row["url_hash"]
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    items.append({
                        "url": row["url"],
                        "title": row["title"],
                        "summary": row["summary"],
                        "source": row["source"],
                        "published_at": row["published_at"],
                        "symbol": row["symbol"]
                    })
    return items


def get_cached_price(symbol: str, data_type: str, max_age_hours: float = 2.0, db_path: str = DB_PATH) -> Optional[Any]:
    """Retrieves cached yfinance payload if fresher than max_age_hours."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload, retrieved_at FROM price_cache WHERE symbol = ? AND data_type = ?
        """, (symbol, data_type))
        row = cursor.fetchone()
        if not row:
            return None

        retrieved_at = datetime.fromisoformat(row["retrieved_at"])
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - retrieved_at > timedelta(hours=max_age_hours):
            return None  # Expired cache

        try:
            return json.loads(row["payload"])
        except Exception:
            return None


def set_cached_price(symbol: str, data_type: str, payload: Any, db_path: str = DB_PATH) -> None:
    """Stores yfinance payload in price cache."""
    now_str = datetime.now(timezone.utc).isoformat()
    json_data = json.dumps(payload, default=str)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO price_cache (symbol, data_type, payload, retrieved_at)
            VALUES (?, ?, ?, ?)
        """, (symbol, data_type, json_data, now_str))
        conn.commit()


def save_scan_run(scan_data: Dict[str, Any], db_path: str = DB_PATH) -> str:
    """Persists a complete market intelligence scan run into the database."""
    run_id = scan_data.get("run_id", datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    now_str = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scan_runs 
            (run_id, run_timestamp, market_regime, nifty_price, nifty_change, bank_nifty_price, bank_nifty_change, vix, candidates_count, deep_analyzed_count, final_report_md, full_summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            now_str,
            scan_data.get("market_regime", "Neutral"),
            scan_data.get("nifty_price", 0.0),
            scan_data.get("nifty_change", 0.0),
            scan_data.get("bank_nifty_price", 0.0),
            scan_data.get("bank_nifty_change", 0.0),
            scan_data.get("vix", 0.0),
            scan_data.get("candidates_count", 0),
            scan_data.get("deep_analyzed_count", 0),
            scan_data.get("final_report_md", ""),
            json.dumps(scan_data.get("full_summary", {}), default=str)
        ))
        conn.commit()
    return run_id


def get_latest_scan_run(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves the most recent scan run."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM scan_runs ORDER BY run_timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def save_fna_event(event_data: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Stores an FNA event with company scale context and financial impact."""
    now_str = datetime.utcnow().isoformat()
    sources_json = json.dumps(event_data.get("sources", [])) if isinstance(event_data.get("sources"), list) else str(event_data.get("sources", ""))
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO fna_events 
            (event_id, company_name, symbol, event_type, headline, what_happened, why_it_matters, fundamental_direction, key_financial_implication, time_horizon, order_value_cr, relative_revenue_pct, materiality_score, sources, event_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_data.get("event_id", ""),
            event_data.get("company_name", ""),
            event_data.get("symbol", ""),
            event_data.get("event_type", ""),
            event_data.get("headline", ""),
            event_data.get("what_happened", ""),
            event_data.get("why_it_matters", ""),
            event_data.get("fundamental_direction", "Mixed"),
            event_data.get("key_financial_implication", ""),
            event_data.get("time_horizon", "Medium Term"),
            event_data.get("order_value_cr"),
            event_data.get("relative_revenue_pct"),
            event_data.get("materiality_score", 0.0),
            sources_json,
            event_data.get("event_date", now_str[:10]),
            now_str
        ))
        conn.commit()


def get_recent_company_events(symbol: str, limit: int = 3, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fetches previously recorded events for the company to provide cross-event continuity."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM fna_events WHERE symbol = ? ORDER BY created_at DESC LIMIT ?
        """, (symbol, limit))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def save_fna_report(report_id: str, report_date: str, item_count: int, report_text: str, report_json: str, db_path: str = DB_PATH) -> None:
    """Stores the daily FNA report."""
    now_str = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO fna_reports (report_id, report_date, item_count, report_text, report_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (report_id, report_date, item_count, report_text, report_json, now_str))
        conn.commit()


def get_fna_report_by_date(report_date: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves an FNA report for a specific date."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM fna_reports WHERE report_date = ? ORDER BY created_at DESC LIMIT 1
        """, (report_date,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


# --- Cross-Day Deduplication Store & Fingerprinting ---

def extract_significant_tokens(text: str) -> set:
    """Extracts lowercase tokens (alphabetic and numeric) excluding common market stop words."""
    words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "shares", "stock", "stocks",
        "india", "ltd", "limited", "company", "announces", "announced", "announcement",
        "regarding", "intimation", "disclosure", "under", "regulation", "bse", "nse",
        "crore", "crores", "rupees", "has", "have", "been", "which", "will", "price",
        "market", "today", "yesterday", "exchange", "informed", "about", "per", "share",
        "after", "into", "its", "set"
    }
    return {w for w in words if w not in stopwords and len(w) >= 2}


def extract_key_numbers(text: str) -> set:
    """Extracts distinctive numbers (e.g. 15, 29, 248, 400, 27000, 220) excluding trivial years."""
    nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    return {n for n in nums if n not in {"0", "1", "2024", "2025", "2026"}}


def generate_event_fingerprint(event: Dict[str, Any]) -> str:
    """Computes a deterministic fingerprint identifying a corporate event's core topic."""
    from engine.candidate_engine import normalize_company_key
    comp = normalize_company_key(event.get("company_name", ""), event.get("symbol", ""))
    ev_type = str(event.get("event_type", "OTHER")).upper()
    text = f"{event.get('headline', '')} {event.get('what_happened', '')}"
    key_nums = sorted(list(extract_key_numbers(text)))[:3]
    tokens = sorted(list(extract_significant_tokens(text)))
    distinctive = [t for t in tokens if len(t) >= 4][:5]
    raw = f"{comp}::{ev_type}::{'_'.join(key_nums)}::{'_'.join(distinctive)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_surfaced_events(events: List[Dict[str, Any]], surfaced_date: str, db_path: str = DB_PATH) -> None:
    """Persists today's finalized TOP NEWS events into fna_surfaced_events."""
    from engine.candidate_engine import normalize_company_key
    now_str = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM fna_surfaced_events WHERE surfaced_date = ?", (surfaced_date,))
        for ev in events:
            comp_key = normalize_company_key(ev.get("company_name", ""), ev.get("symbol", ""))
            fp = generate_event_fingerprint(ev)
            tokens = " ".join(sorted(list(extract_significant_tokens(f"{ev.get('headline', '')} {ev.get('what_happened', '')}"))))
            val = ev.get("order_value_cr")
            try:
                val = float(val) if val is not None else None
            except (ValueError, TypeError):
                val = None

            cursor.execute("""
                INSERT OR REPLACE INTO fna_surfaced_events (
                    fingerprint, company_key, company_name, symbol, event_type,
                    headline, what_happened, order_value_cr, surfaced_date, content_tokens, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fp,
                comp_key,
                ev.get("company_name", ""),
                ev.get("symbol", ""),
                ev.get("event_type", ""),
                ev.get("headline", ""),
                ev.get("what_happened", ""),
                val,
                surfaced_date,
                tokens,
                now_str
            ))
        conn.commit()


def get_surfaced_events_in_window(current_date: str, lookback_days: int = 2, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves events surfaced within the lookback window preceding current_date."""
    try:
        cur_dt = datetime.strptime(current_date, "%Y-%m-%d")
    except ValueError:
        return []

    # Look back up to lookback_days trading days (accounting for weekend)
    calendar_days = lookback_days + (2 if cur_dt.weekday() in [0, 1] else 0) + 1
    start_date = (cur_dt - timedelta(days=calendar_days)).strftime("%Y-%m-%d")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM fna_surfaced_events
            WHERE surfaced_date < ? AND surfaced_date >= ?
            ORDER BY surfaced_date DESC
        """, (current_date, start_date))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def is_stale_recurrent_event(candidate: Dict[str, Any], historical_events: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Checks whether candidate was already surfaced in the lookback window.
    Returns (True, reason) if it is a stale repetition lacking new material development.
    Returns (False, "") if it is genuinely fresh or has significant updated deal terms / stage.
    """
    if not historical_events:
        return False, ""

    from engine.candidate_engine import normalize_company_key
    cand_comp = normalize_company_key(candidate.get("company_name", ""), candidate.get("symbol", ""))
    cand_sym = candidate.get("symbol", "").replace(".NS", "").replace(".BO", "").strip().upper()
    cand_fp = generate_event_fingerprint(candidate)

    cand_text = f"{candidate.get('headline', '')} {candidate.get('what_happened', '')} {candidate.get('summary', '')}"
    cand_tokens = extract_significant_tokens(cand_text)
    cand_nums = extract_key_numbers(cand_text)
    cand_val = candidate.get("order_value_cr")
    try:
        cand_val = float(cand_val) if cand_val is not None else None
    except (ValueError, TypeError):
        cand_val = None

    for hist in historical_events:
        hist_comp = hist.get("company_key", "")
        hist_sym = (hist.get("symbol") or "").replace(".NS", "").replace(".BO", "").strip().upper()
        hist_fp = hist.get("fingerprint", "")

        # Check entity match (handling partial name matches like 'MDL' vs 'Mazagon Dock')
        same_entity = (
            (cand_comp and hist_comp and (cand_comp == hist_comp or cand_comp in hist_comp or hist_comp in cand_comp)) or
            (cand_sym and hist_sym and cand_sym == hist_sym)
        )
        if not same_entity and cand_fp != hist_fp:
            continue

        hist_text = f"{hist.get('headline', '')} {hist.get('what_happened', '')}"
        hist_tokens = set(hist.get("content_tokens", "").split())
        if not hist_tokens:
            hist_tokens = extract_significant_tokens(hist_text)
        hist_nums = extract_key_numbers(hist_text)

        intersection = cand_tokens.intersection(hist_tokens)
        union = cand_tokens.union(hist_tokens)
        jaccard = len(intersection) / len(union) if union else 0.0
        min_len = min(len(cand_tokens), len(hist_tokens))
        overlap_coef = len(intersection) / min_len if min_len > 0 else 0.0
        common_nums = cand_nums.intersection(hist_nums)

        hist_val = hist.get("order_value_cr")
        try:
            hist_val = float(hist_val) if hist_val is not None else None
        except (ValueError, TypeError):
            hist_val = None

        # Check if distinct project/location/facility exists:
        # e.g. Andhra Pradesh vs Dighi Port, or different regional hub/state
        loc_tokens = {
            "andhra", "pradesh", "dighi", "maharashtra", "gujarat", "odisha",
            "karnataka", "tamil", "nadu", "haryana", "rajasthan", "bengal",
            "kerala", "assam", "punjab", "bihar", "jharkhand", "goa",
            "mumbai", "chennai", "delhi", "kolkata", "hyderabad", "bengaluru",
            "vizag", "visakhapatnam", "kochi", "pune", "ahmedabad", "surat",
            "saudi", "jordan", "dubai", "usa", "europe", "japan"
        }
        cand_locs = cand_tokens.intersection(loc_tokens)
        hist_locs = hist_tokens.intersection(loc_tokens)
        has_different_locations = bool(cand_locs and hist_locs and cand_locs != hist_locs) or bool(cand_locs and not hist_locs and ("second" in cand_tokens or "new" in cand_tokens))

        # Multi-factor matching for near-duplicate recurrence on the same company:
        # Require >= 65% overlap PLUS matching key figures (or exact fingerprint match),
        # not just entity + rough topic match, ensuring distinct facilities (like Mazagon Dock Andhra Pradesh vs Dighi) are preserved.
        is_same_event = False
        if cand_fp == hist_fp and not has_different_locations:
            is_same_event = True
        elif same_entity and not has_different_locations:
            if overlap_coef >= 0.65 and (common_nums or (cand_val is not None and hist_val is not None and cand_val == hist_val)):
                is_same_event = True
            elif overlap_coef >= 0.65 and (not cand_nums and not hist_nums):
                is_same_event = True

        if is_same_event:

            # 1. Did numerical deal size change meaningfully (> 20%)?
            if cand_val is not None and hist_val is not None and abs(cand_val - hist_val) > max(1.0, 0.20 * hist_val):
                return False, "" # Material value revision!

            # 2. Did binary outcome advance? (e.g. from L1 bidder / LoI to formal definitive contract award)
            hist_text_lower = hist_text.lower()
            cand_text_lower = cand_text.lower()
            advancement_pairs = [
                (["loi", "letter of intent", "l1", "lowest bidder"], ["bags contract", "secures contract", "signs contract", "receives order", "award of contract"]),
                (["submits bid", "bids for"], ["emerges as", "wins", "awarded"]),
                (["proposed acquisition", "plans to acquire", "announces acquisition"], ["completes acquisition", "closes acquisition", "concludes acquisition"]),
            ]
            for prior_stages, advance_stages in advancement_pairs:
                if any(ps in hist_text_lower for ps in prior_stages) and any(as_ in cand_text_lower for as_ in advance_stages):
                    return False, "" # Milestone progressed to formal execution!

            return True, f"Stale event: already surfaced on {hist.get('surfaced_date')} ({hist.get('headline', '')[:50]}... Overlap: {int(overlap_coef*100)}%) without new material update."

    return False, ""


# Auto initialize database on module import
init_db()

