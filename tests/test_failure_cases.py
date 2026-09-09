"""
Unit tests validating the 6 specific failure cases addressed in the Targeted Update:
1. Failure A: NTPC / Enviro Infra Engineers order attribution (Contractor vs Awarding Client).
2. Failure B: Multi-company container roundup rejection (Stocks in news...).
3. Failure C: Credit Rating verification (ESG rejection, reaffirmation rejection, upgrade/downgrade evaluation).
4. Failure D: Pure price movement rejection.
5. Failure E: Broker target change rejection.
6. Failure F: Government procurement pipeline contextualization (not immediate revenue).
"""

import pytest
from engine.entity_mapper import (
    resolve_entity_from_text,
    validate_event_entity,
    is_multi_company_roundup,
    resolve_event_companies_and_roles,
)
from engine.noise_filter import is_material_fundamental_event
from engine.fna_analyzer import (
    synthesize_fna_item,
    clean_fundamental_headline,
    classify_event_direction_and_type,
)


def test_failure_a_ntpc_vs_enviro_infra():
    """
    FAILURE A: Enviro Infra Engineers secures order from NTPC.
    - Must resolve to Enviro Infra Engineers (EIEL.NS) as CONTRACTOR / Economic Beneficiary.
    - Must NOT resolve to NTPC (NTPC.NS is merely the awarding customer).
    - Validation on NTPC for this text must return False.
    - Headline market commentary must be stripped.
    """
    text = "Enviro Infra Engineers share price jumps 10% on securing ₹190 crore order from NTPC"
    
    # 1. Role resolution check
    roles = resolve_event_companies_and_roles(text)
    role_map = {r["symbol"]: r["role"] for r in roles}
    assert "EIEL.NS" in role_map, "Enviro Infra Engineers must be detected"
    assert role_map["EIEL.NS"] == "CONTRACTOR", "Enviro Infra must be CONTRACTOR"
    assert "NTPC.NS" in role_map, "NTPC must be detected"
    assert role_map["NTPC.NS"] == "CUSTOMER", "NTPC must be recognized as CUSTOMER"

    # 2. Entity resolution check
    entity_meta, reason = resolve_entity_from_text(text)
    assert entity_meta is not None
    assert entity_meta["symbol"] == "EIEL.NS", f"Expected EIEL.NS, got {entity_meta['symbol']}"
    assert "Enviro Infra" in entity_meta["name"]

    # 3. Validation rejection for customer
    is_valid_ntpc, val_reason = validate_event_entity(text, "", "NTPC.NS")
    assert not is_valid_ntpc, "NTPC must NOT be validated as the beneficiary of an order awarded to Enviro Infra"

    # 4. Headline cleaning check
    cleaned = clean_fundamental_headline(text, entity_meta["name"])
    assert "jumps 10%" not in cleaned.lower()
    assert "share price" not in cleaned.lower()
    assert "bags" in cleaned.lower() or "secures" in cleaned.lower()
    assert "190 crore" in cleaned


def test_failure_b_stocks_in_news_roundup_rejection():
    """
    FAILURE B: Multi-company roundups like 'Stocks in news: Biocon, Bank of Baroda, TCS, Sanofi, NMDC'
    must NEVER be attributed to a single company (like TCS) and must be rejected as container noise.
    """
    title = "Stocks in news: Biocon, Bank of Baroda, TCS, Sanofi, NMDC"
    summary = "Stocks in news: Biocon, Bank of Baroda, TCS, Sanofi, NMDC shares will be in focus today ahead of earnings and updates."
    full_text = f"{title} {summary}"

    # 1. Multi-company detection helper
    assert is_multi_company_roundup(full_text) is True

    # 2. Noise filter rejection
    is_mat, reason = is_material_fundamental_event(title, summary)
    assert not is_mat, f"Roundup should be rejected by noise filter: {reason}"
    assert "roundup" in reason.lower()

    # 3. Entity mapper rejection
    entity_meta, res_reason = resolve_entity_from_text(full_text)
    assert entity_meta is None, f"Roundup must not resolve to any single entity: got {entity_meta}"
    assert "roundup" in res_reason.lower()


