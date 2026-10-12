"""저장소 엔진: 해시맵 + LRU 리스트 + TTL 힙 + 메모리 회계.

세 자료구조가 하나의 키를 서로 다른 관점에서 추적한다.

========================  =====================================  ===================
구조                       역할                                    핵심 연산
========================  =====================================  ===================
``HashMap[key -> Entry]``  키로 엔트리를 O(1) 조회                  get/put/remove
``DoublyLinkedList``       사용 순서 (front=MRU, back=LRU)          move_to_front/remove_back
``MinHeap[(exp, key)]``    가장 빨리 만료될 키를 O(1)로 확인         peek/pop
========================  =====================================  ===================

Entry 는 자신의 LRU 노드(``lru_node``)를 들고 있다. 그래서
"해시맵으로 엔트리 찾기(O(1)) → 노드 핸들로 리스트에서 바로 이동(O(1))"이 가능하고,
이것이 **O(1) LRU** 의 핵심이다.

불변식 (모든 명령 실행 후 항상 성립)
1. ``used_memory == Σ(len(utf8(key)) + len(utf8(value)))``  (살아있는 엔트리 기준)
2. ``maxmemory > 0`` 이면 ``used_memory <= maxmemory``
3. 해시맵의 키 집합 == LRU 리스트의 키 집합
4. TTL 힙에는 오래된(stale) 항목이 남아 있을 수 있다 → 꺼낼 때 검증(lazy deletion)
"""

import math
import time
from typing import Callable, Optional

from .structures.dynamic_array import DynamicArray
from .structures.hashmap import HashMap
from .structures.linked_list import DoublyLinkedList, Node
from .structures.min_heap import MinHeap


class OutOfMemoryError(Exception):
    """단일 엔트리 크기가 maxmemory 를 넘어 저장할 수 없을 때 발생한다."""


class _Entry:
    """해시맵에 저장되는 값 묶음."""

    __slots__ = ("key", "value", "size", "lru_node", "expire_at")

    def __init__(self, key: str, value: str, size: int, lru_node: Node) -> None:
        self.key = key
        self.value = value
        self.size = size              # len(utf8(key)) + len(utf8(value))
        self.lru_node = lru_node      # LRU 리스트 안의 내 노드 (O(1) 이동/삭제용 핸들)
        self.expire_at: Optional[float] = None  # 단조 시계 기준 만료 시각(초), 없으면 None


def entry_size(key: str, value: str) -> int:
    """과제 공식: used_memory 에 더해지는 엔트리 크기 (자료구조 오버헤드 제외)."""
    return len(key.encode("utf-8")) + len(value.encode("utf-8"))


