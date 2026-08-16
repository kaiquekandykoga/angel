import logging
import sys
from collections.abc import Sequence

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

logger = logging.getLogger(__name__)


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
    dry_run = "--dry-run" in argv
    remaining = [arg for arg in argv if arg != "--dry-run"]
    if len(remaining) != 1 or remaining[0] not in COMMANDS:
        given = " ".join(argv) or "(none)"
        sys.exit(f"Unknown command: {given}. Valid commands: {', '.join(COMMANDS)}")

    command = remaining[0]
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
