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

const BOOK_VALUE_MODELS = new Set(['AXP']);
const EARLY_STAGE_MODELS = new Set(['NBIS', 'RKLB', 'QBTS', 'ONDS']);
const NORMALIZED_EARNINGS_MODELS = new Set(['MU', 'CAT', 'STX', 'CEG', 'COHR']);

const state = {
  dashboard: null,
  positions: loadPositions(),
  assessments: {},
  opportunities: [],
  pollTimer: null,
  savedSnapshotFor: null,
  savedSignalsFor: null,
  historyRangeBySymbol: {},
  historyRequest: null,
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
  portfolioRiskSection: document.getElementById('portfolioRiskSection'),
  portfolioRiskSummary: document.getElementById('portfolioRiskSummary'),
  portfolioRiskGrid: document.getElementById('portfolioRiskGrid'),
  calibrationSummary: document.getElementById('calibrationSummary'),
  calibrationGrid: document.getElementById('calibrationGrid'),
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

function earningsView(history) {
  if (!Array.isArray(history) || !history.length) return null;
  const surprises = history
    .map(item => ({
      period: item.period || null,
      actual: number(item.actual),
      estimate: number(item.estimate),
      surprisePercent: number(item.surprisePercent),
    }))
    .filter(item => item.surprisePercent !== null)
    .slice(0, 8);
  if (!surprises.length) return null;
  const recent = surprises.slice(0, 4);
  const averageSurprise = average(recent.map(item => clamp(item.surprisePercent, -30, 30)));
  const beats = recent.filter(item => item.surprisePercent > 0).length;
  return {
    recent,
    averageSurprise,
    beats,
    total: recent.length,
    score: clamp(50 + averageSurprise * 1.6),
  };
}

function estimateView(intelligence, currentPrice) {
  if (!intelligence || intelligence.status === 'error') return null;
  const estimate = intelligence.estimate || null;
  const revision = intelligence.estimateRevision || null;
  const target = intelligence.priceTarget || null;
  const consensusTarget = number(target?.consensus) ?? number(target?.median);
  const targetUpside = consensusTarget && currentPrice
    ? ((consensusTarget - currentPrice) / currentPrice) * 100
    : null;
  const targetScore = targetUpside === null
    ? null
    : targetUpside >= 25 ? 90
      : targetUpside >= 12 ? 78
        : targetUpside >= 3 ? 64
          : targetUpside >= -8 ? 48
            : 25;
  const targetLow = number(target?.low);
  const targetHigh = number(target?.high);
  const targetMedian = number(target?.median) ?? consensusTarget;
  const disagreement = targetLow && targetHigh && targetMedian
    ? ((targetHigh - targetLow) / targetMedian) * 100
    : null;
  const revisionDirection = revision?.direction || null;
  const revisionAdjustment = revisionDirection === 'up' ? 8 : revisionDirection === 'down' ? -10 : 0;
  return {
    estimate,
    revision,
    target,
    targetUpside,
    disagreement,
    score: targetScore === null ? null : clamp(targetScore + revisionAdjustment),
    source: intelligence.source,
  };
}

function multipleScore(value, bands) {
  if (!Number.isFinite(value) || value <= 0) return null;
  if (value <= bands.cheap * 0.8) return 95;
  if (value <= bands.cheap) return 86;
  if (value <= (bands.cheap + bands.fair) / 2) return 72;
  if (value <= bands.fair) return 55;
  if (value <= bands.fair * 1.25) return 35;
  return 15;
}

function priceToFairScore(price, fairValue) {
  if (!Number.isFinite(price) || !Number.isFinite(fairValue) || fairValue <= 0) return null;
  const ratio = price / fairValue;
  if (ratio <= 0.72) return 96;
  if (ratio <= 0.86) return 86;
  if (ratio <= 1) return 72;
  if (ratio <= 1.15) return 52;
  if (ratio <= 1.35) return 30;
  return 12;
}

function fairValueRange(low, base, high) {
  const values = [low, base, high].map(number).filter(value => value > 0).sort((a, b) => a - b);
  if (values.length !== 3) return null;
  return { low: values[0], base: values[1], high: values[2] };
}

function valuationView(symbol, instrument, metrics, currentPrice, revenueGrowth, earningsGrowth, roe) {
  const bands = VALUATION_BANDS[instrument.sector] || VALUATION_BANDS.default;
  const forwardPe = number(metrics.forwardPE);
  const priceToCashFlow = number(metrics.pfcfShareTTM);
  const evToEbitda = number(metrics.evEbitdaTTM);
  const evToRevenue = number(metrics.evRevenueTTM);
  const bookValue = number(metrics.bookValuePerShareQuarterly) ?? number(metrics.bookValuePerShareAnnual);
  const eps = NORMALIZED_EARNINGS_MODELS.has(symbol)
    ? number(metrics.epsNormalizedAnnual) ?? number(metrics.epsBasicExclExtraItemsTTM) ?? number(metrics.epsTTM)
    : number(metrics.epsBasicExclExtraItemsTTM) ?? number(metrics.epsTTM) ?? number(metrics.epsNormalizedAnnual);

  if (BOOK_VALUE_MODELS.has(symbol) && bookValue > 0 && roe > 0) {
    const currentPriceToBook = currentPrice / bookValue;
    const reasonablePriceToBook = clamp(0.8 + roe / 10, 1.1, 4.5);
    const range = fairValueRange(
      bookValue * reasonablePriceToBook * 0.75,
      bookValue * reasonablePriceToBook,
      bookValue * reasonablePriceToBook * 1.25,
    );
    return {
      score: average([
        priceToFairScore(currentPrice, range?.base),
        multipleScore(forwardPe, VALUATION_BANDS['Financial services']),
      ]),
      method: 'Book value and return on equity',
      explanation: 'For a lending-led financial company, shareholder capital and the profit earned from it matter more than a generic market P/E.',
      fairValue: range,
      primaryMetric: { label: 'Price to book', value: currentPriceToBook, suffix: '×' },
      confidence: 'Medium',
    };
  }

  if (EARLY_STAGE_MODELS.has(symbol) && evToRevenue > 0 && currentPrice > 0) {
    const sensibleGrowth = clamp(number(revenueGrowth) || 0, 0, 50);
    const reasonableMultiple = clamp(2 + sensibleGrowth / 8, 2, 9);
    const range = fairValueRange(
      currentPrice * (reasonableMultiple * 0.62 / evToRevenue),
      currentPrice * (reasonableMultiple / evToRevenue),
      currentPrice * (reasonableMultiple * 1.35 / evToRevenue),
    );
    return {
      score: priceToFairScore(currentPrice, range?.base),
      method: 'Revenue multiple for an early-stage business',
      explanation: 'Reliable earnings do not exist yet, so Kestrel uses sales growth and the enterprise value paid for each dollar of sales. This is less dependable than an earnings valuation.',
      fairValue: range,
      primaryMetric: { label: 'Enterprise value to sales', value: evToRevenue, suffix: '×' },
      confidence: 'Low',
    };
  }

  if (eps > 0 && currentPrice > 0) {
    const rawGrowth = average([revenueGrowth, earningsGrowth]);
    const sensibleGrowth = clamp(number(rawGrowth) || 8, -10, 30);
    const growthAdjustment = clamp(1 + (sensibleGrowth - 8) / 100, 0.82, 1.22);
    const baseMultiple = ((bands.cheap + bands.fair) / 2) * growthAdjustment;
    const range = fairValueRange(
      eps * bands.cheap * 0.9,
      eps * baseMultiple,
      eps * bands.fair * growthAdjustment,
    );
    const cashFlowBands = { cheap: 18, fair: instrument.sector === 'Software' ? 35 : 30 };
    return {
      score: average([
        priceToFairScore(currentPrice, range?.base),
        multipleScore(forwardPe, bands),
        multipleScore(priceToCashFlow, cashFlowBands),
        multipleScore(evToEbitda, { cheap: 12, fair: 24 }),
      ]),
      method: NORMALIZED_EARNINGS_MODELS.has(symbol) ? 'Normalized earnings through a full business cycle' : 'Earnings and cash flow',
      explanation: NORMALIZED_EARNINGS_MODELS.has(symbol)
        ? 'Profits can swing sharply in this industry, so Kestrel uses normalized earnings and avoids treating a peak year as permanent.'
        : 'Kestrel values the company on sustainable earnings, then checks the result against forward earnings, cash flow, and operating profit where available.',
      fairValue: range,
      primaryMetric: { label: 'Forward P/E', value: forwardPe, suffix: '×' },
      confidence: Number.isFinite(forwardPe) && Number.isFinite(priceToCashFlow) ? 'Medium' : 'Low',
    };
  }

  return {
    score: average([
      multipleScore(forwardPe, bands),
      multipleScore(priceToCashFlow, { cheap: 18, fair: 30 }),
      multipleScore(evToEbitda, { cheap: 12, fair: 24 }),
      multipleScore(evToRevenue, { cheap: 3, fair: 8 }),
    ]),
    method: 'Comparable market multiples',
    explanation: 'There is not enough stable per-share earnings evidence for a dependable fair-value range, so Kestrel only compares several market multiples.',
    fairValue: null,
    primaryMetric: { label: 'Forward P/E', value: forwardPe, suffix: '×' },
    confidence: 'Low',
  };
}

function assess(symbol, rawData, position = null) {
  const instrument = {
    listingMarket: 'US',
    currency: 'USD',
    benchmark: 'SPY',
    ...(INSTRUMENTS[symbol] || { name: symbol, sector: 'default', country: 'US' }),
  };
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
  const earningsEvidence = earningsView(rawData?.earnings);
  const estimateEvidence = estimateView(rawData?.analystIntelligence, currentPrice);

  const qualityParts = [
    metricScore(roe, [[30, 100], [20, 85], [15, 72], [8, 55], [0, 35], [-Infinity, 10]]),
    metricScore(margin, [[25, 100], [15, 85], [8, 68], [3, 52], [0, 35], [-Infinity, 10]]),
    metricScore(debtToEquity, [[-Infinity, null]]),
  ];
  if (Number.isFinite(debtToEquity)) {
    qualityParts[2] = debtToEquity <= 0.35 ? 95 : debtToEquity <= 0.8 ? 75 : debtToEquity <= 1.5 ? 50 : 20;
  }
  const quality = average(qualityParts);

  const valuationEvidence = valuationView(symbol, instrument, metrics, currentPrice, revenueGrowth, earningsGrowth, roe);
  let valuation = valuationEvidence.score;
  if (Number.isFinite(valuation) && Number.isFinite(peg) && peg > 0) {
    valuation = clamp(valuation + (peg <= 1 ? 7 : peg <= 1.8 ? 2 : peg > 3 ? -7 : 0));
  }

  const revenueScore = metricScore(revenueGrowth, [[20, 100], [10, 82], [5, 68], [0, 52], [-10, 30], [-Infinity, 10]]);
  const earningsScore = metricScore(earningsGrowth, [[25, 100], [10, 82], [3, 65], [0, 52], [-15, 28], [-Infinity, 8]]);
  const analystScore = average([
    analysts?.score ?? null,
    estimateEvidence?.score ?? null,
    earningsEvidence?.score ?? null,
  ]);
  const revisionAdjustment = estimateEvidence?.revision?.direction === 'up'
    ? 7
    : estimateEvidence?.revision?.direction === 'down' ? -9 : 0;
  const direction = average([
    revenueScore,
    earningsScore,
    analystScore === null ? null : clamp(analystScore + (analysts?.change || 0) + revisionAdjustment),
  ]);

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
  const secEvidence = rawData?.sec || null;
  const filingAgrees = secEvidence?.ratingReady === true;
  const filingConflict = (number(secEvidence?.conflictCount) || 0) > 0;
  let confidence = filingConflict
    ? 'Low'
    : evidenceCount >= 5 && analysts?.total >= 5
      ? (filingAgrees ? 'High' : 'Medium')
      : 'Low';
  if (confidence === 'High' && estimateEvidence?.disagreement > 60) confidence = 'Medium';

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
  if (estimateEvidence?.revision?.direction === 'up') positives.push('Analysts have raised their earnings or sales expectations since the previous snapshot.');
  if (estimateEvidence?.revision?.direction === 'down') risks.push('Analysts have cut their earnings or sales expectations since the previous snapshot.');
  if (earningsEvidence?.total >= 3 && earningsEvidence.beats >= 3) positives.push(`The company beat earnings expectations in ${earningsEvidence.beats} of the last ${earningsEvidence.total} reports.`);
  if (earningsEvidence?.total >= 3 && earningsEvidence.beats <= 1) risks.push('Recent earnings have repeatedly missed analyst expectations.');
  if (estimateEvidence?.targetUpside >= 15) positives.push('The analyst consensus target remains meaningfully above today’s price.');
  if (estimateEvidence?.targetUpside < -8) risks.push('The analyst consensus target is below today’s price.');
  if (estimateEvidence?.disagreement > 60) risks.push('Analysts disagree widely about what the shares are worth.');

  if (filingAgrees) positives.push('The latest official filing broadly agrees with the market-data figures.');
  if (filingConflict) risks.push('The official filing and market-data figures need reconciling before adding.');

  if (debtToEquity > 1.5) risks.push('Debt is high compared with shareholder capital.');
  if (beta > 1.8) risks.push('The share price has been much more volatile than the wider market.');
  if (drawdown < -35) risks.push('The shares remain in a deep fall from their yearly high.');

  const severeDeterioration = revenueGrowth < -12 && earningsGrowth < -18;
  const weakAgreement = quality < 38 && direction < 38 && (analystScore === null || analystScore < 45);
  const ultraCandidate = confidence === 'High'
    && score >= 86
    && quality >= 78
    && valuation >= 70
    && direction >= 72
    && analystScore >= 70
    && risks.length === 0;

  let action = 'Hold';
  if ((severeDeterioration || weakAgreement) && score < 43) action = 'Sell';
  else if (confidence === 'Medium' && score >= 68 && valuation >= 48 && direction >= 58) action = 'Buy';
  else if (confidence === 'High' && score >= 68 && valuation >= 48 && direction >= 58) action = ultraCandidate ? 'Ultra Buy' : 'Buy';

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
      forwardPe: number(metrics.forwardPE),
      priceToCashFlow: number(metrics.pfcfShareTTM),
      priceToBook: currentPrice && number(metrics.bookValuePerShareQuarterly)
        ? currentPrice / number(metrics.bookValuePerShareQuarterly)
        : null,
      evToEbitda: number(metrics.evEbitdaTTM),
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
      analystTarget: number(estimateEvidence?.target?.consensus) ?? number(estimateEvidence?.target?.median),
      analystTargetUpside: estimateEvidence?.targetUpside ?? null,
      analystDisagreement: estimateEvidence?.disagreement ?? null,
      earningsBeatRate: earningsEvidence?.total ? earningsEvidence.beats / earningsEvidence.total * 100 : null,
      earningsAverageSurprise: earningsEvidence?.averageSurprise ?? null,
    },
    componentScores: { quality, valuation, direction, analyst: analystScore, momentum },
    valuation: valuationEvidence,
    analystEvidence: estimateEvidence,
    earningsEvidence,
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
  if (action === 'Buy' || action === 'Ultra Buy') {
    if (action === 'Ultra Buy') return 'Several independent signals agree: business quality, valuation, direction, analysts, and the latest official filing.';
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

    if (weight >= 15 && (assessment.action === 'Buy' || assessment.action === 'Ultra Buy')) {
      assessment.action = 'Hold';
      assessment.reason = 'The company looks attractive, but this position is already large enough in your portfolio.';
      assessment.risks.unshift('Adding more would increase concentration risk.');
    }
  });
  return total;
}

