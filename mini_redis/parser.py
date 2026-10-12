"""명령줄 토크나이저.

redis-cli 와 같은 규칙으로 한 줄을 인자 목록으로 나눈다.

* 공백으로 인자를 구분한다.
* ``"큰따옴표"`` 안에서는 공백을 포함할 수 있고 ``\\"`` ``\\\\`` ``\\n`` ``\\t`` ``\\r`` ``\\xHH`` 이스케이프를 지원한다.
* ``'작은따옴표'`` 안은 그대로 쓰고 ``\\'`` 만 이스케이프한다.
* 닫는 따옴표 바로 뒤에는 공백이나 줄 끝이 와야 한다(``"a"b`` 는 오류).
* ``""`` 는 빈 문자열 인자다.

예) ``SET user:1 "Alice Kim"`` → ``['SET', 'user:1', 'Alice Kim']``
"""

from typing import List


class ParseError(Exception):
    """따옴표 짝이 맞지 않는 등 명령줄을 해석할 수 없을 때 발생한다."""


_HEX = "0123456789abcdefABCDEF"
_ESCAPE_KEYS = "nrtba"            # \n \r \t \b \a
_ESCAPE_VALUES = "\n\r\t\b\a"


def tokenize(line: str) -> List[str]:
    """명령줄을 토큰 배열로 변환한다. (list 는 '배열' 용도로만 사용)"""
    tokens: List[str] = []
    i, n = 0, len(line)
    while True:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            return tokens

        buf: List[str] = []
        in_double = in_single = False
        while True:
            if in_double:
                if i >= n:
                    raise ParseError("unbalanced quotes")
                ch = line[i]
                if ch == "\\" and i + 1 < n:
                    nxt = line[i + 1]
                    if nxt == "x" and i + 3 < n and line[i + 2] in _HEX and line[i + 3] in _HEX:
                        buf.append(chr(int(line[i + 2:i + 4], 16)))
                        i += 4
                        continue
                    pos = _ESCAPE_KEYS.find(nxt)  # dict 대신 문자열 위치로 매핑
                    buf.append(_ESCAPE_VALUES[pos] if pos >= 0 else nxt)
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    if i < n and not line[i].isspace():
                        raise ParseError("closing quote must be followed by a space")
                    break
                buf.append(ch)
                i += 1
            elif in_single:
                if i >= n:
                    raise ParseError("unbalanced quotes")
                ch = line[i]
                if ch == "\\" and i + 1 < n and line[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                if ch == "'":
                    i += 1
                    if i < n and not line[i].isspace():
                        raise ParseError("closing quote must be followed by a space")
                    break
                buf.append(ch)
                i += 1
            else:
                if i >= n or line[i].isspace():
                    break
                ch = line[i]
                if ch == '"' and not buf:
                    in_double = True
                elif ch == "'" and not buf:
                    in_single = True
                else:
                    buf.append(ch)
                i += 1
        tokens.append("".join(buf))
