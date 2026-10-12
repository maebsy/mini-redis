"""동적 배열 (Dynamic Array) — 보너스 과제.

파이썬 ``list`` 의 ``append`` / ``pop`` 같은 편의 기능을 쓰지 않고,
``[None] * capacity`` 로 만든 **고정 길이 저장소**에 인덱스 접근만 사용해서
"용량이 차면 2배로 늘리는" 동적 배열을 직접 구현한다.

* append  : 평균(amortized) O(1)  — 가끔 O(n) 확장이 일어나지만 2배씩 늘리므로
            n 번 append 의 총 복사 비용은 n + n/2 + n/4 + ... < 2n → 평균 O(1)
* get/set : O(1)
* remove  : O(n)  (뒤쪽 원소를 한 칸씩 당긴다)
* pop     : O(1)  (맨 뒤 원소 제거)

이 배열은 최소 힙의 내부 저장소, 해시맵의 ``keys()`` 반환값 등에 재사용된다.
"""

from typing import Any, Iterable, Iterator, Optional


class DynamicArray:
    """용량 2배 확장 / 1/4 이하일 때 절반 축소하는 동적 배열."""

    __slots__ = ("_items", "_size", "_capacity")

    MIN_CAPACITY = 4

    def __init__(self, capacity: int = MIN_CAPACITY, items: Optional[Iterable[Any]] = None) -> None:
        if capacity < 1:
            capacity = self.MIN_CAPACITY
        self._capacity = capacity
        self._items = [None] * capacity  # 고정 길이 저장소 (인덱스 접근만 사용)
        self._size = 0
        if items is not None:
            for item in items:
                self.append(item)

    # ------------------------------------------------------------------ 기본
    def __len__(self) -> int:
        return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    def is_empty(self) -> bool:
        return self._size == 0

    def _normalize(self, index: int) -> int:
        """음수 인덱스를 지원하고 범위를 검사한다."""
        if index < 0:
            index += self._size
        if index < 0 or index >= self._size:
            raise IndexError("DynamicArray index out of range")
        return index

    def _resize(self, new_capacity: int) -> None:
        """새 고정 배열을 만들고 기존 원소를 복사한다. O(n)"""
        new_items = [None] * new_capacity
        for i in range(self._size):
            new_items[i] = self._items[i]
        self._items = new_items
        self._capacity = new_capacity

    # ------------------------------------------------------------ 공개 API
    def get(self, index: int) -> Any:
        return self._items[self._normalize(index)]

    def set(self, index: int, value: Any) -> None:
        self._items[self._normalize(index)] = value

    def append(self, value: Any) -> None:
        """맨 뒤에 추가. 꽉 차 있으면 용량을 2배로 늘린다. 평균 O(1)"""
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        self._items[self._size] = value
        self._size += 1

    def pop(self) -> Any:
        """맨 뒤 원소를 제거하고 반환한다. O(1) (+ 가끔 축소)"""
        if self._size == 0:
            raise IndexError("pop from empty DynamicArray")
        self._size -= 1
        value = self._items[self._size]
        self._items[self._size] = None  # 참조 해제 (GC 도움)
        self._maybe_shrink()
        return value

    def remove(self, index: int) -> Any:
        """``index`` 위치 원소를 제거하고 반환한다. 뒤 원소를 당기므로 O(n)"""
        index = self._normalize(index)
        value = self._items[index]
        for i in range(index, self._size - 1):
            self._items[i] = self._items[i + 1]
        self._size -= 1
        self._items[self._size] = None
        self._maybe_shrink()
        return value

    def insert(self, index: int, value: Any) -> None:
        """``index`` 위치에 삽입한다. O(n)"""
        if index < 0:
            index += self._size
        if index < 0 or index > self._size:
            raise IndexError("DynamicArray insert index out of range")
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        for i in range(self._size, index, -1):
            self._items[i] = self._items[i - 1]
        self._items[index] = value
        self._size += 1

    def clear(self) -> None:
        self._items = [None] * self.MIN_CAPACITY
        self._capacity = self.MIN_CAPACITY
        self._size = 0

    def _maybe_shrink(self) -> None:
        """원소 수가 용량의 1/4 이하이면 절반으로 줄인다.

        1/2 가 아니라 1/4 에서 줄이는 이유: 경계에서 append/pop 이 반복될 때
        확장·축소가 번갈아 일어나는 thrashing 을 막기 위해서다(히스테리시스).
        """
        if self._capacity > self.MIN_CAPACITY and self._size <= self._capacity // 4:
            self._resize(max(self.MIN_CAPACITY, self._capacity // 2))

    # ---------------------------------------------------------- 파이썬 연동
    def __getitem__(self, index: int) -> Any:
        return self.get(index)

    def __setitem__(self, index: int, value: Any) -> None:
        self.set(index, value)

    def __iter__(self) -> Iterator[Any]:
        for i in range(self._size):
            yield self._items[i]

    def __repr__(self) -> str:
        return "DynamicArray([" + ", ".join(repr(v) for v in self) + "])"
