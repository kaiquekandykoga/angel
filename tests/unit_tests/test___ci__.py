import angel.__ci__


def test_run_runs_all_checks_in_order_and_returns_zero_when_all_pass():
    calls = []

    def fake_call(command):
        calls.append(command)
        return 0

    result = angel.__ci__.run(fake_call)

    assert result == 0
    assert calls == [["ruff", "check"], ["basedpyright"], ["pytest"]]


def test_run_stops_at_first_failing_check_and_returns_its_exit_code():
    calls = []

    def fake_call(command):
        calls.append(command)
        return 1 if command == ["ruff", "check"] else 0

    result = angel.__ci__.run(fake_call)

    assert result == 1
    assert calls == [["ruff", "check"]]
