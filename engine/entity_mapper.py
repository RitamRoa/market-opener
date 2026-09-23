"""
Entity Mapper & Resolution Module for Indian Listed Equities.
Provides rigorous entity verification, distinguishing parent companies from subsidiaries
(e.g., ICICI Bank vs ICICI Prudential Life vs ICICI Lombard; Reliance Industries vs Jio Financial Services).
Authoritative ticker resolution from exchange filings, multi-word matching, and negative lookaheads.
"""

import re
from typing import Optional, Dict, Any, List, Tuple

# Comprehensive curated universe of Indian listed companies
INDIAN_EQUITIES = [
    # ICICI Group (Explicitly separated)
    {
        "symbol": "ICICIBANK.NS",
        "name": "ICICI Bank Ltd",
        "sector": "Banking & Financial Services",
        "aliases": ["icici bank", "icicibank"],
        "exclusions": ["prudential", "pru life", "lombard", "securities", "amc", "mutual fund"]
    },
    {
        "symbol": "ICICIPRULI.NS",
        "name": "ICICI Prudential Life Insurance Co Ltd",
        "sector": "Life Insurance",
        "aliases": ["icici prudential life", "icici pru life", "icici pru", "icicipruli", "icici prudential life insurance"],
        "exclusions": []
    },
    {
        "symbol": "ICICIGI.NS",
        "name": "ICICI Lombard General Insurance Co Ltd",
        "sector": "General Insurance",
        "aliases": ["icici lombard", "icici lombard general insurance", "icicigi"],
        "exclusions": []
    },

    # Reliance Group & Jio (Explicitly separated)
    {
        "symbol": "RELIANCE.NS",
        "name": "Reliance Industries Ltd",
        "sector": "Conglomerate / Energy",
        "aliases": ["reliance industries", "ril", "mukesh ambani", "reliance retail"],
        "exclusions": ["jio financial", "jiofin", "reliance power", "reliance infra", "reliance communication", "rpower", "relinfra"]
    },
    {
        "symbol": "JIOFIN.NS",
        "name": "Jio Financial Services Ltd",
        "sector": "Fintech / Financial Services",
        "aliases": ["jio financial services", "jio financial", "jio fin", "jiofin"],
        "exclusions": []
    },
    {
        "symbol": "RPOWER.NS",
        "name": "Reliance Power Ltd",
        "sector": "Power Generation",
        "aliases": ["reliance power", "rpower", "anil ambani power"],
        "exclusions": []
    },
    {
        "symbol": "RELINFRA.NS",
        "name": "Reliance Infrastructure Ltd",
        "sector": "Infrastructure",
        "aliases": ["reliance infrastructure", "reliance infra", "relinfra"],
        "exclusions": []
    },

    # Tata Group (Explicitly separated)
    {
        "symbol": "TCS.NS",
        "name": "Tata Consultancy Services Ltd",
        "sector": "Information Technology",
        "aliases": ["tata consultancy services", "tcs"],
        "exclusions": ["motors", "steel", "power", "chemicals", "technologies", "tata tech", "elxsi", "consumer"]
    },
    {
        "symbol": "TATAMOTORS.NS",
        "name": "Tata Motors Ltd",
        "sector": "Automobile",
        "aliases": ["tata motors", "jaguar land rover", "jlr"],
        "exclusions": ["technologies", "tata tech", "consultancy", "steel", "power", "chemicals"]
    },
    {
        "symbol": "TATATECH.NS",
        "name": "Tata Technologies Ltd",
        "sector": "Engineering R&D / IT",
        "aliases": ["tata technologies", "tata tech"],
        "exclusions": ["motors", "consultancy"]
    },
    {
        "symbol": "TATASTEEL.NS",
        "name": "Tata Steel Ltd",
        "sector": "Metals & Mining",
        "aliases": ["tata steel"],
        "exclusions": []
    },
    {
        "symbol": "TATAPOWER.NS",
        "name": "Tata Power Company Ltd",
        "sector": "Power Generation & Utilities",
        "aliases": ["tata power"],
        "exclusions": []
    },
    {
        "symbol": "TATACHEM.NS",
        "name": "Tata Chemicals Ltd",
        "sector": "Chemicals",
        "aliases": ["tata chemicals"],
        "exclusions": []
    },
    {
        "symbol": "TATACONSUM.NS",
        "name": "Tata Consumer Products Ltd",
        "sector": "FMCG / Beverages",
        "aliases": ["tata consumer products", "tata consumer", "tata tea", "tata salt"],
        "exclusions": []
    },
    {
        "symbol": "TATAELXSI.NS",
        "name": "Tata Elxsi Ltd",
        "sector": "Design & Technology Services",
        "aliases": ["tata elxsi"],
        "exclusions": []
    },

    # HDFC Group (Explicitly separated)
    {
        "symbol": "HDFCBANK.NS",
        "name": "HDFC Bank Ltd",
        "sector": "Banking & Financial Services",
        "aliases": ["hdfc bank"],
        "exclusions": ["life", "amc", "asset management", "mutual fund"]
    },
    {
        "symbol": "HDFCLIFE.NS",
        "name": "HDFC Life Insurance Company Ltd",
        "sector": "Life Insurance",
        "aliases": ["hdfc life insurance", "hdfc life"],
        "exclusions": ["bank", "amc"]
    },
    {
        "symbol": "HDFCAMC.NS",
        "name": "HDFC Asset Management Company Ltd",
        "sector": "Asset Management",
        "aliases": ["hdfc amc", "hdfc mutual fund", "hdfc asset management"],
        "exclusions": ["bank", "life"]
    },

    # SBI Group (Explicitly separated)
    {
        "symbol": "SBIN.NS",
        "name": "State Bank of India",
        "sector": "Public Sector Banking",
        "aliases": ["state bank of india", "sbi"],
        "exclusions": ["life", "card", "cards", "mutual fund", "capital"]
    },
    {
        "symbol": "BANKBARODA.NS",
        "name": "Bank of Baroda",
        "sector": "Public Sector Banking",
        "aliases": ["bank of baroda", "bob"],
        "exclusions": []
    },
    {
        "symbol": "SBILIFE.NS",
        "name": "SBI Life Insurance Company Ltd",
        "sector": "Life Insurance",
        "aliases": ["sbi life insurance", "sbi life"],
        "exclusions": ["cards", "bank"]
    },
    {
        "symbol": "SBICARD.NS",
        "name": "SBI Cards and Payment Services Ltd",
        "sector": "Credit Cards & Payments",
        "aliases": ["sbi card", "sbi cards", "sbi payment"],
        "exclusions": ["life", "bank"]
    },

    # Bajaj Group (Explicitly separated)
    {
        "symbol": "BAJFINANCE.NS",
        "name": "Bajaj Finance Ltd",
        "sector": "NBFC / Retail Lending",
        "aliases": ["bajaj finance"],
        "exclusions": ["finserv", "auto"]
    },
    {
        "symbol": "BAJAJFINSV.NS",
        "name": "Bajaj Finserv Ltd",
        "sector": "Financial Holding / Insurance",
        "aliases": ["bajaj finserv"],
        "exclusions": ["finance", "auto"]
    },
    {
        "symbol": "BAJAJ-AUTO.NS",
        "name": "Bajaj Auto Ltd",
        "sector": "Automobile / Two-Wheelers",
        "aliases": ["bajaj auto"],
        "exclusions": ["finance", "finserv"]
    },

    # Larsen & Toubro Group (Explicitly separated)
    {
        "symbol": "LT.NS",
        "name": "Larsen & Toubro Ltd",
        "sector": "Infrastructure & Capital Goods",
        "aliases": ["larsen & toubro", "l&t", "larsen and toubro"],
        "exclusions": ["mindtree", "ltimindtree", "technology services", "ltts", "finance", "l&t finance"]
    },
    {
        "symbol": "LTIM.NS",
        "name": "LTIMindtree Ltd",
        "sector": "Information Technology",
        "aliases": ["ltimindtree", "ltim", "l&t infotech"],
        "exclusions": ["finance", "construction"]
    },
    {
        "symbol": "LTTS.NS",
        "name": "L&T Technology Services Ltd",
        "sector": "Engineering R&D Services",
        "aliases": ["l&t technology services", "ltts"],
        "exclusions": []
    },
    {
        "symbol": "LTF.NS",
        "name": "L&T Finance Ltd",
        "sector": "NBFC / Financial Services",
        "aliases": ["l&t finance", "lt finance", "ltf"],
        "exclusions": []
    },

    # Adani Group (Explicitly separated)
    {
        "symbol": "ADANIENT.NS",
        "name": "Adani Enterprises Ltd",
        "sector": "Conglomerate / Mining & Incubator",
        "aliases": ["adani enterprises", "adani ent"],
        "exclusions": ["ports", "power", "green", "total gas", "wilmar", "energy solutions"]
    },
    {
        "symbol": "ADANIPORTS.NS",
        "name": "Adani Ports and Special Economic Zone Ltd",
        "sector": "Ports & Logistics",
        "aliases": ["adani ports", "apsez"],
        "exclusions": ["power", "green", "enterprises"]
    },
    {
        "symbol": "ADANIPOWER.NS",
        "name": "Adani Power Ltd",
        "sector": "Thermal Power",
        "aliases": ["adani power"],
        "exclusions": ["green", "ports", "enterprises"]
    },
    {
        "symbol": "ADANIGREEN.NS",
        "name": "Adani Green Energy Ltd",
        "sector": "Renewable Energy",
        "aliases": ["adani green energy", "adani green"],
        "exclusions": ["power", "ports"]
    },
    {
        "symbol": "ATGL.NS",
        "name": "Adani Total Gas Ltd",
        "sector": "City Gas Distribution",
        "aliases": ["adani total gas", "atgl"],
        "exclusions": []
    },

    # Aviation, Energy Infrastructure & Logistics
    {
        "symbol": "INDIGO.NS",
        "name": "InterGlobe Aviation Ltd",
        "sector": "Aviation / Airlines",
        "aliases": ["indigo", "interglobe aviation", "interglobe", "indigo airlines"],
        "exclusions": ["paints"]
    },
    {
        "symbol": "PETRONET.NS",
        "name": "Petronet LNG Ltd",
        "sector": "Oil & Gas / LNG Infrastructure",
        "aliases": ["petronet lng", "petronet", "petronet lng ltd"],
        "exclusions": []
    },
    {
        "symbol": "SKYWAYS.NS",
        "name": "Skyways Air Services Limited",
        "sector": "Aviation & Logistics",
        "aliases": ["skyways air services", "skyways air", "skyways air services limited", "skyways"],
        "exclusions": []
    },

    # Key Railways, Defense, Infrastructure & PSUs
    {
        "symbol": "RVNL.NS",
        "name": "Rail Vikas Nigam Ltd",
        "sector": "Railways / Infrastructure",
        "aliases": ["rail vikas nigam", "rvnl"],
        "exclusions": []
    },
    {
        "symbol": "IRCTC.NS",
        "name": "Indian Railway Catering and Tourism Corp Ltd",
        "sector": "Railways / Tourism & Catering",
        "aliases": ["irctc", "indian railway catering"],
        "exclusions": []
    },
    {
        "symbol": "IRCON.NS",
        "name": "Ircon International Ltd",
        "sector": "Railways & Construction",
        "aliases": ["ircon international", "ircon"],
        "exclusions": []
    },
    {
        "symbol": "HAL.NS",
        "name": "Hindustan Aeronautics Ltd",
        "sector": "Aerospace & Defense",
        "aliases": ["hindustan aeronautics", "hal"],
        "exclusions": []
    },
    {
        "symbol": "BEL.NS",
        "name": "Bharat Electronics Ltd",
        "sector": "Defense Electronics",
        "aliases": ["bharat electronics", "bel"],
        "exclusions": []
    },
    {
        "symbol": "MAZDOCK.NS",
        "name": "Mazagon Dock Shipbuilders Ltd",
        "sector": "Shipbuilding & Defense",
        "aliases": ["mazagon dock", "mazagaon dock", "mazagon dock shipbuilders", "mazagaon dock shipbuilders", "mazdock"],
        "exclusions": []
    },
    {
        "symbol": "KRSNAA.NS",
        "name": "Krsnaa Diagnostics Ltd",
        "sector": "Healthcare & Diagnostics",
        "aliases": ["krsnaa diagnostics", "krsnaa diagnostics ltd", "krsnaa diagnostics limited", "krsnaa"],
        "exclusions": []
    },
    {
        "symbol": "MRPL.NS",
        "name": "Mangalore Refinery and Petrochemicals Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["mrpl", "mangalore refinery", "mangalore refinery and petrochemicals", "mangalore refinery & petrochemicals"],
        "exclusions": []
    },
    {
        "symbol": "HIGHWAYS.BO",
        "name": "Highway Infrastructure Trust",
        "sector": "Roads & Highways Infrastructure",
        "aliases": ["highway infrastructure", "highway infrastructure trust", "highway infra", "upeida toll", "highway infrastructure ltd"],
        "exclusions": []
    },
    {
        "symbol": "COCHINSHIP.NS",
        "name": "Cochin Shipyard Ltd",
        "sector": "Shipbuilding & Marine",
        "aliases": ["cochin shipyard"],
        "exclusions": []
    },
    {
        "symbol": "BHEL.NS",
        "name": "Bharat Heavy Electricals Ltd",
        "sector": "Capital Goods & Power Equipment",
        "aliases": ["bharat heavy electricals", "bhel"],
        "exclusions": []
    },
    {
        "symbol": "NTPC.NS",
        "name": "NTPC Ltd",
        "sector": "Power Generation",
        "aliases": ["ntpc", "ntpc limited"],
        "exclusions": []
    },
    {
        "symbol": "POWERGRID.NS",
        "name": "Power Grid Corporation of India Ltd",
        "sector": "Power Transmission",
        "aliases": ["power grid", "powergrid"],
        "exclusions": []
    },
    {
        "symbol": "COALINDIA.NS",
        "name": "Coal India Ltd",
        "sector": "Mining & Coal",
        "aliases": ["coal india"],
        "exclusions": []
    },
    {
        "symbol": "NMDC.NS",
        "name": "NMDC Ltd",
        "sector": "Mining & Iron Ore",
        "aliases": ["nmdc limited", "nmdc"],
        "exclusions": ["steel"]
    },
    {
        "symbol": "ONGC.NS",
        "name": "Oil & Natural Gas Corporation Ltd",
        "sector": "Oil Exploration & Production",
        "aliases": ["oil & natural gas", "oil and natural gas", "ongc"],
        "exclusions": []
    },
    {
        "symbol": "IOC.NS",
        "name": "Indian Oil Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["indian oil corporation", "iocl", "indian oil"],
        "exclusions": []
    },
    {
        "symbol": "BPCL.NS",
        "name": "Bharat Petroleum Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["bharat petroleum", "bpcl"],
        "exclusions": []
    },
    {
        "symbol": "HPCL.NS",
        "name": "Hindustan Petroleum Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["hindustan petroleum", "hpcl"],
        "exclusions": []
    },
    {
        "symbol": "GAIL.NS",
        "name": "GAIL (India) Ltd",
        "sector": "Natural Gas Transmission",
        "aliases": ["gail india", "gail"],
        "exclusions": []
    },
    {
        "symbol": "IGL.NS",
        "name": "Indraprastha Gas Ltd",
        "sector": "City Gas Distribution",
        "aliases": ["indraprastha gas", "igl"],
        "exclusions": []
    },
    {
        "symbol": "MGL.NS",
        "name": "Mahanagar Gas Ltd",
        "sector": "City Gas Distribution",
        "aliases": ["mahanagar gas", "mgl"],
        "exclusions": []
    },

    # Key Private Sector Bluechips
    {
        "symbol": "INFY.NS",
        "name": "Infosys Ltd",
        "sector": "Information Technology",
        "aliases": ["infosys", "infy"],
        "exclusions": []
    },
    {
        "symbol": "WIPRO.NS",
        "name": "Wipro Ltd",
        "sector": "Information Technology",
        "aliases": ["wipro"],
        "exclusions": []
    },
    {
        "symbol": "HCLTECH.NS",
        "name": "HCL Technologies Ltd",
        "sector": "Information Technology",
        "aliases": ["hcl technologies", "hcl tech"],
        "exclusions": []
    },
    {
        "symbol": "TECHM.NS",
        "name": "Tech Mahindra Ltd",
        "sector": "Information Technology",
        "aliases": ["tech mahindra", "techm"],
        "exclusions": ["semiconductor", "kaynes", "syrma", "moschip"]
    },
    {
        "symbol": "MAZDOCK.NS",
        "name": "Mazagon Dock Shipbuilders Ltd",
        "sector": "Defence & Shipbuilding",
        "aliases": ["mazagon dock shipbuilders", "mazagon dock shipbuilders ltd", "mazagon dock", "mazdock", "mdl"],
        "exclusions": []
    },
    {
        "symbol": "KAYNES.NS",
        "name": "Kaynes Technology India Ltd",
        "sector": "Electronics Manufacturing / Semiconductor",
        "aliases": ["kaynes technology india", "kaynes technology", "kaynes"],
        "exclusions": []
    },
    {
        "symbol": "SYRMA.NS",
        "name": "Syrma SGS Technology Ltd",
        "sector": "Electronics Manufacturing / Semiconductor",
        "aliases": ["syrma sgs technology", "syrma sgs", "syrma"],
        "exclusions": []
    },
    {
        "symbol": "MOSCHIP.NS",
        "name": "MosChip Technologies Ltd",
        "sector": "Semiconductor Design & Embedded Systems",
        "aliases": ["moschip technologies", "moschip"],
        "exclusions": []
    },
    {
        "symbol": "BHARTIARTL.NS",
        "name": "Bharti Airtel Ltd",
        "sector": "Telecommunications",
        "aliases": ["bharti airtel", "airtel"],
        "exclusions": []
    },
    {
        "symbol": "ITC.NS",
        "name": "ITC Ltd",
        "sector": "FMCG / Cigarettes & Hotels",
        "aliases": ["itc limited", "itc"],
        "exclusions": []
    },
    {
        "symbol": "HINDUNILVR.NS",
        "name": "Hindustan Unilever Ltd",
        "sector": "FMCG / Personal Care",
        "aliases": ["hindustan unilever", "hul"],
        "exclusions": []
    },
    {
        "symbol": "MARUTI.NS",
        "name": "Maruti Suzuki India Ltd",
        "sector": "Automobile / Passenger Cars",
        "aliases": ["maruti suzuki", "maruti"],
        "exclusions": []
    },
    {
        "symbol": "M&M.NS",
        "name": "Mahindra & Mahindra Ltd",
        "sector": "Automobile / UVs & Tractors",
        "aliases": ["mahindra & mahindra", "m&m", "mahindra and mahindra"],
        "exclusions": ["tech mahindra", "mahindra finance", "mahindra lifespaces"]
    },
    {
        "symbol": "TITAN.NS",
        "name": "Titan Company Ltd",
        "sector": "Consumer Goods / Jewellery",
        "aliases": ["titan company", "titan"],
        "exclusions": []
    },
    {
        "symbol": "ASIANPAINT.NS",
        "name": "Asian Paints Ltd",
        "sector": "Paints & Coatings",
        "aliases": ["asian paints", "asian paint"],
        "exclusions": []
    },
    {
        "symbol": "ULTRACEMCO.NS",
        "name": "UltraTech Cement Ltd",
        "sector": "Cement & Building Materials",
        "aliases": ["ultratech cement", "ultratech"],
        "exclusions": []
    },
    {
        "symbol": "SUNPHARMA.NS",
        "name": "Sun Pharmaceutical Industries Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["sun pharma", "sun pharmaceutical"],
        "exclusions": []
    },
    {
        "symbol": "DRREDDY.NS",
        "name": "Dr. Reddy's Laboratories Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["dr reddy", "dr reddys", "dr. reddy's"],
        "exclusions": []
    },
    {
        "symbol": "CIPLA.NS",
        "name": "Cipla Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["cipla"],
        "exclusions": []
    },
    {
        "symbol": "DIVISLAB.NS",
        "name": "Divi's Laboratories Ltd",
        "sector": "Pharmaceuticals / Active Ingredients",
        "aliases": ["divi's laboratories", "divis lab", "divis"],
        "exclusions": []
    },
    {
        "symbol": "LUPIN.NS",
        "name": "Lupin Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["lupin limited", "lupin"],
        "exclusions": []
    },
    {
        "symbol": "AUROPHARMA.NS",
        "name": "Aurobindo Pharma Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["aurobindo pharma", "aurobindo"],
        "exclusions": []
    },
    {
        "symbol": "POLYCAB.NS",
        "name": "Polycab India Ltd",
        "sector": "Wires & Cables / FMEG",
        "aliases": ["polycab india", "polycab"],
        "exclusions": []
    },
    {
        "symbol": "KEI.NS",
        "name": "KEI Industries Ltd",
        "sector": "Cables & EPC",
        "aliases": ["kei industries", "kei"],
        "exclusions": []
    },
    {
        "symbol": "SUZLON.NS",
        "name": "Suzlon Energy Ltd",
        "sector": "Renewable Energy / Wind Turbines",
        "aliases": ["suzlon energy", "suzlon"],
        "exclusions": []
    },
    {
        "symbol": "IREDA.NS",
        "name": "Indian Renewable Energy Development Agency Ltd",
        "sector": "Renewable Energy Financing",
        "aliases": ["ireda", "indian renewable energy"],
        "exclusions": []
    },
    {
        "symbol": "PFC.NS",
        "name": "Power Finance Corporation Ltd",
        "sector": "Power Sector NBFC",
        "aliases": ["power finance corporation", "pfc"],
        "exclusions": []
    },
    {
        "symbol": "RECLTD.NS",
        "name": "REC Ltd",
        "sector": "Power Sector NBFC",
        "aliases": ["rec limited", "rec ltd"],
        "exclusions": []
    },
    {
        "symbol": "ZOMATO.NS",
        "name": "Zomato Ltd",
        "sector": "Food Delivery / Quick Commerce",
        "aliases": ["zomato", "blinkit"],
        "exclusions": []
    },
    {
        "symbol": "TRENT.NS",
        "name": "Trent Ltd",
        "sector": "Retail & Apparel",
        "aliases": ["trent limited", "trent", "zudio", "westside"],
        "exclusions": []
    },
    {
        "symbol": "INDIGO.NS",
        "name": "InterGlobe Aviation Ltd",
        "sector": "Aviation / Airlines",
        "aliases": ["interglobe aviation", "indigo airlines", "indigo"],
        "exclusions": []
    },
    {
        "symbol": "DLF.NS",
        "name": "DLF Ltd",
        "sector": "Real Estate Development",
        "aliases": ["dlf limited", "dlf"],
        "exclusions": []
    },
    {
        "symbol": "LODHA.NS",
        "name": "Macrotech Developers Ltd",
        "sector": "Real Estate Development",
        "aliases": ["macrotech developers", "lodha"],
        "exclusions": []
    },
    {
        "symbol": "GODREJPROP.NS",
        "name": "Godrej Properties Ltd",
        "sector": "Real Estate Development",
        "aliases": ["godrej properties"],
        "exclusions": []
    },
    {
        "symbol": "AZAD.NS",
        "name": "Azad Engineering Ltd",
        "sector": "Precision Engineering / Defense & Aerospace",
        "aliases": ["azad engineering", "azad"],
        "exclusions": []
    },
    {
        "symbol": "SMLMAH.NS",
        "name": "SML Mahindra Limited",
        "sector": "Commercial Vehicles",
        "aliases": ["sml mahindra", "sml isuzu"],
        "exclusions": []
    },
    {
        "symbol": "GVT&D.NS",
        "name": "GE Vernova T&D India Ltd",
        "sector": "Power Transmission & Grid Equipment",
        "aliases": ["ge vernova t&d india", "ge vernova", "ge t&d india", "ge t&d", "gevernova"],
        "exclusions": []
    },
    {
        "symbol": "HINDCOPPER.NS",
        "name": "Hindustan Copper Ltd",
        "sector": "Metals & Mining / Copper",
        "aliases": ["hindustan copper", "hind copper"],
        "exclusions": []
    },
    {
        "symbol": "WABAG.NS",
        "name": "VA Tech Wabag Ltd",
        "sector": "Water Treatment & EPC Infrastructure",
        "aliases": ["va tech wabag", "va tech", "wabag"],
        "exclusions": []
    },
    # Defence & Aerospace
    {
        "symbol": "HAL.NS",
        "name": "Hindustan Aeronautics Ltd",
        "sector": "Defence & Aerospace",
        "aliases": ["hindustan aeronautics", "hal"],
        "exclusions": []
    },
    {
        "symbol": "BEL.NS",
        "name": "Bharat Electronics Ltd",
        "sector": "Defence Electronics",
        "aliases": ["bharat electronics", "bel"],
        "exclusions": []
    },
    {
        "symbol": "ASTRAMICRO.NS",
        "name": "Astra Microwave Products Ltd",
        "sector": "Defence & Satellite Subsystems",
        "aliases": ["astra microwave", "astra micro"],
        "exclusions": []
    },
    {
        "symbol": "SOLARINDS.NS",
        "name": "Solar Industries India Ltd",
        "sector": "Defence Munitions & Industrial Explosives",
        "aliases": ["solar industries", "solar inds"],
        "exclusions": []
    },
    {
        "symbol": "BDL.NS",
        "name": "Bharat Dynamics Ltd",
        "sector": "Defence Guided Missiles",
        "aliases": ["bharat dynamics", "bdl"],
        "exclusions": []
    },
    {
        "symbol": "COCHINSHIP.NS",
        "name": "Cochin Shipyard Ltd",
        "sector": "Defence Ship & Vessel Construction",
        "aliases": ["cochin shipyard"],
        "exclusions": []
    },
    {
        "symbol": "MAZDOCK.NS",
        "name": "Mazagon Dock Shipbuilders Ltd",
        "sector": "Defence Warships & Submarines",
        "aliases": ["mazagon dock", "mazdock"],
        "exclusions": []
    },
    {
        "symbol": "BEML.NS",
        "name": "BEML Ltd",
        "sector": "Heavy Engineering & Defence Vehicles",
        "aliases": ["beml limited", "beml"],
        "exclusions": []
    },
    {
        "symbol": "PARAS.NS",
        "name": "Paras Defence and Space Technologies Ltd",
        "sector": "Defence Optics & Space Electronics",
        "aliases": ["paras defence", "paras space"],
        "exclusions": []
    },
    {
        "symbol": "DATAPATTNS.NS",
        "name": "Data Patterns India Ltd",
        "sector": "Defence Electronics & Radars",
        "aliases": ["data patterns"],
        "exclusions": []
    },
    # Infrastructure, Real Estate & Railway EPC
    {
        "symbol": "GARUDA.NS",
        "name": "Garuda Construction and Engineering Ltd",
        "sector": "Civil Construction & EPC",
        "aliases": ["garuda construction", "garuda"],
        "exclusions": []
    },
    {
        "symbol": "EIEL.NS",
        "name": "Enviro Infra Engineers Ltd",
        "sector": "Environmental & Renewable EPC",
        "aliases": ["enviro infra engineers", "enviro infra", "eiel"],
        "exclusions": []
    },
    {
        "symbol": "RVNL.NS",
        "name": "Rail Vikas Nigam Ltd",
        "sector": "Railway Infrastructure & EPC",
        "aliases": ["rail vikas nigam", "rvnl"],
        "exclusions": []
    },
    {
        "symbol": "IRCON.NS",
        "name": "Ircon International Ltd",
        "sector": "Transport Infrastructure & EPC",
        "aliases": ["ircon international", "ircon"],
        "exclusions": []
    },
    {
        "symbol": "IRFC.NS",
        "name": "Indian Railway Finance Corp Ltd",
        "sector": "Railway Financing",
        "aliases": ["indian railway finance", "irfc"],
        "exclusions": []
    },
    {
        "symbol": "RAILTEL.NS",
        "name": "RailTel Corporation of India Ltd",
        "sector": "Telecom & Rail Infrastructure",
        "aliases": ["railtel corporation", "railtel"],
        "exclusions": []
    },
    {
        "symbol": "NBCC.NS",
        "name": "NBCC India Ltd",
        "sector": "Project Management & Civil EPC",
        "aliases": ["nbcc india", "nbcc"],
        "exclusions": []
    },
    {
        "symbol": "NCC.NS",
        "name": "NCC Ltd",
        "sector": "Construction & Infrastructure",
        "aliases": ["ncc limited", "ncc"],
        "exclusions": []
    },
    {
        "symbol": "PNCINFRA.NS",
        "name": "PNC Infratech Ltd",
        "sector": "Highways & Infrastructure",
        "aliases": ["pnc infratech", "pnc infra"],
        "exclusions": []
    },
    {
        "symbol": "KNRCON.NS",
        "name": "KNR Constructions Ltd",
        "sector": "Highways & Irrigation EPC",
        "aliases": ["knr constructions", "knr"],
        "exclusions": []
    },
    {
        "symbol": "PRESTIGE.NS",
        "name": "Prestige Estates Projects Ltd",
        "sector": "Real Estate Development",
        "aliases": ["prestige estates", "prestige group"],
        "exclusions": []
    },
    {
        "symbol": "GRINFRA.NS",
        "name": "G R Infraprojects Ltd",
        "sector": "Highways & Infrastructure EPC",
        "aliases": ["gr infraprojects", "gr infra", "g r infraprojects", "grinfra"],
        "exclusions": []
    },
    {
        "symbol": "WELCORP.NS",
        "name": "Welspun Corp Ltd",
        "sector": "Steel Pipes & Infrastructure",
        "aliases": ["welspun corp", "welspun corp ltd", "east pipes", "east pipes integrated company"],
        "exclusions": ["welspun living", "welspun enterprises"]
    },
    {
        "symbol": "WELENT.NS",
        "name": "Welspun Enterprises Ltd",
        "sector": "Infrastructure & Water EPC",
        "aliases": ["welspun enterprises", "welspun enterprises ltd"],
        "exclusions": ["welspun corp", "welspun living"]
    },
    {
        "symbol": "ADVAIT.NS",
        "name": "Advait Infratech Ltd",
        "sector": "Power Transmission & Green Energy",
        "aliases": ["advait infratech", "advait energy", "advait"],
        "exclusions": []
    },
    {
        "symbol": "ASHIANA.NS",
        "name": "Ashiana Housing Ltd",
        "sector": "Real Estate Development",
        "aliases": ["ashiana housing", "ashiana housing ltd", "ashiana"],
        "exclusions": []
    },
    {
        "symbol": "ORIANA.NS",
        "name": "Oriana Power Limited",
        "sector": "Renewable Energy / Solar & BESS",
        "aliases": ["oriana power", "truere oriana power", "truere oriana", "oriana power ltd", "oriana"],
        "exclusions": []
    },
    {
        "symbol": "LENSKART.NS",
        "name": "Lenskart",
        "sector": "Eyewear Retail & Consumer Tech",
        "aliases": ["lenskart", "lenskart solutions"],
        "exclusions": []
    },
    {
        "symbol": "OBEROIRLTY.NS",
        "name": "Oberoi Realty Ltd",
        "sector": "Real Estate Development",
        "aliases": ["oberoi realty", "oberoi"],
        "exclusions": []
    },
    # Power, Capital Goods & Electricals
    {
        "symbol": "ADANIPOWER.NS",
        "name": "Adani Power Ltd",
        "sector": "Thermal Power Generation",
        "aliases": ["adani power", "gvk energy"],
        "exclusions": ["ports", "green", "gas", "enterprises", "transmission"]
    },
    {
        "symbol": "TATAPOWER.NS",
        "name": "Tata Power Company Ltd",
        "sector": "Power Generation & Renewable Energy",
        "aliases": ["tata power"],
        "exclusions": ["motors", "steel", "consumer", "chemicals", "communications"]
    },
    {
        "symbol": "BHEL.NS",
        "name": "Bharat Heavy Electricals Ltd",
        "sector": "Heavy Electrical Equipment & EPC",
        "aliases": ["bharat heavy electricals", "bhel"],
        "exclusions": []
    },
    {
        "symbol": "SUZLON.NS",
        "name": "Suzlon Energy Ltd",
        "sector": "Wind Turbine Manufacturing",
        "aliases": ["suzlon energy", "suzlon"],
        "exclusions": []
    },
    {
        "symbol": "INOXWIND.NS",
        "name": "Inox Wind Ltd",
        "sector": "Wind Energy Solutions",
        "aliases": ["inox wind"],
        "exclusions": []
    },
    {
        "symbol": "POLYCAB.NS",
        "name": "Polycab India Ltd",
        "sector": "Wires & Cables / FMEG",
        "aliases": ["polycab india", "polycab"],
        "exclusions": []
    },
    {
        "symbol": "KEI.NS",
        "name": "KEI Industries Ltd",
        "sector": "Cables & EPC",
        "aliases": ["kei industries", "kei"],
        "exclusions": []
    },
    {
        "symbol": "HAVELLS.NS",
        "name": "Havells India Ltd",
        "sector": "Electrical Consumer Goods",
        "aliases": ["havells india", "havells"],
        "exclusions": []
    },
    {
        "symbol": "VOLTAS.NS",
        "name": "Voltas Ltd",
        "sector": "Air Conditioning & Cooling",
        "aliases": ["voltas"],
        "exclusions": []
    },
    {
        "symbol": "BLUESTARCO.NS",
        "name": "Blue Star Ltd",
        "sector": "Air Conditioning & Commercial Refrigeration",
        "aliases": ["blue star"],
        "exclusions": []
    },
    {
        "symbol": "DIXON.NS",
        "name": "Dixon Technologies India Ltd",
        "sector": "Electronics Manufacturing Services (EMS)",
        "aliases": ["dixon technologies", "dixon"],
        "exclusions": []
    },
    {
        "symbol": "KEC.NS",
        "name": "KEC International Ltd",
        "sector": "Power Transmission EPC",
        "aliases": ["kec international", "kec"],
        "exclusions": []
    },
    {
        "symbol": "KALPATPOWR.NS",
        "name": "Kalpataru Projects International Ltd",
        "sector": "Power Transmission & Infrastructure",
        "aliases": ["kalpataru projects", "kalpataru power", "kalpataru"],
        "exclusions": []
    },
    {
        "symbol": "THERMAX.NS",
        "name": "Thermax Ltd",
        "sector": "Energy & Environment Solutions",
        "aliases": ["thermax"],
        "exclusions": []
    },
    {
        "symbol": "CUMMINSIND.NS",
        "name": "Cummins India Ltd",
        "sector": "Diesel & Gas Engines / Gensets",
        "aliases": ["cummins india", "cummins"],
        "exclusions": []
    },
    # Pharmaceuticals & Healthcare
    {
        "symbol": "BIOCON.NS",
        "name": "Biocon Ltd",
        "sector": "Biopharmaceuticals & Biosimilars",
        "aliases": ["biocon limited", "biocon"],
        "exclusions": []
    },
    {
        "symbol": "SANOFI.NS",
        "name": "Sanofi India Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["sanofi india", "sanofi"],
        "exclusions": []
    },
    {
        "symbol": "LUPIN.NS",
        "name": "Lupin Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["lupin limited", "lupin"],
        "exclusions": []
    },
    {
        "symbol": "AUROPHARMA.NS",
        "name": "Aurobindo Pharma Ltd",
        "sector": "Pharmaceuticals & Generics",
        "aliases": ["aurobindo pharma", "aurobindo"],
        "exclusions": []
    },
    {
        "symbol": "TORNTPHARM.NS",
        "name": "Torrent Pharmaceuticals Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["torrent pharmaceuticals", "torrent pharma"],
        "exclusions": []
    },
    {
        "symbol": "ALKEM.NS",
        "name": "Alkem Laboratories Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["alkem laboratories", "alkem"],
        "exclusions": []
    },
    {
        "symbol": "GLENMARK.NS",
        "name": "Glenmark Pharmaceuticals Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["glenmark pharmaceuticals", "glenmark"],
        "exclusions": []
    },
    {
        "symbol": "IPCALAB.NS",
        "name": "IPCA Laboratories Ltd",
        "sector": "Pharmaceuticals & Active Ingredients",
        "aliases": ["ipca laboratories", "ipca"],
        "exclusions": []
    },
    {
        "symbol": "DIVISLAB.NS",
        "name": "Divi's Laboratories Ltd",
        "sector": "Active Pharmaceutical Ingredients (API)",
        "aliases": ["divi's laboratories", "divis lab", "divis"],
        "exclusions": []
    },
    {
        "symbol": "SYNGENE.NS",
        "name": "Syngene International Ltd",
        "sector": "Contract Research (CRO)",
        "aliases": ["syngene international", "syngene"],
        "exclusions": []
    },
    {
        "symbol": "APOLLOHOSP.NS",
        "name": "Apollo Hospitals Enterprise Ltd",
        "sector": "Healthcare Services & Hospitals",
        "aliases": ["apollo hospitals", "apollo hospital"],
        "exclusions": ["tyre", "tyres"]
    },
    {
        "symbol": "FORTIS.NS",
        "name": "Fortis Healthcare Ltd",
        "sector": "Hospitals & Diagnostics",
        "aliases": ["fortis healthcare", "fortis"],
        "exclusions": []
    },
    {
        "symbol": "MAXHEALTH.NS",
        "name": "Max Healthcare Institute Ltd",
        "sector": "Healthcare & Hospitals",
        "aliases": ["max healthcare"],
        "exclusions": ["financial", "life"]
    },
    # Financial Services, NBFCs & Exchanges
    {
        "symbol": "CGCL.NS",
        "name": "Capri Global Capital Ltd",
        "sector": "NBFC / MSME & Housing Finance",
        "aliases": ["capri global capital", "capri global", "cgcl"],
        "exclusions": []
    },
    {
        "symbol": "IFCI.NS",
        "name": "IFCI Ltd",
        "sector": "Development Financial Institution",
        "aliases": ["ifci limited", "ifci"],
        "exclusions": []
    },
    {
        "symbol": "PFC.NS",
        "name": "Power Finance Corporation Ltd",
        "sector": "Power Financing / NBFC",
        "aliases": ["power finance corporation", "pfc"],
        "exclusions": []
    },
    {
        "symbol": "RECLTD.NS",
        "name": "REC Ltd",
        "sector": "Power Financing / NBFC",
        "aliases": ["rec limited", "rec ltd", "rural electrification corporation"],
        "exclusions": []
    },
    {
        "symbol": "IREDA.NS",
        "name": "Indian Renewable Energy Development Agency Ltd",
        "sector": "Green Energy Financing",
        "aliases": ["indian renewable energy", "ireda"],
        "exclusions": []
    },
    {
        "symbol": "SHRIRAMFIN.NS",
        "name": "Shriram Finance Ltd",
        "sector": "NBFC / Commercial Vehicle Lending",
        "aliases": ["shriram finance"],
        "exclusions": []
    },
    {
        "symbol": "CHOLAFIN.NS",
        "name": "Cholamandalam Investment and Finance Co Ltd",
        "sector": "NBFC / Vehicle & Home Lending",
        "aliases": ["cholamandalam investment", "cholamandalam finance", "chola"],
        "exclusions": []
    },
    {
        "symbol": "MUTHOOTFIN.NS",
        "name": "Muthoot Finance Ltd",
        "sector": "Gold Loan Lending",
        "aliases": ["muthoot finance", "muthoot"],
        "exclusions": []
    },
    {
        "symbol": "MANAPPURAM.NS",
        "name": "Manappuram Finance Ltd",
        "sector": "Gold Loan Lending",
        "aliases": ["manappuram finance", "manappuram"],
        "exclusions": []
    },
    {
        "symbol": "BSE.NS",
        "name": "BSE Ltd",
        "sector": "Stock Exchange",
        "aliases": ["bse limited", "bse ltd"],
        "exclusions": []
    },
    {
        "symbol": "MCX.NS",
        "name": "Multi Commodity Exchange of India Ltd",
        "sector": "Commodity Exchange",
        "aliases": ["multi commodity exchange", "mcx"],
        "exclusions": []
    },
    {
        "symbol": "CDSL.NS",
        "name": "Central Depository Services India Ltd",
        "sector": "Securities Depository",
        "aliases": ["central depository services", "cdsl"],
        "exclusions": []
    },
    {
        "symbol": "CAMS.NS",
        "name": "Computer Age Management Services Ltd",
        "sector": "Mutual Fund Registrar & Transfer Agent",
        "aliases": ["computer age management", "cams"],
        "exclusions": []
    },
    # Consumer, Retail & Chemicals
    {
        "symbol": "BORORENEW.NS",
        "name": "Borosil Renewables Ltd",
        "sector": "Solar Glass Manufacturing",
        "aliases": ["borosil renewables", "borosil glass"],
        "exclusions": []
    },
    {
        "symbol": "BOROLTD.NS",
        "name": "Borosil Ltd",
        "sector": "Consumer Glassware & Laboratory Equipment",
        "aliases": ["borosil limited", "borosil ltd"],
        "exclusions": ["renewables"]
    },
    {
        "symbol": "SUKHJITS.NS",
        "name": "Sukhjit Starch & Chemicals Ltd",
        "sector": "Agro-processing & Starch Derivatives",
        "aliases": ["sukhjit starch & chemicals", "sukhjit starch", "sukhjits"],
        "exclusions": []
    },
    {
        "symbol": "SHIPROCKET.NS",
        "name": "Shiprocket (BigFoot Retail Solutions)",
        "sector": "E-Commerce Logistics & Enablement",
        "aliases": ["shiprocket"],
        "exclusions": []
    },
    {
        "symbol": "TRENT.NS",
        "name": "Trent Ltd",
        "sector": "Apparel & Retail (Zudio / Westside)",
        "aliases": ["trent limited", "trent", "zudio"],
        "exclusions": []
    },
    {
        "symbol": "VBL.NS",
        "name": "Varun Beverages Ltd",
        "sector": "Beverages & Bottling",
        "aliases": ["varun beverages", "vbl"],
        "exclusions": []
    },
    {
        "symbol": "DMART.NS",
        "name": "Avenue Supermarts Ltd",
        "sector": "Organized Retail & Supermarkets",
        "aliases": ["avenue supermarts", "dmart"],
        "exclusions": []
    },
    {
        "symbol": "ZOMATO.NS",
        "name": "Zomato Ltd",
        "sector": "Food Delivery & Quick Commerce (Blinkit)",
        "aliases": ["zomato", "blinkit"],
        "exclusions": []
    },
    {
        "symbol": "JUBLFOOD.NS",
        "name": "Jubilant FoodWorks Ltd",
        "sector": "Quick Service Restaurants (Domino's)",
        "aliases": ["jubilant foodworks", "dominos pizza", "domino's"],
        "exclusions": []
    },
    {
        "symbol": "PAGEIND.NS",
        "name": "Page Industries Ltd",
        "sector": "Apparel & Innerwear (Jockey)",
        "aliases": ["page industries", "jockey india"],
        "exclusions": []
    },
    {
        "symbol": "DEEPAKNTR.NS",
        "name": "Deepak Nitrite Ltd",
        "sector": "Specialty Chemicals & Intermediates",
        "aliases": ["deepak nitrite"],
        "exclusions": []
    },
    {
        "symbol": "TATACHEM.NS",
        "name": "Tata Chemicals Ltd",
        "sector": "Basic & Specialty Chemicals / Soda Ash",
        "aliases": ["tata chemicals"],
        "exclusions": ["motors", "steel", "power", "consumer"]
    },
    {
        "symbol": "SRF.NS",
        "name": "SRF Ltd",
        "sector": "Fluorochemicals & Packaging Films",
        "aliases": ["srf limited", "srf"],
        "exclusions": []
    },
    {
        "symbol": "PIDILITIND.NS",
        "name": "Pidilite Industries Ltd",
        "sector": "Adhesives & Construction Chemicals (Fevicol)",
        "aliases": ["pidilite industries", "pidilite", "fevicol"],
        "exclusions": []
    },
    # IT, Technology & Telecom
    {
        "symbol": "KPITTECH.NS",
        "name": "KPIT Technologies Ltd",
        "sector": "Automotive Embedded Software",
        "aliases": ["kpit technologies", "kpit"],
        "exclusions": []
    },
    {
        "symbol": "PERSISTENT.NS",
        "name": "Persistent Systems Ltd",
        "sector": "Digital Engineering & Enterprise IT",
        "aliases": ["persistent systems", "persistent systems ltd"],
        "exclusions": []
    },
    {
        "symbol": "COFORGE.NS",
        "name": "Coforge Ltd",
        "sector": "IT Solutions & Services",
        "aliases": ["coforge limited", "coforge"],
        "exclusions": []
    },
    {
        "symbol": "MPHASIS.NS",
        "name": "Mphasis Ltd",
        "sector": "Banking & Insurance IT Services",
        "aliases": ["mphasis limited", "mphasis"],
        "exclusions": []
    },
    {
        "symbol": "LTTS.NS",
        "name": "L&T Technology Services Ltd",
        "sector": "Engineering Research & Development (ER&D)",
        "aliases": ["l&t technology services", "ltts"],
        "exclusions": []
    },
    {
        "symbol": "TATACOMM.NS",
        "name": "Tata Communications Ltd",
        "sector": "Telecom & Digital Infrastructure",
        "aliases": ["tata communications"],
        "exclusions": ["motors", "steel", "power", "consumer", "chemicals"]
    },
    {
        "symbol": "TEJASNET.NS",
        "name": "Tejas Networks Ltd",
        "sector": "Telecom & Networking Equipment",
        "aliases": ["tejas networks"],
        "exclusions": []
    },
    {
        "symbol": "SHAKTIPUMP.NS",
        "name": "Shakti Pumps (India) Ltd",
        "sector": "Pumps & Industrial Machinery",
        "aliases": ["shakti pumps", "shakti pump", "shaktipump"],
        "exclusions": []
    },
    {
        "symbol": "GPTINFRA.NS",
        "name": "GPT Infraprojects Ltd",
        "sector": "Civil Construction & Infrastructure",
        "aliases": ["gpt infraprojects", "gpt infra", "gptinfra"],
        "exclusions": []
    },
    {
        "symbol": "IRB.NS",
        "name": "IRB Infrastructure Developers Ltd",
        "sector": "Roads & Highways Infrastructure",
        "aliases": ["irb infrastructure developers", "irb infra", "irb infrastructure", "irb"],
        "exclusions": []
    },
    {
        "symbol": "EUREKAFORB.NS",
        "name": "Eureka Forbes Ltd",
        "sector": "Consumer Appliances",
        "aliases": ["eureka forbes"],
        "exclusions": []
    },
    {
        "symbol": "AUBANK.NS",
        "name": "AU Small Finance Bank Ltd",
        "sector": "Banking & Financial Services",
        "aliases": ["au small finance bank", "au small finance", "au bank", "au sfb"],
        "exclusions": []
    },
    {
        "symbol": "HINDZINC.NS",
        "name": "Hindustan Zinc Ltd",
        "sector": "Metals & Mining",
        "aliases": ["hindustan zinc", "hzl"],
        "exclusions": []
    },
    {
        "symbol": "ASMTECH.NS",
        "name": "ASM Technologies Ltd",
        "sector": "IT Services & ER&D",
        "aliases": ["asm technologies", "asm tech", "asmtech"],
        "exclusions": []
    },
    {
        "symbol": "ONGC.NS",
        "name": "Oil and Natural Gas Corporation Ltd",
        "sector": "Oil & Gas Exploration",
        "aliases": ["oil and natural gas corporation", "ongc"],
        "exclusions": ["oil india"]
    },
    {
        "symbol": "OIL.NS",
        "name": "Oil India Ltd",
        "sector": "Oil & Gas Exploration",
        "aliases": ["oil india limited", "oil india"],
        "exclusions": ["oil and natural gas corporation", "ongc"]
    },
    {
        "symbol": "BEML.NS",
        "name": "BEML Ltd",
        "sector": "Defence & Heavy Engineering",
        "aliases": ["beml limited", "beml"],
        "exclusions": []
    },
    {
        "symbol": "GRAPHITE.NS",
        "name": "Graphite India Ltd",
        "sector": "Industrial Minerals & Electrodes",
        "aliases": ["graphite india"],
        "exclusions": []
    },
    {
        "symbol": "DIGJAM.NS",
        "name": "Digjam Ltd",
        "sector": "Textiles",
        "aliases": ["digjam limited", "digjam"],
        "exclusions": []
    },
    {
        "symbol": "INNOVISION.NS",
        "name": "Innovision Ltd",
        "sector": "Infrastructure & Facility Services",
        "aliases": ["innovision limited", "innovision"],
        "exclusions": []
    },
    {
        "symbol": "DUROPLY.NS",
        "name": "Duroply Industries Ltd",
        "sector": "Building Materials / Plywood",
        "aliases": ["duroply industries", "duroply"],
        "exclusions": []
    },
    {
        "symbol": "CYIENTDLM.NS",
        "name": "Cyient DLM Ltd",
        "sector": "Electronic Manufacturing Services",
        "aliases": ["cyient dlm"],
        "exclusions": []
    },
    {
        "symbol": "STLTECH.NS",
        "name": "Sterlite Technologies Ltd",
        "sector": "Telecom Equipment & Optical Fibre",
        "aliases": ["sterlite technologies", "stl tech"],
        "exclusions": []
    },
    {
        "symbol": "DBL.NS",
        "name": "Dilip Buildcon Ltd",
        "sector": "Infrastructure & EPC",
        "aliases": ["dilip buildcon limited", "dilip buildcon", "dbl"],
        "exclusions": []
    },
    {
        "symbol": "REDINGTON.NS",
        "name": "Redington Ltd",
        "sector": "Technology Distribution",
        "aliases": ["redington limited", "redington india", "redington"],
        "exclusions": []
    },
    {
        "symbol": "IOC.NS",
        "name": "Indian Oil Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["indian oil corporation", "indian oil", "iocl", "ioc"],
        "exclusions": []
    },
    {
        "symbol": "BPCL.NS",
        "name": "Bharat Petroleum Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["bharat petroleum corporation", "bharat petroleum", "bpcl"],
        "exclusions": []
    },
    {
        "symbol": "HPCL.NS",
        "name": "Hindustan Petroleum Corporation Ltd",
        "sector": "Oil Refining & Marketing",
        "aliases": ["hindustan petroleum corporation", "hindustan petroleum", "hpcl"],
        "exclusions": []
    },
    {
        "symbol": "INDIANB.NS",
        "name": "Indian Bank",
        "sector": "Public Sector Banking",
        "aliases": ["indian bank"],
        "exclusions": []
    },
    {
        "symbol": "SRGHFL.BO",
        "name": "SRG Housing Finance Ltd",
        "sector": "Housing Finance",
        "aliases": ["srg housing finance", "srg housing", "srg"],
        "exclusions": []
    },
    {
        "symbol": "JUNIPER.NS",
        "name": "Juniper Hotels Ltd",
        "sector": "Hospitality & Renewable Energy",
        "aliases": ["juniper hotels", "juniper green energy", "juniper green", "juniper"],
        "exclusions": []
    },
    {
        "symbol": "NBCC.NS",
        "name": "NBCC (India) Ltd",
        "sector": "Construction & Infrastructure",
        "aliases": ["nbcc", "nbcc india", "nbcc (india)", "national buildings construction corporation"],
        "exclusions": []
    },
    {
        "symbol": "PPLPHARMA.NS",
        "name": "Piramal Pharma Ltd",
        "sector": "Pharmaceuticals",
        "aliases": ["piramal pharma", "pplpharma", "piramal pharma limited"],
        "exclusions": ["piramal enterprises", "pel"]
    },
    {
        "symbol": "PEL.NS",
        "name": "Piramal Enterprises Ltd",
        "sector": "NBFC / Financial Services",
        "aliases": ["piramal enterprises", "pel"],
        "exclusions": ["piramal pharma", "pplpharma"]
    },
    {
        "symbol": "NEULANDLAB.NS",
        "name": "Neuland Laboratories Ltd",
        "sector": "Pharmaceuticals / APIs",
        "aliases": ["neuland laboratories", "neuland lab", "neuland labs", "neuland"],
        "exclusions": []
    },
    {
        "symbol": "BHARATFORG.NS",
        "name": "Bharat Forge Ltd",
        "sector": "Automobile & Defence Engineering",
        "aliases": ["bharat forge", "kalyani group forge"],
        "exclusions": []
    },
    {
        "symbol": "MAZDOCK.NS",
        "name": "Mazagon Dock Shipbuilders Ltd",
        "sector": "Defence Shipbuilding",
        "aliases": ["mazagon dock", "mazagon dock shipbuilders", "mazdock"],
        "exclusions": []
    },
    {
        "symbol": "BHEL.NS",
        "name": "Bharat Heavy Electricals Ltd",
        "sector": "Capital Goods & Power Equipment",
        "aliases": ["bharat heavy electricals", "bhel"],
        "exclusions": []
    },
    {
        "symbol": "GLAND.NS",
        "name": "Gland Pharma Ltd",
        "sector": "Pharmaceuticals / Injectables",
        "aliases": ["gland pharma", "gland"],
        "exclusions": []
    },
    {
        "symbol": "SONATSOFTW.NS",
        "name": "Sonata Software Ltd",
        "sector": "Information Technology",
        "aliases": ["sonata software", "sonatsoftw"],
        "exclusions": []
    },
    {
        "symbol": "ACMESOLAR.NS",
        "name": "ACME Solar Holdings Ltd",
        "sector": "Renewable Energy / Solar",
        "aliases": ["acme solar", "acme solar holdings", "acme cleantech", "544283"],
        "exclusions": []
    },
    {
        "symbol": "GREENPOWER.NS",
        "name": "Orient Green Power Company Ltd",
        "sector": "Renewable Energy / Wind & Biomass",
        "aliases": ["orient green power", "greenpower", "orient green", "533263"],
        "exclusions": []
    },
    {
        "symbol": "EXIDEIND.NS",
        "name": "Exide Industries Ltd",
        "sector": "Auto Ancillaries / Batteries",
        "aliases": ["exide industries", "exide ind", "exide"],
        "exclusions": []
    },
    {
        "symbol": "SAATVIK.BO",
        "name": "Saatvik Green Energy Ltd",
        "sector": "Renewable Energy / Solar Modules",
        "aliases": ["saatvik green energy", "saatvik solar", "saatvik green"],
        "exclusions": []
    },
    {
        "symbol": "VIKRAMSOLAR.NS",
        "name": "Vikram Solar Ltd",
        "sector": "Renewable Energy / Solar Modules",
        "aliases": ["vikram solar", "vikram solar limited"],
        "exclusions": []
    },
    {
        "symbol": "IDEA.NS",
        "name": "Vodafone Idea Ltd",
        "sector": "Telecommunications",
        "aliases": ["vodafone idea", "voda idea", "vi"],
        "exclusions": []
    },
    {
        "symbol": "NHPC.NS",
        "name": "NHPC Ltd",
        "sector": "Power Generation (Hydro)",
        "aliases": ["nhpc", "national hydroelectric power corporation"],
        "exclusions": []
    },
    {
        "symbol": "SJVN.NS",
        "name": "SJVN Ltd",
        "sector": "Power Generation",
        "aliases": ["sjvn", "satluj jal vidyut nigam"],
        "exclusions": []
    },
    {
        "symbol": "RBDENIMS.BO",
        "name": "R&B Denims Ltd",
        "sector": "Textiles / Apparel",
        "aliases": ["r&b denims", "rb denims", "r & b denims"],
        "exclusions": []
    }
]

