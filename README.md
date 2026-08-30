# LENDIQ

A standalone bank credit-decision dashboard. It fetches consolidated annual financial statements from Screener, preserves each displayed source cell, reconciles parsed figures against those cells, and then calculates a weighted lending score.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5050` and enter an NSE/BSE symbol plus the proposed loan amount in ₹ crore.

## Deploy on Render

1. Push this project to a GitHub repository.
2. In Render, choose **New > Blueprint** and connect the repository.
3. Render will read `render.yaml`, install dependencies, run the tests, and start Gunicorn.

Manual web-service settings, if not using the Blueprint:

- Build command: `pip install -r requirements.txt && pytest -q`
- Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app`
- Health check path: `/health`

## Source controls

- The dashboard uses only the requested Screener company page for financial inputs.
- The Source audit tab shows Screener's exact displayed value, the parsed value, and match status.
- The source URL and UTC fetch timestamp accompany every result.
- A `REVIEW REQUIRED` badge is shown if any reconciliation fails.
- Automated collection may be restricted by Screener. Use responsibly and comply with its terms; no bypass mechanism is included.

The score is decision support, not a substitute for audited statements, bureau checks, collateral review, KYC/AML procedures, or a credit officer's judgment.