import pytest
from engine.fna_analyzer import (
    determine_company_role_and_variable,
    synthesize_fna_item,
    verify_credit_rating_event,
    classify_event_type,
)

def test_hindustan_zinc_role_and_variable():
    """Hindustan Zinc deploying e-trucks must have role customer/operator, not contractor."""
    headline = "Hindustan Zinc deploys 30 electric trucks for logistics decarbonisation"
    company = "Hindustan Zinc"
    ev_type = classify_event_type(headline)
    assert ev_type == "OPERATIONAL_INITIATIVE"
    
    role, econ_var = determine_company_role_and_variable(company, headline, ev_type)
    assert role in ("customer", "operator")
    assert "efficiency" in econ_var or "decarbonization" in econ_var or "opex" in econ_var

def test_hindustan_zinc_no_order_book_claims():
    """Synthesizing Hindustan Zinc deployment must NEVER claim order book growth or revenue visibility."""
    event = {
        "title": "Hindustan Zinc deploys 30 electric trucks for logistics decarbonisation",
        "company": "Hindustan Zinc",
        "summary": "Hindustan Zinc has deployed 30 electric trucks from MFL India for green logistics.",
        "text": "Hindustan Zinc announced deployment of 30 55-tonne electric trucks from MFL India to decarbonize supply chain operations.",
        "symbol": "HINDZINC.NS",
        "timestamp": "2026-09-09T10:00:00+05:30",
        "source": "BSE"
    }
    item = synthesize_fna_item(event)
    assert item is not None
    assert item["company_role"] in ("customer", "operator")
    assert "order book" not in item["why_it_matters"].lower()
    assert "revenue visibility" not in item["key_financial_implication"].lower()
    assert "contract win" not in item["fundamental_impact"].lower()

def test_asm_technologies_preferential_issue():
    """ASM Tech preferential issue must be equity capital expansion, NOT credit rating upgrade."""
    headline = "ASM Technologies approves preferential issue of equity shares and warrants"
    company = "ASM Technologies"
    ev_type = classify_event_type(headline)
    assert ev_type == "FUNDING_EQUITY"
    
    role, econ_var = determine_company_role_and_variable(company, headline, ev_type)
    assert role == "issuer"
    assert "equity capital" in econ_var or "capital" in econ_var
    
    event = {
        "title": headline,
        "company": company,
        "summary": "ASM Technologies board approved issue of equity shares and convertible warrants on preferential basis.",
        "text": "ASM Technologies approved preferential allotment to raise funds for working capital and business expansion.",
        "symbol": "ASMTEC.BO",
        "timestamp": "2026-09-09T10:00:00+05:30",
        "source": "BSE"
    }
    item = synthesize_fna_item(event)
    assert item is not None
    assert item["company_role"] == "issuer"
    assert "credit rating" not in item["why_it_matters"].lower()
    assert "credit rating" not in item["key_financial_implication"].lower()
    assert "borrowing cost" not in item["fundamental_impact"].lower()

def test_credit_rating_reaffirmation_rejected():
    """Reaffirmations, withdrawals, and ESG assessments must be rejected by verify_credit_rating_event."""
    reaffirm_text = "ICRA reaffirms [ICRA]AA- rating of ABC Ltd with stable outlook"
    valid, action, agency = verify_credit_rating_event(reaffirm_text)
    assert valid is False
    assert action == "reaffirmation"

    withdraw_text = "CRISIL withdraws rating on commercial paper of XYZ Ltd at company request"
    valid, action, agency = verify_credit_rating_event(withdraw_text)
    assert valid is False
    assert action == "withdrawal"

    esg_text = "Crisil assigns ESG score of 65 to DEF Industries"
    valid, action, agency = verify_credit_rating_event(esg_text)
    assert valid is False

def test_credit_rating_upgrade_and_downgrade_valid():
    """Genuine upgrades and downgrades must be accepted and agency extracted accurately."""
    upgrade_text = "CARE upgrades long-term credit rating of ABC Ltd to CARE AA from CARE A+"
    valid, action, agency = verify_credit_rating_event(upgrade_text)
    assert valid is True
    assert action == "upgrade"
    assert agency == "CARE"

    downgrade_text = "ICRA downgrades short-term bank facilities of XYZ Ltd to ICRA A3"
    valid, action, agency = verify_credit_rating_event(downgrade_text)
    assert valid is True
    assert action == "downgrade"
    assert agency == "ICRA"

def test_dac_defence_approval_contextualization():
    """DAC defence approvals must be contextualized as procurement opportunities, NOT booked revenue."""
    headline = "DAC clears defence procurement worth Rs 45,000 crore under Make in India"
    event = {
        "title": headline,
        "company": "Bharat Electronics",
        "summary": "Defence Acquisition Council cleared AoN for procurement worth 45,000 crore.",
        "text": "The DAC accorded Acceptance of Necessity for indigenous defence equipment procurement.",
        "symbol": "BEL.NS",
        "timestamp": "2026-09-09T10:00:00+05:30",
        "source": "PIB"
    }
    item = synthesize_fna_item(event)
    assert item is not None
    assert "procurement" in item["why_it_matters"].lower()
    assert "procurement pipeline" in item["key_financial_implication"].lower()
    # Confirm it does not falsely claim immediate booked revenue
    assert "immediate booked revenue" not in item["why_it_matters"].lower() or "rather than" in item["why_it_matters"].lower()