function buildPortfolioRisk(assessments, total) {
  if (!total) return null;
  const items = Object.values(assessments).filter(item => item.positionValue > 0);
  const singleStocks = items.filter(item => item.instrument.type !== 'fund');
  const largestStock = [...singleStocks].sort((a, b) => b.portfolioWeight - a.portfolioWeight)[0] || null;
  const sectorValues = {};
  const countryValues = {};
  let marketFallLoss = 0;
  items.forEach(item => {
    sectorValues[item.instrument.sector] = (sectorValues[item.instrument.sector] || 0) + item.positionValue;
    countryValues[item.instrument.country] = (countryValues[item.instrument.country] || 0) + item.positionValue;
    const beta = number(item.metrics?.beta);
    const assumedFall = item.symbol === 'GLD'
      ? 5
      : item.instrument.type === 'fund' ? 20 : clamp((beta || 1) * 20, 10, 40);
    marketFallLoss += item.positionValue * assumedFall / 100;
  });
  const rankedSectors = Object.entries(sectorValues)
    .map(([name, value]) => ({ name, value, weight: value / total * 100 }))
    .sort((a, b) => b.value - a.value);
  const rankedCountries = Object.entries(countryValues)
    .map(([name, value]) => ({ name, value, weight: value / total * 100 }))
    .sort((a, b) => b.value - a.value);
  const largestSector = rankedSectors.find(item => item.name !== 'Broad market') || rankedSectors[0] || null;
  const largestCountry = rankedCountries[0] || null;
  const stressLossPercent = marketFallLoss / total * 100;
  const watch = (largestStock?.portfolioWeight || 0) > 20 || (largestSector?.weight || 0) > 45;
  return {
    status: watch ? 'Concentrated' : 'Reasonably spread',
    largestStock,
    largestSector,
    largestCountry,
    stressLossPercent,
    sectorWeights: rankedSectors,
  };
}

