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
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity, clean_extracted_entity_name
from engine.equity_master import resolve_entity
from engine.policy_macro_engine import detect_policy_event, detect_macro_item
from engine.deduplicator import deduplicate_and_cluster_news
from engine.fna_analyzer import synthesize_fna_item
from engine.db import (
    save_fna_event, 
    save_fna_report, 
    get_connection,
    get_cached_news_by_date,
    get_surfaced_events_in_window,
    is_stale_recurrent_event,
    save_surfaced_events
)
from engine.candidate_engine import (
    compute_research_importance_model,
    assign_materiality_tier,
    map_event_to_discovery_bucket,
    rank_daily_research_candidates,
    is_genuinely_actionable_candidate,
    format_candidate_debug_log,
    normalize_company_key
)
from engine.macro_commentary import generate_macro_commentary
from engine.sector_causal_engine import evaluate_sector_causal_chains

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def run_company_trace(
    trace_company: str,
    all_raw_events: List[Dict[str, Any]],
    material_events: List[Dict[str, Any]],
    resolved_events: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    evaluated_candidates: List[Dict[str, Any]],
    actionable_candidates: List[Dict[str, Any]],
    top_news: List[Dict[str, Any]]
) -> None:
    """
    Diagnostically traces a target company across all 6 pipeline stages:
    1. Ingestion: did raw feeds pull articles mentioning company?
    2. Noise Filter: did it survive routine noise rejection?
    3. Entity Resolution: did it resolve to an NSE/BSE symbol and assign economic role?
    4. Canonical Deduplication: which cluster was it grouped into?
    5. Scoring & Actionability: what was its score, tier, and actionability reason?
    6. Final Selection: was it selected in TOP NEWS or omitted?
    """
    query = trace_company.strip().lower()
    norm_query = normalize_company_key(query)
    target_meta, _ = resolve_entity_from_text(trace_company)
    target_sym = target_meta.get("symbol") if target_meta else None

    def matches(item: Dict[str, Any]) -> bool:
        sym = (item.get("symbol") or item.get("filing_symbol") or "").strip().upper()
        if target_sym and sym and (sym == target_sym or sym.replace(".NS", "").replace(".BO", "") == target_sym.replace(".NS", "").replace(".BO", "")):
            return True
        t = (str(item.get("title", "")) + " " + str(item.get("summary", "")) + " " + 
             str(item.get("company_name", "")) + " " + str(item.get("symbol", "")) + " " +
             str(item.get("headline", "")) + " " + str(item.get("what_happened", ""))).lower()
        if query in t:
            return True
        if target_meta:
            for al in target_meta.get("aliases", []):
                if len(al) >= 4 and al in t:
                    return True
        norm_c = normalize_company_key(item.get("company_name", ""), item.get("symbol", ""))
        if norm_c and len(norm_c) >= 3 and (norm_query in norm_c or norm_c in norm_query):
            return True
        import difflib
        if norm_c and len(norm_c) >= 4 and difflib.SequenceMatcher(None, norm_query, norm_c).ratio() >= 0.75:
            return True
        q_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", norm_query))
        c_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", norm_c))
        if q_tokens and c_tokens:
            if q_tokens.issubset(c_tokens):
                return True
            if len(c_tokens) >= 2 and c_tokens.issubset(q_tokens):
                return True
        return False

    print("\n" + "=" * 70)
    print(f"       COMPANY TRACE REPORT: '{trace_company}'")
    print("=" * 70)

    # Stage 1: Ingestion
    ingested = [ev for ev in all_raw_events if matches(ev)]
    print(f"\n[STAGE 1: INGESTION] Found {len(ingested)} matching raw items.")
    for idx, ev in enumerate(ingested[:5], 1):
        print(f"  {idx}. [{ev.get('source')}] {ev.get('title')[:80]} (Published: {ev.get('published_at')})")

    # Stage 2: Noise Filter
    survived_noise = [ev for ev in material_events if matches(ev)]
    print(f"\n[STAGE 2: NOISE FILTER] {len(survived_noise)} / {len(ingested)} survived noise filter.")
    if len(ingested) > len(survived_noise):
        diff = [ev for ev in ingested if ev not in survived_noise]
        for idx, ev in enumerate(diff[:3], 1):
            from engine.noise_filter import is_material_fundamental_event
            _, r = is_material_fundamental_event(ev["title"], ev["summary"], is_primary_exchange_filing=ev.get("is_primary", False))
            print(f"  Filtered {idx}: {ev.get('title')[:60]}... Reason: {r}")

    # Stage 3: Entity Resolution
    resolved = [ev for ev in resolved_events if matches(ev)]
    print(f"\n[STAGE 3: ENTITY RESOLUTION] {len(resolved)} items resolved.")
    for idx, ev in enumerate(resolved[:3], 1):
        print(f"  Resolved {idx}: Entity='{ev.get('company_name')}' Symbol='{ev.get('symbol')}' Sector='{ev.get('sector')}'")

    # Stage 4: Clustering
    in_clusters = [cl for cl in clusters if matches(cl)]
    print(f"\n[STAGE 4: CLUSTERING] Present in {len(in_clusters)} canonical clusters.")
    for idx, cl in enumerate(in_clusters[:3], 1):
        print(f"  Cluster {idx}: '{cl.get('title', '')[:70]}' (Sources: {len(cl.get('sources', []))})")

    # Stage 5: Evaluation & Scoring
    evaled = [cand for cand in evaluated_candidates if matches(cand)]
    print(f"\n[STAGE 5: EVALUATION & ACTIONABILITY] {len(evaled)} candidates evaluated.")
    for idx, cand in enumerate(evaled[:3], 1):
        sc = cand.get("research_scores", {}).get("total_score", cand.get("research_importance_score", "N/A"))
        tier = cand.get("tier", "N/A")
        reason = cand.get("actionable_reason", "Not assessed")
        stale_reason = cand.get("cross_day_stale_reason")
        print(f"  Candidate {idx}: Score={sc} | Tier={tier} | EventType={cand.get('event_type')}")
        print(f"    Actionability: {reason}")
        if stale_reason:
            print(f"    Cross-Day Status: Omitted (Stale recurrent: {stale_reason})")
        print(f"    Headline: {cand.get('headline', '')[:80]}")

    # Stage 6: Final Selection
    final_matches = [it for it in top_news if matches(it)]
    print(f"\n[STAGE 6: FINAL TOP NEWS SELECTION] {len(final_matches)} included in final TOP NEWS.")
    if final_matches:
        for it in final_matches:
            print(f"  SELECTED: {it.get('company_name')} ({it.get('symbol')}) — Direction: {it.get('fundamental_direction')}")
    else:
        print(f"  OMITTED: '{trace_company}' was not selected in final TOP NEWS list.")
    print("=" * 70 + "\n")


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


