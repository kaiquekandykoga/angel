from __future__ import annotations

from nishikihebi.cli import run


class FakeSession:
    def __init__(self) -> None:
        self.questions = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return f"answer to {question}"


def test_run_answers_a_line_then_exits_on_eof():
    session = FakeSession()
    inputs = iter(["hello"])
    outputs = []

    def input_fn(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    run(session, input_fn=input_fn, output=outputs.append)

    assert session.questions == ["hello"]
    assert outputs == ["answer to hello"]


def test_run_exits_on_slash_exit_command():
    session = FakeSession()
    inputs = iter(["/exit", "should not be reached"])
    outputs = []

    run(session, input_fn=lambda _="": next(inputs), output=outputs.append)

    assert session.questions == []
    assert outputs == []


def test_run_forwards_bare_exit_and_quit_words():
    session = FakeSession()
    inputs = iter(["exit", "quit"])

    def input_fn(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    outputs = []
    run(session, input_fn=input_fn, output=outputs.append)

    assert session.questions == ["exit", "quit"]


def test_run_skips_blank_lines():
    session = FakeSession()
    inputs = iter(["", "  ", "hi"])

    def input_fn(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    outputs = []
    run(session, input_fn=input_fn, output=outputs.append)

    assert session.questions == ["hi"]