# Fast lookup index: symbol -> metadata
SYMBOL_TO_META: Dict[str, Dict[str, Any]] = {item["symbol"]: item for item in INDIAN_EQUITIES}
# Bare symbol index (without .NS) -> metadata
BARE_SYMBOL_TO_META: Dict[str, Dict[str, Any]] = {item["symbol"].replace(".NS", "").replace(".BO", ""): item for item in INDIAN_EQUITIES}


def get_company_meta(symbol: str, text: Optional[str] = None) -> Dict[str, Any]:
    """Returns company metadata for any symbol, generating structured fallback if unindexed."""
    is_numeric = symbol.replace(".NS", "").replace(".BO", "").isdigit()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        clean_sym = symbol
    elif is_numeric:
        clean_sym = f"{symbol}.BO"
    else:
        clean_sym = f"{symbol}.NS"
    if clean_sym in SYMBOL_TO_META:
        return SYMBOL_TO_META[clean_sym]
    
    bare = clean_sym.replace(".NS", "").replace(".BO", "")
    if bare in BARE_SYMBOL_TO_META:
        return BARE_SYMBOL_TO_META[bare]

    # Attempt to extract genuine corporate name from text if available
    cand_name = None
    if text:
        m_corp = re.search(r"\b([A-Z][A-Za-z0-9\s&.\-]+?\s+(?:Limited|Ltd))\b", text)
        if m_corp:
            extracted = m_corp.group(1).strip()
            b_lower = bare.lower()
            if (bare.isdigit() or 
                any(tok in extracted.lower() for tok in b_lower.split() if len(tok) > 2) or 
                (len(b_lower) > 3 and b_lower[:4] in extracted.lower())):
                if len(extracted) < 55 and not any(k in extracted.lower() for k in ["exchange", "securities and exchange", "national stock exchange", "bse limited", "board of india"]):
                    cand_name = extracted

    if not cand_name:
        if bare.endswith("LIMITED"):
            cand_name = f"{bare[:-7].strip()} Limited"
        elif bare.endswith("LTD"):
            cand_name = f"{bare[:-3].strip()} Ltd"
        elif bare.isdigit():
            cand_name = f"BSE Listed Company ({bare})"
        else:
            cand_name = f"{bare} Limited"

    return {
        "symbol": clean_sym,
        "name": cand_name,
        "sector": "Indian Listed Equities",
        "aliases": [bare.lower(), cand_name.lower()],
        "exclusions": []
    }


