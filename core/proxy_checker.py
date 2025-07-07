# core/proxy_checker.py

import asyncio
from typing import List, Tuple
from aiohttp import ClientSession, TCPConnector
from aiohttp_socks import ProxyConnector

# Тип: (ip, port, user, password, type)
# type: "http", "socks5"
Proxy = Tuple[str, int, str, str, str]

async def check_proxy(proxy: Proxy) -> Tuple[Proxy, bool]:
    ip, port, user, password, proxy_type = proxy

    if proxy_type == "socks5":
        auth = f"{user}:{password}@" if user else ""
        proxy_url = f"socks5://{auth}{ip}:{port}"
        connector = ProxyConnector.from_url(proxy_url)
    elif proxy_type == "http":
        auth = f"{user}:{password}@" if user else ""
        proxy_url = f"http://{auth}{ip}:{port}"
        connector = TCPConnector(ssl=False)
    else:
        return proxy, False

    try:
        async with ClientSession(connector=connector) as session:
            async with session.get("http://httpbin.org/ip", proxy=proxy_url, timeout=5) as resp:
                if resp.status == 200:
                    return proxy, True
    except Exception:
        pass

    return proxy, False


async def check_proxies(proxies: List[Proxy]) -> List[Proxy]:
    tasks = [check_proxy(proxy) for proxy in proxies]
    results = await asyncio.gather(*tasks)

    return [proxy for proxy, is_ok in results if is_ok]


# Локальный тест
if __name__ == "__main__":
    sample_proxies = [
        ("127.0.0.1", 8080, "", "", "http"),
        ("127.0.0.1", 1080, "", "", "socks5"),
    ]

    async def run():
        working = await check_proxies(sample_proxies)
        print("✅ Рабочие прокси:")
        for p in working:
            print(p)

    asyncio.run(run())
