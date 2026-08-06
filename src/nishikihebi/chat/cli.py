from collections.abc import Callable

from nishikihebi.chat.session import Session


def run(
    session: Session,
    input_fn: Callable[[str], str] = input,
    output: Callable[[str], None] = print,
) -> None:
    while True:
        try:
            line = input_fn("> ")
        except EOFError:
            return

        question = line.strip()
        if not question:
            continue
        if question == "/exit":
            return

        output(session.ask(question))
