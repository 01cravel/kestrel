# Portfolio challenger validation protocol

Kestrel is decision support. This evaluation can permit a challenger to be
reviewed; it cannot change an allocation or place a trade.

## Frozen experiment

Before any test period begins, record the model version, fixed instrument
universe, `VT` benchmark, constraints, selection rule, data sources,
corporate-action method and one-way cost assumption. Bind the manifest to the
exact model version. It must retain an explicit membership and complete outcome
record for inactive and delisted instruments. Every price observation needs its
own availability date and point-in-time total-return adjustment policy. Each
fold also needs a complete ETF holdings snapshot that was available at its
cutoff; today's look-through is never substituted into the past.
That snapshot must link to immutable archived holdings and fee report IDs for
the exact fund share class. It retains the holdings as-of date, publication,
first-availability and retrieval times, reporting lag, source record ID or SEC
accession, URL and SHA-256 hashes. A current issuer response without that chain
is descriptive only and cannot certify a fold.
The no-cost market archive may open those controls only when every declared
portfolio symbol has a timely adjusted close, a stable point-in-time identity,
and retained raw split and dividend request proofs spanning the decision date.
Missing or late evidence produces no partial certified snapshot.

Holdings preserve the source's units, currency and reported weights without
normalization. The source-reported total must be complete; Kestrel does not
infer missing weights or rescale a partial list. Cash remains explicit, and
derivatives retain contract/notional evidence. Unresolved cash, derivatives,
coverage, currency, fee evidence or share-class identity closes the fold. Mixed
currencies are not aggregated unless a separate, point-in-time conversion rule
and evidence are present.

Current-ticker downloads do not meet this standard. They remain useful for
descriptive research, but Kestrel reports zero eligible unseen windows until a
pre-registered, reconstructable information set exists.

`universe_ledger.py` is the certification boundary. Every eligible protocol
must name a content-addressed snapshot and manifest that the ledger can rebuild
and verify. The snapshot is write-once: included and excluded members, stable
identities, evidence cutoffs and ETF holdings cannot be updated or deleted.
Later outcomes append separately, and a delisted instrument is incomplete until
its transaction terms have independent source evidence. Each outcome preserves
valid-through, effective, availability and retrieval time; stable identity;
currency; adjustment definition; source record ID; raw/derived source hashes;
and a payload hash. Ordinary survivors must have a continuous same-currency
point-in-time total-return path. Ticker changes are followed only through the
same stable identity.

An inactive listing is not enough to finish a delisting. Kestrel also requires
a matching dated SEC or official issuer record. Cash consideration needs the
explicit per-share proceeds and ISO currency. Stock consideration needs the
successor's stable identity, conversion ratio and a same-currency adjusted path
through the test horizon. Disappearance, missing sessions, late evidence,
ambiguous terms and conflicts append `missing` or `conflict` states and keep the
fold closed. Reprocessing identical evidence is idempotent; a correction adds a
new recorded-time version and never changes the old one.
Duplicate or amended N-PORT filings are separate content-addressed records and
must point to the record they supersede. The protocol exposes exact availability
and retrieval timestamps rather than truncating them to dates.

The operational boundary is fail closed too. Before the daily workflow appends
anything, it verifies SQLite and foreign-key integrity, the exact schema and
migration chain, every immutable trigger, JSON payload hash, content address and
snapshot manifest. It repeats that deterministic audit after the transaction and
only then publishes a consistent online backup. Backups are content-addressed,
standalone from WAL and verified before use. Recovery is a separate command that
requires the expected ledger identity and a new empty target; it cannot replace the
live ledger. Hash, identity, schema, WAL-state or recovery-root disagreement blocks
restore. See [LEDGER_OPERATIONS.md](LEDGER_OPERATIONS.md) for the operator procedure.

## Chronological test

- Train on at least 36 months available before the decision cutoff.
- Refit and select the constrained challenger using only that expanding past.
- Evaluate the frozen weights over the next 12 months.
- Use non-overlapping annual windows; require at least five.
- Charge the challenger declared one-way cost in proportion to turnover from
  Candidate 1. Charge the investable `VT` alternative its declared
  implementation cost. Candidate 1 represents doing nothing and has no trade.
- Never tune the search, cost or gate from an outer test result.

## Report and promotion gate

For every window, report net challenger, Candidate 1 and `VT` return. Across
all eligible windows, report annualised net return, maximum drawdown and
information ratio versus Candidate 1 and `VT`. Quantify uncertainty with a
deterministic 95% bootstrap interval that resamples whole annual windows, so
correlated months are never treated as independent evidence.

The walk-forward gate passes only when there are at least five windows, the
challenger beats both comparators in at least 80% of them, both 95% improvement
intervals exclude zero on the positive side, and its information ratio versus
`VT` is positive. Any missing provenance, future-information timestamp,
incorrect benchmark, weak result or thin sample closes the gate.

Passing this gate is necessary but not sufficient. Every other evidence gate
and an explicit human decision still stand between research and any portfolio
change.
