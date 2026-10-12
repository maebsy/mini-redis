import io
import unittest

from mini_redis.repl import run
from mini_redis.server import Server
from tests.helpers import FakeClock


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.server = Server(clock=self.clock, sleep=self.clock.sleep)

    def run_cmd(self, line):
        return self.server.execute_line(line)


class StringCommandsTest(ServerTestCase):
    def test_set_get_del_exists_dbsize_keys(self):
        self.assertEqual(self.run_cmd('SET user:1 "Alice"'), "OK")
        self.assertEqual(self.run_cmd("GET user:1"), '"Alice"')
        self.assertEqual(self.run_cmd("GET nope"), "(nil)")
        self.assertEqual(self.run_cmd("EXISTS user:1"), "(integer) 1")
        self.assertEqual(self.run_cmd("EXISTS nope"), "(integer) 0")
        self.assertEqual(self.run_cmd("DBSIZE"), "(integer) 1")
        self.assertEqual(self.run_cmd("KEYS"), '1) "user:1"')
        self.assertEqual(self.run_cmd("DEL user:1"), "(integer) 1")
        self.assertEqual(self.run_cmd("DEL user:1"), "(integer) 0")
        self.assertEqual(self.run_cmd("KEYS"), "(empty array)")

    def test_commands_are_case_insensitive(self):
        self.assertEqual(self.run_cmd("set a 1"), "OK")
        self.assertEqual(self.run_cmd("gEt a"), '"1"')

    def test_multi_key_del_and_exists(self):
        self.run_cmd("SET a 1")
        self.run_cmd("SET b 2")
        self.assertEqual(self.run_cmd("EXISTS a b c"), "(integer) 2")
        self.assertEqual(self.run_cmd("DEL a b c"), "(integer) 2")

    def test_keys_star_and_pattern(self):
        self.run_cmd("SET a 1")
        self.assertEqual(self.run_cmd("KEYS *"), '1) "a"')
        self.assertTrue(self.run_cmd("KEYS user:*").startswith("(error)"))


class ErrorFormatTest(ServerTestCase):
    def test_standard_errors(self):
        self.assertEqual(self.run_cmd("HELLO"), "(error) ERR unknown command 'HELLO'")
        self.assertEqual(self.run_cmd("GET"), "(error) ERR wrong number of arguments for 'GET' command")
        self.assertEqual(self.run_cmd("SET onlykey"), "(error) ERR wrong number of arguments for 'SET' command")
        self.assertEqual(self.run_cmd("CONFIG SET maxmemory abc"),
                         "(error) ERR value is not an integer or out of range")
        self.assertEqual(self.run_cmd("CONFIG SET maxmemory -1"),
                         "(error) ERR value is not an integer or out of range")
        self.assertEqual(self.run_cmd("EXPIRE k 1.5"), "(error) ERR value is not an integer or out of range")

    def test_oom_error(self):
        self.run_cmd("CONFIG SET maxmemory 5")
        self.assertEqual(self.run_cmd("SET toolong value"),
                         "(error) OOM command not allowed when used_memory > 'maxmemory'")

    def test_unbalanced_quotes(self):
        self.assertTrue(self.run_cmd('SET k "abc').startswith("(error) ERR Protocol error"))

    def test_config_subcommand_errors(self):
        self.assertIn("ERR wrong number of arguments", self.run_cmd("CONFIG SET maxmemory"))
        self.assertIn("Unknown option", self.run_cmd("CONFIG SET maxclients 3"))
        self.assertIn("unknown subcommand", self.run_cmd("CONFIG RESET"))


class MemoryAndTtlCommandsTest(ServerTestCase):
    def test_mission_example_transcript(self):
        self.assertEqual(self.run_cmd("CONFIG SET maxmemory 30"), "OK")
        self.run_cmd('SET user:1 "Alice"')
        self.run_cmd('SET user:2 "Bob"')
        self.run_cmd('SET user:3 "Charlie"')
        self.assertEqual(self.run_cmd("GET user:1"), "(nil)")
        info = self.run_cmd("INFO memory")
        self.assertIn("used_memory:22", info)
        self.assertIn("maxmemory:30", info)
        self.assertIn("evicted_keys:1", info)
        self.assertEqual(self.run_cmd("EXPIRE user:2 3"), "(integer) 1")
        self.clock.advance(1)
        self.assertEqual(self.run_cmd("TTL user:2"), "(integer) 2")
        self.clock.advance(2)
        self.assertEqual(self.run_cmd("GET user:2"), "(nil)")
        self.assertEqual(self.run_cmd("TTL user:2"), "(integer) -2")

    def test_ttl_minus_one_and_expire_missing(self):
        self.run_cmd("SET k v")
        self.assertEqual(self.run_cmd("TTL k"), "(integer) -1")
        self.assertEqual(self.run_cmd("EXPIRE ghost 5"), "(integer) 0")

    def test_config_get(self):
        self.run_cmd("CONFIG SET maxmemory 100")
        self.assertEqual(self.run_cmd("CONFIG GET maxmemory"), '1) "maxmemory"\n2) "100"')

    def test_debug_sleep_advances_fake_clock(self):
        self.run_cmd("SET k v")
        self.run_cmd("EXPIRE k 2")
        self.assertEqual(self.run_cmd("DEBUG SLEEP 2"), "OK")
        self.assertEqual(self.run_cmd("EXISTS k"), "(integer) 0")


