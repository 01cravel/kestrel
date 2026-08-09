# Kestrel source-of-truth policy

Kestrel’s job is not to collect the most data. It is to preserve the shortest dependable chain from an investment decision back to the evidence that justified it.

## Non-negotiable rules

1. Facts outrank opinions. Opinions outrank model-derived guesses.
2. Every decision-critical number retains its source, observation period, unit, currency, retrieval time, and any transformation Kestrel applied.
3. Missing evidence never becomes positive evidence. Conflicts and stale inputs reduce confidence automatically.
4. No single commercial aggregator is a source of truth for prices, fundamentals, estimates, and corporate actions at the same time.
5. Models transform evidence; they do not become evidence. Every model output carries its version, assumptions, input snapshot, uncertainty, and later outcome.
6. Kestrel must refuse a confident rating when a required gate fails.
7. Company guidance remains an issuer claim, not a reported result. Preserve the exact published range; never manufacture a midpoint, silently translate currency, or compare unlike periods or definitions.
8. Historical research uses only an immutable universe snapshot frozen before its outcome. A later ticker list, revised identity, changed ETF portfolio or disappeared company can never replace the original record.
9. Automatic portfolio selection may read only that frozen snapshot. It records the snapshot, manifest, input-evidence and candidate hashes; incomplete membership, thin descriptors or filing conflicts produce no selection. Every direct company needs a versioned economic-theme classification and no selected theme may exceed 12%; missing classifications or an infeasible combination produce no selection. Candidate 1 remains immutable history, while Candidate 2 is labelled as a provisional judgement rather than a newly proven answer.

## Hierarchy

| Tier | Meaning | Examples | Decision use |
|---|---|---|---|
| 1 — Authoritative | The account owner, regulator, exchange, government agency, central bank, or issuer filing | Sarwa statements, SEC EDGAR, FCA NSM, ESMA ESEF, Treasury, BLS | Establish facts |
| 2 — Institutional validated | Licensed, timestamped data with transparent corrections and quality controls | Exchange/SIP market data, LSEG I/B/E/S, FactSet, Bloomberg, S&P corporate actions, MSCI Barra | Validate, standardise, and scale |
| 3 — Provisional | Convenient feeds that are useful but require confirmation | Finnhub, Financial Modeling Prep, Yahoo chart feed | Early view and cross-check only |
| 4 — Experimental | Alternative data or derived models | News sentiment, web traffic, model forecasts, Kestrel scores | Supporting signal only |

## Best source by fact

| Fact | Authoritative or best institutional source | Kestrel rule | Current state |
|---|---|---|---|
| Luke’s holdings, cash, deposits and withdrawals | Sarwa official statement and account record | Daily web capture is reconciled with the latest statement before replacing the portfolio | Trade web capture connected; statement importer remains next |
| Security identity | OpenFIGI plus CIK, LEI, ISIN, exchange MIC and currency | A ticker alone is never a permanent identifier | Persistent OpenFIGI, share-class FIGI and SEC CIK mapping connected; ISIN, MIC and local regulator IDs follow with direct-market coverage |
| Historical investable universe | Official regulator and market-reference listing records joined to Kestrel’s append-only daily manifest | Retain included and excluded members, stable identities, exact cutoff and retrieval times, selection/model/policy versions, ETF holdings and complete delisting outcomes. Corrections append a new valid-time version; updates and deletes are forbidden | Prospective bitemporal ledger and automatic later-outcome capture are connected. Survivors accumulate continuous same-currency adjusted paths; ticker changes follow stable identity. Historical folds remain locked until every member is `complete` or independently evidenced `delisted_complete` |
| US reported fundamentals | SEC EDGAR submissions, filing document and Company Facts XBRL API | Store the filing accession, period and original fact tag; detect amendments and restatements | Connected for core revenue, income and equity checks |
| International reported fundamentals | The issuer’s local regulator filing; ESMA ESEF for the EU and FCA NSM for the UK | Add one regulator pipeline at a time; do not treat a US ADR feed as full local-market coverage | Planned |
| Live and closing prices | CTA/CQ and UTP SIP data; official exchange/consolidated closes | Confirm the latest price independently; reject stale, wrong-currency or split-broken series | Yahoo adjusted daily closes are cross-checked against Finnhub. Databento pay-as-you-go Nasdaq NLS+ closes are the next optional upgrade; no monthly subscription is required |
| Corporate actions and total return | Exchange/issuer notices plus DTCC, normalized by a validated point-in-time service | Splits, dividends, mergers, symbol changes and delistings must be applied before return or risk calculations | The daily no-cost pass now reads SEC filing packages and can accept allow-listed official issuer releases. It appends only explicit effective dates, per-share cash plus ISO currency, stock ratios and stable successor identities, with accession/URL, publication/availability/retrieval clocks and raw hashes. Amendments must name the superseded accession; unlinked conflicts fail closed. An inactive dated listing record is still independently required, so item codes and ticker disappearance never establish a delisting |
| Analyst expectations | Named analyst actions and long-lived point-in-time contributor estimates | Estimates are opinions. Preserve analyst, firm, rating and target change, date and track record; require at least three firms and an independent consensus check | FMP/Finnhub anonymous consensus is provisional. Benzinga named-ratings adapter is ready to connect; Morningstar independent fair value is the preferred separate valuation check if affordable |
| Company guidance and earnings releases | SEC-filed issuer release or a publication on a verified official investor-relations domain | Retain the exact SEC acceptance or IR publication timestamp, metric definition, fiscal period, endpoints, unit, currency and original wording. Compare only an identical metric/definition/period/unit/currency key. Conflicts, missing timestamps and ambiguous units fail closed; no midpoint is inferred | On-demand 8-K/6-K filing-package ingestion and deterministic range comparison are connected at `/api/guidance`. Non-filed IR releases require a verified issuer domain and timezone-bearing publication timestamp |
| Proven-investor holdings | SEC Form 13F filing and information table | Use disclosed changes and portfolio conviction to discover research candidates; never treat delayed ownership as a Buy signal | Direct latest-versus-prior 13F comparison connected for eight deliberately selected long-equity managers, with CUSIP-to-ticker identity checks |
| ETF holdings and fees | Issuer holdings/prospectus plus SEC Form N-PORT | Preserve permanent fund and share-class identity, report date, exact publication/availability/retrieval clocks, lag, original units/currency, cash, derivatives, reported total, accession/source record ID, URL and hashes. Never infer weights, normalize an incomplete total, mix currencies or substitute a current portfolio for a past cutoff. Expose every named company position, but merge cross-fund records only with stable identity evidence | Append-only archive and walk-forward gate connected. The dashboard now searches all verified company rows across the six funds, including sub-basis-point positions that issuer displays round to zero. Missing or stale funds remain visibly partial. Historical collection and five untouched annual windows remain outstanding |
| Rates, inflation and economy | Original agency releases; FRED/ALFRED for observations and vintages | Backtests use only the end-of-day vintage available on the decision date; missing or stale evidence disables the label | Connected for a minimal US evidence set; context only, with no rating impact |
| Portfolio risk | Reproducible derivation from point-in-time, corporate-action-adjusted total returns | Use shrinkage covariance, factor exposures and stress scenarios; reject unstable weights | Simple concentration and beta only |

