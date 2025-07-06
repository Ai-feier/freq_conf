import requests
from typing import List, Dict
import json, os
import time


class BinanceFuturesUtil:
    FUTURES_BASE_URL = "https://fapi.binance.com"
    SPOT_BASE_URL = "https://api.binance.com"
    COINGECKO_URL = "https://api.coingecko.com/api/v3"

    @staticmethod
    def get_all_usdt_contracts() -> List[Dict]:
        """获取所有 USDT 永续合约的 24h ticker 数据"""
        url = f"{BinanceFuturesUtil.FUTURES_BASE_URL}/fapi/v1/ticker/24hr"
        response = requests.get(url)
        response.raise_for_status()
        all_contracts = response.json()
        return [c for c in all_contracts if c["symbol"].endswith("USDT")]

    @staticmethod
    def get_coingecko_market_caps(
            pages: int = 7,
            cache_path: str = "coingecko_cache.json",
            cache_ttl: int = 60 * 60 * 168
    ) -> Dict[str, float]:
        """获取 CoinGecko 上币种的市值（symbol -> market_cap），带本地缓存"""
        # 判断缓存是否存在且未过期
        if os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            if time.time() - mtime < cache_ttl:
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        print(f"✅ 使用缓存数据: {cache_path}")
                        return json.load(f)
                except Exception as e:
                    print(f"⚠️ 读取缓存失败: {e}")

        # 如果缓存失效，则重新请求
        market_caps = {}
        for page in range(1, pages + 1):
            url = f"{BinanceFuturesUtil.COINGECKO_URL}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 250,
                "page": page,
                "sparkline": "false"
            }
            try:
                resp = requests.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                for item in data:
                    symbol = item["symbol"].upper()
                    market_caps[symbol] = item["market_cap"]
                time.sleep(1)  # Respect API rate limit
            except Exception as e:
                print(f"[Page {page}] Failed to fetch: {e}")

        if market_caps:
            # 保存到本地缓存
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(market_caps, f)
                    print(f"✅ 缓存已保存到: {cache_path}")
            except Exception as e:
                print(f"⚠️ 保存缓存失败: {e}")
            return market_caps
        else:
            # 如果请求全部失败，尝试回退使用已有缓存
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        print(f"⚠️ 使用过期缓存: {cache_path}")
                        return json.load(f)
                except Exception as e:
                    print(f"❌ 无法使用过期缓存: {e}")
            return {}  # 最终兜底为空

    @staticmethod
    def get_high_volume_to_marketcap_contracts(threshold: float = 0.7, limit: int = 200) -> List[Dict]:
        """过滤出 24h 成交量 > 市值 * threshold 的币种，排除 BTC 和 ETH"""
        contracts = BinanceFuturesUtil.get_all_usdt_contracts()
        cg_market_caps = BinanceFuturesUtil.get_coingecko_market_caps()

        exclude_symbols = {"BTC", "ETH"}  # 全局排除的币种

        result = []
        for c in contracts:
            symbol = c["symbol"]
            if not symbol.endswith("USDT"):
                continue
            base = symbol.replace("USDT", "").upper()

            # 排除 BTC 和 ETH
            if base in exclude_symbols:
                continue

            volume = float(c["quoteVolume"])
            price = float(c["lastPrice"])
            change = float(c["priceChangePercent"])
            tag = f"{base}/USDT:USDT"

            market_cap = cg_market_caps.get(base)
            if not market_cap or market_cap == 0:
                continue

            ratio = volume / market_cap
            if ratio >= threshold:
                result.append({
                    "symbol": symbol,
                    "volume_usdt": volume,
                    "market_cap": market_cap,
                    "ratio": ratio,
                    "price": price,
                    "change": change,
                    "tag": tag
                })

        # 排序
        sorted_result = sorted(result, key=lambda x: x["ratio"], reverse=True)
        return sorted_result[:limit]


def main():
    filtered = BinanceFuturesUtil.get_high_volume_to_marketcap_contracts(threshold=0.7)

    tags = []
    for idx, item in enumerate(filtered, start=1):
        print(f"{idx}. {item['symbol']} | Volume: {item['volume_usdt']:.2f} USDT | Price: {item['price']} | "
              f"Change: {item['change']}% | Ratio: {item['ratio']:.2f}")
        print(item['tag'])
        tags.append(item['tag'])

    print("\nJSON Result:")
    print(json.dumps(tags, indent=2))


if __name__ == "__main__":
    main()
