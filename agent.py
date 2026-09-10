
import os
from dataclasses import dataclass, field

import pandas as pd

from data_fetcher import fetch_history, get_company_info
from indicators import compute_all


@dataclass
class SignalScore:
    name: str
    score: int          # -2 (strong bearish) .. +2 (strong bullish)
    reason: str

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "reason": self.reason}


@dataclass
class Prediction:
    ticker: str
    last_price: float
    signal: str                 # BUY / HOLD / SELL
    confidence: float            # 0-100
    total_score: int
    signals: list = field(default_factory=list)   # list[SignalScore]
    narrative: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "last_price": self.last_price,
            "signal": self.signal,
            "confidence": self.confidence,
            "total_score": self.total_score,
            "signals": [s.to_dict() for s in self.signals],
            "narrative": self.narrative,
        }


class StockPredictionAgent:
    def __init__(self, ticker: str, period: str = "1y", interval: str = "1d", use_llm: bool = False):
        self.ticker = ticker.upper()
        self.period = period
        self.interval = interval
        self.use_llm = use_llm
        self.df: pd.DataFrame | None = None
        self.info: dict = {}

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def load_data(self):
        raw = fetch_history(self.ticker, self.period, self.interval)
        self.df = compute_all(raw)
        self.info = get_company_info(self.ticker)
        return self.df

    def chart_data(self, days: int = 150) -> list[dict]:
        """
        Return recent price + indicator history as plain dicts,
        ready to hand to a frontend charting library (e.g. Chart.js).
        """
        if self.df is None:
            self.load_data()

        recent = self.df.tail(days)
        records = []
        for idx, row in recent.iterrows():
            records.append({
                "date": idx.strftime("%Y-%m-%d"),
                "close": None if pd.isna(row["Close"]) else round(float(row["Close"]), 2),
                "sma20": None if pd.isna(row["SMA20"]) else round(float(row["SMA20"]), 2),
                "sma50": None if pd.isna(row["SMA50"]) else round(float(row["SMA50"]), 2),
                "rsi": None if pd.isna(row["RSI14"]) else round(float(row["RSI14"]), 2),
            })
        return records

    def info_summary(self) -> dict:
        """Company info + latest price snapshot, for the overview panel."""
        if self.df is None:
            self.load_data()

        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest
        change = float(latest["Close"] - prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100 if prev["Close"] else 0.0

        return {
            "ticker": self.ticker,
            "name": self.info.get("name", self.ticker),
            "sector": self.info.get("sector", "N/A"),
            "market_cap": self.info.get("market_cap", "N/A"),
            "pe_ratio": self.info.get("pe_ratio", "N/A"),
            "52w_high": self.info.get("52w_high", "N/A"),
            "52w_low": self.info.get("52w_low", "N/A"),
            "last_price": round(float(latest["Close"]), 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(latest["Volume"]) if pd.notna(latest.get("Volume")) else "N/A",
        }

    # ------------------------------------------------------------------ #
    # Rule-based scoring - this is the "brain" of the agent
    # ------------------------------------------------------------------ #
    def _score_trend(self, latest, prev) -> SignalScore:
        close, sma20, sma50 = latest["Close"], latest["SMA20"], latest["SMA50"]

        if pd.isna(sma50):
            return SignalScore("Trend (SMA)", 0, "Not enough history for 50-day average yet.")

        if close > sma20 > sma50:
            return SignalScore("Trend (SMA)", 2, "Price is above both the 20-day and 50-day averages (uptrend).")
        if close > sma50:
            return SignalScore("Trend (SMA)", 1, "Price is above the 50-day average.")
        if close < sma20 < sma50:
            return SignalScore("Trend (SMA)", -2, "Price is below both the 20-day and 50-day averages (downtrend).")
        return SignalScore("Trend (SMA)", -1, "Price is below the 50-day average.")

    def _score_momentum_rsi(self, latest) -> SignalScore:
        rsi = latest["RSI14"]
        if pd.isna(rsi):
            return SignalScore("Momentum (RSI)", 0, "Not enough history for RSI yet.")
        if rsi >= 70:
            return SignalScore("Momentum (RSI)", -1, f"RSI is {rsi:.1f} - overbought, a pullback is possible.")
        if rsi <= 30:
            return SignalScore("Momentum (RSI)", 1, f"RSI is {rsi:.1f} - oversold, a bounce is possible.")
        if rsi > 50:
            return SignalScore("Momentum (RSI)", 1, f"RSI is {rsi:.1f} - momentum leans positive.")
        return SignalScore("Momentum (RSI)", -1 if rsi < 45 else 0, f"RSI is {rsi:.1f} - momentum leans neutral/negative.")

    def _score_macd(self, latest, prev) -> SignalScore:
        macd, sig = latest["MACD"], latest["MACD_signal"]
        prev_macd, prev_sig = prev["MACD"], prev["MACD_signal"]

        if pd.isna(macd) or pd.isna(sig):
            return SignalScore("MACD", 0, "Not enough history for MACD yet.")

        crossed_up = prev_macd <= prev_sig and macd > sig
        crossed_down = prev_macd >= prev_sig and macd < sig

        if crossed_up:
            return SignalScore("MACD", 2, "MACD just crossed above its signal line (fresh bullish crossover).")
        if crossed_down:
            return SignalScore("MACD", -2, "MACD just crossed below its signal line (fresh bearish crossover).")
        if macd > sig:
            return SignalScore("MACD", 1, "MACD is above its signal line (bullish).")
        return SignalScore("MACD", -1, "MACD is below its signal line (bearish).")

    def _score_bollinger(self, latest) -> SignalScore:
        close, upper, lower = latest["Close"], latest["BB_upper"], latest["BB_lower"]
        if pd.isna(upper) or pd.isna(lower):
            return SignalScore("Bollinger Bands", 0, "Not enough history for Bollinger Bands yet.")
        if close >= upper:
            return SignalScore("Bollinger Bands", -1, "Price is at/above the upper band - stretched to the upside.")
        if close <= lower:
            return SignalScore("Bollinger Bands", 1, "Price is at/below the lower band - stretched to the downside.")
        return SignalScore("Bollinger Bands", 0, "Price is trading inside its normal range.")

    def _score_volatility(self, latest) -> SignalScore:
        vol = latest["Volatility20"]
        if pd.isna(vol):
            return SignalScore("Volatility", 0, "Not enough history for volatility yet.")
        vol_pct = vol * 100
        if vol_pct > 3:
            return SignalScore("Volatility", 0, f"20-day volatility is high (~{vol_pct:.1f}%/day) - lower confidence in any signal.")
        return SignalScore("Volatility", 0, f"20-day volatility is moderate (~{vol_pct:.1f}%/day).")

    def analyze(self) -> Prediction:
        if self.df is None:
            self.load_data()

        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest

        signals = [
            self._score_trend(latest, prev),
            self._score_momentum_rsi(latest),
            self._score_macd(latest, prev),
            self._score_bollinger(latest),
            self._score_volatility(latest),
        ]

        total_score = sum(s.score for s in signals)

        # Map total score (-8..+8 roughly) to a decision.
        if total_score >= 3:
            decision = "BUY"
        elif total_score <= -3:
            decision = "SELL"
        else:
            decision = "HOLD"

        # Confidence: how strongly the signals agree, scaled to 0-100.
        max_possible = 8
        confidence = min(100.0, (abs(total_score) / max_possible) * 100)

        # High volatility should temper confidence a bit.
        vol = latest.get("Volatility20", 0)
        if pd.notna(vol) and vol * 100 > 3:
            confidence *= 0.8

        prediction = Prediction(
            ticker=self.ticker,
            last_price=round(float(latest["Close"]), 2),
            signal=decision,
            confidence=round(confidence, 1),
            total_score=total_score,
            signals=signals,
        )

        if self.use_llm:
            prediction.narrative = self._llm_explain(prediction)
        else:
            prediction.narrative = self._template_explain(prediction)

        return prediction

    # ------------------------------------------------------------------ #
    # Explanations
    # ------------------------------------------------------------------ #
    def _template_explain(self, prediction: Prediction) -> str:
        bullets = "\n".join(f"  - {s.name}: {s.reason}" for s in prediction.signals)
        return (
            f"Based on current technicals, the combined signal for {prediction.ticker} is "
            f"{prediction.signal} (confidence {prediction.confidence}%).\n{bullets}"
        )

    def _llm_explain(self, prediction: Prediction) -> str:
        """
        Ask an LLM (Google Gemini, free tier) to turn the already-computed
        signals into a short, readable summary. The LLM is NOT given
        permission to change the signal or invent numbers - it only
        explains what's already there. Falls back to the template
        explanation if no API key is set or the call fails for any reason.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return self._template_explain(prediction) + "\n\n(Set GEMINI_API_KEY to get an LLM-written summary.)"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            signal_lines = "\n".join(f"- {s.name} (score {s.score:+d}): {s.reason}" for s in prediction.signals)

            prompt = (
                f"You are a cautious equity research assistant. A rule-based system already "
                f"analyzed {prediction.ticker} and reached this decision - do not change it or "
                f"invent any numbers not given below.\n\n"
                f"Last price: {prediction.last_price}\n"
                f"Decision: {prediction.signal}\n"
                f"Confidence: {prediction.confidence}%\n"
                f"Signals:\n{signal_lines}\n\n"
                f"Write a short (4-6 sentence) plain-English summary of WHY the decision makes "
                f"sense given these signals, and end with one sentence reminding the reader this "
                f"is not financial advice."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=400,
                    http_options=types.HttpOptions(timeout=20_000),  # milliseconds - never hang forever
                ),
            )
            return response.text.strip()

        except Exception as e:
            return self._template_explain(prediction) + f"\n\n(LLM summary unavailable: {e})"
