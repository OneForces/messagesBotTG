# core/proxy_checker.py

import asyncio
import aiohttp
from typing import List, Tuple

# Тип: (ip, port, user, password)
Proxy = Tuple[str, int, str, str]

async def check_proxy(session: aiohttp.ClientSession, proxy: Proxy) -> Tuple[Proxy, bool]:
    ip, port, user, password = proxy
    proxy_url = f"http://{user}:{password}@{ip}:{port}" if user else f"http://{ip}:{port}"

    try:
        async with session.get('http://httpbin.org/ip', proxy=proxy_url, timeout=5) as resp:
            if resp.status == 200:
                return proxy, True
    except Exception:
        pass
    return proxy, False


async def check_proxies(proxies: List[Proxy]) -> List[Proxy]:
    working_proxies = []
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)

    for proxy, is_ok in results:
        if is_ok:
            working_proxies.append(proxy)

    return working_proxies


# Пример локального запуска (для отладки):
if __name__ == "__main__":
    sample_proxies = [
        ("127.0.0.1", 8080, "", ""),
        ("user.proxy.com", 1080, "user", "pass"),
    ]

    async def run():
        good = await check_proxies(sample_proxies)
        print("Рабочие прокси:")
        for p in good:
            print(p)

    asyncio.run(run())
