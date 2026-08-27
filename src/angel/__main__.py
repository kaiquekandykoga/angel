import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from angel.agents._shared import ItemFailure, Review
from angel.agents.chat import repl
from angel.agents.chat.graph import build_chat_graph
from angel.agents.chat.repl import start_session
from angel.agents.issue_review.graph import build_issue_review_graph
from angel.agents.pr_review.graph import build_pr_review_graph
from angel.clients.github import (
    DryRunGitHubClient,
    GitHubClient,
    MissingGitHubCredentialsError,
    build_github_client,
)
from angel.clients.llm import (
    InvalidMaxCompletionTokensError,
    LlmClient,
    MissingApiKeyError,
    build_llm_client,
    reset_usage,
    usage_totals,
)
from angel.console import BOLD, DIM, GREEN, RED, section, style
from angel.logs import configure_logging, get_logger

COMMANDS = ("chat", "pr_review", "issue_review")

DRY_RUN_HELP = "Print each review to stdout and make zero GitHub writes"

log = get_logger(__name__)


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, unknown_command_message: str, **kwargs) -> None:
        self._unknown_command_message = unknown_command_message
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        sys.exit(self._unknown_command_message)


def _build_parser(unknown_command_message: str) -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="angel",
        description="Chat with the model, or review labeled pull requests and issues.",
        epilog=(
            "Run 'angel help <command>' or 'angel <command> --help' "
            "for the options of one command."
        ),
        unknown_command_message=unknown_command_message,
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help=DRY_RUN_HELP
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>",
                                       required=True)

    chat = subparsers.add_parser(
        "chat",
        prog="angel chat",
        description="Start an interactive chat session with the model.",
        help="Interactive REPL against the model",
        unknown_command_message=unknown_command_message,
    )
    chat.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    pr_review = subparsers.add_parser(
        "pr_review",
        prog="angel pr_review",
        description="Review open pull requests labeled angel.",
        help="Review open pull requests labeled angel",
        unknown_command_message=unknown_command_message,
    )
    pr_review.add_argument(
        "--dry-run", action="store_true", default=argparse.SUPPRESS, help=DRY_RUN_HELP
    )

    issue_review = subparsers.add_parser(
        "issue_review",
        prog="angel issue_review",
        description="Review open issues labeled angel.",
        help="Review open issues labeled angel",
        unknown_command_message=unknown_command_message,
    )
    issue_review.add_argument(
        "--dry-run", action="store_true", default=argparse.SUPPRESS, help=DRY_RUN_HELP
    )

    return parser


def run_chat(client: LlmClient) -> None:
    graph = build_chat_graph(client)
    session = start_session(graph)
    repl.run(session)
    _print_usage_section()


def report_failures(failures: list[ItemFailure], succeeded: int) -> None:
    if not failures:
        return
    section("Failures", stream=sys.stderr)
    print(file=sys.stderr)
    for failure in failures:
        target = (
            failure.repository
            if failure.number == 0
            else f"{failure.repository}#{failure.number}"
        )
        print(
            style(
                f"Failed {failure.stage} for {target}: "
                f"{failure.error_type}: {failure.error}",
                RED,
                stream=sys.stderr,
            ),
            file=sys.stderr,
        )
    never_reviewed = sum(
        1 for failure in failures if failure.stage != "post_review_comments"
    )
    total = succeeded + never_reviewed
    sys.exit(f"{len(failures)} of {total} items failed")


def _print_run_section(command: str, dry_run: bool, log_path: Path) -> None:
    section("Run", stream=sys.stdout)
    print()
    print(f"  {'command':<7}   {command}")
    print(f"  {'dry run':<7}   {'yes' if dry_run else 'no'}")
    print(f"  {'log':<7}   {log_path}")


def _print_usage_section() -> None:
    totals = usage_totals()
    section("Usage", stream=sys.stdout)
    print()
    print(f"  {'calls':<13}{totals.calls:>9,}")
    print(f"  {'input_tokens':<13}{totals.input_tokens:>9,}")
    print(f"  {'output_tokens':<13}{totals.output_tokens:>9,}")
    print(f"  {'total_tokens':<13}{totals.total_tokens:>9,}")
    print(f"  {'duration_ms':<13}{totals.duration_ms:>9.1f}")


def _print_reviews(reviews: list[Review], dry_run: bool, nothing_message: str) -> None:
    section("Reviews", stream=sys.stdout)
    print()
    if not reviews:
        print(style(nothing_message, DIM, stream=sys.stdout))
        return
    for review in reviews:
        target = review.target
        label = f"{target.repository}#{target.number}"
        if dry_run:
            print(style(label, BOLD, stream=sys.stdout))
            print(review.body)
            print()
        else:
            print(style(f"  Commented on {label}", GREEN, stream=sys.stdout))


def run_pr_review(
    client: LlmClient, github: GitHubClient, dry_run: bool = False
) -> None:
    graph = build_pr_review_graph(client, github)
    result = graph.invoke({"pull_requests": [], "reviews": [], "failures": []})
    _print_reviews(result["reviews"], dry_run, "No pull requests to review")
    _print_usage_section()
    report_failures(result["failures"], len(result["reviews"]))


def run_issue_review(
    client: LlmClient, github: GitHubClient, dry_run: bool = False
) -> None:
    graph = build_issue_review_graph(client, github)
    result = graph.invoke({"issues": [], "reviews": [], "failures": []})
    _print_reviews(result["reviews"], dry_run, "No issues to review")
    _print_usage_section()
    report_failures(result["failures"], len(result["reviews"]))


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    given = " ".join(argv) or "(none)"
    unknown_command_message = (
        f"Unknown command: {given}. Valid commands: {', '.join(COMMANDS)}"
    )
    parser = _build_parser(unknown_command_message)

    if not argv or argv[:1] == ["help"]:
        rest = argv[1:]
        if not rest:
            parser.parse_args(["--help"])
        if len(rest) != 1 or rest[0] not in COMMANDS:
            sys.exit(unknown_command_message)
        parser.parse_args([rest[0], "--help"])

    args = parser.parse_args(argv)
    command = args.command
    dry_run = args.dry_run
    if dry_run and command == "chat":
        sys.exit("--dry-run is not valid for chat: chat makes no GitHub writes")

    log_path = configure_logging()
    log.info(
        f"running {command}",
        command=command,
        log_path=str(log_path),
        dry_run=dry_run,
    )
    reset_usage()
    _print_run_section(command, dry_run, log_path)

    try:
        client = build_llm_client()
        github = None if command == "chat" else build_github_client()
    except (
        MissingApiKeyError,
        InvalidMaxCompletionTokensError,
        MissingGitHubCredentialsError,
    ) as error:
        sys.exit(str(error))

    if github is None:
        run_chat(client)
    else:
        if dry_run:
            github = DryRunGitHubClient(github)
        if command == "pr_review":
            run_pr_review(client, github, dry_run)
        else:
            run_issue_review(client, github, dry_run)


if __name__ == "__main__":
    main()
