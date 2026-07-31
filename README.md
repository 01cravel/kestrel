# Kestrel

A plain-English daily view of a long-term stock portfolio.

Kestrel answers two questions:

- What should I do with the investments I already own?
- Which strong opportunities am I currently missing?

## Run locally

```sh
FINNHUB_KEY="your-key" python3 server.py
```

Then open [http://127.0.0.1:3050](http://127.0.0.1:3050).

The local server keeps API credentials out of the browser, loads evidence progressively,
and caches results so the dashboard does not start blank after every restart.

## Data and ratings

- Prices, company metrics, and analyst consensus currently come from Finnhub.
- Positions remain in browser local storage.
- Ratings are deliberately capped below `Ultra Buy` until official filing checks are connected.
- The previous prototype can be kept locally as `kestrel-legacy.html`, but is deliberately excluded from Git because it may contain credentials and private portfolio data.
