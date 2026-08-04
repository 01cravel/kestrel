# Swing Radar Phase 1 — success contract

Version: `2026.08.02.1`

The Swing Radar is a research alert, not a Buy/Sell engine. Its first job is to
identify unusually large, investable moves before they happen and state plainly
what is known, what is inferred, and what could cause a loss. It may not place a
trade or silently alter Kestrel's long-term portfolio score.

The machine-readable implementation is in `swing_radar_policy.py`. If prose and
code disagree, a release must stop until they are reconciled and versioned.

## 1. Investable US universe

Eligibility is evaluated **as it was known at each prediction cutoff**. A share
must meet every rule:

- US-listed common stock or ADR on NYSE, Nasdaq or Cboe; active at the cutoff.
- Stable security identity, listing currency and corporate-action history.
- Closing price at least $2.
- Point-in-time market value at least $300 million.
- Median 20-session dollar volume at least $5 million.
- At least 126 prior trading sessions of adjusted price history.

ETFs, funds, preferred shares, warrants, rights, units, OTC securities and test
issues are excluded. Delisted companies remain in historical data. Failed or
missing eligibility fields produce `unknown`, never an assumed pass. A separate
speculative research view may study excluded names, but it cannot train or
populate the investable alert table.

These thresholds are Kestrel capacity and data-quality controls, not claims that
smaller companies cannot rise. Phase 2 must store the raw field, source,
observation time, decision and policy version for every eligibility test.

## 2. Prediction unit and labels

One observation is `(security_id, cutoff, horizon, policy_version)`.

- Normal daily cutoff: 16:15 New York time on a completed US trading session.
- Late releases: information published after the cutoff belongs to the next
  prediction. A special pre-event run may use a later cutoff only when it is
  created and frozen before the event begins.
- Primary horizon: cutoff close to the next regular-session close.
- Secondary horizon: cutoff close to the fifth following regular-session close.
- Benchmark: SPY total return for the same timestamps initially; later, a
  point-in-time sector benchmark may be added as a separately versioned label.

Primary **big swing**:

`abs(stock return - benchmark return) >= 10%`

Secondary **large follow-through**:

`abs(stock return - benchmark return) >= 15% over five sessions`

Positive and negative labels use the sign of benchmark-relative return. Returns
use split- and distribution-adjusted closes. A corporate action, stale quote or
trading halt that makes the return unreliable quarantines the example rather
than labelling it. Volume and gap size are explanatory outcomes, not conditions
for the main label; imposing them would hide real moves from training.

## 3. Catalyst windows

Events are separate from price labels:

- `scheduled`: event date/time was public by the cutoff.
- `unscheduled`: first authoritative publication occurred after the cutoff.
- `rumour`: only a credible timestamped report exists.
- `unexplained`: no dependable cause was found.

For attribution, search from one regular session before the cutoff through the
label horizon. The cause timestamp must never be used as a model feature if it
is later than the cutoff. Known-event models receive only event metadata that
was public at the cutoff. Event predictability, direction predictability and
payoff attractiveness are scored independently.

## 4. No-hindsight controls

Every feature must retain `published_at`, `available_at`, `retrieved_at`, source
and revision/version. A feature is usable only when both `published_at` and
`available_at` are no later than the observation cutoff. Unknown timestamps are
not trainable.

Backtests must also:

- retain inactive and delisted securities and the historical universe;
- use point-in-time identifiers, shares, market values and index membership;
- fit imputation, normalisation, feature selection and calibration on training
  data only;
- split in chronological order, never randomly;
- purge overlapping label windows at split boundaries and embargo the next five
  sessions;
- keep all observations from one issuer/event family in the same fold;
- preserve the first raw vendor response and transformation version;
- prohibit revised estimates, corrected filings and final event outcomes from
  replacing the vintage available at prediction time.

Any breached rule invalidates the affected result. It is not repaired by lowering
confidence.

## 5. Success measurements

Report results for the whole eligible universe, each specialist radar, direction,
market-value band and probability band. Required measures are:

- Brier score and Brier skill versus a rolling historical base-rate forecast.
- Log loss and expected calibration error (10 fixed probability bins).
- Precision-recall AUC, because big swings are rare.
- Precision, recall and false alerts at the fixed daily alert budget.
- Precision among the top 1, 3, 5 and 10 daily candidates.
- Directional accuracy, measured only where a big swing actually occurred.
- Mean and median return, worst return, maximum adverse excursion and maximum
  favourable excursion after each alert, net of recorded spread/slippage.
- Coverage and abstention rate. Missing evidence must not disappear from the
  denominator.

Accuracy alone is not sufficient. A model that always predicts “no swing” can be
accurate and useless.

## 6. Fixed alert and downside gates

The initial alert budget is at most five US names per session. A candidate is
shown as an **Early watch** only when its predicted big-swing probability is at
least 20% and at least twice its point-in-time peer base rate.

It becomes a **Research alert** only when:

- its model has passed the promotion gates below;
- predicted big-swing probability is at least 35%;
- direction is shown only at conditional probability 65% or greater;
- identity, price, corporate actions, liquidity and timestamps are clean;
- the card shows a plausible adverse range and a specific invalidating fact;
- no unresolved source conflict affects the primary reason.

Otherwise Kestrel abstains. The thresholds may change only in a new policy
version supported by out-of-sample evidence; they may not be tuned on the final
test period.

## 7. Shadow-to-live promotion

“Live” means visible research alerts. It never means automatic trading or a Buy
rating. A model remains in shadow mode until all conditions pass on frozen,
unseen predictions:

- at least 60 trading sessions and 200 matured predictions;
- at least 40 matured Early watches, including at least 15 realised big swings;
- positive Brier skill of at least 10% versus the rolling base rate;
- calibration error no greater than 5 percentage points;
- alert precision at least twice the base rate;
- the 95% bootstrap lower bound for alert precision exceeds the base rate;
- directional accuracy at least 60% on realised swings where direction was
  stated;
- no critical data-leakage, identity or corporate-action incident;
- worst observed alert loss, false-positive count and missing-data rate have
  been explicitly reviewed and accepted by Luke rather than hidden in an average.

Every material model or feature change returns to shadow mode. Promotion is a
human approval recorded with the model version and evidence snapshot.

## 8. Plain-English card contract

Every candidate card must answer, in this order:

1. **What may move and when?** Company, symbol and horizon.
2. **How unusual could it be?** Calibrated chance of a 10% benchmark-relative
   move and a realistic up/down range.
3. **Which direction?** Up, down or genuinely uncertain; never force a direction.
4. **Why is it on watch?** At most three pre-cutoff facts.
5. **What is already expected?** Consensus, valuation or option-implied move when
   point-in-time data is available.
6. **What could go wrong?** Principal adverse case and invalidating evidence.
7. **What is fact versus model output?** Linked sources, timestamps, model version
   and evidence-health warning.

Use “chance,” not “confidence,” for probabilities. Never say “will”, “certain”,
“safe”, “guaranteed” or “should buy”. If calibration is not promoted, show
`Experimental — learning only` beside every number.

## Phase 2 hand-off

The market-history build must produce one immutable row per security/session with
the inputs required by `assess_investability`, plus adjusted security and SPY
closes for at least the next five sessions. It must retain raw responses,
historical security type/status, delistings, action flags, source timestamps and
the policy version. Phase 2 should call the shared functions rather than duplicate
thresholds or label logic.
