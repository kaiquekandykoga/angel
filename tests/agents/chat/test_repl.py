from langchain_core.messages import SystemMessage

from nishikihebi.agents.chat.graph import build_chat_graph
from nishikihebi.agents.chat.repl import run, start_session


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


def test_ask_returns_client_reply(fake_client):
    fake_client.reply = "hello there"
    session = start_session(build_chat_graph(fake_client))

    answer = session.ask("hi")

    assert answer == "hello there"


def test_session_keeps_history_across_asks(fake_client):
    session = start_session(build_chat_graph(fake_client))

    session.ask("first")
    session.ask("second")

    last_call_contents = [m.content for m in fake_client.calls[-1]]
    assert "first" in last_call_contents
    assert "second" in last_call_contents


def test_system_prompt_is_not_accumulated_across_asks(fake_client):
    session = start_session(build_chat_graph(fake_client))

    session.ask("first")
    session.ask("second")

    system_messages = [m for m in fake_client.calls[-1] if isinstance(m, SystemMessage)]
    assert len(system_messages) == 1


def test_two_sessions_have_independent_history(fake_client):
    session_a = start_session(build_chat_graph(fake_client))
    session_b = start_session(build_chat_graph(fake_client))

    session_a.ask("from a")
    session_b.ask("from b")

    last_call_contents = [m.content for m in fake_client.calls[-1]]
    assert "from a" not in last_call_contents
    assert "from b" in last_call_contents
