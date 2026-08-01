from __future__ import annotations


def run(session, input_fn=input, output=print) -> None:
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
