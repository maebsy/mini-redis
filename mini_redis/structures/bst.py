"""이진 탐색 트리 (Binary Search Tree) — 보너스 과제.

규칙: 모든 노드에 대해 ``왼쪽 서브트리 키 < 노드 키 < 오른쪽 서브트리 키``.
그래서 **중위 순회 결과가 곧 정렬된 키 순서**가 된다.

* insert / search / delete : 평균 O(log n), 최악 O(n) (정렬된 순서로 넣으면 한쪽으로 치우침)
* inorder                  : O(n)
* range(lo, hi)            : O(log n + k)  — 범위 밖 서브트리는 건너뛴다

``DEBUG SORTEDKEYS`` / ``DEBUG RANGEKEYS`` 명령이 이 트리로 "키 정렬/범위 조회"를 제공한다.
깊은 트리에서도 재귀 한도에 걸리지 않도록 모든 연산을 반복문(+직접 만든 Stack)으로 구현했다.
"""

from typing import Any, Iterator, Optional, Tuple

from .stack_queue_deque import Queue, Stack


class BSTNode:
    __slots__ = ("key", "value", "left", "right")

    def __init__(self, key: Any, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.left: Optional["BSTNode"] = None
        self.right: Optional["BSTNode"] = None


class BinarySearchTree:
    """반복문 기반 이진 탐색 트리. 중위 순회가 정렬 순서를 만든다."""

    __slots__ = ("root", "_size")

    def __init__(self) -> None:
        self.root: Optional[BSTNode] = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    # ------------------------------------------------------------ 삽입/탐색
    def insert(self, key: Any, value: Any = None) -> bool:
        """키 삽입. 새 키면 True, 이미 있으면 값만 갱신하고 False."""
        if self.root is None:
            self.root = BSTNode(key, value)
            self._size = 1
            return True
        node = self.root
        while True:
            if key == node.key:
                node.value = value
                return False
            if key < node.key:
                if node.left is None:
                    node.left = BSTNode(key, value)
                    break
                node = node.left
            else:
                if node.right is None:
                    node.right = BSTNode(key, value)
                    break
                node = node.right
        self._size += 1
        return True

    def search(self, key: Any) -> Optional[BSTNode]:
        """키가 있는 노드를 찾는다. 비교 결과에 따라 한쪽 서브트리만 내려간다."""
        node = self.root
        while node is not None:
            if key == node.key:
                return node
            node = node.left if key < node.key else node.right
        return None

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    # ---------------------------------------------------------------- 삭제
    def delete(self, key: Any) -> bool:
        """키 삭제. 세 가지 경우를 처리한다.

        1) 자식이 없는 노드  : 그냥 떼어낸다.
        2) 자식이 하나인 노드 : 그 자식을 부모에 직접 연결한다.
        3) 자식이 둘인 노드  : 오른쪽 서브트리의 최솟값(중위 후속자)을 찾아
                              키/값을 복사한 뒤, 후속자 노드를 삭제한다(후속자는 왼쪽 자식이 없다).
        """
        parent: Optional[BSTNode] = None
        node = self.root
        while node is not None and node.key != key:
            parent = node
            node = node.left if key < node.key else node.right
        if node is None:
            return False

        if node.left is not None and node.right is not None:  # 경우 3
            succ_parent = node
            succ = node.right
            while succ.left is not None:
                succ_parent = succ
                succ = succ.left
            node.key, node.value = succ.key, succ.value
            # 이제 succ(왼쪽 자식 없음)를 삭제하는 문제로 바뀐다.
            parent, node = succ_parent, succ

        child = node.left if node.left is not None else node.right  # 경우 1, 2
        if parent is None:
            self.root = child
        elif parent.left is node:
            parent.left = child
        else:
            parent.right = child
        self._size -= 1
        return True

    # ---------------------------------------------------------------- 순회
    def inorder(self) -> Iterator[Tuple[Any, Any]]:
        """(key, value) 를 키 오름차순으로 반환. 재귀 대신 Stack 을 사용한다."""
        stack = Stack()
        node = self.root
        while node is not None or not stack.is_empty():
            while node is not None:  # 왼쪽 끝까지 내려가며 쌓기
                stack.push(node)
                node = node.left
            node = stack.pop()
            yield node.key, node.value
            node = node.right

    def keys(self) -> Iterator[Any]:
        for key, _ in self.inorder():
            yield key

    def range(self, low: Any, high: Any) -> Iterator[Any]:
        """``low <= key <= high`` 인 키를 정렬 순서로 반환한다(범위 밖 가지는 가지치기)."""
        stack = Stack()
        node = self.root
        while node is not None or not stack.is_empty():
            while node is not None:
                stack.push(node)
                # low 보다 작은 노드의 왼쪽 서브트리는 전부 범위 밖이므로 내려가지 않는다.
                node = node.left if low < node.key else None
            node = stack.pop()
            if node.key > high:
                return  # 이후 키는 모두 더 크다
            if node.key >= low:
                yield node.key
            node = node.right

    def min(self) -> Any:
        if self.root is None:
            raise ValueError("min() of empty BST")
        node = self.root
        while node.left is not None:
            node = node.left
        return node.key

    def max(self) -> Any:
        if self.root is None:
            raise ValueError("max() of empty BST")
        node = self.root
        while node.right is not None:
            node = node.right
        return node.key

    def height(self) -> int:
        """레벨 순회로 높이를 계산한다(노드 수 기준)."""
        if self.root is None:
            return 0
        queue = Queue()
        queue.enqueue((self.root, 1))
        best = 0
        while not queue.is_empty():
            node, depth = queue.dequeue()
            if depth > best:
                best = depth
            if node.left is not None:
                queue.enqueue((node.left, depth + 1))
            if node.right is not None:
                queue.enqueue((node.right, depth + 1))
        return best
