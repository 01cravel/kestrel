# Kestrel roadmap

Kestrel is decision support for long-term portfolio changes, not an automated trading system. The goal is to improve the quality of the evidence, make uncertainty visible, and measure whether past signals were actually useful.

## Foundation — complete

- One clear daily view for holdings and missed opportunities.
- Plain-English actions: Hold, Sell, Buy, and Ultra Buy.
- Confidence shown separately from the action.
- Progressive market-data loading and a local cache.
- Ultra Buy locked until independent official-source checks are available.

## 1. Trust and verification

- Use official SEC filings and structured XBRL data as the source of truth for US company fundamentals.
- Cross-check important figures with a second independent data source.
- Show the source and effective date beside every important claim.
- Detect stale prices, stock splits, currency mistakes, unusual units, and conflicting figures.
- Withhold or cap a rating when evidence is missing, old, or contradictory.
- Keep an evidence trail explaining exactly why each daily rating was produced.

## 2. Valuation and price history

- Use the P/E ratio alongside forward P/E, free-cash-flow yield, debt, growth, margins, and return on capital.
- Apply valuation measures that suit the business: price-to-book and return on equity for banks, FFO for property companies, normalized earnings for cyclical companies, and cash-flow or unit economics for growth companies.
- Produce conservative, base, and optimistic fair-value ranges instead of one deceptively precise target.
- Add an interactive price-history graph for every holding and opportunity with `1D`, `1W`, `1M`, `1Y`, `5Y`, and `All` ranges.
- Use intraday data for `1D`, adjusted historical prices for longer periods, and clearly state when the available history is limited.
- Include an exact-value tooltip, percentage change for the selected period, earnings markers, and a benchmark comparison where useful.
- Later add a portfolio-level performance graph against a suitable benchmark, with deposits and withdrawals separated from investment returns.

## 3. Analyst, filing, and event intelligence

- Focus on changes in earnings forecasts, guidance, price targets, and recommendation breadth—not just the headline consensus.
- Weight analyst opinions by recency, independence, coverage history, and past accuracy where reliable data exists.
- Show disagreement between analysts because wide disagreement means lower confidence.
- Compare each new filing, earnings release, and management update with the previous one.
- Maintain a plain-English thesis for every holding: why it is owned, the important measures, the main risks, and the evidence that would change the decision.
- Flag thesis improvements and thesis breaks immediately.

## 4. Opportunity and portfolio intelligence

- Expand the opportunity radar beyond a fixed watchlist while keeping minimum quality and liquidity standards.
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

## 6. International expansion

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

1. Official filing verification, source dates, and conflict checks.
2. Reliable historical-price service and the six-range graph.
3. Sector-aware valuation and fair-value ranges.
4. Thesis tracking plus analyst-estimate revisions.
5. Opportunity-versus-holding comparisons and portfolio risk.
6. Historical signal evaluation and confidence calibration.
7. International markets, one verified source set at a time.