## Rating gates

### High confidence

- Instrument, listing, currency and corporate-action state are resolved.
- The current price is fresh and confirmed independently within tolerance.
- The latest official filing is present, current and free of material conflict.
- Every critical metric has complete provenance.
- Company guidance is conflict-free and clearly separated from later actual results and analyst opinion.

### Buy

- High-confidence gates pass.
- Valuation bridges directly to official reported facts.
- Growth expectations are ranges with dispersion and revisions, not a single target.
- Liquidity, position size, correlation and stressed downside all pass.

### Ultra Buy

- All High-confidence and Buy gates pass.
- Institutional point-in-time estimates and validated corporate actions are connected.
- The proposed weight improves the complete portfolio under base and stressed assumptions.
- No unresolved source conflict, stale critical field, or model warning remains.

Until those sources are connected, Kestrel caps confidence at **Medium** and disables **Ultra Buy**.

## Archived ETF evidence

`etf_evidence.py` is the holdings-and-fee evidence boundary. It accepts only an
authoritative issuer file/prospectus or SEC Form N-PORT record with a stable
fund and share-class identity, source record ID or accession, URL, SHA-256
hashes, and timezone-bearing publication, availability and retrieval times.
The normalized report retains its as-of date and reporting lag separately.

Every position keeps its source-reported units, unit name, market value,
currency and weight. Cash stays a position. A derivative keeps its contract
details; it is never flattened into an assumed equity exposure. A report is
complete only when the source declares full coverage and a reported total near
100% (or 1.0 in fractional units), cash, derivatives and currencies are all
resolved, the requested share class matches, the report was known by the
decision cutoff, and an archived share-class fee report is linked. This
tolerance detects a complete source report; Kestrel never rescales its rows.

Identical replay is idempotent. A changed source record must declare an
amendment or correction and point to the prior immutable record. Database
triggers reject updates and deletes. The universe protocol retains both report
IDs, exact clocks, reporting lag, source record IDs, URLs and hashes. A live
issuer response without that archived chain cannot open the historical
look-through gate.

## Point-in-time macro evidence

The minimal US regime set deliberately uses five official series rather than a broad,
fragile dashboard:

| Evidence | Series | Original agency and release | Derived use |
|---|---|---|---|
| Two-year Treasury yield | `DGS2` | Federal Reserve Board, H.15 Selected Interest Rates | Current rate level and yield-curve slope |
| Ten-year Treasury yield | `DGS10` | Federal Reserve Board, H.15 Selected Interest Rates | Current rate level and yield-curve slope |
| Headline CPI-U | `CPIAUCSL` | Bureau of Labor Statistics, Consumer Price Index | Twelve-month inflation and three-month direction |
| Unemployment rate | `UNRATE` | Bureau of Labor Statistics, Employment Situation | Three-month labour-market direction |
| Real GDP | `GDPC1` | Bureau of Economic Analysis, Gross Domestic Product | Latest annualised quarter-on-quarter growth |

