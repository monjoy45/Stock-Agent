# Simple Stock Prediction Agent

A small, readable stock-analysis agent — inspired by the StockAgent research
project you shared, but scaled way down to an intermediate, single-user tool.

**What it does NOT do (on purpose):**
- No multi-agent simulated market, no order-matching engine, no fake exchange.
- No promise of an exact future price.

**What it DOES do:**
- Pulls real historical price data for any ticker (via `yfinance`).
- Computes standard technical indicators: SMA20/50, RSI14, MACD, Bollinger Bands, 20-day volatility.
- Runs a transparent, rule-based scoring system to reach a **BUY / HOLD / SELL** stance with a confidence %.
- Optionally asks Google Gemini (free API tier) to turn that already-decided result into a
  plain-English explanation (the LLM explains the decision, it never invents the numbers or
  overrides the rules).
- Saves a price + RSI chart as a PNG.

## Project layout

```
stock_agent/
├── data_fetcher.py     # downloads OHLCV data + basic company info
├── indicators.py        # SMA, EMA, RSI, MACD, Bollinger Bands, volatility
├── agent.py               # scoring logic + optional LLM narrative
├── main.py                 # CLI entry point (report + chart)
├── app.py                  # Flask web app (landing page + API)
├── templates/index.html
├── static/style.css
├── static/script.js
├── .env.example
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

If you want the LLM-written explanation instead of the plain template, get a free Gemini API
key from [Google AI Studio](https://aistudio.google.com/apikey) (no credit card needed), then:

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your key in:

```
GEMINI_API_KEY=your_actual_key_here
```

That's it — `main.py` loads `.env` automatically, so you don't need to set the environment
variable by hand or re-set it every time you open a new terminal. `.env` is already listed in
`.gitignore` so you won't accidentally commit your key if you push this to GitHub.

(Without a key, it just prints a clear rule-based explanation — everything still works.)

## Usage

```bash
python main.py AAPL
python main.py TCS.NS --period 6mo --llm
python main.py RELIANCE.NS --period 2y --no-chart
```

Indian tickers usually need the exchange suffix, e.g. `.NS` for NSE or `.BO` for BSE.

## Web landing page (optional)

Prefer clicking over typing commands? Run the same agent behind a small web dashboard:

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. Type a ticker *or a company name* (e.g. "Nvidia" resolves to `NVDA`) — or click one of the quick-pick chips. You'll see the company overview (including volume), a price chart with SMA20/SMA50, an RSI chart, and a "Run analysis" button. Clicking it calls the exact same `StockPredictionAgent`
used by `main.py` and shows the BUY/HOLD/SELL verdict, confidence bar, and per-indicator
reasoning. Check "Explain with Gemini" before running to get the LLM-written narrative instead
of the plain-text one (needs `GEMINI_API_KEY` set in `.env`, same as the CLI).

This is a local dev server (`debug=True`) meant for running on your own machine — it isn't
set up for public deployment as-is.

### Sample output

```
============================================================
  STOCK PREDICTION AGENT REPORT - AAPL
============================================================
Company     : Apple Inc.
Sector      : Technology
Last Price  : 227.5
52w Range   : 164.08 - 237.49
------------------------------------------------------------
SIGNAL      : BUY
CONFIDENCE  : 62.5%
SCORE       : 5 (range roughly -8 to +8)
------------------------------------------------------------
Reasoning:
  - Trend (SMA): Price is above both the 20-day and 50-day averages (uptrend).
  - Momentum (RSI): RSI is 58.3 - momentum leans positive.
  - MACD: MACD is above its signal line (bullish).
  - Bollinger Bands: Price is trading inside its normal range.
  - Volatility: 20-day volatility is moderate (~1.2%/day).
============================================================
Note: This is a technical-indicator based estimate for learning
purposes only. It is NOT financial advice.
```

## How the scoring works (the "agent brain")

Each indicator votes a small score from -2 (strongly bearish) to +2 (strongly bullish).
The votes are summed into a total score, which maps to a decision:

| Total score | Decision |
|---|---|
| ≥ +3 | BUY |
| -2 to +2 | HOLD |
| ≤ -3 | SELL |

Confidence is just `|score| / 8 * 100`, reduced a bit further if 20-day volatility is high
(a noisy stock deserves less confidence even if the indicators agree).

This is intentionally simple and inspectable — you can open `agent.py` and see exactly
why any given decision was reached, which is the main thing a "black box" price predictor
can't offer you.

## Ideas to extend it (left as an exercise)

- Add a news-headline sentiment score as one more vote in `analyze()`.
- Backtest the rule set against historical data to see its hit rate.
- Add more indicators (ATR, Stochastic Oscillator) as additional `_score_*` methods.
- Swap the CLI for a small Streamlit dashboard.

## Disclaimer

This tool is for learning about technical analysis and Python, not for making real
trading decisions. Markets are influenced by far more than historical price patterns.
