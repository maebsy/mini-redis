import random
import unittest

from mini_redis.structures.hashmap import FNV_OFFSET_BASIS_64, HashMap, fnv1a_64


class HashFunctionTest(unittest.TestCase):
    def test_known_vectors(self):
        # FNV-1a 64bit 공개 테스트 벡터
        self.assertEqual(fnv1a_64(""), FNV_OFFSET_BASIS_64)
        self.assertEqual(fnv1a_64("a"), 0xAF63DC4C8601EC8C)
        self.assertEqual(fnv1a_64("foobar"), 0x85944171F73967E8)

    def test_deterministic_and_unicode(self):
        self.assertEqual(fnv1a_64("사용자:1"), fnv1a_64("사용자:1"))
        self.assertNotEqual(fnv1a_64("user:1"), fnv1a_64("user:2"))

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            fnv1a_64(123)  # type: ignore[arg-type]


class HashMapTest(unittest.TestCase):
    def test_put_get_overwrite(self):
        m = HashMap()
        self.assertTrue(m.put("a", 1))
        self.assertFalse(m.put("a", 2))
        self.assertEqual(m.get("a"), 2)
        self.assertEqual(m.size(), 1)
        self.assertIsNone(m.get("missing"))
        self.assertEqual(m.get("missing", "x"), "x")

    def test_remove_and_contains(self):
        m = HashMap()
        m.put("a", 1)
        self.assertTrue(m.contains("a"))
        self.assertTrue(m.remove("a"))
        self.assertFalse(m.remove("a"))
        self.assertFalse("a" in m)
        self.assertEqual(len(m), 0)

    def test_collisions_are_chained(self):
        # 모든 키를 같은 버킷으로 보내는 해시 함수 → 체이닝만으로 동작해야 한다
        m = HashMap(capacity=8, hash_func=lambda key: 42)
        for i in range(20):
            m.put("k{}".format(i), i)
        for i in range(20):
            self.assertEqual(m.get("k{}".format(i)), i)
        used, longest, _ = m.chain_stats()
        self.assertEqual(used, 1)
        self.assertEqual(longest, 20)
        self.assertTrue(m.remove("k7"))
        self.assertIsNone(m.get("k7"))
        self.assertEqual(m.size(), 19)

    def test_resize_when_load_factor_exceeds_075(self):
        m = HashMap(capacity=8)
        for i in range(6):  # 6/8 = 0.75 → 아직 확장 안 함
            m.put("k{}".format(i), i)
        self.assertEqual(m.capacity, 8)
        m.put("k6", 6)  # 7/8 = 0.875 > 0.75 → 2배 확장
        self.assertEqual(m.capacity, 16)
        self.assertEqual(m.resize_count, 1)
        self.assertLessEqual(m.load_factor, 0.75)
        for i in range(7):
            self.assertEqual(m.get("k{}".format(i)), i)

    def test_keys_and_items(self):
        m = HashMap()
        expected = ["user:{}".format(i) for i in range(50)]
        for k in expected:
            m.put(k, k.upper())
        keys = m.keys()
        self.assertEqual(len(keys), 50)
        self.assertEqual(sorted(keys), sorted(expected))  # 테스트 검증용 정렬
        for k, v in m.items():
            self.assertEqual(v, k.upper())

    def test_randomized_against_reference(self):
        """무작위 연산 결과를 단순 참조 구현(리스트 탐색)과 비교한다."""
        rng = random.Random(7)
        m = HashMap()
        ref_keys, ref_vals = [], []
        for _ in range(3000):
            key = "k{}".format(rng.randint(0, 300))
            op = rng.random()
            if op < 0.6:
                val = rng.randint(0, 10**6)
                m.put(key, val)
                if key in ref_keys:
                    ref_vals[ref_keys.index(key)] = val
                else:
                    ref_keys.append(key)
                    ref_vals.append(val)
            elif op < 0.8:
                removed = m.remove(key)
                self.assertEqual(removed, key in ref_keys)
                if key in ref_keys:
                    i = ref_keys.index(key)
                    ref_keys.pop(i)
                    ref_vals.pop(i)
            else:
                expected = ref_vals[ref_keys.index(key)] if key in ref_keys else None
                self.assertEqual(m.get(key), expected)
        self.assertEqual(m.size(), len(ref_keys))


if __name__ == "__main__":
    unittest.main()
