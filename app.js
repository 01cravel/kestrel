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
  DELL: { name: 'Dell Technologies', sector: 'Technology', country: 'US' },
  ETN: { name: 'Eaton', sector: 'Industrial', country: 'Ireland' },
  CRDO: { name: 'Credo Technology', sector: 'Semiconductors', country: 'Cayman Islands' },
  MRVL: { name: 'Marvell Technology', sector: 'Semiconductors', country: 'US' },
  NOW: { name: 'ServiceNow', sector: 'Software', country: 'US' },
  RGTI: { name: 'Rigetti Computing', sector: 'Technology', country: 'US' },
  SPCX: { name: 'SpaceX', sector: 'Industrial', country: 'US' },
  BTC: { name: 'Bitcoin', sector: 'Crypto', country: 'Global', type: 'crypto' },
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

const OWNER_GUIDES = {
  MU: {
    business: 'Makes the memory chips that let AI systems, phones and computers store and move data quickly.',
    wealthDriver: 'AI servers need far more memory than ordinary computers, so rising demand can lift both sales and chip prices.',
    mainRisk: 'Memory prices move in boom-and-bust cycles; today’s exceptional profits may not last.',
  },
  SPY: {
    business: 'Owns a small piece of roughly 500 of America’s largest listed companies in one fund.',
    wealthDriver: 'It compounds with the long-term growth and profits of large US businesses without relying on one winner.',
    mainRisk: 'It will fall with the US market and is currently heavily influenced by its largest technology holdings.',
  },
  NBIS: {
    business: 'Builds cloud computing infrastructure designed for companies developing artificial intelligence.',
    wealthDriver: 'It could grow quickly if demand for scarce AI computing capacity continues and customers keep signing large contracts.',
    mainRisk: 'It is spending heavily, has a short operating record and is priced for very rapid growth.',
  },
  VRT: {
    business: 'Supplies the power, cooling and electrical equipment that keeps data centres running.',
    wealthDriver: 'AI data centres consume enormous amounts of power and cooling, creating years of potential infrastructure demand.',
    mainRisk: 'Customers can delay large projects, and a high share price leaves little room for slower growth.',
  },
  V: {
    business: 'Runs the network that moves money when people pay with Visa cards; it generally does not lend the money itself.',
    wealthDriver: 'More spending moving from cash to digital payments can steadily increase the fees travelling across its network.',
    mainRisk: 'Regulators, banks or new payment technology could force fees lower.',
  },
  GLD: {
    business: 'A fund designed to follow the price of physical gold.',
    wealthDriver: 'Gold can protect part of the portfolio when confidence in currencies, governments or markets weakens.',
    mainRisk: 'Gold produces no earnings or cash flow, so returns depend entirely on someone later paying more for it.',
  },
  CAT: {
    business: 'Makes heavy machinery, engines and equipment used in construction, mining and energy projects.',
    wealthDriver: 'Infrastructure spending and replacement demand can support years of equipment sales and profitable servicing.',
    mainRisk: 'Orders can fall sharply when construction, mining or the wider economy slows.',
  },
  NVDA: {
    business: 'Designs the leading chips and software used to train and run many artificial-intelligence systems.',
    wealthDriver: 'If AI computing keeps expanding, Nvidia can sell more chips, networking equipment and software at strong margins.',
    mainRisk: 'Customers are developing alternatives, competition is rising and the valuation assumes continued exceptional growth.',
  },
  RKLB: {
    business: 'Launches small rockets and makes satellites, spacecraft parts and space systems.',
    wealthDriver: 'A larger launch vehicle and growing space-systems orders could turn it into a broader space infrastructure company.',
    mainRisk: 'Rocket development can be delayed or fail, while the business still requires substantial investment.',
  },
  LLY: {
    business: 'Develops medicines, including major treatments for diabetes, obesity and other serious illnesses.',
    wealthDriver: 'Very large demand for its newer medicines and a strong drug pipeline could support long-term earnings growth.',
    mainRisk: 'Drug competition, safety findings, pricing pressure or failed clinical trials can change the outlook quickly.',
  },
  MA: {
    business: 'Runs a global network that connects banks and merchants when people make electronic payments.',
    wealthDriver: 'It can benefit as more of the world’s spending moves from cash to cards and online payments.',
    mainRisk: 'Fee regulation, economic weakness and alternative payment networks could slow growth.',
  },
  HCA: {
    business: 'Operates hospitals, surgery centres and other healthcare facilities across the United States.',
    wealthDriver: 'An ageing population and efficient hospital operations can produce durable demand and cash flow.',
    mainRisk: 'Government reimbursement changes, labour costs and high debt can squeeze profits.',
  },
  AVGO: {
    business: 'Sells specialised chips for data centres and communications, plus large-business infrastructure software.',
    wealthDriver: 'Custom AI chips, networking demand and recurring software income can compound profits from several sources.',
    mainRisk: 'Large customers have bargaining power, acquisitions add debt and chip demand can be cyclical.',
  },
  STX: {
    business: 'Makes high-capacity disk drives used to store large amounts of data.',
    wealthDriver: 'Cloud and AI systems create huge volumes of data that must be stored economically.',
    mainRisk: 'Storage demand and pricing are cyclical, while solid-state technology remains a long-term competitor.',
  },
  GOOGL: {
    business: 'Owns Google Search, YouTube, Android and a large cloud-computing business.',
    wealthDriver: 'Its enormous audience funds AI investment, while cloud and new AI products can create additional profit engines.',
    mainRisk: 'AI could disrupt search advertising, and regulators may restrict how Google operates.',
  },
  AXP: {
    business: 'Runs a payment network and lends mainly to higher-spending consumers and businesses.',
    wealthDriver: 'Growing card spending, membership fees and loyal affluent customers can compound revenue over time.',
    mainRisk: 'A recession can reduce spending and increase unpaid card balances.',
  },
  AMD: {
    business: 'Designs processors and AI accelerators used in personal computers, game consoles and data centres.',
    wealthDriver: 'Winning more data-centre and AI workloads from larger rivals could produce strong sales and profit growth.',
    mainRisk: 'It competes against Nvidia and Intel, and fast product cycles can quickly change market share.',
  },
  CEG: {
    business: 'Produces electricity, mainly from a large fleet of nuclear power stations.',
    wealthDriver: 'Data centres need dependable electricity around the clock, making existing nuclear generation increasingly valuable.',
    mainRisk: 'Power prices, regulation, plant outages and expensive long-term maintenance can materially affect profits.',
  },
  QBTS: {
    business: 'Builds a specialised type of quantum computer aimed at solving optimisation problems.',
    wealthDriver: 'Commercial adoption could grow quickly if its systems solve valuable problems better than normal computers.',
    mainRisk: 'Quantum computing is unproven at scale, losses remain high and future share issuance may dilute owners.',
  },
  COHR: {
    business: 'Makes lasers, optical components and communications equipment used in networks, factories and electronics.',
    wealthDriver: 'AI data centres need faster optical connections, which can drive demand for its communications products.',
    mainRisk: 'The business is cyclical, carries acquisition-related debt and faces intense component competition.',
  },
  ONDS: {
    business: 'Develops autonomous drones and private wireless systems for industrial and government customers.',
    wealthDriver: 'Large defence, security or infrastructure orders could transform its small revenue base.',
    mainRisk: 'Orders are uneven, losses are substantial and shareholders may be diluted to fund growth.',
  },
  DELL: {
    business: 'Sells computers, servers, storage systems and infrastructure used by businesses and data centres.',
    wealthDriver: 'Companies building AI systems need complete servers and supporting infrastructure, not only chips.',
    mainRisk: 'Hardware margins are thin, demand is cyclical and competition keeps pricing pressure high.',
  },
  ETN: {
    business: 'Makes electrical equipment that controls and distributes power in buildings, factories and data centres.',
    wealthDriver: 'Electrification, grid upgrades and data-centre construction create long-lived demand for its equipment.',
    mainRisk: 'A construction slowdown or supply expansion could reduce orders and margins.',
  },
  CRDO: {
    business: 'Designs high-speed connectivity products that move data inside and between data centres.',
    wealthDriver: 'Larger AI clusters require faster links, giving Credo a chance to grow rapidly with network bandwidth.',
    mainRisk: 'Revenue can depend on a few customers, and larger chip companies can compete aggressively.',
  },
  MRVL: {
    business: 'Designs chips for data centres, networking, storage and custom computing systems.',
    wealthDriver: 'Custom AI chips and faster data-centre networks can become much larger sources of revenue.',
    mainRisk: 'Execution on complex custom chips matters, and demand outside AI can remain cyclical.',
  },
  NOW: {
    business: 'Sells software that helps large organisations automate everyday work and technology operations.',
    wealthDriver: 'Recurring subscriptions, high customer retention and AI-assisted automation can compound revenue for years.',
    mainRisk: 'The shares often carry a high valuation, while Microsoft and other software vendors compete for the same budgets.',
  },
  RGTI: {
    business: 'Develops quantum-computing hardware and cloud access to its experimental machines.',
    wealthDriver: 'A genuine technical breakthrough could make its systems valuable to governments and major companies.',
    mainRisk: 'Commercial usefulness remains uncertain, losses are high and funding may require substantial dilution.',
  },
  SPCX: {
    business: 'Provides private exposure to SpaceX, which operates rockets, spacecraft and the Starlink satellite network.',
    wealthDriver: 'Reusable launch leadership and global satellite internet could create several very large businesses.',
    mainRisk: 'It is private, pricing is difficult to verify and the holding may be hard to sell when you want to.',
  },
  BTC: {
    business: 'A scarce digital asset transferred through a decentralised global network rather than a company.',
    wealthDriver: 'Wider adoption as a store of value could increase demand against a fixed maximum supply.',
    mainRisk: 'It produces no cash flow and can lose a large part of its value very quickly.',
  },
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
const QA_MODE = new URLSearchParams(window.location.search).get('mode') === 'qa';
const STORAGE_PREFIX = QA_MODE ? 'kestrel_qa' : 'kestrel';
const POSITIONS_STORAGE_KEY = `${STORAGE_PREFIX}_positions`;
const POSITIONS_BACKUP_KEY = `${STORAGE_PREFIX}_positions_backup`;
const ACTION_SNAPSHOT_KEY = `${STORAGE_PREFIX}_action_snapshot`;

const state = {
  dashboard: null,
  positions: loadPositions(),
  assessments: {},
  opportunities: [],
  candidateAssessments: [],
  leagueOptions: [],
  geographyAudit: null,
  pollTimer: null,
  savedSnapshotFor: null,
  savedSignalsFor: null,
  savedInvestorSignalsFor: null,
  investorCalibration: null,
  historyRangeBySymbol: {},
  historyRequest: null,
  performance: null,
  performanceKey: null,
  performanceRequest: null,
  portfolioRiskData: null,
  portfolioRiskKey: null,
  portfolioRiskRequest: null,
  detailPerformanceRequest: null,
  sarwa: null,
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
  superinvestorSection: document.getElementById('superinvestorSection'),
  superinvestorSummary: document.getElementById('superinvestorSummary'),
  superinvestorPeriod: document.getElementById('superinvestorPeriod'),
  superinvestorList: document.getElementById('superinvestorList'),
  portfolioValue: document.getElementById('portfolioValue'),
  portfolioRiskSection: document.getElementById('portfolioRiskSection'),
  portfolioRiskSummary: document.getElementById('portfolioRiskSummary'),
  portfolioRiskGrid: document.getElementById('portfolioRiskGrid'),
  benchmarkSection: document.getElementById('benchmarkSection'),
  benchmarkSummary: document.getElementById('benchmarkSummary'),
  benchmarkGrid: document.getElementById('benchmarkGrid'),
  benchmarkNote: document.getElementById('benchmarkNote'),
  sarwaSection: document.getElementById('sarwaSection'),
  sarwaTitle: document.getElementById('sarwaTitle'),
  sarwaDetail: document.getElementById('sarwaDetail'),
  sarwaStatus: document.getElementById('sarwaStatus'),
  sarwaLastSync: document.getElementById('sarwaLastSync'),
  sarwaCoverage: document.getElementById('sarwaCoverage'),
  sarwaReviewButton: document.getElementById('sarwaReviewButton'),
  sarwaDialog: document.getElementById('sarwaDialog'),
  sarwaReviewContent: document.getElementById('sarwaReviewContent'),
  sarwaApplyButton: document.getElementById('sarwaApplyButton'),
  sarwaDiscardButton: document.getElementById('sarwaDiscardButton'),
  evidenceSection: document.getElementById('evidenceSection'),
  evidenceTitle: document.getElementById('evidenceTitle'),
  evidenceSummary: document.getElementById('evidenceSummary'),
  evidenceAuthority: document.getElementById('evidenceAuthority'),
  evidenceCap: document.getElementById('evidenceCap'),
  evidenceUltra: document.getElementById('evidenceUltra'),
  evidenceNext: document.getElementById('evidenceNext'),
  evidencePolicyButton: document.getElementById('evidencePolicyButton'),
  evidenceDialog: document.getElementById('evidenceDialog'),
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
    const saved = JSON.parse(localStorage.getItem(POSITIONS_STORAGE_KEY) || '{}');
    return saved && typeof saved === 'object' ? saved : {};
  } catch {
    return {};
  }
}

