from __future__ import annotations

from typing import Any


def _row(data: dict[str, Any], section: str, *names: str) -> list[float | None]:
    rows = data["sections"][section]["rows"]
    for name in names:
        for label, row in rows.items():
            if label.casefold() == name.casefold():
                return row["values"]
    return []


def _last(values: list[float | None], offset: int = 0) -> float | None:
    present = [value for value in values if value is not None]
    return present[-1 - offset] if len(present) > offset else None


def _ratio(numerator: float | None, denominator: float | None, scale: float = 1) -> float | None:
    return numerator / denominator * scale if numerator is not None and denominator not in {None, 0} else None


def _growth(values: list[float | None]) -> float | None:
    latest, previous = _last(values), _last(values, 1)
    return _ratio((latest - previous) if latest is not None and previous is not None else None, abs(previous) if previous else None, 100)


def _points(value: float | None, bands: list[tuple[float, float]], default: float = 0) -> float:
    if value is None:
        return default
    for threshold, points in bands:
        if value >= threshold:
            return points
    return 0


def _fallback(value: float | None, default: float) -> float:
    return default if value is None else value


def build_credit_analysis(data: dict[str, Any], loan_amount: float) -> dict[str, Any]:
    sales = _row(data, "income", "Sales")
    operating_profit = _row(data, "income", "Operating Profit", "OPM")
    net_profit = _row(data, "income", "Net Profit")
    other_income = _row(data, "income", "Other Income")
    interest = _row(data, "income", "Interest")
    pbt = _row(data, "income", "Profit before tax", "PBT")
    tax = _row(data, "income", "Tax %")
    borrowings = _row(data, "balance_sheet", "Borrowings")
    equity_capital = _row(data, "balance_sheet", "Equity Capital")
    reserves = _row(data, "balance_sheet", "Reserves")
    total_assets = _row(data, "balance_sheet", "Total Assets")
    cfo = _row(data, "cash_flow", "Cash from Operating Activity", "Cash from Operating Activities")
    cfi = _row(data, "cash_flow", "Cash from Investing Activity", "Cash from Investing Activities")
    cff = _row(data, "cash_flow", "Cash from Financing Activity", "Cash from Financing Activities")

    latest = {name: _last(values) for name, values in {
        "sales": sales, "operating_profit": operating_profit, "net_profit": net_profit,
        "other_income": other_income, "interest": interest, "pbt": pbt, "tax_rate": tax,
        "borrowings": borrowings, "equity_capital": equity_capital, "reserves": reserves,
        "total_assets": total_assets, "cfo": cfo, "cfi": cfi, "cff": cff,
    }.items()}
    net_worth = (latest["equity_capital"] or 0) + (latest["reserves"] or 0)
    post_debt = (latest["borrowings"] or 0) + max(loan_amount, 0)
    metrics = {
        "revenue_growth": _growth(sales),
        "operating_profit_growth": _growth(operating_profit),
        "net_profit_growth": _growth(net_profit),
        "cfo_growth": _growth(cfo),
        "borrowing_growth": _growth(borrowings),
        "operating_margin": _ratio(latest["operating_profit"], latest["sales"], 100),
        "net_margin": _ratio(latest["net_profit"], latest["sales"], 100),
        "cfo_net_profit": _ratio(latest["cfo"], latest["net_profit"]),
        "cfo_debt": _ratio(latest["cfo"], latest["borrowings"]),
        "debt_equity": _ratio(latest["borrowings"], net_worth),
        "post_loan_debt_equity": _ratio(post_debt, net_worth),
        "interest_coverage": _ratio(latest["operating_profit"], latest["interest"]),
        "interest_burden": _ratio(latest["interest"], latest["operating_profit"], 100),
        "other_income_pbt": _ratio(latest["other_income"], latest["pbt"], 100),
        "asset_turnover": _ratio(latest["sales"], latest["total_assets"]),
        "financial_leverage": _ratio(latest["total_assets"], net_worth),
        "roe": _ratio(latest["net_profit"], net_worth, 100),
        "roce_proxy": _ratio(latest["operating_profit"], net_worth + (latest["borrowings"] or 0), 100),
        "cost_of_debt": _ratio(latest["interest"], latest["borrowings"], 100),
        "borrowings_assets": _ratio(latest["borrowings"], latest["total_assets"], 100),
        "effective_tax_rate": latest["tax_rate"],
    }

    cash_score = sum([
        _points(latest["cfo"], [(0.01, 8)]),
        _points(metrics["cfo_net_profit"], [(1, 10), (0.8, 7), (0.5, 3)]),
        _points(metrics["cfo_debt"], [(0.3, 8), (0.15, 5), (0.05, 2)]),
        _points(metrics["cfo_growth"], [(10, 4), (0, 2)]),
    ])
    debt_score = sum([
        _points(-_fallback(metrics["post_loan_debt_equity"], 99), [(-0.5, 9), (-1, 7), (-2, 3)]),
        _points(metrics["interest_coverage"], [(5, 9), (3, 7), (1.5, 3)]),
        _points(-_fallback(metrics["borrowing_growth"], 99), [(-10, 7), (-25, 4)]),
    ])
    profit_score = sum([
        _points(metrics["operating_margin"], [(20, 6), (10, 4), (5, 2)]),
        _points(metrics["net_margin"], [(10, 5), (5, 3), (0, 1)]),
        _points(metrics["revenue_growth"], [(10, 4), (0, 2)]),
    ])
    liquidity_score = sum([
        _points(net_worth, [(0.01, 4)]),
        _points(-_fallback(metrics["borrowings_assets"], 100), [(-25, 6), (-50, 3)]),
    ])
    earnings_score = sum([
        _points(metrics["cfo_net_profit"], [(1, 6), (0.7, 4), (0.4, 2)]),
        _points(-(metrics["other_income_pbt"] or 0), [(-10, 4), (-25, 2)]),
    ])
    dupont_score = sum([
        _points(metrics["asset_turnover"], [(1, 2), (0.5, 1)]),
        _points(-_fallback(metrics["financial_leverage"], 99), [(-2, 3), (-3, 2), (-5, 1)]),
    ])
    pe = next((item["value"] for name, item in data["top_ratios"].items() if name.casefold() in {"stock p/e", "p/e"}), None)
    investor_score = _points(-(pe or 100), [(-25, 5), (-40, 3), (-70, 1)])
    category_scores = {
        "Cash flow & repayment": round(cash_score, 1), "Debt & leverage": round(debt_score, 1),
        "Profitability": round(profit_score, 1), "Liquidity & strength": round(liquidity_score, 1),
        "Earnings quality": round(earnings_score, 1), "DuPont efficiency": round(dupont_score, 1),
        "Investor perception": round(investor_score, 1),
    }
    score = round(sum(category_scores.values()))
    decision = "APPROVE" if score >= 80 else "APPROVE WITH CONDITIONS" if score >= 60 else "REJECT"

    positives = []
    risks = []
    (positives if (metrics["cfo_net_profit"] or 0) >= 0.8 else risks).append("Profit converts well into cash" if (metrics["cfo_net_profit"] or 0) >= 0.8 else "Weak profit-to-cash conversion")
    (positives if (metrics["interest_coverage"] or 0) >= 3 else risks).append("Comfortable interest coverage" if (metrics["interest_coverage"] or 0) >= 3 else "Interest coverage is under pressure")
    post_loan_de = _fallback(metrics["post_loan_debt_equity"], 99)
    (positives if post_loan_de <= 1 else risks).append("Post-loan leverage remains moderate" if post_loan_de <= 1 else "Post-loan leverage is elevated")
    (positives if (metrics["revenue_growth"] or -1) > 0 else risks).append("Revenue is growing" if (metrics["revenue_growth"] or -1) > 0 else "Revenue growth is weak or negative")
    if (metrics["other_income_pbt"] or 0) > 25:
        risks.append("Profit depends materially on other income")
    if (metrics["roce_proxy"] or 0) > (metrics["cost_of_debt"] or 99):
        positives.append("Operating return exceeds approximate debt cost")
    else:
        risks.append("Operating return does not cover approximate debt cost")

    banker_insights = [
        {"title": "Repayment capacity", "status": "POSITIVE" if (metrics["cfo_net_profit"] or 0) >= 0.8 else "REVIEW", "evidence": f"CFO is {_fallback(metrics['cfo_net_profit'], 0):.2f}x net profit and {_fallback(metrics['cfo_debt'], 0):.2f}x existing debt.", "review": "Confirm cash flow is recurring and not driven by one-off working-capital releases."},
        {"title": "Debt servicing", "status": "POSITIVE" if (metrics["interest_coverage"] or 0) >= 3 else "HIGH ATTENTION", "evidence": f"Operating profit covers interest {_fallback(metrics['interest_coverage'], 0):.2f}x.", "review": "Stress-test coverage for lower profit and the proposed facility's interest cost."},
        {"title": "Post-sanction leverage", "status": "POSITIVE" if post_loan_de <= 1 else "HIGH ATTENTION" if post_loan_de > 2 else "REVIEW", "evidence": f"Debt-to-equity moves to {post_loan_de:.2f}x after the requested loan.", "review": "Verify off-balance-sheet obligations, guarantees, and undrawn limits."},
        {"title": "Earnings sustainability", "status": "REVIEW" if (metrics["other_income_pbt"] or 0) > 25 else "POSITIVE", "evidence": f"Other income contributes {_fallback(metrics['other_income_pbt'], 0):.2f}% of profit before tax.", "review": "Separate recurring operating earnings from exceptional and non-core income."},
        {"title": "Leverage effectiveness", "status": "POSITIVE" if (metrics["roce_proxy"] or 0) > (metrics["cost_of_debt"] or 99) else "HIGH ATTENTION", "evidence": f"ROCE proxy is {_fallback(metrics['roce_proxy'], 0):.2f}% versus debt cost of {_fallback(metrics['cost_of_debt'], 0):.2f}%.", "review": "Validate returns against the loan purpose and projected incremental cash flows."},
    ]
    conditions = [
        "Obtain audited statements and reconcile material differences with Screener data.",
        "Set quarterly covenants for debt-to-equity and interest coverage.",
        "Restrict additional borrowing and related-party advances without lender consent.",
    ]
    if post_loan_de > 1:
        conditions.append("Require scheduled deleveraging or additional collateral before disbursement.")
    if (metrics["cfo_net_profit"] or 0) < 0.8:
        conditions.append("Link disbursement to improved operating cash conversion.")
    due_diligence = [
        "Verify loan purpose, repayment schedule, collateral coverage, and end use.",
        "Review bureau records, facility terms, security charges, and contingent liabilities.",
        "Complete KYC/AML, related-party, promoter, litigation, and regulatory checks.",
        "Run downside scenarios for revenue, margin, interest rate, and working-capital stress.",
    ]

    data.update({
        "loan": {"requested": loan_amount, "existing_borrowings": latest["borrowings"], "proposed_borrowings": post_debt},
        "latest": latest | {"net_worth": net_worth},
        "metrics": metrics,
        "score": score,
        "category_scores": category_scores,
        "decision": decision,
        "repayment_capacity": "Strong" if cash_score >= 23 else "Moderate" if cash_score >= 15 else "Weak",
        "leverage_risk": "Low" if debt_score >= 20 else "Moderate" if debt_score >= 13 else "High",
        "earnings_quality": "Strong" if earnings_score >= 8 else "Requires review" if earnings_score >= 5 else "High risk",
        "strengths": positives[:3],
        "risks": risks[:3],
        "banker_review": {
            "summary": f"Model recommendation: {decision} at {score}/100. Review the evidence and conditions before recording a credit decision.",
            "insights": banker_insights,
            "conditions": conditions,
            "due_diligence": due_diligence,
        },
    })
    return data