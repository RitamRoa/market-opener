import pytest
from engine.fna_analyzer import (
    extract_structured_event_facts,
    validate_source_to_event_fidelity,
    validate_event_to_analysis_consistency,
    validate_fna_story,
    synthesize_fna_item
)

def test_extract_structured_event_facts_order():
    """Verify structured facts extraction for an order contract."""
    raw_event = {
        "title": "Shakti Pumps wins order worth Rs 235 cr from MSEDCL",
        "company_name": "Shakti Pumps (India) Ltd",
        "summary": "Shakti Pumps (India) Ltd announced that it has secured a contract worth Rs 235 crore from MSEDCL.",
        "published_at": "2026-09-10T10:00:00+05:30"
    }
    facts = extract_structured_event_facts(raw_event, f"{raw_event['title']} {raw_event['summary']}")
    assert facts["company"] == "Shakti Pumps (India) Ltd"
    assert facts["event_type"] == "ORDER_CONTRACT"
    assert facts["amount"] == 235.0
    assert facts["amount_metric"] == "order_value"
    assert facts["counterparty"] == "MSEDCL"
    assert facts["status"] == "awarded"

def test_extract_structured_event_facts_equity_raise():
    """Verify structured facts extraction for a preferential issue."""
    raw_event = {
        "title": "Board of ASM Technologies approves preferential issue of Rs 526 crore",
        "company_name": "ASM Technologies Ltd",
        "summary": "Board approved preferential issue of equity shares and warrants to raise Rs 526 crore.",
        "published_at": "2026-09-09T10:00:00+05:30"
    }
    facts = extract_structured_event_facts(raw_event, f"{raw_event['title']} {raw_event['summary']}")
    assert facts["company"] == "ASM Technologies Ltd"
    assert facts["event_type"] == "FUNDING_EQUITY"
    assert facts["amount"] == 526.0
    assert facts["amount_metric"] == "equity_raise"
    assert facts["status"] == "approved"

def test_source_fidelity_rejects_macro_index_mismatch():
    """ONGC matched on Asian market/MSCI drop article without corporate fundamentals must FAIL."""
    raw_event = {
        "title": "Hang Seng, Taiwan Taiex slip as Middle East tensions push oil higher",
        "company_name": "Oil and Natural Gas Corporation Ltd",
        "summary": "Asian markets fell with MSCI Asia-Pacific index slipping 1.2% as geopolitical instability weighed on sentiment.",
        "published_at": "2026-09-09T08:00:00+05:30"
    }
    facts = extract_structured_event_facts(raw_event, f"{raw_event['title']} {raw_event['summary']}")
    is_valid, reason = validate_source_to_event_fidelity(raw_event, facts)
    assert is_valid is False
    assert "broader market index movements" in reason

def test_source_fidelity_rejects_etruck_as_order_win():
    """Hindustan Zinc e-truck logistics deployment must FAIL if classified as an order contract."""
    raw_event = {
        "title": "Hindustan Zinc deploys 30 electric trucks with MFL India",
        "company_name": "Hindustan Zinc Ltd",
        "summary": "Hindustan Zinc has entered into a transportation agreement with MFL India for deployment of 30 e-trucks for logistics operations.",
        "published_at": "2026-09-09T10:00:00+05:30"
    }
    facts = {
        "company": "Hindustan Zinc Ltd",
        "event_type": "ORDER_CONTRACT",
        "amount_metric": "order_value"
    }
    is_valid, reason = validate_source_to_event_fidelity(raw_event, facts)
    assert is_valid is False
    assert "cannot be equated with an order contract win" in reason

def test_analysis_consistency_rejects_preferential_issue_credit_claims():
    """Preferential equity issue claiming credit rating or lower debt cost must FAIL."""
    item = {
        "company_name": "ASM Technologies Ltd",
        "event_type": "FUNDING_EQUITY",
        "company_role": "issuer",
        "headline": "Board approves preferential issue of equity shares",
        "what_happened": "Board approved preferential issue of shares.",
        "why_it_matters": "The equity issue leads to a credit rating improvement and lowers borrowing costs.",
        "fundamental_impact": "Positive — improves credit profile and lowers borrowing costs.",
        "key_financial_implication": "Reduces borrowing yield spreads."
    }
    facts = {
        "company": "ASM Technologies Ltd",
        "event_type": "FUNDING_EQUITY",
        "amount_metric": "equity_raise"
    }
    is_valid, reason = validate_event_to_analysis_consistency(item, facts)
    assert is_valid is False
    assert "Equity preferential issue incorrectly claims" in reason

