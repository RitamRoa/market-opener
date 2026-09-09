"""
Financial Context & Semantic Metric Parsing Module.
Semantically parses financial metrics (Order Value, PAT, Revenue, Capex, Penalty)
and calculates relative magnitude against company baseline scale (Annual Revenue, EBITDA, Market Cap).
Never hallucinates figures: explicitly states when financial metrics are undisclosed.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
import yfinance as yf
from engine.db import get_cached_price, set_cached_price

logger = logging.getLogger(__name__)


class SemanticMetricsList(list):
    """List subclass enabling both list index and dictionary-style access to top metric."""
    def __getitem__(self, item):
        if isinstance(item, str):
            if self:
                return self[0].get(item)
            return None
        return super().__getitem__(item)


def parse_semantic_financial_metrics(text: str) -> SemanticMetricsList:
    """
    Semantically extracts monetary amounts, ranges, and operating metrics:
      - 'ORDER_VALUE': e.g., 'secured ₹100-250 crore order', 'bags Rs 903 crore order', '₹9,000–10,000 cr package'
      - 'PROCUREMENT_PIPELINE': e.g., 'Rs 1.45 lakh crore defence proposals approved'
      - 'OPERATING_UPDATE': e.g., 'Q1 net loss narrows to Rs 14 crore; revenue up 34%'
      - 'PAT': e.g., 'net profit falls 26% to Rs 174 cr', 'PAT jumps 45% to Rs 500 cr'
      - 'REVENUE': e.g., 'revenue increased 8.5% to Rs 3,927 crore'
      - 'CAPEX': e.g., 'capex investment of Rs 1,200 cr'
      - 'PENALTY': e.g., 'penalty of Rs 15 crore'
    """
    if not text:
        return SemanticMetricsList()

    metrics = SemanticMetricsList()

    # 1. Lakh Crore Aggregate Patterns (e.g. "Rs 1.45 lakh crore defence proposals", "Rs 1.10 lakh cr")
    lakh_cr_pattern = r"(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*lakh\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(lakh_cr_pattern, text, re.IGNORECASE):
        raw_val = float(match.group(1).replace(",", ""))
        val_cr = round(raw_val * 100000.0, 1)
        metrics.append({
            "metric": "PROCUREMENT_PIPELINE" if any(w in text.lower() for w in ["defence", "procurement", "dac", "approval", "proposals"]) else "ORDER_VALUE",
            "metric_type": "PROCUREMENT_PIPELINE" if any(w in text.lower() for w in ["defence", "procurement", "dac", "approval", "proposals"]) else "ORDER_VALUE",
            "value_cr": val_cr,
            "amount_cr": val_cr,
            "raw_lakh_cr": raw_val,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"₹{raw_val:,.2f} lakh Cr (₹{val_cr:,.0f} Cr)",
            "description": f"Capital allocation / procurement pipeline of ₹{raw_val:,.2f} lakh Cr"
        })

    # 2. Order Value RANGES (e.g. "₹100-250 crore order", "₹9,000–10,000 cr package", "Rs 100 to 250 crore")
    range_order_pattern = r"(?:(?:order|contract|project|deal|mandate|package)\b[^.]{0,80}?)?(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:-|–|—|to)\s*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(range_order_pattern, text, re.IGNORECASE):
        low_val = float(match.group(1).replace(",", ""))
        high_val = float(match.group(2).replace(",", ""))
        if low_val > high_val:
            low_val, high_val = high_val, low_val
        metrics.append({
            "metric": "ORDER_VALUE",
            "metric_type": "ORDER_VALUE",
            "value_cr": high_val,
            "amount_cr": high_val,
            "range_low_cr": low_val,
            "range_high_cr": high_val,
            "range_text": f"₹{low_val:,.0f}–{high_val:,.0f} Cr",
            "description": f"Disclosed contract range of ₹{low_val:,.0f}–{high_val:,.0f} Cr"
        })

    # 3. PAT / Net Profit patterns (handles "PAT falls 26% to Rs 174 cr", "net profit of Rs 500 cr", etc.)
    pat_pattern = r"(?:net\s+profit|pat|net\s+income)\b[^.]{0,80}?(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(pat_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        pct_match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*%", match.group(0))
        pct_val = float(pct_match.group(1)) if pct_match else None
        metrics.append({
            "metric": "PAT",
            "metric_type": "PAT",
            "value_cr": val,
            "amount_cr": val,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"₹{val:,.1f} Cr",
            "percentage_change": pct_val,
            "description": f"Net Profit (PAT) of ₹{val:,.1f} Cr"
        })

    # Reverse PAT pattern: "Rs 174 cr net profit"
    rev_pat_pattern = r"(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b[^.]{0,40}?\b(?:net\s+profit|pat|net\s+income)\b"
    for match in re.finditer(rev_pat_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        if not any(m["metric"] == "PAT" and abs(m["value_cr"] - val) < 0.01 for m in metrics):
            metrics.append({
                "metric": "PAT",
                "metric_type": "PAT",
                "value_cr": val,
                "amount_cr": val,
                "range_low_cr": None,
                "range_high_cr": None,
                "range_text": f"₹{val:,.1f} Cr",
                "description": f"Net Profit (PAT) of ₹{val:,.1f} Cr"
            })

    # 4. Operating Updates (e.g. "net loss narrows to Rs 14 crore; revenue up 34%")
    loss_narrow_pattern = r"(?:net\s+loss|loss|ebitda\s+loss)\s+(?:narrows?|narrowed|reduced|declined)\s+(?:to|by)?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    loss_match = re.search(loss_narrow_pattern, text, re.IGNORECASE)
    rev_growth_match = re.search(r"(?:revenue|sales|topline)\s+(?:up|increased|grew|surged)\s+(?:by\s+)?([0-9]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    
    if loss_match or rev_growth_match:
        loss_val = float(loss_match.group(1).replace(",", "")) if loss_match else None
        rev_growth = float(rev_growth_match.group(1)) if rev_growth_match else None
        metrics.append({
            "metric": "OPERATING_UPDATE",
            "metric_type": "OPERATING_UPDATE",
            "value_cr": loss_val or 0.0,
            "amount_cr": loss_val or 0.0,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"Loss narrowed to ₹{loss_val} Cr" if loss_val else f"Revenue +{rev_growth}%",
            "percentage_change": rev_growth,
            "loss_cr": loss_val,
            "description": f"Operating update: Revenue +{rev_growth}% YoY, loss narrowed to ₹{loss_val} Cr"
        })

    # 5. Revenue / Sales single patterns (handles "revenue rises 12% to Rs 3,927 cr", etc.)
    rev_pattern = r"(?:revenue|topline|sales|turnover)\b[^.]{0,80}?(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(rev_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        if not any(m["metric"] == "REVENUE" and abs(m["value_cr"] - val) < 0.01 for m in metrics):
            metrics.append({
                "metric": "REVENUE",
                "metric_type": "REVENUE",
                "value_cr": val,
                "amount_cr": val,
                "range_low_cr": None,
                "range_high_cr": None,
                "range_text": f"₹{val:,.1f} Cr",
                "description": f"Revenue of ₹{val:,.1f} Cr"
            })

    # 6. Order / Contract Single Value patterns (INR)
    order_pattern = r"(?:order|contract|project|deal|mandate)\b[^.]{0,80}?(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(order_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        if not any(m["metric"] in ["ORDER_VALUE", "PAT", "PROCUREMENT_PIPELINE"] and abs(m["value_cr"] - val) < 0.01 for m in metrics):
            metrics.append({
                "metric": "ORDER_VALUE",
                "metric_type": "ORDER_VALUE",
                "value_cr": val,
                "amount_cr": val,
                "range_low_cr": None,
                "range_high_cr": None,
                "range_text": f"₹{val:,.1f} Cr",
                "description": f"Order value of ₹{val:,.1f} Cr"
            })

    alt_order_pattern = r"(?:(?:rs\.?|inr|₹)\s*|worth\s+)([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b[^.]{0,50}?\b(?:order|contract|work\s+order|epc|project)\b"
    for match in re.finditer(alt_order_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        if not any(m["metric"] in ["ORDER_VALUE", "PAT", "PROCUREMENT_PIPELINE"] and abs(m["value_cr"] - val) < 0.01 for m in metrics):
            metrics.append({
                "metric": "ORDER_VALUE",
                "metric_type": "ORDER_VALUE",
                "value_cr": val,
                "amount_cr": val,
                "range_low_cr": None,
                "range_high_cr": None,
                "range_text": f"₹{val:,.1f} Cr",
                "description": f"Order value of ₹{val:,.1f} Cr"
            })

    # 7. Capex / Investment patterns
    capex_pattern = r"(?:capex|investment|investing)\s+(?:of|worth|around)?\s*(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(capex_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        metrics.append({
            "metric": "CAPEX",
            "metric_type": "CAPEX",
            "value_cr": val,
            "amount_cr": val,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"₹{val:,.1f} Cr",
            "description": f"Capex investment of ₹{val:,.1f} Cr"
        })

    # 8. Penalty / Regulatory Fine patterns
    penalty_pattern = r"(?:penalty|fine|tax\s+demand)\s+(?:of)?\s*(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
    for match in re.finditer(penalty_pattern, text, re.IGNORECASE):
        val = float(match.group(1).replace(",", ""))
        metrics.append({
            "metric": "PENALTY",
            "metric_type": "PENALTY",
            "value_cr": val,
            "amount_cr": val,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"₹{val:,.1f} Cr",
            "description": f"Regulatory penalty / demand of ₹{val:,.1f} Cr"
        })

    # 9. USD / Foreign Currency Order or Deal patterns ($50 million export deal)
    usd_pattern = r"\$\s*([0-9,]+(?:\.[0-9]+)?)\s*(million|billion|mn|bn)\b"
    for match in re.finditer(usd_pattern, text, re.IGNORECASE):
        raw_val = float(match.group(1).replace(",", ""))
        unit = match.group(2).lower()
        if "billion" in unit or "bn" in unit:
            val_cr = round(raw_val * 8350.0, 1)
        else:
            val_cr = round(raw_val * 8.35, 1)
        metrics.append({
            "metric": "ORDER_VALUE" if any(w in text.lower() for w in ["deal", "order", "contract", "export"]) else "GENERIC_MONETARY",
            "metric_type": "ORDER_VALUE" if any(w in text.lower() for w in ["deal", "order", "contract", "export"]) else "GENERIC_MONETARY",
            "value_cr": val_cr,
            "amount_cr": val_cr,
            "range_low_cr": None,
            "range_high_cr": None,
            "range_text": f"₹{val_cr:,.1f} Cr (~${raw_val} {unit})",
            "description": f"Disclosed monetary figure of ₹{val_cr:,.1f} Cr (~${raw_val} {unit})"
        })

    # 10. Generic monetary extraction if no semantic pattern matched
    if not metrics:
        generic_pattern = r"(?:(?:rs\.?|inr|₹)\s*|worth\s+|valued\s+at\s+)([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b"
        match_gen = re.search(generic_pattern, text, re.IGNORECASE)
        if match_gen:
            val = float(match_gen.group(1).replace(",", ""))
            metrics.append({
                "metric": "GENERIC_MONETARY",
                "metric_type": "GENERIC_MONETARY",
                "value_cr": val,
                "amount_cr": val,
                "range_low_cr": None,
                "range_high_cr": None,
                "range_text": f"₹{val:,.1f} Cr",
                "description": f"Disclosed monetary figure of ₹{val:,.1f} Cr"
            })

    return metrics


def extract_monetary_value_cr(text: str) -> Optional[float]:
    """Extracts first valid transaction or financial figure in ₹ Cr."""
    metrics = parse_semantic_financial_metrics(text)
    if metrics:
        return metrics[0]["value_cr"]
    return None


def extract_monetary_values_and_ranges(text: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """
    Extracts monetary values, ranges, and range text from text.
    Returns (single_or_upper_val_cr, range_low_cr, range_high_cr, range_text).
    """
    metrics = parse_semantic_financial_metrics(text)
    for m in metrics:
        if m.get("range_low_cr") is not None and m.get("range_high_cr") is not None:
            return m.get("value_cr"), m.get("range_low_cr"), m.get("range_high_cr"), m.get("range_text")
        if m.get("value_cr") is not None:
            return m.get("value_cr"), None, None, m.get("range_text")
    return None, None, None, None


def extract_operating_metrics(text: str) -> Dict[str, Any]:
    """
    Extracts key operating and financial update metrics from text.
    Returns dictionary with profit_pct, revenue_pct, margin_bps, loss_cr if detected.
    """
    res = {}
    profit_m = re.search(r"(?:net\s+profit|pat|profit)\s+(?:up|jumped|surged|rose|grew|increased|by)\s+([0-9]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    if profit_m:
        res["profit_pct"] = float(profit_m.group(1))

    rev_m = re.search(r"(?:revenue|sales|topline)\s+(?:up|surged|rose|grew|increased|by)\s+([0-9]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    if rev_m:
        res["revenue_pct"] = float(rev_m.group(1))

    margin_m = re.search(r"(?:margin|ebitda\s+margin)\s+(?:expanded|rose|up)\s+(?:by\s+)?([0-9]+(?:\.[0-9]+)?)\s*bps", text, re.IGNORECASE)
    if margin_m:
        res["margin_bps"] = float(margin_m.group(1))

    loss_m = re.search(r"(?:net\s+loss|loss)\s+(?:narrows?|narrowed|reduced)\s+(?:to|by)?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?s?)\b", text, re.IGNORECASE)
    if loss_m:
        res["loss_cr"] = float(loss_m.group(1).replace(",", ""))

    return res


def get_company_scale(symbol: str) -> Dict[str, Any]:
    """
    Retrieves company's financial baseline (Annual Revenue, EBITDA, Market Cap in ₹ Cr) via yfinance.
    Results are cached in SQLite.
    """
    cached = get_cached_price(symbol, "scale_metrics", max_age_hours=12.0)
    if cached:
        return cached

    scale = {
        "annual_revenue_cr": None,
        "ebitda_cr": None,
        "market_cap_cr": None,
        "symbol": symbol
    }

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}

        rev = info.get("totalRevenue")
        ebitda = info.get("ebitda")
        mcap = info.get("marketCap")

        if rev:
            scale["annual_revenue_cr"] = round(rev / 10000000.0, 1)
        if ebitda:
            scale["ebitda_cr"] = round(ebitda / 10000000.0, 1)
        if mcap:
            scale["market_cap_cr"] = round(mcap / 10000000.0, 1)

        set_cached_price(symbol, "scale_metrics", scale)
    except Exception as e:
        logger.debug(f"Could not retrieve scale metrics for {symbol}: {e}")

    return scale


def evaluate_relative_materiality(symbol: str, event_text: str) -> Dict[str, Any]:
    """
    Semantically evaluates the financial magnitude of an event relative to company scale:
      - If ORDER (single or range): calculates Order / Annual Revenue (%), providing forward visibility.
      - If PROCUREMENT_PIPELINE (lakh crore): contextualizes addressable capital outlay pipeline.
      - If OPERATING_UPDATE: contrasts revenue growth and loss narrowing for operating leverage.
      - If PAT / EARNINGS: contextualizes quarterly profit against annual baseline.
      - If CAPEX: calculates Capex / Annual Revenue (%).
      - If PENALTY: compares fine to revenue / earnings.
    Never mislabels PAT as an order inflow.
    Never states 'cannot be reliably quantified' when numbers exist in text.
    """
    parsed_metrics = parse_semantic_financial_metrics(event_text)
    scale = get_company_scale(symbol)

    annual_rev_cr = scale.get("annual_revenue_cr")
    mcap_cr = scale.get("market_cap_cr")

    result = {
        "parsed_metrics": parsed_metrics,
        "disclosed_value_cr": parsed_metrics[0]["value_cr"] if parsed_metrics else None,
        "range_low_cr": parsed_metrics[0].get("range_low_cr") if parsed_metrics else None,
        "range_high_cr": parsed_metrics[0].get("range_high_cr") if parsed_metrics else None,
        "range_text": parsed_metrics[0].get("range_text") if parsed_metrics else None,
        "primary_metric": parsed_metrics[0]["metric"] if parsed_metrics else None,
        "annual_revenue_cr": annual_rev_cr,
        "market_cap_cr": mcap_cr,
        "pct_of_annual_revenue": None,
        "financial_implication_text": "Financial magnitude cannot be reliably quantified from disclosed information.",
        "scale_materiality_score": 5.0
    }

    if not parsed_metrics:
        return result

    primary = parsed_metrics[0]
    metric_type = primary["metric"]
    val_cr = primary["value_cr"]
    low_cr = primary.get("range_low_cr")
    high_cr = primary.get("range_high_cr")
    range_text = primary.get("range_text")

    if metric_type == "ORDER_VALUE":
        if low_cr and high_cr:
            # Range quantification (e.g. ₹100–250 Cr)
            if annual_rev_cr and annual_rev_cr > 0:
                pct_high = round((high_cr / annual_rev_cr) * 100.0, 1)
                pct_low = round((low_cr / annual_rev_cr) * 100.0, 1)
                result["pct_of_annual_revenue"] = pct_high
                result["financial_implication_text"] = (
                    f"The {range_text} order expands executable order book visibility, with the upper end representing "
                    f"~{pct_high:.1f}% of annual revenue (₹{annual_rev_cr:,.0f} Cr). Earnings realization will depend on execution schedule and project margins."
                )
                result["scale_materiality_score"] = 8.5 if pct_high >= 8.0 else 7.5
            else:
                result["financial_implication_text"] = (
                    f"The {range_text} contract inflow strengthens forward executable backlog; earnings contribution depends on project margins and delivery schedule."
                )
                result["scale_materiality_score"] = 8.0
        else:
            # Single value quantification
            if annual_rev_cr and annual_rev_cr > 0:
                pct = round((val_cr / annual_rev_cr) * 100.0, 1)
                result["pct_of_annual_revenue"] = pct
                if pct >= 20.0:
                    qualifier = "transformational order book expansion representing"
                    score = 9.5
                elif pct >= 8.0:
                    qualifier = "substantial contract inflow representing"
                    score = 8.5
                elif pct >= 2.5:
                    qualifier = "meaningful commercial addition representing"
                    score = 7.5
                else:
                    qualifier = "incremental contract inflow representing"
                    score = 6.5
                result["financial_implication_text"] = (
                    f"Disclosed order value of ₹{val_cr:,.1f} Cr represents a {qualifier} ~{pct:.1f}% of annual revenue (₹{annual_rev_cr:,.0f} Cr). "
                    f"Earnings conversion will depend on delivery schedules and execution margins."
                )
                result["scale_materiality_score"] = score
            else:
                result["financial_implication_text"] = (
                    f"Disclosed contract value is ₹{val_cr:,.1f} Cr, strengthening the forward executable order pipeline; margins and execution schedule remain key determinates."
                )
                result["scale_materiality_score"] = 7.5

    elif metric_type == "PROCUREMENT_PIPELINE":
        raw_lakh = primary.get("raw_lakh_cr", val_cr / 100000.0)
        result["financial_implication_text"] = (
            f"The ₹{raw_lakh:,.2f} lakh Cr procurement clearance establishes a substantial multi-year addressable bidding pool for domestic manufacturers, "
            f"though commercial realization is contingent on subsequent RFP releases and contract awards."
        )
        result["scale_materiality_score"] = 9.0

    elif metric_type == "OPERATING_UPDATE":
        loss_val = primary.get("loss_cr")
        pct_chg = primary.get("percentage_change")
        if loss_val and pct_chg:
            result["financial_implication_text"] = (
                f"Revenue expansion of {pct_chg:.1f}% YoY alongside net loss narrowing to ₹{loss_val:,.1f} Cr highlights improving operating leverage and unit economics."
            )
        elif pct_chg:
            result["financial_implication_text"] = (
                f"Operational volume / top-line growth of {pct_chg:.1f}% demonstrates expanding business throughput and demand traction."
            )
        elif loss_val:
            result["financial_implication_text"] = (
                f"Net loss reduction to ₹{loss_val:,.1f} Cr signals progress toward operational breakeven and cost discipline."
            )
        else:
            result["financial_implication_text"] = "Operating metrics demonstrate improving commercial traction and delivery scale."
        result["scale_materiality_score"] = 8.0

    elif metric_type == "PAT":
        pct_chg = primary.get("percentage_change")
        chg_text = f" ({pct_chg:+.1f}% YoY)" if pct_chg is not None else ""
        if annual_rev_cr and annual_rev_cr > 0:
            result["financial_implication_text"] = f"Reported quarterly Net Profit (PAT) of ₹{val_cr:,.1f} Cr{chg_text} against annual top-line baseline of ₹{annual_rev_cr:,.0f} Cr."
        else:
            result["financial_implication_text"] = f"Reported quarterly Net Profit (PAT) stands at ₹{val_cr:,.1f} Cr{chg_text}."
        result["scale_materiality_score"] = 8.0

    elif metric_type == "REVENUE":
        if annual_rev_cr and annual_rev_cr > 0:
            result["financial_implication_text"] = f"Disclosed quarterly revenue of ₹{val_cr:,.1f} Cr relative to annual revenue baseline of ₹{annual_rev_cr:,.0f} Cr."
        else:
            result["financial_implication_text"] = f"Reported revenue for the period stands at ₹{val_cr:,.1f} Cr."
        result["scale_materiality_score"] = 7.0

    elif metric_type == "CAPEX":
        if annual_rev_cr and annual_rev_cr > 0:
            pct = round((val_cr / annual_rev_cr) * 100.0, 1)
            result["pct_of_annual_revenue"] = pct
            result["financial_implication_text"] = f"Planned capex outlay of ₹{val_cr:,.1f} Cr represents ~{pct:.1f}% of annual revenue, aimed at expanding productive throughput capacity."
        else:
            result["financial_implication_text"] = f"Capital expenditure commitment of ₹{val_cr:,.1f} Cr directed toward asset building."
        result["scale_materiality_score"] = 7.5

    elif metric_type == "PENALTY":
        if annual_rev_cr and annual_rev_cr > 0:
            pct = round((val_cr / annual_rev_cr) * 100.0, 2)
            result["financial_implication_text"] = f"Regulatory demand / penalty of ₹{val_cr:,.1f} Cr (~{pct:.2f}% of annual revenue); primary risk centers on compliance precedent and potential procedural oversight."
        else:
            result["financial_implication_text"] = f"Regulatory penalty / demand of ₹{val_cr:,.1f} Cr imposed."
        result["scale_materiality_score"] = 8.0

    else:
        result["financial_implication_text"] = f"Disclosed transaction figure of ₹{val_cr:,.1f} Cr."
        result["scale_materiality_score"] = 6.5

    return result
