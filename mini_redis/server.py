"""명령어 디스패처.

한 줄 입력이 처리되는 흐름

    입력 문자열 ──tokenize──▶ 토큰 배열 ──lookup──▶ CommandSpec ──arity 검사──▶ handler
                                                                                   │
    화면 출력 ◀──render── Reply ◀──────────────────────────────────────────────────┘

* 명령어 테이블도 직접 만든 ``HashMap[명령어 이름 -> CommandSpec]`` 을 사용한다(내장 dict 미사용).
* 명령어 이름은 대소문자를 구분하지 않는다(대문자로 정규화해서 조회).
* 모든 명령어 실행 직전에 ``store.expire_due_keys()`` 로 만료 키를 정리한다(active expiration).
* 에러는 ``CommandError`` 로 올리고 한 곳에서 ``(error) ...`` 응답으로 바꾼다.
"""

import time
from typing import Callable, List, Optional

from . import replies as R
from .parser import ParseError, tokenize
from .pubsub import Client, PubSub
from .store import OutOfMemoryError, Store
from .structures.bst import BinarySearchTree
from .structures.binary_tree import BinaryTree
from .structures.dynamic_array import DynamicArray
from .structures.hashmap import HashMap
from .structures.stack_queue_deque import Deque

# ---------------------------------------------------------------- 표준 에러 메시지
ERR_UNKNOWN = "ERR unknown command '{}'"
ERR_ARITY = "ERR wrong number of arguments for '{}' command"
ERR_NOT_INT = "ERR value is not an integer or out of range"
ERR_OOM = "OOM command not allowed when used_memory > 'maxmemory'"
ERR_SYNTAX = "ERR syntax error"
ERR_PROTOCOL = "ERR Protocol error: unbalanced quotes in request"

DEFAULT_CLIENT = "default"
HISTORY_SIZE = 100