function compareOpportunity(opportunity, assessments, portfolioRisk) {
  const owned = Object.values(assessments).filter(item => item.positionValue > 0 && item.instrument.type !== 'fund');
  const weakest = [...owned].sort((a, b) => {
    const actionOrder = { Sell: 0, Hold: 1, Buy: 2, 'Ultra Buy': 3 };
    return (actionOrder[a.action] - actionOrder[b.action]) || ((a.score ?? 50) - (b.score ?? 50));
  })[0] || null;
  const sectorWeight = portfolioRisk?.sectorWeights.find(item => item.name === opportunity.instrument.sector)?.weight || 0;
  const scoreAdvantage = weakest && Number.isFinite(opportunity.score) && Number.isFinite(weakest.score)
    ? opportunity.score - weakest.score
    : null;
  if (weakest && scoreAdvantage >= 8) {
    return {
      type: 'replacement',
      title: `Compare with ${weakest.instrument.name}`,
      detail: `${opportunity.instrument.name} currently has a stronger evidence score, but taxes, costs, and your original thesis still matter before replacing anything.`,
      symbol: weakest.symbol,
      scoreAdvantage,
    };
  }
  if (sectorWeight < 8) {
    return {
      type: 'diversification',
      title: `Adds ${opportunity.instrument.sector.toLowerCase()} exposure`,
      detail: 'This idea adds a business area that is currently small or absent in your portfolio.',
    };
  }
  return {
    type: 'watch',
    title: 'A new idea, not an automatic replacement',
    detail: 'Its evidence is attractive, but it does not clearly improve the current portfolio enough to force a trade.',
  };
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
  const portfolioRisk = buildPortfolioRisk(assessments, portfolioTotal);

  const candidateAssessments = dashboard.opportunityUniverse
    .filter(symbol => !state.positions[symbol]?.shares)
    .map(symbol => assess(symbol, dashboard.data[symbol], null));
  state.opportunities = candidateAssessments
    .filter(item => item.action === 'Buy' && item.confidence !== 'Low')
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(item => ({ ...item, comparison: compareOpportunity(item, assessments, portfolioRisk) }));

  renderBrief(dashboard, ownedSymbols, assessments);
  renderHoldings(symbolsToShow, assessments, ownedSymbols.length > 0);
  renderPortfolioValue(portfolioTotal, ownedSymbols);
  renderPortfolioRisk(portfolioRisk, ownedSymbols);
  renderOpportunities(dashboard);
  renderChanges(dashboard);
  recordDailySignals(dashboard, [...Object.values(assessments), ...candidateAssessments]);
}

