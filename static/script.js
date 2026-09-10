const lookupForm = document.getElementById('lookup-form');
const tickerInput = document.getElementById('ticker-input');
const errorMsg = document.getElementById('error-msg');
const results = document.getElementById('results');
const runBtn = document.getElementById('run-btn');
const runStatus = document.getElementById('run-status');
const llmToggle = document.getElementById('llm-toggle');
const verdictBox = document.getElementById('verdict');

let currentTicker = null;
let priceChart = null;
let rsiChart = null;
let isLookingUp = false;

const AMBER = '#E3B341';
const BULL = '#3FB950';
const BEAR = '#F85149';
const MUTED = '#8B93A1';
const GRID = 'rgba(232, 230, 225, 0.06)';

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
  results.hidden = true;
}

function clearError() {
  errorMsg.hidden = true;
}

function fmtMoney(n) {
  if (n === null || n === undefined || n === 'N/A') return 'N/A';
  if (typeof n === 'number' && n > 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
  if (typeof n === 'number' && n > 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
  return n;
}

function fmtVolume(n) {
  if (n === null || n === undefined || n === 'N/A') return 'N/A';
  if (n > 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n > 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n > 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}

function updateClock() {
  const now = new Date();
  const clockEl = document.getElementById('clock');
  if (clockEl) {
    clockEl.textContent = now.toLocaleTimeString(undefined, { hour12: false }) + ' local';
  }
}
updateClock();
setInterval(updateClock, 1000);

async function lookupTicker(ticker) {
  if (isLookingUp) return;   // ignore a second click/submit while one is already in flight
  isLookingUp = true;

  clearError();
  runStatus.textContent = 'loading…';
  verdictBox.hidden = true;

  let fetchFailed = false;
  let data = null;

  try {
    const res = await fetch(`/api/stock/${encodeURIComponent(ticker)}`);
    data = await res.json();
  } catch (err) {
    fetchFailed = true;
  }

  if (fetchFailed) {
    showError('Could not reach the server. Is app.py still running?');
    runStatus.textContent = '';
    isLookingUp = false;
    return;
  }

  if (!data.ok) {
    showError(data.error || `Couldn't find ${ticker}. Check the symbol and try again.`);
    runStatus.textContent = '';
    isLookingUp = false;
    return;
  }

  if (typeof Chart === 'undefined') {
    showError('Chart.js failed to load, so charts can\'t be drawn. Check the browser console / network tab for a blocked or failed request to static/vendor/chart.umd.min.js (an ad blocker or extension can cause this).');
    runStatus.textContent = '';
    isLookingUp = false;
    return;
  }

  try {
    currentTicker = data.info.ticker;   // use the server-resolved symbol, not the raw query
    tickerInput.value = currentTicker;   // e.g. "nvidia" -> "NVDA", so the user sees what matched
    renderOverview(data.info);
    renderCharts(data.chart);
    results.hidden = false;
  } catch (err) {
    console.error('Render error:', err);
    showError(`Got the data but had trouble displaying it: ${err.message}`);
  } finally {
    runStatus.textContent = '';
    isLookingUp = false;
  }
}

function renderOverview(info) {
  document.getElementById('company-name').textContent = info.name;
  document.getElementById('sector').textContent = info.sector;
  document.getElementById('price').textContent = info.last_price;

  const changeEl = document.getElementById('change');
  const isUp = info.change >= 0;
  const sign = isUp ? '+' : '';
  const arrow = isUp ? '▲' : '▼';
  changeEl.textContent = `${arrow} ${sign}${info.change} (${sign}${info.change_pct}%)`;
  changeEl.className = 'change ' + (isUp ? 'up' : 'down');

  document.getElementById('market-cap').textContent = fmtMoney(info.market_cap);
  document.getElementById('pe-ratio').textContent = info.pe_ratio;
  document.getElementById('volume').textContent = fmtVolume(info.volume);
  document.getElementById('high-52w').textContent = info['52w_high'];
  document.getElementById('low-52w').textContent = info['52w_low'];
}

function renderCharts(rows) {
  const labels = rows.map(r => r.date);

  const priceCtx = document.getElementById('price-chart');
  const rsiCtx = document.getElementById('rsi-chart');

  // Destroy any chart already attached to these canvases (covers both our
  // own tracked instances and any stray one from an overlapping call).
  const existingPrice = Chart.getChart(priceCtx);
  if (existingPrice) existingPrice.destroy();
  const existingRsi = Chart.getChart(rsiCtx);
  if (existingRsi) existingRsi.destroy();

  priceChart = new Chart(priceCtx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Close', data: rows.map(r => r.close), borderColor: '#E8E6E1', borderWidth: 1.5, pointRadius: 0 },
        { label: 'SMA20', data: rows.map(r => r.sma20), borderColor: AMBER, borderWidth: 1, pointRadius: 0 },
        { label: 'SMA50', data: rows.map(r => r.sma50), borderColor: '#5B8DEF', borderWidth: 1, pointRadius: 0 },
      ],
    },
    options: chartOptions(),
  });

  const guideLevels = [30, 70];
  rsiChart = new Chart(rsiCtx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'RSI14', data: rows.map(r => r.rsi), borderColor: '#B98CE8', borderWidth: 1.5, pointRadius: 0 },
        ...guideLevels.map(level => ({
          label: `${level}`,
          data: rows.map(() => level),
          borderColor: MUTED,
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
        })),
      ],
    },
    options: chartOptions(0, 100),
  });
}

