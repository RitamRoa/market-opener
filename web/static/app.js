// Indian Stock Market Intelligence Engine — Client Controller

let currentScanData = null;

document.addEventListener("DOMContentLoaded", () => {
  loadMarketContext();
  loadLatestScan();

  // Enter key trigger for search box
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        const query = searchInput.value.trim();
        if (query) {
          openStockModal(query);
        }
      }
    });
  }
});

// Load real-time benchmark context
async function loadMarketContext() {
  try {
    const res = await fetch("/api/market-context");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("regimePill").innerText = data.regime || "Neutral";
    
    // Nifty
    updateMacroMetric("niftyPrice", "niftyChange", data.nifty?.price, data.nifty?.change_pct);
    // Bank Nifty
    updateMacroMetric("bankPrice", "bankChange", data.bank_nifty?.price, data.bank_nifty?.change_pct);
    
    // VIX
    const vixVal = data.vix?.price || 14.0;
    const vixElem = document.getElementById("vixPrice");
    if (vixElem) {
      vixElem.innerText = vixVal.toFixed(2);
      vixElem.className = vixVal >= 18 ? "neg" : "pos";
    }

    // Brent
    updateMacroMetric("brentPrice", "brentChange", data.brent?.price, data.brent?.change_pct, "$");
    // Gold
    updateMacroMetric("goldPrice", "goldChange", data.gold?.price, data.gold?.change_pct, "$");
    
    // USDINR
    const usdinrElem = document.getElementById("usdinrPrice");
    if (usdinrElem && data.usdinr?.price) {
      usdinrElem.innerText = `₹${data.usdinr.price.toFixed(2)}`;
    }

    // Drivers
    const driversElem = document.getElementById("marketDriversText");
    if (driversElem && data.drivers && data.drivers.length > 0) {
      driversElem.innerText = data.drivers.join(" • ");
    }
  } catch (err) {
    console.error("Error loading market context:", err);
  }
}

function updateMacroMetric(priceId, changeId, price, changePct, prefix = "₹") {
  const pElem = document.getElementById(priceId);
  const cElem = document.getElementById(changeId);
  if (!pElem || !cElem || price === undefined) return;

  pElem.innerText = `${prefix}${price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  if (changePct !== undefined) {
    const isPos = changePct >= 0;
    cElem.innerText = `${isPos ? '+' : ''}${changePct.toFixed(2)}%`;
    cElem.className = isPos ? "pos" : "neg";
  }
}

// Load cached scan run
async function loadLatestScan() {
  try {
    const res = await fetch("/api/latest");
    if (res.status === 404) {
      // Prompt initial scan
      document.getElementById("positivesTableBody").innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px;">
            No scan history found. Click <strong>"Run Market Scan"</strong> to launch the autonomous engine.
          </td>
        </tr>
      `;
      document.getElementById("negativesTableBody").innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px;">
            No scan history found.
          </td>
        </tr>
      `;
      return;
    }

    const data = await res.json();
    currentScanData = data.summary;

    document.getElementById("lastUpdated").innerText = `Last Scanned: ${data.timestamp || ""}`;
    document.getElementById("candidatesCount").innerText = data.summary?.all_candidates_count || "--";
    document.getElementById("analyzedCount").innerText = data.summary?.analyzed_count || "--";

    renderOpportunitiesTable("positivesTableBody", data.summary?.positives || [], true);
    renderOpportunitiesTable("negativesTableBody", data.summary?.negatives || [], false);
    renderWatchlist(data.summary?.watchlist || []);
  } catch (err) {
    console.error("Error loading latest scan:", err);
  }
}

function renderOpportunitiesTable(elemId, stocks, isPositive) {
  const tbody = document.getElementById(elemId);
  if (!tbody) return;

  if (!stocks || stocks.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-dim); padding: 30px;">
          No high-conviction opportunities matching strict criteria in current scan.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = stocks.map((s, idx) => {
    const rank = idx + 1;
    const opp = Math.round(s.opportunity_score || 50);
    const conf = Math.round(s.confidence_score || 50);
    const pricedIn = s.priced_in_score !== undefined ? `${s.priced_in_score}/10` : "N/A";
    const ret1d = s.ret_1d || 0;
    const retClass = ret1d >= 0 ? "pos" : "neg";
    const retStr = `${ret1d >= 0 ? '+' : ''}${ret1d.toFixed(2)}%`;
    const priceStr = `₹${(s.current_price || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

    let badgeClass = "score-high";
    if (opp < 65) badgeClass = "score-mid";
    if (!isPositive) badgeClass = "score-risk";

    return `
      <tr>
        <td style="font-weight: 700; color: var(--text-dim);">${rank}</td>
        <td>
          <div class="stock-cell">
            <span class="stock-name">${s.company}</span>
            <span class="stock-sym">${s.symbol} • ${s.sector}</span>
          </div>
        </td>
        <td>
          <span style="font-weight: 600; color: #ffffff;">${s.event_type || 'Event'}</span>
        </td>
        <td>
          <div>${priceStr}</div>
          <div class="${retClass}" style="font-size: 0.75rem;">${retStr}</div>
        </td>
        <td>
          <span style="font-weight: 600;">${s.volume_ratio || 1.0}x</span>
        </td>
        <td>
          <span style="color: var(--accent-amber); font-weight: 600;">${pricedIn}</span>
        </td>
        <td>
          <span class="score-badge ${badgeClass}">${opp}</span>
        </td>
        <td>
          <span style="color: var(--accent-cyan); font-weight: 700;">${conf}%</span>
        </td>
        <td style="text-align: right;">
          <button class="btn-details" onclick="openStockModal('${s.symbol}')">Analyze</button>
        </td>
      </tr>
    `;
  }).join("");
}

