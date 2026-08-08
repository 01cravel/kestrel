# Kestrel roadmap

Kestrel is decision support for long-term portfolio changes, not an automated trading system. The goal is to improve the quality of the evidence, make uncertainty visible, and measure whether past signals were actually useful.

## Foundation — complete

- One clear daily view for holdings and missed opportunities.
- Plain-English actions: Hold, Sell, Buy, and Ultra Buy.
- Confidence shown separately from the action.
- Progressive market-data loading and a local cache.
- Ultra Buy remains locked until official filings, institutional pricing, validated corporate actions, point-in-time estimates and whole-portfolio risk checks all pass.

## Delivery status

- ✅ The scientific challenger now has a pre-registered, expanding walk-forward evaluator: 36 months minimum training, non-overlapping 12-month tests, `VT` after declared costs, return, drawdown, information ratio and whole-window uncertainty. Five independent windows and strong evidence against both Candidate 1 and `VT` are mandatory.
- 🚧 **Next priority: accumulate five genuinely unseen annual windows from the frozen point-in-time universe.** Current-ticker history is rejected because it cannot prove what was known or investable at each past cutoff; the promotion gate therefore remains closed rather than presenting a selection- or survivorship-biased backtest.
- ✅ Selection-agnostic $300,000 Ultimate Portfolio for an 8/10 risk mandate, with explicit weights, explanations, stress cases and an editable capital base.
- ✅ Scientific challenger with conservative return shrinkage, covariance shrinkage, 20,000 constrained alternatives, bootstrap ranges and fail-closed promotion gates.
- ✅ Official ETF look-through for VTI, AVUV, VEA, IEMG, AVDV and PAVE. Direct and hidden company exposure is combined, source freshness and reconciliation are checked, and the challenger enforces an 8% true-company ceiling.
- 🚧 Point-in-time valuation reconstructs trailing P/E and free cash flow only from SEC facts available by each filing date, pairs them with split-normalized prices and applies the matching mechanical adjustment to old per-share facts and share counts. ASML's euro figures use official ECB rates. Cash-flow yield uses operating cash flow less productive-asset purchases and compares each company only with its own history. Every working Yahoo close is independently checked against Nasdaq's official history with an exact-date, 1% tolerance rule; missing coverage or disagreement fails closed. TSM's EPS remains stale, Amazon currently has negative free cash flow after heavy investment, and CEG has too little standalone cash-flow history for a firm conclusion.
- 🚧 A conservative five-year equity DCF keeps the original operating-cash-flow-minus-all-capex result and maintenance-versus-growth owner-cash sensitivity unchanged. A third, separate direct-FCFE view now opens only with complete point-in-time SEC evidence for cash, debt, operating and finance leases, minority interests, matched net borrowing and three historical borrowing observations. It counts normalized repayments but gives no perpetual value credit to positive borrowing. Because FCFE is already after debt cash flows, the balance-sheet claims are displayed and checked but never subtracted again. Missing components, mismatched periods, fewer than three positive cash-flow observations, inadequate beta evidence or terminal value above 80% fails closed; every output is a range, never a target.
- ✅ Private Sarwa snapshot staging, reconciliation, backups, and a review-before-apply dashboard flow.
- ✅ First signed-in Sarwa Trade capture: 24 positions, cash, account total, and a validated comparison against Kestrel.
- ✅ SEC filing verification, source links, conflict checks, and confidence gates.
- ✅ Machine-readable source hierarchy, evidence-health API, dashboard truth status, and a global Medium-confidence ceiling while critical sources remain provisional.
- ✅ Point-in-time US macro evidence from FRED/ALFRED: Federal Reserve rate-curve vintages, BLS inflation and unemployment vintages, and BEA real-GDP vintages. Historical cutoffs cannot see later revisions; missing or stale evidence disables the descriptive regime, which has no direct rating impact.
- ✅ Immutable bitemporal universe ledger: each post-close decision snapshot binds stable identities, included and excluded members, exact availability/retrieval cutoffs, evidence hashes, ETF look-through, model/policy versions and later outcomes. SQLite blocks updates and deletes; corrections and delistings append new versions. The live server starts prospective daily accumulation automatically. A separate certified snapshot opens only when the local archive proves timely adjusted closes, identities, and raw split/dividend coverage for every declared portfolio symbol; the challenger rejects any protocol not cryptographically reconstructed from this ledger.
- ✅ Permanent security master using OpenFIGI and SEC CIK, with fund/ADR handling, ambiguity refusal, and per-instrument confidence gates.
- ✅ Cost-controlled market integrity: daily prices are independently cross-checked, stale data is rejected, and adjusted histories are scanned for unexplained split-sized jumps. Databento pay-as-you-go official closes remain an optional upgrade; no $199 subscription is required.
- ✅ Interactive `1D`, `1W`, `1M`, `1Y`, `5Y`, and `All` price graph.
- ✅ Sector-aware valuation with conservative, reasonable, and optimistic ranges.
- ✅ Daily thesis, earnings-surprise history, and analyst-estimate baselines.
- ✅ Plain-English owner guide for every current holding: what it does, how it can build wealth, its biggest risk, and the exact Buy/Strong Buy analyst vote with all vote categories retained.
- ✅ Named-analyst evidence adapter for Benzinga, including firm, analyst, rating and target changes, recency, accuracy metadata and cross-provider disagreement gates. Trial access and the full-universe audit remain pending.
- ✅ No-cost company-guidance truth layer for SEC-filed 8-K/6-K earnings releases and verified official IR evidence. It preserves the publication cutoff, metric definition, fiscal period, exact range, unit, currency and original wording; rejects conflicts and ambiguity; and compares previous guidance, later actuals and consensus only on an identical key. Guidance is plain-English thesis evidence and has no authority over valuation or portfolio-risk gates.
- ✅ Opportunity-versus-holding comparisons, concentration checks, and a simple stress test.
- ✅ Point-in-time signal journal, model versions, and the first 30-day calibration method.
- ✅ Company-level SEC 13F discovery: duplicate share classes are merged, every idea shows its exact independent pass/fail result, and investor conviction is capped at a five-point decision-rank adjustment.
- 🚧 Manager-skill validation journal: new and increased positions are now stored against SPY for 90-, 180-, and 365-day review. No manager earns extra trust before ten full one-year outcomes.
- ✅ Benchmark-relative holding and portfolio performance across 1 month, 1 year, and 5 years.
- 🚧 Correlation, tax settings, and international local-market sources remain in progress.

