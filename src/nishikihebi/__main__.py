import logging
import sys
from collections.abc import Sequence

from nishikihebi.agents._shared import ItemFailure
from nishikihebi.agents.chat import repl
from nishikihebi.agents.chat.graph import build_chat_graph
from nishikihebi.agents.chat.repl import start_session
from nishikihebi.agents.issue_review.graph import build_issue_review_graph
from nishikihebi.agents.pr_review.graph import build_pr_review_graph
from nishikihebi.clients.github import (
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


def run_pr_review(client: LlmClient, github: GitHubClient) -> None:
    graph = build_pr_review_graph(client, github)
    result = graph.invoke({"pull_requests": [], "reviews": [], "failures": []})
    if not result["reviews"]:
        print("No pull requests to review")
    else:
        for review in result["reviews"]:
            pull_request = review.target
            print(f"Commented on {pull_request.repository}#{pull_request.number}")
    report_failures(result["failures"], len(result["reviews"]))


def run_issue_review(client: LlmClient, github: GitHubClient) -> None:
    graph = build_issue_review_graph(client, github)
    result = graph.invoke({"issues": [], "reviews": [], "failures": []})
    if not result["reviews"]:
        print("No issues to review")
    else:
        for review in result["reviews"]:
            issue = review.target
            print(f"Commented on {issue.repository}#{issue.number}")
    report_failures(result["failures"], len(result["reviews"]))


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in COMMANDS:
        given = " ".join(argv) or "(none)"
        sys.exit(f"Unknown command: {given}. Valid commands: {', '.join(COMMANDS)}")

    command = argv[0]
    log_path = configure_logging()
    logger.info(
        f"running {command}",
        extra={"context": {"command": command, "log_path": str(log_path)}},
    )

    try:
        client = build_llm_client()
        github = None if command == "chat" else build_github_client()
    except (MissingApiKeyError, MissingGitHubCredentialsError) as error:
        sys.exit(str(error))

    if github is None:
        run_chat(client)
    elif command == "pr_review":
        run_pr_review(client, github)
    else:
        run_issue_review(client, github)


if __name__ == "__main__":
    main()
