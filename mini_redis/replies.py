"""Redis 스타일 응답 객체와 출력 포맷터.

명령어 처리 결과를 문자열로 바로 만들지 않고 "응답 타입"으로 반환한 뒤,
출력 형식은 ``render()`` 한 곳에서만 결정한다.

* 명령어 로직은 무엇을 돌려줄지만 신경 쓰고(OK / nil / 정수 / 문자열 / 배열 / 에러),
* 화면 표현(redis-cli 와 같은 ``(integer) 1``, ``(nil)`` 등)은 포맷터가 책임진다.
  → 출력 형식을 바꿔도 명령어 코드는 수정할 필요가 없다.
"""

from typing import Any, Iterable

from .structures.dynamic_array import DynamicArray


class Reply:
    """모든 응답의 기반 클래스."""


class SimpleString(Reply):
    """상태 문자열 (예: OK, PONG). 따옴표 없이 출력된다."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class Nil(Reply):
    """값 없음 → (nil)"""

    __slots__ = ()


class Integer(Reply):
    """정수 → (integer) N"""

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value


class BulkString(Reply):
    """문자열 값 → "value" (따옴표 + 이스케이프)"""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class Array(Reply):
    """배열 → 1) ... 2) ... / 비어 있으면 (empty array)"""

    __slots__ = ("items",)

    def __init__(self, items: Iterable[Any]) -> None:
        self.items = DynamicArray(items=items)


class ErrorReply(Reply):
    """에러 → (error) ERR ..."""

    __slots__ = ("message",)

    def __init__(self, message: str) -> None:
        self.message = message


class Verbatim(Reply):
    """INFO / DEBUG 처럼 여러 줄 텍스트를 그대로 보여주는 응답."""

    __slots__ = ("lines",)

    def __init__(self, lines: Iterable[str]) -> None:
        self.lines = DynamicArray(items=lines)


class NoReply(Reply):
    """출력할 내용이 없는 응답."""

    __slots__ = ()


OK = SimpleString("OK")
NIL = Nil()
NO_REPLY = NoReply()


def _quote(text: str) -> str:
    """redis-cli 처럼 문자열을 큰따옴표로 감싸고 특수문자를 이스케이프한다."""
    out = DynamicArray()
    for ch in text:
        if ch == '"' or ch == "\\":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\x{:02x}".format(ord(ch)))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def render(reply: Reply) -> str:
    """응답 객체를 redis-cli 스타일 문자열로 변환한다."""
    if isinstance(reply, SimpleString):
        return reply.text
    if isinstance(reply, Nil):
        return "(nil)"
    if isinstance(reply, Integer):
        return "(integer) {}".format(reply.value)
    if isinstance(reply, BulkString):
        return _quote(reply.text)
    if isinstance(reply, ErrorReply):
        return "(error) {}".format(reply.message)
    if isinstance(reply, Verbatim):
        return "\n".join(reply.lines)
    if isinstance(reply, NoReply):
        return ""
    if isinstance(reply, Array):
        if len(reply.items) == 0:
            return "(empty array)"
        lines = DynamicArray()
        for i, item in enumerate(reply.items, start=1):
            if isinstance(item, Reply):
                lines.append("{}) {}".format(i, render(item)))
            else:
                lines.append("{}) {}".format(i, _quote(str(item))))
        return "\n".join(lines)
    raise TypeError("unknown reply type: {!r}".format(reply))