function renderWatchlist(watchlist) {
  const container = document.getElementById("watchlistContainer");
  if (!container) return;

  if (!watchlist || watchlist.length === 0) {
    container.innerHTML = `<p style="color: var(--text-dim);">No active watch items.</p>`;
    return;
  }

  container.innerHTML = watchlist.slice(0, 5).map(w => `
    <div class="watch-item">
      <div style="font-weight: 700; color: #ffffff;">${w.company} (${w.symbol})</div>
      <div style="color: var(--text-muted); font-size: 0.8rem; margin-top: 2px;">
        ${w.main_event || w.event_type}
      </div>
      <div style="color: var(--accent-amber); font-size: 0.75rem; margin-top: 4px;">
        * ${w.watchlist_reason || 'Awaiting volume confirmation and multi-broker verification.'}
      </div>
    </div>
  `).join("");
}

// Trigger background market scan
async function triggerScan() {
  const btn = document.getElementById("btnScan");
  const icon = document.getElementById("scanIcon");
  const text = document.getElementById("scanBtnText");

  btn.disabled = true;
  icon.innerHTML = `<div class="spinner"></div>`;
  text.innerText = "Scanning Market...";

  try {
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();

    // Poll status every 2.5 seconds
    const interval = setInterval(async () => {
      const pollRes = await fetch("/api/scan/status");
      const pollData = await pollRes.json();

      if (!pollData.is_scanning) {
        clearInterval(interval);
        btn.disabled = false;
        icon.innerText = "⚡";
        text.innerText = "Run Market Scan";
        // Refresh tables and context
        loadMarketContext();
        loadLatestScan();
      } else {
        text.innerText = pollData.progress || "Analyzing...";
      }
    }, 2500);

  } catch (err) {
    console.error("Scan trigger error:", err);
    btn.disabled = false;
    icon.innerText = "⚡";
    text.innerText = "Run Market Scan";
  }
}

