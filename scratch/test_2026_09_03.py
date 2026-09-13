import zoneinfo
from datetime import datetime
from engine.run_context import RunContext, set_current_context
from engine.nse_bse_client import get_historical_exchange_announcements
from engine.news_collector import collect_historical_market_news
from engine.noise_filter import is_material_fundamental_event

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
dt = datetime.strptime("2026-09-03 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
ctx = RunContext(mode="historical", target_date="2026-09-03", cutoff_datetime=dt)
set_current_context(ctx)

anns, counts = get_historical_exchange_announcements("2026-09-03")
print(f"Total raw announcements: {len(anns)}")
surviving = []
for i, a in enumerate(anns):
    sym = a.get("raw_symbol")
    title = a.get("title", "")
    summary = a.get("summary", "")
    is_mat, reason = is_material_fundamental_event(title, summary, is_primary_exchange_filing=True, published_at="2026-09-03")
    if is_mat:
        surviving.append((sym, title, summary, reason))

from engine.fna_analyzer import synthesize_fna_item
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity

print(f"Surviving material announcements: {len(surviving)}")
for s in surviving[:25]:
    sym, title, summary, reason = s
    meta, _ = resolve_entity_from_text(f"{title} {summary}", filing_symbol=sym)
    comp_name = meta["name"] if meta else sym
    resolved_sym = meta["symbol"] if meta else sym
    ev = {
        "title": title,
        "summary": summary,
        "company_name": comp_name,
        "symbol": resolved_sym,
        "is_primary": True,
        "sources": ["NSE Corporate Announcement"]
    }
    item = synthesize_fna_item(ev, debug=False)
    if not item:
        print(f"REJECTED: {comp_name} ({sym}) - {title[:60]}")
    else:
        print("=" * 60)
        print(f"ACCEPTED: {item['company_name']} ({item['symbol']}) — {item['fundamental_direction']} [{item['event_type']}]")
        print(f"Headline: {item['headline']}")
        print(f"What happened: {item['what_happened']}")
        print(f"Why it matters: {item['why_it_matters']}")
        print(f"Fundamental impact: {item['fundamental_impact']}")
        print(f"Key financial implication: {item['key_financial_implication']}")

