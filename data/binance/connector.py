import ccxt
import pandas as pd
import os

class BinanceConnector:
    def __init__(self):
        # Read API keys from env
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })

    def get_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV from Binance."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            return pd.DataFrame()

    def get_top_tokens(self, limit: int = 15) -> list:
        """Fetch hottest trending coins from CoinGecko + top market cap to guarantee high volatility trades."""
        import requests
        
        try:
            # Fetch Trending Coins from CoinGecko (Free API, no key needed)
            response = requests.get('https://api.coingecko.com/api/v3/search/trending', timeout=5)
            trending_data = response.json()
            
            cg_symbols = []
            for item in trending_data.get('coins', []):
                sym = item['item']['symbol'].upper()
                if sym not in ['USDT', 'USDC']: # Exclude stablecoins
                    cg_symbols.append(f"{sym}/USDT")
            
            # Use top 25 highly volatile and fast-moving altcoins on Binance Futures
            fast_altcoins = [
                "WIF/USDT", "DOGE/USDT", "SUI/USDT", "NEAR/USDT", "SOL/USDT",
                "PEPE/USDT", "SHIB/USDT", "AVAX/USDT", "APT/USDT", "FET/USDT",
                "INJ/USDT", "SEI/USDT", "TIA/USDT", "RENDER/USDT", "GALA/USDT",
                "OP/USDT", "ARB/USDT", "LINK/USDT", "ENA/USDT", "JUP/USDT",
                "BONK/USDT", "FLOKI/USDT", "POPCAT/USDT", "FTM/USDT", "TON/USDT"
            ]
            
            combined = fast_altcoins + cg_symbols
            # Remove duplicates while preserving order
            unique_pairs = []
            heavy_coins = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
            for pair in dict.fromkeys(combined):
                if pair not in heavy_coins:
                    unique_pairs.append(pair)
            
            return unique_pairs[:limit]
            
        except Exception as e:
            print(f"CoinGecko Error, falling back: {e}")
            return [
                "WIF/USDT", "DOGE/USDT", "SUI/USDT", "NEAR/USDT", "SOL/USDT",
                "PEPE/USDT", "SHIB/USDT", "AVAX/USDT", "APT/USDT", "FET/USDT",
                "INJ/USDT", "SEI/USDT", "TIA/USDT", "RENDER/USDT", "GALA/USDT",
                "OP/USDT", "ARB/USDT", "LINK/USDT", "ENA/USDT", "JUP/USDT"
            ][:limit]

    def execute_trade(self, symbol: str, side: str, amount_usdt: float, current_price: float, tp_price: float = None, sl_price: float = None, api_key: str = None, api_secret: str = None) -> dict:
        """Execute a REAL live market order on Binance with Auto-Close (TP/SL)."""
        use_key = api_key or self.api_key
        use_secret = api_secret or self.api_secret
        
        if not use_key or not use_secret:
            return {"status": "error", "message": "Binance API keys not provided. Please enter them in the UI."}
            
        try:
            exec_exchange = self.exchange
            if api_key and api_secret:
                exec_exchange = ccxt.binance({
                    'apiKey': use_key,
                    'secret': use_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'future',
                        'adjustForTimeDifference': True,
                        'recvWindow': 60000
                    }
                })
                exec_exchange.load_time_difference()
                
            # Load markets to get precision and limits
            exec_exchange.load_markets()
            
            # Apply 20x Leverage for High-Frequency Micro Scalping
            leverage = 20
            try:
                exec_exchange.set_leverage(leverage, symbol)
            except Exception as e:
                pass # Ignore if already set or fails
                
            # Total notional position size = margin * leverage
            leveraged_usdt = amount_usdt * leverage
            
            # Calculate raw coin amount
            raw_coin_amount = leveraged_usdt / current_price
            
            # Format to Binance exact precision requirements
            coin_amount = float(exec_exchange.amount_to_precision(symbol, raw_coin_amount))
            
            if coin_amount <= 0:
                return {"status": "error", "message": f"Trade size ${amount_usdt} (with {leverage}x leverage) is too small for {symbol}. Try a cheaper coin or increase amount."}
                
            # Place real entry market order
            order = exec_exchange.create_order(
                symbol=symbol,
                type='market',
                side=side.lower(),
                amount=coin_amount
            )
            
            # Place TP and SL orders to auto-close
            if tp_price and sl_price:
                try:
                    tp_price_formatted = float(exec_exchange.price_to_precision(symbol, tp_price))
                    sl_price_formatted = float(exec_exchange.price_to_precision(symbol, sl_price))
                    
                    # Inverse side for closing the position
                    close_side = 'sell' if side.lower() == 'buy' else 'buy'
                    
                    # Stop Loss
                    exec_exchange.create_order(
                        symbol=symbol,
                        type='STOP_MARKET',
                        side=close_side,
                        amount=coin_amount,
                        params={'stopPrice': sl_price_formatted, 'closePosition': True}
                    )
                    
                    # Take Profit
                    exec_exchange.create_order(
                        symbol=symbol,
                        type='TAKE_PROFIT_MARKET',
                        side=close_side,
                        amount=coin_amount,
                        params={'stopPrice': tp_price_formatted, 'closePosition': True}
                    )
                except Exception as aux_e:
                    print(f"Failed to place TP/SL: {aux_e}")
                    
            return {"status": "success", "order": order}
        except Exception as e:
            return {"status": "error", "message": f"Binance Execution Failed: {str(e)}"}

    def get_balance(self, api_key: str = None, api_secret: str = None) -> dict:
        """Fetch current USDT balance to verify account connection."""
        use_key = api_key or self.api_key
        use_secret = api_secret or self.api_secret
        
        if not use_key or not use_secret:
            return {"status": "error", "message": "Keys missing"}
            
        try:
            exec_exchange = ccxt.binance({
                'apiKey': use_key,
                'secret': use_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000
                }
            })
            exec_exchange.load_time_difference()
            balance = exec_exchange.fetch_balance()
            usdt_free = balance.get('USDT', {}).get('free', 0.0)
            return {"status": "success", "usdt_balance": round(usdt_free, 2)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_open_position(self, api_key: str = None, api_secret: str = None) -> dict:
        """Fetch currently open Futures positions from Binance."""
        use_key = api_key or self.api_key
        use_secret = api_secret or self.api_secret
        
        if not use_key or not use_secret:
            return {"status": "error", "message": "Keys missing"}
            
        try:
            exec_exchange = ccxt.binance({
                'apiKey': use_key,
                'secret': use_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000
                }
            })
            exec_exchange.load_time_difference()
            positions = exec_exchange.fetch_positions()
            # Filter only active positions (where amount != 0)
            active_positions = [p for p in positions if abs(float(p.get('info', {}).get('positionAmt', 0))) > 0]
            
            if active_positions:
                pos = active_positions[0]
                symbol = pos.get('symbol')
                amt = float(pos.get('info', {}).get('positionAmt', 0))
                entry_price = float(pos.get('entryPrice', 0))
                unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                side = "LONG" if amt > 0 else "SHORT"
                
                return {
                    "status": "success", 
                    "active": True, 
                    "trade": {
                        "symbol": symbol,
                        "side": side,
                        "entry": entry_price,
                        "pnl": round(unrealized_pnl, 4)
                    }
                }
            else:
                return {"status": "success", "active": False}
        except Exception as e:
            return {"status": "error", "message": str(e)}

binance_connector = BinanceConnector()
