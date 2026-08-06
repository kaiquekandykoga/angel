import subprocess
import sys
from collections.abc import Callable, Sequence

CHECKS = (["ruff", "check"], ["basedpyright"], ["pytest"])


def run(call: Callable[[Sequence[str]], int] = subprocess.call) -> int:
    for check in CHECKS:
        result = call(check)
        if result != 0:
            return result
    return 0


def main() -> None:
    sys.exit(run())