## Immediate next — Complete the truth layer

The source policy is now explicit in [SOURCE_POLICY.md](SOURCE_POLICY.md). Kestrel currently has authoritative portfolio records, US filings and current official look-through for the six Ultimate Portfolio equity ETFs, but pricing, corporate actions, international filings, analyst expectations and the portfolio risk model are not yet strong enough for the highest-confidence decisions.

1. ✅ Build a permanent security master using FIGI plus regulator, exchange, currency and share-class identifiers. A ticker alone is not an identity.
2. 🚧 Strengthen prices and corporate actions without imposing a permanent fee. The local archive now certifies a decision session only when every declared portfolio symbol has a timely adjusted close, stable identity, and retained raw split/dividend query proof; missing or late evidence produces no partial certified snapshot. Add Databento pay-as-you-go official closes when the free account is ready, and keep mergers and delistings locked until independently evidenced. Reconsider premium reference data only after measured avoided errors or improved decisions exceed its annual cost.
3. 🚧 Add accountable analyst evidence. The Benzinga named-ratings adapter is complete and requires at least three recent firms plus agreement with the broader consensus. Test its free API trial across the full portfolio before paying. Add Morningstar independent fair value as a separate valuation check only if the licence proves worthwhile; reserve LSEG I/B/E/S or FactSet for a later institutional upgrade.
   - Preserve every analyst call exactly as published and score its 3-, 6- and 12-month result against the relevant benchmark. Vendor accuracy statistics may be shown, but Kestrel’s own point-in-time outcome record decides how much trust each analyst earns.
4. 🚧 Issuer holdings are connected and fail closed when stale or incomplete. Add prospectus fees, archived point-in-time holdings and SEC Form N-PORT before historical look-through testing.
5. 🚧 As-filed SEC earnings, free-cash-flow valuation and the independent Nasdaq historical-price cross-check are connected for all eight direct companies. Add enough current TSM earnings and CEG cash-flow history before this gate can pass.
6. 🚧 The maintenance-versus-growth model now feeds a separately gated, balance-sheet-vetted FCFE range. Cash, debt, leases, minority interests and net borrowing retain their SEC tags, filing dates and periods; incomplete or mismatched evidence closes the gate. Add directly quantified maintenance disclosures where issuers provide them and build longer complete net-borrowing histories before this lens can pass across the portfolio.
7. ✅ Add FRED/ALFRED and original-agency vintages for rates, inflation and macro regimes. The first five-series US set is connected as end-of-day research context only. Validate regime-stratified results across multiple cycles before considering any capped model influence.
8. Expand official filing ingestion market by market through ESMA ESEF, FCA NSM and local regulators.
9. Only then unlock High confidence, Ultra Buy and Ideal Portfolio target weights that depend on those inputs.

### No-cost accuracy upgrades before another data subscription

