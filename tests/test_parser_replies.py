import unittest

from mini_redis import replies as R
from mini_redis.parser import ParseError, tokenize


class TokenizerTest(unittest.TestCase):
    def test_plain_tokens(self):
        self.assertEqual(tokenize("SET user:1 Alice"), ["SET", "user:1", "Alice"])
        self.assertEqual(tokenize("   GET   k  "), ["GET", "k"])
        self.assertEqual(tokenize(""), [])

    def test_double_quotes_with_spaces_and_escapes(self):
        self.assertEqual(tokenize('SET k "Alice Kim"'), ["SET", "k", "Alice Kim"])
        self.assertEqual(tokenize(r'SET k "say \"hi\""'), ["SET", "k", 'say "hi"'])
        self.assertEqual(tokenize(r'SET k "a\nb\x41"'), ["SET", "k", "a\nbA"])
        self.assertEqual(tokenize('SET k ""'), ["SET", "k", ""])

    def test_single_quotes(self):
        self.assertEqual(tokenize("SET k 'it\\'s ok'"), ["SET", "k", "it's ok"])

    def test_unicode(self):
        self.assertEqual(tokenize('SET 이름 "홍 길동"'), ["SET", "이름", "홍 길동"])

    def test_errors(self):
        with self.assertRaises(ParseError):
            tokenize('SET k "unclosed')
        with self.assertRaises(ParseError):
            tokenize('SET k "a"b')


class RenderTest(unittest.TestCase):
    def test_basic_types(self):
        self.assertEqual(R.render(R.OK), "OK")
        self.assertEqual(R.render(R.NIL), "(nil)")
        self.assertEqual(R.render(R.Integer(3)), "(integer) 3")
        self.assertEqual(R.render(R.BulkString("Alice")), '"Alice"')
        self.assertEqual(R.render(R.ErrorReply("ERR x")), "(error) ERR x")

    def test_bulk_escaping(self):
        self.assertEqual(R.render(R.BulkString('a"b\\c\n')), r'"a\"b\\c\n"')

    def test_array(self):
        self.assertEqual(R.render(R.Array([])), "(empty array)")
        self.assertEqual(R.render(R.Array([R.BulkString("a"), R.Integer(1)])), '1) "a"\n2) (integer) 1')


if __name__ == "__main__":
    unittest.main()
