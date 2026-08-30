from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.screener.in/company/{symbol}/consolidated/"
SEARCH_URL = "https://www.screener.in/api/company/search/"
SECTIONS = {
    "income": "profit-loss",
    "balance_sheet": "balance-sheet",
    "cash_flow": "cash-flow",
    "ratios": "ratios",
}


class ScreenerError(RuntimeError):
    pass


def search_companies(query: str) -> list[dict[str, str]]:
    clean_query = query.strip()[:80]
    if len(clean_query) < 2:
        return []
    try:
        response = requests.get(
            SEARCH_URL,
            params={"q": clean_query},
            headers={"User-Agent": "LENDIQ/1.0 financial research dashboard"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ScreenerError(f"Screener search failed: {exc}") from exc

    suggestions = []
    for result in results[:8]:
        match = re.search(r"/company/([^/]+)", result.get("url", ""))
        if match and result.get("name"):
            suggestions.append({"name": result["name"], "symbol": match.group(1).upper()})
    return suggestions


def parse_number(raw: str) -> float | None:
    value = raw.strip().replace(",", "").replace("%", "")
    if not value or value in {"-", "--"}:
        return None
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None
    number = float(match.group())
    return -number if negative else number


def _annual_table(soup: BeautifulSoup, section_id: str) -> dict[str, Any]:
    section = soup.find("section", id=section_id)
    table = section.find("table") if section else None
    if not table:
        return {"periods": [], "rows": {}}

    headers = [cell.get_text(" ", strip=True) for cell in table.select("thead th")][1:]
    rows: dict[str, Any] = {}
    for row in table.select("tbody tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True).replace("+", "").strip()
        raw_values = [cell.get_text(" ", strip=True) for cell in cells[1:]]
        values = [parse_number(raw) for raw in raw_values]
        rows[label] = {"values": values, "source_values": raw_values}
    return {"periods": headers, "rows": rows}


def _top_ratios(soup: BeautifulSoup) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in soup.select("#top-ratios li"):
        name = item.select_one(".name")
        number = item.select_one(".number")
        if name and number:
            raw = number.get_text(" ", strip=True)
            result[name.get_text(" ", strip=True)] = {
                "value": parse_number(raw),
                "source_value": raw,
            }
    return result


def _reconciliation(sections: dict[str, Any], top_ratios: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for section_name, section in sections.items():
        for label, row in section["rows"].items():
            for period, raw, parsed in zip(section["periods"], row["source_values"], row["values"]):
                source_number = parse_number(raw)
                checks.append({
                    "field": f"{section_name}.{label}.{period}",
                    "screener_display": raw,
                    "fetched_value": parsed,
                    "match": source_number == parsed,
                })
    for label, item in top_ratios.items():
        checks.append({
            "field": f"market.{label}",
            "screener_display": item["source_value"],
            "fetched_value": item["value"],
            "match": parse_number(item["source_value"]) == item["value"],
        })
    matched = sum(check["match"] for check in checks)
    return {
        "status": "VERIFIED" if checks and matched == len(checks) else "REVIEW REQUIRED",
        "matched": matched,
        "total": len(checks),
        "checks": checks,
    }


def parse_company_html(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    sections = {name: _annual_table(soup, section_id) for name, section_id in SECTIONS.items()}
    top_ratios = _top_ratios(soup)
    return {
        "company": heading.get_text(" ", strip=True) if heading else "Unknown company",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "top_ratios": top_ratios,
        "reconciliation": _reconciliation(sections, top_ratios),
    }


def fetch_company(symbol: str) -> dict[str, Any]:
    clean_symbol = re.sub(r"[^A-Za-z0-9.-]", "", symbol).upper()
    if not clean_symbol:
        raise ScreenerError("Enter a valid NSE/BSE symbol.")
    url = BASE_URL.format(symbol=clean_symbol)
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "LENDIQ/1.0 financial research dashboard"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ScreenerError(f"Screener request failed: {exc}") from exc
    data = parse_company_html(response.text, url)
    if not any(section["rows"] for section in data["sections"].values()):
        raise ScreenerError("No annual financial tables were found on the Screener page.")
    return data