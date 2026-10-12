"""체이닝(Separate Chaining) 방식 해시맵.

동작 개요
---------
1. **해시 함수** ``fnv1a_64(key)``
   문자열 → UTF-8 바이트 → 바이트마다 ``XOR`` 후 소수(FNV prime) 곱셈 → 64비트 정수.
   파이썬 내장 ``hash()`` 는 사용하지 않는다(프로세스마다 시드가 바뀌어 재현성이 없고,
   과제 요구사항이 "해시 함수 직접 설계"이기 때문).
2. **인덱스 계산** ``hash & (capacity - 1)``
   버킷 수를 항상 2의 거듭제곱으로 유지하므로 ``%`` 대신 비트 마스크로 빠르게 계산한다.
3. **충돌 해결 = 체이닝**
   각 버킷은 이중 연결 리스트(``DoublyLinkedList``)이고, 같은 인덱스로 모인
   엔트리(key, value)를 리스트에 이어 붙인다. (요구사항 권장: 이중 연결 리스트 재사용)
4. **리사이즈**
   ``size / capacity > 0.75`` 가 되면 버킷 수를 2배로 늘리고 모든 엔트리를 재배치(rehash)한다.
   버킷 수가 바뀌면 ``hash & (capacity - 1)`` 결과도 바뀌기 때문에 단순 복사가 아니라
   전체 재해싱이 필요하다.

시간 복잡도: put/get/remove/contains 평균 O(1), 최악 O(n)(모든 키가 한 버킷에 몰릴 때).
"""

from typing import Any, Callable, Iterator, Optional, Tuple

from .dynamic_array import DynamicArray
from .linked_list import DoublyLinkedList, Node

# FNV-1a 64-bit 상수 (Fowler–Noll–Vo 해시 표준 값)
FNV_OFFSET_BASIS_64 = 0xCBF29CE484222325
FNV_PRIME_64 = 0x100000001B3
MASK_64 = (1 << 64) - 1


def fnv1a_64(key: str) -> int:
    """FNV-1a 64비트 해시.

    각 바이트를 먼저 XOR 로 섞고(1a 변형) 그다음 소수를 곱해 비트를 퍼뜨린다.
    곱셈 결과는 ``& MASK_64`` 로 64비트에 고정한다(파이썬 int 는 무한 정밀도이므로).

    >>> fnv1a_64("") == FNV_OFFSET_BASIS_64
    True
    """
    if not isinstance(key, str):
        raise TypeError("HashMap key must be str, got {}".format(type(key).__name__))
    h = FNV_OFFSET_BASIS_64
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * FNV_PRIME_64) & MASK_64
    return h


class _Entry:
    """버킷(연결 리스트) 노드에 담기는 key-value 쌍."""

    __slots__ = ("key", "value")

    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