1. ✅ Ingest SEC Form 4 insider purchases and sales directly, separating meaningful open-market buying from routine share awards and tax sales. `sec_events.py` counts only transaction codes P and S; awards, option exercises, tax withholding, gifts and conversions are excluded because the insider chose neither timing nor price. Sales made under a pre-arranged 10b5-1 plan are recorded separately from discretionary ones. Across 28 holdings this found three genuine open-market purchases in 180 days against $700m of selling — a ratio that only means anything because awards are not counted as buying.
2. ✅ Ingest SEC 13F filings directly and compare institutional positions quarter by quarter, while clearly showing the reporting delay. Eight long-equity managers now feed a separate research-candidate tape; share classes are merged at company level, every discovery receives an exact independent verdict, and disclosed conviction can refine—but never override—the research and confidence gates.
3. ✅ Capture company-issued guidance and earnings releases from SEC filings and verified investor-relations evidence, then compare management’s latest range with its previous range, later actual result and analyst consensus only when metric, definition, period, unit and currency match exactly.
4. Compare each valuation with the company’s own history and genuinely similar businesses; never use a broad sector average when the business model is materially different.
5. Preserve the full monthly analyst vote distribution and flag improving or weakening breadth, rather than relying only on today’s consensus percentage.
6. Measure every Kestrel Buy, Hold and Sell against later returns, drawdowns, earnings changes and the correct benchmark before increasing the weight of any signal.

## Immediate next — Mission and Ideal Portfolio

**Mission:** Maximise long-term wealth using the strongest evidence Kestrel can obtain, at a target risk level of 8/10. The horizon is open-ended, the investable universe is global, and no industry or sector receives a preference. Existing holdings must not influence the ideal answer; they are compared with it only after the target portfolio is built.

- Keep two separate views: **Current Portfolio** explains what Luke owns; **Ideal Portfolio** shows what Kestrel would choose from scratch.
- Treat the open-ended horizon, global universe, sector neutrality, and 8/10 risk appetite as locked. Add liquidity needs, expected contributions, tax position, base currency, exclusions, and maximum acceptable drawdown when they become relevant to the transition plan.
- Treat 8/10 as an aggressive risk budget, not permission for uncontrolled concentration. Measure both Luke’s willingness to take risk and his financial capacity to withstand losses.
- Search a broad global universe without sector quotas, then filter for source quality, liquidity, financial strength, valuation, durable growth, governance, and evidence freshness.
- Build the core asset allocation before choosing individual names. Diversify across companies, sectors, countries, currencies, and return drivers.
- Optimise for robust long-term risk-adjusted wealth, not the most optimistic point forecast. Use expected-return ranges, volatility, correlations, stress scenarios, and estimation-error penalties.
- Set explicit limits for single positions, sectors, countries, speculative holdings, crypto, and correlated themes. An 8/10 portfolio may be aggressive while still refusing uncompensated risk.
- Show the ideal weights, the current weights, the difference, why each asset earned its place, expected range of outcomes, and the largest plausible drawdown.
- Create a separate transition plan that accounts for taxes, trading costs, liquidity, and turnover. Never distort the ideal portfolio merely to defend an existing choice.
- Backtest only with point-in-time data, then run proposed changes in shadow mode. Never call a portfolio “perfect” or allow it to trade automatically.

## Immediate priority — Sarwa connection

The aim is to replace manual share counts and costs with a dependable view of the real Sarwa account. This connection must remain read-only: Kestrel may collect and reconcile portfolio data, but it must never place trades, move money, change account settings, or weaken Sarwa security.

### 1. Ask for the safest official route first

- Contact Sarwa support and request a documented read-only portfolio API, partner feed, or complete machine-readable export for Sarwa Trade and Sarwa Invest.
- Confirm the permitted refresh rate, authentication method, account coverage, data fields, and whether automated personal access is allowed.
- Prefer an official API or export over browser automation whenever one becomes available.
- Record the integration method and Sarwa’s answer in the evidence log; do not infer permission from an undocumented internal endpoint.

### 2. Build statement import as the dependable baseline

- Import Sarwa Invest activity statements downloaded from the web dashboard and Sarwa Trade monthly statements from the app.
- Parse holdings, share counts, average prices, cash, deposits, withdrawals, dividends, fees, and transactions where supplied.
- Preview all changes before applying them and clearly flag missing, duplicated, or conflicting rows.
- Keep the original statement locally as the source record and never publish it to Git.

### 3. Add a guarded desktop sync only if no official integration exists

- ✅ Use Luke’s existing signed-in desktop browser session to read Sarwa Trade balance, cash, and positions without storing credentials.
- ✅ Run the same verified capture every day at 12:30 PM Dubai time and surface a clear login-needed message when the session expires.
- Schedule Sarwa Invest/Save checks after the normal daily update window; these accounts reflect the previous market close and usually update before noon.
- Never store the Sarwa password or email OTP in Kestrel. Pause and ask Luke to complete login whenever Sarwa requires two-factor authentication.
- Restrict automation to an explicit read-only list of portfolio and statement pages. Do not expose trade, transfer, withdrawal, funding, security, or account-setting actions to the sync.
- Stop safely if the page structure changes, a login challenge appears, expected totals disappear, or the extracted figures fail validation.
- Save a timestamped snapshot, source page, account type, currency, and reconciliation result for every sync.

### 4. Reconcile before replacing portfolio data

- Compare Sarwa holdings with Kestrel’s previous snapshot, current market prices, and the latest downloaded statement.
- Show additions, removals, share-count changes, cost-basis changes, cash movements, and unexplained differences before updating the main dashboard.
- Never silently remove a holding. Keep the last known-good portfolio and an automatic backup so a failed scrape cannot overwrite real data.
- Display connection health in plain English: last successful sync, source, account coverage, holdings found, and any figures needing review.

