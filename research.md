# Indian Stock Market Intelligence Engine: Comprehensive Research, Selection Methodology & Mathematical Models

---

## 1. Executive Summary & Architecture Overview

The **Indian Stock Market Fundamental News & Analysis (FNA) and Opportunity Intelligence Engine** is an institutional-grade, deterministic, and evidence-driven analytical framework designed specifically for the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE).

The platform operates under five core principles:
1. **Event-First & Zero-Hallucination**: Every insight is anchored directly in verified primary regulatory filings (NSE/BSE announcements, SEBI/RBI orders, PIB releases) or established financial press.
2. **Deterministic Mathematical Scoring**: Stocks are selected, qualified, and ranked through explicit mathematical models, multi-factor weighting schemes, and strict materiality thresholds—eliminating arbitrary heuristics and prompt hallucinations.
3. **Broad Candidate Evaluation Before Rejection**: Potentially important fundamental events are preserved through an early noise filter and evaluated in a broad canonical candidate pool before any actionability decision is made.
4. **Dynamic Actionability (Min Target 4–5, No Hard Limit)**: The final FNA does NOT have a hardcoded count like exactly 3 or 5 stocks. It outputs all genuinely actionable fundamental developments (whether 4, 8, 12, or 15). Quality beats minimum: if only 2–3 genuinely actionable stocks exist, it outputs 2–3 rather than inventing weak noise.
5. **Ascending Closing Price Sorting**: Closing prices for the research date are fetched strictly after fundamental selection is finalized. Stocks are sorted from **Lowest Closing Price $\longrightarrow$ Highest Closing Price** for clean market readability, with price having **zero influence** on selection.
6. **Local & Autonomous**: The system operates with zero external paid API keys, utilizing primary feeds, cached market data, local Python analytical modules, and optional local LLMs with automatic fallback to built-in rule intelligence.

```
+---------------------------------------------------------------------------------------------------+
|                                    DATA INGESTION LAYER                                           |
|  NSE / BSE Announcements (Multi-page)  |  Regulatory (SEBI/RBI/PIB)  |  Financial Press (8+ Feeds) |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                            STAGE 1: QUALITY GATING & BASIC NOISE FILTER                           |
|  - Noise Filter (Reject routine compliance, AGM notices, ESOPs, trading windows, broker calls)    |
|  - Freshness Gate (Reject stale historical quarterly updates)                                     |
|  - Multi-Company Article Splitter (Disassemble roundup articles into discrete company events)     |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                             STAGE 2: ENTITY RESOLUTION & VERIFICATION                             |
|  - Authoritative Symbol Resolution (Ticker mapping to .NS / .BO & BSE scrip fallback)             |
|  - Parent vs Subsidiary Disambiguation (e.g., ICICI Bank vs ICICI Prudential vs ICICI Lombard)    |
|  - Economic Beneficiary Role Resolution (Contractor/Issuer vs Buyer/Customer)                    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                        STAGE 3: DEDUPLICATION & MULTI-SOURCE CLUSTERING                            |
|  - Text Similarity Token Matching (Threshold: 0.35) -> Canonical Event Grouping                   |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                  STAGE 4: FUNDAMENTAL ANALYSIS OF BROAD CANONICAL CANDIDATE POOL                  |
|  - Event Synthesis across 16 Canonical Event Categories                                           |
|  - Strict Binary Directionality Check: Positive or Negative only (Reject Ambiguous/Neutral)       |
|  - 10-Factor Research Importance Model -> RESEARCH_IMPORTANCE_SCORE (0 to 10)                      |
|  - Materiality Tier Assignment -> Tier A (Must Consider), Tier B (Secondary), Tier C              |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                        STAGE 5: ACTIONABILITY & MATERIALITY ASSESSMENT                            |
|  - Evaluate genuine operational catalysts (Orders, Capex, Approvals, M&A, Restructuring)        |
|  - Verified economic impact & quantified scale vs company baseline                                |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                STAGE 6: DYNAMIC CANDIDATE RANKING (MIN TARGET 4–5, NO FIXED CAP)                  |
|  - Prioritize Tier A & primary actionable catalysts                                               |
|  - If < 4: Evaluate qualified secondary candidates without adding weak noise (Quality > Minimum)  |
|  - Show entire actionable pool (e.g. 5, 8, 12, 15 stocks; never arbitrarily capped at 5)          |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                 STAGE 7: CLOSING PRICE RETRIEVAL & ASCENDING SORT (LOWEST -> HIGHEST)             |
|  - Retrieve date-specific closing prices on or before requested date                              |
|  - Filter out unlisted entities (DRHPs, pre-IPO filings)                                          |
|  - Sort final report: Lowest Closing Price -> Highest Closing Price (Zero selection influence)    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                               OUTPUT GENERATION & PERSISTENCE                                     |
|  - 7-Stage Diagnostic Funnel Report (Candidates Retrieved -> Final TOP NEWS)                      |
|  - Sharekhan-Style Terminal FNA Bulletin & Comprehensive Intelligence Markdown Report             |
|  - SQLite Storage & JSON/Text Export in `reports/`                                                |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Data Ingestion & Harmonization

### 2.1 Primary Data Feeds
1. **Exchange Announcements (Primary Source)**:
   - Automated polling of NSE Corporate Disclosures and BSE Regulatory filings.
   - Raw feeds provide high-conviction company filings, official tender captures, earnings releases, board outcomes, and management intimations.
2. **Regulatory & Policy Feeds**:
   - Press Information Bureau (PIB), Defence Acquisition Council (DAC), Cabinet Committee on Economic Affairs (CCEA), Reserve Bank of India (RBI), and Securities and Exchange Board of India (SEBI) notification streams.
3. **Institutional Financial Press**:
   - RSS feeds and news scrapers monitoring *The Economic Times*, *Business Standard*, *Livemint*, *Moneycontrol*, *Reuters*, *Bloomberg*, *CNBC-TV18*, and *NDTV Profit*.

### 2.2 Timezone & Temporal Boundary Enforcement
- All timestamps from RSS feeds (RFC 2822), ISO strings, and exchange filings are parsed into **Asia/Kolkata (IST)**:
  $$\text{Parsed Time} \rightarrow \text{UTC} + 05:30 \quad (\text{Asia/Kolkata})$$
- **Temporal Run Context (`RunContext`)**:
  - When analyzing historical dates (`--date YYYY-MM-DD --cutoff HH:MM:SS`), the system enforces strict temporal isolation:
    $$\text{Event Eligible} \iff \text{Publication Timestamp (IST)} \le \text{Cutoff Datetime (IST)}$$
  - Prevents future look-ahead bias and eliminates data leakage into historical backtests.

### 2.3 Multi-Company Article Deconstruction
Market media frequently publish roundup containers (e.g., *"Stocks in news: Biocon, Tata Motors, L&T, Infosys"*).
- The pipeline detects roundup titles matching:
  $$\text{Pattern} = \text{Regex}(\verb|\b(stocks in news|stocks to watch|stocks to track|buzzing stocks)\b|)$$
- The splitter splits containers using sentence structure, bullet points, and corporate action verbs (`announced`, `secures`, `bags`, `receives`, `wins`, `reports`) to extract independent, discrete `(Company, Event)` candidate pairs for standalone validation.

---

## 3. Multi-Stage Quality Control Gating

Before any corporate event reaches the scoring engine, it must pass three mandatory quality gates.

### 3.1 Quality Gate 1: Noise Filter & Freshness Testing (`engine/noise_filter.py`)
This gate discards administrative, compliance, promotional, and stale noise.

#### A. Routine Filing Rejection (Regex Filtering)
Events matching any of the following patterns are discarded:
- **Trading Window & Share Certificates**: `closure of trading window`, `loss of share certificate`, `duplicate share certificate`.
- **Procedural Compliance**: `Regulation 74(5)`, `Regulation 7(3)`, `Regulation 40(9)`, `Regulation 39(3)`, `compliance certificate`.
- **Administrative Routine**: `scrutinizer's report`, `postal ballot notice`, `schedule of analyst meet`, `earnings call transcript`, `board meeting intimation to consider results`, `newspaper advertisement`, `change in registered office`, `change in company secretary`, `appointment of secretarial/cost auditor`.
- **Shareholder & Takeover Disclosures**: `SEBI SAST Regulations`, `Regulation 29(1)/(2)`, `Regulation 10(5)/(6)`, `Regulation 31(1)/(2)`.
- **Routine AGM/EGM Notices**: `BRSR report`, `Regulation 34(1) Annual Report`, `notice of AGM/EGM`, `extension of AGM`.
- **ESOPs & Stock Options**: `grant of options`, `allotment of equity shares under ESOP`.
- **Exchange Query Clarifications**: `clarification on price movement`, `spurt in volume`.

