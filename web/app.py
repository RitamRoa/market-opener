"""
FastAPI Web Dashboard Backend for Indian Stock Market Intelligence Engine.
Zero API keys — exposes REST endpoints for market regime, scans, deep stock views, and scan history.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import logging
from typing import Optional

from engine.pipeline import run_full_market_scan
from engine.db import get_latest_scan_run, get_connection
from engine.market_context import get_market_context
from engine.candidate_scanner import get_stock_price_metrics
from engine.deep_analyzer import conduct_deep_stock_analysis
from engine.scorer import score_deep_stock
from engine.entity_mapper import get_company_meta

logger = logging.getLogger(__name__)

app = FastAPI(title="Indian Stock Market Intelligence Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# State for background scans
SCAN_STATE = {
    "is_scanning": False,
    "last_run": None,
    "progress": "Idle"
}


@app.get("/")
def serve_index():
    """Serves the dashboard front-end."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Web UI initializing..."}


@app.get("/api/market-context")
def api_market_context():
    """Returns live market benchmark indices and regime."""
    return get_market_context()


@app.get("/api/latest")
def api_latest_scan():
    """Returns the most recent intelligence scan data."""
    latest = get_latest_scan_run()
    if not latest:
        # If no scan exists in DB, execute quick initial scan or return empty
        return JSONResponse(status_code=404, content={"message": "No scans available. Trigger a new scan."})
    
    summary = json.loads(latest["full_summary_json"]) if latest.get("full_summary_json") else {}
    return {
        "run_id": latest["run_id"],
        "timestamp": latest["run_timestamp"],
        "market_regime": latest["market_regime"],
        "report_md": latest["final_report_md"],
        "summary": summary
    }


def background_scan_task():
    global SCAN_STATE
    SCAN_STATE["is_scanning"] = True
    SCAN_STATE["progress"] = "Scanning exchange filings and RSS feeds..."
    try:
        summary, report_md = run_full_market_scan()
        SCAN_STATE["last_run"] = summary
        SCAN_STATE["progress"] = "Completed successfully"
    except Exception as e:
        logger.error(f"Background scan error: {e}")
        SCAN_STATE["progress"] = f"Error: {str(e)}"
    finally:
        SCAN_STATE["is_scanning"] = False


@app.post("/api/scan")
def api_trigger_scan(background_tasks: BackgroundTasks):
    """Triggers an asynchronous market scan."""
    global SCAN_STATE
    if SCAN_STATE["is_scanning"]:
        return {"status": "in_progress", "progress": SCAN_STATE["progress"]}
    
    background_tasks.add_task(background_scan_task)
    SCAN_STATE["is_scanning"] = True
    SCAN_STATE["progress"] = "Initiating scan..."
    return {"status": "started", "message": "Market scan initiated in background."}


@app.get("/api/scan/status")
def api_scan_status():
    """Checks progress of current scan."""
    return SCAN_STATE


@app.get("/api/stocks/{symbol}")
def api_stock_deep_dive(symbol: str):
    """Runs on-demand deep analysis for any requested Indian ticker."""
    clean_sym = symbol.upper()
    if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO"):
        clean_sym = f"{clean_sym}.NS"

    meta = get_company_meta(clean_sym)
    context = get_market_context()
    metrics = get_stock_price_metrics(clean_sym)

    candidate = {
        "symbol": clean_sym,
        "company": meta["name"],
        "sector": meta["sector"],
        "event_type": "On-Demand Deep Analysis",
        "sentiment": "POSITIVE" if metrics["ret_1d"] >= 0 else "MIXED",
        "materiality": 0.75,
        "main_event": f"{meta['name']}: Quantitative & Fundamental Evaluation",
        "summary": "Deep dive on valuations, priced-in metrics, and returns.",
        "sources": ["Exchange Market Data", "yfinance"],
        "is_primary": True,
        **metrics
    }

    deep = conduct_deep_stock_analysis(candidate)
    scored = score_deep_stock(deep, context)
    clean_dict = json.loads(json.dumps(scored, default=str))
    return JSONResponse(content=clean_dict)


# Mount static assets directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
