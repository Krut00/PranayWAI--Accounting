from lendiq.analysis import build_credit_analysis
from lendiq.screener import parse_company_html, parse_number


HTML = """
<h1>Example Industries Ltd</h1>
<div id="top-ratios"><li><span class="name">Stock P/E</span><span class="number">20.5</span></li></div>
<section id="profit-loss"><table><thead><tr><th></th><th>Mar 2023</th><th>Mar 2024</th></tr></thead><tbody>
<tr><td>Sales</td><td>1,000</td><td>1,200</td></tr><tr><td>Operating Profit</td><td>200</td><td>260</td></tr>
<tr><td>Other Income</td><td>10</td><td>12</td></tr><tr><td>Interest</td><td>20</td><td>22</td></tr>
<tr><td>Profit before tax</td><td>180</td><td>238</td></tr><tr><td>Tax %</td><td>25%</td><td>25%</td></tr>
<tr><td>Net Profit</td><td>135</td><td>178</td></tr></tbody></table></section>
<section id="balance-sheet"><table><thead><tr><th></th><th>Mar 2023</th><th>Mar 2024</th></tr></thead><tbody>
<tr><td>Equity Capital</td><td>100</td><td>100</td></tr><tr><td>Reserves</td><td>500</td><td>650</td></tr>
<tr><td>Borrowings</td><td>300</td><td>280</td></tr><tr><td>Total Assets</td><td>1,200</td><td>1,350</td></tr></tbody></table></section>
<section id="cash-flow"><table><thead><tr><th></th><th>Mar 2023</th><th>Mar 2024</th></tr></thead><tbody>
<tr><td>Cash from Operating Activity</td><td>150</td><td>210</td></tr>
<tr><td>Cash from Investing Activity</td><td>(80)</td><td>-90</td></tr><tr><td>Cash from Financing Activity</td><td>-30</td><td>-50</td></tr>
</tbody></table></section><section id="ratios"><table><thead><tr><th></th><th>Mar 2024</th></tr></thead><tbody><tr><td>ROCE %</td><td>24%</td></tr></tbody></table></section>
"""


def test_number_parser_handles_screener_formats():
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("(80)") == -80
    assert parse_number("25%") == 25


def test_pipeline_reconciles_and_scores_source_data():
    source = parse_company_html(HTML, "https://www.screener.in/company/EXAMPLE/")
    result = build_credit_analysis(source, 100)
    assert result["company"] == "Example Industries Ltd"
    assert result["reconciliation"]["status"] == "VERIFIED"
    assert result["reconciliation"]["matched"] == result["reconciliation"]["total"]
    assert result["loan"]["proposed_borrowings"] == 380
    assert result["metrics"]["revenue_growth"] == 20
    assert 0 <= result["score"] <= 100