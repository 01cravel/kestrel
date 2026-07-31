const INSTRUMENTS = {
  MU: { name: 'Micron Technology', sector: 'Semiconductors', country: 'US' },
  SPY: { name: 'S&P 500 fund', sector: 'Broad market', country: 'US', type: 'fund' },
  NBIS: { name: 'Nebius Group', sector: 'Software', country: 'Netherlands' },
  VRT: { name: 'Vertiv', sector: 'Industrial', country: 'US' },
  V: { name: 'Visa', sector: 'Financial services', country: 'US' },
  GLD: { name: 'Gold fund', sector: 'Gold', country: 'Global', type: 'fund' },
  CAT: { name: 'Caterpillar', sector: 'Industrial', country: 'US' },
  NVDA: { name: 'Nvidia', sector: 'Semiconductors', country: 'US' },
  RKLB: { name: 'Rocket Lab', sector: 'Industrial', country: 'US' },
  LLY: { name: 'Eli Lilly', sector: 'Healthcare', country: 'US' },
  MA: { name: 'Mastercard', sector: 'Financial services', country: 'US' },
  HCA: { name: 'HCA Healthcare', sector: 'Healthcare', country: 'US' },
  AVGO: { name: 'Broadcom', sector: 'Semiconductors', country: 'US' },
  STX: { name: 'Seagate Technology', sector: 'Semiconductors', country: 'Ireland' },
  GOOGL: { name: 'Alphabet', sector: 'Software', country: 'US' },
  AXP: { name: 'American Express', sector: 'Financial services', country: 'US' },
  AMD: { name: 'Advanced Micro Devices', sector: 'Semiconductors', country: 'US' },
  CEG: { name: 'Constellation Energy', sector: 'Utilities', country: 'US' },
  QBTS: { name: 'D-Wave Quantum', sector: 'Software', country: 'US' },
  COHR: { name: 'Coherent', sector: 'Semiconductors', country: 'US' },
  ONDS: { name: 'Ondas Holdings', sector: 'Industrial', country: 'US' },
  MSFT: { name: 'Microsoft', sector: 'Software', country: 'US' },
  AMZN: { name: 'Amazon', sector: 'Consumer', country: 'US' },
  META: { name: 'Meta Platforms', sector: 'Software', country: 'US' },
  AAPL: { name: 'Apple', sector: 'Technology', country: 'US' },
  TSM: { name: 'Taiwan Semiconductor', sector: 'Semiconductors', country: 'Taiwan' },
  ASML: { name: 'ASML', sector: 'Semiconductors', country: 'Netherlands' },
  COST: { name: 'Costco', sector: 'Consumer', country: 'US' },
  HD: { name: 'Home Depot', sector: 'Consumer', country: 'US' },
  LIN: { name: 'Linde', sector: 'Industrial', country: 'Ireland' },
  ISRG: { name: 'Intuitive Surgical', sector: 'Healthcare', country: 'US' },
  NVO: { name: 'Novo Nordisk', sector: 'Healthcare', country: 'Denmark' },
  MELI: { name: 'MercadoLibre', sector: 'Consumer', country: 'Latin America' },
  SAP: { name: 'SAP', sector: 'Software', country: 'Germany' },
  SONY: { name: 'Sony', sector: 'Consumer', country: 'Japan' },
  UL: { name: 'Unilever', sector: 'Consumer', country: 'UK' },
  TTE: { name: 'TotalEnergies', sector: 'Energy', country: 'France' },
};

const VALUATION_BANDS = {
  Semiconductors: { cheap: 18, fair: 32 },
  Software: { cheap: 22, fair: 38 },
  Technology: { cheap: 20, fair: 34 },
  'Financial services': { cheap: 11, fair: 20 },
  Healthcare: { cheap: 18, fair: 30 },
  Consumer: { cheap: 20, fair: 32 },
  Industrial: { cheap: 16, fair: 26 },
  Utilities: { cheap: 14, fair: 23 },
  Energy: { cheap: 8, fair: 15 },
  default: { cheap: 15, fair: 25 },
};

const state = {
  dashboard: null,
  positions: loadPositions(),
  assessments: {},
  opportunities: [],
  pollTimer: null,
  savedSnapshotFor: null,
};

