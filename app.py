

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, render_template, request

from agent import StockPredictionAgent
from data_fetcher import resolve_ticker

app = Flask(__name__)

_agent_cache: dict[str, StockPredictionAgent] = {}


def _get_agent(raw_query: str) -> StockPredictionAgent:
    """
    Accepts either a ticker ("AAPL") or a company name ("nvidia") and
    returns a loaded agent, resolving the name to a real ticker first.
    """
    query = raw_query.strip()
    resolved = resolve_ticker(query) or query.upper()

    if resolved not in _agent_cache:
        agent = StockPredictionAgent(resolved)
        agent.load_data()
        _agent_cache[resolved] = agent
    return _agent_cache[resolved]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stock/<ticker>")
def stock_overview(ticker):
    """Company info + recent price/indicator history for the chart."""
    try:
        agent = _get_agent(ticker)
        return jsonify({
            "ok": True,
            "info": agent.info_summary(),
            "chart": agent.chart_data(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/predict/<ticker>", methods=["POST"])
def predict(ticker):
    """Run the rule-based agent (optionally with an LLM narrative)."""
    use_llm = request.args.get("llm", "false").lower() == "true"
    try:
        agent = _get_agent(ticker)
        agent.use_llm = use_llm
        prediction = agent.analyze()
        return jsonify({"ok": True, "prediction": prediction.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
