# Kestrel roadmap

Kestrel is decision support for long-term portfolio changes, not an automated trading system. The goal is to improve the quality of the evidence, make uncertainty visible, and measure whether past signals were actually useful.

## Foundation — complete

- One clear daily view for holdings and missed opportunities.
- Plain-English actions: Hold, Sell, Buy, and Ultra Buy.
- Confidence shown separately from the action.
- Progressive market-data loading and a local cache.
- Ultra Buy remains locked until official filings, institutional pricing, validated corporate actions, point-in-time estimates and whole-portfolio risk checks all pass.

## Delivery status

- 🚧 **Next priority: build Luke’s selection-agnostic Ideal Portfolio for an 8/10 risk mandate.**
- ✅ Private Sarwa snapshot staging, reconciliation, backups, and a review-before-apply dashboard flow.
- ✅ First signed-in Sarwa Trade capture: 24 positions, cash, account total, and a validated comparison against Kestrel.
- ✅ SEC filing verification, source links, conflict checks, and confidence gates.
- ✅ Machine-readable source hierarchy, evidence-health API, dashboard truth status, and a global Medium-confidence ceiling while critical sources remain provisional.
- ✅ Permanent security master using OpenFIGI and SEC CIK, with fund/ADR handling, ambiguity refusal, and per-instrument confidence gates.
- ✅ Cost-controlled market integrity: daily prices are independently cross-checked, stale data is rejected, and adjusted histories are scanned for unexplained split-sized jumps. Databento pay-as-you-go official closes remain an optional upgrade; no $199 subscription is required.
- ✅ Interactive `1D`, `1W`, `1M`, `1Y`, `5Y`, and `All` price graph.
- ✅ Sector-aware valuation with conservative, reasonable, and optimistic ranges.
- ✅ Daily thesis, earnings-surprise history, and analyst-estimate baselines.
- ✅ Plain-English owner guide for every current holding: what it does, how it can build wealth, its biggest risk, and the exact Buy/Strong Buy analyst vote with all vote categories retained.
- ✅ Named-analyst evidence adapter for Benzinga, including firm, analyst, rating and target changes, recency, accuracy metadata and cross-provider disagreement gates. Trial access and the full-universe audit remain pending.
- ✅ Opportunity-versus-holding comparisons, concentration checks, and a simple stress test.
- ✅ Point-in-time signal journal, model versions, and the first 30-day calibration method.
- ✅ Company-level SEC 13F discovery: duplicate share classes are merged, every idea shows its exact independent pass/fail result, and investor conviction is capped at a five-point decision-rank adjustment.
- 🚧 Manager-skill validation journal: new and increased positions are now stored against SPY for 90-, 180-, and 365-day review. No manager earns extra trust before ten full one-year outcomes.
- ✅ Benchmark-relative holding and portfolio performance across 1 month, 1 year, and 5 years.
- 🚧 Correlation, tax settings, and international local-market sources remain in progress.

## Immediate next — Complete the truth layer

The source policy is now explicit in [SOURCE_POLICY.md](SOURCE_POLICY.md). Kestrel currently has authoritative portfolio records and US filings, but pricing, corporate actions, security identity, international filings, fund look-through, analyst expectations and the portfolio risk model are not yet strong enough for the highest-confidence decisions.

1. ✅ Build a permanent security master using FIGI plus regulator, exchange, currency and share-class identifiers. A ticker alone is not an identity.
2. 🚧 Strengthen prices and corporate actions without imposing a permanent fee. The default layer now uses two price feeds, stale-data checks, public split events and adjusted-history discontinuity detection. Add Databento pay-as-you-go official closes when the free account is ready. Reconsider premium reference data only after measured avoided errors or improved decisions exceed its annual cost.
3. 🚧 Add accountable analyst evidence. The Benzinga named-ratings adapter is complete and requires at least three recent firms plus agreement with the broader consensus. Test its free API trial across the full portfolio before paying. Add Morningstar independent fair value as a separate valuation check only if the licence proves worthwhile; reserve LSEG I/B/E/S or FactSet for a later institutional upgrade.
   - Preserve every analyst call exactly as published and score its 3-, 6- and 12-month result against the relevant benchmark. Vendor accuracy statistics may be shown, but Kestrel’s own point-in-time outcome record decides how much trust each analyst earns.
4. Add issuer holdings, prospectus fees and SEC Form N-PORT for ETFs.
5. Add FRED/ALFRED and original-agency vintages for rates, inflation and macro regimes.
6. Expand official filing ingestion market by market through ESMA ESEF, FCA NSM and local regulators.
7. Only then unlock High confidence, Ultra Buy and Ideal Portfolio target weights that depend on those inputs.

### No-cost accuracy upgrades before another data subscription

1. Ingest SEC Form 4 insider purchases and sales directly, separating meaningful open-market buying from routine share awards and tax sales.
2. ✅ Ingest SEC 13F filings directly and compare institutional positions quarter by quarter, while clearly showing the reporting delay. Eight long-equity managers now feed a separate research-candidate tape; share classes are merged at company level, every discovery receives an exact independent verdict, and disclosed conviction can refine—but never override—the research and confidence gates.
3. Capture company-issued guidance and earnings releases from SEC filings and investor-relations pages, then compare management’s latest range with its previous range and the analyst consensus.
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

## 5. Learning and calibration

- Save every daily rating, confidence level, evidence set, valuation, and model version exactly as it appeared at the time.
- Compare signals with later returns, earnings changes, drawdowns, and thesis outcomes.
- Use point-in-time data and walk-forward tests so future information cannot leak into historical results.
- Track hit rate, false alarms, missed opportunities, downside after Buy signals, and upside after Sell signals.
- Measure whether confidence is calibrated—for example, whether High-confidence calls are genuinely more dependable than Medium-confidence calls.
- Test proposed scoring changes in shadow mode before they affect live recommendations.
- Keep scoring changes versioned and reviewable; do not allow an opaque model to retrain itself automatically.

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
