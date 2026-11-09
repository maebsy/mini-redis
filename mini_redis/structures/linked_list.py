"""이중 연결 리스트 (Doubly Linked List).

설계 포인트
-----------
* 노드는 과제 요구사항대로 ``prev`` / ``next`` / ``data`` 세 필드만 가진다.
* 리스트 양 끝에 데이터가 없는 **센티널(sentinel) 노드** ``_head``, ``_tail`` 을 둔다.
  실제 노드는 항상 두 센티널 사이에 있으므로 "맨 앞 / 맨 뒤 / 중간" 삭제를
  분기 없이 같은 코드(``_unlink``)로 처리할 수 있다.
* 모든 삽입/삭제/이동 연산은 포인터 2~4개만 바꾸므로 **O(1)** 이다.
* ``insert_*`` 는 생성한 노드를 반환한다. LRU 처럼 "노드 핸들"을 따로 보관해 두면
  나중에 탐색 없이 ``remove_node`` / ``move_to_front`` 를 O(1)로 호출할 수 있다.

이 리스트는 프로젝트 전반에서 재사용된다.

* LRU 추적 리스트 (store.py)
* 해시맵 체이닝 버킷 (hashmap.py)
* 스택/큐/덱 (stack_queue_deque.py, 보너스)
"""

from typing import Any, Iterator, Optional


class Node:
    """이중 연결 리스트의 노드. ``prev``, ``next``, ``data`` 만 가진다."""

    __slots__ = ("prev", "next", "data")

    def __init__(self, data: Any = None) -> None:
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None
        self.data: Any = data

    def __repr__(self) -> str:
        return "Node({!r})".format(self.data)


class DoublyLinkedList:
    """센티널 노드를 사용하는 이중 연결 리스트.

    방향 규칙: ``front`` = head 쪽, ``back`` = tail 쪽.
    """

    __slots__ = ("_head", "_tail", "_size")

    def __init__(self) -> None:
        self._head = Node()  # 데이터 없는 센티널
        self._tail = Node()  # 데이터 없는 센티널
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    # ------------------------------------------------------------------ 조회
    def __len__(self) -> int:
        return self._size

    def is_empty(self) -> bool:
        return self._size == 0

    @property
    def first(self) -> Optional[Node]:
        """맨 앞 실제 노드 (없으면 None). O(1)"""
        return None if self._size == 0 else self._head.next

    @property
    def last(self) -> Optional[Node]:
        """맨 뒤 실제 노드 (없으면 None). O(1)"""
        return None if self._size == 0 else self._tail.prev

    # ------------------------------------------------------- 내부 포인터 조작
    def _link_after(self, anchor: Node, node: Node) -> None:
        """``anchor`` 바로 뒤에 ``node`` 를 연결한다. 포인터 4개 변경 → O(1)"""
        nxt = anchor.next
        node.prev = anchor
        node.next = nxt
        anchor.next = node
        nxt.prev = node  # type: ignore[union-attr]
        self._size += 1

    def _unlink(self, node: Node) -> None:
        """``node`` 를 리스트에서 떼어낸다. 앞/뒤 노드끼리 직접 연결 → O(1)"""
        prv, nxt = node.prev, node.next
        prv.next = nxt  # type: ignore[union-attr]
        nxt.prev = prv  # type: ignore[union-attr]
        node.prev = None  # 떼어낸 노드임을 표시 (재삭제 방지용)
        node.next = None
        self._size -= 1

    # ---------------------------------------------------------- 공개 메서드
    def insert_front(self, data: Any) -> Node:
        """맨 앞에 삽입하고 생성된 노드를 반환한다. O(1) — 포인터 4개 연결"""
        node = Node(data)
        self._link_after(self._head, node)
        return node

    def insert_back(self, data: Any) -> Node:
        """맨 뒤에 삽입하고 생성된 노드를 반환한다. O(1) — 포인터 4개 연결"""
        node = Node(data)
        self._link_after(self._tail.prev, node)  # type: ignore[arg-type]
        return node

    def remove_front(self) -> Any:
        """맨 앞 노드를 제거하고 data 를 반환한다. 비어 있으면 IndexError. O(1) — 이웃 포인터 2개 + 노드 정리 2개"""
        if self._size == 0:
            raise IndexError("remove_front from empty list")
        node = self._head.next
        self._unlink(node)  # type: ignore[arg-type]
        return node.data  # type: ignore[union-attr]

    def remove_back(self) -> Any:
        """맨 뒤 노드를 제거하고 data 를 반환한다. 비어 있으면 IndexError. O(1) — 이웃 포인터 2개 + 노드 정리 2개"""
        if self._size == 0:
            raise IndexError("remove_back from empty list")
        node = self._tail.prev
        self._unlink(node)  # type: ignore[arg-type]
        return node.data  # type: ignore[union-attr]

    def remove_node(self, node: Node) -> Any:
        """특정 노드를 제거하고 data 를 반환한다. O(1) — 이웃 포인터 2개 + 노드 정리 2개

        전제: ``node`` 는 이 리스트의 노드여야 한다(소유 리스트를 노드에 저장하지 않으므로
        O(1)로 검사할 수 없다). 이미 제거된 노드는 ``prev is None`` 으로 감지한다.
        """
        if node.prev is None or node.next is None:
            raise ValueError("node is not linked to a list")
        self._unlink(node)
        return node.data

    def move_to_front(self, node: Node) -> None:
        """기존 노드를 맨 앞으로 옮긴다(노드 객체 재사용). O(1) — 떼기 4개 + 연결 4개, 리스트 길이와 무관

        LRU 에서 "방금 사용한 키"를 MRU 위치로 올릴 때 사용한다.
        """
        if node.prev is None or node.next is None:
            raise ValueError("node is not linked to a list")
        if node.prev is self._head:  # 이미 맨 앞
            return
        self._unlink(node)
        self._link_after(self._head, node)

    def clear(self) -> None:
        """모든 노드를 제거한다."""
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    # ---------------------------------------------------------------- 순회
    def iter_nodes(self) -> Iterator[Node]:
        """front → back 순서로 노드를 순회한다.

        순회 중 현재 노드를 삭제해도 안전하도록 다음 노드를 먼저 기억해 둔다.
        """
        node = self._head.next
        while node is not self._tail:
            nxt = node.next  # type: ignore[union-attr]
            yield node  # type: ignore[misc]
            node = nxt

    def __iter__(self) -> Iterator[Any]:
        """front → back 순서로 data 를 순회한다."""
        for node in self.iter_nodes():
            yield node.data

    def __repr__(self) -> str:
        return "DoublyLinkedList([" + ", ".join(repr(d) for d in self) + "])"
