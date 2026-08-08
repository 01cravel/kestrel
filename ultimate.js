const DEFAULT_CAPITAL = 300000;
const CAPITAL_STORAGE_KEY = 'kestrel_ultimate_capital_v1';

const PORTFOLIO = [
  { symbol: 'VTI', weight: 20 }, { symbol: 'AVUV', weight: 8 },
  { symbol: 'VEA', weight: 7 }, { symbol: 'IEMG', weight: 7 },
  { symbol: 'AVDV', weight: 5 }, { symbol: 'PAVE', weight: 5 },
  { symbol: 'TSM', weight: 6 }, { symbol: 'GOOGL', weight: 6 },
  { symbol: 'AMZN', weight: 5 }, { symbol: 'ASML', weight: 5 },
  { symbol: 'MELI', weight: 5 }, { symbol: 'ETN', weight: 4 },
  { symbol: 'ISRG', weight: 4 }, { symbol: 'CEG', weight: 3 },
  { symbol: 'IBIT', weight: 8 }, { symbol: 'SGOV', weight: 2 },
];

const COMPANIES = [
  { symbol: 'TSM', name: 'TSMC' }, { symbol: 'GOOGL', name: 'Alphabet' },
  { symbol: 'AMZN', name: 'Amazon' }, { symbol: 'ASML', name: 'ASML' },
  { symbol: 'MELI', name: 'MercadoLibre' }, { symbol: 'ETN', name: 'Eaton' },
  { symbol: 'ISRG', name: 'Intuitive Surgical' }, { symbol: 'CEG', name: 'Constellation' },
];

const SCENARIOS = [
  {
    name: 'Severe global recession',
    description: 'Demand collapses, unemployment rises sharply and investors abandon risky assets.',
    shocks: { VTI:-31, AVUV:-40, VEA:-32, IEMG:-36, AVDV:-40, PAVE:-35, TSM:-38, GOOGL:-32, AMZN:-35, ASML:-40, MELI:-45, ETN:-38, ISRG:-28, CEG:-25, IBIT:-50, SGOV:1 },
  },
  {
    name: 'AI spending disappointment',
    description: 'AI demand remains real, but customers delay spending and expected profits arrive much later.',
    shocks: { VTI:-18, AVUV:-12, VEA:-14, IEMG:-22, AVDV:-14, PAVE:-24, TSM:-48, GOOGL:-30, AMZN:-28, ASML:-44, MELI:-16, ETN:-34, ISRG:-10, CEG:-30, IBIT:-28, SGOV:1 },
  },
  {
    name: 'Inflation and rates shock',
    description: 'Inflation returns, borrowing costs rise and investors pay less for distant future profits.',
    shocks: { VTI:-25, AVUV:-24, VEA:-22, IEMG:-26, AVDV:-24, PAVE:-20, TSM:-27, GOOGL:-28, AMZN:-32, ASML:-30, MELI:-35, ETN:-22, ISRG:-32, CEG:-14, IBIT:-40, SGOV:0 },
  },
  {
    name: 'Technology crash',
    description: 'The market abruptly reprices profitable technology companies as it did after previous bubbles.',
    shocks: { VTI:-32, AVUV:-22, VEA:-21, IEMG:-34, AVDV:-22, PAVE:-28, TSM:-58, GOOGL:-48, AMZN:-48, ASML:-54, MELI:-43, ETN:-34, ISRG:-34, CEG:-27, IBIT:-55, SGOV:1 },
  },
];

const UPSIDE_SCENARIOS = [
  {
    name: 'Productive markets',
    annualReturn: 12,
    description: 'Company profits grow, valuations remain broadly stable and diversification does its job.',
  },
  {
    name: 'Strong execution',
    annualReturn: 22,
    description: 'AI, cloud, electrification and international growth all deliver better-than-normal progress.',
  },
  {
    name: 'Exceptional cycle',
    annualReturn: 35,
    description: 'Several high-conviction themes succeed together and Bitcoin also contributes strongly.',
  },
];

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compactMoney = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 });
const number = value => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const ordinal = value => {
  const rounded = Math.round(value);
  const mod100 = rounded % 100;
  const suffix = mod100 >= 11 && mod100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[rounded % 10] || 'th');
  return `${rounded}${suffix}`;
};