def select_daily_top_news(qualified_tier_a: List[Dict[str, Any]], qualified_tier_b: List[Dict[str, Any]], max_items: int = 5) -> List[Dict[str, Any]]:
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


def run_fna_pipeline(
    max_items: Optional[int] = None, 
    debug: bool = False, 
    target_date: Optional[str] = None, 
    cutoff_time: str = "23:59:59", 
    min_target: int = 4,
    trace_company: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str]:
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
    # Include articles already cached/ingested in SQLite for this target date
    cached_db_news = get_cached_news_by_date(iso_date)
    if cached_db_news:
        raw_news.extend(cached_db_news)

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
            # Check for multi-company policy event or standalone macro trigger
            pol_item = detect_policy_event(ev)
            if pol_item:
                resolved_events.append(pol_item)
                if debug:
                    print(f"[RESOLVED POLICY EVENT] '{ev['title'][:60]}' -> Sector: {pol_item.get('sector')}")
                continue
            
            macro_item = detect_macro_item(ev)
            if macro_item:
                resolved_events.append(macro_item)
                if debug:
                    print(f"[RESOLVED MACRO ITEM] '{ev['title'][:60]}' -> Sector: {macro_item.get('sector')}")
                continue

            if debug:
                print(f"[REJECT UNRESOLVED] '{ev['title'][:60]}' — {res_reason}")
                logger.debug(f"Entity Unresolved: '{ev['title']}' — {res_reason}")
            continue

        assigned_symbol = entity_meta["symbol"]
        raw_company_name = entity_meta["name"]

        # Quality Gate 2.1: Authoritative Grounded Entity Lookup against official NSE/BSE master
        grounded = resolve_entity(raw_company_name, symbol=assigned_symbol)
        if not grounded:
            if debug:
                print(f"[REJECT UNLISTED] '{ev['title'][:60]}' — '{raw_company_name}' ({assigned_symbol}) is not in official listed master")
                logger.debug(f"Entity Unlisted: '{raw_company_name}' is not in official listed master")
            continue
        official_ticker, official_name = grounded

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
                print(f"  Selected Entity: {official_name} ({official_ticker})")

        ev_copy = dict(ev)
        ev_copy["company_name"] = official_name
        ev_copy["ticker"] = official_ticker
        ev_copy["symbol"] = assigned_symbol
        ev_copy["sector"] = entity_meta["sector"]
        resolved_events.append(ev_copy)

    logger.info(f"{len(resolved_events)} events successfully validated to distinct listed entities.")

    # Step 4: Quality Gate 3 — Event Deduplication & Multi-Source Clustering
    print("[INFO] Deduplicating and clustering developments...")
    logger.info("Deduplicating and clustering developments...")
    clusters = deduplicate_and_cluster_news(resolved_events, similarity_threshold=0.55)
    logger.info(f"Clustered into {len(clusters)} distinct canonical fundamental events.")

    # Step 5: Research Candidate Evaluation & Materiality Tiering
    print("[INFO] Fetching market and financial data...")
    print("[INFO] Evaluating fundamental materiality & research scores...")
    print("[INFO] Synthesizing Sharekhan-style report...")
    logger.info("Synthesizing Event-Specific Fundamental Intelligence...")
    
    evaluated_candidates = []
    seen_companies = {}

    for cluster in clusters:
        cand_type = cluster.get("candidate_type")
        # Direct pass-through for already synthesized Policy and Macro intelligence entries
        if cand_type in ["POLICY_EVENT", "MACRO_EVENT"]:
            cluster["tier"] = cluster.get("tier", "Tier A")
            evaluated_candidates.append(cluster)
            save_fna_event(cluster)
            continue

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

        company_key = normalize_company_key(item.get("company_name", ""), item.get("symbol", sym))

        # Retain highest importance candidate per company in the evaluated pool
        # Materiality preference: quantified financial results beat vague qualitative announcements
        if company_key in seen_companies:
            prev_item = seen_companies[company_key]
            prev_is_fin = prev_item.get("event_type") == "FINANCIAL_RESULT"
            curr_is_fin = item.get("event_type") == "FINANCIAL_RESULT"
            prefer_curr = False
            if curr_is_fin and not prev_is_fin:
                prefer_curr = True
            elif prev_is_fin and not curr_is_fin:
                prefer_curr = False
            elif item.get("research_importance_score", 0) > prev_item.get("research_importance_score", 0):
                prefer_curr = True

            primary_item = item if prefer_curr else prev_item
            secondary_item = prev_item if prefer_curr else item

            if prefer_curr:
                evaluated_candidates.remove(prev_item)
                seen_companies[company_key] = primary_item
                evaluated_candidates.append(primary_item)

            # Preserve secondary material fact in primary item
            sec_headline = secondary_item.get("headline", "")
            sec_summary = secondary_item.get("what_happened", "")
            sec_text = secondary_item.get("flowing_prose", "") or sec_summary

            if "secondary_developments" not in primary_item:
                primary_item["secondary_developments"] = []
            primary_item["secondary_developments"].append({
                "headline": sec_headline,
                "what_happened": sec_summary,
                "event_type": secondary_item.get("event_type")
            })

            save_fna_event(primary_item)
            continue

        seen_companies[company_key] = item
        evaluated_candidates.append(item)
        save_fna_event(item)

    # Step 5.1: Actionability Assessment across evaluated candidates
    actionable_candidates = []
    for cand in evaluated_candidates:
        is_act, reason = is_genuinely_actionable_candidate(cand)
        if is_act:
            cand["actionable_reason"] = reason
            actionable_candidates.append(cand)

    # Cross-Day Deduplication (Gap 1)
    # Check candidates against persistent store of surfaced fingerprints from prior 2 trading days.
    prior_surfaced = get_surfaced_events_in_window(iso_date, lookback_days=2)
    fresh_evaluated_candidates = []
    for cand in evaluated_candidates:
        is_stale, stale_reason = is_stale_recurrent_event(cand, prior_surfaced)
        if is_stale:
            cand["cross_day_stale_reason"] = stale_reason
            logger.info(f"Cross-day dedup omitted {cand.get('company_name')}: {stale_reason}")
            if debug:
                print(f"[CROSS-DAY DEDUP] Omitted {cand.get('company_name')}: {stale_reason}")
        else:
            fresh_evaluated_candidates.append(cand)

    # Diagnostic logging: print every candidate's final score before selection cap (Requirement 2)
    print("\n" + "=" * 60)
    print("      CANDIDATE SCORES BEFORE SELECTION CAP")
    print("=" * 60)
    logger.info("CANDIDATE SCORES BEFORE SELECTION CAP:")
    for c in sorted(fresh_evaluated_candidates, key=lambda x: x.get("research_importance_score", 0.0), reverse=True):
        c_score = c.get("research_importance_score", 0.0)
        c_name = clean_extracted_entity_name(c.get("company_name", ""))
        c_sym = c.get("symbol", "")
        c_tier = c.get("tier", "")
        c_type = c.get("event_type", "")
        c_head = (c.get("headline", "") or "")[:50]
        print(f"  {c_name:<30} ({c_sym:<12}) | Score: {c_score:>5.2f} | Tier: {c_tier:<6} | {c_type:<18} | {c_head}")
        logger.info(f"  {c_name} ({c_sym}) | Score: {c_score:.2f} | Tier: {c_tier} | {c_type} | {c_head}")
    print("=" * 60 + "\n")

    # Step 6: Relative Daily Ranking & Selection
    # Discovers genuinely actionable stocks, capped at roughly 5-8 company items.
    ranked_pool = rank_daily_research_candidates(
        fresh_evaluated_candidates,
        max_items=max_items,
        min_target=min_target,
        max_ceiling=10
    )

    from engine.candidate_scanner import get_closing_price_for_date
    print(f"[INFO] Fetching closing prices for candidates on {iso_date} (best-effort)...")
    valid_listed_news = []
    seen_selected_companies = set()
    for it in ranked_pool:
        comp_key = normalize_company_key(it.get("company_name", ""), it.get("symbol", ""))
        if comp_key in seen_selected_companies:
            continue

        sym = it.get("symbol", "")
        close_p = None
        if sym and not sym.startswith(("SECTOR:", "MACRO:")):
            try:
                close_p = get_closing_price_for_date(sym, target_date=iso_date)
            except Exception as e:
                logger.debug(f"Price lookup skipped for {sym}: {e}")

        # Best-effort price attachment — NEVER omit candidate on lookup failure
        if close_p is not None and close_p > 0:
            it["closing_price"] = close_p
        else:
            it["closing_price"] = None
            logger.info(f"Candidate {sym} ({it.get('company_name')}): retained without price.")

        valid_listed_news.append(it)
        seen_selected_companies.add(comp_key)
        if max_items is not None and len(valid_listed_news) >= max_items:
            break

    # Macro Commentary & Gated Sector Causal Commentary (Requirements 1 & 5)
    macro_commentary = generate_macro_commentary(all_raw_events, iso_date)
    sector_causals = evaluate_sector_causal_chains(material_events, iso_date)

    # Gate sector causal chains: Hold any items requiring review in a separate pending file
    # and DO NOT auto-publish unreviewed causal speculations into the main bulletin.
    unreviewed_causals = []
    approved_causals = []
    for sc in sector_causals:
        flag = sc.get("human_review_flag", "")
        if "requires review" in flag.lower() or flag:
            unreviewed_causals.append(sc)
        else:
            approved_causals.append(sc)

    if unreviewed_causals:
        causals_path_json = os.path.join(REPORTS_DIR, f"pending_review_causal_chains_{iso_date}.json")
        with open(causals_path_json, "w", encoding="utf-8") as f:
            json.dump(unreviewed_causals, f, indent=2, default=str)
        print(f"[INFO] {len(unreviewed_causals)} sector causal chain(s) held for human review -> {causals_path_json}")
        logger.info(f"Routed {len(unreviewed_causals)} sector causal chain(s) to pending review file: {causals_path_json}")

    # Final output: strictly ranked list of actionable stocks ordered by descending materiality score
    # Drop macro commentary and sector causal commentary completely from the stock list (no ticker)
    top_news = list(valid_listed_news)

    def top_news_sort_key(x):
        sc = x.get("research_scores")
        if isinstance(sc, dict):
            return -float(sc.get("total_score", sc.get("research_importance_score", 0.0)))
        return -float(x.get("research_importance_score", 0.0) or 0.0)

    top_news.sort(key=top_news_sort_key)

    # Dynamic cap: Keep whatever the existing Tier A/B materiality gate produces (unless max_items explicitly set)
    if max_items is not None:
        top_news = top_news[:max_items]

    # Persist today's surfaced events to SQLite store to prevent repeats tomorrow (Gap 1)
    save_surfaced_events(top_news, iso_date)

    # Run Company Tracing if requested (Gap 2)
    if trace_company:
        run_company_trace(
            trace_company,
            all_raw_events,
            material_events,
            resolved_events,
            clusters,
            evaluated_candidates,
            actionable_candidates,
            top_news
        )

    # Log candidate selection decisions in debug mode
    if debug:
        selected_ids = {it.get("news_id") or it.get("headline") for it in top_news}
        for it in evaluated_candidates:
            is_sel = (it.get("news_id") or it.get("headline")) in selected_ids
            decision_str = "INCLUDED" if is_sel else "OMITTED (Ranked below daily threshold)"
            print(format_candidate_debug_log(it, decision=decision_str))

    fna_items = top_news

    # Print pipeline diagnostic counters matching Section 12 exactly
    print("\n" + "=" * 60)
    print("        RESEARCH EXECUTION DIAGNOSTICS")
    print("=" * 60)
    print(f"Requested Research Date: {iso_date} (Cutoff: {cutoff_dt.strftime('%H:%M:%S IST')})")
    print(f"Candidates Retrieved: {len(all_raw_events)}")
    print(f"Surviving Initial Materiality: {len(material_events)}")
    print(f"Validated Entities: {len(resolved_events)}")
    print(f"Canonical Events: {len(clusters)}")
    print(f"Fundamental Candidates Evaluated: {len(evaluated_candidates)}")
    print(f"Actionable Candidates: {len(actionable_candidates)}")
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