async function recordDailySignals(dashboard, assessments) {
  if (dashboard.status !== 'ready' || !dashboard.lastFullRefresh) return;
  const snapshotKey = String(dashboard.lastFullRefresh);
  if (state.savedSignalsFor === snapshotKey) return;
  state.savedSignalsFor = snapshotKey;
  const signals = assessments
    .filter(item => item.action !== 'Checking' && Number.isFinite(item.metrics?.currentPrice))
    .map(item => ({
      symbol: item.symbol,
      action: item.action,
      confidence: item.confidence,
      score: item.score,
      price: item.metrics.currentPrice,
      owned: Boolean(state.positions[item.symbol]?.shares),
      reason: item.reason,
    }));
  try {
    const response = await fetch('/api/signals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signals, evidenceTimestamp: dashboard.lastFullRefresh }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Signal journal rejected the snapshot');
    renderCalibration(payload.calibration);
  } catch (error) {
    state.savedSignalsFor = null;
    els.calibrationSummary.textContent = 'The signal journal is temporarily unavailable.';
    els.calibrationGrid.innerHTML = `<div class="empty-card wide"><strong>Track record not saved</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderCalibration(calibration) {
  if (!calibration) return;
  const hasOutcomes = calibration.maturedSignals > 0;
  els.calibrationSummary.textContent = hasOutcomes
    ? `${calibration.maturedSignals} calls have reached their first review date.`
    : 'Signals are stored exactly as they appeared; outcomes need time.';
  const reviewDate = calibration.firstReviewDate
    ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${calibration.firstReviewDate}T00:00:00Z`))
    : 'After the first actionable call';
  els.calibrationGrid.innerHTML = `
    <article>
      <span>Evidence days stored</span>
      <strong>${escapeHtml(calibration.recordedDays)}</strong>
      <p>${escapeHtml(calibration.signalsRecorded)} point-in-time assessments saved locally.</p>
    </article>
    <article>
      <span>30-day hit rate</span>
      <strong>${hasOutcomes && calibration.hitRate !== null ? plainPercent(calibration.hitRate) : 'Not ready'}</strong>
      <p>${hasOutcomes ? 'Directional Buy and Sell calls only.' : `First review: ${escapeHtml(reviewDate)}.`}</p>
    </article>
    <article>
      <span>High-confidence check</span>
      <strong>${calibration.highConfidenceHitRate !== null ? plainPercent(calibration.highConfidenceHitRate) : 'Not ready'}</strong>
      <p>High confidence must prove more dependable than Medium confidence.</p>
    </article>
    <article>
      <span>Model version</span>
      <strong>${escapeHtml(calibration.modelVersion)}</strong>
      <p>${escapeHtml(calibration.method)}.</p>
    </article>`;
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