function loadCapital() {
  try {
    const saved = number(localStorage.getItem(CAPITAL_STORAGE_KEY));
    return saved && saved >= 1000 ? saved : DEFAULT_CAPITAL;
  } catch (error) {
    return DEFAULT_CAPITAL;
  }
}

let capital = loadCapital();

function setStatus(element, text, state) {
  element.textContent = text;
  element.className = `lab-status is-${state}`;
}

function renderScenarios() {
  const grid = document.getElementById('stressGrid');
  grid.replaceChildren(...SCENARIOS.map(scenario => {
    const loss = PORTFOLIO.reduce((total, holding) => total + holding.weight * scenario.shocks[holding.symbol] / 100, 0);
    const remaining = capital * (1 + loss / 100);
    const article = document.createElement('article');
    article.className = 'stress-card';
    const body = document.createElement('div');
    const title = document.createElement('h4');
    title.textContent = scenario.name;
    const lossNode = document.createElement('strong');
    lossNode.className = 'stress-loss';
    lossNode.textContent = `${loss.toFixed(1)}%`;
    const value = document.createElement('span');
    value.className = 'stress-value';
    value.textContent = `${money.format(remaining)} remaining`;
    const explanation = document.createElement('p');
    explanation.textContent = scenario.description;
    body.append(title, lossNode, value, explanation);

    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'See every shock assumption';
    const list = document.createElement('div');
    list.className = 'shock-list';
    PORTFOLIO.forEach(holding => {
      const item = document.createElement('span');
      const label = document.createTextNode(holding.symbol);
      const shock = document.createElement('b');
      shock.textContent = `${scenario.shocks[holding.symbol]}%`;
      item.append(label, shock);
      list.append(item);
    });
    details.append(summary, list);
    article.append(body, details);
    return article;
  }));
}

function renderUpsideScenarios() {
  const grid = document.getElementById('upsideGrid');
  grid.replaceChildren(...UPSIDE_SCENARIOS.map(scenario => {
    const totalReturn = (Math.pow(1 + scenario.annualReturn / 100, 2) - 1) * 100;
    const finalValue = capital * (1 + totalReturn / 100);
    const article = document.createElement('article');
    article.className = 'upside-card';
    const title = document.createElement('h5');
    title.textContent = scenario.name;
    const returnNode = document.createElement('strong');
    returnNode.textContent = `+${totalReturn.toFixed(1)}%`;
    const value = document.createElement('span');
    value.textContent = money.format(finalValue);
    const assumption = document.createElement('small');
    assumption.textContent = `${scenario.annualReturn}% a year for two years`;
    const explanation = document.createElement('p');
    explanation.textContent = scenario.description;
    article.append(title, returnNode, value, assumption, explanation);
    return article;
  }));
}

function updateAllocationAmounts() {
  document.querySelectorAll('.ledger-row').forEach(row => {
    const symbol = row.querySelector('b')?.textContent?.trim();
    const holding = PORTFOLIO.find(item => item.symbol === symbol);
    const amount = row.querySelector('.ledger-money strong');
    if (holding && amount) amount.textContent = money.format(capital * holding.weight / 100);
  });
  document.querySelectorAll('[data-group-weight]').forEach(group => {
    const weight = number(group.dataset.groupWeight);
    if (weight !== null) group.textContent = `${weight}% · ${money.format(capital * weight / 100)}`;
  });
}

function renderCapital() {
  const formatted = money.format(capital);
  ['heroCapital', 'mandateCapital', 'runwayCapital', 'outcomeCapital'].forEach(id => {
    const element = document.getElementById(id);
    if (element) element.textContent = formatted;
  });
  document.getElementById('capitalInput').value = String(Math.round(capital));
  updateAllocationAmounts();
  renderUpsideScenarios();
  renderScenarios();
}

