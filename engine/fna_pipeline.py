"""
FNA Master Pipeline: Event-First Fundamental News & Analysis Engine.
Implements the full Sharekhan-style daily intelligence flow:
  Ingest -> Noise Gate -> Entity Resolution Gate -> Deduplication Gate
  -> Financial Context & Materiality -> Synthesis -> Rank -> Format ONLY TOP NEWS.
"""

import os
import json
import logging
import re
import zoneinfo
from email.utils import parsedate_to_datetime
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from engine.nse_bse_client import get_all_exchange_announcements, get_historical_exchange_announcements
from engine.news_collector import collect_market_news, collect_historical_market_news
from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity
from engine.deduplicator import deduplicate_and_cluster_news
from engine.fna_analyzer import synthesize_fna_item
from engine.db import save_fna_event, save_fna_report, get_connection
from engine.candidate_engine import (
    compute_research_importance_model,
    assign_materiality_tier,
    map_event_to_discovery_bucket,
    rank_daily_research_candidates,
    format_candidate_debug_log
)

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def parse_datetime_ist(date_str: str) -> Optional[datetime]:
    """Parses date/time strings from RSS or exchange feeds into Asia/Kolkata (IST) timezone."""
    if not date_str:
        return None
    s = str(date_str).strip()
    # Try RFC 2822 (standard in RSS feeds)
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        pass
    # Try ISO format
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        pass
    # Try explicit common formats
    for fmt in ["%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=IST)
        except Exception:
            pass
    return None


def split_multi_company_article(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Splits multi-company roundup containers (e.g. 'Stocks in news: A, B, C, D')
    into separate company-event pairs for independent validation.
    """
    title = event.get("title", "")
    summary = event.get("summary", "")
    text = event.get("text", "") or summary

    is_roundup = bool(re.search(r"\b(?:stocks\s+in\s+news|stocks\s+to\s+watch|stocks\s+to\s+track|buzzing\s+stocks)\b", title, re.IGNORECASE))
    if not is_roundup and title.split(" - ")[0].count(",") < 2:
        return [event]

    # First attempt: split by line breaks, bullets, or semicolons
    lines = re.split(r"[\r\n]+|[•▪]\s*|;\s*", text)
    sub_events = []
    for line in lines:
        line = line.strip()
        if len(line) < 20:
            continue
        match = re.match(r"^([A-Za-z0-9\s&.\-]+?)[:\-–—]\s*(.+)$", line)
        if match:
            comp_name = match.group(1).strip()
            desc = match.group(2).strip()
            if len(comp_name) < 40 and len(desc) > 15:
                sub_events.append({
                    "title": f"{comp_name}: {desc[:100]}",
                    "company": comp_name,
                    "summary": desc,
                    "text": desc,
                    "source": event.get("source", "Financial News"),
                    "url": event.get("url", ""),
                    "filing_symbol": None,
                    "published_at": event.get("published_at", ""),
                    "publication_date": event.get("publication_date", ""),
                    "event_date": event.get("event_date", ""),
                    "discovery_date": event.get("discovery_date", ""),
                    "is_primary": False
                })

    # Second attempt: if no colon/bullet split found, split by sentences mentioning actions
    if not sub_events:
        sentences = re.split(r"\.\s+(?=[A-Z])", text)
        for s in sentences:
            s = s.strip()
            if len(s) < 25:
                continue
            # Look for "Company [action verbs] ..."
            action_match = re.match(r"^([A-Z][A-Za-z0-9\s&.\-]+?)\s+(?:announced|secures?|secured|bags?|bagged|receives?|received|signs?|signed|approves?|approved|wins?|won|reports?|reported|posts?|posted)\b(.+)$", s, re.IGNORECASE)
            if action_match:
                comp_name = action_match.group(1).strip()
                desc = s
                if len(comp_name) < 40:
                    sub_events.append({
                        "title": f"{comp_name}: {desc[:100]}",
                        "company": comp_name,
                        "summary": desc,
                        "text": desc,
                        "source": event.get("source", "Financial News"),
                        "url": event.get("url", ""),
                        "filing_symbol": None,
                        "published_at": event.get("published_at", ""),
                        "publication_date": event.get("publication_date", ""),
                        "event_date": event.get("event_date", ""),
                        "discovery_date": event.get("discovery_date", ""),
                        "is_primary": False
                    })

    return sub_events if sub_events else [event]


def compute_composite_ranking_score(it: Dict[str, Any]) -> float:
    score = it.get("materiality_score", 7.0)
    # Bonus for quantified monetary value
    if it.get("order_value_cr") or it.get("range_text"):
        score += 0.5
    # Bonus for high-conviction events
    if it.get("event_type") in ["GOVERNMENT_EVENT", "MANAGEMENT_EVENT", "ORDER_CONTRACT", "FUNDING_EQUITY", "OPERATIONAL_INITIATIVE"]:
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


from engine.run_context import RunContext, set_current_context, get_current_context
from engine.db import cache_news


def run_fna_pipeline(max_items: int = 15, debug: bool = False, target_date: Optional[str] = None, cutoff_time: str = "23:59:59") -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes the event-first FNA pipeline and returns (top_news_items, formatted_report_text).
    Supports live scanning and historical date reconstruction via target_date in Asia/Kolkata timezone.
    Enforces central RunContext and zero current data leakage into past dates.
    """
    now_ist = datetime.now(IST)

    if target_date:
        try:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=IST)
        except ValueError:
            raise ValueError(f"Invalid date format '{target_date}'. Expected YYYY-MM-DD.")
        report_date_str = target_dt.strftime("%d %B %Y")
        iso_date = target_date
        cutoff_dt = datetime.strptime(f"{target_date} {cutoff_time}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        is_historical = (target_date < now_ist.strftime("%Y-%m-%d"))
    else:
        report_date_str = now_ist.strftime("%d %B %Y")
        iso_date = now_ist.strftime("%Y-%m-%d")
        cutoff_dt = now_ist
        is_historical = False

    # Initialize and register global RunContext (Section 7)
    ctx = RunContext(
        mode="historical" if is_historical else "live",
        target_date=iso_date,
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )
    set_current_context(ctx)

    all_raw_events = []
    seen_titles = set()

    # Step 1: Direct Source Research for requested date
    print(f"[INFO] Research date: {iso_date} (Cutoff: {cutoff_dt.strftime('%H:%M:%S IST')})")
    logger.info(f"FNA Research: research_date={iso_date}, mode={ctx.mode}, cutoff={cutoff_dt.isoformat()}")

    print(f"[INFO] Querying exchange announcements for {iso_date}...")
    logger.info(f"Querying exchange announcements for {iso_date}...")
    raw_announcements = get_all_exchange_announcements(target_date=iso_date)

    print(f"[INFO] Querying financial news and regulatory feeds for {iso_date}...")
    logger.info(f"Querying financial news and regulatory feeds for {iso_date}...")
    raw_news = collect_market_news(target_date=iso_date)

    for ann in raw_announcements:
        pub_str = ann.get("published_at", "")
        dt = parse_datetime_ist(pub_str) or (cutoff_dt if not is_historical else None)
        if not dt or not ctx.is_eligible(dt):
            continue
        title = ann.get("title", "")
        clean_title = re.sub(r"\s+", " ", title.strip().lower())
        if clean_title in seen_titles:
            continue
        seen_titles.add(clean_title)

        cache_news({
            "title": ann.get("title", ""),
            "summary": ann.get("summary", ""),
            "source": ann.get("source", "NSE Corporate Announcements"),
            "url": ann.get("url", ""),
            "published_at": pub_str,
            "symbol": ann.get("symbol") or ann.get("raw_symbol"),
        })

        all_raw_events.append({
            "title": ann.get("title", ""),
            "summary": ann.get("summary", ""),
            "source": ann.get("source", "NSE Corporate Announcements"),
            "url": ann.get("url", ""),
            "filing_symbol": ann.get("raw_symbol") or ann.get("symbol"),
            "published_at": pub_str,
            "publication_date": dt.isoformat(),
            "event_date": iso_date,
            "discovery_date": dt.strftime("%Y-%m-%d"),
            "is_primary": True
        })

    for news in raw_news:
        pub_str = news.get("published_at", "")
        dt = parse_datetime_ist(pub_str) or (cutoff_dt if not is_historical else None)
        if not dt or not ctx.is_eligible(dt):
            continue
        title = news.get("title", "")
        clean_title = re.sub(r"\s+", " ", title.strip().lower())
        if clean_title in seen_titles:
            continue
        seen_titles.add(clean_title)

        cache_news({
            "title": news.get("title", ""),
            "summary": news.get("summary", ""),
            "source": news.get("source", "Financial News"),
            "url": news.get("url", ""),
            "published_at": pub_str,
            "symbol": None,
        })

        all_raw_events.append({
            "title": news.get("title", ""),
            "summary": news.get("summary", ""),
            "source": news.get("source", "Financial News"),
            "url": news.get("url", ""),
            "filing_symbol": None,
            "published_at": pub_str,
            "publication_date": dt.isoformat(),
            "event_date": iso_date,
            "discovery_date": dt.strftime("%Y-%m-%d"),
            "is_primary": any(k in news.get("source", "").lower() for k in ["pib", "sebi", "rbi", "bureau", "regulator", "exchange"])
        })

    # Expand multi-company roundup containers into discrete candidate company-event pairs
    expanded_raw_events = []
    for ev in all_raw_events:
        sub_items = split_multi_company_article(ev)
        expanded_raw_events.extend(sub_items)
    all_raw_events = expanded_raw_events

    logger.info(f"Ingested {len(all_raw_events)} raw market developments for {iso_date}.")

    if not all_raw_events:
        warn_msg = f"[!] No verified corporate disclosures available for {report_date_str}."
        print(warn_msg)
        logger.warning(warn_msg)
        empty_report = (
            f"============================================================\n"
            f"        🇮🇳 FUNDAMENTAL NEWS & ANALYSIS\n"
            f"        Indian Equity Market\n"
            f"        {report_date_str}\n"
            f"============================================================\n\n"
            f"[!] No verified corporate disclosures available for {report_date_str}.\n"
        )
        return [], empty_report

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

    # Step 5: Research Candidate Evaluation & Materiality Tiering
    print("[INFO] Fetching market and financial data...")
    print("[INFO] Evaluating fundamental materiality & research scores...")
    print("[INFO] Synthesizing Sharekhan-style report...")
    logger.info("Synthesizing Event-Specific Fundamental Intelligence...")
    
    evaluated_candidates = []
    seen_companies = {}

    for cluster in clusters:
        sym = cluster.get("symbol")
        if not sym:
            continue

        c_title = cluster.get("title", "")[:60]
        c_comp = cluster.get("company_name", sym)

        # Synthesize Sharekhan-style item (strictly Positive or Negative only across canonical types)
        item = synthesize_fna_item(cluster, debug=debug)
        if not item:
            continue

        direction = item.get("fundamental_direction")
        if direction not in ["Positive", "Negative"]:
            if debug:
                print(f"[CANDIDATE] {c_comp} — {c_title}\n[STATUS] Rejected\n[REASON] Direction {direction} is not strictly Positive/Negative\n[DECISION] REJECT\n")
            continue

        # Evaluate using 10-Factor Research Importance Model
        score_dict = compute_research_importance_model(item)
        item["research_scores"] = score_dict
        item["research_importance_score"] = score_dict["total_score"]
        item["discovery_bucket"] = map_event_to_discovery_bucket(item.get("event_type", ""))

        # Assign Materiality Tier
        tier = assign_materiality_tier(item, score_dict["total_score"])
        item["tier"] = tier

        if tier == "Tier C":
            if debug:
                print(format_candidate_debug_log(item, decision="REJECT (Tier C)"))
            continue

        company_key = item.get("symbol") or item.get("company_name", sym)

        # Retain highest importance candidate per company
        if company_key in seen_companies:
            prev_item = seen_companies[company_key]
            if item.get("research_importance_score", 0) > prev_item.get("research_importance_score", 0):
                evaluated_candidates.remove(prev_item)
                seen_companies[company_key] = item
                evaluated_candidates.append(item)
                save_fna_event(item)
            continue

        seen_companies[company_key] = item
        evaluated_candidates.append(item)
        save_fna_event(item)

    # Step 6: Relative Daily Ranking & Bucket Balancing across valid candidates
    top_news = rank_daily_research_candidates(evaluated_candidates, max_items=max_items)

    # Log candidate selection decisions in debug mode
    if debug:
        selected_ids = {it.get("news_id") or it.get("headline") for it in top_news}
        for it in evaluated_candidates:
            is_sel = (it.get("news_id") or it.get("headline")) in selected_ids
            decision_str = "INCLUDED" if is_sel else "OMITTED (Ranked below daily threshold)"
            print(format_candidate_debug_log(it, decision=decision_str))

    fna_items = top_news

    # Print pipeline diagnostic counters
    print("\n" + "=" * 60)
    print("        RESEARCH EXECUTION DIAGNOSTICS")
    print("=" * 60)
    print(f"Requested Research Date: {iso_date} (Cutoff: {cutoff_dt.strftime('%H:%M:%S IST')})")
    print(f"Candidates Retrieved: {len(all_raw_events)}")
    print(f"Surviving Materiality Gate: {len(material_events)}")
    print(f"Surviving Entity Validation: {len(resolved_events)}")
    print(f"Canonical Event Clusters: {len(clusters)}")
    print(f"Research Candidates Evaluated: {len(evaluated_candidates)}")
    print(f"Final TOP NEWS: {len(top_news)}")
    print("=" * 60 + "\n")

    logger.info(f"Selected {len(top_news)} TOP NEWS stories for final bulletin.")

    # Step 7: Format strictly ONLY TOP NEWS report
    print("[INFO] Validating and archiving report...")
    logger.info("Validating and archiving report...")
    report_text = format_top_news_report(report_date_str, top_news)

    # Persist report to SQLite and files
    report_id = f"FNA_{iso_date}_{now_ist.strftime('%H%M%S')}"
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
            
            clean_headline = re.sub(r"[\r\n]+", " ", str(item.get("headline", ""))).strip()
            what_happened = re.sub(r"[\r\n]+", " ", str(item.get("what_happened", ""))).strip()
            why_it_matters = re.sub(r"[\r\n]+", " ", str(item.get("why_it_matters", ""))).strip()
            fund_impact = re.sub(r"[\r\n]+", " ", str(item.get("fundamental_impact", ""))).strip()
            fin_implication = re.sub(r"[\r\n]+", " ", str(item.get("key_financial_implication", ""))).strip()
            time_horizon = re.sub(r"[\r\n]+", " ", str(item.get("time_horizon", ""))).strip()
            sources = re.sub(r"[\r\n]+", " ", str(item.get("sources", ""))).strip()

            lines.append(f"{i}. {company_header}")
            lines.append(f"   {clean_headline}")
            lines.append("")
            lines.append("   What happened:")
            lines.append(f"   {what_happened}")
            lines.append("")
            lines.append("   Why it matters:")
            lines.append(f"   {why_it_matters}")
            lines.append("")
            lines.append("   Fundamental impact:")
            lines.append(f"   {fund_impact}")
            lines.append("")
            lines.append("   Key financial implication:")
            lines.append(f"   {fin_implication}")
            lines.append("")
            lines.append("   Time horizon:")
            lines.append(f"   {time_horizon}")
            lines.append("")
            lines.append("   Sources:")
            lines.append(f"   {sources}")
            lines.append("")
            lines.append("-" * 60)
            lines.append("")

    lines.append("=" * 60)
    lines.append("TOP NEWS COMPLETE")
    lines.append("=" * 60)

    # Normalize entire text to ensure pure standard Unix newlines and zero carriage returns
    return "\n".join(lines).replace("\r\n", "\n").replace("\r", " ")