function renderPortfolioRisk(risk, ownedSymbols) {
  if (!ownedSymbols.length || !risk) {
    els.portfolioRiskSection.hidden = true;
    return;
  }
  els.portfolioRiskSection.hidden = false;
  els.portfolioRiskSummary.textContent = risk.status === 'Concentrated'
    ? 'One part of the portfolio deserves a closer look.'
    : 'No major concentration warning is visible.';
  const stockName = risk.largestStock?.instrument.name || 'No single company';
  const stockWeight = risk.largestStock?.portfolioWeight || 0;
  els.portfolioRiskGrid.innerHTML = `
    <article>
      <span>Largest single company</span>
      <strong>${escapeHtml(stockName)}</strong>
      <p>${risk.largestStock ? `${plainPercent(stockWeight)} of the portfolio${stockWeight > 20 ? ' · above the 20% caution line' : ''}` : 'Broad funds are excluded from this measure.'}</p>
    </article>
    <article>
      <span>Largest business area</span>
      <strong>${escapeHtml(risk.largestSector?.name || 'Not available')}</strong>
      <p>${risk.largestSector ? `${plainPercent(risk.largestSector.weight)} of the portfolio` : 'Add holdings to calculate this exposure.'}</p>
    </article>
    <article>
      <span>Largest company home</span>
      <strong>${escapeHtml(risk.largestCountry?.name || 'Not available')}</strong>
      <p>${risk.largestCountry ? `${plainPercent(risk.largestCountry.weight)} of the portfolio by company domicile` : 'Country exposure is not available.'}</p>
    </article>
    <article>
      <span>Rough market-fall test</span>
      <strong>About −${plainPercent(risk.stressLossPercent)}</strong>
      <p>A simple estimate if broad markets fell 20%; this is not a worst-case forecast.</p>
    </article>`;
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
  const { symbol, instrument, reason, metrics, confidence, comparison } = item;
  return `
    <article class="opportunity-card">
      <div>
        <h3>${escapeHtml(instrument.name)} <span class="ticker">${escapeHtml(symbol)}</span></h3>
        <span class="company-price">${money(metrics.currentPrice, 2)} · ${escapeHtml(instrument.country)}</span>
      </div>
      <span class="opportunity-rank">0${index + 1}</span>
      <p class="opportunity-reason">${escapeHtml(reason)}</p>
      ${comparison ? `<p class="opportunity-comparison"><strong>${escapeHtml(comparison.title)}</strong>${escapeHtml(comparison.detail)}</p>` : ''}
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

  const { instrument, action, confidence, reason, positives, risks, metrics, componentScores, rawData, valuation, analystEvidence, earningsEvidence } = item;
  const positiveList = positives.length ? positives : ['No strong positive evidence is available yet.'];
  const riskList = risks.length ? risks : ['No major quantitative warning is visible in the available data.'];
  const fetched = rawData?.fetchedAt ? new Date(rawData.fetchedAt * 1000).toLocaleString() : 'Unknown';

  els.detailContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(instrument.country)} company · ${escapeHtml(instrument.listingMarket)} listing · ${escapeHtml(instrument.sector)}</p>
    <h2>${escapeHtml(instrument.name)} <span class="ticker">${escapeHtml(symbol)}</span></h2>
    <div class="detail-hero" data-action="${escapeHtml(action)}">
      <strong>${escapeHtml(action)}</strong>
      <p>${escapeHtml(reason)}</p>
    </div>
    <div class="detail-section chart-section">
      <div class="chart-heading">
        <div><h3>Price history</h3><p id="chartSummary">Loading verified price history</p></div>
        <div class="chart-ranges" role="group" aria-label="Price history range">
          ${['1D', '1W', '1M', '1Y', '5Y', 'All'].map(range => `<button type="button" data-history-range="${range.toLowerCase()}">${range}</button>`).join('')}
        </div>
      </div>
      <div class="history-chart" id="historyChart" aria-live="polite">
        <div class="chart-loading"><span></span><strong>Loading price evidence</strong></div>
      </div>
      <p class="chart-source" id="chartSource"></p>
    </div>
    <div class="detail-section">
      <h3>What looks like fair value</h3>
      ${renderFairValue(valuation, metrics?.currentPrice)}
    </div>
    <div class="detail-section">
      <h3>The investment thesis</h3>
      ${renderThesis(item)}
    </div>
    ${item.comparison ? `<div class="detail-section">
      <h3>How it could fit your portfolio</h3>
      <div class="fit-card"><strong>${escapeHtml(item.comparison.title)}</strong><p>${escapeHtml(item.comparison.detail)}</p></div>
    </div>` : ''}
    <div class="detail-section">
      <h3>What analysts are changing</h3>
      ${renderAnalystEvidence(analystEvidence, earningsEvidence)}
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
        ${metricTile('Forward price versus earnings', metrics?.forwardPe ? `${metrics.forwardPe.toFixed(1)}×` : 'Not available')}
        ${metricTile('Price versus cash flow', metrics?.priceToCashFlow ? `${metrics.priceToCashFlow.toFixed(1)}×` : 'Not available')}
        ${metricTile('Sales growth', percent(metrics?.revenueGrowth))}
        ${metricTile('Earnings growth', percent(metrics?.earningsGrowth))}
        ${metricTile('Return on equity', plainPercent(metrics?.roe))}
        ${metricTile('Profit margin', plainPercent(metrics?.margin))}
        ${metricTile('Positive analysts', metrics?.analystPositive === null || metrics?.analystPositive === undefined ? 'Not available' : plainPercent(metrics.analystPositive, 0))}
      </div>
    </div>
    <div class="detail-section">
      <h3>Evidence status</h3>
      ${renderEvidenceStatus(rawData?.sec, confidence, fetched)}
      ${item.ultraCandidate && action !== 'Ultra Buy' ? '<p class="plain-reason"><strong>Worth noting:</strong> This company clears the quantitative Ultra Buy bar, but portfolio risk still prevents that rating.</p>' : ''}
      ${rawData?.errors?.length ? `<p class="plain-reason"><strong>Missing evidence:</strong> ${escapeHtml(rawData.errors.join(' · '))}</p>` : ''}
    </div>`;

  els.detailDialog.showModal();
  setupHistoryChart(symbol);
}

