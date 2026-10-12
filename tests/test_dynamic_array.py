import unittest

from mini_redis.structures.dynamic_array import DynamicArray


class DynamicArrayTest(unittest.TestCase):
    def test_append_doubles_capacity(self):
        arr = DynamicArray(capacity=2)
        capacities = []
        for i in range(9):
            arr.append(i)
            capacities.append(arr.capacity)
        self.assertEqual(capacities, [2, 2, 4, 4, 8, 8, 8, 8, 16])
        self.assertEqual(list(arr), list(range(9)))

    def test_get_set_and_negative_index(self):
        arr = DynamicArray(items=[10, 20, 30])
        self.assertEqual(arr.get(0), 10)
        self.assertEqual(arr[-1], 30)
        arr.set(1, 99)
        arr[-1] = 77
        self.assertEqual(list(arr), [10, 99, 77])

    def test_out_of_range(self):
        arr = DynamicArray(items=[1])
        with self.assertRaises(IndexError):
            arr.get(1)
        with self.assertRaises(IndexError):
            arr.set(-2, 0)
        with self.assertRaises(IndexError):
            DynamicArray().pop()

    def test_remove_shifts_left(self):
        arr = DynamicArray(items=[1, 2, 3, 4])
        self.assertEqual(arr.remove(1), 2)
        self.assertEqual(list(arr), [1, 3, 4])
        self.assertEqual(arr.remove(-1), 4)
        self.assertEqual(list(arr), [1, 3])

    def test_insert(self):
        arr = DynamicArray(items=[1, 3])
        arr.insert(1, 2)
        arr.insert(0, 0)
        arr.insert(len(arr), 4)
        self.assertEqual(list(arr), [0, 1, 2, 3, 4])

    def test_pop_shrinks_with_hysteresis(self):
        arr = DynamicArray(capacity=4)
        for i in range(32):
            arr.append(i)
        self.assertEqual(arr.capacity, 32)
        while len(arr) > 8:
            arr.pop()
        self.assertEqual(arr.capacity, 16)  # 8 <= 32/4 → 16 으로 축소
        while len(arr) > 0:
            arr.pop()
        self.assertEqual(arr.capacity, DynamicArray.MIN_CAPACITY)


if __name__ == "__main__":
    unittest.main()