const els = {
  dataState: document.getElementById('dataState'),
  stateDot: document.getElementById('stateDot'),
  stateText: document.getElementById('stateText'),
  todayLabel: document.getElementById('todayLabel'),
  todayDate: document.getElementById('todayDate'),
  briefTitle: document.getElementById('briefTitle'),
  briefDetail: document.getElementById('briefDetail'),
  actNowCount: document.getElementById('actNowCount'),
  holdCount: document.getElementById('holdCount'),
  ideaCount: document.getElementById('ideaCount'),
  progressWrap: document.getElementById('progressWrap'),
  progressText: document.getElementById('progressText'),
  progressNumber: document.getElementById('progressNumber'),
  progressBar: document.getElementById('progressBar'),
  changesList: document.getElementById('changesList'),
  holdingsList: document.getElementById('holdingsList'),
  opportunitiesList: document.getElementById('opportunitiesList'),
  portfolioValue: document.getElementById('portfolioValue'),
  detailDialog: document.getElementById('detailDialog'),
  detailContent: document.getElementById('detailContent'),
  holdingsDialog: document.getElementById('holdingsDialog'),
  holdingsForm: document.getElementById('holdingsForm'),
  holdingsFields: document.getElementById('holdingsFields'),
  methodDialog: document.getElementById('methodDialog'),
};

function loadPositions() {
  try {
    const saved = JSON.parse(localStorage.getItem('kestrel_positions') || '{}');
    return saved && typeof saved === 'object' ? saved : {};
  } catch {
    return {};
  }
}