### 5. Unlock true portfolio performance

- Use dated trades, deposits, withdrawals, dividends, fees, and cash to calculate Luke’s actual account performance rather than assuming today’s holdings existed for the full period.
- Add time-weighted return for investment performance and money-weighted return for Luke’s personal outcome.
- Compare the real portfolio with SPY and later with suitable international benchmarks over matching dates.
- Keep Sarwa-reported performance beside Kestrel’s calculation and flag material disagreements.

## 1. Trust and verification

- Use official SEC filings and structured XBRL data as the source of truth for US company fundamentals.
- Cross-check important figures with a second independent data source.
- Show the source and effective date beside every important claim.
- Detect stale prices, stock splits, currency mistakes, unusual units, and conflicting figures.
- Withhold or cap a rating when evidence is missing, old, or contradictory.
- Keep an evidence trail explaining exactly why each daily rating was produced.

## 2. Valuation and price history

- ✅ Rank owned companies in a research league table using MSCI's published Core Multiple-Factor structure, with visible analyst agreement, value, quality, results, trend, source coverage, and portfolio weight.
- ✅ Insert qualified unowned opportunities into the league table and flag material stock-weight mismatches against a neutral diversified allocation.
- ✅ Add one-year daily-return correlation, annualized covariance, portfolio-risk contribution, and an explicit country-neutral US/global opportunity audit.
- ✅ Replace the fixed watchlist as the sole idea source with direct SEC 13F discovery across eight long-term managers. Show new and increased positions, independent agreement, disclosed portfolio conviction, filing dates and the 45-day reporting limitation; every idea must still pass Kestrel's separate company checks.
- Use the P/E ratio alongside forward P/E, free-cash-flow yield, debt, growth, margins, and return on capital.
- Apply valuation measures that suit the business: price-to-book and return on equity for banks, FFO for property companies, normalized earnings for cyclical companies, and cash-flow or unit economics for growth companies.
- Produce conservative, base, and optimistic fair-value ranges instead of one deceptively precise target.
- Add an interactive price-history graph for every holding and opportunity with `1D`, `1W`, `1M`, `1Y`, `5Y`, and `All` ranges.
- Use intraday data for `1D`, adjusted historical prices for longer periods, and clearly state when the available history is limited.
- Include an exact-value tooltip, percentage change for the selected period, earnings markers, and a benchmark comparison where useful.
- Compare each holding and today’s portfolio with the S&P 500 across 1 month, 1 year, and 5 years, clearly separating this from personal account returns.
- Later add a portfolio-level performance graph against a suitable benchmark, with deposits and withdrawals separated from investment returns.

## 3. Analyst, filing, and event intelligence

- Focus on changes in earnings forecasts, guidance, price targets, and recommendation breadth—not just the headline consensus.
- Weight analyst opinions by recency, independence, coverage history, and past accuracy where reliable data exists.
- Show disagreement between analysts because wide disagreement means lower confidence.
- Compare each new filing, earnings release, and management update with the previous one.
- Maintain a plain-English thesis for every holding: why it is owned, the important measures, the main risks, and the evidence that would change the decision.
- Flag thesis improvements and thesis breaks immediately.

## 4. Opportunity and portfolio intelligence

- 🚧 Expand the opportunity radar beyond a fixed watchlist while keeping minimum quality and liquidity standards. Direct 13F discovery is connected for US-listed long positions; broader global screens, insider buying and local-market filings remain next.
- Compare every opportunity with the portfolio's weakest holding, not only with other unowned stocks.
- Explain when a replacement could improve expected return, diversification, quality, or downside protection.
- Measure concentration by company, sector, country, currency, and investment theme.
- Add correlation, stress tests, maximum-position guidance, and portfolio drawdown risk.
- Include transaction costs, tax assumptions, and the cost of holding cash before recommending a change.

## 5. Recursive learning and calibration

### Current position

Kestrel has the beginnings of a learning record, not yet a learning system:

- ✅ Both journals are append-only. A prediction is written once, never rewritten by a later submission on the same day, and never pruned by age.
- ✅ Outcomes are graded independently. `outcome_source.py` reads the archive's split- and dividend-adjusted closes, enters one session after the decision rather than at the decision price, measures the result against SPY over 30, 90 and 180 days, and takes the maximum drawdown from every session in the holding period. A result inside the declared round-trip cost band counts as neither a hit nor a miss.
- ✅ Kestrel refuses to grade itself. Where the archive cannot cover a prediction, or a corporate action inside the holding period is unresolved, the call is reported as awaiting or not gradeable instead of scored. Manager ideas measured only from Kestrel's own snapshots are shown as provisional and never count toward validation.
- ✅ The rule-based score remains the approved **champion**. No journal outcome changes its inputs or weights automatically.
- ✅ The learning loop is built and runs end to end: features, labelled research set, walk-forward validation with purging, a base-rate champion, a logistic challenger, calibration, promotion gates, a shadow journal and a model-risk report. `python3 learning.py status` reports what it can honestly say; nothing it produces reaches a displayed rating.
- 🚧 The journals still fall short of evidence for changing signals: they do not yet retain full evidence and feature snapshots, include delisting proceeds, evaluate Hold decisions and missed opportunities, or calculate uncertainty.
- 🚧 "Confidence" currently describes evidence completeness. It is not a forecast probability and must not be presented as calibrated until it has passed formal calibration tests.

