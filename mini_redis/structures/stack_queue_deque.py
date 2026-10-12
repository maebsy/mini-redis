"""스택 / 큐 / 덱 — 보너스 과제.

세 자료구조 모두 이중 연결 리스트 위에 얇게 감싼 어댑터(Adapter)다.
양 끝 삽입/삭제가 O(1)인 이중 연결 리스트를 재사용하면 별도 구현 없이
모든 연산을 O(1)로 만들 수 있다. 개념 정리는 ``docs/STACK_QUEUE_DEQUE.md`` 참고.

프로젝트 내 활용처
* Queue : Pub/Sub 구독자별 메시지 버퍼 (pubsub.py)
* Deque : 최근 명령어 히스토리, 최대 길이를 넘으면 가장 오래된 항목 제거 (server.py)
* Stack : BST 중위 순회를 재귀 없이 구현 (bst.py)
"""

from typing import Any, Iterator, Optional

from .linked_list import DoublyLinkedList


class Stack:
    """LIFO(후입선출). push/pop/peek 모두 O(1)."""

    __slots__ = ("_list",)

    def __init__(self) -> None:
        self._list = DoublyLinkedList()

    def push(self, item: Any) -> None:
        self._list.insert_back(item)

    def pop(self) -> Any:
        if self._list.is_empty():
            raise IndexError("pop from empty stack")
        return self._list.remove_back()

    def peek(self) -> Any:
        last = self._list.last
        if last is None:
            raise IndexError("peek from empty stack")
        return last.data

    def is_empty(self) -> bool:
        return self._list.is_empty()

    def __len__(self) -> int:
        return len(self._list)


class Queue:
    """FIFO(선입선출). enqueue/dequeue/peek 모두 O(1)."""

    __slots__ = ("_list",)

    def __init__(self) -> None:
        self._list = DoublyLinkedList()

    def enqueue(self, item: Any) -> None:
        self._list.insert_back(item)

    def dequeue(self) -> Any:
        if self._list.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._list.remove_front()

    def peek(self) -> Any:
        first = self._list.first
        if first is None:
            raise IndexError("peek from empty queue")
        return first.data

    def is_empty(self) -> bool:
        return self._list.is_empty()

    def __len__(self) -> int:
        return len(self._list)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._list)


class Deque:
    """양방향 큐. 양 끝 삽입/삭제 O(1).

    ``maxlen`` 을 주면 가득 찬 상태에서 한쪽에 넣을 때 반대쪽 원소를 버린다
    (최근 N 개만 보관하는 히스토리 버퍼에 유용).
    """

    __slots__ = ("_list", "maxlen")

    def __init__(self, maxlen: Optional[int] = None) -> None:
        if maxlen is not None and maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self._list = DoublyLinkedList()
        self.maxlen = maxlen

    def append(self, item: Any) -> None:
        """오른쪽(back)에 추가. 가득 차면 왼쪽(front) 원소 제거."""
        if self.maxlen is not None and len(self._list) >= self.maxlen:
            self._list.remove_front()
        self._list.insert_back(item)

    def appendleft(self, item: Any) -> None:
        """왼쪽(front)에 추가. 가득 차면 오른쪽(back) 원소 제거."""
        if self.maxlen is not None and len(self._list) >= self.maxlen:
            self._list.remove_back()
        self._list.insert_front(item)

    def pop(self) -> Any:
        if self._list.is_empty():
            raise IndexError("pop from empty deque")
        return self._list.remove_back()

    def popleft(self) -> Any:
        if self._list.is_empty():
            raise IndexError("pop from empty deque")
        return self._list.remove_front()

    def peek_front(self) -> Any:
        first = self._list.first
        if first is None:
            raise IndexError("peek from empty deque")
        return first.data

    def peek_back(self) -> Any:
        last = self._list.last
        if last is None:
            raise IndexError("peek from empty deque")
        return last.data

    def is_empty(self) -> bool:
        return self._list.is_empty()

    def __len__(self) -> int:
        return len(self._list)

    def __iter__(self) -> Iterator[Any]:
        """front → back (오래된 것 → 최근 것) 순서로 순회한다."""
        return iter(self._list)