class Store:
    """Mini Redis 의 데이터 계층. 명령어 문법/출력과는 분리되어 있다.

    ``clock`` 은 초 단위 float 를 반환하는 함수다. 기본값은 ``time.monotonic`` 으로,
    시스템 시계를 사람이 바꿔도 TTL 이 영향을 받지 않는다. 테스트에서는 가짜 시계를 주입한다.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._data = HashMap()
        self._lru = DoublyLinkedList()  # front = 가장 최근 사용(MRU), back = 가장 오래 전 사용(LRU)
        self._ttl = MinHeap()           # (expire_at, key)
        self._clock = clock
        self.maxmemory = 0              # 0 = 무제한
        self.used_memory = 0
        self.evicted_keys = 0
        self.expired_keys = 0
        self._ttl_keys = 0              # 현재 만료 시간이 설정된 살아있는 키 수

    # ================================================================ 내부 헬퍼
    def _remove_entry(self, entry: _Entry) -> None:
        """엔트리를 데이터/LRU 구조에서 제거하고 메모리를 회수한다.

        TTL 힙의 항목은 여기서 지우지 않는다. 힙 중간 원소 삭제는 O(n)이므로,
        나중에 힙에서 꺼낼 때 "이미 없는 키"인지 확인하고 버린다(lazy deletion).
        """
        self._data.remove(entry.key)
        self._lru.remove_node(entry.lru_node)
        self.used_memory -= entry.size
        if entry.expire_at is not None:
            self._ttl_keys -= 1

    def _is_expired(self, entry: _Entry, now: float) -> bool:
        return entry.expire_at is not None and entry.expire_at <= now

    def _lookup(self, key: str) -> Optional[_Entry]:
        """만료 여부를 먼저 확인한 뒤 엔트리를 반환한다(lazy expiration).

        만료됐으면 즉시 삭제하고 None 을 반환한다 → 호출자는 '없는 키'로 처리한다.
        이 함수는 LRU 를 갱신하지 않는다(갱신 여부는 명령어마다 다르기 때문).
        """
        entry = self._data.get(key)
        if entry is None:
            return None
        if self._is_expired(entry, self._clock()):
            self._remove_entry(entry)
            self.expired_keys += 1
            return None
        return entry

    def _evict_until_fits(self) -> int:
        """used_memory 가 maxmemory 이하가 될 때까지 LRU(리스트 맨 뒤)부터 제거한다."""
        evicted = 0
        while self.maxmemory > 0 and self.used_memory > self.maxmemory and not self._lru.is_empty():
            victim_key = self._lru.last.data  # type: ignore[union-attr]
            victim = self._data.get(victim_key)
            self._remove_entry(victim)
            self.evicted_keys += 1
            evicted += 1
        return evicted

    # ================================================================ 만료 처리
    def expire_due_keys(self) -> int:
        """힙 루트부터 만료 시각이 지난 키를 일괄 삭제한다(active expiration).

        힙은 가장 이른 만료 시각을 O(1)로 보여주므로, 루트가 아직 만료 전이면
        나머지도 모두 만료 전이라는 것을 즉시 알 수 있다 → 전체 키를 훑지 않는다.
        비용: 만료된 키 k 개에 대해 O(k log n).
        """
        now = self._clock()
        removed = 0
        while not self._ttl.is_empty() and self._ttl.peek()[0] <= now:
            expire_at, key = self._ttl.pop()
            entry = self._data.get(key)
            # stale 항목 걸러내기: 키가 삭제됐거나, TTL 이 바뀌었거나(재설정/SET 초기화) 한 경우
            if entry is None or entry.expire_at != expire_at:
                continue
            self._remove_entry(entry)
            self.expired_keys += 1
            removed += 1
        return removed

    # ================================================================ 문자열 명령
    def set(self, key: str, value: str) -> None:
        """SET: 저장 후 필요하면 LRU 제거. 기존 키를 덮어쓰면 TTL 을 초기화한다.

        흐름
        1) 크기 계산. 단일 엔트리가 maxmemory 보다 크면 OOM (저장하지 않음)
        2) 기존 키면 값/크기 갱신 + TTL 제거 + MRU 로 이동, 새 키면 MRU 위치에 삽입
        3) used_memory 갱신
        4) used_memory > maxmemory 이면 LRU 부터 제거 (방금 SET 한 키는 MRU 라 마지막까지 남는다)
        """
        size = entry_size(key, value)
        if self.maxmemory > 0 and size > self.maxmemory:
            raise OutOfMemoryError(key)

        entry = self._lookup(key)
        if entry is not None:
            self.used_memory += size - entry.size
            entry.value = value
            entry.size = size
            if entry.expire_at is not None:
                entry.expire_at = None  # 덮어쓰기 → TTL 초기화 (힙 항목은 stale 처리됨)
                self._ttl_keys -= 1
            self._lru.move_to_front(entry.lru_node)
        else:
            node = self._lru.insert_front(key)
            self._data.put(key, _Entry(key, value, size, node))
            self.used_memory += size

        self._evict_until_fits()

    def get(self, key: str) -> Optional[str]:
        """GET: TTL 확인 → (만료면 삭제 후 None) → 값 반환 + LRU 갱신.

        반환에 성공한 경우에만 LRU 를 갱신한다. 만료로 삭제된 경우는 갱신하지 않는다.
        """
        entry = self._lookup(key)          # 1) 해시맵 조회 + 만료 확인(만료면 삭제)
        if entry is None:
            return None                    # 2) 없거나 만료 → (nil), LRU 갱신 없음
        self._lru.move_to_front(entry.lru_node)  # 3) 성공 → MRU 로 이동 O(1)
        return entry.value                 # 4) 값 반환

    def delete(self, key: str) -> bool:
        """DEL: 데이터/LRU 에서 제거. TTL 힙 항목은 lazy deletion 으로 자연히 무효화된다."""
        entry = self._lookup(key)
        if entry is None:
            return False
        self._remove_entry(entry)
        return True

    def exists(self, key: str) -> bool:
        """EXISTS: 존재 여부만 확인한다. 값을 '사용'한 것이 아니므로 LRU 는 갱신하지 않는다."""
        return self._lookup(key) is not None

    def dbsize(self) -> int:
        self.expire_due_keys()
        return self._data.size()

    def keys(self) -> DynamicArray:
        self.expire_due_keys()
        return self._data.keys()

    # ================================================================ TTL 명령
    def expire(self, key: str, seconds: int) -> bool:
        """EXPIRE: 만료 시간 설정. 키가 없으면 False. seconds <= 0 이면 즉시 삭제."""
        entry = self._lookup(key)
        if entry is None:
            return False
        if seconds <= 0:
            self._remove_entry(entry)
            self.expired_keys += 1
            return True
        if entry.expire_at is None:
            self._ttl_keys += 1
        entry.expire_at = self._clock() + seconds
        self._ttl.push((entry.expire_at, key))
        self._maybe_compact_ttl_heap()
        return True

    def _maybe_compact_ttl_heap(self) -> None:
        """stale 항목이 살아있는 TTL 키보다 많아지면 힙을 다시 만든다.

        같은 키에 EXPIRE 를 반복하면 예전 (expire_at, key) 가 힙에 계속 쌓인다.
        lazy deletion 의 약점(메모리 누적)을 보완하기 위해, 힙 크기가 살아있는 TTL 키의
        2배를 넘으면 살아있는 항목만으로 재구성한다. 가끔 O(n log n)이지만 분할 상환하면 작다.
        """
        if self._ttl.size() <= 64 or self._ttl.size() <= 2 * self._ttl_keys:
            return
        rebuilt = MinHeap()
        for entry in self._data.values():
            if entry.expire_at is not None:
                rebuilt.push((entry.expire_at, entry.key))
        self._ttl = rebuilt

    def ttl(self, key: str) -> int:
        """TTL: -2(키 없음), -1(만료 없음), 그 외 남은 초(올림)."""
        entry = self._lookup(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        remaining = entry.expire_at - self._clock()
        # 올림: 0.3초 남은 키를 0 으로 보여주면 '이미 없는 키'처럼 오해할 수 있다.
        return max(1, math.ceil(remaining))

    def persist(self, key: str) -> bool:
        """PERSIST: TTL 제거(확장 명령). 제거했으면 True."""
        entry = self._lookup(key)
        if entry is None or entry.expire_at is None:
            return False
        entry.expire_at = None
        self._ttl_keys -= 1
        return True

    # ================================================================ 메모리 관리
    def set_maxmemory(self, limit: int) -> int:
        """CONFIG SET maxmemory. 줄인 한도를 바로 넘으면 즉시 LRU 제거한다.

        반환값: 이번 호출로 제거된 키 수.
        (설정 직후에도 불변식 'used_memory <= maxmemory' 를 지키기 위한 설계 선택)
        """
        if limit < 0:
            raise ValueError("maxmemory must be >= 0")
        self.maxmemory = limit
        return self._evict_until_fits()

    # ================================================================ 디버그/관찰
    def lru_order(self) -> DynamicArray:
        """MRU → LRU 순서의 키 목록."""
        self.expire_due_keys()
        result = DynamicArray()
        for key in self._lru:
            result.append(key)
        return result

    def ttl_heap_snapshot(self) -> DynamicArray:
        """TTL 힙 내부 배열(레벨 순서) 복사본. stale 항목도 그대로 포함한다."""
        return self._ttl.to_array()

    @property
    def ttl_heap_size(self) -> int:
        return self._ttl.size()

    @property
    def ttl_key_count(self) -> int:
        return self._ttl_keys

    @property
    def hashmap(self) -> HashMap:
        """디버그용 읽기 전용 접근 (DEBUG HASHMAP)."""
        return self._data

    def now(self) -> float:
        return self._clock()

    @property
    def clock(self) -> Callable[[], float]:
        return self._clock
