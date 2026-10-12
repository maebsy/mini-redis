"""이진 트리와 순회 알고리즘 — 보너스 과제.

목적
* 전위/중위/후위/레벨 순회를 직접 구현한다.
* ``from_level_order`` 로 "배열 → 완전 이진 트리" 변환을 제공해서
  **힙이 완전 이진 트리를 배열로 표현한다**는 사실을 코드로 확인한다.
  (``DEBUG TTLHEAP`` 명령이 TTL 힙 배열을 이 트리로 바꿔 그려준다)
"""

from typing import Any, Iterable, Iterator, Optional

from .dynamic_array import DynamicArray
from .stack_queue_deque import Queue


class TreeNode:
    __slots__ = ("value", "left", "right")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.left: Optional["TreeNode"] = None
        self.right: Optional["TreeNode"] = None


class BinaryTree:
    """일반 이진 트리. 순회는 모두 제너레이터로 제공한다."""

    __slots__ = ("root",)

    def __init__(self, root: Optional[TreeNode] = None) -> None:
        self.root = root

    @classmethod
    def from_level_order(cls, values: Iterable[Any]) -> "BinaryTree":
        """레벨 순서 배열로 완전 이진 트리를 만든다.

        배열 인덱스 i 의 자식은 2i+1, 2i+2 — 힙이 쓰는 규칙과 동일하다.
        """
        arr = DynamicArray(items=values)
        n = len(arr)
        if n == 0:
            return cls()
        nodes = DynamicArray()
        for value in arr:
            nodes.append(TreeNode(value))
        for i in range(n):
            left, right = 2 * i + 1, 2 * i + 2
            if left < n:
                nodes[i].left = nodes[left]
            if right < n:
                nodes[i].right = nodes[right]
        return cls(nodes[0])

    # ------------------------------------------------------------------ 순회
    def preorder(self) -> Iterator[Any]:
        """전위 순회: 루트 → 왼쪽 → 오른쪽 (트리 복사/직렬화에 적합)"""
        def walk(node: Optional[TreeNode]) -> Iterator[Any]:
            if node is None:
                return
            yield node.value
            yield from walk(node.left)
            yield from walk(node.right)
        return walk(self.root)

    def inorder(self) -> Iterator[Any]:
        """중위 순회: 왼쪽 → 루트 → 오른쪽 (BST 에서는 정렬 순서)"""
        def walk(node: Optional[TreeNode]) -> Iterator[Any]:
            if node is None:
                return
            yield from walk(node.left)
            yield node.value
            yield from walk(node.right)
        return walk(self.root)

    def postorder(self) -> Iterator[Any]:
        """후위 순회: 왼쪽 → 오른쪽 → 루트 (자식부터 처리, 트리 삭제/크기 계산에 적합)"""
        def walk(node: Optional[TreeNode]) -> Iterator[Any]:
            if node is None:
                return
            yield from walk(node.left)
            yield from walk(node.right)
            yield node.value
        return walk(self.root)

    def levelorder(self) -> Iterator[Any]:
        """레벨 순회(BFS): 큐를 사용해 위층부터 왼쪽→오른쪽으로 방문한다."""
        if self.root is None:
            return
        queue = Queue()
        queue.enqueue(self.root)
        while not queue.is_empty():
            node = queue.dequeue()
            yield node.value
            if node.left is not None:
                queue.enqueue(node.left)
            if node.right is not None:
                queue.enqueue(node.right)

    # ------------------------------------------------------------------ 정보
    def height(self) -> int:
        """트리 높이(노드 수 기준). 빈 트리는 0."""
        def h(node: Optional[TreeNode]) -> int:
            if node is None:
                return 0
            return 1 + max(h(node.left), h(node.right))
        return h(self.root)

    def size(self) -> int:
        count = 0
        for _ in self.preorder():
            count += 1
        return count

    def render(self, formatter=str) -> DynamicArray:
        """트리를 사람이 읽기 쉬운 줄 목록으로 그린다(디렉터리 트리 스타일)."""
        lines = DynamicArray()
        if self.root is None:
            lines.append("(empty tree)")
            return lines

        def walk(node: TreeNode, prefix: str, is_last: bool, is_root: bool, tag: str) -> None:
            if is_root:
                lines.append(formatter(node.value))
                child_prefix = ""
            else:
                connector = "└── " if is_last else "├── "
                lines.append(prefix + connector + tag + formatter(node.value))
                child_prefix = prefix + ("    " if is_last else "│   ")
            children = DynamicArray()
            if node.left is not None:
                children.append(("L: ", node.left))
            if node.right is not None:
                children.append(("R: ", node.right))
            for i in range(len(children)):
                child_tag, child = children[i]
                walk(child, child_prefix, i == len(children) - 1, False, child_tag)

        walk(self.root, "", True, True, "")
        return lines
