import logging

import pytest

from nishikihebi.agents._shared import (
    Finding,
    ItemFailure,
    Severity,
    collect_failures,
    log_review_produced,
)
from nishikihebi.logs import get_logger


def test_collect_failures_no_exception_appends_nothing_and_leaves_scope_unfailed(
    caplog,
):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    failures: list[ItemFailure] = []

    with collect_failures(
        failures, "failed to do thing", stage="a_stage", repository="org/a", number=1
    ) as scope:
        pass

    assert failures == []
    assert scope.failed is False
    assert caplog.records == []


def test_collect_failures_catches_exception_logs_and_appends_failure(caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    failures: list[ItemFailure] = []
    error = ValueError("boom")

    with collect_failures(
        failures, "failed to do thing", stage="a_stage", repository="org/a", number=1
    ) as scope:
        raise error

    assert scope.failed is True
    assert failures == [
        ItemFailure(
            repository="org/a",
            number=1,
            stage="a_stage",
            error_type="ValueError",
            error="boom",
        )
    ]
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    record = warning_records[0]
    assert record.message == "failed to do thing"
    assert record.context == {
        "repository": "org/a",
        "number": 1,
        "stage": "a_stage",
        "error_type": "ValueError",
        "error": "boom",
    }


def test_collect_failures_lets_base_exception_propagate():
    failures: list[ItemFailure] = []

    with (
        pytest.raises(KeyboardInterrupt),
        collect_failures(
            failures,
            "failed to do thing",
            stage="a_stage",
            repository="org/a",
            number=1,
        ),
    ):
        raise KeyboardInterrupt


def test_log_review_produced_with_mixed_severities(caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    log = get_logger("nishikihebi.test")
    findings = [
        Finding(severity=Severity.BLOCKER, title="a", detail="a detail"),
        Finding(severity=Severity.MINOR, title="b", detail="b detail"),
        Finding(severity=Severity.MINOR, title="c", detail="c detail"),
    ]

    log_review_produced(
        log, repository="org/a", number=1, review="review body", findings=findings
    )

    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert len(debug_records) == 1
    record = debug_records[0]
    assert record.message == "review produced"
    assert record.name == "nishikihebi.test"
    assert record.context == {
        "repository": "org/a",
        "number": 1,
        "review": "review body",
        "finding_count": 3,
        "severity_counts": {"blocker": 1, "minor": 2},
    }


def test_log_review_produced_with_no_findings(caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    log = get_logger("nishikihebi.test")

    log_review_produced(
        log, repository="org/a", number=1, review="review body", findings=[]
    )

    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert len(debug_records) == 1
    assert debug_records[0].context == {
        "repository": "org/a",
        "number": 1,
        "review": "review body",
        "finding_count": 0,
        "severity_counts": {},
    }
