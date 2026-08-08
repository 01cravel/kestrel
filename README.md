# Kestrel

A plain-English daily view of a long-term stock portfolio.

Luke’s current mandate is maximum long-term wealth building at a target risk of 8/10, with an open-ended horizon and no sector preference. Kestrel keeps the real portfolio separate from a future selection-agnostic Ideal Portfolio, so existing choices cannot bias the target answer.

Kestrel answers two questions:

- What should I do with the investments I already own?
- Which strong opportunities am I currently missing?

The planned intelligence, verification, charting, and international-market work is tracked in [ROADMAP.md](ROADMAP.md).
The authoritative-source hierarchy and confidence gates are defined in [SOURCE_POLICY.md](SOURCE_POLICY.md).

## Run locally

```sh
FINNHUB_KEY="your-finnhub-key" FMP_KEY="your-fmp-key" FRED_API_KEY="your-fred-key" DATABENTO_API_KEY="your-databento-key" python3 server.py
```

Then open [http://127.0.0.1:3050](http://127.0.0.1:3050).

The local server keeps API credentials out of the browser, loads evidence progressively,
and caches results so the dashboard does not start blank after every restart. Set
`SEC_USER_AGENT` to a descriptive name and contact address when running the SEC checks
outside local development.

`FRED_API_KEY` is optional and is read only from the environment. When present,
`/api/macro` returns an end-of-day point-in-time FRED/ALFRED snapshot; pass an
historical cutoff as `?as_of=YYYY-MM-DD`. The ignored local cache refreshes the
current cutoff every 12 hours, preserves completed historical cutoffs, and never
stores the credential. `KESTREL_MACRO_CACHE_PATH` may relocate that cache and
`FRED_API_BASE_URL` may select another HTTPS-compatible endpoint.

## Data and ratings

- Current prices, company metrics, recommendations, and earnings surprises currently come from Finnhub and are classified as provisional.
- The default cost-controlled market layer cross-checks Yahoo adjusted daily closes against Finnhub and rejects stale prices or unexplained split-sized jumps. If `DATABENTO_API_KEY` is present, Kestrel can add pay-as-you-go `EQUS.SUMMARY` official consolidated closes. Paid corporate-action reference data is optional and is never implied when it is absent.
- Historical prices, analyst estimates, and consensus targets currently come from Financial Modeling Prep when the configured plan covers the symbol. Yahoo Finance provides a clearly labelled provisional chart fallback when it does not; the latest point is cross-checked against Finnhub.
- The named-analyst adapter accepts Benzinga’s official Analyst Ratings feed when `BENZINGA_API_KEY` is present. It preserves the analyst, research firm, rating change, target change, date and available accuracy record, requires at least three recent firms, and checks the result against Finnhub’s broader consensus before it can affect a score.
- Official filing verification comes directly from SEC EDGAR and is shown with the filing date and source link.
- Rates and economic-regime context uses ALFRED observations visible at the requested cutoff: Federal Reserve H.15 2- and 10-year yields, BLS CPI and unemployment, and BEA real GDP. Missing or stale series disable the regime; the label is research context only and cannot change a company or portfolio rating.
- Opportunity discovery now reads the latest and previous SEC Form 13F filings for eight deliberately selected long-equity managers. It ranks the investigation queue by disclosed buying, independent agreement and portfolio conviction, then subjects every resolved company to Kestrel's separate evidence gates. The interface always shows the quarterly delay and never turns ownership alone into a Buy rating.
- Permanent instrument identities come from OpenFIGI and the SEC ticker directory. Ambiguous or unresolved identities automatically block Buy ratings instead of being guessed.
- Positions are stored in browser local storage and an ignored private local portfolio file. Each edit keeps a backup of the previous portfolio.
- Sarwa snapshots enter a separate ignored staging file, are reconciled against the last good portfolio, and require review before they can replace live positions.
- Daily signal history and model versions remain in ignored local files so Kestrel can measure later outcomes without publishing private data.
- Confidence is capped at `Medium` and `Ultra Buy` is locked until institutional pricing, validated corporate actions, point-in-time estimates, complete provenance and whole-portfolio risk checks are connected.
- The previous prototype can be kept locally as `kestrel-legacy.html`, but is deliberately excluded from Git because it may contain credentials and private portfolio data.

For interface testing, use `http://127.0.0.1:3050/?mode=qa`. QA positions use separate browser storage and do not write portfolio or signal-history data.