### Non-negotiable design

Learning means controlled evidence accumulation, not autonomous self-retraining. Every model or scoring change must be reproducible, reviewable, shadow-tested and explicitly approved before it changes a live recommendation.

1. Preserve the approved rule-based score as the champion until a challenger passes every gate below.
2. Keep facts, analyst opinions and model outputs separate. A model may transform evidence; it can never promote its own output into a fact.
3. Freeze the daily decision snapshot at a documented New York market-time cutoff. Any filing, estimate, corporate action or price arriving later belongs to the next decision session.
4. Use only information Kestrel could have known at that cutoff. Never join a historical decision to today's revised fundamentals, adjusted universe or consensus estimate.
5. Retain predictions forever as immutable records. Later outcomes are appended; they never overwrite the original evidence or prediction.
6. No model may place a trade, override source-quality, identity, liquidity, valuation, concentration or portfolio-risk gates, or move a rating by more than one level on its own.

### The three questions Kestrel must keep separate

| Question | Output | Initial label and horizon |
|---|---|---|
| **Big move** | Probability of an unusually large move, regardless of sign | 1- and 5-session event label: absolute cumulative abnormal total return crosses the larger of 5% or twice the ex-ante horizon volatility |
| **Direction** | Probabilities of outperformance, neutral result and underperformance | 30-, 90-, 180- and 252-session benchmark-relative total return after costs; neutral is inside a pre-declared volatility- and cost-aware band |
| **Investment-worthiness** | A portfolio recommendation, not a stock-price prediction | Add, hold, reduce or replace only when expected net benefit, downside, evidence quality and marginal portfolio contribution all pass |

A stock can be likely to rise yet still be unsuitable to buy: expected upside may be too small after costs, the downside may be unacceptable, the position may deepen an existing concentration, or a better opportunity may exist. Investment-worthiness is therefore a constrained portfolio decision, not a binary price label.

### Point-in-time evidence layer

Build an immutable, bitemporal evidence ledger. Each raw observation must retain both the period it describes and the moment Kestrel could first have known it.

Required fields for every decision-critical fact:

- permanent issuer, instrument and listing identifiers; ticker is only a convenience label;
- source, source record ID or SEC accession, source tier and licence;
- report period, effective time, publication/acceptance time and retrieval time;
- original value, normalized value, unit, currency, revision/amendment state and quality flags;
- transformation code version and content hash;
- the feature set, prediction, decision, model version and later outcome derived from it.

The historical investable universe must retain active and inactive listings, IPOs, mergers, suspensions, delistings, historical identifiers, liquidity screens and point-in-time membership. Return histories must use corporate-action-adjusted total returns and include delisting proceeds. A current ticker list or retrospectively adjusted price series is not sufficient for a backtest.

### Exact learning loop

1. **Ingest and validate.** Collect official filings, prices, corporate actions, estimates and macro releases. Reject unresolved identity, stale price, currency, unit and source conflicts before feature construction.
2. **Freeze the information set.** Create one immutable daily snapshot after the market-time cutoff, using only observations published by then.
3. **Build features.** Derive versioned quality, valuation, estimate-revision, event, momentum, risk and portfolio features. Missingness remains visible and reduces confidence.
4. **Predict with champion and challenger.** Store full probability distributions, uncertainty and rationale for each eligible instrument. Publish only the approved champion.
5. **Mature outcomes independently.** Measure next-eligible-session entry and later total-return, abnormal-return, drawdown, earnings, thesis and portfolio outcomes from an independent adjusted data source.
6. **Train only on schedule.** Add matured outcomes to the research set continuously, but retrain challengers no more than quarterly and never alter the live model automatically.
7. **Validate chronologically.** Use nested, expanding walk-forward tests with at least five outer test periods. Tune inside earlier data only; purge training rows whose outcome window overlaps validation and leave a gap at least as long as the relevant outcome horizon.
8. **Calibrate separately.** Fit any probability calibrator on a later, separate chronological slice. Start with simple logistic calibration; use more flexible calibration only when sample size supports it.
9. **Simulate the portfolio decision.** Apply realistic entry delay, transaction costs, taxes, position limits, liquidity, correlations, stress scenarios and turnover before judging investment-worthiness.
10. **Review and shadow.** Register every experiment and comparison. A challenger must run live in shadow mode before it can receive a capped contribution to a recommendation.

### Event studies

For filings, earnings, guidance, analyst actions, insider trades and major corporate events:

- record the first public timestamp and classify the event type;
- estimate expected return only from pre-event data, excluding the event window;
- measure abnormal total return over pre-declared windows such as `[0, 1]`, `[0, 5]` and `[1, 20]` trading sessions;
- merge or flag overlapping events from the same issuer rather than attributing one price move to several causes;
- compare results by event type, sector, size, market regime and source quality.

An event study measures market reaction; it does not prove a causal explanation or a future investment return.

### Success measures

**Big-move model**

- precision-recall lift over the unconditional event rate;
- recall at Kestrel's fixed daily alert budget;
- Brier score, log loss and reliability plots;
- false alarms per 100 alerts, broken down by volatility and market regime.

**Direction model**

- Brier score and log loss for outperformance/neutral/underperformance;
- rank correlation between forecast and later benchmark-relative return;
- net top-minus-bottom spread, false positives and missed opportunities;
- clustered confidence intervals by date and issuer.

**Investment-worthiness and portfolio model**

- incremental net return and information ratio versus doing nothing;
- factor-aware performance, not SPY alone;
- drawdown, expected shortfall, turnover, tax and transaction-cost drag;
- marginal contribution to concentration and portfolio risk;
- realised regret versus the best eligible alternative;
- stability under base, bear, inflation, recession and liquidity stresses.

Hit rate remains a useful diagnostic, but is never a sufficient success measure.

### Gates before a challenger changes a live signal

1. **Data gate:** complete lineage for every decision-critical field; no unresolved identity or corporate-action break in the eligible universe.
2. **Reproducibility gate:** rebuilding any prior decision snapshot reproduces the same features and prediction.
3. **Leakage gate:** automated as-of joins and overlap tests report zero future-information violations.
4. **Statistical gate:** the challenger improves proper forecast scores over the champion and a simple base-rate benchmark in at least four of five outer walk-forward periods, with uncertainty intervals that do not include zero improvement.
5. **Calibration gate:** positive Brier skill; calibration slope between 0.8 and 1.2; no material overconfidence by confidence band, market regime or sector.
6. **Economic gate:** positive incremental portfolio result after conservative costs, without relying only on known factor exposures or a handful of outcomes.
7. **Robustness gate:** result survives delayed execution, doubled costs, threshold perturbation, removal of the best decile of outcomes and major regime splits.
8. **Shadow gate:** at least 12 months and 200 matured independent short-horizon forecasts. The 252-session investment model additionally requires at least 100 matured outcomes across two materially different market regimes.
9. **Deployment gate:** approved human review; initial influence capped at 10% of the evidence score; immediate rollback path to the former champion.

### Phased build

#### Phase A — Make the current journals research-grade

- ✅ Make daily prediction records append-only. Preserving the full evidence and feature snapshot remains outstanding.
- ✅ Replace snapshot-to-snapshot price checks with independent adjusted total-return outcomes.
- 🚧 Record entry convention, benchmark, costs, corporate actions, delisting state and complete maximum drawdown. Entry convention, benchmark, a declared cost band, corporate-action cleanliness and full-path drawdown are stored; delisting state is not.
- Evaluate Hold decisions and missed opportunities, not only Buy and Sell calls.
- 🚧 Report outcomes separately by model version, horizon, action, confidence band, issuer and decision date. Horizon and confidence band are reported; the remaining breakdowns are outstanding.

#### Phase B — Establish an honest historical research dataset

- ✅ Build the bitemporal security master and point-in-time universe. `universe_ledger.py` freezes append-only daily manifests, identity valid time, retained exclusions, ETF holdings and later outcomes; `market_history.py` retains monthly active references plus inactive/delisted records and certifies exact daily bars and raw action-query proofs before the server opens its price/action controls. Five untouched annual windows must still mature before validation can pass.
- Reconstruct US fundamentals from official filing acceptance times and preserve amendments/restatements.
- ✅ Introduce macro-release vintages. Historical benchmark/factor data remains outstanding.
- ✅ Leakage-safe walk-forward evaluation exists in `validation.py`: expanding folds, training rows purged when their outcome window overlaps the test period, an embargo of at least one horizon, and an automated future-information check that must return clean before anything is scored.

#### Phase C — Create simple, interpretable challengers

- ✅ A regularised logistic challenger answers the big-move and direction questions separately, fitted by penalised Newton steps and reporting readable standardised coefficients. The incumbent it must beat is the plain base rate.
- ✅ Feature ablation removes one family at a time and reports how much the score worsens without it.
- ✅ Probability calibration is fitted on a later slice the weights never saw, and reported through Brier score, log loss, skill against the base rate, reliability bins, calibration slope and intercept, and confidence intervals bootstrapped by decision date rather than by row.
- Do not add more complex models unless they deliver stable out-of-time improvement after all costs and gates.

#### Phase D — Build the portfolio decision layer

This phase is deliberately not started. It converts calibrated forecasts into portfolio decisions, and Kestrel has no calibrated forecast yet — no challenger has passed the gates, so there is nothing trustworthy to convert. Building it now would dress up an uncalibrated probability as a portfolio recommendation, which is the exact failure the rest of this section exists to prevent.