#### B. Stale News & Historical Results Detection
- Rejects articles mentioning old financial years (e.g., FY23, FY24) or published in prior years that resurface in search indexes:
  $$\text{Stale Match} = \text{Regex}(\verb|\b(q[1-4]\s*(of\s*)?fy\s*(23|24|2023|2024)|ended\s+march\s+31,?\s*2024)\b|)$$

#### C. Broker Recommendation Exclusion
- Discards articles whose primary content is a broker price target or analyst recommendation lacking an underlying corporate announcement:
  $$\text{Broker Pattern} = \text{Regex}(\verb|\b(raises target price|cuts target price|maintains buy|gives buy call|top shares to buy)\b|)$$

#### D. Pure Price Momentum Exclusion
- Discards articles reporting price movement without a verifiable operational catalyst:
  $$\text{Price Rally Pattern} = \text{Regex}(\verb|\b(shares rise 8%|stock rallies 5%|locked in upper circuit)\b|)$$
  *(Accepted only if accompanied by verified fundamental keywords: order win, patent, capex, earnings, M&A).*

#### E. Credit Rating Reaffirmation & ESG Filtering
- Rejects non-debt ESG ratings (sustainability ratings).
- Rejects routine annual credit rating surveillance/reaffirmations (`reaffirmed`, `reiterated`, `maintains rating`). **Only rating upgrades or downgrades are admitted.**

#### F. Early Filtering Boundary Rule (Noise Removal Only)
The early filter strictly removes obvious administrative noise and non-economic filings. It explicitly does **NOT** eliminate a candidate merely because it does not match a predefined template or rigid event category. Potentially important fundamental events (e.g., plant operationalization, capacity commissioning, strategic agreements, venture investments, disputes) survive this gate to be fully evaluated in the broad candidate pool.

---

### 3.2 Quality Gate 2: Entity Resolution & Role Verification (`engine/entity_mapper.py`)

#### A. Authoritative Ticker Resolution
- Matches company names, aliases, and exchange symbols against a curated universe of listed Indian companies.
- Maps entities to official NSE/BSE tickers (e.g., `HAL.NS`, `LT.NS`, `TCS.NS`).

#### B. Parent vs. Subsidiary Disambiguation
Explicit exclusion masks prevent confusing distinct listed entities under the same corporate umbrella:
- **ICICI Group**:
  - `ICICIBANK.NS` (Exclusions: `prudential`, `pru life`, `lombard`, `securities`, `amc`)
  - `ICICIPRULI.NS` (ICICI Prudential Life Insurance)
  - `ICICIGI.NS` (ICICI Lombard General Insurance)
- **Reliance Group**:
  - `RELIANCE.NS` (Exclusions: `jio financial`, `jiofin`, `reliance power`, `reliance infra`, `rpower`, `relinfra`)
  - `JIOFIN.NS` (Jio Financial Services)
  - `RPOWER.NS` (Reliance Power)
  - `RELINFRA.NS` (Reliance Infrastructure)
- **Tata Group**: Separate mapping for `TATAMOTORS.NS`, `TCS.NS`, `TATAPOWER.NS`, `TATASTEEL.NS`, `TATACONSUM.NS`, `TITAN.NS`.

#### C. Economic Beneficiary Role Resolution
Identifies whether the listed entity is the **economic beneficiary** or the counterparty:
- **Contractor / Supplier / Acquirer / Issuer** $\rightarrow$ Admitted.
- **Buyer / Customer / Awarding Authority** $\rightarrow$ Disqualified or adjusted (e.g., if a company issues a tender or awards an LOI to a vendor, the company itself is incurring capex/opex, not receiving contract revenue).

---

### 3.3 Quality Gate 3: Event Deduplication & Clustering (`engine/deduplicator.py`)
Multiple media outlets and exchange feeds often report the exact same corporate event with slightly differing headlines.
- Computes text similarity across token sets:
  $$\text{Similarity}(S_1, S_2) = \frac{|T_1 \cap T_2|}{|T_1 \cup T_2|} \quad (\text{Jaccard Token Distance})$$
- Events with $\text{Similarity} \ge 0.35$ sharing the same resolved company symbol are clustered into a single **Canonical Event**.
- Primary sources, URLs, and disclosure texts are merged, preserving the highest-fidelity exchange announcement.

---

## 4. Semantic Financial Quantification & Scale Contextualization

The module `engine/financial_context.py` extracts monetary figures and operating metrics from unstructured disclosures and computes their relative magnitude against the company's financial baseline.

### 4.1 Semantic Metric Extraction

| Metric Type | Regex Extraction Target | Example Extracted Text | Standardized Unit |
| :--- | :--- | :--- | :--- |
| **`ORDER_VALUE`** | Single amount or bounded range | *"secured ₹100–250 crore order"*, *"bags ₹903 Cr EPC contract"* | ₹ Cr |
| **`PROCUREMENT_PIPELINE`** | Multi-year sovereign outlay | *"Rs 1.45 lakh crore defence proposals approved by DAC"* | ₹ Cr ($= \text{Val} \times 100,000$) |
| **`OPERATING_UPDATE`** | Growth % & loss narrowing | *"revenue up 34%; net loss narrows to Rs 14 crore"* | YoY % / ₹ Cr |
| **`PAT` (Net Profit)** | Quarterly net profit/loss | *"PAT surges 45% to Rs 500 cr"*, *"net profit falls 26% to Rs 174 cr"* | ₹ Cr & YoY % |
| **`REVENUE`** | Top-line quarterly revenue | *"revenue increased 8.5% to Rs 3,927 crore"* | ₹ Cr & YoY % |
| **`CAPEX`** | Capital expenditure outlay | *"approves capex investment of Rs 1,200 cr for new plant"* | ₹ Cr |
| **`EQUITY_RAISE`** | Preferential issue / QIP / Warrants | *"preferential allotment of shares worth Rs 450 cr"* | ₹ Cr |
| **`PENALTY`** | Regulatory fine / Tax demand | *"tax demand / penalty of Rs 15.4 crore by SEBI"* | ₹ Cr |
| **`TOLL_REVENUE`** | Monthly concession collections | *"toll revenue collection of Rs 128 cr for August"* | ₹ Cr |

### 4.2 Company Scale Baseline Retrieval
The engine pulls and caches key baseline financial figures for each resolved ticker:
- **Annual Revenue ($\text{Rev}_{\text{annual}}$)** in ₹ Cr
- **EBITDA ($\text{EBITDA}_{\text{annual}}$)** in ₹ Cr
- **Market Capitalization ($\text{MCap}$)** in ₹ Cr