def build_one_line_reason(item: Dict[str, Any]) -> str:
    """
    Constructs a crisp, single-sentence fundamental reason with the key number
    (monetary value, physical capacity, percentage, or volume metric).
    """
    headline = (item.get("headline") or "").strip()
    summary = (item.get("what_happened") or item.get("summary") or "").strip()
    order_val = item.get("order_value_cr")
    pct_rev = item.get("relative_revenue_pct")
    range_text = item.get("range_text")
    company = item.get("company_name", "")

    # Base candidate text
    base_text = headline if len(headline) > 15 else summary
    if not base_text:
        base_text = "Key corporate milestone announced."

    from engine.fna_analyzer import clean_fundamental_headline
    clean = clean_fundamental_headline(base_text, company)
    clean = re.sub(r"\bRs\.?\s*(\d+)", r"₹\1", clean)
    clean = re.sub(r"\b(?:crore|crores)\b", "Cr", clean, flags=re.IGNORECASE)

    # Check if a concrete number is present in clean text
    has_number = bool(re.search(r"(?:₹|%|\b\d+)", clean))
    if not has_number:
        if order_val:
            clean = f"{clean} valued at ₹{order_val:,.1f} Cr"
        elif pct_rev:
            clean = f"{clean} (~{pct_rev:.1f}% of revenue)"
        elif range_text:
            clean = f"{clean} ({range_text})"

    # Remove any trailing periods and normalize spaces
    clean = re.sub(r"\s+", " ", clean).strip().rstrip(".")
    return clean