- Convert calibrated forecasts into constrained add/hold/reduce/replace proposals.
- Use shrinkage covariance, factor exposures, neutral market priors and stress testing.
- Compare candidates with the current portfolio and the best alternative, rather than rewarding an isolated attractive stock.

#### Phase E — Shadow, approve and monitor

- ✅ `learning.py shadow` refits on fully matured history only, predicts forward for the newest session, and freezes each prediction with a content hash before any outcome exists. Shadow predictions never appear as an action, and a shadow model can never reach the visible research-alert state.
- ✅ `model_risk.py` produces the monthly review: feature drift, prediction drift, calibration error, reliability, realised outcomes and a named model-risk event for anything that needs a documented resolution.
- ✅ The promotion gates in `swing_radar_policy.promotion_failures` are now fed by real recorded shadow behaviour through `shadow_journal.promotion_metrics`, instead of being unreachable code. Human acceptance of worst loss, false alerts and missing data remains a gate that no amount of good numbers can satisfy.
- Permit only gated, capped, reversible live influence after the full shadow period. No model has been promoted; nothing influences a live recommendation.

### Data-source plan

#### Available now or at low cost

- SEC EDGAR submissions, XBRL Company Facts, Forms 4, 13F and N-PORT for US filings and ownership.
- ALFRED, Treasury, BLS and BEA releases for macro data vintages.
- Nasdaq directories and Daily List, exchange notices, SEC Form 25 and OpenFIGI for identity support.
- Kenneth French factor data for research benchmarks.
- Current Yahoo, Finnhub and FMP feeds as provisional cross-checks and for prospective snapshot collection.
- Databento historical pay-as-you-go data and free credits to validate official market-data integration.

This tier is enough to build the evidence ledger, prospective shadow programme and selected US historical reconstruction. It is not enough for a trustworthy broad-universe historical backtest because current aggregator histories may omit dead companies, overwrite fundamental history or apply corporate-action adjustments retrospectively.

#### Paid sources in priority order

1. **Sharadar full US dataset:** first learning-specific purchase. Point-in-time/as-reported fundamentals plus active and delisted US equity coverage materially reduce restatement and survivorship bias.
2. **Databento security master and corporate actions:** next market-integrity purchase. Point-in-time listing status, identifiers and corporate actions improve returns, identity and delisting treatment.
3. **FactSet point-in-time consensus or LSEG I/B/E/S:** buy only after an ablation study shows estimate history adds material incremental value. These are the institutional sources for historical estimate revisions and global coverage.
4. **CRSP plus Compustat Point-in-Time through WRDS:** gold-standard independent US research validation when institutional or academic access is justified; confirm product-redistribution rights before use.
5. **Benzinga named ratings and Morningstar research:** valuable secondary evidence for event attribution and independent valuation, but not substitutes for a complete point-in-time universe, market or consensus dataset.
6. **Low-cost delisted-data vendors:** useful for prototyping, but remain provisional until Kestrel has independently validated coverage, timestamps and corporate-action treatment.

### Governance and lineage

- ✅ Maintain a model inventory: purpose, owner, scope, inputs, intended use, limitations, version, approval status and rollback version. `model_registry.py` holds it as append-only entries; an approval change adds a superseding entry rather than editing history.
- ✅ Maintain an experiment registry covering every feature, threshold, model and portfolio rule tested, including rejected variants. Every run is recorded with its verdict and its failed gates, whether it passed or not.
- Require independent challenge before promotion: a reviewer verifies point-in-time integrity, labels, code, sample construction, costs and conclusions.
- Monitor input coverage, source drift, feature drift, prediction drift, calibration, realised downside, turnover and exception rates.
- Treat a source failure, material restatement, corporate-action mismatch, calibration breach or data-quality incident as a model-risk event requiring documented resolution.
- Use W3C PROV-style lineage concepts so a user can trace a recommendation through evidence, transformations, model version and outcome.

### Evidence base

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- ALFRED real-time vintages: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- MacKinlay, *Event Studies in Economics and Finance*: https://www.bu.edu/econ/files/2011/01/MacKinlay-1996-Event-Studies-in-Economics-and-Finance.pdf
- CFA Institute, *Investment Model Validation*: https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/rf-brief/investment-model-validation.pdf
- Gneiting and Raftery, proper scoring rules: https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf
- Federal Reserve model-risk guidance: https://www.federalreserve.gov/frrs/guidance/supervisory-guidance-on-model-risk-management.htm
- Shumway, delisting bias: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1997.tb03818.x

### Daily Mover Autopsy and recursive opportunity learning

Build a separate daily research loop that studies the market's largest genuine rises and falls, including companies Luke did not own. Its purpose is to discover repeatable, investable clues without contaminating the long-term portfolio score with hindsight.

**Foundation status — 2 August 2026:**

