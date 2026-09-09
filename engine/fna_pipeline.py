"""
FNA Master Pipeline: Event-First Fundamental News & Analysis Engine.
Implements the full Sharekhan-style daily intelligence flow:
  Ingest -> Noise Gate -> Entity Resolution Gate -> Deduplication Gate
  -> Financial Context & Materiality -> Synthesis -> Rank -> Format ONLY TOP NEWS.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

from engine.nse_bse_client import get_all_exchange_announcements
from engine.news_collector import collect_market_news
from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity
from engine.deduplicator import deduplicate_and_cluster_news
from engine.fna_analyzer import synthesize_fna_item
from engine.db import save_fna_event, save_fna_report

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def compute_composite_ranking_score(it: Dict[str, Any]) -> float:
    score = it.get("materiality_score", 7.0)
    # Bonus for quantified monetary value
    if it.get("order_value_cr") or it.get("range_text"):
        score += 0.5
    # Bonus for high-conviction events
    if it.get("event_type") in ["GOVERNMENT_EVENT", "MANAGEMENT_EVENT", "ORDER_CONTRACT"]:
        score += 0.3
    return score


def select_daily_top_news(qualified_tier_a: List[Dict[str, Any]], qualified_tier_b: List[Dict[str, Any]], max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Two-stage selection model (Section 7 & 32-34):
    1. Filter strictly for POSITIVE or NEGATIVE (never AMBIGUOUS/NEUTRAL).
    2. Prioritize all Tier A items.
    3. Fill remaining slots with strongest Tier B items up to max_items.
    """
    valid_a = [it for it in qualified_tier_a if it.get("classification") in ["POSITIVE", "NEGATIVE"]]
    valid_b = [it for it in qualified_tier_b if it.get("classification") in ["POSITIVE", "NEGATIVE"]]

    valid_a.sort(key=compute_composite_ranking_score, reverse=True)
    valid_b.sort(key=compute_composite_ranking_score, reverse=True)

    top_news = list(valid_a)
    for it in valid_b:
        if len(top_news) >= max_items:
            break
        top_news.append(it)
    return top_news