For a cutoff date, Kestrel requests the ALFRED real-time period where
`realtime_start` and `realtime_end` both equal that cutoff. It separately records the
latest series release or revision vintage no later than the cutoff. Observation dates,
requested vintage, original agency, release, units, retrieval time and transformations
remain visible. The current cache lasts 12 hours; a historical snapshot becomes
immutable only after it has been fetched on a later calendar day.

Daily yield vintages older than 7 days, monthly release vintages older than 45 days,
or GDP vintages older than 120 days are stale. Observation ages are separately capped
at 10, 75 and 240 days respectively. A missing series, missing expected month or
quarter, mismatched yield date, insufficient history for a derived measure, stale
vintage, future cutoff or failed refresh produces an unavailable regime.
An older cache may remain visible for diagnosis after a refresh failure, but it is
marked stale and disabled. The cutoff is end-of-day only and must not be used for
intraday release decisions.

The label is a compact description for regime-stratified validation. It is not a
forecast, an NBER recession determination, or evidence about any company. Its declared
rating impact is always `none`; company filings, valuation, market integrity and
whole-portfolio evidence remain independent gates.

The descriptive rules are fixed before testing: negative latest real-GDP growth is
`contracting`; CPI inflation of at least 3% is `elevated` and below 1% is `low`; a
three-month unemployment increase of at least 0.3 percentage points is `weakening`;
and a negative 10-year minus 2-year spread is `inverted`. `downturn_risk` requires
both contracting GDP and weakening labour, while `inflationary_expansion` requires
positive GDP growth and elevated CPI. These names describe the evidence combination;
they do not declare a recession or predict returns.

## Ideal Portfolio gates

No asset receives a target weight unless:

- its identity and trading currency are unambiguous;
- its investability, liquidity and corporate-action history are clean;
- sufficient adjusted history or a documented risk proxy exists;
- the expected-return range is point-in-time and penalised for uncertainty;
- its marginal contribution to portfolio risk is understood;
- its weight remains sensible across base, bear, inflation, recession and liquidity stresses;
- the result is stable when inputs are perturbed.

The first risk engine will use Ledoit–Wolf shrinkage rather than an uncorrected sample covariance matrix. Expected returns will begin from a neutral market prior and admit Kestrel’s views only in proportion to evidence confidence, following the spirit of Black–Litterman. No optimiser output may trade automatically.

Company guidance may update a plain-English thesis, but it cannot override valuation, identity, liquidity, evidence-quality, concentration, or portfolio-risk gates. A raised range is not itself a Buy signal; a lowered range is not itself a Sell signal.

## Primary references

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC Form N-PORT: https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets
- ESMA ESEF: https://www.esma.europa.eu/issuer-disclosure/electronic-reporting
- FCA National Storage Mechanism: https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism
- OpenFIGI API: https://www.openfigi.com/api/documentation
- CTA/CQ consolidated tape: https://www.nyse.com/data/cta
- UTP Tape C: https://utpplan.com/PageParts/Overview.html
- DTCC corporate actions: https://www.dtcc.com/data-services/corporate-actions-and-reference-data
- Databento official consolidated closes: https://databento.com/docs/examples/equities/closing-prices
- Databento corporate actions and adjustment factors: https://databento.com/docs/venues-and-datasets/corporate-actions
- FRED and ALFRED observations API: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- ALFRED vintage dates API: https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- Federal Reserve H.15 Selected Interest Rates: https://www.federalreserve.gov/releases/h15/
- BLS Consumer Price Index: https://www.bls.gov/cpi/
- BLS Employment Situation: https://www.bls.gov/news.release/empsit.toc.htm
- BEA Gross Domestic Product: https://www.bea.gov/data/gdp/gross-domestic-product
- US Treasury rates feed: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- BLS public API: https://www.bls.gov/developers/home.htm
- Nasdaq market data products: https://www.nasdaqtrader.com/Trader.aspx?id=mddataproducts
- Nasdaq corporate-action Daily List: https://www.nasdaqtrader.com/Trader.aspx?id=DailyListPD
- LSEG I/B/E/S: https://www.lseg.com/en/data-analytics/financial-data/company-data/ibes-estimates
- FactSet consensus estimates: https://www.factset.com/marketplace/catalog/product/factset-estimates-consensus
- Benzinga named analyst ratings: https://docs.benzinga.com/api-reference/calendar-api/get-ratings
- Morningstar independent equity research: https://www.morningstar.com/business/products/institutional-equity-research
- MSCI Barra factor models: https://www.msci.com/data-and-analytics/factor-investing/equity-factor-models
- Ledoit–Wolf research: https://www.econ.uzh.ch/en/people/researchers/ledoit/publications.html
- Black–Litterman, *Global Portfolio Optimization*: https://rpc.cfainstitute.org/research/financial-analysts-journal/1992/faj-v48-n5-28