function saveCapital(nextCapital) {
  capital = Math.max(1000, Math.round(nextCapital));
  try {
    localStorage.setItem(CAPITAL_STORAGE_KEY, String(capital));
  } catch (error) {
    // The calculator still works when browser storage is unavailable.
  }
  renderCapital();
}

function renderValuations(fundamentals = {}) {
  const companies = fundamentals.companies || {};
  const rows = COMPANIES.map(company => {
    const record = companies[company.symbol] || {};
    const current = record.current || {};
    const comparison = record.comparison || {};
    const percentile = comparison.percentile === null || comparison.percentile === undefined
      ? null
      : number(comparison.percentile);
    const currentPrice = current.price === null || current.price === undefined ? null : number(current.price);
    const currentPe = current.pe === null || current.pe === undefined ? null : number(current.pe);
    const priceCheck = record.independentPriceCheck || {};
    const row = document.createElement('div');
    row.className = 'valuation-row';
    row.setAttribute('role', 'row');
    const companyCell = document.createElement('div');
    companyCell.innerHTML = `<b>${company.symbol}</b><small>${company.name}${current.filed ? ` · filed ${current.filed}` : ''}</small>`;
    const priceCell = document.createElement('div');
    const priceValue = document.createElement('strong');
    priceValue.textContent = currentPrice !== null ? `$${currentPrice.toFixed(2)}` : '—';
    const priceProof = document.createElement('small');
    const matched = Number(priceCheck.datesMatched || 0);
    const required = Number(priceCheck.datesRequired || 0);
    const maximumDifference = number(priceCheck.maximumDifferencePct);
    priceProof.className = priceCheck.ready ? 'price-proof is-verified' : 'price-proof is-limited';
    priceProof.textContent = priceCheck.ready
      ? `Nasdaq agrees ${matched}/${required}${maximumDifference !== null ? ` · max ${maximumDifference.toFixed(2)}%` : ''}`
      : `Nasdaq check ${matched}/${required || '—'}`;
    priceCell.append(priceValue, priceProof);
    const peCell = document.createElement('strong');
    peCell.textContent = currentPe !== null ? `${currentPe.toFixed(1)}×` : '—';
    const verdict = document.createElement('span');
    const state = percentile === null ? 'missing' : percentile <= 25 ? 'attractive' : percentile <= 75 ? 'fair' : 'demanding';
    verdict.className = `valuation-verdict is-${state}`;
    const partialNote = record.ready === false && percentile !== null ? ' · filing stale' : '';
    verdict.textContent = percentile === null
      ? `${comparison.observations || 0} comparisons · too few`
      : `${comparison.verdict} · ${ordinal(percentile)} pct${partialNote}`;
    row.append(companyCell, priceCell, peCell, verdict);
    return row;
  });
  document.getElementById('valuationRows').replaceChildren(...rows);

  const cashFlow = fundamentals.cashFlow || {};
  const cashFlowCompanies = cashFlow.companies || {};
  const cashFlowRows = COMPANIES.map(company => {
    const record = cashFlowCompanies[company.symbol] || {};
    const current = record.current || {};
    const comparison = record.comparison || {};
    const fcf = number(current.freeCashFlow);
    const yieldValue = number(current.fcfYield);
    const percentile = comparison.percentile === null || comparison.percentile === undefined
      ? null
      : number(comparison.percentile);
    const row = document.createElement('div');
    row.className = 'cashflow-row';
    row.setAttribute('role', 'row');
    const companyCell = document.createElement('div');
    companyCell.innerHTML = `<b>${company.symbol}</b><small>${current.filed ? `filed ${current.filed}` : record.status === 'unavailable' ? 'filed capex incomplete' : 'limited history'}</small>`;
    const cashCell = document.createElement('strong');
    cashCell.textContent = fcf !== null ? compactMoney.format(fcf) : '—';
    const yieldCell = document.createElement('strong');
    yieldCell.textContent = current.positiveFreeCashFlow === false ? 'Negative' : yieldValue !== null ? `${yieldValue.toFixed(2)}%` : '—';
    const verdict = document.createElement('span');
    const state = percentile === null ? 'missing' : percentile <= 25 ? 'attractive' : percentile <= 75 ? 'fair' : 'demanding';
    verdict.className = `valuation-verdict is-${state}`;
    verdict.textContent = current.positiveFreeCashFlow === false
      ? 'Investment currently exceeds cash generated'
      : percentile === null
      ? `${comparison.observations || 0} comparisons · too few`
      : `${comparison.verdict} · ${ordinal(percentile)} pct`;
    row.append(companyCell, cashCell, yieldCell, verdict);
    return row;
  });
  document.getElementById('cashflowRows').replaceChildren(...cashFlowRows);
  const cashflowStatus = document.getElementById('cashflowStatus');
  const cashflowReady = Number(cashFlow.companiesReady || 0);
  setStatus(cashflowStatus, `${cashflowReady}/8 cash-flow histories`, cashFlow.complete ? 'ready' : 'limited');
  document.getElementById('cashflowMethod').textContent = `${cashFlow.method || 'As-filed free-cash-flow evidence unavailable'}. ${cashFlow.warning || 'Incomplete evidence remains visible and cannot confirm the P/E result.'}`;

  const status = document.getElementById('valuationStatus');
  const verifiedCount = Number(fundamentals.companiesReady || 0);
  const priceChecksReady = Number(fundamentals.priceChecksReady || 0);
  if (fundamentals.complete) {
    setStatus(status, 'All valuation evidence verified', 'ready');
    document.getElementById('valuationFactorNote').textContent = '8/8 earnings, 8/8 cash-flow histories and 8/8 independent prices passed';
  } else {
    setStatus(status, `${verifiedCount}/8 filings · ${priceChecksReady}/8 prices`, 'limited');
    const missingCount = 8 - verifiedCount;
    document.getElementById('valuationFactorNote').textContent = `${missingCount} earnings ${missingCount === 1 ? 'history is' : 'histories are'} incomplete; ${cashflowReady}/8 cash-flow histories and ${priceChecksReady}/8 Nasdaq prices passed`;
  }
  document.getElementById('valuationMethod').textContent = `${fundamentals.method || 'As-filed valuation unavailable'}. ${fundamentals.warning || 'Missing evidence keeps the gate closed.'}`;
}

