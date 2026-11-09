"""측정 스크립트 B-1: used_memory 공식 밖에 있는 자료구조 오버헤드.

체크리스트 4-3 ("used_memory 에 자료구조 오버헤드까지 포함하면?")에 답하기 위한 근거 데이터를 만든다.

    python3 scripts/memory_overhead.py            # 1천 / 1만 / 10만 건
    python3 scripts/memory_overhead.py 50000      # 원하는 크기 추가

측정 항목
1) tracemalloc 으로 잰 실제 할당량 vs used_memory(키+값 바이트) — 엔트리당 오버헤드
2) 엔트리 하나를 이루는 객체별 크기 (sys.getsizeof)
3) 과제 예시(maxmemory 30, user:1~3)를 "키 + 값 + C" 모델로 바꾸면 결과가 어떻게 달라지는가
"""

import os
import sys
import tracemalloc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mini_redis.store as store_mod  # noqa: E402
from mini_redis.store import OutOfMemoryError, Store  # noqa: E402
from mini_redis.structures.linked_list import DoublyLinkedList  # noqa: E402


def measure(n):
    """N 개 엔트리를 넣는 동안 할당된 바이트를 잰다 (키/값 문자열 생성은 측정 밖에서)."""
    keys = ["user:{}".format(i) for i in range(n)]
    values = ["value-{}".format(i) for i in range(n)]
    tracemalloc.start()
    base, _ = tracemalloc.get_traced_memory()
    store = Store()
    for k, v in zip(keys, values):
        store.set(k, v)
    traced, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    structures = traced - base
    strings = sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in zip(keys, values))
    return store, structures, peak - base, strings


def breakdown(store):
    """엔트리 하나를 이루는 객체들의 크기 (CPython, sys.getsizeof)."""
    key = "user:12345"
    value = "value-12345"
    entry = store._data._find_node(next(iter(store._data))).data   # 해시맵 체인의 (key, value) 묶음
    s_entry = entry.value                                          # Store 의 _Entry
    chain_node = store._data._find_node(entry.key)
    hm = store._data
    used, _, _ = hm.chain_stats()
    n = hm.size()
    bucket_list = DoublyLinkedList()
    ptr = 8 if sys.maxsize > 2 ** 32 else 4
    rows = [
        ("Store._Entry (__slots__ 5개)", sys.getsizeof(s_entry), 1),
        ("LRU 리스트 Node (__slots__ 3개)", sys.getsizeof(s_entry.lru_node), 1),
        ("해시맵 체인 Node (__slots__ 3개)", sys.getsizeof(chain_node), 1),
        ("해시맵 _Entry (key, value 묶음)", sys.getsizeof(entry), 1),
        ("버킷 DoublyLinkedList + 센티널 2개 (사용 버킷마다)",
         sys.getsizeof(bucket_list) + 2 * sys.getsizeof(bucket_list._head), used / n),
        ("버킷 배열 칸 (capacity × 포인터)", ptr, hm.capacity / n),
        ("키 str 객체 헤더 (\"{}\")".format(key), sys.getsizeof(key) - len(key), 1),
        ("값 str 객체 헤더 (\"{}\")".format(value), sys.getsizeof(value) - len(value), 1),
    ]
    return rows


def mission_example(c):
    """size = key + value + C 모델로 과제 예시를 재생한다 (entry_size 를 잠시 바꿔 끼움)."""
    original = store_mod.entry_size
    store_mod.entry_size = lambda k, v: len(k.encode("utf-8")) + len(v.encode("utf-8")) + c
    try:
        store = Store()
        store.set_maxmemory(30)
        steps = []
        for k, v in (("user:1", "Alice"), ("user:2", "Bob"), ("user:3", "Charlie")):
            try:
                store.set(k, v)
                steps.append(str(store.used_memory))
            except OutOfMemoryError:
                steps.append("OOM")
        remaining = sorted(store.keys())
        return steps, store.evicted_keys, remaining, store.used_memory
    finally:
        store_mod.entry_size = original


def main():
    sizes = [1_000, 10_000, 100_000] + [int(a) for a in sys.argv[1:]]
    print("## 1) 실제 할당량 vs used_memory\n")
    print("| N | used_memory (키+값) | 자료구조 할당 (tracemalloc) | 엔트리당 자료구조 | 키·값 str 객체 포함 엔트리당 | 배수 (전체 / used_memory) |")
    print("|---|---|---|---|---|---|")
    last = None
    per_entry = 0
    for n in sizes:
        store, structures, _peak, strings = measure(n)
        per_entry = structures / n
        total = structures + strings
        print("| {:,} | {:,} B | {:,} B | {:.0f} B | {:.0f} B | {:.1f}× |".format(
            n, store.used_memory, structures, per_entry, total / n, total / store.used_memory))
        last = store

    print("\n## 2) 엔트리 하나의 구성 (sys.getsizeof, N = {:,})\n".format(last.dbsize()))
    print("| 객체 | 크기 | 엔트리당 개수 | 엔트리당 바이트 |")
    print("|---|---|---|---|")
    total = 0.0
    for name, size, count in breakdown(last):
        total += size * count
        print("| {} | {} B | {:.2f} | {:.0f} B |".format(name, size, count, size * count))
    print("| **합계** | | | **{:.0f} B** |".format(total))

    print("\n## 3) 과제 예시를 다른 메모리 모델로 재생 (maxmemory 30)\n")
    print("| 모델 | SET user:1 후 | SET user:2 후 | SET user:3 후 | evicted_keys | 남은 키 |")
    print("|---|---|---|---|---|---|")
    for c in (0, 16, 48, int(round(per_entry))):
        steps, evicted, remaining, _used = mission_example(c)
        label = "키+값 (현재)" if c == 0 else "키+값+{}".format(c)
        print("| {} | {} | {} | {} | {} | {} |".format(
            label, steps[0], steps[1], steps[2], evicted, ", ".join(remaining) or "(없음)"))

    print("\nPython {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
