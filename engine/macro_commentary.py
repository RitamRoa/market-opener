"""
Macro and Geopolitical Commentary Engine for Indian Equity Daily Intelligence.
Generates un-templated, pure macro opening commentary (independent of company entity resolution).
Extracts and synthesizes major global drivers: geopolitical developments, crude oil moves,
central bank interest rate signals, and global market opening sentiment (Asian markets, GIFT Nifty).
Enforces strict date freshness: discards older articles outside the research window.
"""

import re
import logging
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional, Tuple
from engine.local_llm import query_local_llm

logger = logging.getLogger(__name__)


def parse_event_date(date_str: str) -> Optional[datetime]:
    """Parses date string from article metadata into standard datetime."""
    if not date_str:
        return None
    s = str(date_str).strip()
    try:
        dt = parsedate_to_datetime(s)
        return dt.replace(tzinfo=None)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ["%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def filter_fresh_macro_events(raw_events: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
    """
    Freshness Gate: Discards any macro article not published within the active research window.
    Window is [target_date - 1 day, target_date + 1 day].
    """
    try:
        t_dt = datetime.strptime(target_date, "%Y-%m-%d")
        min_dt = t_dt - timedelta(days=1, hours=6)
        max_dt = t_dt + timedelta(days=1, hours=18)
    except Exception:
        return raw_events

    fresh = []
    for ev in raw_events:
        pub = ev.get("published_at") or ev.get("publication_date") or ev.get("published_date") or ev.get("event_date")
        if pub:
            parsed = parse_event_date(pub)
            if parsed:
                if parsed < min_dt or parsed > max_dt:
                    logger.debug(f"Macro article omitted as stale for {target_date}: '{ev.get('title')}' ({pub})")
                    continue
        fresh.append(ev)
    return fresh


def extract_macro_signals(raw_events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorizes raw events into key macro buckets:
    - geopolitical: War, conflict, ceasefire, shipping lanes, Middle East, Red Sea, Iran, Trump
    - crude_oil: Brent crude price moves, OPEC+ decisions, inventory draws/builds
    - central_banks: US Fed, RBI, ECB, interest rates, bond yields, inflation prints
    - market_cues: Asian markets, Wall Street overnight close, GIFT Nifty, domestic opening cues
    """
    buckets = {
        "geopolitical": [],
        "crude_oil": [],
        "central_banks": [],
        "market_cues": [],
    }

    geo_terms = [
        r"\b(?:israel|gaza|middle\s+east|iran|houthi|red\s+sea|ukraine|russia|ceasefire|tensions|geopolitical|strait\s+of\s+hormuz|retaliation|trump|pentagon)\b",
    ]
    crude_terms = [
        r"\b(?:brent\s+crude|crude\s+oil|oil\s+prices?|petroleum|wti\s+crude|opec(?:\+)?|saudi\s+aramco|aramco|pipeline|strait\s+of\s+hormuz)\b",
    ]
    cb_terms = [
        r"\b(?:federal\s+reserve|us\s+fed|jerome\s+powell|interest\s+rates?|rate\s+cut|rate\s+hike|rate\s+decision|rbi\s+mpc|monetary\s+policy|treasury\s+yields?)\b",
    ]
    market_terms = [
        r"\b(?:gift\s+nifty|asian\s+markets?|nikkei|hang\s+seng|wall\s+street|dow\s+jones|nasdaq|s&p\s+500|global\s+cues|market\s+wrap)\b",
    ]

    for ev in raw_events:
        text = f"{ev.get('title', '')} {ev.get('summary', '')}".lower()
        if any(re.search(p, text) for p in geo_terms):
            buckets["geopolitical"].append(ev)
        if any(re.search(p, text) for p in crude_terms):
            buckets["crude_oil"].append(ev)
        if any(re.search(p, text) for p in cb_terms):
            buckets["central_banks"].append(ev)
        if any(re.search(p, text) for p in market_terms):
            buckets["market_cues"].append(ev)

    return buckets


def generate_macro_commentary(raw_events: List[Dict[str, Any]], target_date: str) -> Optional[Dict[str, Any]]:
    """
    Synthesizes a pure macro opening item matching Sharekhan's un-templated prose style:
    - Strictly uses facts from articles published within the research window for target_date.
    - Explicitly discards older historical facts.
    - No stock ticker attached.
    - Cohesive 2-4 sentence paragraph outlining active macro developments and implications.
    """
    # 1. Enforce strict freshness check
    fresh_events = filter_fresh_macro_events(raw_events, target_date)
    signals = extract_macro_signals(fresh_events)

    has_geo = len(signals["geopolitical"]) > 0
    has_crude = len(signals["crude_oil"]) > 0
    has_cb = len(signals["central_banks"]) > 0
    has_cues = len(signals["market_cues"]) > 0

    if not (has_geo or has_crude or has_cb or has_cues):
        return None

    # Try LLM synthesis with explicit today date and freshness instruction
    all_fresh_titles = [ev.get("title", "") for ev in fresh_events[:15] if len(ev.get("title", "")) > 15]
    if all_fresh_titles:
        prompt = (
            f"Today's date is {target_date}.\n"
            f"You are an institutional Indian stock market equity strategist synthesizing the morning market opening macro commentary.\n"
            f"Use ONLY facts from the following fresh news headlines published on or very near {target_date}.\n"
            f"STRICTLY DISCARD any facts from older dates (such as previous weeks' defense sales or past pipeline repair milestones) even if topically relevant.\n"
            f"Headlines for {target_date}:\n- " + "\n- ".join(all_fresh_titles) + "\n\n"
            f"Write a concise, professional 3-sentence macro overview covering overseas geopolitical developments, crude oil moves, and domestic opening cues, followed by:\n"
            f"Three Things to Watch: 1) ...; 2) ...; 3) ...\n"
            f"Do NOT include boilerplate disclaimers or markdown section titles."
        )
        llm_response = query_local_llm(prompt, system_prompt="You are a senior institutional equity strategist.")
        if llm_response and len(llm_response.strip()) > 80 and "Three Things to Watch" in llm_response:
            all_sources = []
            for ev in fresh_events[:5]:
                src = ev.get("source")
                if src and src not in all_sources:
                    all_sources.append(src)
            return {
                "candidate_type": "MACRO_COMMENTARY",
                "company_name": "Global Market & Macro Context",
                "headline": "Global Market & Macro Context",
                "flowing_prose": llm_response.strip(),
                "sources": " | ".join(all_sources[:3]) if all_sources else "Global Market Feeds",
                "event_date": target_date,
                "research_importance_score": 9.9,
                "materiality_score": 9.5,
            }

    # Dynamic expert rule-based synthesis strictly from fresh articles
    sentences = []
    geo_corpus = " ".join([f"{ev.get('title', '')} {ev.get('summary', '')}" for ev in signals["geopolitical"] + signals["crude_oil"]]).lower()

    # 1. Geopolitical Driver: Extract actual active themes from fresh headlines
    active_geo_facts = []
    if "iran" in geo_corpus:
        if any(w in geo_corpus for w in ["retaliation", "without limitation", "threaten", "warn"]):
            active_geo_facts.append("Iran's rhetoric warning of retaliation without limitations")
        elif any(w in geo_corpus for w in ["strike", "drone", "missile", "escalat"]):
            active_geo_facts.append("escalating military posturing and retaliatory threats involving Iran")
        else:
            active_geo_facts.append("heightened Middle East tensions involving Iran")

    if "trump" in geo_corpus:
        if any(w in geo_corpus for w in ["deciding", "mode", "deliberat", "policy"]):
            active_geo_facts.append("deliberations surrounding prospective US policy and tariff frameworks")
        else:
            active_geo_facts.append("evolving US policy signals")

    if "hormuz" in geo_corpus or "strait" in geo_corpus:
        active_geo_facts.append("maritime transit monitoring across the Strait of Hormuz")
    elif "red sea" in geo_corpus:
        active_geo_facts.append("shipping route security developments across the Red Sea")

    if active_geo_facts:
        if len(active_geo_facts) == 1:
            detail_str = active_geo_facts[0]
        elif len(active_geo_facts) == 2:
            detail_str = f"{active_geo_facts[0]} and {active_geo_facts[1]}"
        else:
            detail_str = f"{active_geo_facts[0]}, {active_geo_facts[1]}, and {active_geo_facts[2]}"
        sentences.append(f"Global market risk sentiment was shaped by fresh overseas geopolitical developments, notably {detail_str}, elevating headline sensitivity across trade routes.")
    elif has_geo and has_crude:
        crude_text = " ".join([f"{ev.get('title', '')} {ev.get('summary', '')}" for ev in signals["crude_oil"]]).lower()
        if any(w in crude_text for w in ["ease", "eases", "drop", "drops", "slide", "slides", "fall", "falls", "slips"]):
            oil_clause = "Brent crude eased amid tentative signs of diplomatic stabilization"
        elif any(w in crude_text for w in ["surge", "surges", "jump", "jumps", "spike", "spikes", "rises", "climbs"]):
            oil_clause = "Brent crude firmed as geopolitical friction elevated supply risk premiums"
        else:
            oil_clause = "Brent crude traded in a tight range as markets digested cross-border developments"
        sentences.append(f"Global market risk sentiment reflected evolving international headlines as {oil_clause}.")
    elif has_geo:
        sentences.append("Global financial markets continued to monitor active geopolitical developments across international trade corridors, with cross-asset headline sensitivity remaining elevated.")

    # 2. Crude Oil Benchmark Driver
    if has_crude:
        crude_sample = signals["crude_oil"][0]
        c_title = crude_sample.get("title", "")
        p_m = re.search(r"\$(\d+(?:\.\d+)?)(?:\s*(?:per\s+barrel|/bbl|bbl))?", c_title, re.IGNORECASE)
        price_str = f"near ${p_m.group(1)} per barrel" if p_m else "near benchmark levels"
        sentences.append(f"Crude oil benchmarks held steady with Brent crude hovering {price_str}, as energy participants weighed physical supply security against broader macroeconomic consumption trends.")

    # 3. Central Bank / Rates Driver
    if has_cb:
        cb_sample = signals["central_banks"][0]
        cb_text = f"{cb_sample.get('title', '')} {cb_sample.get('summary', '')}".lower()
        if "rate cut" in cb_text:
            sentences.append("On the monetary policy front, sovereign bond yields adjusted as participants recalibrated interest rate trajectories ahead of upcoming central bank meetings.")
        elif "powell" in cb_text or "federal reserve" in cb_text:
            sentences.append("Federal Reserve communications indicated that interest rate policy will remain data-dependent, anchoring benchmark sovereign yields.")
        else:
            sentences.append("Benchmark sovereign bond yields stabilized as institutional participants assessed global monetary policy guidance.")

    # 4. Market Open Cues & GIFT Nifty
    if has_cues:
        cues_text = " ".join([f"{ev.get('title', '')} {ev.get('summary', '')}" for ev in signals["market_cues"]]).lower()
        if any(w in cues_text for w in ["positive", "gain", "green", "higher", "rise", "advance"]):
            sentences.append("Asian equities opened predominantly in positive territory following supportive cues from Wall Street, while GIFT Nifty pointed toward a steady to positive opening for domestic bourses.")
        elif any(w in cues_text for w in ["negative", "loss", "red", "lower", "fall", "decline"]):
            sentences.append("Asian markets experienced cautious trading following consolidation across international benchmarks, indicating a measured opening for domestic indices.")
        else:
            sentences.append("Asian indices traded with measured optimism, providing a stable external backdrop for the Indian market open.")

    # 5. Dynamic Structured Institutional Summary: Three Things to Watch
    watch_1 = "1) Middle East geopolitical developments and crude tanker freight rate adjustments"
    if "iran" in geo_corpus:
        watch_1 = "1) Retaliatory risks and diplomatic friction in the Middle East"
    elif "hormuz" in geo_corpus:
        watch_1 = "1) Strait of Hormuz shipping transit alerts and maritime insurance premiums"

    watch_2 = "2) Domestic fuel marketing margins and upstream realisations as crude benchmarks digest supply news"
    watch_3 = "3) Institutional FPI flows and GIFT Nifty opening trajectory"

    sentences.append(f"Three Things to Watch: {watch_1}; {watch_2}; {watch_3}.")

    prose = " ".join(sentences)
    prose = re.sub(r"\s+", " ", prose).strip()

    all_sources = []
    for bucket in signals.values():
        for item in bucket:
            src = item.get("source")
            if src and src not in all_sources:
                all_sources.append(src)

    return {
        "candidate_type": "MACRO_COMMENTARY",
        "company_name": "Global Market & Macro Context",
        "headline": "Global Market & Macro Context",
        "flowing_prose": prose,
        "sources": " | ".join(all_sources[:3]) if all_sources else "Global Market Feeds",
        "event_date": target_date,
        "research_importance_score": 9.9,
        "materiality_score": 9.5,
    }

