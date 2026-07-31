# Kestrel

A plain-English daily view of a long-term stock portfolio.

Kestrel answers two questions:

- What should I do with the investments I already own?
- Which strong opportunities am I currently missing?

The planned intelligence, verification, charting, and international-market work is tracked in [ROADMAP.md](ROADMAP.md).

## Run locally

```sh
FINNHUB_KEY="your-finnhub-key" FMP_KEY="your-fmp-key" python3 server.py
```

Then open [http://127.0.0.1:3050](http://127.0.0.1:3050).

The local server keeps API credentials out of the browser, loads evidence progressively,
and caches results so the dashboard does not start blank after every restart. Set
`SEC_USER_AGENT` to a descriptive name and contact address when running the SEC checks
outside local development.

## Data and ratings

- Current prices, company metrics, recommendations, and earnings surprises come from Finnhub.
- Historical prices, analyst estimates, and consensus targets come from Financial Modeling Prep when the configured plan covers the symbol. Yahoo Finance provides a clearly labelled chart fallback when it does not; the latest point is cross-checked against Finnhub.
- Official filing verification comes directly from SEC EDGAR and is shown with the filing date and source link.
- Positions remain in browser local storage.
- Daily signal history and model versions remain in ignored local files so Kestrel can measure later outcomes without publishing private data.
- `Ultra Buy` requires exceptional scores, official-filing agreement, and a portfolio concentration check.
- The previous prototype can be kept locally as `kestrel-legacy.html`, but is deliberately excluded from Git because it may contain credentials and private portfolio data.
