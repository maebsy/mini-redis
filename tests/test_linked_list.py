import unittest

from mini_redis.structures.linked_list import DoublyLinkedList, Node


def as_list(dll):
    return [x for x in dll]


class DoublyLinkedListTest(unittest.TestCase):
    def test_node_has_only_required_fields(self):
        self.assertEqual(Node.__slots__, ("prev", "next", "data"))

    def test_insert_front_and_back(self):
        dll = DoublyLinkedList()
        dll.insert_back(2)
        dll.insert_front(1)
        dll.insert_back(3)
        self.assertEqual(as_list(dll), [1, 2, 3])
        self.assertEqual(len(dll), 3)
        self.assertEqual(dll.first.data, 1)
        self.assertEqual(dll.last.data, 3)

    def test_remove_front_and_back(self):
        dll = DoublyLinkedList()
        for x in (1, 2, 3):
            dll.insert_back(x)
        self.assertEqual(dll.remove_front(), 1)
        self.assertEqual(dll.remove_back(), 3)
        self.assertEqual(as_list(dll), [2])
        self.assertEqual(dll.remove_back(), 2)
        self.assertTrue(dll.is_empty())
        self.assertIsNone(dll.first)
        self.assertIsNone(dll.last)

    def test_remove_from_empty_raises(self):
        dll = DoublyLinkedList()
        with self.assertRaises(IndexError):
            dll.remove_front()
        with self.assertRaises(IndexError):
            dll.remove_back()

    def test_remove_node_middle_first_last(self):
        dll = DoublyLinkedList()
        nodes = [dll.insert_back(x) for x in "abcde"]
        self.assertEqual(dll.remove_node(nodes[2]), "c")  # middle
        self.assertEqual(dll.remove_node(nodes[0]), "a")  # first
        self.assertEqual(dll.remove_node(nodes[4]), "e")  # last
        self.assertEqual(as_list(dll), ["b", "d"])
        self.assertEqual(len(dll), 2)

    def test_remove_node_twice_raises(self):
        dll = DoublyLinkedList()
        node = dll.insert_back(1)
        dll.remove_node(node)
        with self.assertRaises(ValueError):
            dll.remove_node(node)

    def test_move_to_front(self):
        dll = DoublyLinkedList()
        nodes = [dll.insert_back(x) for x in (1, 2, 3)]
        dll.move_to_front(nodes[2])
        self.assertEqual(as_list(dll), [3, 1, 2])
        dll.move_to_front(nodes[2])  # already first → no-op
        self.assertEqual(as_list(dll), [3, 1, 2])
        dll.move_to_front(nodes[1])
        self.assertEqual(as_list(dll), [2, 3, 1])
        self.assertEqual(len(dll), 3)

    def test_backward_links_are_consistent(self):
        dll = DoublyLinkedList()
        for x in range(5):
            dll.insert_back(x)
        node, seen = dll.last, []
        while node is not None and node.data is not None:
            seen.append(node.data)
            node = node.prev
        self.assertEqual(seen, [4, 3, 2, 1, 0])

    def test_iter_nodes_allows_removal_during_iteration(self):
        dll = DoublyLinkedList()
        for x in range(6):
            dll.insert_back(x)
        for node in dll.iter_nodes():
            if node.data % 2 == 0:
                dll.remove_node(node)
        self.assertEqual(as_list(dll), [1, 3, 5])


if __name__ == "__main__":
    unittest.main()
