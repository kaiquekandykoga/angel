from langchain_core.messages import SystemMessage

from nishikihebi.chat.session import start_session
from nishikihebi.graph import build_graph


def test_ask_returns_model_reply(fake_model):
    fake_model.reply = "hello there"
    session = start_session(build_graph(fake_model))

    answer = session.ask("hi")

    assert answer == "hello there"


def test_session_keeps_history_across_asks(fake_model):
    session = start_session(build_graph(fake_model))

    session.ask("first")
    session.ask("second")

    last_call_contents = [m.content for m in fake_model.calls[-1]]
    assert "first" in last_call_contents
    assert "second" in last_call_contents


def test_system_prompt_is_not_accumulated_across_asks(fake_model):
    session = start_session(build_graph(fake_model))

    session.ask("first")
    session.ask("second")

    system_messages = [m for m in fake_model.calls[-1] if isinstance(m, SystemMessage)]
    assert len(system_messages) == 1


def test_two_sessions_have_independent_history(fake_model):
    session_a = start_session(build_graph(fake_model))
    session_b = start_session(build_graph(fake_model))

    session_a.ask("from a")
    session_b.ask("from b")

    last_call_contents = [m.content for m in fake_model.calls[-1]]
    assert "from a" not in last_call_contents
    assert "from b" in last_call_contents
