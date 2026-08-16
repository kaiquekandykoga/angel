from typing import TextIO

from nishikihebi.env import load_env_var

RESET = "0"
BOLD = "1"
DIM = "2"
RED = "31"
GREEN = "32"
YELLOW = "33"
BLUE = "34"
MAGENTA = "35"
CYAN = "36"

_SECTION_WIDTH = 72


def color_enabled(stream: TextIO) -> bool:
    if load_env_var("NO_COLOR"):
        return False

    match (load_env_var("NISHIKIHEBI_COLOR") or "").strip().lower():
        case "never":
            return False
        case "always":
            return True

    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def style(text: str, *codes: str, stream: TextIO) -> str:
    if not codes or not color_enabled(stream):
        return text
    return f"\x1b[{';'.join(codes)}m{text}\x1b[{RESET}m"


def section(title: str, *, stream: TextIO) -> None:
    if len(title) >= _SECTION_WIDTH:
        heading = f"{title} "
    else:
        rule = "─" * (_SECTION_WIDTH - len(title) - 1)
        heading = f"{title} {rule}"
    print(file=stream)
    print(style(heading, BOLD, CYAN, stream=stream), file=stream)