// Stock Deep Dive Modal
async function openStockModal(symbol) {
  const modal = document.getElementById("stockModal");
  modal.classList.add("active");

  // Check if stock is already present in currentScanData for instant rendering
  let preloaded = null;
  if (currentScanData) {
    const all = [...(currentScanData.positives || []), ...(currentScanData.negatives || []), ...(currentScanData.watchlist || [])];
    preloaded = all.find(s => s.symbol === symbol || s.symbol === `${symbol}.NS`);
  }

  if (preloaded) {
    populateModalWithData(preloaded);
  } else {
    // Show loading placeholders
    document.getElementById("modalStockName").innerText = "Analyzing Equity...";
    document.getElementById("modalStockSym").innerText = symbol;
    document.getElementById("modalEventTitle").innerText = "Querying live exchange and yfinance feeds...";
  }

  try {
    const res = await fetch(`/api/stocks/${encodeURIComponent(symbol)}`);
    if (!res.ok) {
      if (!preloaded) throw new Error("Failed to load stock");
      return;
    }
    const data = await res.json();
    populateModalWithData(data);
  } catch (err) {
    console.error("Error opening modal:", err);
    if (!preloaded) {
      document.getElementById("modalStockName").innerText = "Data Retrieval Failed";
      document.getElementById("modalEventTitle").innerText = "Could not fetch ticker information.";
    }
  }
}

function populateModalWithData(data) {
  document.getElementById("modalStockName").innerText = data.company || data.symbol;
  document.getElementById("modalStockSym").innerText = data.symbol;
  document.getElementById("modalSectorPill").innerText = data.sector || "Equities";
  
  document.getElementById("modalPrice").innerText = `₹${(data.current_price || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  const ret1d = data.ret_1d || 0;
  const retElem = document.getElementById("modalPriceChange");
  retElem.innerText = `${ret1d >= 0 ? '+' : ''}${ret1d.toFixed(2)}% 1D`;
  retElem.className = ret1d >= 0 ? "pos" : "neg";

  document.getElementById("modalOppScore").innerText = `${Math.round(data.opportunity_score || 50)}/100`;
  document.getElementById("modalConfScore").innerText = `${Math.round(data.confidence_score || 50)}/100`;
  document.getElementById("modalPricedInScore").innerText = `${data.priced_in_score || 5}/10`;
  document.getElementById("modalVolMultiple").innerText = `${data.volume_ratio || 1.0}x`;

  document.getElementById("modalEventTitle").innerText = data.main_event || data.event_type;
  document.getElementById("modalEventSummary").innerText = data.summary || "Catalyst analyzed via proprietary zero-API-key pipeline.";
  document.getElementById("modalSources").innerHTML = `<strong>Verified Sources:</strong> ${(data.sources || ['Exchange Filings']).join(', ')}`;

  // Bull & Bear Cases
  document.getElementById("modalBullCase").innerText = data.bull_case || "Thesis pending additional confirmation.";
  document.getElementById("modalBearCase").innerText = data.bear_case || "Risks include broader market sentiment and macro headwinds.";

  // Fundamental Dimensions
  const fund = data.fundamental_impact || {};
  document.getElementById("modalDimRev").innerText = `${fund.revenue_impact || 5}/10`;
  document.getElementById("modalDimProf").innerText = `${fund.profit_impact || 5}/10`;
  document.getElementById("modalDimMargin").innerText = `${fund.margin_impact || 5}/10`;
  document.getElementById("modalDimCash").innerText = `${fund.cashflow_impact || 5}/10`;
  document.getElementById("modalDimStrat").innerText = `${fund.strategic_impact || 5}/10`;

  // Multiples
  const fin = data.deep_financials || {};
  document.getElementById("modalPE").innerText = fin.pe_ratio ? `${Number(fin.pe_ratio).toFixed(1)}x` : "N/A";
  document.getElementById("modalFwdPE").innerText = fin.forward_pe ? `${Number(fin.forward_pe).toFixed(1)}x` : "N/A";
  document.getElementById("modalPB").innerText = fin.pb_ratio ? `${Number(fin.pb_ratio).toFixed(2)}x` : "N/A";
  document.getElementById("modalDiv").innerText = fin.dividend_yield ? `${Number(fin.dividend_yield).toFixed(2)}%` : "0.00%";
}

function closeModal() {
  document.getElementById("stockModal").classList.remove("active");
}

function closeModalOnOverlay(e) {
  if (e.target.id === "stockModal") {
    closeModal();
  }
}