function renderDcf(dcf = {}) {
  const companies = dcf.companies || {};
  const rows = COMPANIES.map(company => {
    const record = companies[company.symbol] || {};
    const reported = record.reportedView || {};
    const ownerCash = record.ownerCashView || {};
    const investment = record.investmentModel || {};
    const evidence = investment.evidence || {};
    const scenarios = Object.fromEntries((ownerCash.scenarios || []).map(item => [item.id, item]));
    const row = document.createElement('div');
    row.className = `dcf-table-row ${record.ready ? 'is-ready' : 'is-limited'}`;
    row.setAttribute('role', 'row');

    const companyCell = document.createElement('div');
    companyCell.innerHTML = `<b>${company.symbol}</b><small>${record.normalizedReady ? 'Owner-cash range passed' : record.reportedReady ? 'Reported range only' : record.message || 'Evidence incomplete'}</small>`;
    const priceCell = document.createElement('strong');
    priceCell.textContent = number(record.currentPrice) !== null ? `$${number(record.currentPrice).toFixed(2)}` : '—';

    const scenarioCell = id => {
      const scenario = scenarios[id];
      const cell = document.createElement('div');
      if (!scenario) {
        cell.innerHTML = '<strong>—</strong><small>No defensible value</small>';
        return cell;
      }
      const relation = number(scenario.versusPricePct);
      cell.className = relation !== null && relation >= 0 ? 'is-above' : 'is-below';
      cell.innerHTML = `<strong>$${Number(scenario.value).toFixed(2)}</strong><small>${relation >= 0 ? '+' : ''}${relation.toFixed(1)}% vs market</small>`;
      return cell;
    };

    const reportedCell = document.createElement('div');
    if (number(reported.rangeLow) !== null && number(reported.rangeHigh) !== null) {
      reportedCell.innerHTML = `<strong>$${Number(reported.rangeLow).toFixed(2)}–$${Number(reported.rangeHigh).toFixed(2)}</strong><small>All productive spending deducted</small>`;
    } else {
      reportedCell.innerHTML = '<strong>—</strong><small>Reported cash not positive or history too short</small>';
    }

    const splitCell = document.createElement('div');
    splitCell.className = 'dcf-driver';
    const maintenance = investment.maintenanceRange || [];
    const growth = investment.growthRange || [];
    splitCell.textContent = investment.ready && maintenance.length === 2 && growth.length === 2
      ? `${compactMoney.format(maintenance[0])}–${compactMoney.format(maintenance[1])} maintain · ${compactMoney.format(growth[0])}–${compactMoney.format(growth[1])} growth`
      : investment.message || 'No defensible split';

    const evidenceCell = document.createElement('div');
    evidenceCell.className = 'dcf-evidence';
    if (evidence.sourceUrl) {
      const link = document.createElement('a');
      link.href = evidence.sourceUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = evidence.quality === 'moderate' ? 'Moderate · issuer filing' : 'Insufficient · issuer filing';
      const detail = document.createElement('small');
      detail.textContent = evidence.finding || investment.message;
      evidenceCell.append(link, detail);
    } else {
      evidenceCell.innerHTML = `<strong>Missing</strong><small>${investment.message || 'No dated issuer evidence'}</small>`;
    }
    row.append(companyCell, priceCell, reportedCell, scenarioCell('downside'), scenarioCell('base'), scenarioCell('strong'), splitCell, evidenceCell);
    return row;
  });
  document.getElementById('dcfRows').replaceChildren(...rows);
  const normalized = Number(dcf.normalizedCompaniesReady || 0);
  const reported = Number(dcf.reportedCompaniesReady || 0);
  setStatus(document.getElementById('dcfStatus'), `${normalized}/8 owner-cash · ${reported}/8 reported`, dcf.complete ? 'ready' : 'limited');
  const riskFree = dcf.riskFreeEvidence || {};
  const riskFreeText = number(riskFree.valuePct) !== null
    ? ` Risk-free anchor: ${Number(riskFree.valuePct).toFixed(2)}%${riskFree.date ? ` on ${riskFree.date}` : ' conservative floor'}.`
    : '';
  document.getElementById('dcfMethod').textContent = `${dcf.method || 'DCF evidence unavailable'}.${riskFreeText} ${dcf.warning || 'Missing evidence produces no value.'}`;
}

