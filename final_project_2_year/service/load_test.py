"""Простой обстрел сервиса GET /recommend из нескольких потоков.

    python service/load_test.py --url http://localhost:8000 --requests 2000 --threads 8

Id пользователей берутся случайно от 0 до 1.5 млн, так что попадаются и люди
с историей, и новые. Печатает запросы в секунду, перцентили времени и коды ответов.
"""

import argparse
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def one_request(base, user_id):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            f"{base}/recommend?user_id={user_id}", timeout=30
        ) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except OSError:
        status = "connection error"
    return status, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=2000)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    rng = random.Random(42)
    user_ids = [rng.randint(0, 1_500_000) for _ in range(args.requests)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        results = list(pool.map(lambda u: one_request(base, u), user_ids))
    total = time.perf_counter() - started

    latencies = sorted(sec for _, sec in results)
    codes = Counter(status for status, _ in results)

    def pct(q):
        return latencies[min(len(latencies) - 1, int(q * len(latencies)))] * 1000

    print(f"запросов: {len(results)}, потоков: {args.threads}, время: {total:.1f} c")
    print(f"запросов в секунду: {len(results) / total:.0f}")
    print(
        f"время ответа, мс: p50 {pct(0.5):.1f}, p95 {pct(0.95):.1f}, "
        f"p99 {pct(0.99):.1f}, max {latencies[-1] * 1000:.1f}"
    )
    print(f"коды ответов: {dict(codes)}")


if __name__ == "__main__":
    main()
