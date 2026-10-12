import random
import unittest

from mini_redis.structures.binary_tree import BinaryTree
from mini_redis.structures.bst import BinarySearchTree
from mini_redis.structures.min_heap import MinHeap
from mini_redis.structures.stack_queue_deque import Deque, Queue, Stack


class StackQueueDequeTest(unittest.TestCase):
    def test_stack_lifo(self):
        s = Stack()
        for x in (1, 2, 3):
            s.push(x)
        self.assertEqual(s.peek(), 3)
        self.assertEqual([s.pop(), s.pop(), s.pop()], [3, 2, 1])
        with self.assertRaises(IndexError):
            s.pop()

    def test_queue_fifo(self):
        q = Queue()
        for x in (1, 2, 3):
            q.enqueue(x)
        self.assertEqual(q.peek(), 1)
        self.assertEqual([q.dequeue(), q.dequeue(), q.dequeue()], [1, 2, 3])
        with self.assertRaises(IndexError):
            q.dequeue()

    def test_deque_both_ends_and_maxlen(self):
        d = Deque(maxlen=3)
        d.append(1)
        d.append(2)
        d.appendleft(0)
        self.assertEqual(list(d), [0, 1, 2])
        d.append(3)  # 가득 참 → 왼쪽(0) 제거
        self.assertEqual(list(d), [1, 2, 3])
        d.appendleft(9)  # 가득 참 → 오른쪽(3) 제거
        self.assertEqual(list(d), [9, 1, 2])
        self.assertEqual(d.pop(), 2)
        self.assertEqual(d.popleft(), 9)
        self.assertEqual(d.peek_front(), 1)
        self.assertEqual(d.peek_back(), 1)


class BinaryTreeTest(unittest.TestCase):
    def setUp(self):
        #        1
        #      /   \
        #     2     3
        #    / \   /
        #   4   5 6
        self.tree = BinaryTree.from_level_order([1, 2, 3, 4, 5, 6])

    def test_traversals(self):
        self.assertEqual(list(self.tree.preorder()), [1, 2, 4, 5, 3, 6])
        self.assertEqual(list(self.tree.inorder()), [4, 2, 5, 1, 6, 3])
        self.assertEqual(list(self.tree.postorder()), [4, 5, 2, 6, 3, 1])
        self.assertEqual(list(self.tree.levelorder()), [1, 2, 3, 4, 5, 6])

    def test_height_and_size(self):
        self.assertEqual(self.tree.height(), 3)
        self.assertEqual(self.tree.size(), 6)
        self.assertEqual(BinaryTree().height(), 0)

    def test_heap_array_is_a_complete_binary_tree(self):
        """힙 배열을 트리로 바꾸면 레벨 순회 = 배열 순서, 모든 부모 <= 자식."""
        heap = MinHeap()
        for v in (9, 4, 7, 1, 8, 2, 6):
            heap.push(v)
        array = list(heap.to_array())
        tree = BinaryTree.from_level_order(array)
        self.assertEqual(list(tree.levelorder()), array)

        def check(node):
            for child in (node.left, node.right):
                if child is not None:
                    self.assertLessEqual(node.value, child.value)
                    check(child)
        check(tree.root)

    def test_render(self):
        lines = list(BinaryTree.from_level_order([1, 2, 3]).render())
        self.assertEqual(lines, ["1", "├── L: 2", "└── R: 3"])


class BinarySearchTreeTest(unittest.TestCase):
    def test_insert_search_inorder(self):
        bst = BinarySearchTree()
        for k in (50, 30, 70, 20, 40, 60, 80):
            self.assertTrue(bst.insert(k, str(k)))
        self.assertFalse(bst.insert(40, "forty"))
        self.assertEqual(bst.search(40).value, "forty")
        self.assertIsNone(bst.search(45))
        self.assertEqual(list(bst.keys()), [20, 30, 40, 50, 60, 70, 80])
        self.assertEqual((bst.min(), bst.max()), (20, 80))
        self.assertEqual(bst.height(), 3)

    def test_delete_three_cases(self):
        bst = BinarySearchTree()
        for k in (50, 30, 70, 20, 40, 60, 80, 65):
            bst.insert(k)
        self.assertTrue(bst.delete(20))   # 리프
        self.assertTrue(bst.delete(60))   # 자식 하나(65)
        self.assertTrue(bst.delete(50))   # 자식 둘(루트) → 후속자 65
        self.assertFalse(bst.delete(999))
        self.assertEqual(list(bst.keys()), [30, 40, 65, 70, 80])
        self.assertEqual(bst.root.key, 65)
        self.assertEqual(len(bst), 5)

    def test_range(self):
        bst = BinarySearchTree()
        for k in "mcxaqbz":
            bst.insert(k)
        self.assertEqual(list(bst.range("b", "q")), ["b", "c", "m", "q"])
        self.assertEqual(list(bst.range("n", "p")), [])

    def test_randomized_against_reference(self):
        rng = random.Random(3)
        bst = BinarySearchTree()
        ref = []
        for _ in range(2000):
            k = rng.randint(0, 200)
            if rng.random() < 0.6:
                bst.insert(k)
                if k not in ref:
                    ref.append(k)
            else:
                self.assertEqual(bst.delete(k), k in ref)
                if k in ref:
                    ref.remove(k)
        self.assertEqual(list(bst.keys()), sorted(ref))

    def test_sorted_insert_does_not_hit_recursion_limit(self):
        bst = BinarySearchTree()
        for k in range(5000):  # 최악의 경우(한쪽으로 치우친 트리)
            bst.insert(k)
        self.assertEqual(sum(1 for _ in bst.keys()), 5000)
        self.assertEqual(bst.height(), 5000)


if __name__ == "__main__":
    unittest.main()
