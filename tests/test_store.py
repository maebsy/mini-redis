import unittest

from mini_redis.store import OutOfMemoryError, Store, entry_size
from tests.helpers import FakeClock


def keys_of(store):
    return sorted(store.keys())


class MemoryAccountingTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = Store(clock=self.clock)

    def test_entry_size_uses_utf8_bytes(self):
        self.assertEqual(entry_size("user:1", "Alice"), 11)
        self.assertEqual(entry_size("이름", "철수"), 12)  # 한글 1자 = 3바이트

    def test_used_memory_tracks_set_overwrite_delete(self):
        s = self.store
        s.set("a", "123")          # 1 + 3
        self.assertEqual(s.used_memory, 4)
        s.set("a", "1")            # 덮어쓰기 → 1 + 1
        self.assertEqual(s.used_memory, 2)
        s.set("bb", "xyz")         # + 5
        self.assertEqual(s.used_memory, 7)
        s.delete("a")
        self.assertEqual(s.used_memory, 5)
        s.delete("bb")
        self.assertEqual(s.used_memory, 0)


class LruEvictionTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = Store(clock=self.clock)

    def test_mission_example(self):
        s = self.store
        s.set_maxmemory(30)
        s.set("user:1", "Alice")    # 11
        s.set("user:2", "Bob")      # 9  → 20
        s.set("user:3", "Charlie")  # 13 → 33 > 30 → user:1 제거
        self.assertIsNone(s.get("user:1"))
        self.assertEqual(s.used_memory, 22)
        self.assertEqual(s.evicted_keys, 1)
        self.assertEqual(keys_of(s), ["user:2", "user:3"])

    def test_get_refreshes_lru(self):
        s = self.store
        s.set_maxmemory(30)
        s.set("user:1", "Alice")
        s.set("user:2", "Bob")
        self.assertEqual(s.get("user:1"), "Alice")  # user:1 이 MRU 가 됨
        s.set("user:3", "Charlie")                  # 이제 LRU 는 user:2
        self.assertIsNone(s.get("user:2"))
        self.assertEqual(s.get("user:1"), "Alice")

    def test_exists_does_not_refresh_lru(self):
        s = self.store
        s.set_maxmemory(30)
        s.set("user:1", "Alice")
        s.set("user:2", "Bob")
        self.assertTrue(s.exists("user:1"))  # LRU 갱신 안 함
        s.set("user:3", "Charlie")
        self.assertFalse(s.exists("user:1"))
        self.assertTrue(s.exists("user:2"))

    def test_evicts_multiple_until_fits(self):
        s = self.store
        s.set_maxmemory(20)
        for i in range(4):
            s.set("k{}".format(i), "v")  # 각 3바이트 → 12
        s.set("big", "x" * 12)           # 15 → 27 > 20 → k0, k1, k2 순서로 제거
        self.assertEqual(s.used_memory, 18)
        self.assertEqual(s.evicted_keys, 3)
        self.assertEqual(keys_of(s), ["big", "k3"])

    def test_single_entry_larger_than_maxmemory_is_oom(self):
        s = self.store
        s.set_maxmemory(10)
        s.set("a", "1")
        with self.assertRaises(OutOfMemoryError):
            s.set("toolarge", "123")  # 11 > 10
        self.assertEqual(keys_of(s), ["a"])  # 기존 데이터 보존
        self.assertEqual(s.used_memory, 2)

    def test_overwrite_with_too_large_value_keeps_old_value(self):
        s = self.store
        s.set_maxmemory(10)
        s.set("k", "v")
        with self.assertRaises(OutOfMemoryError):
            s.set("k", "x" * 20)
        self.assertEqual(s.get("k"), "v")

    def test_lowering_maxmemory_evicts_immediately(self):
        s = self.store
        s.set("a", "1111")  # 5
        s.set("b", "2222")  # 5
        evicted = s.set_maxmemory(6)
        self.assertEqual(evicted, 1)
        self.assertEqual(keys_of(s), ["b"])
        self.assertLessEqual(s.used_memory, s.maxmemory)

    def test_zero_means_unlimited(self):
        s = self.store
        s.set_maxmemory(0)
        for i in range(100):
            s.set("key{}".format(i), "value")
        self.assertEqual(s.dbsize(), 100)
        self.assertEqual(s.evicted_keys, 0)

    def test_negative_maxmemory_rejected(self):
        with self.assertRaises(ValueError):
            self.store.set_maxmemory(-1)


class TtlTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = Store(clock=self.clock)

    def test_ttl_codes(self):
        s = self.store
        self.assertEqual(s.ttl("nope"), -2)
        s.set("k", "v")
        self.assertEqual(s.ttl("k"), -1)
        self.assertTrue(s.expire("k", 3))
        self.assertEqual(s.ttl("k"), 3)
        self.clock.advance(1.2)
        self.assertEqual(s.ttl("k"), 2)  # 1.8초 남음 → 올림 2

    def test_expire_missing_key_returns_false(self):
        self.assertFalse(self.store.expire("ghost", 10))

    def test_get_on_expired_key_deletes_and_returns_none(self):
        s = self.store
        s.set("k", "v")
        s.expire("k", 2)
        self.clock.advance(2)
        self.assertIsNone(s.get("k"))
        self.assertEqual(s.ttl("k"), -2)
        self.assertEqual(s.used_memory, 0)
        self.assertEqual(s.expired_keys, 1)

    def test_expired_get_does_not_touch_lru(self):
        s = self.store
        s.set("a", "1")
        s.set("b", "2")
        s.expire("a", 1)
        self.clock.advance(5)
        self.assertIsNone(s.get("a"))
        self.assertEqual(list(s.lru_order()), ["b"])

    def test_set_overwrite_clears_ttl(self):
        s = self.store
        s.set("k", "v")
        s.expire("k", 5)
        s.set("k", "v2")
        self.assertEqual(s.ttl("k"), -1)
        self.clock.advance(10)
        self.assertEqual(s.get("k"), "v2")  # 힙의 옛 항목은 stale → 무시

    def test_non_positive_seconds_expire_immediately(self):
        s = self.store
        s.set("k", "v")
        self.assertTrue(s.expire("k", 0))
        self.assertFalse(s.exists("k"))
        s.set("k2", "v")
        self.assertTrue(s.expire("k2", -5))
        self.assertEqual(s.dbsize(), 0)

    def test_active_expiration_uses_heap_order(self):
        s = self.store
        for i, sec in enumerate((5, 1, 3)):
            s.set("k{}".format(i), "v")
            s.expire("k{}".format(i), sec)
        self.clock.advance(3)
        self.assertEqual(s.expire_due_keys(), 2)  # 1초, 3초짜리 만료
        self.assertEqual(keys_of(s), ["k0"])

    def test_dbsize_and_keys_exclude_expired(self):
        s = self.store
        s.set("a", "1")
        s.set("b", "1")
        s.expire("a", 1)
        self.clock.advance(1)
        self.assertEqual(s.dbsize(), 1)
        self.assertEqual(keys_of(s), ["b"])

    def test_delete_then_reset_ignores_stale_heap_entry(self):
        s = self.store
        s.set("k", "v")
        s.expire("k", 1)
        s.delete("k")
        s.set("k", "new")
        self.clock.advance(2)
        self.assertEqual(s.get("k"), "new")

    def test_re_expire_extends_lifetime(self):
        s = self.store
        s.set("k", "v")
        s.expire("k", 1)
        s.expire("k", 10)
        self.clock.advance(2)
        self.assertEqual(s.get("k"), "v")
        self.assertEqual(s.ttl("k"), 8)

    def test_persist_removes_ttl(self):
        s = self.store
        s.set("k", "v")
        s.expire("k", 1)
        self.assertTrue(s.persist("k"))
        self.clock.advance(5)
        self.assertEqual(s.get("k"), "v")
        self.assertFalse(s.persist("k"))

    def test_heap_compaction_keeps_live_entries(self):
        s = self.store
        s.set("k", "v")
        for i in range(500):  # 같은 키에 EXPIRE 반복 → stale 항목 누적
            s.expire("k", 100 + i)
        self.assertLessEqual(s.ttl_heap_size, 130)  # 주기적으로 재구성됨
        self.assertEqual(s.ttl_key_count, 1)
        self.clock.advance(598)
        self.assertEqual(s.get("k"), "v")
        self.clock.advance(2)
        self.assertIsNone(s.get("k"))

    def test_ttl_key_count_bookkeeping(self):
        s = self.store
        s.set("a", "1")
        s.set("b", "1")
        s.expire("a", 10)
        s.expire("b", 10)
        self.assertEqual(s.ttl_key_count, 2)
        s.set("a", "2")       # TTL 초기화
        s.delete("b")         # TTL 키 삭제
        self.assertEqual(s.ttl_key_count, 0)


class ConsistencyTest(unittest.TestCase):
    def test_invariants_under_random_workload(self):
        import random
        rng = random.Random(2024)
        clock = FakeClock()
        s = Store(clock=clock)
        s.set_maxmemory(200)
        for step in range(5000):
            key = "k{}".format(rng.randint(0, 60))
            op = rng.random()
            if op < 0.45:
                s.set(key, "v" * rng.randint(0, 20))
            elif op < 0.65:
                s.get(key)
            elif op < 0.75:
                s.delete(key)
            elif op < 0.9:
                s.expire(key, rng.randint(-1, 5))
            else:
                clock.advance(rng.random() * 2)
            s.expire_due_keys()
            # 불변식 1: used_memory == 살아있는 엔트리 크기 합
            total = sum(entry_size(k, s.hashmap.get(k).value) for k in s.hashmap)
            self.assertEqual(s.used_memory, total, "step {}".format(step))
            # 불변식 2: 메모리 한도 준수
            self.assertLessEqual(s.used_memory, s.maxmemory)
            # 불변식 3: 해시맵 키 == LRU 리스트 키
            self.assertEqual(sorted(s.hashmap), sorted(s.lru_order()))


if __name__ == "__main__":
    unittest.main()