def get_entity_by_symbol(sym: str) -> Optional[Dict[str, Any]]:
    for eq in INDIAN_EQUITIES:
        if eq.get("symbol") == sym:
            return eq
    return None


EXTERNAL_ECONOMIC_EXPOSURE_REGISTRY = [
    {
        "keywords": ["defence acquisition council", "dac", "capital acquisition", "weapons", "radar", "electronic warfare", "su-30mki", "fighter aircraft"],
        "condition": lambda t: any(k in t for k in ["defence acquisition council", "dac", "capital acquisition"]) and any(k in t for k in ["weapons", "radar", "electronic warfare", "fighter", "aircraft", "su-30mki", "air force", "armed forces"]),
        "resolver": lambda t: (
            get_entity_by_symbol("BEL.NS") if any(k in t for k in ["radar", "electronic warfare", "electronics"]) else
            get_entity_by_symbol("HAL.NS")
        ),
        "mechanism": "Verified economic exposure: defense capital procurement to domestic aerospace / electronics manufacturers"
    },
    {
        "keywords": ["copper", "smelter"],
        "condition": lambda t: "copper" in t and any(k in t for k in ["surge", "rally", "record high", "supply disruption", "smelter", "lme"]),
        "resolver": lambda t: get_entity_by_symbol("HINDCOPPER.NS"),
        "mechanism": "Verified economic exposure: pure-play domestic copper miner and producer"
    },
    {
        "keywords": ["hvdc", "transmission corridor"],
        "condition": lambda t: any(k in t for k in ["hvdc", "transmission corridor", "evacuate renewable"]),
        "resolver": lambda t: get_entity_by_symbol("POWERGRID.NS"),
        "mechanism": "Verified economic exposure: national grid utility & HVDC transmission infrastructure"
    },
    {
        "keywords": ["crude", "brent", "oil"],
        "condition": lambda t: any(k in t for k in ["brent", "crude oil", "crude benchmark", "crude price"]) and any(k in t for k in ["upstream", "realization", "production", "producers", "rally", "spikes past"]),
        "resolver": lambda t: get_entity_by_symbol("ONGC.NS"),
        "mechanism": "Verified economic exposure: upstream crude realization beneficiary"
    },
    {
        "keywords": ["crude", "brent", "omc", "fuel retail"],
        "condition": lambda t: any(k in t for k in ["brent", "crude oil"]) and any(k in t for k in ["marketing margin", "omc", "fuel retail", "retailer", "under-recovery"]),
        "resolver": lambda t: get_entity_by_symbol("IOC.NS"),
        "mechanism": "Verified economic exposure: fuel retail marketing margin compression"
    }
]



