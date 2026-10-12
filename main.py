"""Mini Redis 실행 파일: ``python main.py``"""

import sys

from mini_redis.repl import run

if __name__ == "__main__":
    sys.exit(run())
