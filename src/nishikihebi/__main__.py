import argparse
import logging
import sys
from collections.abc import Sequence
from typing import NoReturn

from nishikihebi.agents._shared import ItemFailure, Review
from nishikihebi.agents.chat import repl
from nishikihebi.agents.chat.graph import build_chat_graph
from nishikihebi.agents.chat.repl import start_session
from nishikihebi.agents.issue_review.graph import build_issue_review_graph
from nishikihebi.agents.pr_review.graph import build_pr_review_graph
from nishikihebi.clients.github import (
    DryRunGitHubClient,
    GitHubClient,
    MissingGitHubCredentialsError,
    build_github_client,
)
from nishikihebi.clients.llm import LlmClient, MissingApiKeyError, build_llm_client
from nishikihebi.logs import configure_logging

COMMANDS = ("chat", "pr_review", "issue_review")

DRY_RUN_HELP = "Print each review to stdout and make zero GitHub writes"

logger = logging.getLogger(__name__)


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, unknown_command_message: str, **kwargs) -> None:
        self._unknown_command_message = unknown_command_message
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        sys.exit(self._unknown_command_message)


def _build_parser(unknown_command_message: str) -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="nishikihebi",
        description="Chat with the model, or review labeled pull requests and issues.",
        epilog=(
            "Run 'nishikihebi help <command>' or 'nishikihebi <command> --help' "
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
        prog="nishikihebi chat",
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
        prog="nishikihebi pr_review",
        description="Review open pull requests labeled nishikihebi.",
        help="Review open pull requests labeled nishikihebi",
        unknown_command_message=unknown_command_message,
    )
    pr_review.add_argument(
        "--dry-run", action="store_true", default=argparse.SUPPRESS, help=DRY_RUN_HELP
    )

    issue_review = subparsers.add_parser(
        "issue_review",
        prog="nishikihebi issue_review",
        description="Review open issues labeled nishikihebi.",
        help="Review open issues labeled nishikihebi",
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


def report_failures(failures: list[ItemFailure], succeeded: int) -> None:
    if not failures:
        return
    for failure in failures:
        target = (
            failure.repository
            if failure.number == 0
            else f"{failure.repository}#{failure.number}"
        )
        print(
            f"Failed {failure.stage} for {target}: "
            f"{failure.error_type}: {failure.error}",
            file=sys.stderr,
        )
    never_reviewed = sum(
        1 for failure in failures if failure.stage != "post_review_comments"
    )
    total = succeeded + never_reviewed
    sys.exit(f"{len(failures)} of {total} items failed")


def _print_review(review: Review, dry_run: bool) -> None:
    target = review.target
    if dry_run:
        print(f"--- {target.repository}#{target.number} ---")
        print(review.body)
    else:
        print(f"Commented on {target.repository}#{target.number}")


def run_pr_review(
    client: LlmClient, github: GitHubClient, dry_run: bool = False
) -> None:
    graph = build_pr_review_graph(client, github)
    result = graph.invoke({"pull_requests": [], "reviews": [], "failures": []})
    if not result["reviews"]:
        print("No pull requests to review")
    else:
        for review in result["reviews"]:
            _print_review(review, dry_run)
    report_failures(result["failures"], len(result["reviews"]))


def run_issue_review(
    client: LlmClient, github: GitHubClient, dry_run: bool = False
) -> None:
    graph = build_issue_review_graph(client, github)
    result = graph.invoke({"issues": [], "reviews": [], "failures": []})
    if not result["reviews"]:
        print("No issues to review")
    else:
        for review in result["reviews"]:
            _print_review(review, dry_run)
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
    logger.info(
        f"running {command}",
        extra={
            "context": {
                "command": command,
                "log_path": str(log_path),
                "dry_run": dry_run,
            }
        },
    )

    try:
        client = build_llm_client()
        github = None if command == "chat" else build_github_client()
    except (MissingApiKeyError, MissingGitHubCredentialsError) as error:
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