def _next_power_of_two(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


class HashMap:
    """문자열 키를 사용하는 체이닝 해시맵."""

    DEFAULT_CAPACITY = 8
    MAX_LOAD_FACTOR = 0.75

    __slots__ = ("_capacity", "_buckets", "_size", "_hash", "_resize_count")

    def __init__(self, capacity: int = DEFAULT_CAPACITY, hash_func: Callable[[str], int] = fnv1a_64) -> None:
        self._capacity = _next_power_of_two(max(1, capacity))
        # 고정 길이 버킷 테이블. 각 칸은 None(빈 버킷) 또는 DoublyLinkedList.
        self._buckets = [None] * self._capacity
        self._size = 0
        self._hash = hash_func
        self._resize_count = 0

    # ------------------------------------------------------------ 내부 헬퍼
    def _index(self, key: str) -> int:
        """해시값을 버킷 인덱스로 변환. capacity 가 2^k 이므로 하위 k 비트만 취한다."""
        return self._hash(key) & (self._capacity - 1)

    def _find_node(self, key: str) -> Optional[Node]:
        """키가 들어 있는 체인 노드를 찾는다. 버킷 내부만 선형 탐색."""
        bucket = self._buckets[self._index(key)]
        if bucket is None:
            return None
        for node in bucket.iter_nodes():
            if node.data.key == key:
                return node
        return None

    def _resize(self, new_capacity: int) -> None:
        """버킷 수를 ``new_capacity`` 로 바꾸고 모든 엔트리를 재해싱한다. O(n)

        절차
        1) 새 버킷 테이블을 만든다(기존 크기의 2배).
        2) 기존 버킷을 순서대로 돌며 각 엔트리의 인덱스를 **새 capacity 기준으로 다시 계산**한다.
        3) 새 테이블의 해당 버킷 체인 뒤에 붙인다.
        """
        old_buckets = self._buckets
        self._capacity = new_capacity
        self._buckets = [None] * new_capacity
        for bucket in old_buckets:
            if bucket is None:
                continue
            for entry in bucket:
                idx = self._index(entry.key)
                target = self._buckets[idx]
                if target is None:
                    target = DoublyLinkedList()
                    self._buckets[idx] = target
                target.insert_back(entry)
        self._resize_count += 1

    # ------------------------------------------------------------ 공개 API
    def put(self, key: str, value: Any) -> bool:
        """키-값 저장. 새 키면 True, 기존 키 덮어쓰기면 False 를 반환한다."""
        node = self._find_node(key)
        if node is not None:
            node.data.value = value
            return False
        idx = self._index(key)
        bucket = self._buckets[idx]
        if bucket is None:
            bucket = DoublyLinkedList()
            self._buckets[idx] = bucket
        bucket.insert_back(_Entry(key, value))
        self._size += 1
        if self._size / self._capacity > self.MAX_LOAD_FACTOR:
            self._resize(self._capacity * 2)
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """키의 값을 반환한다. 없으면 ``default``."""
        node = self._find_node(key)
        return default if node is None else node.data.value

    def remove(self, key: str) -> bool:
        """키를 삭제한다. 삭제했으면 True, 없었으면 False."""
        idx = self._index(key)
        bucket = self._buckets[idx]
        if bucket is None:
            return False
        for node in bucket.iter_nodes():
            if node.data.key == key:
                bucket.remove_node(node)
                if bucket.is_empty():
                    self._buckets[idx] = None  # 빈 체인은 해제
                self._size -= 1
                return True
        return False

    def contains(self, key: str) -> bool:
        return self._find_node(key) is not None

    def keys(self) -> DynamicArray:
        """전체 키 목록(순서 보장 없음)을 동적 배열로 반환한다. O(n + capacity)"""
        result = DynamicArray()
        for key in self:
            result.append(key)
        return result

    def size(self) -> int:
        return self._size

    def clear(self) -> None:
        self._capacity = self.DEFAULT_CAPACITY
        self._buckets = [None] * self._capacity
        self._size = 0

    # ------------------------------------------------------------ 순회/통계
    def items(self) -> Iterator[Tuple[str, Any]]:
        for bucket in self._buckets:
            if bucket is None:
                continue
            for entry in bucket:
                yield entry.key, entry.value

    def values(self) -> Iterator[Any]:
        for _, value in self.items():
            yield value

    def __iter__(self) -> Iterator[str]:
        for key, _ in self.items():
            yield key

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def load_factor(self) -> float:
        return self._size / self._capacity

    @property
    def resize_count(self) -> int:
        return self._resize_count

    def chain_stats(self) -> Tuple[int, int, float]:
        """(사용 중인 버킷 수, 최장 체인 길이, 사용 버킷 평균 체인 길이)"""
        used = 0
        longest = 0
        for bucket in self._buckets:
            if bucket is None:
                continue
            used += 1
            if len(bucket) > longest:
                longest = len(bucket)
        avg = (self._size / used) if used else 0.0
        return used, longest, avg

    def __repr__(self) -> str:
        pairs = ", ".join("{!r}: {!r}".format(k, v) for k, v in self.items())
        return "HashMap({" + pairs + "})"
