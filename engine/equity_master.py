"""
Official Equity Master Resolution Module for Indian Listed Equities.
Grounds corporate entity resolution against official NSE and BSE listed company masters.
Guarantees:
  1. Exact or near-exact matching only (normalized names, symbols, and curated aliases).
  2. Zero fuzzy matching or synthetic ticker invention.
  3. Unlisted entities (e.g. Binance, Genrobotics, OnEMI) or garbage tokens (e.g. FY27) return None.
  4. Always returns official company name and official ticker symbol.
"""

import os
import csv
import json
import re
from typing import Optional, Tuple, Dict, Any, List

# Paths to master files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
NSE_MASTER_CSV = os.path.join(DATA_DIR, "nse_equity_master.csv")
BSE_MASTER_JSON = os.path.join(DATA_DIR, "bse_equity_master.json")

# Suffixes to strip during normalization
CORPORATE_SUFFIX_REGEX = re.compile(
    r"\b(?:private\s+limited|pvt\s+ltd|pvt\s+limited|limited|ltd|corporation|corp|inc|incorporated|llc|plc|company|co)\b\.?",
    re.IGNORECASE
)
INDIA_SUFFIX_REGEX = re.compile(
    r"\b(?:india\s+limited|india\s+ltd|\(india\)|india)\b\.?",
    re.IGNORECASE
)