def test_analysis_consistency_rejects_rbi_stake_commercialization_claims():
    """AU Small Finance Bank RBI stake approval claiming immediate commercialization must FAIL."""
    item = {
        "company_name": "AU Small Finance Bank Ltd",
        "event_type": "PRODUCT_APPROVAL",
        "company_role": "beneficiary",
        "headline": "ICICI Prudential AMC gets RBI approval to buy stake",
        "what_happened": "AU Small Finance Bank has announced: RBI approval for ICICI Prudential AMC to acquire stake.",
        "why_it_matters": "Securing RBI clearance unlocks immediate commercialization and expands addressable target market reach.",
        "fundamental_impact": "Positive — enables immediate commercialization and expands addressable target market reach.",
        "key_financial_implication": "Expands institutional equity stability."
    }
    facts = {
        "company": "AU Small Finance Bank Ltd",
        "event_type": "PRODUCT_APPROVAL",
        "amount_metric": None
    }
    is_valid, reason = validate_event_to_analysis_consistency(item, facts)
    assert is_valid is False
    assert "Regulatory stake clearance incorrectly claims" in reason

def test_analysis_consistency_rejects_dac_booked_revenue():
    """DAC defence clearance asserting firm signed contract or immediate booked revenue must FAIL."""
    item = {
        "company_name": "Hindustan Aeronautics Ltd",
        "event_type": "GOVERNMENT_EVENT",
        "company_role": "beneficiary",
        "headline": "DAC clears Rs 1.10 lakh crore defence proposals",
        "what_happened": "DAC approved proposals worth Rs 1.10 lakh crore.",
        "why_it_matters": "This award constitutes immediate booked revenue and signed contracts for the firm.",
        "fundamental_impact": "Positive — immediate booked revenue.",
        "key_financial_implication": "Booked revenue added to balance sheet."
    }
    facts = {
        "company": "Hindustan Aeronautics Ltd",
        "event_type": "GOVERNMENT_EVENT",
        "amount_metric": "procurement_value"
    }
    is_valid, reason = validate_event_to_analysis_consistency(item, facts)
    assert is_valid is False
    assert "Government defence clearance incorrectly claims" in reason or "asserts firm signed contract" in reason

def test_full_pipeline_synthesize_clean_story():
    """A fully consistent Shakti Pumps contract story must PASS synthesis and validation."""
    raw_event = {
        "title": "Shakti Pumps wins order worth Rs 235 cr from MSEDCL",
        "company_name": "Shakti Pumps (India) Ltd",
        "symbol": "SHAKTIPUMP.NS",
        "summary": "Shakti Pumps (India) Ltd has received a work order worth Rs 235 crore from MSEDCL for solar water pumping systems.",
        "published_at": "2026-09-10T10:00:00+05:30",
        "source": "Business Standard"
    }
    item = synthesize_fna_item(raw_event, debug=True)
    assert item is not None
    assert item["company_name"] == "Shakti Pumps (India) Ltd"
    assert item["fundamental_direction"] == "Positive"
    assert "order book" in item["why_it_matters"].lower()
    assert "structured_facts" in item
    assert item["structured_facts"]["amount_metric"] == "order_value"


def test_analysis_consistency_rejects_hallucinated_financial_number():
    """An item claiming a financial figure not present in facts or text must FAIL."""
    item = {
        "company_name": "Ice Make Refrigeration Ltd",
        "event_type": "FUNDING_EQUITY",
        "company_role": "issuer",
        "headline": "Ice Make allots 23.67 lakh equity shares on preferential basis",
        "what_happened": "Ice Make announced preferential allotment of 2,367,573 equity shares.",
        "why_it_matters": "The ₹526.0 crore equity infusion fortifies Ice Make's balance sheet.",
        "fundamental_impact": "Positive — strengthens balance sheet equity capital.",
        "key_financial_implication": "Directly augments net worth and cash balances."
    }
    facts = {
        "company": "Ice Make Refrigeration Ltd",
        "event_type": "FUNDING_EQUITY",
        "amount": None,
        "amount_metric": "equity_raise",
        "source_facts": {
            "text": "Ice Make allots 23.67 lakh equity shares on preferential basis to non-promoter group."
        }
    }
    is_valid, reason = validate_event_to_analysis_consistency(item, facts)
    assert is_valid is False
    assert "Analysis claims financial figure" in reason


def test_preferential_issue_without_amount_does_not_hallucinate():
    """Preferential allotment without disclosed rupee value must NOT invent ₹526 crore or marquee investors."""
    raw_event = {
        "title": "Ice Make Refrigeration allots 23.67 lakh equity shares on preferential basis",
        "company_name": "Ice Make Refrigeration Ltd",
        "symbol": "ICEMAKE.NS",
        "summary": "Ice Make Refrigeration has allotted 23,67,573 equity shares of face value Rs 10 each on preferential basis.",
        "published_at": "2026-09-10T10:00:00+05:30",
        "source": "BSE"
    }
    item = synthesize_fna_item(raw_event, debug=True)
    assert item is not None
    assert "526" not in item["why_it_matters"]
    assert "marquee investors" not in item["why_it_matters"]
    assert "expands Ice Make Refrigeration Ltd's paid-up equity capital" in item["why_it_matters"]

