"""최소 힙 (Binary Min-Heap).

완전 이진 트리를 배열(``DynamicArray``)에 레벨 순서로 저장한다.

* 인덱스 i 의 부모: ``(i - 1) // 2``
* 인덱스 i 의 자식: ``2*i + 1`` (왼쪽), ``2*i + 2`` (오른쪽)
* 힙 속성: 모든 부모 ≤ 자식  →  **루트(인덱스 0)가 항상 최솟값**

연산 복잡도
* peek : O(1)          — 루트만 보면 된다
* push : O(log n)      — 맨 끝에 넣고 부모와 비교하며 위로 올린다(_heapify_up)
* pop  : O(log n)      — 마지막 원소를 루트로 옮기고 아래로 내린다(_heapify_down)

TTL 관리에서는 ``(expire_at, key)`` 튜플을 넣는다. 튜플은 첫 원소(만료 시각)부터
비교되므로 "가장 먼저 만료될 키"가 항상 루트에 위치한다.
"""

from typing import Any, Iterator

from .dynamic_array import DynamicArray


class MinHeap:
    """비교 가능한 원소를 저장하는 최소 힙."""

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data = DynamicArray()

    # ------------------------------------------------------------ 공개 API
    def push(self, item: Any) -> None:
        """원소 추가. O(log n)"""
        self._data.append(item)
        self._heapify_up(len(self._data) - 1)

    def pop(self) -> Any:
        """최솟값을 꺼낸다. 비어 있으면 IndexError. O(log n)"""
        n = len(self._data)
        if n == 0:
            raise IndexError("pop from empty heap")
        root = self._data[0]
        last = self._data.pop()
        if n > 1:
            self._data[0] = last
            self._heapify_down(0)
        return root

    def peek(self) -> Any:
        """최솟값을 꺼내지 않고 확인한다. 비어 있으면 IndexError. O(1)"""
        if len(self._data) == 0:
            raise IndexError("peek from empty heap")
        return self._data[0]

    def size(self) -> int:
        return len(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def clear(self) -> None:
        self._data.clear()

    # ------------------------------------------------------------ 내부 연산
    def _swap(self, i: int, j: int) -> None:
        tmp = self._data[i]
        self._data[i] = self._data[j]
        self._data[j] = tmp

    def _heapify_up(self, index: int) -> None:
        """새로 넣은 원소를 부모보다 작으면 계속 위로 올린다(sift-up)."""
        while index > 0:
            parent = (index - 1) // 2
            if self._data[index] < self._data[parent]:
                self._swap(index, parent)
                index = parent
            else:
                break

    def _heapify_down(self, index: int) -> None:
        """루트로 옮긴 원소를 더 작은 자식과 바꾸며 아래로 내린다(sift-down)."""
        n = len(self._data)
        while True:
            left = 2 * index + 1
            right = left + 1
            smallest = index
            if left < n and self._data[left] < self._data[smallest]:
                smallest = left
            if right < n and self._data[right] < self._data[smallest]:
                smallest = right
            if smallest == index:
                break
            self._swap(index, smallest)
            index = smallest

    # ------------------------------------------------------------ 디버그/보너스
    def to_array(self) -> DynamicArray:
        """내부 배열(레벨 순서) 복사본. 이진 트리 시각화(보너스)에 사용한다."""
        return DynamicArray(items=self._data)

    def is_valid(self) -> bool:
        """힙 속성(부모 ≤ 자식)을 만족하는지 검사한다. 테스트용."""
        n = len(self._data)
        for i in range(1, n):
            if self._data[i] < self._data[(i - 1) // 2]:
                return False
        return True

    def __iter__(self) -> Iterator[Any]:
        """배열(레벨) 순서 순회. 정렬 순서가 아님에 주의."""
        return iter(self._data)

    def __repr__(self) -> str:
        return "MinHeap(" + repr(list(self._data)) + ")"