function chartOptions(min, max) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: MUTED, font: { family: 'IBM Plex Mono', size: 11 }, boxWidth: 14 } },
    },
    scales: {
      x: { ticks: { color: MUTED, maxTicksLimit: 6, font: { family: 'IBM Plex Mono', size: 10 } }, grid: { color: GRID } },
      y: {
        min, max,
        ticks: { color: MUTED, font: { family: 'IBM Plex Mono', size: 10 } },
        grid: { color: GRID },
      },
    },
  };
}

async function runAnalysis() {
  if (!currentTicker) return;

  runBtn.disabled = true;
  runStatus.textContent = 'thinking…';
  verdictBox.hidden = true;

  try {
    const useLlm = llmToggle.checked;
    const res = await fetch(`/api/predict/${encodeURIComponent(currentTicker)}?llm=${useLlm}`, { method: 'POST' });
    const data = await res.json();

    if (!data.ok) {
      showError(data.error || 'Analysis failed.');
      return;
    }

    renderVerdict(data.prediction);
    runStatus.textContent = '';
  } catch (err) {
    showError('Something went wrong running the analysis.');
  } finally {
    runBtn.disabled = false;
  }
}

function renderVerdict(pred) {
  const signalEl = document.getElementById('verdict-signal');
  const signalClass = pred.signal.toLowerCase();
  signalEl.textContent = pred.signal;
  signalEl.className = 'verdict-signal ' + signalClass;

  document.getElementById('confidence-value').textContent = pred.confidence;
  const fillEl = document.getElementById('confidence-fill');
  fillEl.style.width = pred.confidence + '%';
  fillEl.className = 'confidence-fill ' + signalClass;

  const list = document.getElementById('signal-list');
  list.innerHTML = '';
  pred.signals.forEach(s => {
    const li = document.createElement('li');
    li.className = s.score > 0 ? 'pos' : s.score < 0 ? 'neg' : '';
    li.innerHTML = `<span class="signal-name">${s.name}:</span> ${s.reason}`;
    list.appendChild(li);
  });

  document.getElementById('narrative').textContent = pred.narrative;
  verdictBox.hidden = false;
}

lookupForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const ticker = tickerInput.value.trim();
  if (ticker) lookupTicker(ticker);
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const ticker = chip.dataset.ticker;
    tickerInput.value = ticker;
    lookupTicker(ticker);
  });
});

runBtn.addEventListener('click', runAnalysis);