function renderFairValue(valuation, currentPrice) {
  if (!valuation) {
    return '<div class="fair-value-empty"><strong>Not enough evidence</strong><span>Kestrel will not invent a precise value without a suitable model.</span></div>';
  }
  const range = valuation.fairValue;
  const modelCopy = `<p class="valuation-method"><strong>${escapeHtml(valuation.method)}</strong><span>${escapeHtml(valuation.explanation)}</span></p>`;
  if (!range) {
    return `${modelCopy}<div class="fair-value-empty"><strong>No dependable range yet</strong><span>Market multiples are included in the score, but the available figures do not support a responsible per-share range.</span></div>`;
  }
  const difference = Number.isFinite(currentPrice) && range.base
    ? ((currentPrice - range.base) / range.base) * 100
    : null;
  const comparison = difference === null
    ? 'Today’s price could not be compared.'
    : Math.abs(difference) < 4
      ? 'Today’s price is close to the reasonable case.'
      : `Today’s price is about ${Math.abs(difference).toFixed(0)}% ${difference > 0 ? 'above' : 'below'} the reasonable case.`;
  return `${modelCopy}
    <div class="fair-value-band">
      <div><span>Conservative</span><strong>${money(range.low, 2)}</strong></div>
      <div class="is-base"><span>Reasonable</span><strong>${money(range.base, 2)}</strong></div>
      <div><span>Optimistic</span><strong>${money(range.high, 2)}</strong></div>
    </div>
    <p class="fair-value-note">${escapeHtml(comparison)} This is a valuation range, not a price prediction.</p>`;
}

function renderThesis(item) {
  const { instrument, action, positives, risks, metrics, valuation, rawData } = item;
  const sectorNeeds = {
    Semiconductors: 'Demand, margins, and cash generation must remain healthy through the industry cycle.',
    Software: 'Sales growth and profit margins must remain durable without excessive spending or dilution.',
    'Financial services': 'Returns on shareholder capital must stay strong while credit and funding risks remain controlled.',
    Healthcare: 'Earnings growth must persist and the product or treatment pipeline must continue delivering.',
    Consumer: 'Demand, pricing power, and margins must hold up through weaker economic periods.',
    Industrial: 'Order demand and cash generation must remain healthy across the economic cycle.',
    Utilities: 'New investment must earn sensible returns without debt becoming uncomfortable.',
    Energy: 'Cash generation must remain resilient at less favourable commodity prices.',
  };
  const status = action === 'Sell'
    ? 'Thesis looks broken'
    : risks.length >= 3 || rawData?.sec?.conflictCount
      ? 'Needs watching'
      : 'Thesis is on track';
  const statusClass = action === 'Sell' ? 'is-broken' : status === 'Needs watching' ? 'is-watch' : 'is-on-track';
  const changeConditions = [];
  if (rawData?.sec?.conflictCount) changeConditions.push('Reconcile the disagreement between the official filing and market-data feed.');
  changeConditions.push('Reassess if sales and earnings both start shrinking.');
  changeConditions.push('Reassess if analyst estimates trend down across more than one snapshot.');
  if (valuation?.fairValue?.high) changeConditions.push(`Do not add blindly if the price rises beyond the optimistic value of ${money(valuation.fairValue.high, 2)}.`);

  return `<div class="thesis-card ${statusClass}">
    <div class="thesis-status"><span>Current status</span><strong>${escapeHtml(status)}</strong></div>
    <div class="thesis-columns">
      <div><span>Why own it</span><p>${escapeHtml(positives.slice(0, 2).join(' ') || item.reason)}</p></div>
      <div><span>What must stay true</span><p>${escapeHtml(instrument.type === 'fund' ? 'The fund must continue serving its diversification role at an appropriate portfolio weight.' : sectorNeeds[instrument.sector] || 'Business quality, growth, and financial strength must remain intact.')}</p></div>
      <div><span>What would change the view</span><ul>${changeConditions.slice(0, 3).map(text => `<li>${escapeHtml(text)}</li>`).join('')}</ul></div>
    </div>
  </div>`;
}

function renderAnalystEvidence(analystEvidence, earningsEvidence) {
  if (!analystEvidence && !earningsEvidence) {
    return '<div class="fair-value-empty"><strong>No dependable analyst history</strong><span>Kestrel will not treat missing analyst data as positive evidence.</span></div>';
  }
  const target = analystEvidence?.target || {};
  const estimate = analystEvidence?.estimate || null;
  const revision = analystEvidence?.revision || null;
  const revisionCopy = revision?.status === 'baseline'
    ? 'Today establishes the estimate baseline. Changes will appear after later daily snapshots.'
    : revision?.direction === 'up'
      ? 'Earnings or sales expectations have moved up since the earlier snapshot.'
      : revision?.direction === 'down'
        ? 'Earnings or sales expectations have moved down since the earlier snapshot.'
        : revision?.status === 'compared' ? 'Expectations are broadly unchanged.' : 'Estimate changes are not available yet.';
  const beatCopy = earningsEvidence?.total
    ? `${earningsEvidence.beats} of the last ${earningsEvidence.total} reported earnings figures beat expectations.`
    : 'Recent earnings surprises are not available.';

  return `<div class="analyst-evidence-grid">
    <div>
      <span>Consensus price range</span>
      <strong>${number(target.low) ? money(number(target.low), 2) : '—'} – ${number(target.high) ? money(number(target.high), 2) : '—'}</strong>
      <small>Central view ${number(target.consensus) || number(target.median) ? money(number(target.consensus) ?? number(target.median), 2) : 'not available'}</small>
    </div>
    <div>
      <span>Next annual estimate</span>
      <strong>${estimate?.epsAverage !== null && estimate?.epsAverage !== undefined ? `${money(number(estimate.epsAverage), 2)} EPS` : 'Not available'}</strong>
      <small>${estimate ? `${estimate.epsAnalysts || 0} EPS analysts · year ending ${escapeHtml(estimate.fiscalDate || '—')}` : 'No estimate returned'}</small>
    </div>
    <div>
      <span>Estimate direction</span>
      <strong>${revision?.direction === 'up' ? 'Rising' : revision?.direction === 'down' ? 'Falling' : revision?.status === 'compared' ? 'Stable' : 'Baseline'}</strong>
      <small>${escapeHtml(revisionCopy)}</small>
    </div>
    <div>
      <span>Recent earnings</span>
      <strong>${earningsEvidence?.averageSurprise !== null && earningsEvidence?.averageSurprise !== undefined ? percent(earningsEvidence.averageSurprise) : 'Not available'}</strong>
      <small>${escapeHtml(beatCopy)}</small>
    </div>
  </div>
  <p class="chart-source">${escapeHtml(analystEvidence?.source || 'Finnhub earnings history')}. Analyst targets are opinions, not verified company results.</p>`;
}