def run_fna_pipeline(max_items: int = 15, debug: bool = False) -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes the event-first FNA pipeline and returns (top_news_items, formatted_report_text).
    """
    now = datetime.now()
    report_date_str = now.strftime("%d %B %Y")
    iso_date = now.strftime("%Y-%m-%d")

    print("[INFO] Collecting exchange filings...")
    logger.info("Collecting exchange filings...")
    raw_announcements = get_all_exchange_announcements()

    print("[INFO] Collecting financial news feeds...")
    logger.info("Collecting financial news feeds...")
    raw_news = collect_market_news()

    all_raw_events = []

    # Process Announcements
    for ann in raw_announcements:
        all_raw_events.append({
            "title": ann.get("title", ""),
            "summary": ann.get("summary", ""),
            "source": ann.get("source", "NSE Corporate Announcements"),
            "url": ann.get("url", ""),
            "filing_symbol": ann.get("raw_symbol") or ann.get("symbol"),
            "published_at": ann.get("published_at", ""),
            "is_primary": True
        })

    # Process News items
    for news in raw_news:
        all_raw_events.append({
            "title": news.get("title", ""),
            "summary": news.get("summary", ""),
            "source": news.get("source", "Financial News"),
            "url": news.get("url", ""),
            "filing_symbol": None,
            "published_at": news.get("published_at", ""),
            "is_primary": False
        })

    logger.info(f"Ingested {len(all_raw_events)} raw market developments.")

    # Step 2: Quality Gate 1 — Noise Filter
    print("[INFO] Filtering routine disclosures and stale news...")
    logger.info("Filtering routine disclosures and stale news...")
    material_events = []
    for ev in all_raw_events:
        is_mat, reason = is_material_fundamental_event(
            ev["title"],
            ev["summary"],
            is_primary_exchange_filing=ev.get("is_primary", False),
            published_at=ev.get("published_at", "")
        )
        if is_mat:
            material_events.append(ev)
        elif debug:
            print(f"[REJECT NOISE] {ev['title'][:60]}... Reason: {reason}")
            logger.debug(f"Filtered: {ev['title'][:60]}... Reason: {reason}")

    logger.info(f"{len(material_events)} material developments passed noise gate.")

    # Step 3: Quality Gate 2 — Entity Resolution & Verification
    print("[INFO] Resolving corporate entities...")
    logger.info("Resolving corporate entities...")
    resolved_events = []
    for ev in material_events:
        full_text = f"{ev['title']} {ev['summary']}"
        entity_meta, res_reason = resolve_entity_from_text(full_text, filing_symbol=ev.get("filing_symbol"))

        if not entity_meta:
            if debug:
                print(f"[REJECT UNRESOLVED] '{ev['title'][:60]}' — {res_reason}")
                logger.debug(f"Entity Unresolved: '{ev['title']}' — {res_reason}")
            continue

        assigned_symbol = entity_meta["symbol"]

        # Validate entity (catches parent-subsidiary mismatch or client vs vendor confusion)
        is_valid, val_reason = validate_event_entity(ev["title"], ev["summary"], assigned_symbol)
        if not is_valid:
            if debug:
                print(f"[REJECT VALIDATION] '{ev['title'][:60]}' — {val_reason}")
                logger.debug(f"Entity Validation Rejected: {val_reason}")
            continue

        if debug:
            from engine.entity_mapper import resolve_event_companies_and_roles
            roles = resolve_event_companies_and_roles(full_text)
            if roles:
                print(f"[ROLE RESOLUTION] \"{ev['title'][:70]}\"")
                for r in roles:
                    is_ben = "YES" if r["symbol"] == assigned_symbol else "NO"
                    print(f"  - {r['name']} ({r['symbol']}) -> ROLE: {r['role']} (Economic Beneficiary: {is_ben})")
                print(f"  Selected Entity: {entity_meta['name']} ({assigned_symbol})")

        ev_copy = dict(ev)
        ev_copy["company_name"] = entity_meta["name"]
        ev_copy["symbol"] = assigned_symbol
        ev_copy["sector"] = entity_meta["sector"]
        resolved_events.append(ev_copy)

    logger.info(f"{len(resolved_events)} events successfully validated to distinct listed entities.")

    # Step 4: Quality Gate 3 — Event Deduplication & Multi-Source Clustering
    print("[INFO] Deduplicating and clustering developments...")
    logger.info("Deduplicating and clustering developments...")
    clusters = deduplicate_and_cluster_news(resolved_events, similarity_threshold=0.35)
    logger.info(f"Clustered into {len(clusters)} distinct canonical fundamental events.")

    # Step 5: Fundamental Analysis & Two-Stage Selection (Section 6, 7 & 8)
    print("[INFO] Fetching market and financial data...")
    print("[INFO] Evaluating fundamental materiality & tiers...")
    print("[INFO] Synthesizing Sharekhan-style report...")
    logger.info("Synthesizing Event-Specific Fundamental Intelligence...")
    
    qualified_tier_a = []
    qualified_tier_b = []
    seen_companies = {}

    for cluster in clusters:
        sym = cluster.get("symbol")
        if not sym:
            continue

        c_title = cluster.get("title", "")[:60]
        c_comp = cluster.get("company_name", sym)

        # Synthesize Sharekhan-style item (strictly Positive or Negative only across 16 canonical types)
        item = synthesize_fna_item(cluster)
        if not item:
            if debug:
                print(f"[CANDIDATE] {c_comp} — {c_title}\n[STATUS] Tier C\n[REASON] Ambiguous or non-binary directional catalyst\n[DECISION] REJECT\n")
            continue

        direction = item.get("fundamental_direction")
        if direction not in ["Positive", "Negative"]:
            if debug:
                print(f"[CANDIDATE] {c_comp} — {c_title}\n[STATUS] Tier C\n[REASON] Direction {direction} is not strictly Positive/Negative\n[DECISION] REJECT\n")
            continue

        tier = item.get("tier", "Tier B")
        company_key = item.get("symbol") or item.get("company_name", sym)

        # Stage 1: Categorization into Materiality Tiers
        if tier == "Tier C":
            if debug:
                print(f"[CANDIDATE] {c_comp} — {item.get('headline')}\n[STATUS] Tier C\n[REASON] Low materiality or routine disclosure\n[DECISION] REJECT\n")
            continue

        # Avoid duplicate events for same company; retain highest materiality
        if company_key in seen_companies:
            prev_tier, prev_item = seen_companies[company_key]
            if item.get("materiality_score", 0) > prev_item.get("materiality_score", 0):
                if prev_tier == "Tier A" and prev_item in qualified_tier_a:
                    qualified_tier_a.remove(prev_item)
                elif prev_tier == "Tier B" and prev_item in qualified_tier_b:
                    qualified_tier_b.remove(prev_item)
                seen_companies[company_key] = (tier, item)
                if tier == "Tier A":
                    qualified_tier_a.append(item)
                else:
                    qualified_tier_b.append(item)
                save_fna_event(item)
            continue

        seen_companies[company_key] = (tier, item)
        if tier == "Tier A":
            qualified_tier_a.append(item)
        else:
            qualified_tier_b.append(item)
        save_fna_event(item)

    # Step 6: Relative Daily Ranking across valid events (Section 7 & 32-34)
    top_news = select_daily_top_news(qualified_tier_a, qualified_tier_b, max_items=max_items)

    # Log candidate selection decisions matching Section 41
    if debug:
        for it in top_news:
            fin_info = f"Order/Val: ₹{it.get('order_value_cr')} Cr" if it.get("order_value_cr") else "Impact established qualitatively"
            print(f"[CANDIDATE] {it.get('company_name')} — {it.get('headline')}\n[STATUS] {it.get('tier')}\n[REASON] {fin_info} | {it.get('event_type')}\n[DECISION] INCLUDED\n")

    fna_items = top_news

    # Print pipeline diagnostic counters matching Section 37
    print(f"[INFO] Raw developments: {len(all_raw_events)}")
    print(f"[INFO] Potentially fundamental: {len(material_events)}")
    print(f"[INFO] Entity-validated: {len(resolved_events)}")
    print(f"[INFO] Canonical events: {len(clusters)}")
    print(f"[INFO] FNA-worthy: {len(qualified_tier_a) + len(qualified_tier_b)}")
    print(f"[INFO] Final TOP NEWS: {len(top_news)}")

    logger.info(f"Selected {len(top_news)} TOP NEWS stories for final bulletin.")

    # Step 7: Format strictly ONLY TOP NEWS report
    print("[INFO] Validating and archiving report...")
    logger.info("Validating and archiving report...")
    report_text = format_top_news_report(report_date_str, top_news)

    # Persist report to SQLite and files
    report_id = f"FNA_{now.strftime('%Y%m%d_%H%M%S')}"
    save_fna_report(
        report_id=report_id,
        report_date=iso_date,
        item_count=len(top_news),
        report_text=report_text,
        report_json=json.dumps(top_news, default=str)
    )

    # Export to text and json files
    txt_path = os.path.join(REPORTS_DIR, f"fna_{iso_date}.txt")
    json_path = os.path.join(REPORTS_DIR, f"fna_{iso_date}.json")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(top_news, f, indent=2, default=str)

    return top_news, report_text


def format_top_news_report(report_date_str: str, items: List[Dict[str, Any]]) -> str:
    """
    Formats the intelligence bulletin matching the Sharekhan FNA CLI format.
    STRICTLY ONLY TOP NEWS. No Macro Wrap. No Watchlist. No Trading Signals.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("        🇮🇳 FUNDAMENTAL NEWS & ANALYSIS")
    lines.append("        Indian Equity Market")
    lines.append(f"        {report_date_str}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("TOP NEWS")
    lines.append("")

    if not items:
        lines.append("No material fundamental developments passed quality gating today.")
        lines.append("")
    else:
        for i, item in enumerate(items, start=1):
            clean_ticker = item.get("symbol", "").replace(".NS", "").replace(".BO", "")
            company_header = f"{item.get('company_name')} ({clean_ticker}) — {item.get('fundamental_direction')}"
            
            lines.append(f"{i}. {company_header}")
            lines.append(f"   {item.get('headline')}")
            lines.append("")
            lines.append("   What happened:")
            lines.append(f"   {item.get('what_happened')}")
            lines.append("")
            lines.append("   Why it matters:")
            lines.append(f"   {item.get('why_it_matters')}")
            lines.append("")
            lines.append("   Fundamental impact:")
            lines.append(f"   {item.get('fundamental_impact')}")
            lines.append("")
            lines.append("   Key financial implication:")
            lines.append(f"   {item.get('key_financial_implication')}")
            lines.append("")
            lines.append("   Time horizon:")
            lines.append(f"   {item.get('time_horizon')}")
            lines.append("")
            lines.append("   Sources:")
            lines.append(f"   {item.get('sources')}")
            lines.append("")
            lines.append("-" * 60)
            lines.append("")

    lines.append("=" * 60)
    lines.append("TOP NEWS COMPLETE")
    lines.append("=" * 60)

    return "\n".join(lines)
