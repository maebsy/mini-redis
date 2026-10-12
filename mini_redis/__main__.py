"""``python -m mini_redis`` 진입점."""

import sys

from .repl import run

if __name__ == "__main__":
    sys.exit(run())