class DebugAndExtensionTest(ServerTestCase):
    def test_debug_hashmap_and_lru(self):
        self.run_cmd("SET a 1")
        self.run_cmd("SET b 2")
        self.run_cmd("GET a")
        self.assertEqual(self.run_cmd("DEBUG LRU"), '1) "a"\n2) "b"')
        stats = self.run_cmd("DEBUG HASHMAP")
        self.assertIn("hash_function:FNV-1a 64-bit", stats)
        self.assertIn("size:2", stats)

    def test_debug_sorted_and_range_keys(self):
        for key in ("m", "c", "x", "a", "q"):
            self.run_cmd("SET {} 1".format(key))
        self.assertEqual(self.run_cmd("DEBUG SORTEDKEYS"), '1) "a"\n2) "c"\n3) "m"\n4) "q"\n5) "x"')
        self.assertEqual(self.run_cmd("DEBUG RANGEKEYS c q"), '1) "c"\n2) "m"\n3) "q"')

    def test_debug_ttlheap_renders_tree(self):
        for i, sec in enumerate((30, 10, 20)):
            self.run_cmd("SET k{} v".format(i))
            self.run_cmd("EXPIRE k{} {}".format(i, sec))
        out = self.run_cmd("DEBUG TTLHEAP")
        first_tree_line = out.splitlines()[1]
        self.assertTrue(first_tree_line.startswith("k1"))  # 10초짜리가 루트(최솟값)

    def test_help_lists_groups(self):
        out = self.run_cmd("HELP")
        self.assertIn("# 필수 명령어", out)
        self.assertIn("# 보너스 명령어", out)
        self.assertIn("SET key value", self.run_cmd("HELP set"))

    def test_ping_persist_flushall(self):
        self.assertEqual(self.run_cmd("PING"), "PONG")
        self.run_cmd("CONFIG SET maxmemory 50")
        self.run_cmd("SET k v")
        self.run_cmd("EXPIRE k 5")
        self.assertEqual(self.run_cmd("PERSIST k"), "(integer) 1")
        self.assertEqual(self.run_cmd("FLUSHALL"), "OK")
        self.assertEqual(self.run_cmd("DBSIZE"), "(integer) 0")
        self.assertIn("maxmemory:50", self.run_cmd("INFO memory"))


class BonusCommandsTest(ServerTestCase):
    def test_pubsub_between_virtual_clients(self):
        self.run_cmd("CLIENT SWITCH alice")
        self.assertEqual(self.run_cmd("SUBSCRIBE news"), '1) "subscribe"\n2) "news"\n3) (integer) 1')
        self.run_cmd("CLIENT SWITCH bob")
        self.run_cmd("SUBSCRIBE news sports")
        self.run_cmd("CLIENT SWITCH default")
        self.assertEqual(self.run_cmd('PUBLISH news "hello all"'), "(integer) 2")
        self.assertEqual(self.run_cmd("PUBLISH sports goal"), "(integer) 1")
        self.assertEqual(self.run_cmd("PUBLISH empty x"), "(integer) 0")
        # alice 로 전환하면 쌓여 있던 메시지가 출력된다
        out = self.run_cmd("CLIENT SWITCH alice")
        self.assertEqual(out, 'OK\n1) "message"\n2) "news"\n3) "hello all"')
        out = self.run_cmd("CLIENT SWITCH bob")
        self.assertIn('3) "hello all"', out)
        self.assertIn('3) "goal"', out)
        # 구독 해제 후에는 받지 않는다
        self.run_cmd("UNSUBSCRIBE news")
        self.run_cmd("CLIENT SWITCH default")
        self.assertEqual(self.run_cmd("PUBLISH news again"), "(integer) 1")

    def test_self_subscribed_client_sees_message_immediately(self):
        self.run_cmd("SUBSCRIBE ch")
        out = self.run_cmd("PUBLISH ch hi")
        self.assertEqual(out, '(integer) 1\n1) "message"\n2) "ch"\n3) "hi"')

    def test_unsubscribe_all_and_none(self):
        self.run_cmd("SUBSCRIBE a b")
        out = self.run_cmd("UNSUBSCRIBE")
        self.assertIn('2) "a"', out)
        self.assertIn('(integer) 0', out)
        self.assertEqual(self.run_cmd("UNSUBSCRIBE"), '1) "unsubscribe"\n2) (nil)\n3) (integer) 0')

    def test_history_uses_bounded_deque(self):
        for i in range(3):
            self.run_cmd("SET k{} v".format(i))
        out = self.run_cmd("HISTORY 2")
        self.assertEqual(out, '1) "SET k2 v"\n2) "HISTORY 2"')

    def test_client_list(self):
        self.run_cmd("CLIENT SWITCH alice")
        out = self.run_cmd("CLIENT LIST")
        self.assertIn("* name=alice", out)
        self.assertIn("name=default", out)


class ReplTest(unittest.TestCase):
    def test_piped_session_echoes_prompt_and_stops_on_exit(self):
        clock = FakeClock()
        server = Server(clock=clock, sleep=clock.sleep)
        stdin = io.StringIO("# comment\nSET a 1\n\nGET a\nquit\nGET a\n")
        stdout = io.StringIO()
        self.assertEqual(run(server, stdin=stdin, stdout=stdout, interactive=False), 0)
        self.assertEqual(stdout.getvalue().splitlines(), [
            "mini-redis> # comment",
            "mini-redis> SET a 1",
            "OK",
            "mini-redis> ",
            "mini-redis> GET a",
            '"1"',
            "mini-redis> quit",
        ])


if __name__ == "__main__":
    unittest.main()