function portfolioVolatility(covariance) {
  let variance = 0;
  for (const left of PORTFOLIO) {
    for (const right of PORTFOLIO) {
      const value = number(covariance?.[left.symbol]?.[right.symbol]);
      if (value === null) return null;
      variance += left.weight / 100 * right.weight / 100 * value;
    }
  }
  return variance > 0 ? Math.sqrt(variance) * 100 : null;
}

function strongestCompanyCorrelation(correlations) {
  let strongest = null;
  for (let left = 0; left < COMPANIES.length; left += 1) {
    for (let right = left + 1; right < COMPANIES.length; right += 1) {
      const value = number(correlations?.[COMPANIES[left].symbol]?.[COMPANIES[right].symbol]);
      if (value !== null && (!strongest || value > strongest.value)) {
        strongest = { left: COMPANIES[left].symbol, right: COMPANIES[right].symbol, value };
      }
    }
  }
  return strongest;
}

async function loadRisk() {
  const status = document.getElementById('riskStatus');
  try {
    const symbols = PORTFOLIO.map(holding => holding.symbol).join(',');
    const response = await fetch(`/api/portfolio-risk?symbols=${encodeURIComponent(symbols)}`);
    if (!response.ok) throw new Error('Risk history was unavailable');
    const payload = await response.json();
    const coverage = PORTFOLIO.filter(holding => number(payload.annualCovariance?.[holding.symbol]?.[holding.symbol]) !== null).length;
    document.getElementById('historyCoverage').textContent = `${coverage} / ${PORTFOLIO.length}`;
    const volatility = coverage === PORTFOLIO.length ? portfolioVolatility(payload.annualCovariance) : null;
    document.getElementById('portfolioVolatility').textContent = volatility ? `${volatility.toFixed(1)}%` : 'Not complete';
    const correlation = strongestCompanyCorrelation(payload.correlations);
    if (correlation) {
      document.getElementById('highestCorrelation').textContent = correlation.value.toFixed(2);
      document.getElementById('correlationPair').textContent = `${correlation.left} and ${correlation.right} moved most alike`;
    }
    setStatus(status, coverage === PORTFOLIO.length ? 'History complete' : `${coverage} of ${PORTFOLIO.length} covered`, coverage === PORTFOLIO.length ? 'ready' : 'limited');
    document.getElementById('riskMethod').textContent = `${payload.method}. Sources: ${[...new Set(Object.values(payload.sources || {}))].join(' and ') || 'not available'}.`;
  } catch (error) {
    setStatus(status, 'History unavailable', 'limited');
    document.getElementById('portfolioVolatility').textContent = 'Not calculated';
    document.getElementById('riskMethod').textContent = 'Kestrel could not verify enough adjusted daily prices, so it has not displayed a volatility estimate.';
  }
}