def test_failure_c_credit_rating_esg_and_reaffirmation_gating():
    """
    FAILURE C: Credit rating actions.
    - ESG ratings are NOT debt credit ratings -> Rejected.
    - Reaffirmations / surveillance without notch change -> Rejected.
    - Verified upgrades -> Positive, without unsupported deleveraging claims.
    - Verified downgrades -> Negative.
    """
    # C1: ESG rating rejected
    esg_title = "Varroc Engineering receives ESG rating from S&P Global"
    esg_summary = "Varroc Engineering gets strong ESG score of 68 from S&P Global in annual assessment."
    is_mat_esg, reason_esg = is_material_fundamental_event(esg_title, esg_summary)
    assert not is_mat_esg, f"ESG rating should be rejected: {reason_esg}"
    assert "esg" in reason_esg.lower()

    # C2: Reaffirmation rejected
    reaff_title = "CRISIL reaffirms AAA rating for HDFC Bank with stable outlook"
    reaff_summary = "CRISIL has reaffirmed its 'CRISIL AAA/Stable' rating on the debt instruments of HDFC Bank."
    is_mat_reaff, reason_reaff = is_material_fundamental_event(reaff_title, reaff_summary)
    assert not is_mat_reaff, f"Routine rating reaffirmation should be rejected: {reason_reaff}"
    assert "reaffirmation" in reason_reaff.lower() or "unchanged" in reason_reaff.lower()

    # C3: Genuine Upgrade accepted and evaluated as Positive
    upg_title = "ICRA upgrades Tata Motors long-term credit rating to AA+ from AA"
    upg_summary = "ICRA has upgraded the long-term rating of Tata Motors from AA to AA+ with a stable outlook reflecting operational cash flows."
    is_mat_upg, _ = is_material_fundamental_event(upg_title, upg_summary)
    assert is_mat_upg, "Rating upgrade must pass noise filter"

    item_cluster = {
        "title": upg_title,
        "summary": upg_summary,
        "symbol": "TATAMOTORS.NS",
        "company_name": "Tata Motors Ltd",
        "sector": "Automobile",
        "sources": ["ICRA", "NSE Corporate Announcements"]
    }
    fna_item = synthesize_fna_item(item_cluster)
    assert fna_item["fundamental_direction"] == "Positive"
    assert fna_item["event_type"] == "FUNDING_DEBT_EVENT"
    # Check that it doesn't assert unsupported debt deleveraging
    assert "debt deleveraging" not in fna_item["why_it_matters"].lower()

    # C4: Genuine Downgrade accepted and evaluated as Negative
    down_title = "Care Ratings downgrades XYZ Debt Instruments to BB from BBB"
    down_summary = "Care Ratings has downgraded debt instruments due to deteriorating liquidity profile."
    is_mat_down, _ = is_material_fundamental_event(down_title, down_summary)
    assert is_mat_down, "Rating downgrade must pass noise filter"
    cat, direction, conf = classify_event_direction_and_type(f"{down_title} {down_summary}")
    assert direction == "Negative"


def test_failure_d_pure_price_movement_rejection():
    """
    FAILURE D: Pure price movement articles without fundamental catalysts must be rejected.
    """
    title = "Zomato shares surge 8% amid heavy trading volumes"
    summary = "Shares of Zomato rallied 8% in morning trade with high trading volumes on NSE."
    is_mat, reason = is_material_fundamental_event(title, summary)
    assert not is_mat, f"Pure price rally should be rejected: {reason}"
    assert "price movement" in reason.lower() or "catalyst" in reason.lower()


def test_failure_e_broker_target_revision_rejection():
    """
    FAILURE E: Broker target price changes and analyst calls are opinions, not fundamental company developments.
    Must be rejected as standalone TOP NEWS.
    """
    title = "Jefferies raises target price on Reliance Industries to ₹3,400"
    summary = "Global brokerage Jefferies maintains buy rating on Reliance Industries with revised price target."
    is_mat, reason = is_material_fundamental_event(title, summary)
    assert not is_mat, f"Broker target revision should be rejected: {reason}"
    assert "broker" in reason.lower() or "analyst" in reason.lower() or "opinion" in reason.lower()


def test_failure_f_government_procurement_pipeline_context():
    """
    FAILURE F: Multi-crore government procurement / defence capital approvals (e.g. ₹1.10 lakh crore)
    must be contextualized as forward procurement pipeline for domestic defence contractors, NOT booked revenue.
    """
    title = "Defence Ministry DAC clears ₹1.10 lakh crore capital acquisition proposal"
    summary = "The Defence Acquisition Council (DAC) approved Acceptance of Necessity (AoN) for capital procurement worth ₹1.10 lakh crore for armed forces."

    cat, direction, conf = classify_event_direction_and_type(f"{title} {summary}")
    assert cat == "GOVERNMENT_EVENT"
    assert direction == "Positive"

    item_cluster = {
        "title": title,
        "summary": summary,
        "symbol": "HAL.NS",
        "company_name": "Hindustan Aeronautics Ltd",
        "sector": "Defence",
        "sources": ["Press Information Bureau", "Financial News"]
    }
    fna_item = synthesize_fna_item(item_cluster)
    assert fna_item is not None
    assert fna_item["fundamental_direction"] == "Positive"
    # Verify pipeline context is explained and immediate revenue assumption is dispelled
    text_corpus = f"{fna_item['why_it_matters']} {fna_item['key_financial_implication']}".lower()
    assert "pipeline" in text_corpus or "forward" in text_corpus or "multi-year" in text_corpus
    assert "not immediate" in text_corpus or "forward procurement" in text_corpus or "tender" in text_corpus or "bidding" in text_corpus