class CommandError(Exception):
    """명령 실행 중 사용자에게 보여줄 에러. 메시지는 'ERR ...' 형식."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CommandSpec:
    """명령어 메타데이터. max_args 가 None 이면 개수 제한 없음."""

    __slots__ = ("name", "handler", "min_args", "max_args", "syntax", "summary", "group")

    def __init__(self, name, handler, min_args, max_args, syntax, summary, group):
        self.name = name
        self.handler = handler
        self.min_args = min_args
        self.max_args = max_args
        self.syntax = syntax
        self.summary = summary
        self.group = group  # "core" | "extension" | "bonus"


def parse_int(text: str) -> int:
    """Redis 와 같은 엄격한 정수 파싱: 공백·소수점·'+' 기호 불허."""
    body = text[1:] if text.startswith("-") else text
    if not body or not body.isdigit() or not body.isascii():
        raise CommandError(ERR_NOT_INT)
    if len(body) > 1 and body[0] == "0":
        raise CommandError(ERR_NOT_INT)  # '007' 같은 표기 거부 (Redis 동작과 동일)
    return int(text)


class Server:
    """Store / PubSub / 히스토리 / 클라이언트를 묶어 명령어를 실행한다."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = Store(clock=clock)
        self.pubsub = PubSub()
        self.history = Deque(maxlen=HISTORY_SIZE)
        self.clients = HashMap()
        self.current = Client(DEFAULT_CLIENT)
        self.clients.put(DEFAULT_CLIENT, self.current)
        self.commands_processed = 0
        self._sleep = sleep
        self._commands = HashMap()
        self._register_commands()

    # ================================================================ 실행 진입점
    def prompt(self) -> str:
        if self.current.name == DEFAULT_CLIENT:
            return "mini-redis> "
        return "mini-redis({})> ".format(self.current.name)

    def execute_line(self, line: str) -> str:
        """한 줄을 실행하고 화면에 출력할 문자열을 반환한다."""
        try:
            tokens = tokenize(line)
        except ParseError:
            return R.render(R.ErrorReply(ERR_PROTOCOL))
        if not tokens:
            return ""
        self.history.append(line.strip())
        output = R.render(self.execute(tokens))
        pending = self.render_pending_messages()
        if pending:
            output = pending if not output else output + "\n" + pending
        return output

    def execute(self, tokens: List[str]) -> R.Reply:
        """토큰 배열을 실행해 응답 객체를 반환한다."""
        typed = tokens[0]
        args = tokens[1:]
        spec = self._commands.get(typed.upper())
        if spec is None:
            return R.ErrorReply(ERR_UNKNOWN.format(typed))
        if len(args) < spec.min_args or (spec.max_args is not None and len(args) > spec.max_args):
            return R.ErrorReply(ERR_ARITY.format(typed))
        self.commands_processed += 1
        self.store.expire_due_keys()  # active expiration: 힙 루트부터 만료된 키 정리
        try:
            return spec.handler(typed, args)
        except CommandError as exc:
            return R.ErrorReply(exc.message)

    def render_pending_messages(self) -> str:
        """현재 클라이언트 inbox 에 쌓인 Pub/Sub 메시지를 redis-cli 형식으로 만든다."""
        messages = self.current.drain()
        if len(messages) == 0:
            return ""
        blocks = DynamicArray()
        for channel, message in messages:
            blocks.append(R.render(R.Array([R.BulkString("message"), R.BulkString(channel), R.BulkString(message)])))
        return "\n".join(blocks)

    # ================================================================ 등록
    def _add(self, name, handler, min_args, max_args, syntax, summary, group="core"):
        self._commands.put(name, CommandSpec(name, handler, min_args, max_args, syntax, summary, group))

    def _register_commands(self) -> None:
        # 필수 명령어
        self._add("SET", self._cmd_set, 2, 2, "SET key value", "키에 값 저장 (기존 TTL 초기화)")
        self._add("GET", self._cmd_get, 1, 1, "GET key", "값 조회 (성공 시 LRU 갱신)")
        self._add("DEL", self._cmd_del, 1, None, "DEL key [key ...]", "키 삭제, 삭제한 개수 반환")
        self._add("EXISTS", self._cmd_exists, 1, None, "EXISTS key [key ...]", "존재하는 키 개수 반환")
        self._add("DBSIZE", self._cmd_dbsize, 0, 0, "DBSIZE", "전체 키 개수")
        self._add("KEYS", self._cmd_keys, 0, 1, "KEYS [*]", "전체 키 목록 (패턴 미지원)")
        self._add("CONFIG", self._cmd_config, 1, None, "CONFIG SET maxmemory <bytes> | CONFIG GET maxmemory", "최대 메모리 설정/조회")
        self._add("INFO", self._cmd_info, 0, 1, "INFO [memory|stats|keyspace]", "서버 상태 정보")
        self._add("EXPIRE", self._cmd_expire, 2, 2, "EXPIRE key seconds", "만료 시간(초) 설정")
        self._add("TTL", self._cmd_ttl, 1, 1, "TTL key", "남은 만료 시간(-2: 없음, -1: 만료 없음)")
        # 확장 명령어 (설명/시연 편의)
        self._add("PING", self._cmd_ping, 0, 1, "PING [message]", "연결 확인", "extension")
        self._add("PERSIST", self._cmd_persist, 1, 1, "PERSIST key", "TTL 제거", "extension")
        self._add("FLUSHALL", self._cmd_flushall, 0, 0, "FLUSHALL", "모든 키 삭제 (설정은 유지)", "extension")
        self._add("DEBUG", self._cmd_debug, 1, None, "DEBUG HELP", "내부 자료구조 상태 확인", "extension")
        self._add("HELP", self._cmd_help, 0, 1, "HELP [command]", "명령어 도움말", "extension")
        # 보너스 명령어
        self._add("HISTORY", self._cmd_history, 0, 1, "HISTORY [count]", "최근 명령어 (Deque 기반)", "bonus")
        self._add("PUBLISH", self._cmd_publish, 2, 2, "PUBLISH channel message", "채널에 메시지 발행", "bonus")
        self._add("SUBSCRIBE", self._cmd_subscribe, 1, None, "SUBSCRIBE channel [channel ...]", "채널 구독", "bonus")
        self._add("UNSUBSCRIBE", self._cmd_unsubscribe, 0, None, "UNSUBSCRIBE [channel ...]", "구독 해제", "bonus")
        self._add("CLIENT", self._cmd_client, 1, 2, "CLIENT SWITCH name | CLIENT LIST | CLIENT GETNAME", "가상 클라이언트 전환/조회", "bonus")

    # ================================================================ 필수 명령어
    def _cmd_set(self, typed: str, args: List[str]) -> R.Reply:
        try:
            self.store.set(args[0], args[1])
        except OutOfMemoryError:
            raise CommandError(ERR_OOM)
        return R.OK

    def _cmd_get(self, typed: str, args: List[str]) -> R.Reply:
        value = self.store.get(args[0])
        return R.NIL if value is None else R.BulkString(value)

    def _cmd_del(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(sum(1 for key in args if self.store.delete(key)))

    def _cmd_exists(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(sum(1 for key in args if self.store.exists(key)))

    def _cmd_dbsize(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(self.store.dbsize())

    def _cmd_keys(self, typed: str, args: List[str]) -> R.Reply:
        if args and args[0] != "*":
            raise CommandError("ERR pattern matching is not supported (use KEYS or KEYS *)")
        return R.Array(R.BulkString(k) for k in self.store.keys())

    def _cmd_config(self, typed: str, args: List[str]) -> R.Reply:
        sub = args[0].upper()
        if sub == "SET":
            if len(args) != 3:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            if args[1].lower() != "maxmemory":
                raise CommandError("ERR Unknown option or number of arguments for CONFIG SET - '{}'".format(args[1]))
            limit = parse_int(args[2])
            if limit < 0:
                raise CommandError(ERR_NOT_INT)
            self.store.set_maxmemory(limit)
            return R.OK
        if sub == "GET":
            if len(args) != 2:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            if args[1].lower() != "maxmemory":
                return R.Array([])
            return R.Array([R.BulkString("maxmemory"), R.BulkString(str(self.store.maxmemory))])
        raise CommandError("ERR unknown subcommand '{}'. Try CONFIG SET or CONFIG GET.".format(args[0]))

    def _cmd_info(self, typed: str, args: List[str]) -> R.Reply:
        section = args[0].lower() if args else "all"
        s = self.store
        memory = [
            "# Memory",
            "used_memory:{}".format(s.used_memory),
            "maxmemory:{}".format(s.maxmemory),
            "maxmemory_policy:allkeys-lru",
            "evicted_keys:{}".format(s.evicted_keys),
        ]
        stats = [
            "# Stats",
            "total_commands_processed:{}".format(self.commands_processed),
            "expired_keys:{}".format(s.expired_keys),
            "evicted_keys:{}".format(s.evicted_keys),
            "pubsub_channels:{}".format(self.pubsub.channels.size()),
        ]
        keyspace = [
            "# Keyspace",
            "db0:keys={},expires={}".format(s.dbsize(), s.ttl_key_count),
        ]
        if section == "memory":
            return R.Verbatim(memory)
        if section == "stats":
            return R.Verbatim(stats)
        if section == "keyspace":
            return R.Verbatim(keyspace)
        if section in ("all", "everything", "default"):
            return R.Verbatim(memory + [""] + stats + [""] + keyspace)
        raise CommandError("ERR unsupported INFO section '{}' (memory|stats|keyspace)".format(args[0]))

    def _cmd_expire(self, typed: str, args: List[str]) -> R.Reply:
        seconds = parse_int(args[1])
        return R.Integer(1 if self.store.expire(args[0], seconds) else 0)

    def _cmd_ttl(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(self.store.ttl(args[0]))

    # ================================================================ 확장 명령어
    def _cmd_ping(self, typed: str, args: List[str]) -> R.Reply:
        return R.BulkString(args[0]) if args else R.SimpleString("PONG")

    def _cmd_persist(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(1 if self.store.persist(args[0]) else 0)

    def _cmd_flushall(self, typed: str, args: List[str]) -> R.Reply:
        maxmemory = self.store.maxmemory
        evicted, expired = self.store.evicted_keys, self.store.expired_keys
        self.store = Store(clock=self.store.clock)  # 같은 시계 재사용
        self.store.maxmemory = maxmemory
        self.store.evicted_keys, self.store.expired_keys = evicted, expired
        return R.OK

    def _cmd_help(self, typed: str, args: List[str]) -> R.Reply:
        if args:
            spec = self._commands.get(args[0].upper())
            if spec is None:
                raise CommandError(ERR_UNKNOWN.format(args[0]))
            return R.Verbatim(["{}  — {}".format(spec.syntax, spec.summary)])
        groups = (("core", "필수 명령어"), ("extension", "확장 명령어"), ("bonus", "보너스 명령어"))
        lines = DynamicArray()
        for group, title in groups:
            lines.append("# " + title)
            specs = DynamicArray()
            for name in self._commands:
                spec = self._commands.get(name)
                if spec.group == group:
                    specs.append(spec)
            # 이름순 출력 (BST 중위 순회 = 정렬)
            tree = BinarySearchTree()
            for spec in specs:
                tree.insert(spec.name, spec)
            for _, spec in tree.inorder():
                lines.append("  {:<44} {}".format(spec.syntax, spec.summary))
            lines.append("")
        lines.append("exit | quit  — 종료")
        return R.Verbatim(lines)

    def _cmd_debug(self, typed: str, args: List[str]) -> R.Reply:
        sub = args[0].upper()
        s = self.store
        if sub == "HELP":
            return R.Verbatim([
                "DEBUG HASHMAP            해시맵 용량/로드 팩터/체인 길이",
                "DEBUG LRU                LRU 순서 (MRU → LRU)",
                "DEBUG TTLHEAP            TTL 최소 힙을 완전 이진 트리로 출력 (보너스: 이진 트리)",
                "DEBUG SORTEDKEYS         키를 정렬해서 출력 (보너스: BST 중위 순회)",
                "DEBUG RANGEKEYS lo hi    lo <= key <= hi 범위 조회 (보너스: BST)",
                "DEBUG SLEEP seconds      지정한 초만큼 대기 (TTL 시연용)",
                "DEBUG EVICTIONS [count]  최근 LRU 제거 기록 (최신순, 최대 16개)",
            ])
        if sub == "HASHMAP":
            hm = s.hashmap
            used, longest, avg = hm.chain_stats()
            return R.Verbatim([
                "hash_function:FNV-1a 64-bit",
                "collision_strategy:separate chaining (doubly linked list)",
                "size:{}".format(hm.size()),
                "capacity:{}".format(hm.capacity),
                "load_factor:{:.3f}".format(hm.load_factor),
                "max_load_factor:{}".format(hm.MAX_LOAD_FACTOR),
                "resize_count:{}".format(hm.resize_count),
                "used_buckets:{}".format(used),
                "longest_chain:{}".format(longest),
                "avg_chain_length:{:.2f}".format(avg),
            ])
        if sub == "LRU":
            return R.Array(R.BulkString(k) for k in s.lru_order())
        if sub == "TTLHEAP":
            snapshot = s.ttl_heap_snapshot()
            now = s.now()
            lines = DynamicArray()
            stale = len(snapshot) - s.ttl_key_count
            lines.append("heap_size:{} live_ttl_keys:{} stale_entries:{}".format(len(snapshot), s.ttl_key_count, stale))
            tree = BinaryTree.from_level_order(snapshot)
            for line in tree.render(lambda item: "{} (in {:.1f}s)".format(item[1], item[0] - now)):
                lines.append(line)
            return R.Verbatim(lines)
        if sub == "SORTEDKEYS":
            tree = BinarySearchTree()
            for key in s.keys():
                tree.insert(key)
            return R.Array(R.BulkString(k) for k in tree.keys())
        if sub == "RANGEKEYS":
            if len(args) != 3:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            tree = BinarySearchTree()
            for key in s.keys():
                tree.insert(key)
            return R.Array(R.BulkString(k) for k in tree.range(args[1], args[2]))
        if sub == "SLEEP":
            if len(args) != 2:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            try:
                seconds = float(args[1])
            except ValueError:
                raise CommandError("ERR value is not a valid float")
            if seconds < 0:
                raise CommandError("ERR value is not a valid float")
            self._sleep(seconds)
            return R.OK
        if sub == "EVICTIONS":
            if len(args) > 2:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            items = DynamicArray(items=s.recent_evictions)  # front=오래된 것 → back=최신
            count = len(items)
            if len(args) == 2:
                count = parse_int(args[1])
                if count < 1:
                    raise CommandError("ERR count must be positive")
            now = s.now()
            lines = DynamicArray()
            lines.append("evicted_keys:{} recent_logged:{} (최대 16개 보관, FLUSHALL 시 초기화)".format(
                s.evicted_keys, len(items)))
            if len(items) == 0:
                lines.append("(empty)")
            else:
                shown = 0
                for i in range(len(items) - 1, -1, -1):  # 최신순
                    if shown >= count:
                        break
                    key, size, evicted_at = items[i]
                    lines.append("{}) {} ({} bytes, {:.1f}s ago)".format(shown + 1, key, size, now - evicted_at))
                    shown += 1
            return R.Verbatim(lines)
        raise CommandError("ERR unknown subcommand '{}'. Try DEBUG HELP.".format(args[0]))

    # ================================================================ 보너스 명령어
    def _cmd_history(self, typed: str, args: List[str]) -> R.Reply:
        count = parse_int(args[0]) if args else 10
        if count <= 0:
            raise CommandError(ERR_NOT_INT)
        items = DynamicArray(items=self.history)
        start = max(0, len(items) - count)
        return R.Array(R.BulkString(items[i]) for i in range(start, len(items)))

    def _cmd_publish(self, typed: str, args: List[str]) -> R.Reply:
        return R.Integer(self.pubsub.publish(args[0], args[1]))

    def _cmd_subscribe(self, typed: str, args: List[str]) -> R.Reply:
        items = DynamicArray()
        for channel in args:
            count = self.pubsub.subscribe(self.current, channel)
            items.append(R.BulkString("subscribe"))
            items.append(R.BulkString(channel))
            items.append(R.Integer(count))
        return R.Array(items)

    def _cmd_unsubscribe(self, typed: str, args: List[str]) -> R.Reply:
        channels = args if args else list(self.pubsub.subscribed_channels(self.current))
        items = DynamicArray()
        for channel in channels:
            count = self.pubsub.unsubscribe(self.current, channel)
            items.append(R.BulkString("unsubscribe"))
            items.append(R.BulkString(channel))
            items.append(R.Integer(count))
        if len(items) == 0:  # 구독 중인 채널이 없을 때 (Redis 와 동일한 형태)
            items.append(R.BulkString("unsubscribe"))
            items.append(R.NIL)
            items.append(R.Integer(0))
        return R.Array(items)

    def _cmd_client(self, typed: str, args: List[str]) -> R.Reply:
        sub = args[0].upper()
        if sub == "SWITCH":
            if len(args) != 2:
                raise CommandError(ERR_ARITY.format(typed + " " + args[0]))
            name = args[1]
            client: Optional[Client] = self.clients.get(name)
            if client is None:
                client = Client(name)
                self.clients.put(name, client)
            self.current = client
            return R.OK
        if sub == "GETNAME":
            return R.BulkString(self.current.name)
        if sub == "LIST":
            lines = DynamicArray()
            for name in self.clients:
                c = self.clients.get(name)
                marker = "*" if c is self.current else " "
                lines.append("{} name={} sub={} pending={}".format(marker, c.name, c.subscription_count(), len(c.inbox)))
            return R.Verbatim(lines)
        raise CommandError("ERR unknown subcommand '{}'. Try CLIENT SWITCH|LIST|GETNAME.".format(args[0]))