def format_top_news_report(report_date_str: str, items: List[Dict[str, Any]]) -> str:
    """
    Formats the intelligence bulletin into a ranked list ordered by descending materiality score:
      1. TICKER — Positive/Negative — one-line reason with the key number
      2. TICKER — ...
    Zero confidence tags, zero extra fields. Dynamic cap.
    Macro/global context and sector causal chains are completely omitted (they have no ticker).
    """
    from engine.equity_master import resolve_entity

    # Filter strictly to listed company candidates with valid tickers
    stock_candidates = []
    for it in items:
        if not it or not isinstance(it, dict):
            continue
        cand_type = it.get("candidate_type", "")
        # Drop macro and sector causal chains entirely
        if cand_type in ["MACRO_COMMENTARY", "SECTOR_CAUSAL_COMMENTARY", "POLICY_EVENT", "MACRO_EVENT"]:
            continue

        raw_name = it.get("company_name", "")
        raw_sym = it.get("symbol", "")
        grounded = resolve_entity(raw_name, symbol=raw_sym)
        if not grounded and not raw_sym:
            continue

        it_copy = dict(it)
        if grounded:
            official_ticker, official_name = grounded
            it_copy["ticker"] = official_ticker
            it_copy["company_name"] = official_name
        else:
            clean_sym = raw_sym.replace(".NS", "").replace(".BO", "").strip()
            it_copy["ticker"] = clean_sym or raw_name

        stock_candidates.append(it_copy)

    # Sort strictly by descending research importance score / materiality score
    def get_cand_score(x):
        sc = x.get("research_scores")
        if isinstance(sc, dict):
            return float(sc.get("total_score", sc.get("research_importance_score", 0.0)))
        if "research_importance_score" in x:
            return float(x["research_importance_score"])
        return float(x.get("materiality_score", 0.0))

    stock_candidates.sort(key=get_cand_score, reverse=True)

    if not stock_candidates:
        return "No verified corporate disclosures available"

    lines = []
    for idx, it in enumerate(stock_candidates, start=1):
        ticker = it.get("ticker") or it.get("symbol", "").replace(".NS", "").replace(".BO", "") or it.get("company_name", "")
        direction = it.get("fundamental_direction") or it.get("direction", "Positive")
        reason = build_one_line_reason(it)
        lines.append(f"{idx}. {ticker} — {direction} — {reason}")

    return "\n".join(lines).replace("\r\n", "\n").replace("\r", " ")
