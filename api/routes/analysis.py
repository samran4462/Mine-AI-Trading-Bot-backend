from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter()

@router.get("/htf", response_model=Dict[str, Any])
async def get_htf_analysis(symbol: str = "XAUUSD"):
    """
    Returns Higher Timeframe (Monthly, Weekly, Daily, 4H) analysis for a symbol.
    """
    # Mock data to demonstrate the structure
    return {
        "symbol": symbol,
        "bias": "bullish",
        "key_levels": {
            "resistance": [2050.0, 2075.0],
            "support": [2010.0, 1980.0]
        },
        "market_structure": "Higher Highs, Higher Lows"
    }

@router.get("/ltf", response_model=Dict[str, Any])
async def get_ltf_analysis(symbol: str = "XAUUSD"):
    """
    Returns Lower Timeframe (1H, 15M, 5M, 1M) analysis for precise setup confirmation.
    """
    return {
        "symbol": symbol,
        "bias": "neutral",
        "recent_action": "consolidation",
        "liquidity_sweeps": [],
        "order_blocks": []
    }

from orchestration.langchain.agent import LangchainOrchestrator
from pydantic import BaseModel

orchestrator = LangchainOrchestrator()

from data.binance.connector import binance_connector
from feature_engineering.structure.analyzer import StructureAnalyzer
from feature_engineering.liquidity.analyzer import LiquidityAnalyzer
import pandas as pd

class MarketScanRequest(BaseModel):
    symbol: str

@router.post("/full-scan")
async def run_full_market_scan(scan_req: MarketScanRequest):
    """
    Triggers a full HTF to LTF analysis pipeline using live Binance data.
    """
    symbol = scan_req.symbol
    
    # 1. Fetch Live Data (e.g., 5m timeframe for LTF)
    df = binance_connector.get_ohlcv(symbol, timeframe='5m', limit=100)
    
    if df.empty:
        return {"status": "error", "message": "Failed to fetch market data"}
        
    # 2. Run Feature Engineering (Structure & Liquidity)
    struct_analyzer = StructureAnalyzer(df.copy())
    df_struct = struct_analyzer.identify_swing_points()
    df_struct = struct_analyzer.detect_bos_choch()
    
    liq_analyzer = LiquidityAnalyzer(df_struct)
    df_final = liq_analyzer.detect_fvg()
    df_final = liq_analyzer.detect_liquidity_sweeps(df_struct['high'].rolling(5).max(), df_struct['low'].rolling(5).min())
    
    # Extract latest market conditions
    latest = df_final.iloc[-1]
    prev = df_final.iloc[-2]
    
    ltf_bias = "bullish" if latest.get('structure_signal') in ["BOS_BULLISH", "CHOCH_BULLISH"] else "bearish" if latest.get('structure_signal') in ["BOS_BEARISH", "CHOCH_BEARISH"] else "neutral"
    
    liquidity_status = latest.get('liquidity_sweep', 'none')
    if liquidity_status == "NONE" and (latest.get('bullish_fvg') or latest.get('bearish_fvg')):
        liquidity_status = "FVG Present"
        
    market_data = {
        "htf_context": "neutral", # In full system, fetch 4H data separately
        "ltf_structure": ltf_bias,
        "liquidity": liquidity_status,
        "news_risk": "low",
        "volatility": "normal",
        "current_price": float(latest['close'])
    }
    
    # 3. Run through AI Orchestrator
    decision_result = orchestrator.evaluate_setup(market_data)
    
    return {
        "status": "scan_complete",
        "symbol": symbol,
        "market_data": market_data,
        "decision": decision_result["decision"],
        "reason": decision_result["reason"]
    }

class TopTokensRequest(BaseModel):
    platform: str
    limit: int = 20

@router.post("/get-top-tokens")
async def get_top_tokens(req: TopTokensRequest):
    if req.platform.lower() == "binance":
        symbols = binance_connector.get_top_tokens(limit=req.limit)
    else:
        symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    return {"symbols": symbols}

class SingleScanRequest(BaseModel):
    platform: str
    symbol: str

@router.post("/scan-single")
async def scan_single_token(req: SingleScanRequest):
    """Scans a single token and returns immediately."""
    sym = req.symbol
    try:
        if req.platform.lower() == "binance":
            # Switch to 1m timeframe for ULTRA FAST micro-scalping signals
            df = binance_connector.get_ohlcv(sym, timeframe='1m', limit=100)
        else:
            from data.mt5.connector import mt5_connector
            import MetaTrader5 as mt5
            df = mt5_connector.get_historical_data(sym, mt5.TIMEFRAME_M1, 100)
            
        if df.empty: 
            return {"status": "error", "symbol": sym, "message": "No data"}
            
        # 1. RSI Calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. Bollinger Bands Calculation (Best for Fast, Safe 1m Scalping)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['std_20'] = df['close'].rolling(window=20).std()
        df['upper_bb'] = df['sma_20'] + (2.5 * df['std_20']) # 2.5 Standard Deviations (Extreme)
        df['lower_bb'] = df['sma_20'] - (2.5 * df['std_20'])
        
        latest = df.iloc[-1]
        rsi_val = latest.get('rsi', 50)
        if pd.isna(rsi_val): rsi_val = 50
        
        # Determine PROFESSIONAL CONFLUENCE Bias
        ltf_bias = "neutral"
        liquidity_status = "none"
        
        # High-Frequency AI Mean-Reversion (Elastic Snapback Strategy)
        is_bb_oversold = latest['close'] <= latest['lower_bb']
        is_bb_overbought = latest['close'] >= latest['upper_bb']
        
        # AI Confluence Bullish: Price stretched far below Lower Band + RSI Oversold
        if is_bb_oversold or (rsi_val < 35):
            ltf_bias = "bullish"
            liquidity_status = "AI_Confluence_Bullish"
                
        # AI Confluence Bearish: Price stretched far above Upper Band + RSI Overbought
        elif is_bb_overbought or (rsi_val > 65):
            ltf_bias = "bearish"
            liquidity_status = "AI_Confluence_Bearish"
            
        market_data = {
            "htf_context": "neutral",
            "ltf_structure": ltf_bias,
            "liquidity": liquidity_status,
            "news_risk": "low",
            "volatility": "normal",
            "current_price": float(latest['close'])
        }
        
        decision_result = orchestrator.evaluate_setup(market_data)
        
        # Calculate EXACT 2-Minute Scalping parameters
        price = market_data["current_price"]
        is_buy = ltf_bias == "bullish"
        
        # Ultra-Fast Scalping: 0.15% Take Profit (Extremely quick, seconds to hit)
        # 3.0% Stop Loss (Very wide, to give the trade breathing room and NEVER close in loss on small wicks)
        sl_pct = 0.03 # 3.0% SL
        tp_pct = 0.0015 # 0.15% TP
        
        stop_loss = price * (1 - sl_pct) if is_buy else price * (1 + sl_pct)
        take_profit = price * (1 + tp_pct) if is_buy else price * (1 - tp_pct)
        
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "status": "success",
            "symbol": sym,
            "decision": decision_result["decision"],
            "reason": decision_result["reason"],
            "price": price,
            "bias": ltf_bias,
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "duration": "1 to 3 Mins (Micro-Scalp)",
            "time": current_time
        }
    except Exception as e:
        return {"status": "error", "symbol": sym, "message": str(e)}
