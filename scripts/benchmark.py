"""간단한 성능 측정 스크립트.

체크리스트 항목 4 ("데이터가 10만 건으로 늘어나면 병목은?")에 답하기 위한 근거 데이터를 만든다.

    python scripts/benchmark.py            # 1천 / 1만 / 10만 건
    python scripts/benchmark.py 200000     # 원하는 크기 추가

측정 항목
* SET / GET 처리량 (ops/sec), 가장 느린 SET 한 번의 지연(리사이즈 순간)
* 해시맵 리사이즈 횟수, 최종 capacity, 최장 체인 길이
* maxmemory 를 건 상태에서 LRU 제거 처리량
* KEYS (전체 순회) 소요 시간 — O(n) 명령의 비용
* TTL 대량 만료(active expiration) 소요 시간
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_redis.store import Store  # noqa: E402


class StepClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def bench(n: int) -> list:
    clock = StepClock()
    store = Store(clock=clock)
    keys = ["user:{}".format(i) for i in range(n)]

    worst = 0.0
    t0 = time.perf_counter()
    for k in keys:
        s0 = time.perf_counter()
        store.set(k, "value")
        elapsed = time.perf_counter() - s0
        if elapsed > worst:
            worst = elapsed  # 가장 느린 SET 한 번 = 리사이즈(전체 재해싱)가 일어난 순간
    t_set = time.perf_counter() - t0

    t0 = time.perf_counter()
    for k in keys:
        store.get(k)
    t_get = time.perf_counter() - t0

    hm = store.hashmap
    _, longest, avg = hm.chain_stats()

    t0 = time.perf_counter()
    count = len(store.keys())
    t_keys = time.perf_counter() - t0
    assert count == n

    for k in keys:
        store.expire(k, 1)
    clock.now = 2.0
    t0 = time.perf_counter()
    expired = store.expire_due_keys()
    t_expire = time.perf_counter() - t0
    assert expired == n

    lru = Store(clock=clock)
    lru.set_maxmemory(n // 10 * 15)  # 대략 10% 만 남도록
    t0 = time.perf_counter()
    for k in keys:
        lru.set(k, "value")
    t_lru = time.perf_counter() - t0

    return [
        n,
        int(n / t_set),
        round(worst * 1000, 1),
        int(n / t_get),
        hm.resize_count,
        hm.capacity,
        longest,
        round(avg, 2),
        round(t_keys * 1000, 1),
        round(t_expire * 1000, 1),
        int(n / t_lru),
        lru.evicted_keys,
    ]


def main() -> None:
    sizes = [1_000, 10_000, 100_000] + [int(a) for a in sys.argv[1:]]
    header = ["N", "SET ops/s", "max SET ms", "GET ops/s", "resize", "capacity", "max chain", "avg chain",
              "KEYS ms", "expire-all ms", "SET+LRU ops/s", "evicted"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for n in sizes:
        print("| " + " | ".join(str(v) for v in bench(n)) + " |")
    print()
    print("Python {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
