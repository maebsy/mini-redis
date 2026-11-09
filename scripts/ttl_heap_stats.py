"""측정 스크립트 A-2: TTL 힙이 얼마나 자주 재구성되는가.

Store._maybe_compact_ttl_heap 은 힙 크기가 64 를 넘고 살아있는 TTL 키의 2배를 넘으면
힙을 다시 만든다(stale 항목 제거). 같은 키에 EXPIRE 를 반복하거나 DEL/SET 으로 TTL 을
무효화하면 stale 항목이 쌓이는데, 이 스크립트는 그 재구성 빈도를 공개 API 만으로 측정한다.

    python3 scripts/ttl_heap_stats.py

재구성 감지: expire() 호출 전후의 ttl_heap_size 를 비교해, 호출 뒤 크기가
(호출 전 크기 + 1) 보다 작으면 그 호출에서 재구성이 일어난 것으로 본다.

워크로드
  (a) 반복 갱신: K 개 키를 R 번 라운드로빈으로 EXPIRE (K=1000/10000, R=1/5/20)
  (b) EXPIRE 후 절반 DEL, 남은 키 다시 EXPIRE 를 반복
  (c) EXPIRE 후 SET 덮어쓰기(= TTL 무효화) 반복
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_redis.store import Store  # noqa: E402


class FakeClock:
    """잠들지 않는 가짜 시계. now 를 직접 올려도 되지만 여기선 고정값이면 충분하다."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Stats:
    def __init__(self, store):
        self.store = store
        self.expire_calls = 0
        self.rebuilds = 0
        self.peak_heap = 0
        self.peak_live = 0

    def expire(self, key, seconds):
        before = self.store.ttl_heap_size
        self.store.expire(key, seconds)
        after = self.store.ttl_heap_size
        self.expire_calls += 1
        if after < before + 1:      # 늘어나지 않았으면 재구성이 일어난 것
            self.rebuilds += 1
        if after > self.peak_heap:
            self.peak_heap = after
            self.peak_live = self.store.ttl_key_count


def workload_repeat(k, r):
    """(a) K 개 키를 R 번 라운드로빈으로 EXPIRE."""
    store = Store(clock=FakeClock())
    keys = ["k{}".format(i) for i in range(k)]
    for key in keys:
        store.set(key, "v")
    st = Stats(store)
    for _ in range(r):
        for key in keys:
            st.expire(key, 10_000)
    return st


def workload_del_half():
    """(b) EXPIRE 후 남은 키 절반을 DEL, 남은 키 다시 EXPIRE 를 반복."""
    k = 10_000
    store = Store(clock=FakeClock())
    keys = ["k{}".format(i) for i in range(k)]
    for key in keys:
        store.set(key, "v")
    st = Stats(store)
    remaining = keys
    while len(remaining) > 2:
        for key in remaining:
            st.expire(key, 10_000)
        half = len(remaining) // 2
        for key in remaining[:half]:
            store.delete(key)
        remaining = remaining[half:]
    return st


def workload_set_overwrite():
    """(c) EXPIRE 후 SET 덮어쓰기(TTL 무효화) 를 반복해 stale 항목을 쌓는다."""
    k = 10_000
    rounds = 5
    store = Store(clock=FakeClock())
    keys = ["k{}".format(i) for i in range(k)]
    for key in keys:
        store.set(key, "v")
    st = Stats(store)
    for key in keys:              # 최초 EXPIRE
        st.expire(key, 10_000)
    for _ in range(rounds):
        for key in keys:          # SET 덮어쓰기 → TTL 무효화, 힙에 stale 잔류
            store.set(key, "v2")
        for key in keys:          # 다시 EXPIRE
            st.expire(key, 10_000)
    return st


def row(name, st, total_ms):
    calls = st.expire_calls
    per_rebuild = round(calls / st.rebuilds, 1) if st.rebuilds else "-"
    peak_ratio = round(st.peak_heap / st.peak_live, 2) if st.peak_live else "-"
    us = round(total_ms * 1000 / calls, 2) if calls else "-"
    return [name, calls, st.rebuilds, per_rebuild, st.peak_heap, peak_ratio,
            st.store.ttl_heap_size, round(total_ms, 1), us]


def main():
    header = ["workload", "EXPIRE calls", "rebuilds", "calls/rebuild", "peak heap",
              "peak/live", "final heap", "total ms", "µs/EXPIRE"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))

    specs = []
    for k in (1_000, 10_000):
        for r in (1, 5, 20):
            specs.append(("(a) K={} R={}".format(k, r), lambda k=k, r=r: workload_repeat(k, r)))
    specs.append(("(b) del-half 반복", workload_del_half))
    specs.append(("(c) set 덮어쓰기", workload_set_overwrite))

    for name, fn in specs:
        t0 = time.perf_counter()
        st = fn()
        total_ms = (time.perf_counter() - t0) * 1000
        print("| " + " | ".join(str(v) for v in row(name, st, total_ms)) + " |")

    print()
    print("Python {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
