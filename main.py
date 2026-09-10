

import argparse

from dotenv import load_dotenv
load_dotenv()  

import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt

from agent import StockPredictionAgent


def print_report(agent: StockPredictionAgent, prediction) -> None:
    info = agent.info
    print("=" * 60)
    print(f"  STOCK PREDICTION AGENT REPORT - {prediction.ticker}")
    print("=" * 60)
    print(f"Company     : {info.get('name', 'N/A')}")
    print(f"Sector      : {info.get('sector', 'N/A')}")
    print(f"Last Price  : {prediction.last_price}")
    print(f"52w Range   : {info.get('52w_low', 'N/A')} - {info.get('52w_high', 'N/A')}")
    print("-" * 60)
    print(f"SIGNAL      : {prediction.signal}")
    print(f"CONFIDENCE  : {prediction.confidence}%")
    print(f"SCORE       : {prediction.total_score} (range roughly -8 to +8)")
    print("-" * 60)
    print("Reasoning:")
    print(prediction.narrative)
    print("=" * 60)
    print("Note: This is a technical-indicator based estimate for learning")
    print("purposes only. It is NOT financial advice.")


def save_chart(agent: StockPredictionAgent, out_path: str) -> None:
    df = agent.df.tail(120)  # last ~6 months of daily data for readability

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(df.index, df["Close"], label="Close", color="black", linewidth=1.2)
    ax1.plot(df.index, df["SMA20"], label="SMA20", linestyle="--")
    ax1.plot(df.index, df["SMA50"], label="SMA50", linestyle="--")
    ax1.fill_between(df.index, df["BB_lower"], df["BB_upper"], color="gray", alpha=0.15, label="Bollinger Band")
    ax1.set_title(f"{agent.ticker} - Price & Trend")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.plot(df.index, df["RSI14"], color="purple", linewidth=1.0)
    ax2.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax2.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax2.set_title("RSI (14)")
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Simple stock prediction agent")
    parser.add_argument("ticker", type=str, help="Stock symbol, e.g. AAPL or INFY.NS")
    parser.add_argument("--period", type=str, default="1y", help="History window: 6mo, 1y, 2y, 5y (default: 1y)")
    parser.add_argument("--interval", type=str, default="1d", help="Candle interval: 1d, 1wk (default: 1d)")
    parser.add_argument("--llm", action="store_true", help="Use an LLM (Claude) to write the explanation")
    parser.add_argument("--no-chart", action="store_true", help="Skip saving the chart image")
    parser.add_argument("--out", type=str, default="chart.png", help="Path to save the chart image")
    args = parser.parse_args()

    agent = StockPredictionAgent(args.ticker, period=args.period, interval=args.interval, use_llm=args.llm)
    agent.load_data()
    prediction = agent.analyze()

    print_report(agent, prediction)

    if not args.no_chart:
        save_chart(agent, args.out)
        print(f"\nChart saved to: {args.out}")


if __name__ == "__main__":
    main()
