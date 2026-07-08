import pandas as pd
from pathlib import Path
from flask import Blueprint, jsonify, send_file
import subprocess
import threading

chart_us_bp = Blueprint("chart_analysis_us", __name__)

_BASE = Path(__file__).parent.parent.parent
CHARTS_DIR = _BASE / "charts"
OUTPUT_CSV = _BASE / "gemini_chart_analysis.csv"
MAIN_SCRIPT = _BASE / "main_us.py"

_state = {
    "running": False,
    "status": "idle",
    "total": 100,
    "current": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}

def _run_script():
    global _state
    try:
        # Run the standalone main_us.py script
        process = subprocess.Popen(["python", str(MAIN_SCRIPT)], cwd=str(_BASE))
        process.wait()
        _state["status"] = "done"
    except Exception as e:
        _state["status"] = "error"
        _state["error"] = str(e)
    finally:
        _state["running"] = False

@chart_us_bp.post("/run")
def run_analysis():
    global _state
    if _state["running"]:
        return jsonify({"ok": False, "message": "이미 분석 중입니다."}), 409
    
    _state["running"] = True
    _state["status"] = "running"
    threading.Thread(target=_run_script, daemon=True).start()
    return jsonify({"ok": True, "message": "US 차트 분석을 시작했습니다."})

@chart_us_bp.get("/status")
def get_status():
    snap = dict(_state)
    snap["pct"] = 50 if snap["running"] else (100 if snap["status"] == "done" else 0)
    return jsonify(snap)

@chart_us_bp.get("/results")
def get_results():
    if not OUTPUT_CSV.exists():
        return jsonify({"results": [], "summary": {"BUY": 0, "HOLD": 0, "SELL": 0}})
    
    df = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
    df["confidence"] = pd.to_numeric(df.get("confidence", 0), errors="coerce").fillna(0)
    df = df.sort_values("confidence", ascending=False)
    
    summary = {}
    if "signal" in df.columns:
        summary = df["signal"].str.upper().value_counts().to_dict()
    
    # ensure proper english keys for React bindings
    results = df.rename(columns={"ticker": "종목코드"}).to_dict(orient="records")
    for row in results:
        row["종목명"] = row.get("종목코드")
        row["시장"] = "S&P 500"
    
    return jsonify({"results": results, "summary": summary})

@chart_us_bp.get("/charts/<path:ticker>")
def get_chart(ticker: str):
    path = CHARTS_DIR / f"{ticker}.png"
    if path.exists():
        return send_file(str(path), mimetype="image/png")
    return jsonify({"error": "차트를 찾을 수 없습니다."}), 404

@chart_us_bp.get("/stock-summary/<ticker>")
def stock_summary(ticker: str):
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        end = datetime.today()
        start = end - timedelta(days=365)
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        
        if df.empty:
            return jsonify({"error": "데이터를 찾을 수 없습니다."}), 404

        # Clean columns if multi-index
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.droplevel("Ticker")
            except:
                df.columns = df.columns.droplevel(1)

        history = []
        for idx, row in df.iterrows():
            history.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            })
        
        return jsonify({
            "ticker": ticker,
            "price_history": history
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