- ✅ Phase 1: the investable universe, swing definitions, no-hindsight rules, success measures, alert limits and shadow-to-live safety gates are fixed in a versioned, tested policy.
- ✅ Phase 2 build: the resumable two-year Massive market-history pipeline, corporate-action handling, SPY-relative labels, validation and audit trail are implemented and tested.
- ✅ Phase 2 prices: 499 completed US sessions and 5.67 million daily bars are stored locally through 31 July 2026. Point-in-time market value still needs an additional historical source; Kestrel leaves it unknown rather than substituting today's value.
- ✅ First autopsy screen: liquid common shares are ranked by benchmark-relative move, with pre-move price/volume evidence and strict no-hindsight labels.
- 🚧 Catalyst evidence: REPL, IESC and RBLX have timestamped official-source explanations for 31 July. Unverified causes remain visibly unverified.
- 🚧 First forward shadow list: five pre-event predictions were frozen on 3 August for the week ending 7 August. Direction is withheld until a validated model earns the right to state it.
- 🚧 Each shadow candidate now shows an experimental chance of a 10% benchmark-relative rise, based on its SEC-timestamped earnings reactions and shrunk toward the peer base rate. It remains uncalibrated until the frozen journal matures.
- ✅ The two-year archive's strongest provisional big-move clues now appear beside every frozen candidate as a separate setup score. Kestrel keeps this distinct from bullish probability and does not multiply overlapping clues into false precision.

1. **Freeze the evidence first.** At each market close, save the top gainers and losers across a liquid, investable global universe together with the price, volume, market value, float, short interest, options-implied move and every source timestamp. Exclude penny-stock distortions, reverse splits, stale prices and untradeable names unless they are shown in a clearly labelled speculative section.
2. **Explain what happened.** Link each exceptional move to the earliest credible catalyst: regulator decision, trial result, earnings, guidance, takeover, contract, court ruling, filing, macro shock or no verified public explanation. Prefer regulator, exchange, company filing and official-agency sources; preserve competing explanations when causality is uncertain.
3. **Reconstruct only what was knowable beforehand.** Create a time-stamped pre-event dossier containing the public event calendar, earlier filings, estimate revisions, insider and institutional changes, short interest, unusual options pricing, price/volume behaviour, valuation, balance-sheet survival risk and comparable historical events. Never use a document published after the decision in the pre-event record.
4. **Separate three questions.** Show whether the event was predictable, whether the direction was predictable, and whether the payoff justified the risk. A known FDA date with an unknowable committee vote is a flagged binary catalyst—not a retrospective Buy.
5. **Measure surprise and amplification.** Compare the actual move with the options-implied move and normal volatility. Identify short squeezes, thin floats, crowded positioning and liquidity gaps as amplifiers, not as the underlying business catalyst.
6. **Compare with a control group.** For every apparent clue, examine similar companies that had the same clue but did not jump. Use event studies, base rates and walk-forward tests so Kestrel learns from failures as well as spectacular winners.
7. **Create a daily plain-English card.** Answer: what moved, why, what was public beforehand, what was genuinely unforeseeable, what Kestrel would have flagged before the event, what the downside was, and whether the lesson changes tomorrow's opportunity radar.
8. **Keep learning guarded.** Score every pre-event flag with later returns, drawdown, Brier calibration and benchmark-relative results. Proposed rules run in shadow mode first, require a meaningful sample, remain versioned and reviewable, and never automatically rewrite the live Buy/Sell model.
9. **Feed only proven lessons back.** A recurring clue may affect the opportunity radar only after out-of-sample evidence shows that it improves results after spreads, slippage and failed events. One dramatic winner can generate a research hypothesis but can never create a rule by itself.

**First case study — REPL, 31 July 2026:** reconstruct the public FDA timeline, the negative staff briefing, the advisory-panel vote, the scheduled 2 August decision, the stock's extreme short interest and the resulting price reaction. Label the meeting as knowable, the favourable 10–3 vote as uncertain beforehand, and the crowded short position as a likely move amplifier. Use this as the acceptance test for the first Mover Autopsy screen.

## 6. International expansion

- Current international names are US-listed shares or ADRs and use SEC filings; this is not yet the same as direct local-market coverage.
- Add one market at a time, starting with markets that provide dependable official digital filings.
- Normalize currencies, reporting periods, accounting standards, share classes, and local market conventions.
- Add country, governance, political, liquidity, and currency risks without burying the main decision.
- Select a suitable local benchmark and valuation method for each market.

## Daily experience

The main screen should remain simple even as the intelligence underneath becomes deeper. Every assessment should answer:

1. What changed?
2. What is the suggested action?
3. How confident is Kestrel?
4. What evidence supports it?
5. What is the main risk?
6. What would change the rating?

Kestrel should never present certainty that the evidence does not justify, and it should never place a trade automatically.

## Recommended build order

1. Mission profile and written investment policy constraints.
2. Global investable-universe and evidence-quality filters.
3. Correlation, drawdown, and stress-test engine.
4. Selection-agnostic Ideal Portfolio with target weights and ranges.
5. Current-versus-Ideal gap and cost-aware transition plan.
6. International markets, one verified source set at a time.
