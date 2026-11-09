"""측정 스크립트 A-1: FNV-1a 해시의 버킷 분포 품질.

체크리스트 "해시 함수를 직접 설계했는가 / 분포가 고른가" 에 답하기 위한 근거 데이터를 만든다.

    python3 scripts/hash_distribution.py               # 1천 / 1만 / 10만 건
    python3 scripts/hash_distribution.py 5000          # 원하는 크기 추가

각 키 집합을 실제 HashMap 에 넣어(실제 리사이즈 정책이 capacity 를 정하도록) 버킷 배열에서
직접 지표를 계산한다.

* capacity, load factor α = size / capacity
* 빈 버킷 비율(측정) vs 기대값 e^(−α)
* 사용 버킷 평균 체인 길이(측정) vs 기대값 α / (1 − e^(−α))
* 최장 체인 길이
* 카이제곱 Σ(c − α)² / α 를 (capacity − 1) 로 나눈 값 (≈1.0 이면 균일 분포)

마지막으로 일부러 나쁜 해시(UTF-8 바이트 합) 를 sequential 키에 적용한 baseline 을 함께 찍어
'분포가 나쁘면 어떻게 보이는지' 를 대비한다.
"""

import math
import os
import random
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_redis.structures.hashmap import HashMap, fnv1a_64  # noqa: E402


def weak_hash(key):
    """일부러 나쁜 해시: UTF-8 바이트 값의 단순 합. 값 범위가 좁아 분포가 뭉친다."""
    return sum(key.encode("utf-8"))


def build_keys(rng, n):
    """측정용 키 집합 4종을 만든다. random 집합은 중복을 피해 정확히 n 개를 보장한다."""
    sequential = ["user:{}".format(i) for i in range(n)]
    numeric = ["{}".format(i) for i in range(n)]
    korean = ["사용자:{}".format(i) for i in range(n)]
    alphabet = string.ascii_lowercase + string.digits
    randset = set()
    while len(randset) < n:
        randset.add("".join(rng.choice(alphabet) for _ in range(8)))
    return [
        ("user:{i}", sequential),
        ("{i}", numeric),
        ("random8", sorted(randset)),
        ("사용자:{i}", korean),
    ]


def metrics(keys, hash_func):
    """키들을 실제 HashMap 에 넣고 버킷 배열에서 분포 지표를 뽑는다."""
    hm = HashMap(hash_func=hash_func)
    for k in keys:
        hm.put(k, 1)
    capacity = hm.capacity
    size = len(hm)
    alpha = size / capacity

    empty = 0
    longest = 0
    chi = 0.0
    for bucket in hm._buckets:  # 버킷 배열 직접 관찰 (디버그 목적)
        c = 0 if bucket is None else len(bucket)
        if c == 0:
            empty += 1
        elif c > longest:
            longest = c
        chi += (c - alpha) ** 2 / alpha
    used = capacity - empty

    empty_meas = empty / capacity
    empty_exp = math.exp(-alpha)
    avg_meas = (size / used) if used else 0.0
    denom = 1.0 - math.exp(-alpha)
    avg_exp = (alpha / denom) if denom > 0 else 0.0
    chi_norm = chi / (capacity - 1) if capacity > 1 else 0.0

    return [capacity, round(alpha, 3), round(empty_meas, 3), round(empty_exp, 3),
            round(avg_meas, 3), round(avg_exp, 3), longest, round(chi_norm, 3)]


def main():
    sizes = [1_000, 10_000, 100_000] + [int(a) for a in sys.argv[1:]]
    header = ["key set", "N", "capacity", "α", "empty meas", "empty e^(−α)",
              "avg chain", "avg exp", "longest", "chi²/(cap−1)"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))

    rng = random.Random(42)
    for n in sizes:
        for label, keys in build_keys(rng, n):
            row = [label, n] + metrics(keys, fnv1a_64)
            print("| " + " | ".join(str(v) for v in row) + " |")

    # baseline: 일부러 나쁜 해시 (바이트 합) 를 sequential 키에 적용
    for n in sizes:
        keys = ["user:{}".format(i) for i in range(n)]
        row = ["baseline(weak)", n] + metrics(keys, weak_hash)
        print("| " + " | ".join(str(v) for v in row) + " |")

    print()
    print("Python {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
