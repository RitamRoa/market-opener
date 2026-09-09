"""
Database & Caching Module for Local Indian Stock Market Intelligence Engine.
Stores and caches news, filings, price data, events, and opportunity scores in SQLite.
Guarantees zero repeated downloading and persists complete historical track records.
"""

import sqlite3
import json
import os
import hashlib
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


# Auto initialize database on module import
init_db()