def normalize_corporate_name(name: str) -> str:
    """
    Normalizes a corporate name for exact/near-exact matching:
    - Lowercases and converts '&' to 'and'.
    - Strips corporate legal suffixes (Ltd, Limited, Pvt Ltd, Corp, Inc, etc.).
    - Removes punctuation and normalizes whitespace.
    """
    if not name:
        return ""
    s = name.lower()
    s = s.replace("&", " and ")
    # Replace non-alphanumeric (except spaces) with space
    s = re.sub(r"[^\w\s]", " ", s)
    # Remove corporate suffixes
    s = CORPORATE_SUFFIX_REGEX.sub(" ", s)
    s = INDIA_SUFFIX_REGEX.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class EquityMasterIndex:
    """In-memory singleton index of official NSE and BSE listed companies."""

    def __init__(self):
        self.symbol_map: Dict[str, Tuple[str, str]] = {}  # SYMBOL -> (canonical_ticker, official_name)
        self.normalized_name_map: Dict[str, Tuple[str, str]] = {}  # norm_name -> (canonical_ticker, official_name)
        self.alias_map: Dict[str, Tuple[str, str]] = {}  # alias -> (canonical_ticker, official_name)
        self.loaded = False

    def load_masters(self) -> None:
        if self.loaded:
            return

        # 1. Load NSE Master CSV
        if os.path.exists(NSE_MASTER_CSV):
            with open(NSE_MASTER_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = (row.get("SYMBOL") or "").strip().upper()
                    name = (row.get("NAME OF COMPANY") or "").strip()
                    if not symbol or not name:
                        continue
                    canonical_sym = f"{symbol}.NS"
                    # Store (symbol, official_name)
                    self.symbol_map[symbol] = (symbol, name)
                    self.symbol_map[canonical_sym] = (symbol, name)
                    
                    norm_name = normalize_corporate_name(name)
                    if norm_name and norm_name not in self.normalized_name_map:
                        self.normalized_name_map[norm_name] = (symbol, name)
                    
                    # Also register exact lower name
                    exact_lower = name.lower().strip()
                    if exact_lower not in self.normalized_name_map:
                        self.normalized_name_map[exact_lower] = (symbol, name)

        # 2. Load BSE Master JSON
        if os.path.exists(BSE_MASTER_JSON):
            with open(BSE_MASTER_JSON, mode="r", encoding="utf-8", errors="ignore") as f:
                try:
                    bse_data = json.load(f)
                    for item in bse_data:
                        scrip_cd = str(item.get("SCRIP_CD") or "").strip()
                        scrip_id = str(item.get("scrip_id") or "").strip().upper()
                        issuer_name = str(item.get("Issuer_Name") or item.get("Scrip_Name") or "").strip()
                        if not issuer_name:
                            continue
                        
                        bse_ticker = scrip_id if scrip_id else scrip_cd
                        bse_canonical = f"{scrip_id}.BO" if scrip_id else f"{scrip_cd}.BO"
                        
                        # Register scrip_id and scrip_cd if not already present from NSE
                        if scrip_id and scrip_id not in self.symbol_map:
                            self.symbol_map[scrip_id] = (bse_ticker, issuer_name)
                            self.symbol_map[bse_canonical] = (bse_ticker, issuer_name)
                        if scrip_cd and scrip_cd not in self.symbol_map:
                            self.symbol_map[scrip_cd] = (bse_ticker, issuer_name)
                            self.symbol_map[f"{scrip_cd}.BO"] = (bse_ticker, issuer_name)

                        norm_name = normalize_corporate_name(issuer_name)
                        if norm_name and norm_name not in self.normalized_name_map:
                            self.normalized_name_map[norm_name] = (bse_ticker, issuer_name)
                        
                        scrip_name_norm = normalize_corporate_name(str(item.get("Scrip_Name") or ""))
                        if scrip_name_norm and scrip_name_norm not in self.normalized_name_map:
                            self.normalized_name_map[scrip_name_norm] = (bse_ticker, issuer_name)
                except Exception as e:
                    pass

        # 3. Load Curated Aliases from INDIAN_EQUITIES
        try:
            from engine.entity_mapper import INDIAN_EQUITIES
            for eq in INDIAN_EQUITIES:
                sym = eq.get("symbol", "").strip()
                official_name = eq.get("name", "").strip()
                if not sym or not official_name:
                    continue
                # Only register aliases for verified listed companies
                if sym in self.symbol_map:
                    canonical_ticker, master_name = self.symbol_map[sym]
                else:
                    continue  # Unlisted entity - discard!

                # Register all curated aliases
                for alias in eq.get("aliases", []):
                    clean_a = alias.lower().strip()
                    if clean_a:
                        self.alias_map[clean_a] = (canonical_ticker, master_name)
                        norm_a = normalize_corporate_name(clean_a)
                        if norm_a:
                            self.alias_map[norm_a] = (canonical_ticker, master_name)
        except Exception:
            pass

        self.loaded = True


# Singleton instance
_MASTER_INDEX = EquityMasterIndex()


def get_master_index() -> EquityMasterIndex:
    if not _MASTER_INDEX.loaded:
        _MASTER_INDEX.load_masters()
    return _MASTER_INDEX


def resolve_entity(extracted_name: str, symbol: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Grounds corporate entity resolution against the official NSE and BSE listed company master lists.
    Exact or near-exact match only (ignoring corporate suffixes, standard aliases).
    No fuzzy/approximate matching.
    
    Returns:
        (canonical_ticker, official_company_name) if successfully grounded.
        None if candidate is unlisted, fabricated, or noise (e.g. FY27, Binance, Genrobotics).
    """
    from engine.entity_mapper import clean_extracted_entity_name

    idx = get_master_index()

    # 1. Check direct symbol lookup if provided
    if symbol:
        clean_sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "").replace(".BSE", "")
        if clean_sym in idx.symbol_map:
            return idx.symbol_map[clean_sym]
        full_sym = symbol.strip().upper()
        if full_sym in idx.symbol_map:
            return idx.symbol_map[full_sym]

    if not extracted_name:
        return None

    # 2. Clean raw extracted string of temporal/publisher/fiscal year junk and trailing verbs
    cleaned = clean_extracted_entity_name(extracted_name).strip()
    if not cleaned or len(cleaned) < 2:
        return None

    # 3. Discard explicit noise/temporal patterns
    if re.match(r"^(?:FY\s*\d{2,4}|Q[1-4]|Today|Yesterday|Tomorrow|India)$", cleaned, re.IGNORECASE):
        return None

    cleaned_upper = cleaned.upper()
    cleaned_lower = cleaned.lower()

    # 4. Check if extracted string is an exact listed symbol (e.g. "TCS", "INFY", "MAZDOCK", "HAL")
    if cleaned_upper in idx.symbol_map:
        return idx.symbol_map[cleaned_upper]

    # 5. Check curated aliases (e.g. "ril" -> RELIANCE, "mazdock" -> MAZDOCK, "icici bank" -> ICICIBANK)
    if cleaned_lower in idx.alias_map:
        return idx.alias_map[cleaned_lower]

    # 6. Check normalized name map
    norm = normalize_corporate_name(cleaned)
    if norm in idx.alias_map:
        return idx.alias_map[norm]
    if norm in idx.normalized_name_map:
        return idx.normalized_name_map[norm]

    # 7. Exact lower check against normalized name map
    if cleaned_lower in idx.normalized_name_map:
        return idx.normalized_name_map[cleaned_lower]

    # If no exact/near-exact match in official listed universe, return None
    return None
