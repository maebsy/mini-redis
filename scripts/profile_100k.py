"""측정 스크립트 B-2: 10만 건 규모에서 시간이 어디에 쓰이는가.

체크리스트 4-2 ("데이터가 10만 건으로 늘면 병목은?")의 원인을 단계별로 나눠 잰다.
benchmark.py 가 "얼마나 빠른가"를 본다면, 이 스크립트는 "어디서 느려지는가"를 본다.

    python3 scripts/profile_100k.py           # N = 100,000
    python3 scripts/profile_100k.py 200000    # N 변경

측정 항목
* FNV-1a 해시 한 번의 비용 (짧은 키 / 64바이트 키) — 순수 파이썬 바이트 반복
* SET 전체 시간과 리사이즈가 일어난 put 하나하나의 시간 (가장 큰 것들)
* GET 전체 / 한 번당
* KEYS 를 세 단계로 분리: 수집(store.keys) · 출력 문자열 만들기(replies.render) · 쓰기(os.devnull)
* N 개 키 동시 만료: expire_due_keys 한 번
* N 개 키 저장 후 메모리 (tracemalloc)
"""

import os
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_redis import replies as R  # noqa: E402
from mini_redis.store import Store  # noqa: E402
from mini_redis.structures.hashmap import fnv1a_64  # noqa: E402


class StepClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def per_call_us(fn, arg, repeat=200_000):
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn(arg)
    return (time.perf_counter() - t0) * 1e6 / repeat


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    rows = []

    short_key, long_key = "user:12345", "k" * 64
    rows.append(("FNV-1a 1회 (키 10바이트)", "{:.2f} µs".format(per_call_us(fnv1a_64, short_key))))
    rows.append(("FNV-1a 1회 (키 64바이트)", "{:.2f} µs".format(per_call_us(fnv1a_64, long_key))))

    clock = StepClock()
    store = Store(clock=clock)
    hm = store.hashmap
    keys = ["user:{}".format(i) for i in range(n)]
    resizes = []
    t0 = time.perf_counter()
    for k in keys:
        before = hm.capacity
        s = time.perf_counter()
        store.set(k, "v")
        if hm.capacity != before:
            resizes.append((time.perf_counter() - s, before, hm.capacity))
    set_total = time.perf_counter() - t0
    resize_total = sum(r[0] for r in resizes)
    rows.append(("SET {:,}건 전체".format(n), "{:,.0f} ms ({:,.0f} ops/s)".format(set_total * 1e3, n / set_total)))
    rows.append(("  그중 리사이즈 {}회 합계".format(len(resizes)),
                 "{:,.0f} ms ({:.0f}%)".format(resize_total * 1e3, resize_total / set_total * 100)))
    for dt, a, b in sorted(resizes, reverse=True)[:3]:
        rows.append(("  리사이즈 {:,} → {:,} 버킷".format(a, b), "{:,.1f} ms (SET 한 번)".format(dt * 1e3)))

    t0 = time.perf_counter()
    for k in keys:
        store.get(k)
    get_total = time.perf_counter() - t0
    rows.append(("GET {:,}건 전체".format(n), "{:,.0f} ms ({:.2f} µs/회)".format(get_total * 1e3, get_total * 1e6 / n)))

    t0 = time.perf_counter()
    arr = store.keys()
    t1 = time.perf_counter()
    text = R.render(R.Array(R.BulkString(k) for k in arr))
    t2 = time.perf_counter()
    with open(os.devnull, "w", encoding="utf-8") as out:
        out.write(text + "\n")
    t3 = time.perf_counter()
    rows.append(("KEYS ① 수집 (store.keys)", "{:,.1f} ms".format((t1 - t0) * 1e3)))
    rows.append(("KEYS ② 출력 문자열 만들기 (render)", "{:,.1f} ms ({:,.1f} MB)".format((t2 - t1) * 1e3, len(text.encode("utf-8")) / 1e6)))
    rows.append(("KEYS ③ 쓰기 (/dev/null)", "{:,.1f} ms".format((t3 - t2) * 1e3)))

    for k in keys:
        store.expire(k, 10)
    clock.now += 11
    t0 = time.perf_counter()
    removed = store.expire_due_keys()
    rows.append(("동시 만료 {:,}개 (expire_due_keys 1회)".format(removed),
                 "{:,.0f} ms".format((time.perf_counter() - t0) * 1e3)))
    # 메모리는 시간 측정과 따로 잰다 (tracemalloc 이 켜져 있으면 SET 이 몇 배 느려진다)
    tracemalloc.start()
    mem_store = Store()
    for k in keys:
        mem_store.set(k, "v")
    mem, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rows.append(("메모리 ({:,}건 저장 직후, tracemalloc)".format(n), "{:,.1f} MB (엔트리당 {:,.0f} B)".format(mem / 1e6, mem / n)))

    print("| 항목 | 측정값 |")
    print("|---|---|")
    for name, value in rows:
        print("| {} | {} |".format(name, value))
    print("\nPython {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