function setupHistoryChart(symbol) {
  const selectedRange = state.historyRangeBySymbol[symbol] || '1y';
  document.querySelectorAll('[data-history-range]').forEach(button => {
    const isSelected = button.dataset.historyRange === selectedRange;
    button.classList.toggle('is-active', isSelected);
    button.setAttribute('aria-pressed', String(isSelected));
    button.addEventListener('click', () => {
      state.historyRangeBySymbol[symbol] = button.dataset.historyRange;
      document.querySelectorAll('[data-history-range]').forEach(candidate => {
        const active = candidate === button;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-pressed', String(active));
      });
      loadHistory(symbol, button.dataset.historyRange);
    });
  });
  loadHistory(symbol, selectedRange);
}

async function loadHistory(symbol, range) {
  state.historyRequest?.abort();
  state.historyRequest = new AbortController();
  const chart = document.getElementById('historyChart');
  const summary = document.getElementById('chartSummary');
  const source = document.getElementById('chartSource');
  if (!chart || !summary || !source) return;
  chart.innerHTML = '<div class="chart-loading"><span></span><strong>Loading price evidence</strong></div>';
  summary.textContent = `Checking the ${range.toUpperCase()} record`;
  source.textContent = '';
  try {
    const response = await fetch(`/api/history?symbol=${encodeURIComponent(symbol)}&range=${encodeURIComponent(range)}`, {
      cache: 'no-store',
      signal: state.historyRequest.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Price history is unavailable');
    renderHistoryChart(payload, chart, summary, source);
  } catch (error) {
    if (error.name === 'AbortError') return;
    chart.innerHTML = `<div class="chart-error"><strong>Price history is unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
    summary.textContent = 'The rating still uses current market and company evidence';
  }
}

function renderHistoryChart(payload, chart, summary, source) {
  const points = (payload.points || [])
    .map(point => ({ ...point, close: number(point.close), timestamp: number(point.timestamp) }))
    .filter(point => point.close !== null && point.timestamp !== null);
  if (!points.length) throw new Error('No prices were returned for this period');

  const width = 720;
  const height = 250;
  const inset = { top: 20, right: 16, bottom: 30, left: 16 };
  const closes = points.map(point => point.close);
  const minimum = Math.min(...closes);
  const maximum = Math.max(...closes);
  const spread = maximum - minimum || maximum * 0.02 || 1;
  const low = minimum - spread * 0.08;
  const high = maximum + spread * 0.08;
  const x = index => inset.left + (index / Math.max(1, points.length - 1)) * (width - inset.left - inset.right);
  const y = value => inset.top + ((high - value) / (high - low)) * (height - inset.top - inset.bottom);
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${x(index).toFixed(2)} ${y(point.close).toFixed(2)}`).join(' ');
  const area = `${path} L ${x(points.length - 1).toFixed(2)} ${height - inset.bottom} L ${x(0).toFixed(2)} ${height - inset.bottom} Z`;
  const first = points[0];
  const last = points.at(-1);
  const periodReturn = number(payload.periodReturn) ?? ((last.close - first.close) / first.close * 100);
  const directionClass = periodReturn >= 0 ? 'is-up' : 'is-down';
  const directionText = `${periodReturn >= 0 ? '+' : ''}${periodReturn.toFixed(1)}%`;
  const rangeLabel = String(payload.range || '').toUpperCase();
  summary.innerHTML = `<strong class="${directionClass}">${directionText}</strong> over ${escapeHtml(rangeLabel)} · ${money(last.close, 2)} latest`;

  chart.className = `history-chart ${directionClass}`;
  chart.innerHTML = `
    <div class="chart-stage">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(payload.symbol)} price changed ${escapeHtml(directionText)} over ${escapeHtml(rangeLabel)}">
        <defs><linearGradient id="historyArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-opacity="0.2"/><stop offset="1" stop-opacity="0"/></linearGradient></defs>
        <line class="chart-grid" x1="${inset.left}" x2="${width - inset.right}" y1="${y(maximum)}" y2="${y(maximum)}"/>
        <line class="chart-grid" x1="${inset.left}" x2="${width - inset.right}" y1="${y(minimum)}" y2="${y(minimum)}"/>
        <path class="chart-area" d="${area}"/>
        <path class="chart-line" d="${path}"/>
        <line class="chart-crosshair" x1="0" x2="0" y1="${inset.top}" y2="${height - inset.bottom}" hidden/>
        <circle class="chart-point" cx="0" cy="0" r="5" hidden/>
        <text class="chart-axis chart-axis-high" x="${width - inset.right}" y="${Math.max(12, y(maximum) - 6)}">${escapeHtml(money(maximum, 2))}</text>
        <text class="chart-axis" x="${inset.left}" y="${height - 7}">${escapeHtml(formatHistoryDate(first, payload.range))}</text>
        <text class="chart-axis chart-axis-end" x="${width - inset.right}" y="${height - 7}">${escapeHtml(formatHistoryDate(last, payload.range))}</text>
      </svg>
      <div class="chart-tooltip" hidden><strong></strong><span></span></div>
    </div>
    ${payload.session ? `<div class="session-stats">
      ${metricTile('Open', money(number(payload.session.open), 2))}
      ${metricTile('High', money(number(payload.session.high), 2))}
      ${metricTile('Low', money(number(payload.session.low), 2))}
      ${metricTile('Latest', money(number(payload.session.current), 2))}
    </div>` : ''}`;

  const stage = chart.querySelector('.chart-stage');
  const svg = chart.querySelector('svg');
  const crosshair = chart.querySelector('.chart-crosshair');
  const dot = chart.querySelector('.chart-point');
  const tooltip = chart.querySelector('.chart-tooltip');
  const showPoint = event => {
    const bounds = svg.getBoundingClientRect();
    const relative = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const index = Math.round(relative * (points.length - 1));
    const point = points[index];
    const pointX = x(index);
    const pointY = y(point.close);
    crosshair.setAttribute('x1', pointX);
    crosshair.setAttribute('x2', pointX);
    crosshair.removeAttribute('hidden');
    dot.setAttribute('cx', pointX);
    dot.setAttribute('cy', pointY);
    dot.removeAttribute('hidden');
    tooltip.querySelector('strong').textContent = money(point.close, 2);
    tooltip.querySelector('span').textContent = formatHistoryDate(point, payload.range, true);
    tooltip.style.left = `${relative * 100}%`;
    tooltip.classList.toggle('is-left', relative > 0.72);
    tooltip.hidden = false;
  };
  stage.addEventListener('pointermove', showPoint);
  stage.addEventListener('pointerleave', () => {
    crosshair.setAttribute('hidden', '');
    dot.setAttribute('hidden', '');
    tooltip.hidden = true;
  });

  const limitedText = payload.limited ? ' Intraday detail builds from snapshots while Kestrel is running.' : '';
  const rawCount = number(payload.rawPointCount);
  const sampleText = rawCount && rawCount > points.length ? ` ${rawCount.toLocaleString()} source observations are represented.` : '';
  const crossCheck = payload.latestCrossCheck?.status === 'review'
    ? ' The latest daily close and live quote differ enough to warrant caution.'
    : '';
  source.textContent = `${payload.method} from ${payload.source}.${limitedText}${sampleText}${crossCheck}`;
}

function formatHistoryDate(point, range, detailed = false) {
  const date = new Date(point.timestamp * 1000);
  if (range === '1d') {
    return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: detailed ? 'short' : undefined }).format(date);
  }
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: detailed || range === '1y' || range === '5y' || range === 'all' ? 'numeric' : undefined,
    timeZone: 'UTC',
  }).format(date);
}