### 4.3 Relative Sizing Formulas

#### 1. Contract / Order Value Relative Sizing:
$$\text{Relative Order Ratio (\%)} = \left( \frac{\text{Order Value (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}} \right) \times 100$$

*Qualitative Materiality Interpretation:*
$$\text{Scale Category} = \begin{cases} 
\text{Transformational} & \text{if } \text{Ratio} \ge 20.0\% \quad (\text{Materiality Score} = 9.5) \\
\text{Substantial} & \text{if } 8.0\% \le \text{Ratio} < 20.0\% \quad (\text{Materiality Score} = 8.5) \\
\text{Meaningful} & \text{if } 2.5\% \le \text{Ratio} < 8.0\% \quad (\text{Materiality Score} = 7.5) \\
\text{Incremental} & \text{if } \text{Ratio} < 2.5\% \quad (\text{Materiality Score} = 6.5)
\end{cases}$$

#### 2. Range-Based Orders (e.g., ₹100–250 Cr):
$$\text{Ratio}_{\text{high}} = \left( \frac{\text{Range High (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}} \right) \times 100, \quad \text{Ratio}_{\text{low}} = \left( \frac{\text{Range Low (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}} \right) \times 100$$

#### 3. Capex Relative Sizing:
$$\text{Capex Intensity (\%)} = \left( \frac{\text{Capex Outlay (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}} \right) \times 100$$

#### 4. Regulatory Penalty Relative Sizing:
$$\text{Penalty Impact (\%)} = \left( \frac{\text{Penalty Amount (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}} \right) \times 100$$

---

## 5. Canonical Event Categories & Two-Pass Validation

The engine classifies each qualifying corporate event into one of **16 Canonical Event Types**:

```
1. ORDER_CONTRACT          5. REGULATORY_EVENT        9. STRATEGIC_DEAL         13. PRICING_EVENT
2. OPERATING_UPDATE        6. COMMODITY_EVENT        10. CAPACITY_EXPANSION     14. CUSTOMER_EVENT
3. FINANCIAL_RESULT        7. INDUSTRY_EVENT         11. PRODUCT_APPROVAL       15. FUNDING_DEBT_EVENT
4. GOVERNMENT_EVENT        8. ACQUISITION            12. MANAGEMENT_EVENT       16. OTHER_MATERIAL
```

### 5.1 Strict Binary Fundamental Directionality
- Every event is classified strictly as **`Positive`** or **`Negative`**.
- **Zero `Neutral`** and **Zero `Mixed`** classifications are permitted in the final Top News bulletin. Ambiguous developments that cannot be definitively classified are discarded.

### 5.2 Two-Pass Master Consistency & Fact-Checking Validation Gate

```
Raw Event Disclosures + Structured Extracted Facts
                       │
                       ▼
    [ PASS 1: SOURCE -> EVENT FIDELITY CHECK ]
    - Does the claimed event category match source text?
    - Are extracted financial figures present in the source?
    - Is the company the actual economic beneficiary?
                       │
             ┌─────────┴─────────┐
             │                   │
           PASS                FAIL ──► [ REJECT CANDIDATE ]
             │
             ▼
    [ PASS 2: EVENT -> ANALYSIS CONSISTENCY CHECK ]
    - Does 'Why it matters' contain forbidden boilerplate?
    - Is L1 lowest bidder correctly marked as contingent on LoA?
    - Is LOI correctly noted as pending definitive contract?
    - Does financial implication match correct financial concept?
    - Does fundamental direction match analytical commentary?
                       │
             ┌─────────┴─────────┐
             │                   │
           PASS                FAIL ──► [ REJECT CANDIDATE ]
             │
             ▼
    [ QUALIFIED RESEARCH CANDIDATE ]
```

#### Forbidden Boilerplate Phrase Blacklist
Analyses containing any of the following ungrounded clichés are automatically rejected:
- *"tangible operational tailwind"*
- *"order conversion/execution holds"*
- *"incremental revenue contribution can expand operating leverage"*
- *"execution bottlenecks, client concentration, or general broader market weakness"*
- *"strengthens executable order book and enhances forward revenue visibility"* (when not an order)
- *"unlocking immediate commercialization potential"*
- *"funds capex without incremental debt"* (when not equity raise)
- *"offering economies of scale once consolidation is finalized"*

---

## 6. Mathematical Scoring Models & Formulas

The intelligence engine employs six interrelated mathematical scoring models:

```
+---------------------------------------------------------------------------------------------------+
|                                  SIX CORE MATHEMATICAL MODELS                                     |
|                                                                                                   |
|  1. 10-Factor Research Importance Model ---------> Calculates RESEARCH_IMPORTANCE_SCORE (0-10)   |
|  2. Materiality Tier Assignment -----------------> Assigns Tier A, Tier B, or Tier C             |
|  3. Preliminary Technical & Stock Score ---------> Calculates PRELIMINARY_SCORE (0-100)          |
|  4. Priced-In Evaluation Model ------------------> Calculates PRICED_IN_SCORE (0-10)              |
|  5. 5-Dimension Fundamental Impact Matrix -------> Calculates OVERALL_FUNDAMENTAL_IMPACT (0-10)   |
|  6. Master Opportunity & Confidence Model -------> Calculates OPPORTUNITY_SCORE & CONFIDENCE      |
+---------------------------------------------------------------------------------------------------+
```

---

### 6.1 Model 1: 10-Factor Research Importance Model (`engine/candidate_engine.py`)

This model evaluates the fundamental importance of a candidate development across 10 sub-dimensions, outputting the composite **`RESEARCH_IMPORTANCE_SCORE`** ($S_{\text{res}} \in [0.0, 10.0]$):

$$\boxed{S_{\text{res}} = \sum_{i=1}^{10} w_i \cdot F_i}$$

Where the weights $w_i$ and factors $F_i \in [0.0, 10.0]$ are defined as:

| Factor ($F_i$) | Dimension Name | Weight ($w_i$) | Scoring Criteria & Determination Logic |
| :--- | :--- | :---: | :--- |
| $F_1$ | **Fundamental Materiality** | **0.25 (25%)** | $9.5$ if Order $\ge ₹1,000$ Cr; $8.8$ if $\ge ₹300$ Cr; $8.0$ if $\ge ₹100$ Cr; $8.5$ for Government/Equity events or Auditor resignation; otherwise base materiality score $\in [1.0, 10.0]$. |
| $F_2$ | **Financial Significance** | **0.15 (15%)** | $9.5$ if $\frac{\text{Order}}{\text{Rev}} \ge 15\%$; $8.5$ if $\ge 7\%$; $7.5$ if $\ge 2\%$; $8.0$ if Order $\ge ₹200$ Cr; $7.5$ if mentions EBITDA/margin/turnaround; otherwise $6.0$. |
| $F_3$ | **Strategic Significance** | **0.15 (15%)** | $9.0$ for Government policy, major Acquisition, or Product Approval; $8.5$ for Strategic Deals / Equity Infusion; $7.5$ for Orders / Capex; $6.5$ base. |
| $F_4$ | **Company Exposure** | **0.10 (10%)** | $10.0$ for direct contractor/issuer/acquirer/target; $9.5$ for primary operator; $8.5$ for direct read-through beneficiary; $8.0$ for indirect exposure. |
| $F_5$ | **Investor Relevance** | **0.10 (10%)** | $9.0$ for Order win, Government policy, Equity raise, Operating update; $8.5$ for Commodity shift, Management exit, Approval; $5.5$ if brief; $7.5$ base. |
| $F_6$ | **Quantifiability** | **0.10 (10%)** | $10.0$ if both absolute value (₹ Cr) and \% of revenue present; $9.0$ if single ₹ Cr or range present; $8.0$ if operational metrics (\%, MW, MT) present; $3.5$ if unquantified. |
| $F_7$ | **Evidence Strength** | **0.05 (5%)** | $10.0$ if verified via official NSE/BSE exchange filing; $9.0$ if top-tier press (Reuters, BS, ET, Mint); $7.5$ standard press; $5.0$ if text $< 80$ chars. |
| $F_8$ | **Source Quality** | **0.05 (5%)** | $10.0$ for primary exchange/regulatory disclosure; $9.0$ for major financial dailies; $7.5$ other media. |
| $F_9$ | **Novelty** | **0.03 (3%)** | $9.5$ for first-of-its-kind, LOI, major credit upgrade to 'AA', mandate; $8.5$ for regular operating updates; $8.0$ base. |
| $F_{10}$ | **Freshness** | **0.02 (2%)** | $9.5$ for intraday/immediate cycle disclosures ($< 24$ hours). |

---

### 6.2 Model 2: Materiality Tier Assignment Logic

Every candidate is evaluated and categorized into one of three strict tiers:

$$\text{Tier} = \begin{cases} 
\mathbf{Tier\ A} \quad (\text{Must Consider / High Conviction}) & \text{if } S_{\text{res}} \ge 8.2 \text{ OR meets Tier A Specific Rule} \\
\mathbf{Tier\ B} \quad (\text{Substantive Secondary}) & \text{if } S_{\text{res}} \ge 6.0 \text{ OR } (S_{\text{res}} \ge 5.5 \text{ and } (\text{Order Value} \text{ or } \frac{\text{Order}}{\text{Rev}} \text{ exists})) \\
\mathbf{Tier\ C} \quad (\text{Low Materiality}) & \text{otherwise}
\end{cases}$$

#### Tier A Specific Deterministic Override Rules:
A candidate is automatically elevated to **Tier A** if:
1. $\text{Event Type} = \text{ORDER\_CONTRACT}$ AND $\left(\frac{\text{Order}}{\text{Rev}} \ge 10.0\% \text{ OR } \text{Order Value} \ge ₹250\text{ Cr}\right)$
2. $\text{Event Type} = \text{MANAGEMENT\_EVENT}$ AND $\text{Direction} = \text{Negative}$ AND $\text{"auditor resignation" in text}$
3. $\text{Event Type} = \text{GOVERNMENT\_EVENT}$ AND $S_{\text{res}} \ge 7.8$
4. $\text{Event Type} = \text{OPERATING\_UPDATE}$ AND $\text{Disclosed Volume/Value} \ge ₹500\text{ Cr}$

---

### 6.3 Model 3: Preliminary Stock Scoring Model (0–100) (`engine/candidate_scanner.py`)

Used in the broader market scanner to rank candidate stocks from incoming technical and disclosure feeds:

$$\boxed{S_{\text{prelim}} = 0.25 S_{\text{news}} + 0.15 S_{\text{price\_mov}} + 0.15 S_{\text{vol\_abnorm}} + 0.20 S_{\text{catalyst}} + 0.10 S_{\text{sector}} + 0.05 S_{\text{mkt\_rel}} + 0.05 S_{\text{fresh}} + 0.05 S_{\text{conf}}}$$

#### Sub-Score Calculation Formulas:

1. **News Importance ($S_{\text{news}} \in [0, 100]$)**:
   $$S_{\text{news}} = \min\left(100.0, \; (\text{Materiality} \times 80.0) + (\text{Primary Bonus})\right)$$
   $$\text{Primary Bonus} = 20.0 \text{ (if official exchange filing)}, \quad 5.0 \text{ (if secondary news)}$$

2. **Price Movement ($S_{\text{price\_mov}} \in [0, 100]$)**:
   $$S_{\text{price\_mov}} = \min\left(100.0, \; |\text{Ret}_{\text{1D}}| \times 12.0 + 20.0\right)$$
   *(Rewards volatility and technical expansion on the event day).*

3. **Volume Abnormality Ratio ($S_{\text{vol\_abnorm}} \in [0, 100]$)**:
   $$\text{Volume Ratio } (V_R) = \frac{\text{Volume}_{\text{today}}}{\text{SMA}_{20}(\text{Volume})}$$
   $$S_{\text{vol\_abnorm}} = \begin{cases}
   100.0 & \text{if } V_R \ge 3.0 \\
   85.0  & \text{if } 2.0 \le V_R < 3.0 \\
   70.0  & \text{if } 1.5 \le V_R < 2.0 \\
   50.0  & \text{if } 1.0 \le V_R < 1.5 \\
   30.0  & \text{if } V_R < 1.0
   \end{cases}$$

4. **Catalyst Strength ($S_{\text{catalyst}} \in [0, 100]$)**:
   $$S_{\text{catalyst}} = \begin{cases}
   90.0 & \text{for Regulatory Actions, Order Wins, Earnings Results} \\
   80.0 & \text{for Acquisitions \& M\&A, Capital Actions} \\
   70.0 & \text{for Capacity Expansion, Capex, Management Changes} \\
   50.0 & \text{for General Market Disclosures}
   \end{cases}$$

5. **Sector Relevance ($S_{\text{sector}} \in [0, 100]$)**:
   $$S_{\text{sector}} = \begin{cases}
   85.0 & \text{if Sector } \in \{\text{Defense, Energy, Banking, Infra, Auto, Metals, Pharma}\} \\
   60.0 & \text{otherwise}
   \end{cases}$$

6. **Market Relevance ($S_{\text{mkt\_rel}} \in [0, 100]$)**:
   $$S_{\text{mkt\_rel}} = \min(100.0, \; 50.0 + \text{Sources Count} \times 15.0)$$

7. **News Freshness ($S_{\text{fresh}} \in [0, 100]$)**: $95.0$ if primary filing; $80.0$ if secondary.
8. **Data Confidence ($S_{\text{conf}} \in [0, 100]$)**: $90.0$ if valid OHLCV price history verified; $50.0$ otherwise.

---

### 6.4 Model 4: Priced-In Evaluation Model (0–10) (`engine/priced_in.py`)

Quantifies whether a catalyst has already been anticipated by the market ($0.0 = \text{Fresh surprise}$, $10.0 = \text{Extremely priced in / Sell-on-news risk}$):

$$\text{Base Score} = 4.0$$

#### Adjustment Factors:

1. **Price Run-Up Adjustments ($\Delta S_{\text{price}}$)**:
   - **If Sentiment is `POSITIVE`**:
     $$\Delta S_{\text{price}} = \begin{cases}
     +3.0 & \text{if } \text{Ret}_{\text{1M}} > 20.0\% \text{ or } \text{Ret}_{\text{5D}} > 10.0\% \quad (\text{Smart money pre-positioned}) \\
     +1.5 & \text{if } \text{Ret}_{\text{1M}} > 8.0\% \quad (\text{Partial discounting}) \\
     -2.0 & \text{if } \text{Ret}_{\text{1M}} < -5.0\% \quad (\text{Lagging stock / Genuine fresh surprise})
     \end{cases}$$
   - **If Sentiment is `NEGATIVE`**:
     $$\Delta S_{\text{price}} = \begin{cases}
     +3.0 & \text{if } \text{Ret}_{\text{1M}} < -15.0\% \text{ or } \text{Ret}_{\text{5D}} < -8.0\% \quad (\text{Bad news pre-discounted}) \\
     -2.0 & \text{if } \text{Ret}_{\text{1M}} > 5.0\% \quad (\text{Unpriced shock to strong stock})
     \end{cases}$$

2. **Valuation Stretch Adjustments ($\Delta S_{\text{val}}$)**:
   $$\Delta S_{\text{val}} = \begin{cases}
   +1.5 & \text{if Trailing P/E} > 65.0 \quad (\text{Zero margin of safety}) \\
   -1.5 & \text{if Trailing P/E} < 18.0 \quad (\text{Attractive valuation buffer})
   \end{cases}$$

3. **Volume Confirmation Adjustments ($\Delta S_{\text{vol}}$)**:
   $$\Delta S_{\text{vol}} = \begin{cases}
   +1.0 & \text{if } V_R > 2.5 \text{ and } |\text{Ret}_{\text{5D}}| > 8.0\% \quad (\text{Mature move volume surge}) \\
   0.0  & \text{otherwise}
   \end{cases}$$

$$\boxed{\text{Priced-In Score} = \min\left(10.0, \; \max\left(0.0, \; 4.0 + \Delta S_{\text{price}} + \Delta S_{\text{val}} + \Delta S_{\text{vol}}\right)\right)}$$

*Classification Categories:*
- $\le 3.0$: **Not Priced In** (High Surprise / Fresh Catalyst)
- $3.1 - 6.5$: **Partially Priced In** (Moderate Discounting)
- $\ge 6.6$: **Extremely Priced In** (Vulnerable to *"Sell on News"* Profit Booking)

---

### 6.5 Model 5: 5-Dimension Fundamental Impact Matrix (`engine/deep_analyzer.py`)

Evaluates the multi-dimensional business impact of a catalyst on a 0 to 10 scale:

$$\text{Base Scale} = \text{Materiality} \times 10.0$$

| Event Type | Revenue Impact ($I_{\text{rev}}$) | Profit Impact ($I_{\text{prof}}$) | Margin Impact ($I_{\text{margin}}$) | Cash Flow ($I_{\text{cf}}$) | Strategic Impact ($I_{\text{strat}}$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Contract / Order Win** | $\min(10, \text{Scale} \times 1.00)$ | $\min(10, \text{Scale} \times 0.85)$ | $\min(10, \text{Scale} \times 0.70)$ | $\min(10, \text{Scale} \times 0.75)$ | $\min(10, \text{Scale} \times 0.80)$ |
| **Earnings / Results** | $\min(10, \text{Scale} \times 0.90)$ | $\min(10, \text{Scale} \times 1.00)$ | $\min(10, \text{Scale} \times 0.95)$ | $\min(10, \text{Scale} \times 0.85)$ | $\min(10, \text{Scale} \times 0.70)$ |
| **Regulatory / Legal** | $\min(10, \text{Scale} \times 0.70)$ | $\min(10, \text{Scale} \times 0.95)$ | $\min(10, \text{Scale} \times 0.85)$ | $\min(10, \text{Scale} \times 0.90)$ | $\min(10, \text{Scale} \times 0.95)$ |
| **Acquisition / M&A** | $\min(10, \text{Scale} \times 0.95)$ | $\min(10, \text{Scale} \times 0.75)$ | $\min(10, \text{Scale} \times 0.70)$ | $\min(10, \text{Scale} \times 0.65)$ | $\min(10, \text{Scale} \times 1.00)$ |
| **General Catalyst** | $\min(10, \text{Scale} \times 0.60)$ | $\min(10, \text{Scale} \times 0.60)$ | $\min(10, \text{Scale} \times 0.60)$ | $\min(10, \text{Scale} \times 0.60)$ | $\min(10, \text{Scale} \times 0.60)$ |

#### Overall Fundamental Impact Score ($I_{\text{fund}} \in [0.0, 10.0]$):
$$\boxed{I_{\text{fund}} = 0.25 I_{\text{rev}} + 0.25 I_{\text{prof}} + 0.20 I_{\text{margin}} + 0.15 I_{\text{cf}} + 0.15 I_{\text{strat}}}$$

---

### 6.6 Model 6: Master Opportunity Score & Confidence Score (`engine/scorer.py`)

The Master Opportunity Score evaluates candidates for inclusion in deep-dive intelligence reports:

$$\boxed{S_{\text{opp}} = 0.25 S_{\text{news}} + 0.20 S_{\text{fund}} + 0.15 S_{\text{surprise}} + 0.15 S_{\text{setup}} + 0.10 S_{\text{hist}} + 0.05 S_{\text{vol}} + 0.05 S_{\text{mkt}} + 0.05 S_{\text{risk}}}$$

#### Sub-Component Definitions:
1. **News Materiality Score ($S_{\text{news}}$)**:
   $$S_{\text{news}} = \min(100.0, \; \text{Materiality} \times 100.0)$$
2. **Fundamental Impact Score ($S_{\text{fund}}$)**:
   $$S_{\text{fund}} = \min(100.0, \; I_{\text{fund}} \times 10.0)$$
3. **Surprise Score ($S_{\text{surprise}}$)**:
   $$S_{\text{surprise}} = \max(0.0, \; (10.0 - \text{Priced-In Score}) \times 10.0)$$
4. **Price Setup Score ($S_{\text{setup}}$)**:
   - Positive Sentiment:
     $$S_{\text{setup}} = \begin{cases}
     85.0 & \text{if } \text{Ret}_{\text{1D}} > 0.5\% \text{ and } \text{Ret}_{\text{1M}} < 15.0\% \quad (\text{Fresh breakout}) \\
     70.0 & \text{if } \text{Ret}_{\text{1D}} > 0.0\% \\
     40.0 & \text{if } \text{Ret}_{\text{1M}} > 30.0\% \quad (\text{Overextended}) \\
     55.0 & \text{otherwise}
     \end{cases}$$
   - Negative Sentiment:
     $$S_{\text{setup}} = \begin{cases}
     80.0 & \text{if } \text{Ret}_{\text{1D}} < -1.0\% \quad (\text{Downside confirmation}) \\
     60.0 & \text{otherwise}
     \end{cases}$$
5. **Historical Reaction Score ($S_{\text{hist}}$)**:
   $$S_{\text{hist}} = \begin{cases} 75.0 & \text{if historical catalyst precedent verified} \\ 50.0 & \text{if insufficient historical precedent} \end{cases}$$
6. **Volume Confirmation Score ($S_{\text{vol}}$)**:
   $$S_{\text{vol}} = \begin{cases} 95.0 & \text{if } V_R \ge 2.0 \\ 75.0 & \text{if } 1.3 \le V_R < 2.0 \\ 50.0 & \text{if } 0.8 \le V_R < 1.3 \\ 30.0 & \text{if } V_R < 0.8 \end{cases}$$
7. **Market Support Score ($S_{\text{mkt}}$)**:
   $$S_{\text{mkt}} = \begin{cases}
   80.0 & \text{if Bullish Regime \& Positive Sentiment OR Bearish Regime \& Negative Sentiment} \\
   40.0 & \text{if Regime conflicts with event sentiment} \\
   60.0 & \text{if Neutral Regime}
   \end{cases}$$
8. **Risk Score ($S_{\text{risk}}$)**:
   $$\text{Deductions} = (25.0 \text{ if } \text{Priced-In} \ge 7.5) + (20.0 \text{ if P/E} > 60) + (15.0 \text{ if } V_R < 0.7)$$
   $$S_{\text{risk}} = \max(10.0, \; 100.0 - \text{Deductions})$$

#### Valuation Trap & Crowded Trade Penalty Multiplier:
If a stock exhibits positive sentiment but suffers from both an extreme priced-in score and rich valuation:
$$\text{If } (\text{Sentiment} = \text{POSITIVE}) \land (\text{Priced-In} \ge 7.5) \land (\text{P/E} > 50.0) \implies \boxed{S_{\text{opp}} \leftarrow S_{\text{opp}} \times 0.80}$$

#### Confidence Score Calculation ($C_{\text{score}} \in [0, 95]$):
$$C_{\text{score}} = \min\left(95.0, \; 60.0 + (\text{Primary Source Bonus}) + (\text{Multiple Sources Bonus}) + (\text{Price Verification Bonus})\right)$$
$$\text{Primary Source Bonus} = 20.0 \text{ (if NSE/BSE filing)}, \quad \text{Multiple Sources Bonus} = 10.0 \text{ (if } \ge 2 \text{ sources)}, \quad \text{Price Bonus} = 10.0$$

---

### 6.7 Model 7: Actionability & Directionality Assessment (`engine/candidate_engine.py`)

Actionable does **not** mean price movement, sensational headlines, large numbers, or predefined brand names.  
Actionable means the event provides a **credible, sufficiently material fundamental development that could reasonably matter to an investor or analyst monitoring the stock**.

$$\text{Candidate Actionable} = \begin{cases}
\text{True} & \text{if Direction} \in \{\text{Positive, Negative}\} \land (\text{Tier A} \lor S_{\text{res}} \ge 8.0) \\
\text{True} & \text{if Direction} \in \{\text{Positive, Negative}\} \land (S_{\text{res}} \ge 6.0 \lor \text{Tier B}) \land \text{Event Type} \in \mathcal{A} \\
\text{True} & \text{if Direction} \in \{\text{Positive, Negative}\} \land (S_{\text{res}} \ge 5.5 \land \text{Quantified Financial Impact}) \\
\text{False} & \text{otherwise (Rejected as non-actionable or ambiguous)}
\end{cases}$$

Where the recognized actionable catalyst set $\mathcal{A}$ comprises:
$$\mathcal{A} = \left\{ \begin{array}{l}
\text{ORDER\_CONTRACT}, \; \text{CAPACITY\_EXPANSION}, \; \text{ACQUISITION}, \; \text{STRATEGIC\_DEAL}, \\
\text{PRODUCT\_APPROVAL}, \; \text{REGULATORY\_EVENT}, \; \text{OPERATING\_UPDATE}, \; \text{GOVERNMENT\_EVENT}, \\
\text{COMMODITY\_EVENT}, \; \text{FUNDING\_EQUITY}, \; \text{FUNDING\_DEBT\_EVENT}, \; \text{MANAGEMENT\_EVENT}, \\
\text{PRICING\_EVENT}, \; \text{CUSTOMER\_EVENT}, \; \text{FINANCIAL\_RESULT}
\end{array} \right\}$$

#### Strict Binary Directionality Requirement:
- If an event is ambiguous or has mixed directional implications, it is strictly **rejected**.
- Final published classification must only be **`Positive`** or **`Negative`**.
- Zero Neutral, Zero Mixed, and Zero Ambiguous events are permitted in the final report.

---

## 7. Complete Stock Selection & Dynamic Ranking Workflow

The engine follows an open, merit-based candidate funnel optimizing for **actionability and fundamental importance** rather than an arbitrary fixed count:

```
                  RAW DISCLOSURE FEED (Exchange Announcements / Financial Press)
                                           │
                                           ▼
                                 [ 1. BASIC NOISE FILTER ]
                                 Remove routine compliance, stale news, administrative filings.
                                 Preserve all potentially important corporate developments.
                                           │
                                           ▼
                              [ 2. ENTITY & ROLE VALIDATION ]
                              Resolve listed entity (.NS / .BO) and verify economic role
                              (Contractor/Issuer vs Awarding Customer/Authority).
                                           │
                                           ▼
                              [ 3. CANONICAL EVENT CLUSTERING ]
                              Group multi-source disclosures into distinct canonical clusters.
                                           │
                                           ▼
                      [ 4. BROAD FUNDAMENTAL CANDIDATE EVALUATION ]
                      Synthesize event intelligence for ALL canonical events.
                      Strict Directionality Check: Positive or Negative only.
                      Score with 10-Factor Research Model & assign Materiality Tiers.
                      (No premature dropping of Tier C prior to evaluation).
                                           │
                                           ▼
                         [ 5. ACTIONABILITY & MATERIALITY ASSESSMENT ]
                         Identify genuine operational catalysts via Model 7.
                         Separate primary actionable candidates from secondary pool.
                                           │
                                           ▼
                     [ 6. DYNAMIC CANDIDATE RANKING (MIN TARGET 4–5) ]
                     - Show ALL genuinely actionable stocks (e.g. 5, 8, 12, 15).
                     - If actionable < 4: Evaluate qualified secondary candidates
                       without injecting weak noise (Quality beats Minimum).
                     - Never artificially cut down to 5.
                                           │
                                           ▼
                     [ 7. CLOSING PRICE RETRIEVAL & ASCENDING SORT ]
                     - Retrieve date-specific closing prices on or before requested date.
                     - Omit unlisted entities (DRHPs / pre-IPO filings).
                     - Sort ascending: LOWEST CLOSING PRICE -> HIGHEST CLOSING PRICE.
                     - Zero influence of stock price on fundamental selection.
                                           │
                                           ▼
                         [ 8. FINAL ACTIONABLE "TOP NEWS" BULLETIN ]
                         Display 7-stage diagnostics & publish Sharekhan-style report.
```

### 7.1 Dynamic Stock Count & Minimum Target Principles:
1. **No Fixed Cap**:
   - The final FNA does NOT have a hardcoded number such as exactly 3 or exactly 5 stocks.
   - If 5 genuinely actionable stocks exist $\rightarrow$ show all 5.
   - If 8 genuinely actionable stocks exist $\rightarrow$ show all 8.
   - If 12 or 15 genuinely actionable stocks exist $\rightarrow$ show all 12 or 15 without artificially truncating the list.
2. **Minimum Target of 4–5 Stocks**:
   - The engine uses 4–5 stocks as a minimum target, not as a hard limit.
   - If only 2 actionable stocks exist initially, the engine evaluates qualified secondary candidates (Tier B with verified commercial categories) to supplement up to 4.
   - **Quality Beats Minimum**: If only 2 or 3 genuinely actionable stocks exist after evaluating the pool, the engine outputs 2 or 3 rather than inventing weak or irrelevant stories simply to reach 5.

### 7.2 Best-Effort Price Fetch & Gate Removal (`engine/fna_pipeline.py`):
Once the final actionable stock set has been determined strictly on fundamental merit:
1. Fetch closing prices on a best-effort basis for the requested date.
2. **Zero-Omission Principle**: Candidates passing fundamental scoring and materiality checks are **never omitted** if price lookup fails or if the entity is unlisted / recently listed. Price lookups are non-blocking and purely auxiliary.

### 7.3 Simplified Sharekhan-Style Flowing Prose Output Format:
Matching actual Sharekhan Daily FNA bulletins, the output eschews multi-section boilerplate templates (`What happened:`, `Why it matters:`, etc.) in favor of clean, institutional flowing prose:
1. **Header Format**:
   $$\text{Company Name} \text{ — } \text{Positive / Negative}$$
   - **No price shown in the header** — just the clean company name and the directional tag at the end.
2. **Narrative Flow**:
   - **2 to 5 sentences per item**: Natural, institutional journalistic prose.
   - **Zero section headers**: Mechanics, commercial scale, and financial implications are folded directly into the sentences.
   - **Factual & Quantified**: Deal values (₹ Cr), execution horizons, milestone billing, and balance sheet impacts are embedded organically.
3. **Multi-Company Policy & Regulatory Events**:
   - Captures sector-wide policy moves (RBI, SEBI, NPCI circulars, duty/tariff changes).
   - Generates headline, flowing policy summary, and a bulleted list of `Key Beneficiaries / Impacted` stocks.
4. **Standalone Macro Triggers**:
   - One-liner macro trigger + affected sector + directional sentiment (e.g. Brent crude spikes, US 10Y yield surges).

Example Output:
```text
1. Mazagon Dock Shipbuilders Ltd — Positive
   Mazagon Dock Shipbuilders has secured a major offshore pipeline contract valued at ₹1,486 crore from ONGC. Securing this contract expands the executable order book and provides firm revenue visibility for execution over the contract delivery schedule. The addition strengthens its medium-term pipeline, with milestone billing minimizing working capital strain.

------------------------------------------------------------

2. Neogen Chemicals Ltd — Positive
   Neogen Chemicals has entered into a strategic joint venture with MU Ionic Solutions for electric vehicle battery electrolyte manufacturing. Entering into this agreement combines technical capabilities and market access to address target automotive and energy storage segments. Commercial realization will commence upon capitalization and operational ramp-up of the planned manufacturing facility.

------------------------------------------------------------

3. [POLICY & REGULATORY] NPCI and RBI mandate 1.1% interchange fee on UPI merchant transactions — Positive
   The Reserve Bank of India and NPCI have mandated a 1.1% interchange fee on merchant transactions conducted via prepaid payment instruments above ₹2,000. This measure enhances unit economics and interchange revenue for digital payment aggregators and acquiring banks.

   Key Beneficiaries / Impacted:
   • PAYTM (One97 Communications Ltd) — Positive
   • SBIN (State Bank of India) — Positive
   • HDFCBANK (HDFC Bank Ltd) — Positive

------------------------------------------------------------

4. [MACRO CONTEXT] US 10-Year Treasury Yield surges 18 bps to 4.38% — Negative for Emerging Market Equities
```

---

## 8. Second-Order Macro Effects & Market Context

The engine evaluates economic ripple effects across supply chains and competitive landscapes (`engine/second_order.py`).

### 8.1 Macro Ripple Matrix

| Macro / Sector Event | Direct Beneficiaries | Second-Order Supply Chain Beneficiaries | Impacted Detriments (Squeezed Margins) | Economic Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Crude Oil Surge** | Upstream E&P (`ONGC.NS`, `OIL.NS`) | Renewable Energy (`IREDA.NS`, `SUZLON.NS`, `TATAPOWER.NS`) | Aviation (`INDIGO.NS`), Paints (`ASIANPAINT.NS`, `BERGEPAINT.NS`), Tyres (`MRF.NS`, `APOLLOTYRE.NS`) | Upstream realization expands; ATF (40% airline cost) and crude petrochemical derivatives inflate downstream input costs. |
| **Defense & Infra Capex** | Aerospace & Defense (`HAL.NS`, `BEL.NS`, `MAZDOCK.NS`) | Capital Goods & Cables (`LT.NS`, `BHEL.NS`, `POLYCAB.NS`), Metals (`TATASTEEL.NS`) | Fiscal Deficit Sensitive Sovereign Debt | Direct domestic order book expansion under *Atmanirbhar Bharat*; subcontracting and electrification demand surges. |
| **Power & AI Electrification** | Baseload Power (`NTPC.NS`, `TATAPOWER.NS`, `POWERGRID.NS`) | Electrical Equipment (`SIEMENS.NS`, `ABB.NS`, `CGPOWER.NS`) | Energy-Intensive Smelters | High-voltage transformer demand surges to support data center compute and industrial load. |
| **Commercial Vehicle Demand** | CV Manufacturers (`TATAMOTORS.NS`, `ASHOKLEY.NS`) | Auto Ancillaries & Castings (`BHARATFORG.NS`, `MOTHERSON.NS`) | Rail Freight Substitution (`CONCOR.NS`) | Component production runs expand plant utilization; road freight intensifies competition against rail. |

### 8.2 Competitor Displacement Analysis
When a major corporate event occurs, the engine maps peer implications:
- **Major Order Capture**: Locks in market capacity and shuts out direct peers from that bidding pool.
- **Regulatory Scrutiny / Ban**: Creates immediate market share migration opportunities for direct rivals (e.g., peer bank or pharma competitors).
- **Earnings Margin Outperformance**: Serves as an operational bellwether for sector peers.

---

## 9. Master Reference Formula Table

| Mathematical Model / Metric | Exact Mathematical Formula | Output Range | Key Interpretation |
| :--- | :--- | :---: | :--- |
| **Relative Order Sizing** | $\text{Ratio} = \left(\frac{\text{Order (₹ Cr)}}{\text{Annual Revenue (₹ Cr)}}\right) \times 100$ | $0\% - \infty$ | $\ge 20\%$ Transformational, $\ge 8\%$ Substantial, $\ge 2.5\%$ Meaningful |
| **Volume Ratio ($V_R$)** | $V_R = \frac{\text{Volume}_{\text{today}}}{\text{SMA}_{20}(\text{Volume})}$ | $0.0 - \infty$ | $V_R \ge 2.0\text{x}$ signals institutional volume accumulation |
| **10-Factor Research Score** | $S_{\text{res}} = \sum_{i=1}^{10} w_i \cdot F_i$ | $0.0 - 10.0$ | Composite score evaluating fundamental research importance |
| **Materiality Tiers** | $\text{Tier A} \iff S_{\text{res}} \ge 8.2 \lor \text{Override}; \; \text{Tier B} \iff S_{\text{res}} \ge 6.0 \lor (S_{\text{res}} \ge 5.5 \land \text{Metric})$ | Categorical | Tier A (High Conviction), Tier B (Substantive), Tier C (Low Materiality) |
| **Actionability Filter** | $\text{Actionable} \iff \text{Direction} \in \{\text{Pos}, \text{Neg}\} \land (S_{\text{res}} \ge 6.0 \lor \text{Tier B}) \land \text{Type} \in \mathcal{A}$ | Boolean | Only verified operational catalysts with confirmed direction qualify |
| **Dynamic Stock Selection** | $\text{Count} = \max(\min(\text{Actionable}, \text{Ceiling}), \text{MinTarget})$ subject to quality | Variable ($3-15$) | 4–5 min target; shows all actionable stocks without artificial 5-item cap |
| **Closing Price Sorting** | $\text{Sorted} = \text{OrderBy}(\text{SelectedStocks}, \; \text{key}=\text{ClosingPrice})$ | Ascending (₹) | Lowest closing price to highest closing price; zero selection influence |
| **Priced-In Score** | $S_{\text{priced\_in}} = \min(10.0, \max(0.0, 4.0 + \Delta_{\text{price}} + \Delta_{\text{val}} + \Delta_{\text{vol}}))$ | $0.0 - 10.0$ | $\le 3.0$ Fresh surprise, $\ge 6.6$ Sell-on-news risk |
| **Fundamental Impact** | $I_{\text{fund}} = 0.25 I_{\text{rev}} + 0.25 I_{\text{prof}} + 0.20 I_{\text{margin}} + 0.15 I_{\text{cf}} + 0.15 I_{\text{strat}}$ | $0.0 - 10.0$ | Comprehensive 5-dimension fundamental business impact |
| **Preliminary Score** | $S_{\text{prelim}} = \sum_{j=1}^{8} w_j \cdot C_j$ | $0.0 - 100.0$ | $\ge 58.0$ qualifies stock for deep quantitative dive |
| **Master Opportunity Score** | $S_{\text{opp}} = 0.25 S_{\text{news}} + 0.20 S_{\text{fund}} + 0.15 S_{\text{surprise}} + 0.15 S_{\text{setup}} + 0.10 S_{\text{hist}} + 0.05 S_{\text{vol}} + 0.05 S_{\text{mkt}} + 0.05 S_{\text{risk}}$ | $0.0 - 100.0$ | Multi-factor conviction score for long/short thesis generation |
| **Valuation Trap Penalty** | $S_{\text{opp}} \leftarrow S_{\text{opp}} \times 0.80$ | Multiplier | Applied when Positive sentiment $\land \text{Priced-In} \ge 7.5 \land \text{P/E} > 50$ |
| **Confidence Score** | $C_{\text{score}} = \min(95.0, 60.0 + \text{Bonuses})$ | $0.0 - 95.0$ | Verification confidence based on primary exchange source & data validity |

---

## 10. Transparent 7-Stage Diagnostic Funnel & Verification

Every execution of the FNA engine prints full diagnostic metrics across the candidate pipeline:

```text
============================================================
        RESEARCH EXECUTION DIAGNOSTICS
============================================================
Requested Research Date: YYYY-MM-DD (Cutoff: HH:MM:SS IST)
Candidates Retrieved: [N_1]
Surviving Initial Materiality: [N_2]
Validated Entities: [N_3]
Canonical Events: [N_4]
Fundamental Candidates Evaluated: [N_5]
Actionable Candidates: [N_6]
Final TOP NEWS: [N_7]
============================================================
```

### Funnel Stage Definitions:
1. **Candidates Retrieved**: Total raw developments ingested from exchange feeds (NSE/BSE) and 8+ financial press sources for the target date.
2. **Surviving Initial Materiality**: Developments passing the early basic noise filter (administrative and routine compliance disclosures removed).
3. **Validated Entities**: Events successfully resolved to a listed NSE/BSE corporate entity and verified as the genuine economic beneficiary.
4. **Canonical Events**: Multi-source duplicates clustered into unique corporate developments via token-similarity deduplication.
5. **Fundamental Candidates Evaluated**: Canonical candidates passing two-pass consistency validation, synthesized, and scored via the 10-Factor Research Model.
6. **Actionable Candidates**: Candidates meeting Model 7 criteria with verified directional fundamental catalysts (`Positive` or `Negative` only).
7. **Final TOP NEWS**: Final traded stocks selected by dynamic ranking, validated for traded closing prices, and sorted ascending from lowest to highest closing price.

---

## 11. Production Polish & Real-World Alignment Upgrades

To ensure complete parity with institutional intelligence desks (e.g. Sharekhan's daily Fundamental News & Analysis bulletin), the engine incorporates five specialized real-world analytical enhancements:

### 11.1 Cross-Day Deduplication & Persistent Fingerprint Store
- **Problem**: Stale corporate developments (e.g. an acquisition announcement from day $T-1$) can resurface on day $T$ when follow-up opinion articles are published, displacing genuinely new corporate developments.
- **Solution**: The engine persists all surfaced developments into an SQLite store (`fna_surfaced_events`) indexed by:
  $$\text{Fingerprint} = \text{SHA256}(\text{Symbol} \parallel \text{EventType} \parallel \text{SignificantTokens})$$
- **Recurrence Logic**: On day $T$, candidate events are checked against the prior 2 trading days. If token Jaccard similarity exceeds $35\%$ and no material delta (e.g. $\ge 15\%$ contract value change, regulatory clearance) is found, the candidate is omitted with a logged diagnostic reason:
  $$J(\mathcal{T}_{\text{cand}}, \mathcal{T}_{\text{surfaced}}) = \frac{|\mathcal{T}_{\text{cand}} \cap \mathcal{T}_{\text{surfaced}}|}{|\mathcal{T}_{\text{cand}} \cup \mathcal{T}_{\text{surfaced}}|} \ge 0.35 \implies \text{Omitted as Stale Recurrence}$$

### 11.2 End-to-End Company Tracing (`--trace-company "<Name>"`)
- **Diagnostic Transparency**: Enables analysts to trace any specific corporate entity across all 6 pipeline stages:
  1. *Ingestion*: Matched raw news and regulatory filings with exact timestamps and source feeds.
  2. *Noise Filter*: Survival status and specific rejection rationale if discarded.
  3. *Entity Resolution*: Assigned NSE/BSE symbol, canonical sector, and operational beneficiary role.
  4. *Clustering*: Multi-source canonical cluster assignment and deduplication grouping.
  5. *Scoring & Actionability*: Exact 10-factor score breakdown, materiality tier, and actionability justification.
  6. *Final Selection*: Inclusion in TOP NEWS or threshold ranking cut status.
- **Robust Entity Matching**: Employs symbol mapping, alias resolution, token subset verification, and sequence similarity fallback ($\ge 0.75$ ratio), guaranteeing accurate diagnosis regardless of spelling variations (e.g., *Mazagaon Dock* vs. *Mazagon Dock*).

### 11.3 Global Macro & Domestic Market Commentary
- **Candidate Type**: `MACRO_COMMENTARY`
- **Mechanism**: Ingests macroeconomic and geopolitical developments independently (crude oil fluctuations, central bank policy rate trajectories, foreign institutional sentiment, and GIFT Nifty opening indicators).
- **Prose Delivery**: Generates a unified 2–4 sentence narrative matching Sharekhan's introductory tone. Formatted cleanly with zero stock tickers and zero directional sentiment tags.

### 11.4 Sector Cause-and-Effect Causal Transmission Engine
- **Candidate Type**: `SECTOR_CAUSAL_COMMENTARY`
- **Mechanism**: Evaluates second-order economic ripple effects from macroeconomic and fiscal policies:
  - *US Interest Rate Trajectory* $\longrightarrow$ North American enterprise IT spend moderation $\longrightarrow$ Elongated deal conversion cycles for Indian Tier-1 IT services.
  - *Windfall Tax (SAED) Cuts* $\longrightarrow$ Elimination of export levy friction $\longrightarrow$ Margin expansion across domestic refiners and upstream producers.
  - *Crude Oil Spikes* $\longrightarrow$ Input cost inflation in ATF and petrochemical monomers $\longrightarrow$ Near-term margin friction for domestic airlines and paint manufacturers.
- **Human Oversight**: Every generated causal chain is transparently tagged with `[Requires Review: 2nd-order transmission]`.

### 11.5 Steep Log-Scale Contract Value & Strategic Significance Model
- **Scale Hierarchy**: Prevents mega infrastructure and defense agreements from being ranked alongside routine operational contracts:
  - $\ge ₹10,000\text{ Cr}$: $\text{Materiality} = 10.0$, $\text{FinSig} = 10.0$, $\text{StratSig} = 9.8$, $\text{DealScaleBoost} = +0.85$
  - $\ge ₹2,500\text{ Cr}$: $\text{Materiality} = 9.8$, $\text{FinSig} = 9.5$, $\text{StratSig} = 9.0$, $\text{DealScaleBoost} = +0.60$
  - $\ge ₹1,000\text{ Cr}$: $\text{Materiality} = 9.2$, $\text{FinSig} = 9.0$, $\text{DealScaleBoost} = +0.40$
  - $\ge ₹300\text{ Cr}$: $\text{Materiality} = 8.5$, $\text{FinSig} = 8.2$, $\text{DealScaleBoost} = +0.20$
  - $< ₹100\text{ Cr}$: $\text{FinSig} = 6.2$, $\text{DealScaleBoost} = -0.30$ (routine order discount unless $\ge 15\%$ revenue)
- **Outcome**: Mega agreements (such as Mazagon Dock's ₹27,000 Cr shipbuilding MoU) decisively outrank routine smaller ₹63 Cr domestic orders.
