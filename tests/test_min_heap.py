import random
import unittest

from mini_redis.structures.min_heap import MinHeap


class MinHeapTest(unittest.TestCase):
    def test_push_pop_returns_ascending(self):
        heap = MinHeap()
        values = [5, 3, 8, 1, 9, 2, 7]
        for v in values:
            heap.push(v)
            self.assertTrue(heap.is_valid())
        out = []
        while not heap.is_empty():
            out.append(heap.pop())
            self.assertTrue(heap.is_valid())
        self.assertEqual(out, [1, 2, 3, 5, 7, 8, 9])

    def test_peek_does_not_remove(self):
        heap = MinHeap()
        heap.push(3)
        heap.push(1)
        self.assertEqual(heap.peek(), 1)
        self.assertEqual(heap.size(), 2)

    def test_empty_raises(self):
        heap = MinHeap()
        with self.assertRaises(IndexError):
            heap.pop()
        with self.assertRaises(IndexError):
            heap.peek()

    def test_ttl_tuples_order_by_expire_at(self):
        heap = MinHeap()
        heap.push((105.0, "c"))
        heap.push((101.5, "a"))
        heap.push((103.0, "b"))
        self.assertEqual(heap.pop(), (101.5, "a"))
        self.assertEqual(heap.pop(), (103.0, "b"))
        self.assertEqual(heap.pop(), (105.0, "c"))

    def test_randomized_heap_sort(self):
        rng = random.Random(42)
        data = [rng.randint(-1000, 1000) for _ in range(500)]
        heap = MinHeap()
        for v in data:
            heap.push(v)
        out = [heap.pop() for _ in range(len(data))]
        self.assertTrue(all(out[i] <= out[i + 1] for i in range(len(out) - 1)))
        self.assertEqual(len(out), len(data))


if __name__ == "__main__":
    unittest.main()