function renderEvidenceStatus(sec, confidence, marketFetched) {
  const marketLine = `<p class="plain-reason"><strong>${escapeHtml(confidence)} confidence.</strong> Market and analyst data came through Finnhub at ${escapeHtml(marketFetched)}.</p>`;
  if (!sec || sec.status === 'error' || sec.status === 'unavailable') {
    const message = sec?.message || 'The official filing check has not completed yet.';
    return `${marketLine}<div class="evidence-card is-limited"><strong>Official filing not verified</strong><span>${escapeHtml(message)}</span></div>`;
  }
  if (sec.status === 'not_applicable') {
    return `${marketLine}<div class="evidence-card is-neutral"><strong>Fund assessment</strong><span>${escapeHtml(sec.message)}</span></div>`;
  }

  const filing = sec.filing || {};
  const checks = Array.isArray(sec.checks) ? sec.checks : [];
  const statusText = sec.ratingReady ? 'Official figures agree' : sec.status === 'verified' ? 'Official filing checked' : 'Official filing is incomplete';
  const statusClass = sec.ratingReady ? 'is-verified' : (sec.conflictCount ? 'is-review' : 'is-limited');
  const filingLink = filing.url
    ? `<a href="${escapeHtml(filing.url)}" target="_blank" rel="noopener">Open ${escapeHtml(filing.form || 'filing')} filed ${escapeHtml(filing.filed || '')}</a>`
    : `<span>${escapeHtml(filing.form || 'Filing')} filed ${escapeHtml(filing.filed || 'on an unknown date')}</span>`;
  const checkRows = checks.length
    ? `<div class="source-checks">${checks.map(check => `
        <div class="source-check" data-status="${escapeHtml(check.status)}">
          <span>${escapeHtml(check.label)}</span>
          <strong>${check.status === 'agrees' ? 'Broadly agrees' : 'Needs review'}</strong>
          <small>Filing ${plainPercent(number(check.officialValue))} · market feed ${plainPercent(number(check.marketValue))}</small>
        </div>`).join('')}</div>`
    : '<p class="source-note">The filing is available, but comparable figures were not found for an independent check.</p>';

  return `${marketLine}
    <div class="evidence-card ${statusClass}">
      <div class="evidence-card-head"><strong>${escapeHtml(statusText)}</strong><span>${escapeHtml(sec.source || 'U.S. SEC EDGAR')}</span></div>
      <div class="source-filing">${filingLink}<span>Reporting period ended ${escapeHtml(sec.facts?.periodEnd || filing.periodEnd || '—')}</span></div>
      ${checkRows}
    </div>`;
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