function savePositions() {
  localStorage.setItem('kestrel_positions', JSON.stringify(state.positions));
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clamp(value, minimum = 0, maximum = 100) {
  return Math.max(minimum, Math.min(maximum, value));
}

function average(values) {
  const valid = values.filter(value => Number.isFinite(value));
  if (!valid.length) return null;
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

function money(value, decimals = 0) {
  if (!Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function compactMoney(value) {
  if (!Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function percent(value, decimals = 1) {
  if (!Number.isFinite(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
}

function plainPercent(value, decimals = 1) {
  if (!Number.isFinite(value)) return '—';
  return `${value.toFixed(decimals)}%`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function metricScore(value, stops) {
  if (!Number.isFinite(value)) return null;
  for (const [threshold, score] of stops) {
    if (value >= threshold) return score;
  }
  return stops.at(-1)[1];
}

function analystView(recommendations) {
  if (!Array.isArray(recommendations) || !recommendations.length) return null;
  const current = recommendations[0];
  const previous = recommendations[1];

  const calculate = period => {
    if (!period) return null;
    const strongBuy = number(period.strongBuy) || 0;
    const buy = number(period.buy) || 0;
    const hold = number(period.hold) || 0;
    const sell = number(period.sell) || 0;
    const strongSell = number(period.strongSell) || 0;
    const total = strongBuy + buy + hold + sell + strongSell;
    if (!total) return null;
    const weighted = (strongBuy * 2 + buy - sell - strongSell * 2) / (total * 2);
    return {
      total,
      positiveShare: ((strongBuy + buy) / total) * 100,
      weighted,
      score: clamp(50 + weighted * 50),
    };
  };

  const latest = calculate(current);
  if (!latest) return null;
  const prior = calculate(previous);
  const change = prior ? latest.score - prior.score : 0;
  return { ...latest, change, period: current.period || null };
}

function assess(symbol, rawData, position = null) {
  const instrument = INSTRUMENTS[symbol] || { name: symbol, sector: 'default', country: 'US' };
  const quote = rawData?.quote || null;
  const metrics = rawData?.metrics || {};
  const analysts = analystView(rawData?.recommendations);
  const currentPrice = number(quote?.c);

  if (!currentPrice) {
    return {
      symbol,
      instrument,
      action: 'Checking',
      confidence: 'Low',
      score: null,
      reason: 'Current evidence has not arrived yet.',
      risks: ['No current price is available.'],
      positives: [],
      rawData,
      position,
    };
  }

  if (instrument.type === 'fund') {
    return assessFund(symbol, instrument, rawData, position);
  }

  const pe = number(metrics.peTTM) ?? number(metrics.peNormalizedAnnual);
  const peg = number(metrics.pegTTM);
  const roe = number(metrics.roeTTM);
  const margin = number(metrics.netProfitMarginTTM);
  const revenueGrowth = number(metrics.revenueGrowthTTMYoy) ?? number(metrics.revenueGrowth3Y);
  const earningsGrowth = number(metrics.epsGrowthTTMYoy) ?? number(metrics.epsGrowth3Y);
  const debtToEquity = number(metrics['totalDebt/totalEquityQuarterly']) ?? number(metrics['totalDebt/totalEquityAnnual']);
  const beta = number(metrics.beta);
  const weekHigh = number(metrics['52WeekHigh']);
  const weekLow = number(metrics['52WeekLow']);
  const yearReturn = number(metrics['52WeekPriceReturnDaily']);
  const drawdown = weekHigh ? ((currentPrice - weekHigh) / weekHigh) * 100 : null;
  const yearlyPosition = weekHigh && weekLow && weekHigh > weekLow
    ? ((currentPrice - weekLow) / (weekHigh - weekLow)) * 100
    : null;

  const qualityParts = [
    metricScore(roe, [[30, 100], [20, 85], [15, 72], [8, 55], [0, 35], [-Infinity, 10]]),
    metricScore(margin, [[25, 100], [15, 85], [8, 68], [3, 52], [0, 35], [-Infinity, 10]]),
    metricScore(debtToEquity, [[-Infinity, null]]),
  ];
  if (Number.isFinite(debtToEquity)) {
    qualityParts[2] = debtToEquity <= 0.35 ? 95 : debtToEquity <= 0.8 ? 75 : debtToEquity <= 1.5 ? 50 : 20;
  }
  const quality = average(qualityParts);

  const bands = VALUATION_BANDS[instrument.sector] || VALUATION_BANDS.default;
  let valuation = null;
  if (Number.isFinite(pe) && pe > 0) {
    valuation = pe <= bands.cheap ? 92 : pe <= bands.fair ? 72 : pe <= bands.fair * 1.25 ? 47 : 22;
    if (Number.isFinite(peg) && peg > 0) {
      valuation = clamp(valuation + (peg <= 1 ? 10 : peg <= 1.8 ? 3 : peg > 3 ? -10 : 0));
    }
  }

  const revenueScore = metricScore(revenueGrowth, [[20, 100], [10, 82], [5, 68], [0, 52], [-10, 30], [-Infinity, 10]]);
  const earningsScore = metricScore(earningsGrowth, [[25, 100], [10, 82], [3, 65], [0, 52], [-15, 28], [-Infinity, 8]]);
  const direction = average([revenueScore, earningsScore, analysts ? clamp(analysts.score + analysts.change) : null]);

  const analystScore = analysts?.score ?? null;
  const momentum = average([
    metricScore(yearReturn, [[30, 92], [15, 80], [5, 68], [0, 58], [-15, 40], [-Infinity, 20]]),
    metricScore(yearlyPosition, [[80, 82], [55, 72], [35, 58], [15, 40], [-Infinity, 25]]),
  ]);

  const weightedInputs = [
    [quality, 30],
    [valuation, 25],
    [direction, 20],
    [analystScore, 15],
    [momentum, 10],
  ].filter(([value]) => Number.isFinite(value));
  const totalWeight = weightedInputs.reduce((sum, [, weight]) => sum + weight, 0);
  const score = totalWeight
    ? weightedInputs.reduce((sum, [value, weight]) => sum + value * weight, 0) / totalWeight
    : null;

  const evidenceCount = [pe, roe, margin, revenueGrowth, earningsGrowth, analysts, weekHigh]
    .filter(value => value !== null && value !== undefined).length;
  const confidence = evidenceCount >= 5 && analysts?.total >= 5 ? 'Medium' : 'Low';

  const positives = [];
  const risks = [];

  if (quality >= 75) positives.push('The business is producing strong profits from its capital.');
  else if (quality !== null && quality < 45) risks.push('Business quality looks weaker than we want.');

  if (revenueGrowth >= 8 && earningsGrowth >= 8) positives.push('Sales and earnings are growing at a healthy pace.');
  if (revenueGrowth < 0) risks.push('Sales are shrinking compared with the previous period.');
  if (earningsGrowth < 0) risks.push('Earnings are moving in the wrong direction.');

  if (valuation >= 70) positives.push('The price looks reasonable against earnings and expected growth.');
  if (valuation !== null && valuation < 35) risks.push('The price leaves little room for disappointment.');

  if (analysts?.positiveShare >= 70) positives.push('Most covering analysts remain positive.');
  if (analysts?.change >= 5) positives.push('The analyst view has improved recently.');
  if (analysts?.change <= -5) risks.push('The analyst view has weakened recently.');

  if (debtToEquity > 1.5) risks.push('Debt is high compared with shareholder capital.');
  if (beta > 1.8) risks.push('The share price has been much more volatile than the wider market.');
  if (drawdown < -35) risks.push('The shares remain in a deep fall from their yearly high.');

  const severeDeterioration = revenueGrowth < -12 && earningsGrowth < -18;
  const weakAgreement = quality < 38 && direction < 38 && (analystScore === null || analystScore < 45);
  const ultraCandidate = confidence === 'Medium'
    && score >= 82
    && quality >= 78
    && valuation >= 70
    && direction >= 72
    && analystScore >= 70
    && risks.length <= 1;

  let action = 'Hold';
  if ((severeDeterioration || weakAgreement) && score < 43) action = 'Sell';
  else if (confidence === 'Medium' && score >= 68 && valuation >= 48 && direction >= 58) action = 'Buy';

  let reason = buildReason(action, { quality, valuation, direction, analysts, positives, risks });

  return {
    symbol,
    instrument,
    action,
    confidence,
    score,
    reason,
    positives,
    risks,
    ultraCandidate,
    rawData,
    position,
    metrics: {
      pe,
      peg,
      roe,
      margin,
      revenueGrowth,
      earningsGrowth,
      debtToEquity,
      beta,
      drawdown,
      yearReturn,
      currentPrice,
      dayChange: number(quote.dp),
      analystCount: analysts?.total ?? null,
      analystPositive: analysts?.positiveShare ?? null,
      analystChange: analysts?.change ?? null,
    },
    componentScores: { quality, valuation, direction, analyst: analystScore, momentum },
  };
}

function assessFund(symbol, instrument, rawData, position) {
  const quote = rawData.quote;
  const metrics = rawData.metrics || {};
  const currentPrice = number(quote.c);
  const weekHigh = number(metrics['52WeekHigh']);
  const weekLow = number(metrics['52WeekLow']);
  const yearReturn = number(metrics['52WeekPriceReturnDaily']);
  const drawdown = weekHigh ? ((currentPrice - weekHigh) / weekHigh) * 100 : null;
  const risks = [];
  if (drawdown < -25) risks.push('The fund is well below its yearly high.');

  return {
    symbol,
    instrument,
    action: 'Hold',
    confidence: 'Low',
    score: 50,
    reason: instrument.sector === 'Gold'
      ? 'Gold can diversify the portfolio, but company valuation measures do not apply to it.'
      : 'This broad fund is a portfolio anchor, not an individual company assessment.',
    positives: ['The holding spreads risk across more than one company.'],
    risks,
    ultraCandidate: false,
    rawData,
    position,
    metrics: {
      currentPrice,
      dayChange: number(quote.dp),
      drawdown,
      yearReturn,
    },
    componentScores: {},
  };
}

function buildReason(action, evidence) {
  const { quality, valuation, direction, analysts, positives, risks } = evidence;
  if (action === 'Sell') {
    return 'The company is weakening in more than one important area. Keeping it now needs a fresh investment case.';
  }
  if (action === 'Buy') {
    if (quality >= 75 && valuation >= 70) return 'The business looks strong, growth is holding up, and today’s price appears sensible.';
    if (analysts?.positiveShare >= 75) return 'Company progress and analyst evidence are positive, while the price remains acceptable.';
    return positives.slice(0, 2).join(' ') || 'Several independent parts of the evidence support adding carefully.';
  }
  if (quality >= 72 && valuation !== null && valuation < 40) {
    return 'The business looks strong, but the share price already expects a great deal to go right.';
  }
  if (direction !== null && direction < 45) {
    return 'The holding remains investable, but growth is not strong enough to justify adding today.';
  }
  if (risks.length) return `${risks[0]} There is not enough evidence to make a change today.`;
  return 'The investment case looks broadly intact, but the evidence does not justify adding or selling today.';
}

function applyPortfolioRisk(assessments) {
  const values = Object.values(assessments).map(assessment => {
    const shares = number(assessment.position?.shares) || 0;
    return shares * (assessment.metrics?.currentPrice || 0);
  });
  const total = values.reduce((sum, value) => sum + value, 0);

  Object.values(assessments).forEach(assessment => {
    const shares = number(assessment.position?.shares) || 0;
    const value = shares * (assessment.metrics?.currentPrice || 0);
    const weight = total > 0 ? (value / total) * 100 : 0;
    assessment.positionValue = value;
    assessment.portfolioWeight = weight;

    if (weight >= 15 && assessment.action === 'Buy') {
      assessment.action = 'Hold';
      assessment.reason = 'The company looks attractive, but this position is already large enough in your portfolio.';
      assessment.risks.unshift('Adding more would increase concentration risk.');
    }
  });
  return total;
}

async function fetchDashboard() {
  try {
    const response = await fetch('/api/dashboard', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Dashboard returned ${response.status}`);
    state.dashboard = await response.json();
    calculateAndRender();
    schedulePoll(state.dashboard.status === 'ready' ? 60000 : 2500);
  } catch (error) {
    showConnectionError(error);
    schedulePoll(5000);
  }
}

function schedulePoll(delay) {
  window.clearTimeout(state.pollTimer);
  state.pollTimer = window.setTimeout(fetchDashboard, delay);
}

function calculateAndRender() {
  const dashboard = state.dashboard;
  updateDataStatus(dashboard);
  updateProgress(dashboard);

  const ownedSymbols = dashboard.holdingsUniverse.filter(symbol => number(state.positions[symbol]?.shares) > 0);
  const symbolsToShow = ownedSymbols.length ? ownedSymbols : dashboard.holdingsUniverse;
  const assessments = {};

  symbolsToShow.forEach(symbol => {
    assessments[symbol] = assess(symbol, dashboard.data[symbol], state.positions[symbol] || null);
  });
  state.assessments = assessments;
  const portfolioTotal = applyPortfolioRisk(assessments);

  state.opportunities = dashboard.opportunityUniverse
    .filter(symbol => !state.positions[symbol]?.shares)
    .map(symbol => assess(symbol, dashboard.data[symbol], null))
    .filter(item => item.action === 'Buy' && item.confidence !== 'Low')
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  renderBrief(dashboard, ownedSymbols, assessments);
  renderHoldings(symbolsToShow, assessments, ownedSymbols.length > 0);
  renderPortfolioValue(portfolioTotal, ownedSymbols);
  renderOpportunities(dashboard);
  renderChanges(dashboard);
}

function updateDataStatus(dashboard) {
  const isLoading = dashboard.status === 'refreshing' || dashboard.status === 'starting' || dashboard.status === 'cached';
  const isError = dashboard.status === 'error' || !dashboard.keyConfigured;
  els.stateDot.className = `state-dot${isLoading ? ' is-loading' : ''}${isError ? ' is-error' : ''}`;
  els.stateText.textContent = dashboard.message;
}

function updateProgress(dashboard) {
  const progress = dashboard.total ? Math.round((dashboard.completed / dashboard.total) * 100) : 0;
  const complete = dashboard.status === 'ready' && progress >= 100;
  els.progressWrap.hidden = complete;
  els.progressText.textContent = dashboard.message;
  els.progressNumber.textContent = `${progress}%`;
  els.progressBar.style.width = `${progress}%`;
}

function renderBrief(dashboard, ownedSymbols, assessments) {
  const now = new Date();
  els.todayDate.textContent = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' }).format(now);
  els.todayLabel.textContent = new Intl.DateTimeFormat('en-GB', { weekday: 'long' }).format(now);

  const assessedOwned = ownedSymbols.map(symbol => assessments[symbol]).filter(item => item?.action !== 'Checking');
  const buys = assessedOwned.filter(item => item.action === 'Buy' || item.action === 'Ultra Buy');
  const sells = assessedOwned.filter(item => item.action === 'Sell');
  const holds = assessedOwned.filter(item => item.action === 'Hold');

  els.actNowCount.textContent = assessedOwned.length ? buys.length + sells.length : '—';
  els.holdCount.textContent = assessedOwned.length ? holds.length : '—';
  els.ideaCount.textContent = state.opportunities.length || (dashboard.status === 'ready' ? '0' : '—');

  if (!ownedSymbols.length) {
    els.briefTitle.textContent = 'Add your holdings to begin the daily assessment.';
    els.briefDetail.textContent = 'Kestrel will then compare what you own with the strongest opportunities it can verify.';
    return;
  }
  if (dashboard.status !== 'ready') {
    els.briefTitle.textContent = 'Checking your holdings before looking for new ideas.';
    els.briefDetail.textContent = `${assessedOwned.length} of ${ownedSymbols.length} owned positions have enough evidence for an early view.`;
    return;
  }
  if (sells.length) {
    els.briefTitle.textContent = `${sells.length} holding${sells.length === 1 ? '' : 's'} need a fresh look today.`;
    els.briefDetail.textContent = 'A sell rating means several important signals weakened together. Open the evidence before acting.';
  } else if (buys.length) {
    els.briefTitle.textContent = `${buys.length} holding${buys.length === 1 ? '' : 's'} may justify adding carefully.`;
    els.briefDetail.textContent = 'Position size and confidence still matter. A positive rating is not a promise of profit.';
  } else {
    els.briefTitle.textContent = 'Nothing in your portfolio needs action today.';
    els.briefDetail.textContent = 'Hold is a deliberate decision: the current evidence does not justify trading.';
  }
}

function renderHoldings(symbols, assessments, hasOwnedPositions) {
  if (!hasOwnedPositions) {
    els.holdingsList.innerHTML = `
      <div class="empty-card">
        <strong>Your holdings are not set up on this address</strong>
        <span>Choose “Edit holdings” and enter your share counts. Kestrel will keep them in this browser.</span>
      </div>`;
    return;
  }

  const order = { Sell: 0, Buy: 1, Hold: 2, Checking: 3 };
  const sorted = symbols
    .map(symbol => assessments[symbol])
    .sort((a, b) => (order[a.action] - order[b.action]) || (b.positionValue - a.positionValue));

  els.holdingsList.innerHTML = sorted.map(renderHoldingRow).join('');
  els.holdingsList.querySelectorAll('[data-detail-symbol]').forEach(button => {
    button.addEventListener('click', () => openDetail(button.dataset.detailSymbol));
  });
}

function renderHoldingRow(assessment) {
  const { symbol, instrument, action, confidence, reason, metrics, positionValue, portfolioWeight, position } = assessment;
  const dayClass = metrics?.dayChange >= 0 ? 'positive' : 'negative';
  const price = metrics?.currentPrice;
  const cost = number(position?.cost);
  const shares = number(position?.shares) || 0;
  const gain = cost && price ? (price - cost) * shares : null;
  const gainText = gain === null ? `${shares.toFixed(shares % 1 ? 2 : 0)} shares` : `${gain >= 0 ? '+' : ''}${compactMoney(gain)} since purchase`;

  return `
    <article class="assessment-row" data-action="${escapeHtml(action)}">
      <div class="decision-cell">
        <span class="decision-label">${escapeHtml(action)}</span>
        <span class="confidence-label">${escapeHtml(confidence)} confidence</span>
      </div>
      <div class="company-cell">
        <div class="company-line"><strong>${escapeHtml(instrument.name)}</strong><span class="ticker">${escapeHtml(symbol)}</span></div>
        <div class="company-price"><span>${money(price, 2)}</span><span class="${dayClass}">${percent(metrics?.dayChange)}</span></div>
      </div>
      <div class="reason-cell">
        <p class="plain-reason">${escapeHtml(reason)}</p>
        <button type="button" data-detail-symbol="${escapeHtml(symbol)}">See the evidence</button>
      </div>
      <div class="position-cell">
        <small>Your position</small>
        <strong>${compactMoney(positionValue)}</strong>
        <span>${plainPercent(portfolioWeight)} of stocks · ${escapeHtml(gainText)}</span>
      </div>
    </article>`;
}

function renderPortfolioValue(total, ownedSymbols) {
  if (!ownedSymbols.length || !total) {
    els.portfolioValue.textContent = 'Add share counts to calculate position sizes';
    return;
  }
  els.portfolioValue.textContent = `${compactMoney(total)} across ${ownedSymbols.length} holdings`;
}

function renderOpportunities(dashboard) {
  if (state.opportunities.length) {
    els.opportunitiesList.innerHTML = state.opportunities.map((item, index) => renderOpportunity(item, index)).join('');
    els.opportunitiesList.querySelectorAll('[data-detail-symbol]').forEach(button => {
      button.addEventListener('click', () => openDetail(button.dataset.detailSymbol, true));
    });
    return;
  }

  if (dashboard.status !== 'ready') {
    const checkedCandidates = dashboard.opportunityUniverse.filter(symbol => dashboard.data[symbol]?.quote).length;
    els.opportunitiesList.innerHTML = `
      <div class="empty-card wide">
        <strong>Holdings come first</strong>
        <span>${checkedCandidates} of ${dashboard.opportunityUniverse.length} opportunity candidates checked so far.</span>
      </div>`;
    return;
  }

  els.opportunitiesList.innerHTML = `
    <div class="empty-card wide">
      <strong>No candidate clears the evidence bar today</strong>
      <span>Kestrel will not force a recommendation merely to fill this space.</span>
    </div>`;
}

function renderOpportunity(item, index) {
  const { symbol, instrument, reason, metrics, confidence } = item;
  return `
    <article class="opportunity-card">
      <div>
        <h3>${escapeHtml(instrument.name)} <span class="ticker">${escapeHtml(symbol)}</span></h3>
        <span class="company-price">${money(metrics.currentPrice, 2)} · ${escapeHtml(instrument.country)}</span>
      </div>
      <span class="opportunity-rank">0${index + 1}</span>
      <p>${escapeHtml(reason)}</p>
      <div class="opportunity-bottom">
        <div>
          <span class="action-pill">Buy · not owned</span>
          <button type="button" data-detail-symbol="${escapeHtml(symbol)}">See why it made the list</button>
        </div>
        <span class="evidence-note">${escapeHtml(confidence)} confidence<br>${escapeHtml(instrument.sector)}</span>
      </div>
    </article>`;
}

function renderChanges(dashboard) {
  if (dashboard.status !== 'ready') return;
  const snapshotKey = String(dashboard.lastFullRefresh || 'ready');
  if (state.savedSnapshotFor === snapshotKey) return;

  let previous = {};
  try {
    previous = JSON.parse(localStorage.getItem('kestrel_action_snapshot') || '{}');
  } catch {
    previous = {};
  }

  const current = {};
  const changes = [];
  Object.values(state.assessments).forEach(item => {
    if (item.action === 'Checking') return;
    current[item.symbol] = item.action;
    if (previous[item.symbol] && previous[item.symbol] !== item.action) {
      changes.push({ ...item, from: previous[item.symbol] });
    }
  });

  if (changes.length) {
    els.changesList.innerHTML = changes.slice(0, 3).map(item => `
      <article class="change-card">
        <div class="change-top"><span class="ticker">${escapeHtml(item.symbol)}</span><span class="action-pill">${escapeHtml(item.from)} → ${escapeHtml(item.action)}</span></div>
        <p>${escapeHtml(item.reason)}</p>
      </article>`).join('');
  } else if (Object.keys(previous).length) {
    els.changesList.innerHTML = `
      <div class="empty-card">
        <strong>No meaningful rating changes</strong>
        <span>The evidence has not moved enough to justify action.</span>
      </div>`;
  } else {
    els.changesList.innerHTML = `
      <div class="empty-card">
        <strong>Your baseline is ready</strong>
        <span>Future rating changes will appear here with a plain-English explanation.</span>
      </div>`;
  }

  localStorage.setItem('kestrel_action_snapshot', JSON.stringify(current));
  state.savedSnapshotFor = snapshotKey;
}

function openDetail(symbol, isOpportunity = false) {
  const item = isOpportunity
    ? state.opportunities.find(candidate => candidate.symbol === symbol)
    : state.assessments[symbol];
  if (!item) return;

  const { instrument, action, confidence, reason, positives, risks, metrics, componentScores, rawData } = item;
  const positiveList = positives.length ? positives : ['No strong positive evidence is available yet.'];
  const riskList = risks.length ? risks : ['No major quantitative warning is visible in the available data.'];
  const fetched = rawData?.fetchedAt ? new Date(rawData.fetchedAt * 1000).toLocaleString() : 'Unknown';

  els.detailContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(instrument.country)} · ${escapeHtml(instrument.sector)}</p>
    <h2>${escapeHtml(instrument.name)} <span class="ticker">${escapeHtml(symbol)}</span></h2>
    <div class="detail-hero" data-action="${escapeHtml(action)}">
      <strong>${escapeHtml(action)}</strong>
      <p>${escapeHtml(reason)}</p>
    </div>
    <div class="detail-section">
      <h3>Why Kestrel reached this view</h3>
      <ul class="detail-bullets">${positiveList.map(text => `<li>${escapeHtml(text)}</li>`).join('')}</ul>
    </div>
    <div class="detail-section">
      <h3>What could make this wrong</h3>
      <ul class="detail-bullets">${riskList.map(text => `<li>${escapeHtml(text)}</li>`).join('')}</ul>
    </div>
    <div class="detail-section">
      <h3>The numbers underneath</h3>
      <div class="metric-grid">
        ${metricTile('Price versus earnings', metrics?.pe ? `${metrics.pe.toFixed(1)}×` : 'Not available')}
        ${metricTile('Sales growth', percent(metrics?.revenueGrowth))}
        ${metricTile('Earnings growth', percent(metrics?.earningsGrowth))}
        ${metricTile('Return on equity', plainPercent(metrics?.roe))}
        ${metricTile('Profit margin', plainPercent(metrics?.margin))}
        ${metricTile('Positive analysts', metrics?.analystPositive === null || metrics?.analystPositive === undefined ? 'Not available' : plainPercent(metrics.analystPositive, 0))}
      </div>
    </div>
    <div class="detail-section">
      <h3>Evidence status</h3>
      <p class="plain-reason"><strong>${escapeHtml(confidence)} confidence.</strong> Market and analyst data came through Finnhub at ${escapeHtml(fetched)}. Official company filing checks are not connected yet, so Ultra Buy remains locked.</p>
      ${item.ultraCandidate ? '<p class="plain-reason"><strong>Worth noting:</strong> This company clears the quantitative Ultra Buy bar, pending independent filing verification and portfolio checks.</p>' : ''}
      ${rawData?.errors?.length ? `<p class="plain-reason"><strong>Missing evidence:</strong> ${escapeHtml(rawData.errors.join(' · '))}</p>` : ''}
    </div>`;

  els.detailDialog.showModal();
}

function metricTile(label, value) {
  return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function openHoldingsEditor() {
  const universe = state.dashboard?.holdingsUniverse || Object.keys(state.positions);
  els.holdingsFields.innerHTML = universe.map(symbol => {
    const instrument = INSTRUMENTS[symbol] || { name: symbol };
    const position = state.positions[symbol] || {};
    return `
      <div class="holding-field">
        <label for="shares-${escapeHtml(symbol)}"><strong>${escapeHtml(instrument.name)}</strong><span>${escapeHtml(symbol)}</span></label>
        <input id="shares-${escapeHtml(symbol)}" name="shares-${escapeHtml(symbol)}" type="number" min="0" step="any" value="${escapeHtml(position.shares || '')}" placeholder="0" aria-label="${escapeHtml(symbol)} shares">
        <input name="cost-${escapeHtml(symbol)}" type="number" min="0" step="any" value="${escapeHtml(position.cost || '')}" placeholder="Optional" aria-label="${escapeHtml(symbol)} average cost">
      </div>`;
  }).join('');
  els.holdingsDialog.showModal();
}

function handleHoldingsSave(event) {
  event.preventDefault();
  const formData = new FormData(els.holdingsForm);
  const universe = state.dashboard?.holdingsUniverse || [];
  const next = {};
  universe.forEach(symbol => {
    const shares = number(formData.get(`shares-${symbol}`));
    const cost = number(formData.get(`cost-${symbol}`));
    if (shares > 0) next[symbol] = { shares, cost: cost > 0 ? cost : null };
  });
  state.positions = next;
  savePositions();
  els.holdingsDialog.close();
  calculateAndRender();
}

async function requestRefresh() {
  const button = document.getElementById('refreshButton');
  button.disabled = true;
  button.textContent = 'Refresh queued';
  try {
    await fetch('/api/refresh', { method: 'POST' });
    schedulePoll(500);
  } finally {
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = 'Refresh evidence';
    }, 1800);
  }
}

function showConnectionError(error) {
  els.stateDot.className = 'state-dot is-error';
  els.stateText.textContent = 'Local data service is not responding';
  els.briefTitle.textContent = 'Kestrel cannot reach its evidence service.';
  els.briefDetail.textContent = 'Keep the local server running on port 3050, then refresh this page.';
  console.error(error);
}

document.querySelectorAll('[data-close-dialog]').forEach(button => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.getElementById('editHoldingsButton').addEventListener('click', openHoldingsEditor);
document.getElementById('refreshButton').addEventListener('click', requestRefresh);
document.getElementById('methodButton').addEventListener('click', () => els.methodDialog.showModal());
els.holdingsForm.addEventListener('submit', handleHoldingsSave);

document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
});

fetchDashboard();
