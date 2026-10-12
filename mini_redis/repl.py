"""REPL (Read-Eval-Print Loop).

``mini-redis>`` 프롬프트를 띄우고 "입력 → 파싱/실행 → 출력"을 반복한다.

* 대화형 터미널이면 ``input()`` 으로 읽고, 가능하면 readline 으로 방향키 히스토리를 지원한다.
* 표준 입력이 파일/파이프이면(예: ``python main.py < examples/demo.txt``) 프롬프트와 명령을
  함께 출력해서 실제 세션과 같은 모양의 실행 기록(transcript)을 만든다.
* ``exit`` / ``quit`` / Ctrl+D(EOF) / Ctrl+C 로 종료한다.
"""

import sys
from typing import Optional, TextIO

from .server import Server

BANNER = "Mini Redis 1.0 — 'HELP' 로 명령어 목록, 'exit' 또는 'quit' 로 종료"


def run(server: Optional[Server] = None, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout,
        interactive: Optional[bool] = None) -> int:
    """REPL 을 실행하고 종료 코드를 반환한다."""
    server = server or Server()
    if interactive is None:
        interactive = stdin.isatty()
    if interactive:
        try:
            import readline  # noqa: F401  (방향키 히스토리, Windows 에는 없을 수 있음)
        except ImportError:
            pass
        print(BANNER, file=stdout)

    while True:
        prompt = server.prompt()
        try:
            if interactive:
                line = input(prompt)
            else:
                line = stdin.readline()
                if line == "":
                    break  # EOF
                line = line.rstrip("\n")
                print(prompt + line, file=stdout)
        except EOFError:
            print(file=stdout)
            break
        except KeyboardInterrupt:
            print(file=stdout)
            break

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # 빈 줄과 주석(# ...)은 무시 → 데모 스크립트에 설명을 달 수 있다
        if stripped.lower() in ("exit", "quit"):
            break
        output = server.execute_line(stripped)
        if output:
            print(output, file=stdout)
    return 0


def main() -> int:
    """콘솔 진입점. ``python main.py | head`` 처럼 출력이 중간에 끊겨도 조용히 종료한다."""
    import os
    try:
        return run()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
