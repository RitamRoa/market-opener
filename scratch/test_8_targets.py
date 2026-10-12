import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity
from engine.equity_master import resolve_entity
from engine.fna_analyzer import classify_event_direction_and_type, synthesize_fna_item

test_cases = [
    ("Omaxe (SEBI order)", 
     "SAT dismisses Omaxe appeal against SEBI order over financial statement irregularities", 
     "The Exchange has sought clarification from Omaxe Limited with respect to recent news item captioned SAT dismisses Omaxe appeal against SEBI order over financial statement irregularities."),
    
    ("Clean Max Enviro (block deal)",
     "Clean Max Enviro share price volatile on a likely ₹1,063 crore block deal to sell 85 lakh shares",
     "Augment India is likely to sell shares worth ₹1,063 crore in Clean Max Enviro via a block deal at a floor price of ₹1,250 per share."),

    ("Aequs (promoter preferential warrants)",
     "Aequs approves preferential issue of convertible warrants to promoter group",
     "The Board of Directors of Aequs Limited approved the allotment of convertible equity warrants on a preferential basis to the promoter group, increasing promoter shareholding to 62%."),

    ("Signature Global",
     "Signatureglobal targets ₹6,000 crore GDV from Gurugram luxury villa project; launch in 9-12 months",
     "Signature Global (India) Limited targets ₹6,000 crore gross development value (GDV) from its upcoming luxury villa project in Gurugram, scheduled for launch within 9 to 12 months."),

    ("Godrej Properties",
     "Godrej Properties to develop ₹6,000 cr luxury housing project in Mumbai",
     "Godrej Properties has entered into an agreement to develop a 2.5-acre prime land parcel in South Mumbai with estimated GDV of ₹6,000 crore."),

    ("Dredging Corporation",
     "Govt extends green clearances for ports, dredging projects to up to 30 yrs",
     "Dredging Corporation of India to benefit as Ministry of Environment extends environmental clearances for port and dredging infrastructure projects up to 30 years."),

    ("SAIL (BCCL MoU)",
     "SAIL signs MoU with Bharat Coking Coal (BCCL) for coking coal supply",
     "Steel Authority of India Limited (SAIL) has entered into a memorandum of understanding (MoU) with Bharat Coking Coal Limited (BCCL) to secure long-term domestic coking coal supplies for its blast furnaces."),

    ("Augmont Enterprises (NSE EGR)",
     "Augmont Enterprises shares rally 10% as NSE empanels company for EGR ecosystem",
     "Augmont Enterprises and its subsidiaries were empanelled by NSE as key partners to promote the Electronic Gold Receipt (EGR) ecosystem.")
]

for label, title, summary in test_cases:
    print(f"\n==================== {label} ====================")
    # 1. Noise gate
    is_mat, n_reason = is_material_fundamental_event(title, summary)
    print(f"1. Noise Gate: {'PASSED' if is_mat else 'DROPPED'} ({n_reason})")
    
    # 2. Entity resolution
    full_text = f"{title} {summary}"
    meta, res_reason = resolve_entity_from_text(full_text)
    if not meta:
        print(f"2. Entity Resolution: DROPPED ({res_reason})")
        continue
    grounded = resolve_entity(meta["name"], symbol=meta["symbol"])
    if not grounded:
        print(f"2. Entity Grounding: DROPPED ({meta['name']} not in equity master)")
        continue
    official_ticker, official_name = grounded
    is_valid, v_reason = validate_event_entity(title, summary, meta["symbol"])
    if not is_valid:
        print(f"2. Entity Validation: DROPPED ({v_reason})")
        continue
    print(f"2. Entity Resolution: PASSED -> {official_name} ({official_ticker})")

    # 3. Classification
    ev_type, direction, base_mat = classify_event_direction_and_type(full_text)
    print(f"3. Classification: Type={ev_type}, Direction={direction}, BaseMat={base_mat}")

    # 4. Synthesis
    cluster = {
        "title": title,
        "summary": summary,
        "company_name": official_name,
        "symbol": meta["symbol"],
        "ticker": official_ticker,
        "sources": ["Public Disclosure"],
        "is_primary": False
    }
    synth = synthesize_fna_item(cluster)
    if not synth:
        print(f"4. Synthesis: DROPPED (Returned None)")
    else:
        print(f"4. Synthesis: PASSED -> Direction={synth.get('fundamental_direction')}, MatScore={synth.get('materiality_score')}")