function savePositions() {
  localStorage.setItem(POSITIONS_STORAGE_KEY, JSON.stringify(state.positions));
}

function backupPositions() {
  localStorage.setItem(POSITIONS_BACKUP_KEY, JSON.stringify({
    savedAt: new Date().toISOString(),
    positions: state.positions,
  }));
}

async function syncPortfolioFromServer() {
  if (QA_MODE) return;
  try {
    const response = await fetch('/api/portfolio', { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Portfolio could not be loaded');
    if (payload.positions && Object.keys(payload.positions).length) {
      state.positions = payload.positions;
      savePositions();
    }
  } catch (error) {
    console.warn('Using the browser portfolio because the private portfolio file is unavailable.');
  }
}

async function savePortfolioToServer() {
  if (QA_MODE) return;
  try {
    const response = await fetch('/api/portfolio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ positions: state.positions }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Portfolio backup failed');
  } catch (error) {
    els.stateText.textContent = 'Portfolio saved in this browser; private disk backup failed';
  }
}

async function fetchSarwaStatus() {
  try {
    const response = await fetch('/api/sarwa', { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Sarwa connection status is unavailable');
    state.sarwa = payload;
    renderSarwaStatus();
  } catch (error) {
    els.sarwaTitle.textContent = 'Sarwa connection is temporarily unavailable';
    els.sarwaDetail.textContent = 'Your private Kestrel portfolio remains unchanged.';
    els.sarwaStatus.textContent = 'Offline';
  }
}

function renderSarwaStatus() {
  const sarwa = state.sarwa;
  if (!sarwa) return;
  const pending = sarwa.pending;
  const connected = sarwa.status === 'connected';
  els.sarwaSection.dataset.status = sarwa.status;
  els.sarwaReviewButton.hidden = !pending;
  els.sarwaLastSync.textContent = sarwa.lastSuccessfulSync
    ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(sarwa.lastSuccessfulSync * 1000))
    : 'Not yet';
  els.sarwaCoverage.textContent = `${sarwa.lastHoldingCount || sarwa.currentHoldingCount || 0} holding${(sarwa.lastHoldingCount || sarwa.currentHoldingCount) === 1 ? '' : 's'}`;

  if (pending) {
    const reconciliation = pending.reconciliation || {};
    const changeCount = (reconciliation.added?.length || 0) + (reconciliation.removed?.length || 0) + (reconciliation.changed?.length || 0);
    els.sarwaTitle.textContent = changeCount ? 'Sarwa found portfolio changes' : 'Sarwa matches Kestrel';
    els.sarwaDetail.textContent = changeCount
      ? `${changeCount} change${changeCount === 1 ? '' : 's'} waiting for your review. Nothing has been applied.`
      : 'The latest Sarwa snapshot agrees with your private portfolio.';
    els.sarwaStatus.textContent = pending.canApply ? 'Review ready' : 'Needs attention';
    return;
  }

  if (connected) {
    els.sarwaTitle.textContent = 'Portfolio linked to Sarwa';
    els.sarwaDetail.textContent = `Last verified from ${sarwa.lastSource === 'sarwa_statement' ? 'an official Sarwa statement' : 'the read-only Sarwa web account'}.`;
    els.sarwaStatus.textContent = 'Connected';
    return;
  }

  els.sarwaTitle.textContent = 'Ready for your first Sarwa sync';
  els.sarwaDetail.textContent = 'Open Sarwa and sign in. Your 21 restored holdings stay untouched until a snapshot is verified.';
  els.sarwaStatus.textContent = 'Sign-in needed';
}

function formatPositionChange(item, type) {
  if (type === 'added') return `<li class="is-added"><strong>${escapeHtml(item.symbol)}</strong><span>Added · ${escapeHtml(item.shares)} shares${item.cost ? ` at ${money(number(item.cost), 2)} average` : ''}</span></li>`;
  if (type === 'removed') return `<li class="is-removed"><strong>${escapeHtml(item.symbol)}</strong><span>Would be removed · currently ${escapeHtml(item.shares)} shares</span></li>`;
  return `<li class="is-changed"><strong>${escapeHtml(item.symbol)}</strong><span>Shares ${escapeHtml(item.sharesFrom)} → ${escapeHtml(item.sharesTo)}${item.costFrom !== item.costTo ? ` · average ${money(number(item.costFrom), 2)} → ${money(number(item.costTo), 2)}` : ''}</span></li>`;
}

function openSarwaReview() {
  const pending = state.sarwa?.pending;
  if (!pending) return;
  const reconciliation = pending.reconciliation || {};
  const rows = [
    ...(reconciliation.added || []).map(item => formatPositionChange(item, 'added')),
    ...(reconciliation.changed || []).map(item => formatPositionChange(item, 'changed')),
    ...(reconciliation.removed || []).map(item => formatPositionChange(item, 'removed')),
  ];
  const warnings = reconciliation.warnings || [];
  els.sarwaReviewContent.innerHTML = `
    <div class="sarwa-review-summary">
      <div><span>Source</span><strong>${pending.snapshot?.source === 'sarwa_statement' ? 'Official statement' : 'Sarwa web account'}</strong></div>
      <div><span>Positions found</span><strong>${Object.keys(pending.snapshot?.positions || {}).length}</strong></div>
      <div><span>Unchanged</span><strong>${reconciliation.unchanged || 0}</strong></div>
    </div>
    ${rows.length ? `<ul class="sarwa-change-list">${rows.join('')}</ul>` : '<div class="fair-value-empty"><strong>No portfolio differences</strong><span>The snapshot agrees with Kestrel.</span></div>'}
    ${warnings.length ? `<div class="sarwa-warnings"><strong>Resolve before applying</strong>${warnings.map(warning => `<p>${escapeHtml(warning)}</p>`).join('')}</div>` : ''}`;
  els.sarwaApplyButton.disabled = !pending.canApply;
  els.sarwaApplyButton.textContent = rows.length ? 'Apply verified changes' : 'Confirm portfolio match';
  els.sarwaDialog.showModal();
}

async function applySarwaSnapshot() {
  els.sarwaApplyButton.disabled = true;
  els.sarwaApplyButton.textContent = 'Applying verified snapshot';
  try {
    const response = await fetch('/api/sarwa/apply', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Sarwa snapshot could not be applied');
    backupPositions();
    state.positions = payload.portfolio.positions;
    savePositions();
    state.sarwa = payload.sarwa;
    state.performance = null;
    state.performanceKey = null;
    state.portfolioRiskRequest?.abort();
    state.portfolioRiskRequest = null;
    state.portfolioRiskData = null;
    state.portfolioRiskKey = null;
    els.sarwaDialog.close();
    renderSarwaStatus();
    if (state.dashboard) calculateAndRender();
  } catch (error) {
    els.sarwaApplyButton.disabled = false;
    els.sarwaApplyButton.textContent = 'Try applying again';
    els.sarwaReviewContent.insertAdjacentHTML('beforeend', `<div class="sarwa-warnings"><strong>Nothing changed</strong><p>${escapeHtml(error.message)}</p></div>`);
  }
}

async function discardSarwaSnapshot() {
  const response = await fetch('/api/sarwa/discard', { method: 'POST' });
  const payload = await response.json();
  if (response.ok) {
    state.sarwa = payload.sarwa;
    els.sarwaDialog.close();
    renderSarwaStatus();
  }
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function optionalNumber(value) {
  return value === null || value === undefined || value === '' ? null : number(value);
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

function relativeView(value) {
  if (!Number.isFinite(value)) return null;
  if (Math.abs(value) < 0.05) return { status: 'matched', className: 'is-matched', words: 'In line with market' };
  return value > 0
    ? { status: 'ahead', className: 'is-ahead', words: `Ahead by ${Math.abs(value).toFixed(1)} pts` }
    : { status: 'behind', className: 'is-behind', words: `Behind by ${Math.abs(value).toFixed(1)} pts` };
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
    const positiveTotal = strongBuy + buy;
    const weighted = (strongBuy * 2 + buy - sell - strongSell * 2) / (total * 2);
    return {
      total,
      strongBuy,
      buy,
      hold,
      sell,
      strongSell,
      positiveTotal,
      positiveShare: (positiveTotal / total) * 100,
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

function ownerGuide(symbol, instrument) {
  if (OWNER_GUIDES[symbol]) return OWNER_GUIDES[symbol];
  return {
    business: `${instrument.name} operates in the ${String(instrument.sector || 'company').toLowerCase()} market.`,
    wealthDriver: 'Long-term wealth depends on the company growing sales, profits and cash per share.',
    mainRisk: 'The investment can disappoint if growth weakens or today’s share price already assumes too much success.',
  };
}

function sectorFromProfile(profile) {
  const industry = String(profile?.finnhubIndustry || '').toLowerCase();
  if (/semiconductor/.test(industry)) return 'Semiconductors';
  if (/software|internet|media/.test(industry)) return 'Software';
  if (/bank|financial|insurance/.test(industry)) return 'Financial services';
  if (/health|medical|pharma|biotech/.test(industry)) return 'Healthcare';
  if (/energy|oil|gas/.test(industry)) return 'Energy';
  if (/utilit/.test(industry)) return 'Utilities';
  if (/industrial|aerospace|machinery|construction/.test(industry)) return 'Industrial';
  if (/retail|consumer|food|beverage|restaurant/.test(industry)) return 'Consumer';
  if (/technology|electronic/.test(industry)) return 'Technology';
  return 'default';
}

function analystVoteText(analysts, includeBreakdown = false) {
  if (!analysts?.total) return {
    headline: 'No current analyst vote available',
    detail: 'Missing analyst coverage is not counted as support.',
  };
  const headline = `${analysts.positiveTotal}/${analysts.total} analysts say Buy or Strong Buy`;
  const detail = includeBreakdown
    ? `${analysts.strongBuy} strong buy · ${analysts.buy} buy · ${analysts.hold} hold · ${analysts.sell} sell · ${analysts.strongSell} strong sell`
    : `${plainPercent(analysts.positiveShare, 0)} positive in the latest monthly consensus`;
  return { headline, detail };
}

function confidenceExplanation({ confidence, uncappedConfidence, analysts, namedAnalysts, secEvidence, securityIdentity, marketIntegrity }) {
  const confirmed = [];
  const limits = [];
  if (securityIdentity?.status === 'resolved') confirmed.push('the exact listed security is identified');
  if (marketIntegrity?.ratingReady) confirmed.push('two price records agree');
  if (secEvidence?.ratingReady) confirmed.push('the latest company filing agrees with the market figures');
  else if (secEvidence?.status === 'verified') limits.push('the latest filing contains figures that still need reconciling');
  if (analysts?.total) confirmed.push(`${analysts.total} analyst votes are available`);
  else limits.push('no current analyst vote is available');
  if (namedAnalysts?.ratingReady) confirmed.push(`${namedAnalysts.uniqueFirms} named research firms pass the cross-check`);
  else if (namedAnalysts?.recentActions?.length) limits.push('named ratings do not yet pass every cross-check');
  else limits.push('the current Benzinga trial does not cover this stock');
  if (uncappedConfidence !== confidence) {
    limits.push('institutional-grade pricing, corporate-action history and point-in-time forecasts are not all connected');
  }
  return {
    headline: `${confidence} confidence means ${confidence === 'Medium' ? 'the direction is useful, but it is not strong enough to act on blindly' : confidence === 'High' ? 'several independent checks agree' : 'one or more important checks are missing or disagree'}.`,
    confirmed,
    limits,
  };
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
  const securityIdentity = state.dashboard?.securityMaster?.instruments?.[symbol] || null;
  const marketIntegrity = state.dashboard?.marketIntegrity?.instruments?.[symbol] || null;
  const namedAnalysts = state.dashboard?.namedAnalysts?.instruments?.[symbol] || null;
  const profile = rawData?.profile || null;
  const instrument = {
    listingMarket: 'US',
    currency: 'USD',
    benchmark: 'SPY',
    ...(INSTRUMENTS[symbol] || {
      name: profile?.name || symbol,
      sector: sectorFromProfile(profile),
      country: profile?.country || 'US',
    }),
    securityIdentity,
    marketIntegrity,
    namedAnalysts,
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

  if (instrument.type === 'crypto') {
    return assessCrypto(symbol, instrument, rawData, position);
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
  const sixMonthReturn = number(metrics['26WeekPriceReturnDaily']);
  const yearReturn = number(metrics['52WeekPriceReturnDaily']);
  const returnVolatility = number(metrics['3MonthADReturnStd']);
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
    namedAnalysts?.ratingReady ? number(namedAnalysts.score) : null,
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
  const identityResolved = securityIdentity?.status === 'resolved';
  if (!identityResolved) confidence = 'Low';
  const marketChecksActive = number(state.dashboard?.marketIntegrity?.summary?.priceRecords) > 0;
  if (marketChecksActive && marketIntegrity?.ratingReady !== true) confidence = 'Low';
  const unconstrainedConfidence = confidence;
  confidence = capConfidence(confidence);

  const positives = [];
  const risks = [];

  if (!identityResolved) {
    risks.push(securityIdentity?.message || 'The permanent instrument identity has not been resolved, so Kestrel will not recommend buying it.');
  }
  if (marketChecksActive && marketIntegrity?.ratingReady !== true) {
    risks.push(marketIntegrity?.message || 'The official close or corporate-action check needs review before Kestrel can recommend buying.');
  }

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
  if (namedAnalysts?.ratingReady) positives.push(`${namedAnalysts.uniqueFirms} named research firms provide recent ratings that agree with the broader consensus.`);
  if (namedAnalysts?.crossCheck?.status === 'review') risks.push('Named research-firm ratings disagree materially with the broader analyst consensus.');

  if (filingAgrees) positives.push('The latest official filing broadly agrees with the market-data figures.');
  if (filingConflict) risks.push('The official filing and market-data figures need reconciling before adding.');
  if (marketIntegrity?.institutionalVerified) {
    positives.push('The official consolidated close agrees with the independent price check and corporate-action record.');
  } else if (marketIntegrity?.ratingReady) {
    positives.push('Two price feeds agree and the adjusted history contains no unexplained split-sized jump.');
  }

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
  const confidenceDetails = confidenceExplanation({
    confidence,
    uncappedConfidence: unconstrainedConfidence,
    analysts,
    namedAnalysts,
    secEvidence,
    securityIdentity,
    marketIntegrity,
  });

  return {
    symbol,
    instrument,
    action,
    confidence,
    score,
    reason,
    ownerGuide: ownerGuide(symbol, instrument),
    analystVote: analystVoteText(analysts, true),
    confidenceDetails,
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
      sixMonthReturn,
      returnVolatility,
      currentPrice,
      dayChange: number(quote.dp),
      analystCount: analysts?.total ?? null,
      analystStrongBuy: analysts?.strongBuy ?? null,
      analystBuy: analysts?.buy ?? null,
      analystHold: analysts?.hold ?? null,
      analystSell: analysts?.sell ?? null,
      analystStrongSell: analysts?.strongSell ?? null,
      analystPositiveCount: analysts?.positiveTotal ?? null,
      analystPositive: analysts?.positiveShare ?? null,
      analystChange: analysts?.change ?? null,
      estimateRevisionDirection: estimateEvidence?.revision?.direction || null,
      analystTarget: number(estimateEvidence?.target?.consensus) ?? number(estimateEvidence?.target?.median),
      analystTargetUpside: estimateEvidence?.targetUpside ?? null,
      analystDisagreement: estimateEvidence?.disagreement ?? null,
      earningsBeatRate: earningsEvidence?.total ? earningsEvidence.beats / earningsEvidence.total * 100 : null,
      earningsBeats: earningsEvidence?.beats ?? null,
      earningsReports: earningsEvidence?.total ?? null,
      earningsAverageSurprise: earningsEvidence?.averageSurprise ?? null,
    },
    componentScores: { quality, valuation, direction, analyst: analystScore, momentum },
    valuation: valuationEvidence,
    analystEvidence: estimateEvidence,
    earningsEvidence,
    namedAnalystEvidence: namedAnalysts,
  };
}

function assessCrypto(symbol, instrument, rawData, position) {
  const quote = rawData.quote || {};
  return {
    symbol,
    instrument,
    action: 'Hold',
    confidence: 'Low',
    score: 50,
    reason: 'Kestrel can track the price and portfolio weight, but stock valuation and company analyst signals do not apply to Bitcoin.',
    ownerGuide: ownerGuide(symbol, instrument),
    analystVote: { headline: 'Stock analyst votes do not apply', detail: 'Bitcoin needs a separate evidence model.' },
    confidenceDetails: {
      headline: 'Low confidence means Kestrel is only tracking the position today.',
      confirmed: ['the holding and current price are visible'],
      limits: ['company earnings, filings and stock analyst votes do not apply to Bitcoin'],
    },
    positives: ['The holding is visible and included in portfolio risk calculations.'],
    risks: ['Kestrel will not issue a Buy, Ultra Buy, or Sell signal for Bitcoin until a separate crypto evidence model is built.'],
    ultraCandidate: false,
    rawData,
    position,
    metrics: {
      currentPrice: number(quote.c),
      dayChange: number(quote.dp),
    },
    componentScores: {},
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
    ownerGuide: ownerGuide(symbol, instrument),
    analystVote: { headline: 'Company analyst votes do not apply', detail: 'This is a fund, not one operating company.' },
    confidenceDetails: {
      headline: 'Low confidence refers to the Buy or Sell signal, not whether the fund exists.',
      confirmed: ['the holding and current price are visible'],
      limits: ['company earnings and individual-company analyst votes do not apply to this fund'],
    },
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
  if (analysts?.positiveShare >= 75 && valuation !== null && valuation < 55) {
    return 'Analysts are strongly positive, but the current price does not offer enough margin for error to add more.';
  }
  if (risks.length) return risks[0];
  if (quality >= 60 && direction >= 55) {
    return 'The company is still progressing, but today’s mix of growth and price is better suited to holding than adding.';
  }
  return 'The company is not weak enough to sell, but it is not clearly strong and inexpensive enough to add today.';
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

function averageMapValues(maps, symbol) {
  return average(maps.map(map => map.get(symbol)).filter(Number.isFinite));
}

function weightedAvailable(parts) {
  const available = parts.filter(([value]) => Number.isFinite(value));
  const weight = available.reduce((sum, [, partWeight]) => sum + Math.abs(partWeight), 0);
  if (!weight) return null;
  return available.reduce((sum, [value, partWeight]) => sum + value * partWeight, 0) / weight;
}

function roundedMapScore(map, symbol) {
  const value = number(map.get(symbol));
  return Number.isFinite(value) ? Math.round(value) : null;
}

function zScores(items, getter, sectorRelative = false) {
  const result = new Map();
  const allValues = items.map(item => number(getter(item))).filter(Number.isFinite);
  const grouped = new Map();
  items.forEach(item => {
    const key = sectorRelative ? item.instrument.sector : '__all__';
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  });
  const calculate = values => {
    const mean = average(values);
    const variance = average(values.map(value => (value - mean) ** 2));
    return { mean, deviation: Math.sqrt(variance || 0) };
  };
  const allStats = calculate(allValues);
  grouped.forEach(group => {
    const groupValues = group.map(item => number(getter(item))).filter(Number.isFinite);
    const stats = groupValues.length >= 4 ? calculate(groupValues) : allStats;
    group.forEach(item => {
      const value = number(getter(item));
      if (!Number.isFinite(value)) return;
      const z = stats.deviation > 0 ? (value - stats.mean) / stats.deviation : 0;
      result.set(item.symbol, clamp(z, -3, 3));
    });
  });
  return result;
}

function zScoresFromMap(items, values, sectorRelative = false) {
  return zScores(items, item => values.get(item.symbol), sectorRelative);
}

function percentileScores(items, values) {
  const ranked = items
    .map(item => ({ symbol: item.symbol, value: number(values.get(item.symbol)) }))
    .filter(item => Number.isFinite(item.value))
    .sort((a, b) => a.value - b.value);
  const result = new Map();
  if (ranked.length === 1) {
    result.set(ranked[0].symbol, 50);
    return result;
  }
  ranked.forEach((item, index) => result.set(item.symbol, index / (ranked.length - 1) * 100));
  return result;
}

function researchLabel(score) {
  if (!Number.isFinite(score)) return 'Not ranked';
  if (score >= 85) return 'Top tier';
  if (score >= 70) return 'Strong';
  if (score >= 55) return 'Positive';
  if (score >= 35) return 'Mixed';
  return 'Weak';
}

function applyResearchLeague(items) {
  const eligible = items.filter(item => item
    && item.action !== 'Checking'
    && item.instrument.type !== 'fund'
    && item.instrument.type !== 'crypto'
    && Number.isFinite(item.metrics?.currentPrice));
  if (!eligible.length) return;

  // MSCI Core Multiple-Factor, April 2025: sector-relative Value and Quality,
  // plus Momentum enhanced with Analyst Sentiment. Missing descriptors stay missing.
  const bookYieldZ = zScores(eligible, item => item.metrics?.priceToBook > 0 ? 1 / item.metrics.priceToBook : null);
  const earningsYieldZ = zScores(eligible, item => item.metrics?.forwardPe > 0 ? 1 / item.metrics.forwardPe : null);
  const valueRaw = new Map(eligible.map(item => [item.symbol, weightedAvailable([
    [bookYieldZ.get(item.symbol), 0.33],
    [earningsYieldZ.get(item.symbol), 0.67],
  ])]));
  const valueFactor = zScoresFromMap(eligible, valueRaw, true);

  const roeZ = zScores(eligible, item => item.metrics?.roe);
  const marginZ = zScores(eligible, item => item.metrics?.margin);
  const profitability = new Map(eligible.map(item => [item.symbol, averageMapValues([roeZ, marginZ], item.symbol)]));
  const leverageZ = zScores(eligible, item => item.metrics?.debtToEquity);
  const qualityRaw = new Map(eligible.map(item => [item.symbol, weightedAvailable([
    [profitability.get(item.symbol), 0.25],
    [leverageZ.get(item.symbol), -0.125],
  ])]));
  const qualityFactor = zScoresFromMap(eligible, qualityRaw, true);

  const riskAdjustedSixMonth = zScores(eligible, item => {
    const volatility = number(item.metrics?.returnVolatility);
    return volatility > 0 ? number(item.metrics?.sixMonthReturn) / volatility : null;
  });
  const riskAdjustedYear = zScores(eligible, item => {
    const volatility = number(item.metrics?.returnVolatility);
    return volatility > 0 ? number(item.metrics?.yearReturn) / volatility : null;
  });
  const priceMomentumRaw = new Map(eligible.map(item => [item.symbol, averageMapValues([
    riskAdjustedSixMonth,
    riskAdjustedYear,
  ], item.symbol)]));
  const priceMomentum = zScoresFromMap(eligible, priceMomentumRaw);

  const analystBreadthZ = zScores(eligible, item => item.metrics?.analystCount >= 3 ? item.metrics.analystPositive : null);
  const recommendationChangeZ = zScores(eligible, item => item.metrics?.analystChange);
  const estimateRevisionZ = zScores(eligible, item => item.metrics?.estimateRevisionDirection === 'up'
    ? 1
    : item.metrics?.estimateRevisionDirection === 'down' ? -1 : null);
  const earningsSurpriseZ = zScores(eligible, item => item.metrics?.earningsAverageSurprise);
  const analystSentimentRaw = new Map(eligible.map(item => [item.symbol, averageMapValues([
    analystBreadthZ,
    recommendationChangeZ,
    estimateRevisionZ,
    earningsSurpriseZ,
  ], item.symbol)]));
  const analystSentiment = zScoresFromMap(eligible, analystSentimentRaw);
  const momentumRaw = new Map(eligible.map(item => [item.symbol, averageMapValues([
    priceMomentum,
    analystSentiment,
  ], item.symbol)]));
  const momentumFactor = zScoresFromMap(eligible, momentumRaw);

  const alpha = new Map(eligible.map(item => [item.symbol,
    (number(momentumFactor.get(item.symbol)) || 0) * 0.3334
    + (number(valueFactor.get(item.symbol)) || 0) * 0.3333
    + (number(qualityFactor.get(item.symbol)) || 0) * 0.3333,
  ]));
  const scorePercentile = percentileScores(eligible, alpha);
  const valuePercentile = percentileScores(eligible, valueFactor);
  const qualityPercentile = percentileScores(eligible, qualityFactor);
  const momentumPercentile = percentileScores(eligible, momentumFactor);
  const sentimentPercentile = percentileScores(eligible, analystSentiment);

  // Cohen, Polk and Silli's "Best Ideas" research supports disclosed portfolio
  // concentration as useful information. We keep the SEC factor separate and
  // capped: it can refine close calls, never repair weak research or confidence.
  const disclosedIdeas = eligible
    .filter(item => item.investorIdea)
    .sort((a, b) => (b.investorIdea.activeBuyerCount || 0) - (a.investorIdea.activeBuyerCount || 0)
      || (b.investorIdea.ownerCount || 0) - (a.investorIdea.ownerCount || 0)
      || (b.investorIdea.highestConviction || 0) - (a.investorIdea.highestConviction || 0));
  const investorConviction = new Map();
  disclosedIdeas.forEach((item, index) => {
    const percentile = disclosedIdeas.length === 1
      ? 75
      : 55 + ((disclosedIdeas.length - index - 1) / (disclosedIdeas.length - 1)) * 45;
    investorConviction.set(item.symbol, Math.round(percentile));
  });

  eligible.forEach(item => {
    const available = [
      item.metrics?.priceToBook,
      item.metrics?.forwardPe,
      item.metrics?.roe,
      item.metrics?.margin,
      item.metrics?.debtToEquity,
      item.metrics?.sixMonthReturn,
      item.metrics?.yearReturn,
      item.metrics?.returnVolatility,
      item.metrics?.analystPositive,
      item.metrics?.analystChange,
      item.metrics?.earningsAverageSurprise,
    ].filter(Number.isFinite).length;
    const score = scorePercentile.get(item.symbol);
    item.researchRank = {
      score: Number.isFinite(score) ? Math.round(score) : null,
      label: researchLabel(score),
      value: roundedMapScore(valuePercentile, item.symbol),
      quality: roundedMapScore(qualityPercentile, item.symbol),
      momentum: roundedMapScore(momentumPercentile, item.symbol),
      analystSentiment: roundedMapScore(sentimentPercentile, item.symbol),
      coverage: available,
      coverageTotal: 11,
      universeSize: eligible.length,
      method: 'MSCI Core Multi-Factor public-data adaptation',
    };
    const conviction = investorConviction.get(item.symbol);
    item.researchRank.investorConviction = Number.isFinite(conviction) ? conviction : null;
    item.researchRank.decisionScore = Number.isFinite(score)
      ? Math.round(clamp(score + (Number.isFinite(conviction) ? (conviction - 50) * 0.1 : 0)))
      : null;
  });

  [...eligible]
    .sort((a, b) => b.researchRank.score - a.researchRank.score)
    .forEach((item, index) => { item.researchRank.researchPosition = index + 1; });
  [...eligible]
    .sort((a, b) => b.researchRank.decisionScore - a.researchRank.decisionScore
      || b.researchRank.score - a.researchRank.score)
    .forEach((item, index) => { item.researchRank.universePosition = index + 1; });
}

function correlationWords(value) {
  if (!Number.isFinite(value)) return 'Overlap checking';
  if (value >= 0.75) return `High overlap · ${value.toFixed(2)}`;
  if (value >= 0.45) return `Moderate overlap · ${value.toFixed(2)}`;
  return `Useful diversifier · ${value.toFixed(2)}`;
}

function riskContributionWords(value) {
  if (!Number.isFinite(value)) return '';
  if (value < 0) return 'slightly offsets combined risk';
  return `${plainPercent(value)} of portfolio risk`;
}

function portfolioInteraction(symbol, assessments) {
  const risk = state.portfolioRiskData;
  if (!risk?.correlations?.[symbol]) return null;
  const owned = Object.values(assessments).filter(item => item.positionValue > 0);
  const peers = owned.filter(item => item.symbol !== symbol);
  const peerWeight = peers.reduce((sum, item) => sum + item.portfolioWeight, 0);
  const weightedCorrelation = peers.reduce((sum, item) => {
    const correlation = optionalNumber(risk.correlations?.[symbol]?.[item.symbol]);
    return sum + (Number.isFinite(correlation) ? correlation * item.portfolioWeight : 0);
  }, 0);
  const coveredPeerWeight = peers.reduce((sum, item) => {
    const correlation = optionalNumber(risk.correlations?.[symbol]?.[item.symbol]);
    return sum + (Number.isFinite(correlation) ? item.portfolioWeight : 0);
  }, 0);
  const averageCorrelation = coveredPeerWeight > 0 ? weightedCorrelation / coveredPeerWeight : null;

  let portfolioVariance = 0;
  owned.forEach(left => {
    owned.forEach(right => {
      const covariance = optionalNumber(risk.annualCovariance?.[left.symbol]?.[right.symbol]);
      if (Number.isFinite(covariance)) portfolioVariance += left.portfolioWeight / 100 * right.portfolioWeight / 100 * covariance;
    });
  });
  const item = assessments[symbol];
  let riskContribution = null;
  if (item?.positionValue > 0 && portfolioVariance > 0) {
    const marginalVariance = owned.reduce((sum, peer) => {
      const covariance = optionalNumber(risk.annualCovariance?.[symbol]?.[peer.symbol]);
      return sum + (Number.isFinite(covariance) ? peer.portfolioWeight / 100 * covariance : 0);
    }, 0);
    riskContribution = item.portfolioWeight / 100 * marginalVariance / portfolioVariance * 100;
  }
  return {
    averageCorrelation,
    riskContribution,
    peerWeight,
    label: correlationWords(averageCorrelation),
  };
}

function applyPortfolioInteractions(assessments, options) {
  [...Object.values(assessments), ...options].forEach(item => {
    item.portfolioInteraction = portfolioInteraction(item.symbol, assessments);
  });
}

function applyWeightReview(assessments) {
  const companies = Object.values(assessments)
    .filter(item => item.positionValue > 0 && item.instrument.type !== 'fund' && item.instrument.type !== 'crypto');
  const companyWeight = companies.reduce((sum, item) => sum + item.portfolioWeight, 0);
  const neutralWeight = companies.length ? companyWeight / companies.length : null;

  Object.values(assessments).forEach(item => {
    if (!item.researchRank || !Number.isFinite(neutralWeight)) {
      item.weightReview = {
        tone: 'separate',
        label: 'Separate allocation',
        detail: item.instrument.type === 'fund' ? 'Portfolio anchor; company ranking does not apply.' : 'Reviewed outside the company model.',
      };
      return;
    }
    const actual = number(item.portfolioWeight) || 0;
    const score = number(item.researchRank.score);
    const averageCorrelation = number(item.portfolioInteraction?.averageCorrelation);
    const riskContribution = number(item.portfolioInteraction?.riskContribution);
    const highOverlap = averageCorrelation >= 0.75;
    const riskHeavy = Number.isFinite(riskContribution) && riskContribution > actual * 1.5;
    const farAboveNeutral = actual > neutralWeight * 2;
    const aboveNeutral = actual > neutralWeight * 1.5;
    const belowNeutral = actual < neutralWeight * 0.5;

    if (farAboveNeutral || (aboveNeutral && (score < 55 || item.confidence === 'Low' || highOverlap || riskHeavy))) {
      item.weightReview = {
        tone: 'over',
        label: 'Review: overweight',
        detail: `${plainPercent(actual)} versus ${plainPercent(neutralWeight)} neutral · ${correlationWords(averageCorrelation).toLowerCase()}${Number.isFinite(riskContribution) ? ` · ${riskContributionWords(riskContribution)}` : ''}.`,
      };
    } else if (belowNeutral && score >= 70 && item.confidence !== 'Low' && !highOverlap) {
      item.weightReview = {
        tone: 'under',
        label: 'Review: underweight',
        detail: `${plainPercent(actual)} despite strong evidence · ${correlationWords(averageCorrelation).toLowerCase()}.`,
      };
    } else {
      item.weightReview = {
        tone: 'balanced',
        label: 'Weight looks reasonable',
        detail: `${plainPercent(actual)} versus ${plainPercent(neutralWeight)} neutral · ${correlationWords(averageCorrelation).toLowerCase()}.`,
      };
    }
  });
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
  renderEvidencePolicy(dashboard.evidencePolicy);

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
  const investorIdeas = new Map((dashboard.superinvestors?.ideas || []).map(idea => [idea.symbol, idea]));
  Object.values(assessments).forEach(item => { item.investorIdea = investorIdeas.get(item.symbol) || null; });
  candidateAssessments.forEach(item => { item.investorIdea = investorIdeas.get(item.symbol) || null; });
  state.candidateAssessments = candidateAssessments;
  applyResearchLeague([...Object.values(assessments), ...candidateAssessments]);
  const usCandidates = candidateAssessments
    .filter(item => item.instrument.country === 'US')
    .sort((a, b) => (b.researchRank?.decisionScore ?? -1) - (a.researchRank?.decisionScore ?? -1));
  state.geographyAudit = {
    usChecked: usCandidates.length,
    internationalChecked: candidateAssessments.length - usCandidates.length,
    bestUs: usCandidates[0] || null,
  };
  applyPortfolioInteractions(assessments, candidateAssessments);
  applyWeightReview(assessments);
  state.opportunities = candidateAssessments
    .filter(item => item.action === 'Buy' && item.confidence !== 'Low')
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(item => ({ ...item, comparison: compareOpportunity(item, assessments, portfolioRisk) }));
  const rankedLeagueCandidates = candidateAssessments
    .filter(item => item.researchRank?.score >= 70 && item.action !== 'Sell')
    .sort((a, b) => b.researchRank.decisionScore - a.researchRank.decisionScore)
    .slice(0, 3);
  const bestUsChallenger = state.geographyAudit.bestUs;
  if (bestUsChallenger?.researchRank?.score >= 70
      && !rankedLeagueCandidates.some(item => item.symbol === bestUsChallenger.symbol)) {
    rankedLeagueCandidates.push(bestUsChallenger);
  }
  state.leagueOptions = rankedLeagueCandidates.map(item => ({
    ...item,
    isLeagueOption: true,
    isWatchOption: item.confidence === 'Low',
    positionValue: 0,
    portfolioWeight: 0,
    weightReview: {
      tone: item.confidence === 'Low' ? 'watch' : 'missing',
      label: item.confidence === 'Low' ? 'Watch only: confidence low' : 'Not owned',
      detail: `Universe rank #${item.researchRank?.universePosition || '—'} · ${correlationWords(item.portfolioInteraction?.averageCorrelation).toLowerCase()}.`,
    },
    }));

  renderBrief(dashboard, ownedSymbols, assessments);
  renderHoldings(symbolsToShow, assessments, ownedSymbols.length > 0);
  renderPortfolioValue(portfolioTotal, ownedSymbols);
  renderBenchmarkPerformance(ownedSymbols);
  renderPortfolioRisk(portfolioRisk, ownedSymbols);
  renderSuperinvestors(dashboard, assessments, candidateAssessments);
  renderOpportunities(dashboard);
  renderChanges(dashboard);
  recordDailySignals(dashboard, [...Object.values(assessments), ...candidateAssessments]);
  recordInvestorSignals(dashboard, [...Object.values(assessments), ...candidateAssessments]);
  ensureBenchmarkPerformance(ownedSymbols);
  ensurePortfolioRiskData([...ownedSymbols, ...state.leagueOptions.map(item => item.symbol)]);
}

function capConfidence(confidence) {
  const order = ['Low', 'Medium', 'High'];
  const cap = state.dashboard?.evidencePolicy?.ratingGate?.maximumConfidence;
  const confidenceIndex = order.indexOf(confidence);
  const capIndex = order.indexOf(cap);
  if (confidenceIndex < 0 || capIndex < 0) return confidence;
  return order[Math.min(confidenceIndex, capIndex)];
}

function renderEvidencePolicy(policy) {
  if (!policy || !els.evidenceSection) return;
  els.evidenceSection.dataset.status = policy.status || 'guarded';
  els.evidenceTitle.textContent = policy.title || 'Evidence standard unavailable';
  els.evidenceSummary.textContent = policy.summary || 'Kestrel cannot verify the source hierarchy yet.';
  els.evidenceAuthority.textContent = `${policy.authoritativeAreas || 0} of ${policy.totalAreas || 0}`;
  els.evidenceCap.textContent = policy.ratingGate?.maximumConfidence || 'Low';
  els.evidenceUltra.textContent = policy.ratingGate?.ultraBuyEnabled ? 'Enabled' : 'Locked';
  els.evidenceNext.textContent = policy.nextUpgrade || 'Connect the next authoritative source.';
}

function ensureBenchmarkPerformance(ownedSymbols) {
  if (!ownedSymbols.length) return;
  const performanceKey = [...ownedSymbols].sort().join(',');
  if (state.performanceKey === performanceKey && (state.performance || state.performanceRequest)) return;

  state.performanceRequest?.abort();
  const controller = new AbortController();
  state.performanceRequest = controller;
  state.performanceKey = performanceKey;
  state.performance = null;
  renderBenchmarkPerformance(ownedSymbols);

  fetch(`/api/performance?symbols=${encodeURIComponent(performanceKey)}`, {
    cache: 'no-store',
    signal: controller.signal,
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || 'Market comparison is unavailable');
      return payload;
    })
    .then(payload => {
      if (state.performanceKey !== performanceKey) return;
      state.performance = payload;
      state.performanceRequest = null;
      renderBenchmarkPerformance(ownedSymbols);
      renderHoldings(ownedSymbols, state.assessments, true);
    })
    .catch(error => {
      if (error.name === 'AbortError' || state.performanceKey !== performanceKey) return;
      state.performanceRequest = null;
      els.benchmarkSummary.textContent = 'The market comparison could not be completed.';
      els.benchmarkGrid.innerHTML = `<div class="benchmark-empty"><strong>Comparison unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
    });
}

function ensurePortfolioRiskData(symbols) {
  const riskSymbols = [...new Set(symbols)].sort();
  if (riskSymbols.length < 2) return;
  const riskKey = riskSymbols.join(',');
  if (state.portfolioRiskKey === riskKey && (state.portfolioRiskData || state.portfolioRiskRequest)) return;

  state.portfolioRiskRequest?.abort();
  const controller = new AbortController();
  state.portfolioRiskRequest = controller;
  state.portfolioRiskKey = riskKey;
  state.portfolioRiskData = null;

  fetch(`/api/portfolio-risk?symbols=${encodeURIComponent(riskKey)}`, {
    cache: 'no-store',
    signal: controller.signal,
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || 'Portfolio interaction data is unavailable');
      return payload;
    })
    .then(payload => {
      if (state.portfolioRiskKey !== riskKey) return;
      state.portfolioRiskData = payload;
      state.portfolioRiskRequest = null;
      calculateAndRender();
    })
    .catch(error => {
      if (error.name === 'AbortError' || state.portfolioRiskKey !== riskKey) return;
      state.portfolioRiskRequest = null;
      console.warn('Portfolio interaction check unavailable', error);
    });
}

function holdingPerformance(symbol, range) {
  const holding = state.performance?.data?.[symbol]?.[range];
  const benchmark = state.performance?.data?.[state.performance?.benchmark || 'SPY']?.[range];
  const holdingReturn = holding?.return === null || holding?.return === undefined ? null : number(holding.return);
  const benchmarkReturn = benchmark?.return === null || benchmark?.return === undefined ? null : number(benchmark.return);
  if (holdingReturn === null || benchmarkReturn === null) return null;
  return {
    return: holdingReturn,
    benchmarkReturn,
    relative: holdingReturn - benchmarkReturn,
    startDate: holding.startDate,
    endDate: holding.endDate,
  };
}

function portfolioPerformance(ownedSymbols, range) {
  const benchmark = state.performance?.data?.[state.performance?.benchmark || 'SPY']?.[range];
  const benchmarkReturn = benchmark?.return === null || benchmark?.return === undefined ? null : number(benchmark.return);
  if (benchmarkReturn === null) return null;

  let startValue = 0;
  let endValue = 0;
  let coveredValue = 0;
  let totalValue = 0;
  ownedSymbols.forEach(symbol => {
    const shares = number(state.positions[symbol]?.shares) || 0;
    const currentPrice = number(state.assessments[symbol]?.metrics?.currentPrice) || 0;
    const performance = state.performance?.data?.[symbol]?.[range];
    totalValue += shares * currentPrice;
    const startPrice = performance?.startPrice === null || performance?.startPrice === undefined ? null : number(performance.startPrice);
    const rangeEndPrice = performance?.endPrice === null || performance?.endPrice === undefined ? null : number(performance.endPrice);
    if (!shares || startPrice === null || rangeEndPrice === null) return;
    startValue += shares * startPrice;
    endValue += shares * rangeEndPrice;
    coveredValue += shares * currentPrice;
  });
  if (!startValue || !endValue) return null;
  const portfolioReturn = (endValue - startValue) / startValue * 100;
  return {
    return: portfolioReturn,
    benchmarkReturn,
    relative: portfolioReturn - benchmarkReturn,
    coverage: totalValue ? coveredValue / totalValue * 100 : 0,
  };
}

function renderBenchmarkPerformance(ownedSymbols) {
  if (!ownedSymbols.length) {
    els.benchmarkSection.hidden = true;
    return;
  }
  els.benchmarkSection.hidden = false;
  if (!state.performance) {
    els.benchmarkSummary.textContent = 'Comparing today’s holdings with the S&P 500.';
    els.benchmarkGrid.innerHTML = ['1 month', '1 year', '5 years'].map(label => `
      <article class="benchmark-card is-loading"><span>${label}</span><strong>Checking</strong><p>Building the like-for-like comparison.</p></article>`).join('');
    return;
  }

  const periods = [['1m', '1 month'], ['1y', '1 year'], ['5y', '5 years']];
  const results = periods.map(([range, label]) => ({ range, label, value: portfolioPerformance(ownedSymbols, range) }));
  const available = results.filter(item => item.value);
  const longest = [...available].reverse()[0];
  const longestView = longest ? relativeView(longest.value.relative) : null;
  els.benchmarkSummary.textContent = longestView
    ? `${longestView.status === 'matched' ? 'In line with' : longestView.status === 'ahead' ? 'Ahead of' : 'Behind'} the S&P 500 over ${longest.label}.`
    : 'There is not enough matching history for a fair comparison yet.';
  els.benchmarkGrid.innerHTML = results.map(({ label, value }) => {
    if (!value) return `<article class="benchmark-card is-unavailable"><span>${label}</span><strong>Not enough history</strong><p>Kestrel will not fill the gap with an estimate.</p></article>`;
    const relative = relativeView(value.relative);
    const coverageCopy = value.coverage < 99 ? ` · covers ${plainPercent(value.coverage, 0)} of today’s portfolio` : '';
    return `<article class="benchmark-card ${relative.className}">
      <span>${label}</span>
      <strong>${escapeHtml(relative.words)}</strong>
      <p>Your holdings ${percent(value.return)} · S&amp;P 500 ${percent(value.benchmarkReturn)}${escapeHtml(coverageCopy)}</p>
    </article>`;
  }).join('');
  const sources = [...new Set(Object.values(state.performance.data || {}).flatMap(ranges => Object.values(ranges || {}).map(item => item?.source).filter(Boolean)))];
  els.benchmarkNote.textContent = `This asks how today’s holdings would have performed if held for each full period, compared with the S&P 500 tracker SPY. Purchases, sales, deposits, withdrawals, tax and fees are not included. Source${sources.length === 1 ? '' : 's'}: ${sources.join(' and ') || 'historical market data'}.`;
}

async function recordDailySignals(dashboard, assessments) {
  if (QA_MODE) return;
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

async function recordInvestorSignals(dashboard, assessments) {
  if (QA_MODE || dashboard.status !== 'ready' || !dashboard.lastFullRefresh) return;
  const snapshotKey = String(dashboard.lastFullRefresh);
  if (state.savedInvestorSignalsFor === snapshotKey) return;
  const bySymbol = new Map(assessments.map(item => [item.symbol, item]));
  const benchmarkPrice = number(bySymbol.get('SPY')?.metrics?.currentPrice)
    || number(assess('SPY', dashboard.data.SPY, null)?.metrics?.currentPrice);
  const ideas = (dashboard.superinvestors?.ideas || [])
    .map(idea => ({
      symbol: idea.symbol,
      price: number(bySymbol.get(idea.symbol)?.metrics?.currentPrice),
      managers: idea.managers,
    }))
    .filter(idea => Number.isFinite(idea.price));
  if (!Number.isFinite(benchmarkPrice) || !ideas.length) return;
  state.savedInvestorSignalsFor = snapshotKey;
  try {
    const response = await fetch('/api/investor-signals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ideas, benchmarkPrice }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Manager outcome journal rejected the snapshot');
    state.investorCalibration = payload.calibration;
    renderSuperinvestors(dashboard, state.assessments, state.candidateAssessments);
  } catch (error) {
    state.savedInvestorSignalsFor = null;
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
  els.holdingsList.dataset.riskReady = state.portfolioRiskData ? 'true' : 'false';
  if (!hasOwnedPositions) {
    els.holdingsList.innerHTML = `
      <div class="empty-card">
        <strong>Your holdings are not set up on this address</strong>
        <span>Choose “Edit holdings” and enter your share counts. Kestrel will keep them in this browser.</span>
      </div>`;
    return;
  }

  const sorted = [
    ...symbols.map(symbol => assessments[symbol]),
    ...state.leagueOptions,
  ]
    .sort((a, b) => {
      const aScore = number(a.researchRank?.decisionScore);
      const bScore = number(b.researchRank?.decisionScore);
      if (Number.isFinite(aScore) && Number.isFinite(bScore)) return bScore - aScore;
      if (Number.isFinite(aScore)) return -1;
      if (Number.isFinite(bScore)) return 1;
      return b.positionValue - a.positionValue;
    });
  let leagueRank = 0;
  sorted.forEach(item => {
    item.holdingRank = item.researchRank ? ++leagueRank : null;
  });

  els.holdingsList.innerHTML = `
    <div class="league-header" aria-hidden="true">
      <span>Decision rank</span><span>Decision and company</span><span>Analysts</span><span>Value</span><span>Quality</span><span>Results</span><span>Trend</span><span>Position / weight</span>
    </div>
    ${renderGeographyAudit()}
    ${sorted.map(renderHoldingRow).join('')}`;
  els.holdingsList.querySelectorAll('[data-detail-symbol]').forEach(button => {
    button.addEventListener('click', () => openDetail(button.dataset.detailSymbol, button.dataset.leagueOption === 'true'));
  });
}

function renderGeographyAudit() {
  const audit = state.geographyAudit;
  if (!audit) return '';
  const best = audit.bestUs;
  const bestText = best?.researchRank
    ? `Best US challenger: ${best.instrument.name} at ${best.researchRank.score}/100${best.researchRank.score >= 70 ? best.confidence === 'Low' ? ' · score passes; confidence does not' : ' · passes the option gate' : ' · below the 70-point option gate'}`
    : 'No US challenger has enough evidence to rank yet';
  return `<div class="league-audit"><strong>Country-neutral check</strong><span>${audit.usChecked} US and ${audit.internationalChecked} international candidates assessed on identical rules.</span><em>${escapeHtml(bestText)}</em></div>`;
}

function leagueScore(value) {
  return Number.isFinite(value) ? `${Math.round(value)}` : '—';
}

function ratio(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)}×` : '—';
}

function signedPoints(value) {
  if (!Number.isFinite(value) || Math.abs(value) < 0.05) return 'No monthly change';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} points this month`;
}

function renderHoldingRow(assessment) {
  const { symbol, instrument, action, confidence, reason, metrics, positionValue, portfolioWeight, position, researchRank, weightReview, isLeagueOption, isWatchOption } = assessment;
  const dayClass = metrics?.dayChange >= 0 ? 'positive' : 'negative';
  const price = metrics?.currentPrice;
  const cost = number(position?.cost);
  const shares = number(position?.shares) || 0;
  const gain = cost && price ? (price - cost) * shares : null;
  const gainText = isLeagueOption
    ? 'Strong evidence, currently missing'
    : gain === null ? `${shares.toFixed(shares % 1 ? 2 : 0)} shares` : `${gain >= 0 ? '+' : ''}${compactMoney(gain)} since purchase`;
  const oneYear = holdingPerformance(symbol, '1y');
  const oneYearView = oneYear ? relativeView(oneYear.relative) : null;
  const marketComparison = isLeagueOption
    ? '<span class="holding-benchmark is-option">Compare before changing anything</span>'
    : oneYear
    ? `<span class="holding-benchmark ${oneYearView.className}">1Y · ${escapeHtml(oneYearView.words.toLowerCase())}</span>`
    : '<span class="holding-benchmark is-pending">1Y market comparison checking</span>';
  const guide = assessment.ownerGuide || ownerGuide(symbol, instrument);
  const analystCount = number(metrics?.analystCount);
  const analystPositive = number(metrics?.analystPositive);
  const analystVotes = analystCount
    ? `${metrics.analystPositiveCount}/${analystCount} Buy or Strong Buy`
    : 'No current vote';
  const analystBreakdown = analystCount
    ? `${metrics.analystStrongBuy} strong buy · ${metrics.analystBuy} buy · ${metrics.analystHold} hold · ${metrics.analystSell + metrics.analystStrongSell} sell`
    : 'Missing coverage is not counted as support';
  const earningsRecord = Number.isFinite(metrics?.earningsReports) && metrics.earningsReports > 0
    ? `${metrics.earningsBeats}/${metrics.earningsReports} recent beats`
    : 'Recent result record unavailable';
  const researchCoverage = researchRank
    ? `${researchRank.coverage}/${researchRank.coverageTotal} inputs`
    : 'Separate asset model';

  return `
    <article class="assessment-row league-row${isLeagueOption ? ' is-league-option' : ''}${isWatchOption ? ' is-watch-option' : ''}" data-action="${escapeHtml(action)}">
      <div class="league-rank-cell">
        <span class="holding-rank">${isLeagueOption ? 'OPTION' : researchRank ? `#${assessment.holdingRank}` : '—'}</span>
        <strong>${leagueScore(researchRank?.decisionScore)}</strong>
        <small>${researchRank ? 'Decision score' : 'Not comparable'}</small>
        <em>${researchRank ? `Research ${leagueScore(researchRank.score)} · #${researchRank.universePosition}/${researchRank.universeSize}` : 'Not a company'}</em>
      </div>
      <div class="company-cell">
        ${isLeagueOption ? `<div class="missing-ribbon">${isWatchOption ? 'US watch · confidence low' : 'You do not own this'}</div>` : ''}
        <div class="company-line"><strong>${escapeHtml(instrument.name)}</strong><span class="ticker">${escapeHtml(symbol)}</span></div>
        <div class="company-price"><span>${money(price, 2)}</span><span class="${dayClass}">${percent(metrics?.dayChange)}</span></div>
        <div class="decision-inline"><span>${escapeHtml(action)}</span><small>${escapeHtml(confidence)} confidence</small></div>
        <p class="plain-reason">${escapeHtml(reason)}</p>
        <div class="what-it-does">
          <span>What it does</span>
          <p>${escapeHtml(guide.business)}</p>
        </div>
        ${assessment.investorIdea ? `<span class="filing-signal">Investor conviction ${leagueScore(researchRank?.investorConviction)} · ${assessment.investorIdea.activeBuyerCount || 0} buying manager${assessment.investorIdea.activeBuyerCount === 1 ? '' : 's'} · ${assessment.investorIdea.ownerCount || 0} owner${assessment.investorIdea.ownerCount === 1 ? '' : 's'}</span>` : ''}
        <button type="button" data-detail-symbol="${escapeHtml(symbol)}" data-league-option="${isLeagueOption ? 'true' : 'false'}">Full evidence</button>
      </div>
      <div class="league-metric analyst-cell">
        <span>Analyst agreement</span>
        <strong>${plainPercent(analystPositive, 0)}</strong>
        <small>${escapeHtml(analystVotes)}</small>
        <em>${escapeHtml(analystBreakdown)}</em>
        <i>${escapeHtml(signedPoints(metrics?.analystChange))}</i>
      </div>
      <div class="league-metric">
        <span>Value score</span>
        <strong>${leagueScore(researchRank?.value)}</strong>
        <small>Forward P/E ${ratio(metrics?.forwardPe)}</small>
        <em>Price/book ${ratio(metrics?.priceToBook)}</em>
      </div>
      <div class="league-metric">
        <span>Quality score</span>
        <strong>${leagueScore(researchRank?.quality)}</strong>
        <small>ROE ${plainPercent(metrics?.roe, 1)}</small>
        <em>Debt/equity ${ratio(metrics?.debtToEquity)}</em>
      </div>
      <div class="league-metric">
        <span>Recent results</span>
        <strong>${Number.isFinite(metrics?.earningsBeatRate) ? plainPercent(metrics.earningsBeatRate, 0) : '—'}</strong>
        <small>${escapeHtml(earningsRecord)}</small>
        <em>Sales ${percent(metrics?.revenueGrowth)} · EPS ${percent(metrics?.earningsGrowth)}</em>
      </div>
      <div class="league-metric">
        <span>Trend score</span>
        <strong>${leagueScore(researchRank?.momentum)}</strong>
        <small>6M ${percent(metrics?.sixMonthReturn)}</small>
        <em>1Y ${percent(metrics?.yearReturn)} · analyst ${leagueScore(researchRank?.analystSentiment)}</em>
      </div>
      <div class="position-cell">
        <strong>${isLeagueOption ? 'Not owned' : compactMoney(positionValue)}</strong>
        <span>${isLeagueOption ? '0% of portfolio' : `${plainPercent(portfolioWeight)} of portfolio`}</span>
        <span>${escapeHtml(gainText)}</span>
        ${marketComparison}
        ${weightReview ? `<div class="weight-flag" data-tone="${escapeHtml(weightReview.tone)}"><b>${escapeHtml(weightReview.label)}</b><span>${escapeHtml(weightReview.detail)}</span></div>` : ''}
        <small>${escapeHtml(researchCoverage)}</small>
      </div>
    </article>`;
}

function renderSuperinvestors(dashboard, assessments, candidates) {
  const intelligence = dashboard.superinvestors;
  if (!intelligence) return;
  const allAssessments = new Map([
    ...Object.values(assessments).map(item => [item.symbol, item]),
    ...candidates.map(item => [item.symbol, item]),
  ]);
  const ideas = (intelligence.ideas || []).map(idea => ({ ...idea, assessment: allAssessments.get(idea.symbol) || null }));
  const qualified = ideas.filter(idea => !state.positions[idea.symbol]?.shares
    && idea.assessment?.action === 'Buy' && idea.assessment?.confidence !== 'Low').length;
  const alreadyOwned = ideas.filter(idea => number(state.positions[idea.symbol]?.shares) > 0).length;
  const period = intelligence.latestPeriodEnd
    ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${intelligence.latestPeriodEnd}T00:00:00Z`))
    : 'an unavailable quarter end';
  els.superinvestorSummary.textContent = `${ideas.length} unique companies checked · ${qualified} qualified · ${alreadyOwned} already owned.`;
  els.superinvestorPeriod.textContent = `Positions are as at ${period}. They may be 45 days old and exclude shorts, hedges and non-US listings.`;

  if (!ideas.length) {
    els.superinvestorList.innerHTML = `<div class="empty-card wide"><strong>${escapeHtml(intelligence.status === 'error' ? 'SEC filing check unavailable' : 'Still resolving disclosed positions')}</strong><span>${escapeHtml(intelligence.message)}</span></div>`;
    return;
  }

  const calibration = state.investorCalibration;
  const matured = (calibration?.managers || []).reduce((sum, manager) => sum + (manager.matured365 || 0), 0);
  const validationCopy = calibration?.status === 'validated'
    ? `${matured} full one-year outcomes are available. Only managers with at least ${calibration.minimumValidatedIdeas} mature ideas may earn extra trust.`
    : `${calibration?.ideasRecorded || 0} fresh buying ideas are now stored. One-year results are not ready, so every manager still receives equal trust.`;
  const validationCard = `<article class="investor-validation-card wide">
    <span>Manager skill check</span>
    <strong>${calibration?.status === 'validated' ? 'Measured track records available' : 'Building a verified track record'}</strong>
    <p>${escapeHtml(validationCopy)}</p>
  </article>`;
  els.superinvestorList.innerHTML = validationCard + ideas.map((idea, index) => renderSuperinvestorIdea(idea, index)).join('');
  els.superinvestorList.querySelectorAll('[data-investor-symbol]').forEach(button => {
    button.addEventListener('click', () => openDetail(button.dataset.investorSymbol, true));
  });
}

function renderSuperinvestorIdea(idea, index) {
  const assessment = idea.assessment;
  const owned = number(state.positions[idea.symbol]?.shares) > 0;
  const active = number(idea.activeBuyerCount) || 0;
  const headline = active
    ? `${active} tracked manager${active === 1 ? '' : 's'} newly bought or increased it`
    : `Held by ${idea.ownerCount} tracked manager${idea.ownerCount === 1 ? '' : 's'}`;
  const firstLimit = assessment?.confidenceDetails?.limits?.[0];
  const verdict = !assessment || assessment.action === 'Checking'
    ? { tone: 'checking', label: 'Checks still running', detail: 'No decision will be shown until the independent evidence arrives.' }
    : owned
      ? { tone: 'owned', label: 'Already owned — not a missing opportunity', detail: `Current independent view: ${assessment.action} with ${assessment.confidence.toLowerCase()} confidence. ${assessment.reason}` }
      : assessment.action === 'Buy' && assessment.confidence !== 'Low'
        ? { tone: 'passed', label: 'Qualified opportunity', detail: `Independent business, price and direction checks pass with ${assessment.confidence.toLowerCase()} confidence.` }
        : assessment.confidence === 'Low'
          ? { tone: 'rejected', label: 'Does not qualify — confidence is Low', detail: firstLimit ? `Missing check: ${firstLimit}.` : assessment.reason }
          : { tone: 'rejected', label: `Does not qualify — independent view is ${assessment.action}`, detail: assessment.reason };
  const managerRows = (idea.managers || []).slice(0, 3).map(manager => {
    const filed = manager.filedAt
      ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${manager.filedAt}T00:00:00Z`))
      : 'date unavailable';
    return `
    <li>
      <span><strong>${escapeHtml(manager.name)}</strong><small>${escapeHtml(manager.style)} · filed ${escapeHtml(filed)}</small></span>
      <span class="filing-action" data-action="${escapeHtml(manager.action.toLowerCase())}">${escapeHtml(manager.action)}</span>
      <span><strong>${plainPercent(number(manager.portfolioWeight), 2)}</strong><small>of disclosed portfolio</small></span>
      <a href="${escapeHtml(manager.filingUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${escapeHtml(manager.name)} SEC filing">SEC ↗</a>
    </li>`;
  }).join('');
  return `<article class="filing-card" data-verdict="${verdict.tone}">
    <div class="filing-card-rank">${String(index + 1).padStart(2, '0')}</div>
    <div class="filing-card-heading">
      <span class="filing-owned">${owned ? 'You own this' : 'You do not own this'}</span>
      <h3>${escapeHtml(assessment?.instrument?.name || idea.name || idea.issuer)} <span>${escapeHtml(idea.symbol)}</span></h3>
      <p>${escapeHtml(headline)}</p>
      ${(idea.shareClasses || []).length > 1 ? `<small class="share-class-note">One company · ${idea.shareClasses.map(escapeHtml).join(' + ')} merged</small>` : ''}
    </div>
    <ul class="filing-manager-list">${managerRows}</ul>
    <div class="filing-card-bottom">
      <span class="filing-verdict"><strong>${escapeHtml(verdict.label)}</strong><small>${escapeHtml(verdict.detail)}</small></span>
      ${assessment ? `<button type="button" data-investor-symbol="${escapeHtml(idea.symbol)}">See independent evidence</button>` : '<span>Market evidence has not arrived yet</span>'}
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
  els.portfolioRiskSummary.textContent = state.portfolioRiskData
    ? 'Position reviews now include one-year correlation and covariance.'
    : risk.status === 'Concentrated'
      ? 'One part of the portfolio deserves a closer look.'
      : 'Calculating how the holdings move together.';
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
  const guide = item.ownerGuide || ownerGuide(symbol, instrument);
  return `
    <article class="opportunity-card">
      <div>
        <h3>${escapeHtml(instrument.name)} <span class="ticker">${escapeHtml(symbol)}</span></h3>
        <span class="company-price">${money(metrics.currentPrice, 2)} · ${escapeHtml(instrument.country)}</span>
      </div>
      <span class="opportunity-rank">0${index + 1}</span>
      <div class="opportunity-business"><span>What it does</span><p>${escapeHtml(guide.business)}</p></div>
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
    previous = JSON.parse(localStorage.getItem(ACTION_SNAPSHOT_KEY) || '{}');
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

  localStorage.setItem(ACTION_SNAPSHOT_KEY, JSON.stringify(current));
  state.savedSnapshotFor = snapshotKey;
}

function openDetail(symbol, isOpportunity = false) {
  const item = isOpportunity
    ? state.leagueOptions.find(candidate => candidate.symbol === symbol)
      || state.opportunities.find(candidate => candidate.symbol === symbol)
      || state.candidateAssessments.find(candidate => candidate.symbol === symbol)
    : state.assessments[symbol];
  if (!item) return;

  const { instrument, action, confidence, reason, positives, risks, metrics, componentScores, rawData, valuation, analystEvidence, earningsEvidence, namedAnalystEvidence } = item;
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
    <div class="detail-section owner-brief-section">
      <h3>Understand this holding in one minute</h3>
      ${renderOwnerBrief(item)}
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
      <h3>Against the S&amp;P 500</h3>
      ${renderHoldingBenchmark(symbol)}
      <p class="chart-source">Price performance is supporting evidence only. It does not change the Buy, Hold or Sell rating by itself.</p>
    </div>
    <div class="detail-section">
      <h3>What looks like fair value</h3>
      ${renderFairValue(valuation, metrics?.currentPrice)}
    </div>
    <div class="detail-section">
      <h3>The simple investment case</h3>
      ${renderThesis(item)}
    </div>
    ${item.comparison ? `<div class="detail-section">
      <h3>How it could fit your portfolio</h3>
      <div class="fit-card"><strong>${escapeHtml(item.comparison.title)}</strong><p>${escapeHtml(item.comparison.detail)}</p></div>
    </div>` : ''}
    <div class="detail-section">
      <h3>What Wall Street currently thinks</h3>
      ${renderAnalystEvidence(analystEvidence, earningsEvidence, namedAnalystEvidence, metrics)}
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
        ${metricTile('Buy or Strong Buy', metrics?.analystPositiveCount === null || metrics?.analystPositiveCount === undefined ? 'Not available' : `${metrics.analystPositiveCount}/${metrics.analystCount}`)}
      </div>
    </div>
    <div class="detail-section">
      <h3>Evidence status</h3>
      ${renderConfidenceDetails(item.confidenceDetails)}
      ${renderEvidenceStatus(rawData?.sec, confidence, fetched, instrument.securityIdentity, instrument.marketIntegrity)}
      ${item.ultraCandidate && action !== 'Ultra Buy' ? '<p class="plain-reason"><strong>Worth noting:</strong> This company clears the quantitative Ultra Buy bar, but portfolio risk still prevents that rating.</p>' : ''}
      ${rawData?.errors?.length ? `<p class="plain-reason"><strong>Missing evidence:</strong> ${escapeHtml(rawData.errors.join(' · '))}</p>` : ''}
    </div>`;

  els.detailDialog.showModal();
  setupHistoryChart(symbol);
  ensureDetailBenchmark(symbol);
}

async function ensureDetailBenchmark(symbol) {
  if (state.performance?.data?.[symbol]) return;
  state.detailPerformanceRequest?.abort();
  const controller = new AbortController();
  state.detailPerformanceRequest = controller;
  try {
    const response = await fetch(`/api/performance?symbols=${encodeURIComponent(symbol)}`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || 'Market comparison is unavailable');
    state.performance = state.performance
      ? {
          ...state.performance,
          data: { ...state.performance.data, ...payload.data },
          errors: { ...state.performance.errors, ...payload.errors },
        }
      : payload;
    const block = els.detailContent.querySelector('.holding-benchmark-grid');
    if (block?.dataset.benchmarkSymbol === symbol) block.outerHTML = renderHoldingBenchmark(symbol);
  } catch (error) {
    if (error.name !== 'AbortError') console.warn(`Benchmark comparison unavailable for ${symbol}`);
  } finally {
    if (state.detailPerformanceRequest === controller) state.detailPerformanceRequest = null;
  }
}

function renderHoldingBenchmark(symbol) {
  const periods = [['1m', '1 month'], ['1y', '1 year'], ['5y', '5 years']];
  const isChecking = !state.performance?.data?.[symbol];
  return `<div class="holding-benchmark-grid" data-benchmark-symbol="${escapeHtml(symbol)}">${periods.map(([range, label]) => {
    const value = holdingPerformance(symbol, range);
    if (!value) return `<div><span>${label}</span><strong>${isChecking ? 'Checking' : 'Not enough history'}</strong><small>${isChecking ? 'Loading a matching market record.' : 'Kestrel will not fill the gap with an estimate.'}</small></div>`;
    const relative = relativeView(value.relative);
    return `<div class="${relative.className}">
      <span>${label}</span>
      <strong>${escapeHtml(relative.words)}</strong>
      <small>${escapeHtml(symbol)} ${percent(value.return)} · S&amp;P 500 ${percent(value.benchmarkReturn)}</small>
    </div>`;
  }).join('')}</div>`;
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

function renderOwnerBrief(item) {
  const guide = item.ownerGuide || ownerGuide(item.symbol, item.instrument);
  const vote = item.analystVote || analystVoteText(null, true);
  return `<div class="owner-brief-grid">
    <article>
      <span>What you actually own</span>
      <p>${escapeHtml(guide.business)}</p>
    </article>
    <article>
      <span>How it could build wealth</span>
      <p>${escapeHtml(guide.wealthDriver)}</p>
    </article>
    <article class="is-risk">
      <span>The biggest danger</span>
      <p>${escapeHtml(guide.mainRisk)}</p>
    </article>
    <article class="is-vote">
      <span>Wall Street vote</span>
      <strong>${escapeHtml(vote.headline)}</strong>
      <small>${escapeHtml(vote.detail)}</small>
    </article>
  </div>`;
}

function renderConfidenceDetails(details) {
  if (!details) return '';
  const confirmed = Array.isArray(details.confirmed) ? details.confirmed : [];
  const limits = Array.isArray(details.limits) ? details.limits : [];
  return `<div class="confidence-explainer">
    <strong>${escapeHtml(details.headline)}</strong>
    <div>
      <span>What is checked</span>
      <p>${escapeHtml(confirmed.length ? confirmed.join('; ') : 'No independent check has completed yet')}.</p>
    </div>
    <div>
      <span>What still limits certainty</span>
      <p>${escapeHtml(limits.length ? limits.join('; ') : 'No material evidence limitation is currently visible')}.</p>
    </div>
  </div>`;
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

function renderAnalystEvidence(analystEvidence, earningsEvidence, namedAnalystEvidence, metrics = {}) {
  const hasVote = Number.isFinite(metrics?.analystCount) && metrics.analystCount > 0;
  if (!analystEvidence && !earningsEvidence && !namedAnalystEvidence?.recentActions?.length && !hasVote) {
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
  const namedActions = Array.isArray(namedAnalystEvidence?.recentActions) ? namedAnalystEvidence.recentActions.slice(0, 4) : [];
  const namedHtml = namedActions.length
    ? `<div class="fair-value-empty">
        <strong>${escapeHtml(namedAnalystEvidence.uniqueFirms)} named research firms checked</strong>
        <span>${escapeHtml(namedAnalystEvidence.message)}</span>
      </div>
      <ul class="detail-bullets">${namedActions.map(action => {
        const analyst = [action.analyst, action.firm].filter(Boolean).join(' · ');
        const target = number(action.priceTarget) ? ` · target ${money(number(action.priceTarget), 2)}` : '';
        const description = `${action.date} · ${analyst} · ${action.action || 'Updates'} ${action.rating || 'rating'}${target}`;
        return `<li>${action.sourceUrl ? `<a href="${escapeHtml(action.sourceUrl)}" target="_blank" rel="noopener">${escapeHtml(description)}</a>` : escapeHtml(description)}</li>`;
      }).join('')}</ul>`
    : '';
  const voteHtml = hasVote
    ? `<div class="wall-street-vote">
        <span>Latest recommendation vote</span>
        <strong>${escapeHtml(`${metrics.analystPositiveCount}/${metrics.analystCount} analysts say Buy or Strong Buy`)}</strong>
        <p>${escapeHtml(`${metrics.analystStrongBuy || 0} strong buy · ${metrics.analystBuy || 0} buy · ${metrics.analystHold || 0} hold · ${metrics.analystSell || 0} sell · ${metrics.analystStrongSell || 0} strong sell`)}</p>
      </div>`
    : '<div class="fair-value-empty"><strong>No current analyst vote</strong><span>Missing votes are not counted as positive.</span></div>';

  return `${voteHtml}<div class="analyst-evidence-grid">
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
  ${namedHtml}
  <p class="chart-source">Finnhub recommendation consensus${analystEvidence?.source ? ` · ${escapeHtml(analystEvidence.source)}` : ''}. These are analyst opinions, not verified company results.</p>`;
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
  const benchmark = holdingPerformance(payload.symbol, payload.range);
  const benchmarkView = benchmark ? relativeView(benchmark.relative) : null;
  const benchmarkCopy = benchmark
    ? ` · S&P 500 ${percent(benchmark.benchmarkReturn)} · ${benchmarkView.words.toLowerCase()}`
    : '';
  summary.innerHTML = `<strong class="${directionClass}">${directionText}</strong> over ${escapeHtml(rangeLabel)} · ${money(last.close, 2)} latest${escapeHtml(benchmarkCopy)}`;

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

function renderEvidenceStatus(sec, confidence, marketFetched, identity, marketIntegrity) {
  const marketLine = marketIntegrity?.institutionalVerified
    ? '<p class="plain-reason"><strong>Price check passed.</strong> The decision price matches an official consolidated close and an independent comparison.</p>'
    : marketIntegrity?.ratingReady
      ? '<p class="plain-reason"><strong>Price check passed.</strong> Two daily price feeds agree and no unexplained split-sized jump was found.</p>'
      : '<p class="plain-reason"><strong>Price check needs attention.</strong> The price or split-adjustment records do not yet agree.</p>';
  const identityIds = [identity?.identifiers?.figi ? `FIGI ${identity.identifiers.figi}` : null, identity?.identifiers?.cik ? `SEC CIK ${identity.identifiers.cik}` : null].filter(Boolean).join(' · ');
  const identityReady = identity?.status === 'resolved';
  const identityCard = `<div class="evidence-card ${identityReady ? 'is-verified' : 'is-limited'}">
    <div class="evidence-card-head"><strong>${identityReady ? 'Permanent identity resolved' : 'Identity needs review'}</strong><span>OpenFIGI + SEC</span></div>
    <div class="source-filing"><span>${escapeHtml(identity?.name || identity?.symbol || 'Instrument not mapped')}</span><span>${escapeHtml(identityIds || identity?.message || 'No stable identifier available')}</span></div>
  </div>`;
  const checkedPrice = marketIntegrity?.checkedClose || marketIntegrity?.officialClose;
  const checkedClose = number(checkedPrice?.close);
  const marketCard = checkedPrice || state.dashboard?.marketIntegrity?.summary?.keyConfigured
    ? `<div class="evidence-card ${marketIntegrity?.ratingReady ? 'is-verified' : 'is-limited'}">
        <div class="evidence-card-head"><strong>${marketIntegrity?.institutionalVerified ? 'Official market checks agree' : marketIntegrity?.ratingReady ? 'Daily market checks agree' : 'Market checks need review'}</strong><span>${marketIntegrity?.institutionalVerified ? 'Nasdaq NLS+ · Databento' : 'Cost-controlled cross-check'}</span></div>
        <div class="source-filing"><span>${checkedClose ? `${money(checkedClose, 2)} close on ${escapeHtml(checkedPrice.date)}` : 'No checked close available'}</span><span>${escapeHtml(marketIntegrity?.message || 'Corporate-action validation has not completed')}</span></div>
      </div>`
    : '';
  if (!sec || sec.status === 'error' || sec.status === 'unavailable') {
    const message = sec?.message || 'The official filing check has not completed yet.';
    return `${marketLine}${identityCard}${marketCard}<div class="evidence-card is-limited"><strong>Official filing not verified</strong><span>${escapeHtml(message)}</span></div>`;
  }
  if (sec.status === 'not_applicable') {
    return `${marketLine}${identityCard}${marketCard}<div class="evidence-card is-neutral"><strong>Fund assessment</strong><span>${escapeHtml(sec.message)}</span></div>`;
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

  return `${marketLine}${identityCard}${marketCard}
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
  backupPositions();
  state.positions = next;
  state.performanceRequest?.abort();
  state.performanceRequest = null;
  state.performance = null;
  state.performanceKey = null;
  state.portfolioRiskRequest?.abort();
  state.portfolioRiskRequest = null;
  state.portfolioRiskData = null;
  state.portfolioRiskKey = null;
  savePositions();
  savePortfolioToServer();
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
els.evidencePolicyButton.addEventListener('click', () => els.evidenceDialog.showModal());
els.sarwaReviewButton.addEventListener('click', openSarwaReview);
els.sarwaApplyButton.addEventListener('click', applySarwaSnapshot);
els.sarwaDiscardButton.addEventListener('click', discardSarwaSnapshot);
els.holdingsForm.addEventListener('submit', handleHoldingsSave);

document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
});

async function startKestrel() {
  await syncPortfolioFromServer();
  fetchSarwaStatus();
  fetchDashboard();
}

startKestrel();
