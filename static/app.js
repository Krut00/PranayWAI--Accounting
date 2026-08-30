const $ = (selector) => document.querySelector(selector);
const fmt = (value, suffix = "") => value == null ? "N/A" : `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
const labels = {
  revenue_growth: "Revenue growth", operating_profit_growth: "Operating profit growth", net_profit_growth: "Net profit growth",
  cfo_growth: "CFO growth", borrowing_growth: "Borrowing growth", operating_margin: "Operating margin", net_margin: "Net margin",
  cfo_net_profit: "CFO / Net profit", cfo_debt: "CFO / Debt", debt_equity: "Debt / Equity", post_loan_debt_equity: "Post-loan D/E",
  interest_coverage: "Interest coverage", interest_burden: "Interest / Operating profit", other_income_pbt: "Other income / PBT",
  asset_turnover: "Asset turnover", financial_leverage: "Financial leverage", roe: "ROE", roce_proxy: "ROCE proxy",
  cost_of_debt: "Approx. cost of debt", borrowings_assets: "Borrowings / Assets", effective_tax_rate: "Effective tax rate"
};
const percentMetrics = new Set(["revenue_growth", "operating_profit_growth", "net_profit_growth", "cfo_growth", "borrowing_growth", "operating_margin", "net_margin", "interest_burden", "other_income_pbt", "roe", "roce_proxy", "cost_of_debt", "borrowings_assets", "effective_tax_rate"]);
let searchTimer;

function updateLoan(value) {
  const amount = Math.max(0, Math.min(100000, Number(value) || 0));
  $("#loanAmount").value = amount;
  $("#loanRange").value = amount;
  $("#loanOutput").textContent = `₹${amount.toLocaleString("en-IN")} Cr`;
}

function showSuggestions(items) {
  const menu = $("#suggestions");
  menu.replaceChildren();
  items.forEach(item => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "option");
    const name = document.createElement("strong");
    const symbol = document.createElement("span");
    name.textContent = item.name;
    symbol.textContent = item.symbol;
    button.append(name, symbol);
    button.addEventListener("click", () => {
      $("#symbol").value = item.symbol;
      $("#symbol").dataset.symbol = item.symbol;
      menu.hidden = true;
    });
    menu.append(button);
  });
  menu.hidden = items.length === 0;
}

$("#symbol").addEventListener("input", (event) => {
  delete event.target.dataset.symbol;
  clearTimeout(searchTimer);
  const query = event.target.value.trim();
  if (query.length < 2) return showSuggestions([]);
  searchTimer = setTimeout(async () => {
    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const items = await response.json();
      showSuggestions(response.ok ? items : []);
    } catch {
      showSuggestions([]);
    }
  }, 250);
});

$("#loanRange").addEventListener("input", event => updateLoan(event.target.value));
$("#loanAmount").addEventListener("input", event => updateLoan(event.target.value));
document.addEventListener("click", event => {
  if (!event.target.closest(".company-search")) $("#suggestions").hidden = true;
});

function render(data) {
  $("#dashboard").hidden = false;
  $("#loading").hidden = true;
  $("#companyName").textContent = data.company;
  $("#score").textContent = data.score;
  $("#decision").textContent = data.decision;
  $("#decision").className = `decision ${data.decision === "APPROVE" ? "approve" : data.decision === "REJECT" ? "reject" : "conditional"}`;
  $("#decisionMeta").textContent = `${data.repayment_capacity} repayment capacity · ${data.leverage_risk} leverage risk`;
  $("#sourceLink").href = data.source_url;
  $("#sourceBadge").textContent = `${data.reconciliation.status} · ${data.reconciliation.matched}/${data.reconciliation.total}`;
  $("#sourceBadge").className = `source-badge ${data.reconciliation.status === "VERIFIED" ? "verified" : "review"}`;
  $("#kpis").innerHTML = [
    ["Loan request", `₹${fmt(data.loan.requested)} Cr`], ["Existing debt", `₹${fmt(data.loan.existing_borrowings)} Cr`],
    ["Post-loan D/E", fmt(data.metrics.post_loan_debt_equity, "×")], ["Interest cover", fmt(data.metrics.interest_coverage, "×")],
    ["CFO / profit", fmt(data.metrics.cfo_net_profit, "×")], ["Earnings quality", data.earnings_quality]
  ].map(([name, value]) => `<article class="kpi"><span>${name}</span><strong>${value}</strong></article>`).join("");
  const weights = {"Cash flow & repayment": 30, "Debt & leverage": 25, "Profitability": 15, "Liquidity & strength": 10, "Earnings quality": 10, "DuPont efficiency": 5, "Investor perception": 5};
  $("#scoreBars").innerHTML = Object.entries(data.category_scores).map(([name, score]) => `<div class="score-row"><div><span>${name}</span><strong>${score}/${weights[name]}</strong></div><div class="bar"><i style="width:${score / weights[name] * 100}%"></i></div></div>`).join("");
  $("#strengths").innerHTML = data.strengths.map(item => `<li>${item}</li>`).join("") || "<li>No strong factor identified.</li>";
  $("#risks").innerHTML = data.risks.map(item => `<li>${item}</li>`).join("") || "<li>No material risk identified.</li>";
  $("#metrics").innerHTML = Object.entries(data.metrics).map(([name, value]) => `<div><span>${labels[name] || name}</span><strong>${fmt(value, percentMetrics.has(name) ? "%" : "×")}</strong></div>`).join("");
  renderTrend(data);
  renderBankerReview(data.banker_review);
  renderStatements(data.sections);
  renderAudit(data.reconciliation);
}

function renderBankerReview(review) {
  $("#reviewSummary").textContent = review.summary;
  $("#reviewInsights").innerHTML = review.insights.map(insight => `<article class="insight"><div><span class="insight-status ${insight.status.toLowerCase().replace(" ", "-")}">${insight.status}</span><h3>${insight.title}</h3></div><strong>${insight.evidence}</strong><p>${insight.review}</p></article>`).join("");
  $("#loanConditions").innerHTML = review.conditions.map(item => `<li>${item}</li>`).join("");
  $("#dueDiligence").innerHTML = review.due_diligence.map(item => `<li>${item}</li>`).join("");
}

function renderTrend(data) {
  const section = data.sections.cash_flow;
  const profitSection = data.sections.income;
  const cfo = Object.entries(section.rows).find(([name]) => name.toLowerCase().includes("operating activ"))?.[1]?.values || [];
  const profit = profitSection.rows["Net Profit"]?.values || [];
  const periods = section.periods.slice(-6);
  const pairs = periods.map((period, index) => ({ period, cfo: cfo[cfo.length - periods.length + index], profit: profit[profit.length - periods.length + index] }));
  const max = Math.max(1, ...pairs.flatMap(item => [Math.abs(item.cfo || 0), Math.abs(item.profit || 0)]));
  $("#trendChart").innerHTML = `<div class="legend"><i></i> Net profit <i></i> CFO</div><div class="columns">${pairs.map(item => `<div class="year"><div class="sticks"><i style="height:${Math.abs(item.profit || 0) / max * 150}px"></i><i style="height:${Math.abs(item.cfo || 0) / max * 150}px"></i></div><span>${item.period}</span></div>`).join("")}</div>`;
}

function renderStatements(sections) {
  $("#statementTables").innerHTML = Object.entries(sections).map(([name, section]) => {
    const periods = section.periods.slice(-5);
    const rows = Object.entries(section.rows).map(([label, row]) => `<tr><th>${label}</th>${row.source_values.slice(-5).map(value => `<td>${value || "-"}</td>`).join("")}</tr>`).join("");
    return `<article><p class="eyebrow">SCREENER · ₹ CRORE</p><h3>${name.replaceAll("_", " ")}</h3><div class="table-scroll"><table><thead><tr><th>Line item</th>${periods.map(p => `<th>${p}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div></article>`;
  }).join("");
}

function renderAudit(reconciliation) {
  $("#auditSummary").textContent = `${reconciliation.matched} of ${reconciliation.total} matched`;
  $("#auditTable").innerHTML = `<div class="audit-head"><span>Field</span><span>Screener display</span><span>Fetched value</span><span>Status</span></div>${reconciliation.checks.slice(-200).reverse().map(check => `<div><span>${check.field}</span><span>${check.screener_display || "blank"}</span><span>${fmt(check.fetched_value)}</span><strong class="${check.match ? "ok" : "bad"}">${check.match ? "MATCH" : "REVIEW"}</strong></div>`).join("")}`;
}

$("#searchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#dashboard").hidden = true;
  $("#loading").hidden = false;
  $("#loading").textContent = "Fetching and reconciling Screener data…";
  try {
    const response = await fetch(`/api/company/${encodeURIComponent($("#symbol").value)}?loan_amount=${encodeURIComponent($("#loanAmount").value)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Analysis failed");
    render(data);
  } catch (error) {
    $("#loading").textContent = error.message;
  }
});

document.querySelectorAll(".tabs button").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".tabs button, .view").forEach(item => item.classList.remove("active"));
  button.classList.add("active");
  $(`#${button.dataset.target}`).classList.add("active");
}));