def clean_extracted_entity_name(name: str) -> str:
    """
    Rigorously strips leading and trailing tokens, administrative bodies, auxiliary verbs,
    temporal words, fiscal years, and announcement boilerplate from extracted corporate names.
    e.g. 'FY27' -> '', 'Today India Genrobotics' -> 'Genrobotics', 'OnEMI board' -> 'OnEMI', 'Welspun Corp unit' -> 'Welspun Corp'.
    """
    if not name:
        return ""
    cleaned = name.strip()

    # 1. Strip leading junk tokens:
    # - Fiscal year/quarter references: "FY27", "FY 2026-27", "Q1FY27"
    cleaned = re.sub(r"^(?:FY\s*\d{2,4}|Q[1-4](?:FY\s*\d{2,4})?)\b\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # - Publisher / news header artifacts: "Today India", "Manufacturing Today India", "Daily", "Morning", "Weekly"
    cleaned = re.sub(r"^(?:(?:Manufacturing\s+)?Today\s+India|Daily|Morning|Weekly|News|Report)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # - Temporal & frequency words: "Today", "Yesterday", "Tomorrow", "Now", "Recently"
    cleaned = re.sub(r"^(?:Today|Yesterday|Tomorrow|Now|Currently|Recently)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # - Stray leading prepositions & connector words: "In", "At", "On", "For", "To", "From", "With", "By", "As", "After", "Before", "Following", "Per"
    cleaned = re.sub(r"^(?:In|At|On|For|To|From|With|By|As|After|Before|Following|Per|According\s+to|Amid|Meanwhile)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # - Leading relationship prefixes: "Kissht parent OnEMI" -> "OnEMI"
    cleaned = re.sub(r"^(?:parent\s+|subsidiary\s+|promoter\s+|associate\s+|arm\s+|unit\s+|step-down\s+subsidiary\s+)", "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Strip trailing corporate action verbs, administrative bodies, and filler
    trailing_denylist = [
        r"\b(?:board(?:\s+of\s+directors)?|panel|committee|management|promoters?|shareholders?)\b.*$",
        r"\b(?:announced|announces|announcing|said|says|saying|stated|states|reported|reports)\b.*$",
        r"\b(?:has|have|had|is|are|was|were|will|shall|to|its|and|or|for|at|in|on|with)\b.*$",
        r"\b(?:arm|unit|subsidiary|division)$",  # Don't tack 'unit' or 'arm' onto display name!
    ]
    for pat in trailing_denylist:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # Discard if cleaned string is just a fiscal year or temporal word
    if re.match(r"^(?:FY\s*\d{2,4}|Q[1-4]|Today|Yesterday|Tomorrow|India)$", cleaned, re.IGNORECASE):
        return ""

    return cleaned


def validate_and_normalize_entity_display_name(extracted_name: str, symbol: Optional[str] = None) -> str:
    """
    Validates extracted entity name against the official listed equity master list.
    Exact or near-exact match only.
    On successful match, always returns the official company name from the master list.
    If no match is found, returns empty string to discard the candidate.
    """
    if not extracted_name and not symbol:
        return ""

    from engine.equity_master import resolve_entity
    grounded = resolve_entity(extracted_name, symbol=symbol)
    if grounded:
        return grounded[1]
    return ""


def extract_dynamic_corporate_entity(text: str) -> Optional[Dict[str, Any]]:
    """
    Dynamically resolves listed Indian corporate entities mentioned in text by strictly
    grounding them against the official NSE and BSE listed company masters.
    Rejects unlisted entities, law firms, and administrative bodies. Zero fabricated tickers.
    """
    if not text:
        return None

    from engine.equity_master import resolve_entity

    # Exclude common media, regulatory, legal, governmental or advisor phrases
    excluded_names = {
        "reuters", "bloomberg", "business standard", "economic times", "the economic times",
        "moneycontrol", "livemint", "mint", "financial express", "cnbc", "cnbc-tv18", "ndtv profit",
        "press information bureau", "pib", "sebi", "rbi", "reserve bank of india",
        "national stock exchange", "bse limited", "bombay stock exchange",
        "high court", "supreme court", "central government", "government of india",
        "ministry of finance", "ministry of defence", "defence acquisition council",
        "nifty 50", "bse sensex", "bank nifty", "cabinet committee",
        "dla piper", "webber wentzel", "cam", "cyril amarchand", "shardul amarchand",
        "azb & partners", "azb", "khaitan & co", "trilegal", "luthra",
        # Geopolitical, sovereign, military, political exclusions
        "pakistan", "pakistan army", "pakistan navy", "pakistan-china", "indian navy", "indian army",
        "army", "navy", "military", "air force", "defence ministry", "ministry", "parliament", "government",
        "trump", "trump's sons", "biden", "white house", "pentagon", "state department", "united states",
        "china", "russia", "israel", "iran", "saudi arabia", "bangladesh", "houthi", "united kingdom",
        "court", "tribunal", "commission", "boundary", "police"
    }

    advisor_keywords = ["advise", "advisor", "advising", "counsel", "law firm", "piper", "wentzel", "amarchand", "legal", "ratings limited", "credit ratings"]

    # Match formal Indian corporate names ending with Limited or Ltd
    pattern = r"\b([A-Z][A-Za-z0-9&.\-']+(?:\s+[A-Za-z0-9&.\-']+){0,3}\s+(?:Limited|Ltd))\b"
    matches = re.finditer(pattern, text)
    for m in matches:
        cand_name = clean_extracted_entity_name(m.group(1).strip())
        cand_lower = cand_name.lower()
        if any(ex in cand_lower for ex in excluded_names) or any(k in cand_lower for k in advisor_keywords) or len(cand_name) < 5 or len(cand_name) > 50:
            continue
        if is_awarding_client_in_text(text.lower(), cand_lower):
            continue

        grounded = resolve_entity(cand_name)
        if not grounded:
            continue
        sym, official_name = grounded
        return {
            "symbol": sym,
            "name": official_name,
            "sector": "Indian Listed Equities",
            "aliases": [cand_lower, sym.replace(".NS", "").replace(".BO", "").lower()],
            "exclusions": []
        }

    # Match corporate names acting as subjects before milestone verbs (anchored to clause start)
    pattern_action = r"(?:^|[.\n;\-]\s*)\b([A-Z][A-Za-z0-9&.\-']+(?:\s+[A-Za-z0-9&.\-']+){0,3})\s+(?:secures?|bags?|wins?|receives?|awarded|signs?|enters?\s+into|acquires?|approves?|commissions?|invests?|plans?\s+to\s+invest|to\s+invest)\b"
    for m in re.finditer(pattern_action, text):
        cand_name = clean_extracted_entity_name(m.group(1).strip())
        cand_lower = cand_name.lower()

        # Reject pure fiscal years or invalid tokens
        if not cand_name or re.match(r"^(?:FY\s*\d{2,4}|Q[1-4]|Today|Yesterday|India)$", cand_name, re.IGNORECASE):
            continue

        if cand_lower in ["mdl", "mazdock", "mazagon dock"]:
            return {
                "symbol": "MAZDOCK.NS",
                "name": "Mazagon Dock Shipbuilders Ltd",
                "sector": "Defence & Shipbuilding",
                "aliases": ["mazagon dock shipbuilders", "mazagon dock shipbuilders ltd", "mazagon dock", "mazdock", "mdl"],
                "exclusions": []
            }

        if any(ex in cand_lower for ex in excluded_names) or any(k in cand_lower for k in advisor_keywords) or len(cand_name) < 3 or len(cand_name) > 40:
            continue
        if is_awarding_client_in_text(text.lower(), cand_lower):
            continue

        grounded = resolve_entity(cand_name)
        if not grounded:
            continue
        sym, official_name = grounded
        return {
            "symbol": sym,
            "name": official_name,
            "sector": "Indian Listed Equities",
            "aliases": [cand_lower, sym.replace(".NS", "").replace(".BO", "").lower()],
            "exclusions": []
        }

    return None


def resolve_external_event_beneficiary(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Identifies listed Indian corporate beneficiaries for macro, government, commodity, or industry events
    by checking for company exposure independently from available evidence rather than hardcoded lists.
    """
    if not text:
        return None, "Empty text provided."
    text_lower = text.lower()

    # Dynamic Discovery: Match economic drivers against sectoral exposure mechanisms
    for reg in EXTERNAL_ECONOMIC_EXPOSURE_REGISTRY:
        if reg["condition"](text_lower):
            entity = reg["resolver"](text_lower)
            if entity:
                return entity, reg["mechanism"]
    return None, "No direct beneficiary without explicit exposure evidence."



def is_multi_company_roundup(text: str) -> bool:
    """Detects multi-company roundup articles (e.g. 'Stocks in news: Biocon, Bank of Baroda, TCS...')."""
    if not text:
        return False
    # Check only the title/headline portion (up to 120 chars), never full multi-sentence article summaries
    title_line = text.split("\n")[0].split(" - ")[0] if " - " in text else text.split("\n")[0]
    if len(title_line) > 130:
        title_line = title_line[:130]
    title_lower = title_line.lower()

    # If the headline refers to a single unifying corporate or sovereign event, it is not a generic container
    if re.search(r"\b(?:dac\b|procurement|lakh\s+crore|order\b|contract\b|bags?\b|secures?\b|wins?\b|loi\b|epc\b|usfda\b|fda\b|scheme\s+of\s+amalgamation|merger\s+with|preferential\s+issue|resignation\b|toll\s+revenue|raises?\s+fees?|fee\s+(?:hike|revision)|baggage|quarterly\s+results|net\s+profit|revenue\s+growth|consides?|approves?)\b", title_lower):
        return False

    if re.search(r"\b(?:stocks\s+in\s+news|stocks\s+to\s+watch|buzzing\s+stocks|top\s+stocks\s+to\s+watch|stocks\s+to\s+track|stocks,\s+including|shares,\s+including)\b", title_lower):
        return True

    # Sector rally / multi-stock movement (e.g., semiconductor stocks rallied, defence stocks surge)
    if re.search(r"\b(?:semiconductor|defence|pharma|railway|auto|banking|it)\s+stocks?\s+.*?\b(?:rally|rallied|surge|surged|gain|jump)\b", title_lower):
        return True

    comma_count = title_line.count(",")
    if re.search(r"\b(?:stocks?|shares?|brokerages?|losers?|gainers?)\b", title_lower) and comma_count >= 2 and any(conj in title_lower for conj in [" and ", " & ", "order sparks", "shares in focus", "stock picks", "stocks rally"]):
        return True

    return False


def is_awarding_client_in_text(text_lower: str, alias: str) -> bool:
    """
    Rigorously checks if an alias appears in an awarding customer/client role in a contract event:
      - 'order from <alias>'
      - 'contract from <alias>'
      - 'securing/bagging/winning <order> from <alias>'
      - 'awarded by / placed by <alias>'
      - '<alias> awards/places contract to'
    Never matches if alias is the subject winning/securing the order.
    """
    alias_esc = re.escape(alias)
    # If the alias is explicitly the subject performing the winning/securing action, it is the CONTRACTOR, not client!
    if re.search(rf"\b{alias_esc}\b\s+(?:wins?|won|bags?|bagged|secures?|secured|receives?|received)\b", text_lower):
        return False

    # Pattern 1: order/contract/project from <alias>
    if re.search(rf"\b(?:order|contract|project|work\s+order|epc|mandate|package)\b[^.]{{0,60}}?\bfrom\s+{alias_esc}\b", text_lower):
        return True
    # Pattern 2: securing/bags/bagged/secures/receives/wins ... from <alias>
    if re.search(rf"\b(?:secures?|secured|securing|bags?|bagged|bagging|wins?|won|winning|receives?|received|receiving|awarded)\b[^.]{{0,60}}?\bfrom\s+{alias_esc}\b", text_lower):
        return True
    # Pattern 3: awarded by / placed by / given by <alias>
    if re.search(rf"\b(?:awarded|placed|given)\s+by\s+{alias_esc}\b", text_lower):
        return True
    # Pattern 4: <alias> awards/places/gives contract/order to
    if re.search(rf"\b{alias_esc}\b\s+(?:awards?|awarded|places?|placed|gives?|given)\s+(?:a\s+)?(?:contract|order|project)\b", text_lower):
        return True
    # Pattern 5: <alias> as client project identifier (e.g. 'NTPC wind project order', 'NTPC thermal project')
    if re.search(rf"\b{alias_esc}\b\s+(?:[a-z0-9\-]+\s+){{0,2}}(?:project|wind\s+project|thermal\s+project|tender)\b", text_lower):
        if re.search(r"\b(?:secures?|secured|securing|bags?|bagged|bagging|wins?|won|winning|receives?|received|receiving|awarded|epc\s+contract)\b", text_lower):
            return True
    return False


def resolve_event_companies_and_roles(text: str) -> List[Dict[str, Any]]:
    """
    Rigorously parses event text to identify all referenced listed companies and assigns their operational roles.
    Distinguishes:
      - CONTRACTOR / VENDOR (winning/awarded the project -> direct positive exposure)
      - CUSTOMER / BUYER / OWNER (awarding/paying the contract -> capex/commercial client)
      - ISSUER (issuing debt/equity/warrants -> capital structure)
      - TARGET (being acquired)
      - ACQUIRER (purchasing target)
    """
    if not text:
        return []
    text_lower = text.lower()
    discovered: Dict[str, Dict[str, Any]] = {}

    for item in INDIAN_EQUITIES:
        sym = item["symbol"]
        for excl in item.get("exclusions", []):
            if re.search(rf"\b{re.escape(excl)}\b", text_lower):
                continue
        for alias in item["aliases"]:
            if len(alias) >= 3 and re.search(rf"\b{re.escape(alias)}\b", text_lower):
                if sym not in discovered or len(alias) > len(discovered[sym]["matched_alias"]):
                    discovered[sym] = {
                        "item": item,
                        "matched_alias": alias
                    }
                break

    roles: List[Dict[str, Any]] = []
    for sym, d in discovered.items():
        item = d["item"]
        alias = d["matched_alias"]
        name = item["name"]
        ticker = sym.replace(".NS", "").replace(".BO", "")

        if is_awarding_client_in_text(text_lower, alias):
            roles.append({
                "name": name,
                "ticker": ticker,
                "symbol": sym,
                "role": "CUSTOMER",
                "impact": "neutral_or_capex",
                "directness": "indirect",
                "primary": False
            })
        elif re.search(r"\b(?:order|contract|project|work\s+order|epc|mandate|package|secures?|secured|securing|bags?|bagged|bagging|wins?|won|winning)\b", text_lower):
            roles.append({
                "name": name,
                "ticker": ticker,
                "symbol": sym,
                "role": "CONTRACTOR",
                "impact": "positive",
                "directness": "direct",
                "primary": True
            })
        else:
            roles.append({
                "name": name,
                "ticker": ticker,
                "symbol": sym,
                "role": "BENEFICIARY",
                "impact": "positive",
                "directness": "direct",
                "primary": True
            })

    return roles


def resolve_entity_from_text(text: str, filing_symbol: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Rigorously resolves a text snippet (headline + description) to a single Indian listed company.
    Enforces MENTION != BENEFICIARY rule:
      1. Guards against multi-company roundup container articles (rejects wholesale attribution).
      2. Distinguishes winning contractor/vendor from awarding client/customer.
      3. Never assigns an order win to a customer paying capex.
    """
    if not text and not filing_symbol:
        return None, "Empty text and no filing symbol provided."

    text_lower = text.lower() if text else ""

    # Priority 0: If an exchange filing symbol is provided directly from NSE/BSE
    if filing_symbol:
        clean_filing = filing_symbol.strip().upper().replace(".NS", "").replace(".BO", "")
        # Check if clean_filing or scrip code matches any alias or ticker in INDIAN_EQUITIES
        for item in INDIAN_EQUITIES:
            if item["symbol"].replace(".NS", "").replace(".BO", "") == clean_filing or clean_filing.lower() in [a.lower() for a in item.get("aliases", [])]:
                return item, f"Resolved via authoritative exchange filing symbol/scrip '{clean_filing}' to {item['name']} ({item['symbol']})."

        is_bse = filing_symbol.strip().upper().endswith(".BO") or filing_symbol.strip().isdigit()
        suffix = ".BO" if (is_bse or clean_filing.isdigit()) else ".NS"
        canonical_sym = f"{clean_filing}{suffix}"
        meta = get_company_meta(canonical_sym, text=text)

        # Check if text explicitly discusses a different subsidiary
        for sub_item in INDIAN_EQUITIES:
            if sub_item["symbol"] == canonical_sym:
                continue
            for alias in sub_item["aliases"]:
                if len(alias) >= 5 and re.search(rf"\b{re.escape(alias)}\b", text_lower):
                    if any(ex in text_lower for ex in meta.get("exclusions", [])):
                        return sub_item, f"Re-routed from {canonical_sym} to distinct subsidiary {sub_item['symbol']} based on explicit mention of '{alias}'."

        return meta, f"Resolved via authoritative exchange filing symbol '{clean_filing}'."

    # Priority 1: Multi-company roundup container check (e.g. "Stocks in news: Biocon, Bank of Baroda, TCS...")
    if is_multi_company_roundup(text):
        return None, "Multi-company roundup container article; cannot attribute wholesale to a single entity."

    # Priority 2: Match against universe with longest-alias-first strategy
    candidates: List[Tuple[Dict[str, Any], str, int]] = []

    for item in INDIAN_EQUITIES:
        sym = item["symbol"]
        bare_ticker = sym.replace(".NS", "").replace(".BO", "").lower()

        # Check exclusions first: if text contains any forbidden word for this entity, skip!
        has_exclusion = False
        for excl in item.get("exclusions", []):
            if re.search(rf"\b{re.escape(excl)}\b", text_lower):
                has_exclusion = True
                break
        if has_exclusion:
            continue

        # Check aliases
        for alias in item["aliases"]:
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text_lower):
                candidates.append((item, alias, len(alias)))
                break

    if not candidates:
        ext_meta, ext_reason = resolve_external_event_beneficiary(text)
        if ext_meta:
            return ext_meta, ext_reason
        dynamic_cand = extract_dynamic_corporate_entity(text)
        if dynamic_cand:
            return dynamic_cand, f"Dynamically extracted corporate entity '{dynamic_cand['name']}' from text."

        return None, "No verified Indian listed entity found in text."

    # Priority 2.1: Primary Beneficiary Resolution (Contractor/Vendor vs Awarding Customer)
    client_candidates = []
    beneficiary_candidates = []

    for cand, alias, alias_len in candidates:
        if is_awarding_client_in_text(text_lower, alias):
            client_candidates.append((cand, alias, alias_len))
        else:
            beneficiary_candidates.append((cand, alias, alias_len))

    # Priority 2.2: Sovereign DAC Defence Procurement Resolution
    if any(k in text_lower for k in ["defence acquisition council", "dac", "procurement proposals", "acceptance of necessity", "aon"]):
        hal_cands = [c for c in beneficiary_candidates if c[0]["symbol"] == "HAL.NS"]
        if hal_cands:
            return hal_cands[0][0], "Resolved as apex sovereign aerospace/defence contractor 'Hindustan Aeronautics' (HAL.NS) for DAC capital procurement proposals."
        bel_cands = [c for c in beneficiary_candidates if c[0]["symbol"] == "BEL.NS"]
        if bel_cands:
            return bel_cands[0][0], "Resolved as sovereign defence electronics contractor 'Bharat Electronics' (BEL.NS) for DAC radar/EW procurement."

    # If we have genuine beneficiary candidates:
    if beneficiary_candidates:
        beneficiary_candidates.sort(key=lambda x: x[2], reverse=True)
        best_candidate, matched_alias, _ = beneficiary_candidates[0]
        if client_candidates:
            return best_candidate, f"Resolved as winning contractor/beneficiary '{best_candidate['name']}' ({best_candidate['symbol']}) over awarding customer/client '{client_candidates[0][0]['name']}'."
        return best_candidate, f"Matched specific alias '{matched_alias}' for {best_candidate['name']} ({best_candidate['symbol']})."

    # If all candidates are merely awarding customers (e.g. order won from NTPC, but contractor is unlisted/external):
    if client_candidates:
        client_cand, client_alias, _ = client_candidates[0]
        if re.search(r"\b(?:secures?|secured|securing|bags?|bagged|bagging|wins?|won|winning|receives?|received|receiving|awarded)\b.*?\b(?:order|contract|epc|project)\b", text_lower):
            return None, f"Entity '{client_cand['name']}' ({client_cand['symbol']}) is merely the customer/project owner issuing the contract; contractor beneficiary is outside listed universe."

    # Fallback: Sort candidates by length of matching alias descending (most specific match wins)
    candidates.sort(key=lambda x: x[2], reverse=True)
    best_candidate, matched_alias, _ = candidates[0]
    return best_candidate, f"Matched specific alias '{matched_alias}' for {best_candidate['name']} ({best_candidate['symbol']})."


def validate_event_entity(event_title: str, event_summary: str, assigned_symbol: str) -> Tuple[bool, str]:
    """
    Quality Control Gate 1: Entity Validation Check.
    Ensures that the assigned symbol is legitimately the subject of the news event,
    and catches conflicts such as Reliance Industries receiving Jio Financial news,
    or a customer being assigned an event where a vendor won a contract FROM that customer.
    """
    full_text = f"{event_title} {event_summary}".lower()
    clean_sym = assigned_symbol.replace(".NS", "").replace(".BO", "")
    meta = get_company_meta(assigned_symbol)

    # Check negative exclusions
    for excl in meta.get("exclusions", []):
        if re.search(rf"\b{re.escape(excl)}\b", full_text):
            # Check if text also explicitly names another company
            for other in INDIAN_EQUITIES:
                if other["symbol"] != assigned_symbol:
                    for alias in other["aliases"]:
                        if re.search(rf"\b{re.escape(alias)}\b", full_text):
                            return False, f"Entity mismatch: Text discusses '{alias}' ({other['symbol']}), which conflicts with assigned entity {assigned_symbol}."
            return False, f"Entity validation failed: Text triggered exclusion keyword '{excl}' for {assigned_symbol}."

    # Check if assigned_symbol is merely the awarding customer/client in a contract won by a vendor
    for alias in meta.get("aliases", []):
        if is_awarding_client_in_text(full_text, alias):
            return False, f"Entity validation failed: {assigned_symbol} is the awarding customer/project owner, not the winning contractor beneficiary."

    # Verify that assigned entity has legitimate textual presence in full_text
    if not assigned_symbol.startswith(("SECTOR:", "MACRO:")):
        aliases = meta.get("aliases", [])
        name_clean = meta.get("name", "")
        comp_tokens = [w for w in re.sub(r"[^\w\s]", " ", name_clean).lower().split() if len(w) >= 4 and w not in ["limited", "india", "company", "corporation", "ltd", "holdings", "industries"]]
        has_presence = False
        for a in aliases:
            if len(a) >= 3 and re.search(rf"\b{re.escape(a)}\b", full_text):
                has_presence = True
                break
        if not has_presence and comp_tokens:
            if any(re.search(rf"\b{re.escape(tok)}\b", full_text) for tok in comp_tokens):
                has_presence = True

        if not has_presence:
            return False, f"Entity validation failed: Assigned entity '{name_clean}' ({assigned_symbol}) has no textual presence in article."

    return True, f"Entity {assigned_symbol} validated successfully."


def match_company_in_text(text: str) -> List[Dict[str, Any]]:
    """Backward-compatible helper: resolves matching company in text."""
    meta, _ = resolve_entity_from_text(text)
    return [meta] if meta else []


# Authoritative grounded entity lookup from official NSE/BSE master
from engine.equity_master import resolve_entity


