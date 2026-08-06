from nishikihebi.chat.cli import run


class FakeSession:
    def __init__(self) -> None:
        self.questions = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return f"answer to {question}"


def test_run_answers_a_line_then_exits_on_eof(scripted_input):
    session = FakeSession()
    outputs = []

    run(session, input_fn=scripted_input("hello"), output=outputs.append)

    assert session.questions == ["hello"]
    assert outputs == ["answer to hello"]


def test_run_exits_on_slash_exit_command(scripted_input):
    session = FakeSession()
    outputs = []

    run(
        session,
        input_fn=scripted_input("/exit", "should not be reached"),
        output=outputs.append,
    )

    assert session.questions == []
    assert outputs == []


def test_run_forwards_bare_exit_and_quit_words(scripted_input):
    session = FakeSession()
    outputs = []

    run(session, input_fn=scripted_input("exit", "quit"), output=outputs.append)

    assert session.questions == ["exit", "quit"]


def test_run_skips_blank_lines(scripted_input):
    session = FakeSession()
    outputs = []

    run(session, input_fn=scripted_input("", "  ", "hi"), output=outputs.append)

    assert session.questions == ["hi"]
