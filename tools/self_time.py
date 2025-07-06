import requests
from typing import List, Dict
import json, os
import time
from datetime import datetime, timedelta
import concurrent.futures

class BinanceFuturesUtil:
    FUTURES_BASE_URL = "https://fapi.binance.com"
    COINGECKO_URL = "https://api.coingecko.com/api/v3"

    @staticmethod
    def get_coingecko_market_caps(
            pages: int = 7,
            cache_path: str = "coingecko_cache.json",
            cache_ttl: int = 60 * 60 * 24 * 7  # 7天缓存
    ) -> Dict[str, float]:
        """
        从 CoinGecko 获取 top 市值加密货币的市值，返回 dict，key 是币种符号（大写），value 是市值（USD）
        带简单缓存，避免频繁请求
        """
        now = time.time()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if now - cache.get("timestamp", 0) < cache_ttl:
                    return cache.get("data", {})
            except Exception:
                pass

        market_caps = {}
        per_page = 250  # CoinGecko 最大每页250个
        for page in range(1, pages + 1):
            url = f"{BinanceFuturesUtil.COINGECKO_URL}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
            }
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                for coin in data:
                    symbol = coin.get("symbol", "").upper()
                    market_cap = coin.get("market_cap")
                    if symbol and market_cap:
                        market_caps[symbol] = market_cap
            except Exception as e:
                print(f"Error fetching CoinGecko data page {page}: {e}")
                break

        # 写缓存
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now, "data": market_caps}, f)
        except Exception as e:
            print(f"Error writing cache: {e}")

        return market_caps

    @staticmethod
    def get_usdt_perpetual_symbols() -> List[str]:
        """获取所有 USDT 永续合约的合约标识符，例如 BTCUSDT"""
        url = f"{BinanceFuturesUtil.FUTURES_BASE_URL}/fapi/v1/exchangeInfo"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        symbols = [s['symbol'] for s in data['symbols'] if s['symbol'].endswith("USDT") and s['contractType'] == "PERPETUAL"]
        return symbols

    @staticmethod
    def get_daily_volume(symbol: str, date_str: str) -> float:
        """
        获取指定合约某一天的成交额（以USDT计），使用1d K线数据
        date_str 格式: "20250603"
        """
        date = datetime.strptime(date_str, "%Y%m%d")
        start_ts = int(date.timestamp() * 1000)
        end_ts = int((date + timedelta(days=1)).timestamp() * 1000)

        url = f"{BinanceFuturesUtil.FUTURES_BASE_URL}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": "1d",
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1
        }
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        klines = resp.json()
        if not klines:
            return 0.0

        # K线返回格式 [Open time, Open, High, Low, Close, Volume, ...]
        # 成交额 = 收盘价 * 成交量
        close_price = float(klines[0][4])
        volume = float(klines[0][5])
        return close_price * volume

    @staticmethod
    def _check_symbol_volume_ratio(symbol: str, base: str, market_cap: float, date_str: str, days: int,
                                   threshold: float):
        """
        检查指定 symbol 在 date_str 前 days 天内是否有成交额/市值 > threshold
        成功返回包含 symbol 信息的 dict，否则返回 None
        """
        print(f"_check_symbol_volume_ratio: {symbol}, market_cap: {market_cap}, date_str: {date_str}")
        for i in range(days):
            check_date = (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=i)).strftime("%Y%m%d")
            try:
                volume_usdt = BinanceFuturesUtil.get_daily_volume(symbol, check_date)
            except Exception as e:
                print(f"Error fetching daily volume for {symbol} on {check_date}: {e}")
                volume_usdt = 0

            ratio = volume_usdt / market_cap
            if ratio > threshold:
                # 获取最新行情简化信息
                try:
                    ticker_url = f"{BinanceFuturesUtil.FUTURES_BASE_URL}/fapi/v1/ticker/24hr?symbol={symbol}"
                    resp = requests.get(ticker_url)
                    resp.raise_for_status()
                    ticker = resp.json()
                    price = float(ticker.get("lastPrice", 0))
                    change = float(ticker.get("priceChangePercent", 0))
                except Exception as e:
                    print(f"Error fetching ticker for {symbol}: {e}")
                    price = 0
                    change = 0

                tag = f"{base}/USDT:USDT"
                return {
                    "symbol": symbol,
                    "volume_usdt": volume_usdt,
                    "market_cap": market_cap,
                    "ratio": ratio,
                    "price": price,
                    "change": change,
                    "tag": tag
                }
        return None

    @staticmethod
    def get_high_volume_to_marketcap_contracts(
            date_str: str = None,
            days: int = 1,
            threshold: float = 0.7,
            limit: int = 200
    ) -> List[Dict]:
        if not date_str:
            date_str = datetime.utcnow().strftime("%Y%m%d")

        cg_market_caps = BinanceFuturesUtil.get_coingecko_market_caps()
        symbols = BinanceFuturesUtil.get_usdt_perpetual_symbols()
        exclude_symbols = {"BTC", "ETH"}

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for symbol in symbols:
                base = symbol.replace("USDT", "").upper()
                if base in exclude_symbols:
                    continue
                market_cap = cg_market_caps.get(base)
                if not market_cap or market_cap == 0:
                    continue
                futures.append(executor.submit(
                    BinanceFuturesUtil._check_symbol_volume_ratio,
                    symbol, base, market_cap, date_str, days, threshold
                ))

            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res is not None:
                    results.append(res)

        results.sort(key=lambda x: x["ratio"], reverse=True)
        return results[:limit]


def backtesting_filter(date_str: str = "20250603", days: int = 3, threshold: float = 0.7):
    filtered = BinanceFuturesUtil.get_high_volume_to_marketcap_contracts(
        date_str=date_str,
        days=days,
        threshold=threshold
    )

    tags = []
    for idx, item in enumerate(filtered, start=1):
        print(f"{idx}. {item['symbol']} | Volume: {item['volume_usdt']:.2f} USDT | Price: {item['price']} | "
              f"Change: {item['change']}% | Ratio: {item['ratio']:.2f}")
        print(item['tag'])
        tags.append(item['tag'])

    print("\nJSON Result:")
    print(json.dumps(tags, indent=2))

    # 打印日期范围
    start_date = datetime.strptime(date_str, "%Y%m%d")
    end_date = start_date + timedelta(days=days)
    print(f"\nDate Range: {date_str}-{end_date.strftime('%Y%m%d')}")



if __name__ == "__main__":
    backtesting_filter(date_str="20250603", days=14)