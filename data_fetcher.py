
import pandas as pd
import yfinance as yf


def resolve_ticker(query: str) -> str | None:
    """
    Turn a loose query - a company name ("nvidia"), a partial name, or an
    already-correct ticker ("AAPL") - into a real ticker symbol.

    Returns None if nothing reasonable was found.
    """
    query = query.strip()
    if not query:
        return None

    try:
        results = yf.Search(query, max_results=8).quotes
    except Exception:
        results = []

    if not results:
        return None

    # Exact ticker match wins outright (e.g. user typed "AAPL" or "tcs.ns").
    for r in results:
        symbol = r.get("symbol", "")
        if symbol.upper() == query.upper():
            return symbol

    # Otherwise prefer actual equities over ETFs/indices/futures/options.
    equities = [r for r in results if r.get("quoteType") == "EQUITY"]
    pool = equities or results
    return pool[0].get("symbol")


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Download historical price data for a ticker.

    Parameters
    ----------
    ticker : str
        Stock symbol, e.g. "AAPL", "TCS.NS", "RELIANCE.NS".
    period : str
        How far back to fetch: "6mo", "1y", "2y", "5y", "max", etc.
    interval : str
        Candle size: "1d", "1wk", "1mo".

    Returns
    -------
    pd.DataFrame
        Indexed by date, columns: Open, High, Low, Close, Volume.
    """
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)

    if df is None or df.empty:
        raise ValueError(
            f"No data returned for '{ticker}'. Check the symbol "
            f"(Indian tickers usually need a suffix, e.g. 'INFY.NS')."
        )

    # yfinance sometimes returns MultiIndex columns for a single ticker -
    # flatten them so downstream code can just use df['Close'] etc.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()
    return df


def get_company_info(ticker: str) -> dict:
    """
    Fetch a small snippet of company/fundamental info (best-effort).
    Some fields may be missing depending on the ticker/exchange.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}

    return {
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "pe_ratio": info.get("trailingPE", "N/A"),
        "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
    }
