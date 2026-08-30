from flask import Flask, jsonify, render_template, request

from lendiq.analysis import build_credit_analysis
from lendiq.screener import ScreenerError, fetch_company, search_companies

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/search")
def search():
    try:
        return jsonify(search_companies(request.args.get("q", "")))
    except ScreenerError as exc:
        return jsonify({"error": str(exc)}), 502


@app.get("/api/company/<symbol>")
def company(symbol: str):
    loan_amount = request.args.get("loan_amount", type=float, default=0.0)
    try:
        company_data = fetch_company(symbol)
        return jsonify(build_credit_analysis(company_data, loan_amount))
    except ScreenerError as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5050)