function sciencePercent(value) {
  const parsed = number(value);
  return parsed === null ? '—' : `${parsed > 0 ? '+' : ''}${parsed.toFixed(1)}%`;
}

function renderScienceComparison(payload) {
  const records = [
    { name: 'Candidate 1 · frozen', metrics: payload.candidate?.metrics, className: '' },
    { name: 'Research challenger', metrics: payload.challenger?.metrics, className: 'is-research' },
    { name: 'VT · global benchmark', metrics: payload.benchmark, className: '' },
  ];
  const rows = records.map(record => {
    const row = document.createElement('div');
    row.className = `science-table-row ${record.className}`.trim();
    row.setAttribute('role', 'row');
    const name = document.createElement('strong');
    name.textContent = record.name;
    const metrics = record.metrics || {};
    const values = [metrics.annualReturn, metrics.annualVolatility, metrics.worstTwoYear, metrics.maxDrawdown];
    row.append(name, ...values.map(value => {
      const cell = document.createElement('span');
      cell.textContent = sciencePercent(value);
      return cell;
    }));
    return row;
  });
  document.getElementById('scienceComparisonRows').replaceChildren(...rows);
}

function renderScienceChanges(payload) {
  const changes = (payload.challenger?.changes || []).filter(item => Math.abs(number(item.change) || 0) >= 0.1).slice(0, 7);
  const rows = changes.map(item => {
    const row = document.createElement('div');
    row.className = `science-change ${item.change < 0 ? 'is-down' : 'is-up'}`;
    const symbol = document.createElement('b');
    symbol.textContent = item.symbol;
    const weights = document.createElement('span');
    weights.textContent = `${Number(item.candidate).toFixed(1)}% → ${Number(item.challenger).toFixed(1)}%`;
    const change = document.createElement('strong');
    change.textContent = `${item.change > 0 ? '+' : ''}${Number(item.change).toFixed(1)} pts`;
    row.append(symbol, weights, change);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'lab-loading';
    empty.textContent = 'No provisional change cleared the reporting threshold.';
    rows.push(empty);
  }
  document.getElementById('scienceChangeList').replaceChildren(...rows);
  const research = payload.research || {};
  document.getElementById('scienceCost').textContent = `${Number(research.turnoverPercent || 0).toFixed(1)}% one-way turnover · approximately ${Number(research.estimatedTradingCostPercent || 0).toFixed(3)}% estimated trading cost before tax.`;
}

function renderScienceGates(payload) {
  const rows = (payload.gates?.items || []).map(gate => {
    const row = document.createElement('div');
    row.className = `science-gate ${gate.passed ? 'is-passed' : 'is-blocked'}`;
    const marker = document.createElement('i');
    marker.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = `${gate.passed ? 'Passed' : 'Missing'} · ${gate.name}${gate.detail ? ` · ${gate.detail}` : ''}`;
    row.append(marker, label);
    return row;
  });
  document.getElementById('scienceGateList').replaceChildren(...rows);
}

function renderWalkForward(payload) {
  const result = payload.walkForward || {};
  const metrics = result.metrics?.challenger || {};
  const eligible = result.eligible === true;
  const blocked = result.status === 'blocked';
  setStatus(
    document.getElementById('walkForwardStatus'),
    eligible ? 'Evidence passed' : blocked ? 'Integrity gate closed' : 'Evidence too weak',
    eligible ? 'ready' : 'limited'
  );
  document.getElementById('walkForwardWindows').textContent = `${result.windowCount || 0} / ${result.minimumWindows || 5}`;
  document.getElementById('walkForwardReturn').textContent = sciencePercent(metrics.annualReturn);
  document.getElementById('walkForwardDrawdown').textContent = sciencePercent(metrics.maxDrawdown);
  document.getElementById('walkForwardRisk').textContent = number(metrics.informationRatioVsBenchmark) === null
    ? '—'
    : Number(metrics.informationRatioVsBenchmark).toFixed(2);
  const failures = result.failures || [];
  document.getElementById('walkForwardSummary').textContent = eligible
    ? `The challenger beat Candidate 1 in ${result.candidateWins} windows and VT in ${result.benchmarkWins}, after declared costs.`
    : failures[0] || 'The challenger has not earned promotion on genuinely unseen evidence.';

  const rows = (result.windows || []).map(window => {
    const passed = Number(window.versusCandidate) > 0 && Number(window.versusBenchmark) > 0;
    const row = document.createElement('article');
    row.className = `walkforward-window ${passed ? 'is-passed' : 'is-blocked'}`;
    const period = document.createElement('div');
    const dates = document.createElement('span');
    dates.textContent = `${window.from} → ${window.through}`;
    const trained = document.createElement('small');
    trained.textContent = `trained through ${window.trainedThrough}`;
    period.append(dates, trained);
    const outcome = document.createElement('strong');
    outcome.textContent = sciencePercent(window.challengerNetReturn);
    const comparisons = document.createElement('p');
    comparisons.textContent = `${sciencePercent(window.versusCandidate)} vs Candidate 1 · ${sciencePercent(window.versusBenchmark)} vs VT`;
    const marker = document.createElement('b');
    marker.textContent = passed ? 'Won both' : 'Did not win both';
    row.append(period, outcome, comparisons, marker);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'walkforward-empty';
    empty.textContent = 'No historical window is allowed to count until its universe and inputs can be reconstructed as they were known then.';
    rows.push(empty);
  }
  document.getElementById('walkForwardWindowList').replaceChildren(...rows);
  const candidate = result.uncertainty?.versusCandidate || {};
  const benchmark = result.uncertainty?.versusBenchmark || {};
  document.getElementById('walkForwardUncertainty').textContent = candidate.low === null || candidate.low === undefined
    ? 'A 95% uncertainty range needs at least five independent annual windows. Until then, the promotion gate stays closed.'
    : `95% net-return improvement range: ${sciencePercent(candidate.low)} to ${sciencePercent(candidate.high)} versus Candidate 1; ${sciencePercent(benchmark.low)} to ${sciencePercent(benchmark.high)} versus VT. Whole annual windows were resampled.`;
}

function renderLookthrough(payload) {
  const lookthrough = payload.lookthrough || {};
  const complete = lookthrough.complete === true;
  setStatus(
    document.getElementById('lookthroughStatus'),
    complete ? `${lookthrough.fundsReady} of ${lookthrough.fundsTotal} ETFs verified` : `${lookthrough.fundsReady || 0} of ${lookthrough.fundsTotal || 6} ETFs verified`,
    complete ? 'ready' : 'limited'
  );
  const rows = (lookthrough.exposures || []).map(item => {
    const row = document.createElement('div');
    row.className = 'lookthrough-row';
    row.setAttribute('role', 'row');
    const symbol = document.createElement('strong');
    symbol.textContent = item.symbol;
    const direct = document.createElement('span');
    direct.textContent = `${Number(item.direct || 0).toFixed(2)}%`;
    const hidden = document.createElement('span');
    hidden.textContent = `+${Number(item.insideFunds || 0).toFixed(2)}%`;
    const effective = document.createElement('b');
    effective.textContent = `${Number(item.effective || 0).toFixed(2)}%`;
    if (Number(item.effective || 0) > 8) row.classList.add('is-over');
    row.append(symbol, direct, hidden, effective);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'lab-loading';
    empty.textContent = 'Official holdings are incomplete, so Kestrel will not estimate the overlap.';
    rows.push(empty);
  }
  document.getElementById('lookthroughRows').replaceChildren(...rows);
  const current = (lookthrough.sources || []).filter(source => source.ready);
  const oldest = current.reduce((value, source) => Math.max(value, Number(source.ageDays || 0)), 0);
  document.getElementById('lookthroughMethod').textContent = complete
    ? `${current.length} official issuer files reconciled; oldest is ${oldest} days old. An 8% true-company ceiling is now enforced in the challenger.`
    : 'One or more official issuer files is missing, stale or does not reconcile near 100%, so the look-through gate remains closed.';
}

function renderPortfolioScience(payload) {
  const research = payload.research || {};
  const gates = payload.gates || {};
  const ready = payload.status === 'promotion_ready';
  setStatus(document.getElementById('scienceStatus'), ready ? 'Promotion gates passed' : 'Research only · no changes', ready ? 'ready' : 'limited');
  document.getElementById('scienceHistory').textContent = `${research.commonMonths || 0} months`;
  document.getElementById('scienceHistoryDates').textContent = research.commonFrom && research.commonThrough
    ? `${research.commonFrom} to ${research.commonThrough}`
    : 'A complete common history is not available';
  document.getElementById('scienceAlternatives').textContent = new Intl.NumberFormat('en-US').format(research.portfoliosTested || 0);
  document.getElementById('scienceGates').textContent = `${gates.passed || 0} / ${gates.total || 0}`;
  document.getElementById('scienceDecision').textContent = ready ? 'Eligible to challenge' : 'Keep Candidate 1';
  document.getElementById('scienceDecisionNote').textContent = payload.message || 'No allocation changes while evidence is incomplete';
  renderScienceComparison(payload);
  renderScienceChanges(payload);
  renderWalkForward(payload);
  renderScienceGates(payload);
  renderLookthrough(payload);
  renderValuations(payload.fundamentals);
  renderDcf(payload.dcf);
}

async function loadPortfolioScience() {
  try {
    const response = await fetch('/api/portfolio-science');
    if (!response.ok) throw new Error('Scientific portfolio audit was unavailable');
    renderPortfolioScience(await response.json());
  } catch (error) {
    setStatus(document.getElementById('scienceStatus'), 'Audit unavailable · no changes', 'limited');
    document.getElementById('scienceDecision').textContent = 'Keep Candidate 1';
    document.getElementById('scienceDecisionNote').textContent = 'Kestrel could not complete the evidence checks, so it made no allocation changes.';
    renderWalkForward({});
    renderLookthrough({});
    renderValuations({});
    renderDcf({});
  }
}

const capitalInput = document.getElementById('capitalInput');
capitalInput.addEventListener('input', event => {
  const value = number(event.target.value);
  if (value !== null && value >= 1000) saveCapital(value);
});
capitalInput.addEventListener('change', event => {
  const value = number(event.target.value);
  saveCapital(value !== null && value >= 1000 ? value : capital);
});
document.getElementById('resetCapital').addEventListener('click', () => saveCapital(DEFAULT_CAPITAL));

renderCapital();
loadRisk();
loadPortfolioScience();
